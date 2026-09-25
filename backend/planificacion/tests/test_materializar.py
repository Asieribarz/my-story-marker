"""B-1 y B-18: la materialización del contexto, y la siembra que se lee como entró."""

import sqlite3
from datetime import date
from pathlib import Path

from backend.capitulo.tests.referencia import MOMENTO, biblia_de_referencia
from backend.contexto.tests.referencia import HOY, referencia
from backend.contexto.validacion import validar
from backend.escaleta.consultas import leer_escaleta
from backend.escaleta.modelos import SalidaEscaletista
from backend.escaleta.tests.referencia import salida_escaletista
from backend.planificacion.consultas import leer_planificacion
from backend.planificacion.materializar import materializar_contexto
from backend.planificacion.modelos import SalidaPlanificador
from backend.planificacion.tests.referencia import salida_planificador
from backend.shared.db import crear_base


def _volcado(conexion: sqlite3.Connection) -> dict[str, list[tuple[object, ...]]]:
    tablas = ("personalizacion", "hecho", "personaje", "localizacion", "ruta", "regla_mundo")
    volcado = {t: sorted(map(tuple, conexion.execute(f"SELECT * FROM {t}"))) for t in tablas}
    volcado["evento"] = sorted(
        map(tuple, conexion.execute("SELECT * FROM evento WHERE capitulo IS NULL"))
    )
    volcado["vetos"] = sorted(map(tuple, conexion.execute("SELECT * FROM palabra_prohibida")))
    return volcado


def test_materializa_el_contexto_y_lleva_la_exclusion_al_evento(tmp_path: Path) -> None:
    datos = referencia()
    datos["novela"]["personalizacion"]["hechos"][1]["excluye"] = {"fuente": "h1", "tipo": "muerte"}
    informe = validar(datos, date.fromisoformat(HOY))
    assert informe.contexto is not None
    conexion = crear_base(tmp_path / "proyecto.sqlite")
    materializar_contexto(conexion, informe.contexto, MOMENTO)

    personajes = conexion.execute(
        "SELECT id, nombre, origen, fecha_nacimiento FROM personaje ORDER BY id"
    ).fetchall()
    assert [tuple(p) for p in personajes] == [
        ("antag", None, "ficticio", None),
        ("nala", None, "real", None),
        ("prot", "Aitana", "real", "2017-04-12"),
    ]
    assert conexion.execute("SELECT count(*) FROM localizacion").fetchone()[0] == 8
    assert [tuple(r) for r in conexion.execute("SELECT * FROM ruta")] == [
        (1, "casa_abuela", 0),
        (2, "bosque", 1),
        (3, "faro", 1),
        (4, "cueva_final", 1),
    ]
    assert conexion.execute("SELECT count(*) FROM hecho").fetchone()[0] == 5
    evento = conexion.execute(
        "SELECT momento, dia, lugar, capitulo, excluye, tipo_exclusion, hecho FROM evento"
    ).fetchall()
    assert [tuple(e) for e in evento] == [("2023-07", None, "playa", None, "nala", "muerte", "h2")]
    vetos = conexion.execute("SELECT termino, nivel FROM palabra_prohibida").fetchall()
    assert [tuple(v) for v in vetos] == [("hospitales", "novela")]

    antes = _volcado(conexion)
    materializar_contexto(conexion, informe.contexto, MOMENTO)
    assert _volcado(conexion) == antes


def test_un_evento_sin_exclusion_no_excluye_a_nadie(tmp_path: Path) -> None:
    informe = validar(referencia(), date.fromisoformat(HOY))
    assert informe.contexto is not None
    conexion = crear_base(tmp_path / "proyecto.sqlite")
    materializar_contexto(conexion, informe.contexto, MOMENTO)
    fila = conexion.execute("SELECT excluye, tipo_exclusion FROM evento").fetchone()
    assert tuple(fila) == (None, None)


def test_la_siembra_se_lee_como_entro(tmp_path: Path) -> None:
    conexion = biblia_de_referencia(tmp_path / "proyecto.sqlite")
    assert leer_planificacion(conexion) == SalidaPlanificador.model_validate(salida_planificador())
    escaleta = SalidaEscaletista.model_validate(salida_escaletista())
    assert leer_escaleta(conexion) == escaleta.fichas
    # La planificación completa los personajes que materializó el contexto sin duplicarlos.
    nombres = conexion.execute("SELECT id, nombre FROM personaje ORDER BY id").fetchall()
    assert [tuple(n) for n in nombres] == [("antag", "Bruno"), ("nala", "Nala"), ("prot", "Aitana")]
