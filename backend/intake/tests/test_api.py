"""Paso 3 · las rutas de `intake` con `TestClient`: el brief (RF-10, RF-13, RF-14) y la
confirmación de hechos (RF-15). Son acciones del comprador: no llevan el token del bloqueo y
solo caben en `intake` (RF-04).

Todos los datos de persona son ficticios; el email tiene forma válida pero no es de nadie.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from backend.intake.entrada import canjear
from backend.proyecto.errores import EntradaNoCanjeable
from backend.proyecto.tests.apoyo import BRIEF, HECHO, TEXTO_LIBRE, forzar
from backend.proyecto.tests.cliente_api import ClienteApi, cliente_api, error
from backend.shared.tipos import EstadoProyecto

EMAIL_FICTICIO = "nadie@ejemplo.invalid"
OTRO_HECHO: dict[str, Any] = {
    "tipo": "lugar",
    "texto": "El faro del puerto",
    "prioridad": "deseable",
}


@pytest.fixture
def api(tmp_path: Path) -> Iterator[ClienteApi]:
    with cliente_api(tmp_path) as cliente:
        yield cliente


def _con_hechos(api: ClienteApi) -> tuple[str, str, list[dict[str, Any]]]:
    """Un proyecto con dos hechos propuestos por el Extractor, pendientes de confirmar."""
    proyecto = api.crear()
    token = api.tomar(proyecto)
    api.enviar_brief(proyecto, BRIEF, TEXTO_LIBRE)
    orden = api.orden(proyecto, token)
    api.aceptado(proyecto, token, orden["id"], {"hechos": [HECHO, OTRO_HECHO]})
    hechos: list[dict[str, Any]] = api.http.get(f"/proyectos/{proyecto}/hechos").json()["hechos"]
    return proyecto, token, hechos


def _confirmar(api: ClienteApi, proyecto: str, decisiones: list[dict[str, Any]]) -> Any:
    return api.http.post(
        f"/proyectos/{proyecto}/hechos/confirmacion", json={"decisiones": decisiones}
    )


# ─── El brief ────────────────────────────────────────────────────────────────


def test_el_brief_guarda_el_texto_libre_aparte(api: ClienteApi) -> None:
    proyecto = api.crear()
    respuesta = api.enviar_brief(proyecto, BRIEF, TEXTO_LIBRE)
    assert respuesta.status_code == 200, respuesta.text
    with api.abrir(proyecto) as abierto:
        assert abierto.disposicion.texto_libre.read_text(encoding="utf-8") == TEXTO_LIBRE
        fila = abierto.conexion.execute("SELECT ruta_texto_libre FROM brief").fetchone()
        assert fila[0] == "brief/texto_libre.txt"


def test_un_dato_excluido_se_descarta_sin_devolver_su_valor(api: ClienteApi) -> None:
    proyecto = api.crear()
    respuesta = api.enviar_brief(proyecto, {**BRIEF, "contacto": EMAIL_FICTICIO})
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["descartes"] == [{"tipo": "email", "campo": "contacto"}]
    assert EMAIL_FICTICIO not in respuesta.text
    with api.abrir(proyecto) as abierto:
        guardado = abierto.conexion.execute("SELECT respuestas FROM brief").fetchone()[0]
        assert EMAIL_FICTICIO not in guardado


def test_volver_a_enviar_el_brief_sustituye_el_anterior(api: ClienteApi) -> None:
    proyecto = api.crear()
    api.enviar_brief(proyecto, BRIEF, TEXTO_LIBRE)
    api.enviar_brief(proyecto, {"ocasion": "navidad"})
    with api.abrir(proyecto) as abierto:
        fila = abierto.conexion.execute("SELECT respuestas, ruta_texto_libre FROM brief").fetchone()
        assert (fila[0], fila[1]) == ('{"ocasion": "navidad"}', None)


def test_el_brief_fuera_de_intake_no_se_guarda(api: ClienteApi) -> None:
    proyecto = api.crear()
    with api.abrir(proyecto) as abierto:
        forzar(abierto, EstadoProyecto.CONTEXTO)
    respuesta = api.enviar_brief(proyecto, BRIEF, TEXTO_LIBRE)
    assert error(respuesta) == (409, "transicion_invalida", "RF-04")
    assert "solo se admite en intake" in respuesta.json()["detalle"]
    with api.abrir(proyecto) as abierto:
        assert abierto.conexion.execute("SELECT count(*) FROM brief").fetchone()[0] == 0
        assert not abierto.disposicion.texto_libre.exists()


@pytest.mark.parametrize(
    "cuerpo",
    [{}, {"respuestas": {}}, {"respuestas": BRIEF, "texto_libre": ""}, {"respuestas": "x"}],
)
def test_un_brief_mal_formado_es_un_error_de_validacion(
    api: ClienteApi, cuerpo: dict[str, Any]
) -> None:
    proyecto = api.crear()
    respuesta = api.http.post(f"/proyectos/{proyecto}/brief", json=cuerpo)
    assert error(respuesta) == (422, "validacion", None)


# ─── Los hechos ──────────────────────────────────────────────────────────────


def test_sin_extraccion_no_hay_hechos_pendientes(api: ClienteApi) -> None:
    proyecto = api.crear()
    assert api.http.get(f"/proyectos/{proyecto}/hechos").json() == {"hechos": []}


def test_confirmar_y_rechazar_deja_solo_los_confirmados(api: ClienteApi) -> None:
    proyecto, token, hechos = _con_hechos(api)
    assert [h["texto"] for h in hechos] == [HECHO["texto"], OTRO_HECHO["texto"]]
    primero, segundo = (h["id"] for h in hechos)

    parcial = _confirmar(api, proyecto, [{"hecho": primero, "confirmado": True}])
    assert [h["id"] for h in parcial.json()["hechos"]] == [segundo]
    assert api.siguiente(proyecto, token)["motivo"] == "confirmacion_hechos"

    resto = _confirmar(api, proyecto, [{"hecho": segundo, "confirmado": False}])
    assert resto.json() == {"hechos": []}
    with api.abrir(proyecto) as abierto:
        estados = abierto.conexion.execute(
            "SELECT estado FROM hecho_propuesto ORDER BY id"
        ).fetchall()
        assert [e[0] for e in estados] == ["confirmado", "rechazado"]
    assert api.orden(proyecto, token)["agente"] == "agente-contexto"


def test_un_hecho_que_no_esta_pendiente_no_se_decide(api: ClienteApi) -> None:
    proyecto, _, hechos = _con_hechos(api)
    primero = hechos[0]["id"]
    _confirmar(api, proyecto, [{"hecho": primero, "confirmado": True}])
    otra_vez = _confirmar(
        api,
        proyecto,
        [{"hecho": hechos[1]["id"], "confirmado": True}, {"hecho": primero, "confirmado": False}],
    )
    assert error(otra_vez) == (409, "decision_humana_invalida", "RF-15")
    inexistente = _confirmar(api, proyecto, [{"hecho": 99, "confirmado": True}])
    assert error(inexistente) == (409, "decision_humana_invalida", "RF-15")
    assert [h["id"] for h in api.http.get(f"/proyectos/{proyecto}/hechos").json()["hechos"]] == [
        hechos[1]["id"]
    ]


@pytest.mark.parametrize(
    "decisiones",
    [[], [{"hecho": 1, "confirmado": True}, {"hecho": 1, "confirmado": False}], [{"hecho": 1}]],
)
def test_una_confirmacion_mal_formada_es_un_error_de_validacion(
    api: ClienteApi, decisiones: list[dict[str, Any]]
) -> None:
    proyecto, _, _ = _con_hechos(api)
    assert error(_confirmar(api, proyecto, decisiones)) == (422, "validacion", None)


def test_confirmar_fuera_de_intake_es_una_transicion_invalida(api: ClienteApi) -> None:
    proyecto = api.crear()
    with api.abrir(proyecto) as abierto:
        forzar(abierto, EstadoProyecto.PLANIFICACION)
    respuesta = _confirmar(api, proyecto, [{"hecho": 1, "confirmado": True}])
    assert error(respuesta) == (409, "transicion_invalida", "RF-04")


# ─── Volver a enviar el brief (RF-07a, RF-14, RF-15) ─────────────────────────

OTRO_TEXTO = "Colecciona conchas de la playa del norte."


def _texto_de(api: ClienteApi, orden: dict[str, Any]) -> str:
    return canjear(orden["entrada"]["texto_libre"]["identificador"], api.reloj.ahora, api.raiz)


def test_reenviar_el_brief_no_hereda_los_intentos_ni_el_informe_del_extractor(
    api: ClienteApi,
) -> None:
    proyecto = api.crear()
    token = api.tomar(proyecto)
    api.enviar_brief(proyecto, BRIEF, TEXTO_LIBRE)
    for _ in range(2):
        fallida = api.orden(proyecto, token)
        assert api.registrar(proyecto, token, fallida["id"], "mal").json()["tipo"] == "fallo_forma"
    vigente = api.orden(proyecto, token)
    assert (vigente["agente"], vigente["intento"]) == ("extractor-hechos", 3)

    assert api.enviar_brief(proyecto, BRIEF).status_code == 200
    leido = api.estado(proyecto)
    assert (leido["intentos_paso"], leido["orden_vigente"]) == (0, None)
    # La orden que trabajaba con el brief anterior se cerró sin resultado.
    tardio = api.registrar(proyecto, token, vigente["id"], {"hechos": [HECHO]})
    assert error(tardio) == (409, "orden_ajena", "RF-08a")

    normalizar = api.orden(proyecto, token)
    assert (normalizar["agente"], normalizar["intento"]) == ("agente-contexto", 1)
    assert normalizar["entrada"]["informe_anterior"] is None
    assert api.registrar(proyecto, token, normalizar["id"], []).json()["estado"] == "intake"
    assert api.orden(proyecto, token)["intento"] == 2


def test_reenviar_el_brief_con_texto_no_hereda_los_intentos_del_agente_de_contexto(
    api: ClienteApi,
) -> None:
    proyecto = api.crear()
    token = api.tomar(proyecto)
    api.enviar_brief(proyecto, BRIEF)
    normalizar = api.orden(proyecto, token)
    api.registrar(proyecto, token, normalizar["id"], [])
    assert api.estado(proyecto)["intentos_paso"] == 1

    api.enviar_brief(proyecto, BRIEF, TEXTO_LIBRE)
    extraccion = api.orden(proyecto, token)
    assert (extraccion["agente"], extraccion["intento"]) == ("extractor-hechos", 1)
    assert extraccion["entrada"]["informe_anterior"] is None


def test_otro_texto_libre_se_vuelve_a_extraer_y_lo_del_anterior_no_vale(api: ClienteApi) -> None:
    proyecto, token, hechos = _con_hechos(api)
    _confirmar(api, proyecto, [{"hecho": hechos[0]["id"], "confirmado": True}])

    assert api.enviar_brief(proyecto, BRIEF, OTRO_TEXTO).status_code == 200
    assert api.http.get(f"/proyectos/{proyecto}/hechos").json() == {"hechos": []}
    with api.abrir(proyecto) as abierto:
        assert abierto.conexion.execute("SELECT count(*) FROM hecho_propuesto").fetchone()[0] == 0
    extraccion = api.orden(proyecto, token)
    assert (extraccion["agente"], extraccion["intento"]) == ("extractor-hechos", 1)
    assert _texto_de(api, extraccion) == OTRO_TEXTO


def test_retirar_el_texto_libre_borra_su_fichero_y_lo_extraido(api: ClienteApi) -> None:
    proyecto = api.crear()
    token = api.tomar(proyecto)
    api.enviar_brief(proyecto, BRIEF, TEXTO_LIBRE)
    anterior = api.orden(proyecto, token)
    identificador = anterior["entrada"]["texto_libre"]["identificador"]
    api.aceptado(proyecto, token, anterior["id"], {"hechos": [HECHO]})

    assert api.enviar_brief(proyecto, BRIEF).json()["texto_libre"] is False
    with api.abrir(proyecto) as abierto:
        assert not abierto.disposicion.texto_libre.exists()
        fila = abierto.conexion.execute("SELECT ruta_texto_libre, extraccion FROM brief")
        assert tuple(fila.fetchone()) == (None, None)
    assert api.http.get(f"/proyectos/{proyecto}/hechos").json() == {"hechos": []}
    with pytest.raises(EntradaNoCanjeable):
        canjear(identificador, api.reloj.ahora, api.raiz)
    assert api.orden(proyecto, token)["agente"] == "agente-contexto"


def test_el_mismo_texto_libre_conserva_la_extraccion_y_sus_hechos(api: ClienteApi) -> None:
    proyecto, token, hechos = _con_hechos(api)
    reenvio = api.enviar_brief(proyecto, {**BRIEF, "dedicatoria": "Para Aitana"}, TEXTO_LIBRE)
    assert reenvio.status_code == 200, reenvio.text
    pendientes = api.http.get(f"/proyectos/{proyecto}/hechos").json()["hechos"]
    assert [h["id"] for h in pendientes] == [h["id"] for h in hechos]
    assert api.siguiente(proyecto, token) == {
        "decision": "esperar_humano",
        "motivo": "confirmacion_hechos",
    }
