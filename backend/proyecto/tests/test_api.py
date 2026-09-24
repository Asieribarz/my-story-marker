"""Paso 3 y bloque 2 · la API transversal con `TestClient`: el flujo de intake a
planificación, la siguiente orden con su sello y el registro de la salida cruda (RF-03,
RF-06, RF-08a, RF-77a, §4.1), el bloqueo (V-34, RF-09b), la auditoría de la policy
(§4.1.9), el borrado (RF-09a) y el modelo de error de spec-backend-1.md §5.1.

Todos los datos de persona son ficticios.
"""

import json
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

from backend.app import ROUTERS
from backend.proyecto.dependencias import CABECERA_BLOQUEO, RutaJsonEstricto
from backend.proyecto.errores import CodigoError
from backend.proyecto.errores_http import ESTADO_HTTP
from backend.proyecto.tests.apoyo import (
    BRIEF,
    HECHO,
    NORMALIZADO,
    TEXTO_LIBRE,
    contexto_con_el_hecho,
    transiciones,
)
from backend.proyecto.tests.cliente_api import (
    ClienteApi,
    Respuesta,
    cliente_api,
    con_token,
    error,
)

SIN_PROYECTO = "0" * 32


@pytest.fixture
def api(tmp_path: Path) -> Iterator[ClienteApi]:
    with cliente_api(tmp_path) as cliente:
        yield cliente


# ─── El flujo feliz ──────────────────────────────────────────────────────────


def test_de_intake_a_planificacion_con_texto_libre_y_hechos(api: ClienteApi) -> None:
    proyecto = api.crear()
    assert api.estado(proyecto)["estado"] == "intake"
    token = api.tomar(proyecto)
    assert api.siguiente(proyecto, token) == {"decision": "esperar_humano", "motivo": "brief"}

    brief = api.enviar_brief(proyecto, BRIEF, TEXTO_LIBRE)
    assert brief.status_code == 200, brief.text
    assert brief.json() == {"descartes": [], "texto_libre": True}

    extraccion = api.orden(proyecto, token)
    assert (extraccion["agente"], extraccion["intento"], extraccion["registro"]) == (
        "extractor-hechos",
        1,
        "skill",
    )
    assert extraccion["entrada"]["necesita"] == ["texto_libre"]
    registro = api.aceptado(proyecto, token, extraccion["id"], {"hechos": [HECHO]})
    assert (registro["estado"], registro["repetido"]) == ("intake", False)
    assert api.siguiente(proyecto, token) == {
        "decision": "esperar_humano",
        "motivo": "confirmacion_hechos",
    }

    pendientes = api.http.get(f"/proyectos/{proyecto}/hechos").json()["hechos"]
    assert [(h["tipo"], h["texto"]) for h in pendientes] == [(HECHO["tipo"], HECHO["texto"])]
    confirmacion = api.http.post(
        f"/proyectos/{proyecto}/hechos/confirmacion",
        json={"decisiones": [{"hecho": pendientes[0]["id"], "confirmado": True}]},
    )
    assert confirmacion.status_code == 200, confirmacion.text
    assert confirmacion.json() == {"hechos": []}

    normalizar = api.orden(proyecto, token)
    assert normalizar["agente"] == "agente-contexto"
    assert normalizar["entrada"]["necesita"] == ["brief", "hechos_confirmados"]
    assert api.aceptado(proyecto, token, normalizar["id"], NORMALIZADO)["estado"] == "contexto"

    instanciar = api.orden(proyecto, token)
    assert (instanciar["agente"], instanciar["estado"]) == ("agente-contexto", "contexto")
    registro = api.aceptado(proyecto, token, instanciar["id"], contexto_con_el_hecho())
    assert registro["estado"] == "planificacion"

    leido = api.estado(proyecto)
    assert (leido["estado"], leido["orden_vigente"], leido["intentos_paso"]) == (
        "planificacion",
        None,
        0,
    )
    with api.abrir(proyecto) as abierto:
        assert transiciones(abierto.conexion) == [
            ("intake", "contexto", "brief_normalizado"),
            ("contexto", "planificacion", "contexto_validado"),
        ]
        assert abierto.conexion.execute("SELECT count(*) FROM contexto").fetchone()[0] == 1

        # B-1: al salir de `contexto`, lo que fija el contexto ya está en la biblia.
        assert abierto.conexion.execute("SELECT count(*) FROM personaje").fetchone()[0] > 0

    # El planificador ya tiene esquema: una salida que no encaja es un intento fallido.
    planificador = api.orden(proyecto, token)
    assert planificador["agente"] == "planificador"
    assert planificador["sello"] == f"{proyecto}:{planificador['id']}:1"
    fallido = api.registrar(proyecto, token, planificador["id"], {"plan": {}})
    assert fallido.status_code == 200, fallido.text
    assert (fallido.json()["desenlace"], fallido.json()["tipo"]) == ("rechazada", "fallo_forma")
    assert api.estado(proyecto)["intentos_paso"] == 1


