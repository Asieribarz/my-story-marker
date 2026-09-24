"""V-32 (RF-113, TC-5): umbral del juez de manuscrito en los bordes, y RF-77a.

Sumas 17 y 18, un criterio a 2 con suma alta, y una salida con cuatro criterios que es un
fallo de forma y no persiste nada. Todos los datos son ficticios.
"""

import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.proyecto.abierto import Proyecto
from backend.proyecto.manejadores import ContextoManejo, Salida
from backend.proyecto.maquina import TipoDesenlace, ViaRegistro
from backend.proyecto.orden import OrdenEmitida
from backend.shared.tipos import Agente, CriterioManuscrito, EstadoProyecto
from backend.verificacion.manejadores import MANEJADORES
from backend.verificacion.modelos import aprueba
from backend.verificacion.tests.apoyo import MOMENTO, proyecto

AHORA = datetime(2026, 9, 23, 10, tzinfo=UTC)


@pytest.fixture
def abierto(tmp_path: Path) -> Iterator[Proyecto]:
    disposicion, conexion = proyecto(tmp_path)
    yield Proyecto(disposicion, conexion)
    conexion.close()


def _salida(puntuaciones: list[int], capitulos: list[int] | None = None) -> dict[str, object]:
    return {
        "criterios": [
            {"criterio": c.value, "puntuacion": p, "justificacion": f"El capítulo {i + 1}."}
            for i, (c, p) in enumerate(zip(CriterioManuscrito, puntuaciones, strict=False))
        ],
        "capitulos": capitulos or [],
    }


def _juzgar(p: Proyecto, resultado: object) -> Salida:
    orden = OrdenEmitida(
        7, EstadoProyecto.VERIFICACION_MANUSCRITO, Agente.JUEZ_MANUSCRITO, 1, None, {},
        ViaRegistro.SKILL, MOMENTO, "x:7:1",
    )  # fmt: skip
    return MANEJADORES[Agente.JUEZ_MANUSCRITO](ContextoManejo(p, orden, AHORA), resultado)


def _gate(c: sqlite3.Connection) -> tuple[int, dict[str, object]]:
    fila = c.execute("SELECT ok, detalle FROM gate_resultado WHERE gate = 'juez'").fetchone()
    return int(fila["ok"]), json.loads(fila["detalle"])


@pytest.mark.parametrize(
    ("puntuaciones", "ok"),
    [([4, 4, 3, 3, 4], True), ([4, 3, 3, 3, 4], False), ([5, 5, 5, 5, 2], False)],
    ids=["suma 18", "suma 17", "criterio a 2"],
)
def test_v32_umbral_en_los_bordes(abierto: Proyecto, puntuaciones: list[int], ok: bool) -> None:
    assert aprueba(puntuaciones) is ok
    salida = _juzgar(abierto, _salida(puntuaciones, [9, 2, 9]))
    assert salida.desenlace.tipo is TipoDesenlace.ACEPTADO
    fila_ok, detalle = _gate(abierto.conexion)
    assert (bool(fila_ok), detalle["suma"], detalle["capitulos"]) == (ok, sum(puntuaciones), [2, 9])
    filas = abierto.conexion.execute(
        "SELECT revisor, version_novela, ciclo FROM informe_juez"
    ).fetchall()
    assert [tuple(f) for f in filas] == [("juez", 1, 0)] * 5


@pytest.mark.parametrize(
    "resultado",
    [
        _salida([4, 4, 4, 4]),
        {**_salida([4, 4, 4, 4, 4]), "capitulos": [11]},
        _salida([4, 4, 4, 4, 6]),
        {"criterios": [{"criterio": "continuidad", "puntuacion": 4, "justificacion": "x"}] * 5},
        _salida([4, 3, 3, 3, 4]),
    ],
    ids=[
        "cuatro criterios",
        "capitulo fuera",
        "puntuacion 6",
        "criterio repetido",
        "suspende sin capitulos (M-6)",
    ],
)
def test_una_salida_fuera_de_esquema_es_fallo_de_forma(
    abierto: Proyecto, resultado: object
) -> None:
    salida = _juzgar(abierto, resultado)
    assert salida.desenlace.tipo is TipoDesenlace.FALLO_FORMA and salida.detalle["errores"]
    assert abierto.conexion.execute("SELECT count(*) FROM informe_juez").fetchone()[0] == 0
    assert abierto.conexion.execute("SELECT count(*) FROM gate_resultado").fetchone()[0] == 0


def test_el_check_de_criterio_coincide_con_el_enum(abierto: Proyecto) -> None:
    sql = abierto.conexion.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'informe_juez'"
    ).fetchone()[0]
    assert all(f"'{c.value}'" in sql for c in CriterioManuscrito)
