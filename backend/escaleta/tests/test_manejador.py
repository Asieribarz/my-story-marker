"""V-21 y RF-77a: el manejador del escaletista.

RF-41 y RF-42 con un hito ausente y otro duplicado, RF-43 y B-9 con un caso que los dispara,
y la escaleta de referencia como control: se guarda con sus presagios previstos (B-16) y sin
avisos. Todos los datos son ficticios.
"""

import sqlite3
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from backend.capitulo.tests.referencia import MOMENTO
from backend.contexto.persistencia import guardar_contexto
from backend.contexto.tests.referencia import HOY, referencia
from backend.contexto.validacion import validar
from backend.escaleta.consultas import leer_escaleta
from backend.escaleta.manejadores import MANEJADORES, registrar_escaleta
from backend.escaleta.tests.referencia import salida_escaletista
from backend.planificacion.consultas import guardar_planificacion
from backend.planificacion.materializar import materializar_contexto
from backend.planificacion.modelos import SalidaPlanificador
from backend.planificacion.tests.referencia import salida_planificador
from backend.proyecto.manejadores import manejador_de
from backend.proyecto.maquina import TipoDesenlace
from backend.shared.db import crear_base
from backend.shared.tipos import Agente

Salida = dict[str, Any]


@pytest.fixture
def conexion(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """Contexto de referencia materializado y plan guardado, sin escaleta."""
    base = crear_base(tmp_path / "proyecto.sqlite")
    informe = validar(referencia(), date.fromisoformat(HOY))
    assert informe.contexto is not None
    guardar_contexto(base, informe, MOMENTO)
    materializar_contexto(base, informe.contexto, MOMENTO)
    guardar_planificacion(base, SalidaPlanificador.model_validate(salida_planificador()))
    yield base
    base.close()


def _ficha(s: Salida, numero: int) -> dict[str, Any]:
    ficha: dict[str, Any] = s["fichas"][numero - 1]
    return ficha


INCOHERENCIAS: dict[str, tuple[Callable[[Salida], object], str]] = {
    "hito ausente": (lambda s: _ficha(s, 9).update(hitos=[]), "RF-42 · hito_ausente"),
    "hito duplicado": (
        lambda s: _ficha(s, 10).update(hitos=["climax"]),
        "RF-42 · hito_duplicado",
    ),
    "falta una ficha": (lambda s: s["fichas"].pop(), "RF-41 · numero_de_fichas"),
    "presagio sin cobro": (lambda s: _ficha(s, 9).update(cobrar=[]), "RF-43 · presagio_sin_cobro"),
    "el día retrocede": (lambda s: _ficha(s, 5).update(dia=1), "RF-76 · dia_retrocede"),
}


def test_la_escaleta_de_referencia_se_guarda_con_sus_presagios(
    conexion: sqlite3.Connection,
) -> None:
    assert manejador_de(Agente.ESCALETISTA) is MANEJADORES[Agente.ESCALETISTA]
    salida = registrar_escaleta(conexion, salida_escaletista())
    assert salida.desenlace.tipo is TipoDesenlace.ACEPTADO, salida.detalle
    assert salida.detalle["avisos"] == []
    assert len(leer_escaleta(conexion)) == 10
    presagio = conexion.execute(
        "SELECT p.plantar_en, p.cobrar_en, e.estado FROM presagio p "
        "JOIN presagio_estado e ON e.presagio = p.id WHERE p.clave = 'mapa_oculto'"
    ).fetchone()
    assert tuple(presagio) == (2, 9, "previsto")


@pytest.mark.parametrize(("cambio", "regla"), list(INCOHERENCIAS.values()), ids=list(INCOHERENCIAS))
def test_una_escaleta_incoherente_no_se_guarda(
    conexion: sqlite3.Connection, cambio: Callable[[Salida], object], regla: str
) -> None:
    datos = salida_escaletista()
    cambio(datos)
    salida = registrar_escaleta(conexion, datos)
    assert salida.desenlace.tipo is TipoDesenlace.FALLO_CONTENIDO
    assert regla in {h["regla"] for h in salida.detalle["hallazgos"]}
    assert leer_escaleta(conexion) == ()
    assert conexion.execute("SELECT count(*) FROM presagio").fetchone()[0] == 0


def test_un_hecho_obligatorio_sin_ficha_es_un_aviso(conexion: sqlite3.Connection) -> None:
    datos = salida_escaletista()
    _ficha(datos, 1)["hechos"] = ["h3"]
    salida = registrar_escaleta(conexion, datos)
    assert salida.desenlace.tipo is TipoDesenlace.ACEPTADO
    assert [a["evidencia"] for a in salida.detalle["avisos"]] == ["h1"]