def test_sin_texto_libre_no_hay_extraccion(api: ClienteApi) -> None:
    proyecto = api.crear()
    token = api.tomar(proyecto)
    assert api.enviar_brief(proyecto, BRIEF).json() == {"descartes": [], "texto_libre": False}
    assert api.orden(proyecto, token)["agente"] == "agente-contexto"


def test_crear_con_las_paradas_activas(api: ClienteApi) -> None:
    respuesta = api.http.post("/proyectos", json={"parada_plan": True})
    assert respuesta.status_code == 201
    creado = respuesta.json()
    assert (creado["parada_plan"], creado["parada_final"], creado["bloqueo"]) == (
        True,
        False,
        None,
    )
    assert [(c["numero"], c["estado"]) for c in creado["capitulos"]] == [
        (n, "pendiente") for n in range(1, 11)
    ]


# ─── Siguiente orden y registro (RF-06, RF-08a, TC-11) ───────────────────────


def _sello(api: ClienteApi, proyecto: str, orden: int) -> str:
    with api.abrir(proyecto) as abierto:
        fila = abierto.conexion.execute("SELECT sello FROM orden WHERE id = ?", (orden,))
        sello: str = fila.fetchone()[0]
    return sello


def _extraccion(api: ClienteApi) -> tuple[str, str, int]:
    proyecto = api.crear()
    token = api.tomar(proyecto)
    api.enviar_brief(proyecto, BRIEF, TEXTO_LIBRE)
    return proyecto, token, int(api.orden(proyecto, token)["id"])


def test_pedir_la_orden_dos_veces_devuelve_la_misma(api: ClienteApi) -> None:
    proyecto, token, orden = _extraccion(api)
    otra = api.siguiente(proyecto, token)["orden"]
    assert otra["id"] == orden
    # El estado enseña la misma orden, sin el identificador de un solo uso (RF-14).
    # Tampoco el sello: con él se escribe en la biblia por `/mcp/escritura` (AJ-4).
    vista = api.estado(proyecto)["orden_vigente"]
    entrada = otra["entrada"]
    sin_identificador = {**entrada, "texto_libre": {"caduca": entrada["texto_libre"]["caduca"]}}
    assert otra["sello"]
    assert vista == {**otra, "entrada": sin_identificador, "sello": None}


def test_el_mismo_resultado_es_idempotente_y_otro_se_rechaza(api: ClienteApi) -> None:
    proyecto, token, orden = _extraccion(api)
    primero = api.aceptado(proyecto, token, orden, {"hechos": [HECHO]})
    repetido = api.aceptado(proyecto, token, orden, {"hechos": [HECHO]})
    assert repetido == {**primero, "repetido": True}

    distinto = api.registrar(proyecto, token, orden, {"hechos": []})
    assert error(distinto) == (409, "orden_ajena", "RF-08a")
    inexistente = api.registrar(proyecto, token, orden + 7, {"hechos": []})
    assert error(inexistente) == (409, "sello_invalido", "RF-08a")
    assert len(api.http.get(f"/proyectos/{proyecto}/hechos").json()["hechos"]) == 1


def test_un_resultado_fuera_de_esquema_es_un_intento_fallido_con_200(api: ClienteApi) -> None:
    proyecto, token, orden = _extraccion(api)
    fallido = api.registrar(proyecto, token, orden, ["no es un sobre"])
    assert fallido.status_code == 200, fallido.text
    registro = fallido.json()
    assert (registro["desenlace"], registro["tipo"]) == ("rechazada", "fallo_forma")

    reintento = api.orden(proyecto, token)
    assert (reintento["intento"], reintento["entrada"]["informe_anterior"]) == (
        2,
        registro["detalle"],
    )


