"""Contratos del harness con el backend (specs/plan-agentes.md §4): cabecera de orden, cuerpo
de `/resultado` y estado local."""

from __future__ import annotations

import json

import comun
from apoyo import PROYECTO

ORDEN = {
    "id": 7,
    "agente": "extractor-hechos",
    "intento": 1,
    "capitulo": None,
    "entrada": {"necesita": ["texto_libre"], "identificador": "abc"},
    "registro": "skill",
}


def test_el_prompt_empieza_por_la_cabecera_y_se_lee_de_vuelta() -> None:
    prompt = comun.prompt_para_subagente(PROYECTO, ORDEN)
    assert prompt.splitlines()[0] == f"orden: {PROYECTO}:7"
    cabecera = comun.leer_cabecera(prompt)
    assert cabecera == comun.Cabecera(PROYECTO, f"{PROYECTO}:7")
    assert cabecera.orden == 7
    assert '"identificador": "abc"' in prompt


def test_el_sello_del_backend_es_opaco_y_la_orden_se_busca_por_el() -> None:
    sello = f"{PROYECTO}:7:g3"
    orden = {**ORDEN, "id": 12, "sello": sello}
    comun.guardar_orden(PROYECTO, orden)
    prompt = comun.prompt_para_subagente(PROYECTO, orden)
    assert prompt.splitlines()[0] == f"orden: {sello}"
    cabecera = comun.leer_cabecera(prompt)
    assert cabecera is not None and cabecera.sello == sello
    assert cabecera.orden == 12  # la guardada, no el segmento del sello


def test_sin_cabecera_en_la_primera_linea_no_hay_orden() -> None:
    assert comun.leer_cabecera("hola\norden: " + PROYECTO + ":7") is None
    assert comun.leer_cabecera(None) is None
    assert comun.leer_cabecera("orden: nohex:7") is None


def test_json_se_extrae_del_ultimo_bloque_delimitado() -> None:
    salida = (
        f'orden: {PROYECTO}:7\n\nPienso en voz alta.\n```json\n{{"hechos": []}}\n```\n'
        '```json\n{"hechos": [{"tipo": "rasgo"}]}\n```'
    )
    assert comun.cuerpo_de_resultado(7, "extractor-hechos", salida) == {
        "orden": 7,
        "resultado": {"hechos": [{"tipo": "rasgo"}]},
    }


def test_una_salida_sin_json_valido_se_envia_como_texto_para_que_el_backend_la_rechace() -> None:
    cuerpo = comun.cuerpo_de_resultado(7, "planificador", "```json\n{roto\n```")
    assert cuerpo == {"orden": 7, "resultado": "```json\n{roto\n```"}


def test_el_escritor_devuelve_titulo_y_texto() -> None:
    salida = f"orden: {PROYECTO}:9\n# La brújula\n\nPrimer párrafo.\n\nSegundo."
    assert comun.cuerpo_de_resultado(9, "escritor", salida) == {
        "orden": 9,
        "resultado": {"titulo": "La brújula", "texto": "Primer párrafo.\n\nSegundo."},
    }


def test_el_estado_local_guarda_bloqueo_orden_y_acuse(estado_temporal) -> None:  # type: ignore[no-untyped-def]
    comun.guardar_bloqueo(PROYECTO, {"token": "t", "tipo": "sesion", "caduca": "x"})
    comun.guardar_orden(PROYECTO, ORDEN)
    comun.guardar_acuse(PROYECTO, 7, {"registrado": True})
    assert comun.leer_token(PROYECTO) == "t"
    assert comun.leer_orden(PROYECTO) == ORDEN
    assert comun.leer_acuse(PROYECTO, 7)["registrado"] is True  # type: ignore[index]
    assert (estado_temporal / ".gitignore").read_text(encoding="utf-8") == "*\n"
    comun.borrar_bloqueo(PROYECTO)
    assert comun.leer_token(PROYECTO) is None


def test_el_resumen_acota_el_informe() -> None:
    resumen = comun.resumen_registro({"orden": 1, "detalle": {"x": "y" * 100}}, limite=20)
    assert resumen["detalle"].endswith("…(recortado)")
    assert json.loads(comun.resumen_registro({"detalle": {"a": 1}})["detalle"]) == {"a": 1}
