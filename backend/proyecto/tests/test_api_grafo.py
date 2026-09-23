"""V-14 y V-20 por la API: ninguna secuencia de llamadas sin la acción humana saca al
proyecto de una parada (RN-3, RF-05, RF-05a), y ninguna secuencia de contextos inválidos lo
lleva a `planificacion` (RF-22).

Las paradas que la API aún no alcanza —faltan los manejadores de los pasos 4 a 9a— se
colocan con `apoyo.forzar`; lo que se prueba después va todo por HTTP. Todos los datos de
persona son ficticios.
"""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from backend.contexto.tests.referencia import referencia
from backend.proyecto.tests.apoyo import (
    BRIEF,
    NORMALIZADO,
    forzar,
    proponer_cambio,
    transiciones,
    volcado,
)
from backend.proyecto.tests.cliente_api import ClienteApi, cliente_api, con_token, error
from backend.shared.tipos import EstadoProyecto as E

_POR_EJEMPLO = settings(
    max_examples=20, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)


@pytest.fixture
def api(tmp_path: Path) -> Iterator[ClienteApi]:
    with cliente_api(tmp_path) as cliente:
        yield cliente


# ─── V-14 · paradas humanas ──────────────────────────────────────────────────

# Lo que responde la siguiente orden en cada parada, sin la acción humana.
_ESPERA: dict[E, dict[str, str]] = {
    E.APROBACION_PLAN: {"decision": "esperar_humano", "motivo": "aprobacion_plan"},
    E.APROBACION_FINAL: {"decision": "esperar_humano", "motivo": "aprobacion_final"},
    E.PUBLICADA: {"decision": "publicada"},
    E.CAMBIO_SOLICITADO: {"decision": "esperar_humano", "motivo": "confirmacion_cambio"},
    E.DETENIDA: {"decision": "detenida", "desde": "contexto"},
}

# Cada llamada que no es la acción humana de la parada, con la respuesta que debe dar.
_LLAMADAS = (
    "siguiente",
    "resultado",
    "renovar",
    "otro_ejecutor",
    "estado",
    "brief",
    "confirmar_hechos",
    "validar_contexto",
    "reintentar",
)


def _llamar(api: ClienteApi, proyecto: str, token: str, llamada: str, n: int, parada: E) -> None:
    ruta = f"/proyectos/{proyecto}"
    match llamada:
        case "siguiente":
            assert api.siguiente(proyecto, token) == _ESPERA[parada]
        case "resultado":
            respuesta = api.registrar(proyecto, token, n, {"hechos": []})
            assert error(respuesta) == (409, "orden_ajena", "RF-08a")
        case "renovar":
            respuesta = api.http.post(f"{ruta}/bloqueo", headers=con_token(token))
            assert respuesta.status_code == 200
        case "otro_ejecutor":
            respuesta = api.http.post(f"{ruta}/bloqueo", json={"tipo": "worker"})
            assert error(respuesta) == (423, "bloqueo_ajeno", "RF-09b")
        case "estado":
            assert api.estado(proyecto)["estado"] == parada.value
        case "brief":
            respuesta = api.enviar_brief(proyecto, BRIEF)
            assert error(respuesta) == (409, "transicion_invalida", "RF-04")
        case "confirmar_hechos":
            respuesta = api.http.post(
                f"{ruta}/hechos/confirmacion",
                json={"decisiones": [{"hecho": n, "confirmado": True}]},
            )
            assert error(respuesta) == (409, "transicion_invalida", "RF-04")
        case "validar_contexto":
            respuesta = api.http.post(f"{ruta}/contexto/validar", json=referencia())
            assert respuesta.json()["valido"] is True
        case "reintentar":
            # Es la acción humana de `detenida`; en las demás paradas no tiene arista.
            respuesta = api.http.post(f"{ruta}/reintentar")
            assert error(respuesta) == (409, "transicion_invalida", "RF-04")
        case _:
            raise AssertionError(llamada)


@_POR_EJEMPLO
@given(
    parada=st.sampled_from(sorted(_ESPERA)),
    llamadas=st.lists(st.tuples(st.sampled_from(_LLAMADAS), st.integers(1, 5)), max_size=8),
)
def test_ninguna_secuencia_de_llamadas_sale_de_una_parada(
    api: ClienteApi, parada: E, llamadas: list[tuple[str, int]]
) -> None:
    proyecto = api.crear(parada_plan=True, parada_final=True)
    token = api.tomar(proyecto)
    with api.abrir(proyecto) as abierto:
        desde = E.CONTEXTO if parada is E.DETENIDA else None
        forzar(abierto, parada, detenida_desde=desde, parada_plan=True, parada_final=True)
        if parada is E.CAMBIO_SOLICITADO:
            proponer_cambio(abierto)
        antes = volcado(abierto.conexion)

    for llamada, n in llamadas:
        if parada is E.DETENIDA and llamada == "reintentar":
            continue
        _llamar(api, proyecto, token, llamada, n, parada)

    with api.abrir(proyecto) as abierto:
        assert volcado(abierto.conexion) == antes


