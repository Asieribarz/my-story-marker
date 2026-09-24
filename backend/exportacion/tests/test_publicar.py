"""RF-93 a RF-98 y V-30: publicar la versión N+1. El PDF lo imprime una impresora falsa;
el real está en test_pdf.py. Datos ficticios."""

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from backend.exportacion.manejadores import MANEJADORES
from backend.exportacion.publicar import (
    ErrorPublicacion,
    publicar_con,
    versiones_publicadas,
)
from backend.exportacion.tests.apoyo import (
    METADATOS,
    contrato_lectura,
    escribir_version,
    impresora_falsa,
    proyecto_listo,
)
from backend.proyecto.manejadores import OrdenNoEmitible
from backend.proyecto.maquina import TipoDesenlace
from backend.shared.rutas import (
    CRONOLOGIA,
    FICHEROS_DE_VERSION,
    LECTURA_JSON,
    PDF,
    DisposicionProyecto,
)
from backend.shared.tipos import Agente

MOMENTO_1 = "2026-09-23T12:00:00Z"
MOMENTO_2 = "2026-09-24T12:00:00Z"


@pytest.fixture
def listo(tmp_path: Path) -> Iterator[tuple[sqlite3.Connection, DisposicionProyecto]]:
    conexion, disposicion = proyecto_listo(tmp_path)
    yield conexion, disposicion
    conexion.close()


def _publicar(conexion: sqlite3.Connection, disposicion: DisposicionProyecto, m: str) -> int:
    return publicar_con(conexion, disposicion, METADATOS, m, impresora_falsa)


def _lectura(disposicion: DisposicionProyecto, version: int) -> dict[str, Any]:
    ruta = disposicion.fichero_de_version(version, LECTURA_JSON)
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


@pytest.mark.parametrize(
    "estado", ["capitulos", "verificacion_manuscrito", "aprobacion_final", "publicada"]
)
def test_rf93_fuera_de_publicacion_falla(
    listo: tuple[sqlite3.Connection, DisposicionProyecto], estado: str
) -> None:
    conexion, disposicion = listo
    conexion.execute("UPDATE proyecto SET estado = ?", (estado,))
    with pytest.raises(ErrorPublicacion):
        _publicar(conexion, disposicion, MOMENTO_1)
    assert conexion.execute("SELECT count(*) FROM version_novela").fetchone()[0] == 0
    assert list(disposicion.export.iterdir()) == []


def test_control_rf93_desde_publicacion_publica(
    listo: tuple[sqlite3.Connection, DisposicionProyecto],
) -> None:
    conexion, disposicion = listo
    assert _publicar(conexion, disposicion, MOMENTO_1) == 1
    assert {p.name for p in disposicion.version_novela(1).iterdir()} == FICHEROS_DE_VERSION - {
        CRONOLOGIA
    }
    assert [p.name for p in disposicion.export.iterdir()] == ["v1"]  # sin temporales


def test_rn8_un_capitulo_sin_aprobar_no_se_publica(
    listo: tuple[sqlite3.Connection, DisposicionProyecto],
) -> None:
    conexion, disposicion = listo
    conexion.execute("UPDATE capitulo_version SET estado = 'verificado' WHERE capitulo = 4")
    with pytest.raises(ErrorPublicacion, match=r"\[4\]"):
        _publicar(conexion, disposicion, MOMENTO_1)