def test_agotado_el_tope_se_detiene_y_reintentar_vuelve_a_la_fase(api: ClienteApi) -> None:
    proyecto, token, _ = _extraccion(api)
    for _ in range(3):
        orden = api.orden(proyecto, token)
        assert api.registrar(proyecto, token, orden["id"], "mal").status_code == 200
    assert api.siguiente(proyecto, token) == {"decision": "detenida", "desde": "intake"}
    detenida = api.estado(proyecto)
    assert (detenida["estado"], detenida["detenida_desde"]) == ("detenida", "intake")

    # Reintentar es una acción humana: no lleva el token del bloqueo.
    vuelta = api.http.post(f"/proyectos/{proyecto}/reintentar", json={"notas": "otra vez"})
    assert vuelta.status_code == 200, vuelta.text
    assert (vuelta.json()["estado"], vuelta.json()["detenida_desde"]) == ("intake", None)
    assert api.orden(proyecto, token)["intento"] == 1


# ─── V-34 · bloqueo por proyecto (RF-09b, Q7) ────────────────────────────────


def test_con_el_bloqueo_tomado_otro_ejecutor_no_recibe_orden_y_al_caducar_si(
    api: ClienteApi,
) -> None:
    proyecto = api.crear()
    sesion = api.tomar(proyecto, "sesion")

    ajeno = api.http.post(f"/proyectos/{proyecto}/bloqueo", json={"tipo": "worker"})
    assert error(ajeno) == (423, "bloqueo_ajeno", "RF-09b")
    assert "sesion" in ajeno.json()["detalle"]
    assert "2026-09-23T10:30:00+00:00" in ajeno.json()["detalle"]
    assert error(api.http.post(f"/proyectos/{proyecto}/siguiente")) == (
        428,
        "bloqueo_requerido",
        "RF-09b",
    )
    assert error(api.pedir(proyecto, "token-inventado")) == (423, "bloqueo_ajeno", "RF-09b")

    api.reloj.avanzar(30)
    worker = api.tomar(proyecto, "worker")
    assert api.siguiente(proyecto, worker)["decision"] == "esperar_humano"
    assert error(api.pedir(proyecto, sesion)) == (423, "bloqueo_ajeno", "RF-09b")
    visible = api.estado(proyecto)["bloqueo"]
    assert visible == {"tipo": "worker", "caduca": "2026-09-23T11:00:00Z"}


def test_renovar_alarga_el_bloqueo_y_soltarlo_lo_libera(api: ClienteApi) -> None:
    proyecto = api.crear()
    token = api.tomar(proyecto)
    api.reloj.avanzar(20)
    renovado = api.http.post(f"/proyectos/{proyecto}/bloqueo", headers=con_token(token))
    assert renovado.status_code == 200, renovado.text
    assert renovado.json() == {"token": token, "tipo": "sesion", "caduca": "2026-09-23T10:50:00Z"}

    api.reloj.avanzar(20)
    assert api.pedir(proyecto, token).status_code == 200
    soltado = api.http.delete(f"/proyectos/{proyecto}/bloqueo", headers=con_token(token))
    assert (soltado.status_code, soltado.content) == (204, b"")
    assert api.estado(proyecto)["bloqueo"] is None
    assert error(api.pedir(proyecto, token)) == (428, "bloqueo_requerido", "RF-09b")


def test_renovar_un_bloqueo_caducado_pide_volver_a_tomarlo(api: ClienteApi) -> None:
    proyecto = api.crear()
    token = api.tomar(proyecto)
    api.reloj.avanzar(31)
    caducado = api.http.post(f"/proyectos/{proyecto}/bloqueo", headers=con_token(token))
    assert error(caducado) == (428, "bloqueo_requerido", "RF-09b")
    assert error(api.http.post(f"/proyectos/{proyecto}/bloqueo")) == (422, "validacion", None)


def test_borrar_se_deniega_con_el_bloqueo_vigente_y_borra_sin_el(api: ClienteApi) -> None:
    proyecto = api.crear()
    api.enviar_brief(proyecto, BRIEF, TEXTO_LIBRE)
    token = api.tomar(proyecto)
    assert error(api.http.delete(f"/proyectos/{proyecto}")) == (423, "bloqueo_ajeno", "RF-09b")
    assert (api.raiz / "novelas" / proyecto).is_dir()

    api.http.delete(f"/proyectos/{proyecto}/bloqueo", headers=con_token(token))
    borrado = api.http.delete(f"/proyectos/{proyecto}")
    assert borrado.status_code == 204, borrado.text
    assert not (api.raiz / "novelas" / proyecto).exists()
    ausente = api.http.get(f"/proyectos/{proyecto}/estado")
    assert error(ausente) == (404, "proyecto_inexistente", "RF-02")