def test_reintentar_es_la_salida_humana_de_detenida(api: ClienteApi) -> None:
    proyecto = api.crear()
    with api.abrir(proyecto) as abierto:
        forzar(abierto, E.DETENIDA, detenida_desde=E.CONTEXTO, intentos_paso=0)
    vuelta = api.http.post(f"/proyectos/{proyecto}/reintentar")
    assert vuelta.status_code == 200, vuelta.text
    assert vuelta.json()["estado"] == "contexto"


# ─── V-20 · un contexto inválido no sale de `contexto` ───────────────────────


def _con(cambio: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    datos = referencia()
    cambio(datos["novela"])
    return datos


# Cada uno infringe una regla distinta: tipos, coherencia de público y de estructura.
_INVALIDOS: list[object] = [
    _con(lambda n: n.update(publico="adulto")),
    _con(lambda n: n.update(tono="melancolico")),
    _con(lambda n: n["formato"].update(capitulos=12)),
    {"novela": {}},
    "texto suelto",
]


def _en_contexto(api: ClienteApi) -> tuple[str, str]:
    """Un proyecto llevado a `contexto` por la API: brief sin texto libre y normalizado."""
    proyecto = api.crear()
    token = api.tomar(proyecto)
    api.enviar_brief(proyecto, BRIEF)
    normalizar = api.orden(proyecto, token)
    assert api.aceptado(proyecto, token, normalizar["id"], NORMALIZADO)["estado"] == "contexto"
    return proyecto, token


def _orden_de_contexto(api: ClienteApi, proyecto: str, token: str) -> dict[str, Any]:
    decision = api.siguiente(proyecto, token)
    if decision["decision"] == "detenida":
        assert decision["desde"] == "contexto"
        assert api.http.post(f"/proyectos/{proyecto}/reintentar").status_code == 200
        decision = api.siguiente(proyecto, token)
    assert decision["decision"] == "orden", decision
    orden: dict[str, Any] = decision["orden"]
    assert orden["agente"] == "agente-contexto"
    return orden


def _contextos_guardados(api: ClienteApi, proyecto: str) -> int:
    with api.abrir(proyecto) as abierto:
        return int(abierto.conexion.execute("SELECT count(*) FROM contexto").fetchone()[0])


def _desde_contexto(api: ClienteApi, proyecto: str) -> list[tuple[str, str, str]]:
    """Las transiciones escritas desde que el proyecto llegó a `contexto`."""
    with api.abrir(proyecto) as abierto:
        return transiciones(abierto.conexion)[1:]


# Menos ejemplos que V-14: cada uno recorre intake por HTTP, y la misma propiedad sobre el
# núcleo ya corre con más en `test_contexto_en_grafo.py`.
@settings(_POR_EJEMPLO, max_examples=10)
@given(resultados=st.lists(st.sampled_from(_INVALIDOS), min_size=1, max_size=7))
def test_ninguna_secuencia_de_contextos_invalidos_llega_a_planificar(
    api: ClienteApi, resultados: list[object]
) -> None:
    proyecto, token = _en_contexto(api)
    seguidos = 0
    for resultado in resultados:
        orden = _orden_de_contexto(api, proyecto, token)
        seguidos = orden["intento"]
        respuesta = api.registrar(proyecto, token, orden["id"], resultado)
        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["desenlace"] == "rechazada"
        # Solo el tercer fallo seguido saca de `contexto`, y solo a `detenida` (Q6, RF-07a).
        leido = api.estado(proyecto)
        esperado = ("detenida", "contexto") if seguidos == 3 else ("contexto", None)
        assert (leido["estado"], leido["detenida_desde"]) == esperado
        salidas = set(_desde_contexto(api, proyecto))
        assert salidas <= {
            ("contexto", "detenida", "tope_agotado"),
            ("detenida", "contexto", "reintentar"),
        }
    assert _contextos_guardados(api, proyecto) == 0

    # Control: el mismo proyecto sale en cuanto recibe el contexto válido de referencia.
    orden = _orden_de_contexto(api, proyecto, token)
    assert api.aceptado(proyecto, token, orden["id"], referencia())["estado"] == "planificacion"
    assert _contextos_guardados(api, proyecto) == 1