def test_lectura_json_cumple_el_contrato_del_frontend(
    listo: tuple[sqlite3.Connection, DisposicionProyecto],
) -> None:
    conexion, disposicion = listo
    _publicar(conexion, disposicion, MOMENTO_1)
    escribir_version(conexion, disposicion, 3, 2)
    escribir_version(conexion, disposicion, 7, 2)
    _publicar(conexion, disposicion, MOMENTO_2)
    v1, v2 = _lectura(disposicion, 1), _lectura(disposicion, 2)
    assert contrato_lectura(v1) == [] and contrato_lectura(v2) == []
    assert set(v2) == {
        "version",
        "anterior",
        "cambiados",
        "portada",
        "capitulos",
        "personajes",
        "lugares",
    }
    assert (v1["anterior"], v1["cambiados"]) == (None, [])
    assert (v2["version"], v2["anterior"], v2["cambiados"]) == (2, 1, [3, 7])
    assert v2["portada"]["titulo"] == METADATOS.titulo
    assert "versión 2" in v2["capitulos"][2]["html"] and "versión 1" in v2["capitulos"][3]["html"]
    presentes = conexion.execute(
        "SELECT personaje, group_concat(capitulo) FROM ("
        "SELECT personaje, capitulo FROM ficha_capitulo_personaje WHERE papel = 'presente' "
        "ORDER BY capitulo) GROUP BY personaje"
    ).fetchall()
    for fila in presentes:
        ficha = next(p for p in v2["personajes"] if p["id"] == fila[0])
        assert ficha["capitulos"] == [int(c) for c in fila[1].split(",")]
    for p in v2["personajes"]:
        assert not {"deseo", "necesidad", "herida", "defecto"} & set(p)
    html = disposicion.fichero_de_version(2, "lectura.html").read_text(encoding="utf-8")
    assert 'id="novedades"' in html and 'href="#cap-03"' in html and 'id="cap-10"' in html
    assert 'id="novedades"' not in disposicion.fichero_de_version(1, "lectura.html").read_text(
        encoding="utf-8"
    )
    versiones = versiones_publicadas(conexion)
    assert [(v.version, v.publicada, list(v.cambiados)) for v in versiones] == [
        (1, MOMENTO_1, []),
        (2, MOMENTO_2, [3, 7]),
    ]


def test_metadatos_y_manuscrito(listo: tuple[sqlite3.Connection, DisposicionProyecto]) -> None:
    conexion, disposicion = listo
    _publicar(conexion, disposicion, MOMENTO_1)
    meta = json.loads(disposicion.fichero_de_version(1, "metadatos.json").read_text("utf-8"))
    assert meta["titulo"] == METADATOS.titulo and meta["version"] == 1
    assert meta["serie"] is None and len(meta["palabras_clave"]) == 5
    md = disposicion.fichero_de_version(1, "manuscrito.md").read_text(encoding="utf-8")
    assert md.startswith(f"# {METADATOS.titulo}\n") and md.count("\n## ") == 10


def test_copia_la_cronologia_de_la_ultima_pasada(
    listo: tuple[sqlite3.Connection, DisposicionProyecto],
) -> None:
    conexion, disposicion = listo
    conexion.execute("UPDATE proyecto SET pasadas = 2")
    lean = disposicion.cronologia_de_pasada(2)
    lean.parent.mkdir(parents=True)
    lean.write_bytes(b"import Cronologia\n")
    _publicar(conexion, disposicion, MOMENTO_1)
    assert disposicion.fichero_de_version(1, CRONOLOGIA).read_bytes() == b"import Cronologia\n"


def test_sin_pdf_no_queda_nada_a_medias(
    listo: tuple[sqlite3.Connection, DisposicionProyecto],
) -> None:
    conexion, disposicion = listo

    def sin_navegador(html: Path, destino: Path) -> None:
        raise OrdenNoEmitible("pdf_no_disponible", None, {})

    with pytest.raises(OrdenNoEmitible) as error:
        publicar_con(conexion, disposicion, METADATOS, MOMENTO_1, sin_navegador)
    assert error.value.causa == "pdf_no_disponible"
    assert list(disposicion.export.iterdir()) == []
    assert conexion.execute("SELECT count(*) FROM version_novela").fetchone()[0] == 0


def test_un_export_sin_fila_no_es_version_y_se_sustituye(
    listo: tuple[sqlite3.Connection, DisposicionProyecto],
) -> None:
    conexion, disposicion = listo
    huerfano = disposicion.version_novela(1)
    huerfano.mkdir()
    (huerfano / PDF).write_bytes(b"resto")
    _publicar(conexion, disposicion, MOMENTO_1)
    assert (huerfano / PDF).read_bytes() != b"resto"


# ─── V-30 ────────────────────────────────────────────────────────────────────


def _huella(conexion: sqlite3.Connection, disposicion: DisposicionProyecto, v: int) -> object:
    filas = conexion.execute(
        "SELECT n.numero, n.cambio, n.publicada, c.capitulo, c.capitulo_version "
        "FROM version_novela n JOIN version_novela_capitulo c ON c.version_novela = n.numero "
        "WHERE n.numero = ? ORDER BY c.capitulo",
        (v,),
    ).fetchall()
    ficheros = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(disposicion.version_novela(v).iterdir())
    }
    return [tuple(f) for f in filas], ficheros


