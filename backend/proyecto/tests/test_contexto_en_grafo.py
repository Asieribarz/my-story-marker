"""V-20 (RF-22): con un contexto que infringe una regla, el proyecto no llega a planificar.

El paso 2 entregó la guarda `puede_salir_de_contexto`; aquí se prueba conectada al grafo.
Lo que se afirma, exactamente: ninguna secuencia lleva el proyecto a `planificacion` ni
persiste el contexto inválido, y la única salida de `contexto` es la del tope agotado (Q6,
RF-07a): el tercer fallo seguido lo deja en `detenida` desde `contexto`, y nunca antes.
«Reintentar», la acción humana, lo devuelve a `contexto` con el contador a cero.
"""

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from backend.contexto.tests.referencia import referencia
from backend.intake.persistencia import guardar_brief
from backend.proyecto.abierto import Proyecto
from backend.proyecto.bloqueo import tomar_bloqueo
from backend.proyecto.maquina import TOPE, Detenida, Entrada, TipoDesenlace
from backend.proyecto.orden import OrdenEmitida
from backend.proyecto.persistencia import (
    crear_proyecto,
    emitir_siguiente_orden,
    leer_estado,
    reintentar,
)
from backend.proyecto.tests.apoyo import AHORA, estado, forzar, registrar, transiciones
from backend.shared.tipos import Agente, TipoEjecutor
from backend.shared.tipos import EstadoProyecto as E