# ─── La composición (Q9) ─────────────────────────────────────────────────────


def test_la_aplicacion_publica_las_rutas_de_cada_rebanada(api: ClienteApi) -> None:
    especificacion = api.http.get("/openapi.json")
    assert especificacion.status_code == 200
    rutas = {
        (metodo.upper(), ruta)
        for ruta, metodos in especificacion.json()["paths"].items()
        for metodo in metodos
    }
    p = "/proyectos/{id}"
    assert rutas == {
        ("POST", "/proyectos"),
        ("GET", "/proyectos"),
        ("GET", f"{p}/metricas"),
        ("GET", f"{p}/estado"),
        ("POST", f"{p}/siguiente"),
        ("POST", f"{p}/resultado"),
        ("POST", f"{p}/bloqueo"),
        ("DELETE", f"{p}/bloqueo"),
        ("POST", f"{p}/reintentar"),
        ("POST", f"{p}/plan/aprobacion"),
        ("POST", f"{p}/aprobacion-final"),
        ("POST", f"{p}/auditoria"),
        ("DELETE", p),
        ("POST", f"{p}/brief"),
        ("GET", f"{p}/hechos"),
        ("POST", f"{p}/hechos/confirmacion"),
        ("POST", f"{p}/contexto/validar"),
        ("GET", f"{p}/plan"),
        ("GET", f"{p}/escaleta"),
        ("GET", f"{p}/versiones"),
        ("GET", f"{p}/versiones/{{version}}/lectura"),
        ("GET", f"{p}/versiones/{{version}}/capitulos/{{numero}}"),
        ("GET", f"{p}/versiones/{{version}}/manuscrito"),
        ("GET", f"{p}/versiones/{{version}}/pdf"),
        ("POST", f"{p}/manuscrito/juez"),
        ("GET", f"{p}/manuscrito/juez"),
        ("POST", f"{p}/cambios"),
        ("POST", f"{p}/generacion"),
        ("GET", f"{p}/cambios/{{cambio}}"),
        ("POST", f"{p}/cambios/{{cambio}}/confirmacion"),
    }


# ─── El modelo de error (spec-backend-1.md §5.1, TC-11) ───────────────────────────────


def test_cada_codigo_del_catalogo_tiene_su_estado_http() -> None:
    assert set(ESTADO_HTTP) == set(CodigoError)


def test_una_transicion_invalida_no_es_un_error_de_validacion(api: ClienteApi) -> None:
    proyecto = api.crear()
    fuera_de_parada = api.http.post(f"/proyectos/{proyecto}/reintentar")
    assert error(fuera_de_parada) == (409, "transicion_invalida", "RF-04")
    mal_formada = api.http.post(f"/proyectos/{proyecto}/reintentar", json={"notas": 3})
    assert error(mal_formada) == (422, "validacion", None)
    assert api.estado(proyecto)["estado"] == "intake"


@pytest.mark.parametrize(
    "ruta",
    [f"/proyectos/{SIN_PROYECTO}/estado", "/proyectos/no-es-un-identificador/estado"],
)
def test_un_proyecto_que_no_existe_da_404(api: ClienteApi, ruta: str) -> None:
    assert error(api.http.get(ruta)) == (404, "proyecto_inexistente", "RF-02")


def test_una_ruta_que_no_existe_da_404_con_el_mismo_cuerpo(api: ClienteApi) -> None:
    assert error(api.http.get("/no-existe")) == (404, "no_encontrado", None)


def test_el_error_de_validacion_no_repite_el_valor_recibido(api: ClienteApi) -> None:
    proyecto = api.crear()
    token = api.tomar(proyecto)
    valor = "nadie@ejemplo.invalid"
    respuesta = api.http.post(
        f"/proyectos/{proyecto}/resultado", json={"orden": [valor]}, headers=con_token(token)
    )
    assert error(respuesta) == (422, "validacion", None)
    detalle = respuesta.json()["detalle"]
    assert "body.orden" in detalle and "body.salida_cruda" in detalle
    assert valor not in detalle


# ─── Borrar con otra conexión abierta (RF-09a) ───────────────────────────────


