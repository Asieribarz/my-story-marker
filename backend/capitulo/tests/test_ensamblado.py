"""El Recuperador: V-3a, V-4, V-5 y V-23 sobre la biblia de referencia (RF-50 a RF-59b)."""

import hashlib
import json
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.capitulo import ensamblado, estimador, similitud
from backend.capitulo.ensamblado import ErrorEnsamblado, PromptPreparado, preparar_prompt
from backend.capitulo.tests.referencia import MOMENTO, biblia_de_referencia, verificar
from backend.escaleta.consultas import guardar_escaleta
from backend.escaleta.modelos import SalidaEscaletista
from backend.escaleta.tests.referencia import salida_escaletista
from backend.shared.rutas import DisposicionProyecto

ID = "0123456789abcdef0123456789abcdef"
PARRAFO = "Aitana cruzó el bosque de hayas con la brújula en la mano y Nala detrás. "


@contextmanager
def proyecto() -> Iterator[tuple[sqlite3.Connection, DisposicionProyecto]]:
    with tempfile.TemporaryDirectory() as carpeta:
        disposicion = DisposicionProyecto.de(ID, Path(carpeta))
        disposicion.crear_directorios()
        conexion = biblia_de_referencia(disposicion.base)
        try:
            yield conexion, disposicion
        finally:
            conexion.close()


def aprobar(
    conexion: sqlite3.Connection, disposicion: DisposicionProyecto, n: int, texto: str
) -> None:
    verificar(conexion, n)
    conexion.execute(
        "UPDATE capitulo SET estado = 'aprobado', version_vigente = 1 WHERE numero = ?", (n,)
    )
    ruta = disposicion.capitulo(n, 1, 1)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(texto.encode("utf-8"))


def ficheros(preparado: PromptPreparado) -> list[bytes]:
    rutas = [*preparado.rutas_partes, preparado.ruta_completa, preparado.ruta_desglose]
    return [r.read_bytes() for r in rutas]


def pasajes(n: int, tamano: int) -> tuple[similitud.Fragmento, ...]:
    return tuple(similitud.Fragmento(c, 1, 1.0, PARRAFO * tamano) for c in range(1, n + 1))


# ─── V-3a: misma entrada, mismos bytes ───────────────────────────────────────


@settings(max_examples=5, deadline=None)
@given(
    numero=st.integers(1, 10),
    informe=st.one_of(st.none(), st.text(max_size=200)),
    aprobados=st.sets(st.integers(1, 9), max_size=3),
)
def test_misma_entrada_mismos_bytes(numero: int, informe: str | None, aprobados: set[int]) -> None:
    salidas = []
    for _ in range(2):
        with proyecto() as (conexion, disposicion):
            for n in sorted(aprobados):
                aprobar(conexion, disposicion, n, f"# Capítulo {n}\n\n{PARRAFO}\r\n")
            salidas.append(
                ficheros(preparar_prompt(conexion, disposicion, numero, 1, 1, informe, MOMENTO))
            )
    assert salidas[0] == salidas[1]


# ─── V-5: nunca se pasa del tope; todo recorte declarado; unidades enteras ────


@settings(max_examples=8, deadline=None)
@given(
    tope=st.integers(1200, 6000),
    informe=st.integers(0, 60),
    anterior=st.integers(0, 120),
    fragmentos=st.integers(0, 6),
    tamano=st.integers(1, 25),
)
def test_el_recorte_cabe_se_declara_y_no_corta_unidades(
    tope: int, informe: int, anterior: int, fragmentos: int, tamano: int
) -> None:
    unidades = pasajes(fragmentos, tamano)
    with (
        proyecto() as (conexion, disposicion),
        patch.object(ensamblado, "TOPE", tope),
        patch.object(ensamblado, "LIMITE_PARTE", 700),
        patch.object(similitud, "buscar", lambda *_: unidades),
    ):
        aprobar(conexion, disposicion, 5, "# Cinco\n\n" + "\n\n".join([PARRAFO] * anterior))
        preparado = preparar_prompt(conexion, disposicion, 6, 1, 1, PARRAFO * informe, MOMENTO)
        texto = preparado.ruta_completa.read_text(encoding="utf-8")
        desglose = json.loads(preparado.ruta_desglose.read_text(encoding="utf-8"))

        assert preparado.tokens_estimados == estimador.estimar_tokens(texto) <= tope
        partes = [r.read_text(encoding="utf-8") for r in preparado.rutas_partes]
        assert "".join(partes) == texto
        assert all(estimador.estimar_tokens(p) <= 700 for p in partes)
        recortados = {r["bloque"] for r in desglose["recortes"]}
        for bloque in desglose["bloques"]:
            cabecera = f"## {bloque['titulo']}\n"
            assert (bloque["id"] in recortados) == bloque["recortado"]
            if bloque["tokens"] == 0:  # fuera entero
                assert cabecera not in texto and bloque["recortado"]
            else:
                assert cabecera in texto
        emitidos = [f["emitido"] for f in desglose["similitud"]]
        assert emitidos == sorted(emitidos, reverse=True)  # caen desde la cola del ranking
        for fragmento, unidad in zip(desglose["similitud"], unidades, strict=True):
            procedencia = f"Procedencia: capítulo {unidad.capitulo}, fragmento 1."
            entero = procedencia + "\n\n" + unidad.texto.strip()
            assert (entero in texto) == fragmento["emitido"]
            assert (f"capítulo {unidad.capitulo}, fragmento" in texto) == fragmento["emitido"]
        # Sin recortes, el prompt es el que habría salido sin tope.
        with patch.object(ensamblado, "TOPE", 10**9):
            completo = preparar_prompt(conexion, disposicion, 6, 1, 2, PARRAFO * informe, MOMENTO)
        excede = completo.tokens_estimados > tope
        assert bool(desglose["recortes"]) == excede
        assert ("## Omitido por espacio" in texto) == excede