@settings(
    max_examples=6,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    st.lists(st.sets(st.integers(min_value=1, max_value=10), max_size=4), min_size=1, max_size=3)
)
def test_v30_publicar_nunca_modifica_versiones_anteriores(
    tmp_path_factory: pytest.TempPathFactory, cambios: list[set[int]]
) -> None:
    """V-30 (RF-95, RN-9): para cualquier secuencia de publicaciones, las filas y los
    ficheros de toda versión anterior son idénticos antes y después."""
    conexion, disposicion = proyecto_listo(tmp_path_factory.mktemp("v30"))
    try:
        vigentes = dict.fromkeys(range(1, 11), 1)
        _publicar(conexion, disposicion, MOMENTO_1)
        huellas: dict[int, object] = {1: _huella(conexion, disposicion, 1)}
        for paso, capitulos in enumerate(cambios, start=2):
            for n in sorted(capitulos):
                vigentes[n] += 1
                escribir_version(conexion, disposicion, n, vigentes[n])
            conexion.execute("UPDATE proyecto SET estado = 'publicacion'")
            numero = _publicar(conexion, disposicion, f"2026-10-0{paso}T00:00:00Z")
            assert numero == paso
            assert _lectura(disposicion, numero)["cambiados"] == sorted(capitulos)
            for anterior, huella in huellas.items():
                assert _huella(conexion, disposicion, anterior) == huella
            huellas[numero] = _huella(conexion, disposicion, numero)
        with pytest.raises(sqlite3.DatabaseError):
            conexion.execute("UPDATE version_novela_capitulo SET capitulo_version = 1")
    finally:
        conexion.close()


# ─── Manejador ───────────────────────────────────────────────────────────────


class _Proyecto:
    def __init__(self, conexion: sqlite3.Connection, disposicion: DisposicionProyecto) -> None:
        self.conexion = conexion
        self.disposicion = disposicion


class _Contexto:
    def __init__(self, conexion: sqlite3.Connection, disposicion: DisposicionProyecto) -> None:
        self.conexion = conexion
        self.proyecto = _Proyecto(conexion, disposicion)
        self.momento = MOMENTO_1


@pytest.mark.parametrize(
    "salida",
    [
        {"titulo": "T", "sinopsis": "S"},
        {"titulo": "T", "sinopsis": "S", "palabras_clave": ["a", "b"]},
        {"titulo": "T", "sinopsis": "S", "palabras_clave": list("abcde"), "otra": 1},
        {"titulo": "T", "sinopsis": "palabra " * 121, "palabras_clave": list("abcde")},
        "no es un objeto",
    ],
)
def test_manejador_salida_fuera_de_esquema_es_forma_y_no_publica(
    listo: tuple[sqlite3.Connection, DisposicionProyecto], salida: object
) -> None:
    conexion, disposicion = listo
    resultado = MANEJADORES[Agente.EXPORTADOR](_Contexto(conexion, disposicion), salida)  # type: ignore[arg-type]
    assert resultado.desenlace.tipo is TipoDesenlace.FALLO_FORMA
    assert conexion.execute("SELECT count(*) FROM version_novela").fetchone()[0] == 0


def test_manejador_acepta_la_salida_del_agente_y_publica(
    listo: tuple[sqlite3.Connection, DisposicionProyecto], monkeypatch: pytest.MonkeyPatch
) -> None:
    """La forma de `.claude/agents/exportador.md`, con `serie` y `volumen` a null."""
    from backend.exportacion import publicar as modulo

    conexion, disposicion = listo
    monkeypatch.setattr(modulo, "imprimir_pdf", impresora_falsa)
    salida = {
        "titulo": "El faro",
        "sinopsis": "Una aventura.",
        "palabras_clave": ["Mar", "faro", "brújula", "amistad", "viaje"],
        "serie": None,
        "volumen": None,
    }
    resultado = MANEJADORES[Agente.EXPORTADOR](_Contexto(conexion, disposicion), salida)  # type: ignore[arg-type]
    assert resultado.desenlace.tipo is TipoDesenlace.ACEPTADO
    assert resultado.detalle == {"version": 1}
    meta = json.loads(disposicion.fichero_de_version(1, "metadatos.json").read_text("utf-8"))
    assert meta["palabras_clave"][0] == "mar"