@pytest.mark.skipif(sys.platform != "win32", reason="solo Windows impide mover una base abierta")
def test_borrar_con_la_base_abierta_por_otra_peticion_no_borra_nada(api: ClienteApi) -> None:
    proyecto = api.crear()
    api.enviar_brief(proyecto, BRIEF, TEXTO_LIBRE)
    with api.abrir(proyecto) as abierto:
        en_uso = api.http.delete(f"/proyectos/{proyecto}")
        assert error(en_uso) == (409, "proyecto_en_uso", "RF-09a")
        assert abierto.disposicion.texto_libre.read_text(encoding="utf-8") == TEXTO_LIBRE
    assert api.estado(proyecto)["estado"] == "intake"
    assert api.http.delete(f"/proyectos/{proyecto}").status_code == 204
    assert not (api.raiz / "novelas" / proyecto).exists()


# ─── Cuerpos que no son JSON estricto ────────────────────────────────────────

_JSON = {"content-type": "application/json"}


def _crudo(api: ClienteApi, ruta: str, cuerpo: str, token: str | None = None) -> Respuesta:
    cabeceras = _JSON if token is None else {**_JSON, **con_token(token)}
    return api.http.post(ruta, content=cuerpo.encode("ascii"), headers=cabeceras)


def test_toda_ruta_lee_json_estricto_salvo_la_del_resultado() -> None:
    """La salida cruda puede traer un sustituto suelto: es un intento fallido, no un 422."""
    rutas = [r for router in ROUTERS for r in router.routes if isinstance(r, APIRoute)]
    laxas = {
        (r.path, *sorted(r.methods or ())) for r in rutas if not isinstance(r, RutaJsonEstricto)
    }
    assert laxas == {("/proyectos/{id}/resultado", "POST")}
    assert all(type(r) is APIRoute for r in rutas if not isinstance(r, RutaJsonEstricto))


@pytest.mark.parametrize(
    ("valor", "motivo"),
    [
        ("NaN", "NaN, Infinity y -Infinity"),
        ("-Infinity", "NaN, Infinity y -Infinity"),
        ('"sin \\ud800 pareja"', "sustituto suelto"),
    ],
)
def test_un_resultado_fuera_de_json_estricto_es_un_intento_fallido(
    api: ClienteApi, valor: str, motivo: str
) -> None:
    """RF-77a, TC-11: un bloque que no es JSON estricto es un fallo de forma con 200, no un
    500 ni un 422 que la sesión repetiría sin fin; el mismo cuerpo otra vez es idempotente."""
    proyecto, token, orden = _extraccion(api)
    salida = '```json\n{"hechos": [{"texto": ' + valor + "}]}\n```"
    cuerpo = json.dumps({"orden": _sello(api, proyecto, orden), "salida_cruda": salida})
    fallido = _crudo(api, f"/proyectos/{proyecto}/resultado", cuerpo, token)
    assert fallido.status_code == 200, fallido.text
    registro = fallido.json()
    assert (registro["desenlace"], registro["tipo"]) == ("rechazada", "fallo_forma")
    assert motivo in registro["detalle"]["errores"][0]
    repetido = _crudo(api, f"/proyectos/{proyecto}/resultado", cuerpo, token)
    assert repetido.json() == {**registro, "repetido": True}
    assert api.estado(proyecto)["intentos_paso"] == 1
    assert api.orden(proyecto, token)["intento"] == 2


def test_una_salida_cruda_con_un_sustituto_suelto_es_un_intento_fallido(
    api: ClienteApi,
) -> None:
    """La ruta del resultado lee su cuerpo sin JSON estricto: el texto del modelo no es UTF-8,
    y eso es un fallo de forma, no un 422 ni un 500 al guardarlo."""
    proyecto, token, orden = _extraccion(api)
    cuerpo = f'{{"orden": "{_sello(api, proyecto, orden)}", "salida_cruda": "a \\ud800 b"}}'
    fallido = _crudo(api, f"/proyectos/{proyecto}/resultado", cuerpo, token)
    assert fallido.status_code == 200, fallido.text
    assert "sustituto suelto" in fallido.json()["detalle"]["errores"][0]