def test_si_ni_la_ficha_cabe_no_cabe_con_desglose() -> None:
    with proyecto() as (conexion, disposicion), patch.object(ensamblado, "TOPE", 50):
        with pytest.raises(ErrorEnsamblado) as error:
            preparar_prompt(conexion, disposicion, 1, 1, 1, None, MOMENTO)
    assert error.value.causa == "no_cabe"
    assert {r["bloque"] for r in error.value.detalle["recortes"]} >= {"guia", "presentes"}


def test_un_prompt_de_cien_mil_tokens_se_parte_en_trozos_de_veinte_mil() -> None:
    with proyecto() as (conexion, disposicion):
        aprobar(conexion, disposicion, 1, "\n\n".join([PARRAFO * 5] * 500))
        preparado = preparar_prompt(conexion, disposicion, 2, 1, 1, None, MOMENTO)
        desglose = json.loads(preparado.ruta_desglose.read_text(encoding="utf-8"))
    assert 60_000 < preparado.tokens_estimados <= ensamblado.TOPE
    assert len(preparado.rutas_partes) >= 3
    assert all(p["tokens"] <= ensamblado.LIMITE_PARTE for p in desglose["partes"])


# ─── V-23: el vacío es asimétrico ────────────────────────────────────────────


def test_similitud_vacia_sin_encabezado_ni_recorte() -> None:
    assert similitud.buscar(sqlite3.connect(":memory:"), similitud.Consulta("", (), "x", 1)) == ()
    with proyecto() as (conexion, disposicion):
        preparado = preparar_prompt(conexion, disposicion, 3, 1, 1, None, MOMENTO)
        texto = preparado.ruta_completa.read_text(encoding="utf-8")
        desglose = json.loads(preparado.ruta_desglose.read_text(encoding="utf-8"))
    assert "Pasajes" not in texto and ensamblado.ENCABEZADO_PASAJES not in texto
    assert desglose["recortes"] == [] and desglose["similitud"] == []
    assert "## Resumen acumulado\n\nNinguno." in texto  # opcional vacío: no es recorte


def test_control_con_pasajes_hay_encabezado_y_procedencia() -> None:
    with (
        proyecto() as (conexion, disposicion),
        patch.object(similitud, "buscar", lambda *_: pasajes(2, 1)),
    ):
        texto = preparar_prompt(conexion, disposicion, 3, 1, 1, None, MOMENTO).ruta_completa
        contenido = texto.read_text(encoding="utf-8")
    assert ensamblado.ENCABEZADO_PASAJES in contenido
    assert "Procedencia: capítulo 2, fragmento 1." in contenido


def test_estructurada_vacia_aborta_con_mensaje_accionable() -> None:
    with proyecto() as (conexion, disposicion):
        conexion.execute("DELETE FROM guia_estilo")
        with pytest.raises(ErrorEnsamblado) as error:
            preparar_prompt(conexion, disposicion, 3, 1, 1, None, MOMENTO)
    assert error.value.causa == "inconsistencia"
    assert error.value.detalle["bloque"] == "guia"
    assert "planificación" in error.value.detalle["motivo"]


def test_b9_inconsistencia_antes_de_ensamblar() -> None:
    salida = salida_escaletista()
    salida["fichas"][4]["dia"] = 1  # el capítulo 4 termina en D2: el día retrocede
    with proyecto() as (conexion, disposicion):
        guardar_escaleta(conexion, SalidaEscaletista.model_validate(salida))
        with pytest.raises(ErrorEnsamblado) as error:
            preparar_prompt(conexion, disposicion, 5, 1, 1, None, MOMENTO)
        assert not disposicion.prompt(5, 1, 1).exists()
        preparar_prompt(conexion, disposicion, 4, 1, 1, None, MOMENTO)  # control
    assert error.value.causa == "inconsistencia"
    assert error.value.detalle["hallazgos"][0]["regla"] == "RF-76 · dia_retrocede"


# ─── V-4: de un hallazgo al prompt exacto ────────────────────────────────────


def test_del_hallazgo_al_fichero_de_prompt() -> None:
    with proyecto() as (conexion, disposicion):
        preparado = preparar_prompt(conexion, disposicion, 2, 1, 3, "Longitud: corto.", MOMENTO)
        # Un hallazgo de informe lleva su capítulo, versión e intento (capitulo_version).
        capitulo, version, intento = 2, 1, 3
        desglose = json.loads(
            disposicion.desglose(capitulo, version, intento).read_text(encoding="utf-8")
        )
        prompt = disposicion.absoluta(desglose["prompt"])
        assert prompt == preparado.ruta_completa.resolve()
        assert hashlib.sha256(prompt.read_bytes()).hexdigest() == desglose["sha256"]
        assert [disposicion.absoluta(p["ruta"]) for p in desglose["partes"]] == [
            r.resolve() for r in preparado.rutas_partes
        ]
        assert "Longitud: corto." in prompt.read_text(encoding="utf-8")
