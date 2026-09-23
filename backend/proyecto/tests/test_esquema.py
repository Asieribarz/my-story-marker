"""Paso 3 · esquema: las listas cerradas de `proyecto` y `orden` coinciden con el código."""

import re
import sqlite3

import pytest

from backend.proyecto.abierto import Proyecto
from backend.proyecto.tests.apoyo import MOMENTO
from backend.proyecto.transiciones import ORIGENES_DE_DETENIDA
from backend.shared.tipos import Agente, DesenlaceOrden, EstadoProyecto, TipoEjecutor


def _lista_check(conexion: sqlite3.Connection, tabla: str, columna: str) -> set[str]:
    fila = conexion.execute("SELECT sql FROM sqlite_master WHERE name = ?", (tabla,)).fetchone()
    patron = rf"^\s*{columna}\s[^,]*?CHECK \({columna} IN \(([^)]*)\)"
    coincidencia = re.search(patron, fila["sql"], flags=re.MULTILINE)
    assert coincidencia, f"{tabla}.{columna} no tiene CHECK con lista cerrada"
    return set(re.findall(r"'([^']+)'", coincidencia.group(1)))


def test_las_listas_de_orden_y_proyecto_coinciden_con_el_codigo(proyecto: Proyecto) -> None:
    conexion = proyecto.conexion
    assert _lista_check(conexion, "orden", "agente") == set(Agente)
    assert _lista_check(conexion, "orden", "desenlace") == set(DesenlaceOrden)
    assert _lista_check(conexion, "orden", "estado_proyecto") == set(EstadoProyecto)
    assert _lista_check(conexion, "proyecto", "bloqueo_tipo") == set(TipoEjecutor)
    assert _lista_check(conexion, "proyecto", "detenida_desde") == set(ORIGENES_DE_DETENIDA)


def _insertar_orden(conexion: sqlite3.Connection, cerrada: str | None = None) -> None:
    conexion.execute(
        "INSERT INTO orden (estado_proyecto, agente, intento, entrada, emitida, cerrada, "
        "desenlace) VALUES ('intake', 'extractor-hechos', 1, '{}', ?, ?, ?)",
        (MOMENTO, cerrada, "aceptada" if cerrada else None),
    )


def test_no_puede_haber_dos_ordenes_vigentes(proyecto: Proyecto) -> None:
    conexion = proyecto.conexion
    _insertar_orden(conexion, cerrada=MOMENTO)
    _insertar_orden(conexion, cerrada=MOMENTO)
    _insertar_orden(conexion)
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        _insertar_orden(conexion)


def test_una_orden_cerrada_lleva_desenlace(proyecto: Proyecto) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        proyecto.conexion.execute(
            "INSERT INTO orden (estado_proyecto, agente, intento, entrada, emitida, cerrada) "
            "VALUES ('intake', 'extractor-hechos', 1, '{}', ?, ?)",
            (MOMENTO, MOMENTO),
        )


@pytest.mark.parametrize(
    ("estado", "desde"),
    [("detenida", None), ("capitulos", "capitulos"), ("detenida", "publicada")],
)
def test_detenida_desde_solo_acompana_a_detenida(
    proyecto: Proyecto, estado: str, desde: str | None
) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        proyecto.conexion.execute(
            "UPDATE proyecto SET estado = ?, detenida_desde = ?", (estado, desde)
        )


def test_el_bloqueo_va_entero_o_no_va(proyecto: Proyecto) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        proyecto.conexion.execute(
            "UPDATE proyecto SET bloqueo_titular = 'x', bloqueo_caduca = ?", (MOMENTO,)
        )