@pytest.mark.parametrize(
    ("ruta", "cuerpo"),
    [
        ("brief", '{"respuestas": {"edad": NaN}}'),
        ("brief", '{"respuestas": {"nombre": "Aitana"}, "texto_libre": "a \\udc80 b"}'),
        ("brief", '{"respuestas": {"\\ud800": 1}}'),
        ("contexto/validar", '{"novela": {"titulo": "\\ud800"}}'),
        ("contexto/validar", '{"novela": {"capitulos": Infinity}}'),
        ("reintentar", '{"notas": "\\ud800"}'),
        ("hechos/confirmacion", '{"decisiones": [{"hecho": NaN, "confirmado": true}]}'),
    ],
)
def test_un_cuerpo_fuera_de_json_estricto_es_un_error_de_validacion(
    api: ClienteApi, ruta: str, cuerpo: str
) -> None:
    proyecto = api.crear()
    respuesta = _crudo(api, f"/proyectos/{proyecto}/{ruta}", cuerpo)
    assert error(respuesta) == (422, "validacion", None)
    assert "RFC 8259" in respuesta.json()["detalle"] or "UTF-8" in respuesta.json()["detalle"]
    with api.abrir(proyecto) as abierto:
        assert abierto.conexion.execute("SELECT count(*) FROM brief").fetchone()[0] == 0
        assert not abierto.disposicion.texto_libre.exists()


# ─── Cabecera y enteros fuera de rango ───────────────────────────────────────


@pytest.mark.parametrize("token", ["é".encode("latin-1"), "ñandú".encode("latin-1")])
def test_un_token_con_caracteres_no_ascii_es_un_bloqueo_ajeno(
    api: ClienteApi, token: bytes
) -> None:
    proyecto = api.crear()
    api.tomar(proyecto)
    cabecera = {CABECERA_BLOQUEO.encode("ascii"): token}
    for metodo, ruta in [("POST", "siguiente"), ("POST", "bloqueo"), ("DELETE", "bloqueo")]:
        respuesta = api.http.request(metodo, f"/proyectos/{proyecto}/{ruta}", headers=cabecera)
        assert error(respuesta) == (423, "bloqueo_ajeno", "RF-09b"), (metodo, ruta)


def test_un_sello_de_otro_proyecto_o_mal_formado_no_registra(api: ClienteApi) -> None:
    """AJ-4: el sello identifica la orden; uno que no es de ninguna orden del proyecto da
    `sello_invalido` y no toca nada. Control: el suyo registra."""
    proyecto, token, orden = _extraccion(api)
    for sello in (f"{SIN_PROYECTO}:{orden}:1", "sin-forma", f"{proyecto}:{orden}:0"):
        respuesta = api.registrar_crudo(
            proyecto, token, {"orden": sello, "salida_cruda": '{"hechos": []}'}
        )
        assert error(respuesta) == (409, "sello_invalido", "RF-08a")
    assert api.estado(proyecto)["orden_vigente"]["id"] == orden
    assert api.aceptado(proyecto, token, orden, {"hechos": []})["orden"] == orden


def test_los_metadatos_se_guardan_con_la_orden(api: ClienteApi) -> None:
    """§4.1.8: todos opcionales; los que llegan quedan en la orden al cerrarla."""
    proyecto, token, orden = _extraccion(api)
    metadatos = {"modelo": "sonnet", "tokens_entrada": 1200, "duracion_ms": 900, "otro": 1}
    respuesta = api.registrar(proyecto, token, orden, {"hechos": []}, metadatos=metadatos)
    assert respuesta.status_code == 200, respuesta.text
    with api.abrir(proyecto) as abierto:
        guardado = abierto.conexion.execute("SELECT metadatos FROM orden").fetchone()[0]
    assert json.loads(guardado) == {"modelo": "sonnet", "tokens_entrada": 1200, "duracion_ms": 900}
    negativo = api.registrar(proyecto, token, orden, {"hechos": []}, {"tokens_salida": -1})
    assert error(negativo) == (422, "validacion", None)


# ─── Auditoría de la policy (§4.1.9) ─────────────────────────────────────────


def test_la_auditoria_de_la_policy_queda_en_el_proyecto(api: ClienteApi) -> None:
    proyecto = api.crear()
    decision = {
        "decision": "denegada",
        "herramienta": "Read",
        "agente": "escritor",
        "motivo": "brief/ no se lee con herramientas de fichero",
    }
    assert api.http.post(f"/proyectos/{proyecto}/auditoria", json=decision).status_code == 204
    otra = {**decision, "decision": "quizas"}
    assert error(api.http.post(f"/proyectos/{proyecto}/auditoria", json=otra)) == (
        422,
        "validacion",
        None,
    )
    with api.abrir(proyecto) as abierto:
        filas = abierto.conexion.execute("SELECT tipo, detalle FROM auditoria").fetchall()
    assert [(f["tipo"], json.loads(f["detalle"])) for f in filas] == [("policy", decision)]