def _con(cambio: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    datos = referencia()
    cambio(datos["novela"])
    return datos


# Cada uno infringe una regla distinta: tipos, coherencia de público y de estructura.
INVALIDOS: list[object] = [
    _con(lambda n: n.update(publico="adulto")),
    _con(lambda n: n["estructura"]["nudo"].update(crisis=2)),
    _con(lambda n: n["tipo_aventura"]["contenido"].update(violencia=2)),
    _con(lambda n: n.update(tono="melancolico")),
    _con(lambda n: n["formato"].update(capitulos=12)),
    {"novela": {}},
    ["no es un objeto"],
    "texto suelto",
]


def _contextos_guardados(proyecto: Proyecto) -> int:
    return int(proyecto.conexion.execute("SELECT count(*) FROM contexto").fetchone()[0])


# Las únicas transiciones que puede escribir una secuencia de contextos inválidos: el tope
# agotado, y la vuelta humana desde `detenida`.
TOPE_AGOTADO = ("contexto", "detenida", "tope_agotado")
REINTENTAR = ("detenida", "contexto", "reintentar")


def test_un_contexto_invalido_vuelve_al_agente_con_el_informe(
    proyecto: Proyecto, token: str
) -> None:
    forzar(proyecto, E.CONTEXTO)
    primera = emitir_siguiente_orden(proyecto, token, AHORA)
    assert isinstance(primera, OrdenEmitida)
    registro = registrar(proyecto, primera.id, INVALIDOS[0], token, AHORA)
    assert (registro.tipo, registro.estado) == (TipoDesenlace.FALLO_CONTENIDO, E.CONTEXTO)
    assert registro.detalle["hallazgos"][0]["regla"] == "RF-24 · publico_por_edad"

    segunda = emitir_siguiente_orden(proyecto, token, AHORA)
    assert isinstance(segunda, OrdenEmitida)
    assert (segunda.agente, segunda.intento) == (Agente.AGENTE_CONTEXTO, 2)
    assert Entrada.INFORME_ANTERIOR.value in segunda.entrada["necesita"]
    assert segunda.entrada["informe_anterior"] == registro.detalle
    assert _contextos_guardados(proyecto) == 0


@settings(
    max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(resultados=st.lists(st.sampled_from(INVALIDOS), min_size=1, max_size=8))
def test_ninguna_secuencia_de_contextos_invalidos_sale_de_contexto(
    tmp_path: Path, resultados: list[object]
) -> None:
    with crear_proyecto(AHORA, raiz_proyectos=tmp_path) as proyecto:
        token = tomar_bloqueo(proyecto, TipoEjecutor.SESION, AHORA).token
        forzar(proyecto, E.CONTEXTO)
        seguidos = 0
        for resultado in resultados:
            emision = emitir_siguiente_orden(proyecto, token, AHORA)
            if isinstance(emision, Detenida):
                assert emision.desde is E.CONTEXTO
                reintentar(proyecto, AHORA)
                seguidos = 0
                emision = emitir_siguiente_orden(proyecto, token, AHORA)
            assert isinstance(emision, OrdenEmitida)
            assert emision.intento == seguidos + 1
            registrar(proyecto, emision.id, resultado, token, AHORA)
            seguidos += 1

            leido = leer_estado(proyecto, AHORA)
            if seguidos == TOPE:
                assert (leido.estado, leido.detenida_desde) == (E.DETENIDA, E.CONTEXTO)
                assert transiciones(proyecto.conexion)[-1] == TOPE_AGOTADO
            else:
                assert leido.estado is E.CONTEXTO
            assert set(transiciones(proyecto.conexion)) <= {TOPE_AGOTADO, REINTENTAR}
            assert _contextos_guardados(proyecto) == 0

        # Control: el mismo proyecto sale en cuanto recibe un contexto válido.
        emision = emitir_siguiente_orden(proyecto, token, AHORA)
        if isinstance(emision, Detenida):
            reintentar(proyecto, AHORA)
            emision = emitir_siguiente_orden(proyecto, token, AHORA)
        assert isinstance(emision, OrdenEmitida)
        registrar(proyecto, emision.id, referencia(), token, AHORA)
        assert estado(proyecto.conexion) is E.PLANIFICACION
        assert _contextos_guardados(proyecto) == 1


# ─── B-20: lo que fijó el comprador sale intacto ─────────────────────────────


def _guardar_brief_de_la_referencia(proyecto: Proyecto) -> dict[str, Any]:
    novela = referencia()["novela"]
    personalizacion = {k: v for k, v in novela["personalizacion"].items() if k != "texto_libre"}
    respuestas = {"personalizacion": personalizacion, "preferencias": {"tono": novela["tono"]}}
    guardar_brief(proyecto.conexion, proyecto.disposicion, respuestas, None, "2026-09-23T00:00:00Z")
    return respuestas


def test_un_contexto_que_cambia_el_brief_no_sale_de_contexto(
    proyecto: Proyecto, token: str
) -> None:
    _guardar_brief_de_la_referencia(proyecto)
    forzar(proyecto, E.CONTEXTO)
    orden = emitir_siguiente_orden(proyecto, token, AHORA)
    assert isinstance(orden, OrdenEmitida)
    anonimizado = _con(
        lambda n: n["personalizacion"]["destinatario"].update(nombre="[NOMBRE_ANONIMIZADO]")
    )
    registro = registrar(proyecto, orden.id, anonimizado, token, AHORA)
    assert (registro.tipo, registro.estado) == (TipoDesenlace.FALLO_CONTENIDO, E.CONTEXTO)
    assert {h["regla"] for h in registro.detalle["hallazgos"]} == {"B-20 · conservacion_del_brief"}
    assert _contextos_guardados(proyecto) == 0

    # Control: el mismo brief con el contexto fiel sale a planificar.
    segunda = emitir_siguiente_orden(proyecto, token, AHORA)
    assert isinstance(segunda, OrdenEmitida)
    registrar(proyecto, segunda.id, referencia(), token, AHORA)
    assert estado(proyecto.conexion) is E.PLANIFICACION


def test_una_normalizacion_que_cambia_el_brief_no_se_guarda(proyecto: Proyecto, token: str) -> None:
    respuestas = _guardar_brief_de_la_referencia(proyecto)
    orden = emitir_siguiente_orden(proyecto, token, AHORA)
    assert isinstance(orden, OrdenEmitida)
    assert (orden.agente, orden.estado) == (Agente.AGENTE_CONTEXTO, E.INTAKE)
    normalizado = {**copy.deepcopy(respuestas), "notas": [], "faltan": []}
    normalizado["personalizacion"]["edad_lector"] += 1
    registro = registrar(proyecto, orden.id, normalizado, token, AHORA)
    assert registro.tipo is TipoDesenlace.FALLO_CONTENIDO
    assert [h["localizacion"] for h in registro.detalle["hallazgos"]] == [
        "personalizacion.edad_lector"
    ]
    fila = proyecto.conexion.execute("SELECT normalizado FROM brief WHERE id = 1").fetchone()
    assert fila["normalizado"] is None

    # Control: la normalización fiel se guarda.
    segunda = emitir_siguiente_orden(proyecto, token, AHORA)
    assert isinstance(segunda, OrdenEmitida)
    fiel = {**copy.deepcopy(respuestas), "notas": [], "faltan": []}
    assert registrar(proyecto, segunda.id, fiel, token, AHORA).tipo is TipoDesenlace.ACEPTADO
