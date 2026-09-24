"""RF-77a y B-1: el manejador del planificador.

Una salida que contradice el contexto no se guarda y vuelve con la regla que infringe; la de
referencia se guarda con su siembra del glosario. Todos los datos son ficticios.
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
from backend.planificacion.consultas import leer_planificacion
from backend.planificacion.manejadores import MANEJADORES, registrar_planificacion
from backend.planificacion.materializar import materializar_contexto
from backend.planificacion.tests.referencia import salida_planificador
from backend.proyecto.manejadores import manejador_de
from backend.proyecto.maquina import TipoDesenlace
from backend.shared.db import crear_base
from backend.shared.tipos import Agente

Salida = dict[str, Any]


@pytest.fixture
def conexion(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """El contexto de referencia validado y materializado, sin planificar."""
    base = crear_base(tmp_path / "proyecto.sqlite")
    informe = validar(referencia(), date.fromisoformat(HOY))
    assert informe.contexto is not None
    guardar_contexto(base, informe, MOMENTO)
    materializar_contexto(base, informe.contexto, MOMENTO)
    yield base
    base.close()


def _con_id(elementos: list[dict[str, Any]], ident: str) -> dict[str, Any]:
    return next(e for e in elementos if e["id"] == ident)


def _nueva_localizacion(s: Salida, nivel: str, padre: str) -> None:
    lugar = {"id": "sierra", "nivel": nivel, "padre": padre, "nombre": "Sierra", "descripcion": "."}
    s["mundo"]["localizaciones"].append(lugar)


CONTRADICCIONES: dict[str, tuple[Callable[[Salida], object], str]] = {
    "otro modelo": (lambda s: s["plan"].update(modelo="viaje_heroe"), "B-1 · plan_del_contexto"),
    "detonante fuera del planteamiento": (
        lambda s: s["plan"]["reparto"].update(detonante=3),
        "B-3 · hito_en_planteamiento",
    ),
    "falta un personaje": (lambda s: s["personajes"].pop(), "B-1 · personaje_del_contexto"),
    "otro arco": (
        lambda s: _con_id(s["personajes"], "prot").update(arco="negativo"),
        "B-1 · personaje_del_contexto",
    ),
    "otro nombre para un personaje real": (
        lambda s: _con_id(s["personajes"], "nala").update(nombre="Luna"),
        "B-4 · nombre_del_personaje_real",
    ),
    "otro padre": (
        lambda s: _con_id(s["mundo"]["localizaciones"], "casa_abuela").update(padre="costa"),
        "B-1 · localizacion_del_contexto",
    ),
    "localización nueva que no es micro": (
        lambda s: _nueva_localizacion(s, "meso", "comarca"),
        "B-1 · localizacion_nueva_micro",
    ),
    "otro narrador": (
        lambda s: s["estilo"].update(narrador="primera"),
        "B-1 · estilo_del_contexto",
    ),
    "lista negra sin las prohibidas": (
        lambda s: s["estilo"].update(lista_negra=[]),
        "B-4 · lista_negra_sin_prohibidas",
    ),
    "un término para dos entidades": (
        lambda s: s["mundo"]["objetos"][0]["alias"].append("Nala"),
        "RF-77a · incoherente_con_la_base",
    ),
}


def test_la_salida_de_referencia_se_guarda_y_siembra_el_glosario(
    conexion: sqlite3.Connection,
) -> None:
    assert manejador_de(Agente.PLANIFICADOR) is MANEJADORES[Agente.PLANIFICADOR]
    salida = registrar_planificacion(conexion, salida_planificador())
    assert salida.desenlace.tipo is TipoDesenlace.ACEPTADO, salida.detalle
    assert leer_planificacion(conexion) is not None
    glosario = conexion.execute(
        "SELECT termino, referencia, tipo FROM glosario WHERE referencia = 'prot' ORDER BY termino"
    ).fetchall()
    assert [tuple(t) for t in glosario] == [
        ("Aitana", "prot", "canonico"),
        ("Aiti", "prot", "alias"),
    ]


@pytest.mark.parametrize(
    ("cambio", "regla"), list(CONTRADICCIONES.values()), ids=list(CONTRADICCIONES)
)
def test_una_salida_que_contradice_el_contexto_no_se_guarda(
    conexion: sqlite3.Connection, cambio: Callable[[Salida], object], regla: str
) -> None:
    datos = salida_planificador()
    cambio(datos)
    salida = registrar_planificacion(conexion, datos)
    assert salida.desenlace.tipo is TipoDesenlace.FALLO_CONTENIDO
    assert regla in {h["regla"] for h in salida.detalle["hallazgos"]}
    assert leer_planificacion(conexion) is None
    assert conexion.execute("SELECT count(*) FROM glosario").fetchone()[0] == 0


def test_una_salida_mal_formada_es_un_fallo_de_forma(conexion: sqlite3.Connection) -> None:
    salida = registrar_planificacion(conexion, {"plan": {}})
    assert salida.desenlace.tipo is TipoDesenlace.FALLO_FORMA
    assert salida.detalle["errores"]
    assert leer_planificacion(conexion) is None
