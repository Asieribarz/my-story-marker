"""El hook `SubagentStop` de punta a punta contra un backend falso (A-4, A-5, P-2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import comun
import msm
import subagente
from apoyo import PROYECTO, BackendFalso


def transcript(tmp_path: Path, prompt: str) -> Path:
    ruta = tmp_path / "agente.jsonl"
    lineas: list[dict[str, Any]] = [
        {"type": "user", "timestamp": "2026-09-23T10:00:00Z", "message": {"content": prompt}},
        {
            "type": "assistant",
            "timestamp": "2026-09-23T10:00:03Z",
            "message": {
                "id": "m1",
                "model": "claude-haiku-4-5",
                "usage": {"input_tokens": 5, "output_tokens": 50},
            },
        },
    ]
    ruta.write_text("\n".join(json.dumps(x) for x in lineas), encoding="utf-8")
    return ruta


def evento(ruta: Path, agente: str, salida: str) -> dict[str, Any]:
    return {
        "hook_event_name": "SubagentStop",
        "agent_type": agente,
        "agent_id": "a1",
        "agent_transcript_path": str(ruta),
        "last_assistant_message": salida,
    }


def preparar(backend: BackendFalso, orden: dict[str, Any]) -> None:
    comun.guardar_bloqueo(PROYECTO, {"token": "tok", "tipo": "sesion", "caduca": "x"})
    comun.guardar_orden(PROYECTO, orden)
    backend.respuestas[("POST", f"/proyectos/{PROYECTO}/resultado")] = (
        200,
        {"orden": orden["id"], "agente": orden["agente"], "desenlace": "aceptada", "detalle": {}},
    )


def test_registra_toda_salida_aunque_la_orden_diga_skill(
    tmp_path: Path, backend: BackendFalso, estado_temporal: Path
) -> None:
    orden = {"id": 3, "agente": "extractor-hechos", "intento": 1, "registro": "skill"}
    preparar(backend, orden)
    prompt = comun.prompt_para_subagente(PROYECTO, orden)
    salida = f'orden: {PROYECTO}:3\n```json\n{{"hechos": []}}\n```'

    assert (
        subagente.procesar(evento(transcript(tmp_path, prompt), "extractor-hechos", salida))
        == "registrada"
    )

    [peticion] = backend.peticiones
    assert peticion["token"] == "tok"
    assert peticion["cuerpo"]["orden"] == f"{PROYECTO}:3"
    assert peticion["cuerpo"]["salida_cruda"] == salida
    assert comun.leer_acuse(PROYECTO, 3)["registrado"] is True  # type: ignore[index]
    [uso] = [json.loads(x) for x in (estado_temporal / "uso.jsonl").read_text("utf-8").splitlines()]
    assert uso["agente"] == "extractor-hechos" and uso["tokens"]["output_tokens"] == 50
    assert uso["duracion_ms"] == 3000
    assert uso["version_prompt"] == subagente.version_prompt("extractor-hechos")


def test_msm_acuse_ensena_lo_que_registro_el_hook(
    tmp_path: Path, backend: BackendFalso, capsys: Any
) -> None:
    orden = {"id": 4, "agente": "escritor", "intento": 1, "registro": "hook_validacion"}
    preparar(backend, orden)
    ruta = transcript(tmp_path, comun.prompt_para_subagente(PROYECTO, orden))
    subagente.procesar(evento(ruta, "escritor", f"orden: {PROYECTO}:4\n# T\n\nTexto."))
    assert msm.main(["acuse", PROYECTO]) == 0
    assert json.loads(capsys.readouterr().out)["desenlace"] == "aceptada"


def test_msm_acuse_espera_a_que_el_hook_termine(
    tmp_path: Path, backend: BackendFalso, capsys: Any, monkeypatch: Any
) -> None:
    orden = {"id": 6, "agente": "escritor", "intento": 1, "registro": "hook_validacion"}
    preparar(backend, orden)
    ruta = transcript(tmp_path, comun.prompt_para_subagente(PROYECTO, orden))
    esperas: list[float] = []

    def dormir(segundos: float) -> None:  # el hook termina durante la primera espera
        esperas.append(segundos)
        subagente.procesar(evento(ruta, "escritor", f"orden: {PROYECTO}:6\n# T\n\nTexto."))

    monkeypatch.setattr(msm.time, "sleep", dormir)
    assert msm.main(["acuse", PROYECTO]) == 0
    assert esperas == [msm.ESPERA_ENTRE_LECTURAS]
    assert json.loads(capsys.readouterr().out)["desenlace"] == "aceptada"


def test_msm_acuse_sin_hook_se_rinde_al_agotar_la_espera(capsys: Any) -> None:
    comun.guardar_orden(PROYECTO, {"id": 7, "agente": "escritor", "intento": 1})
    assert msm.main(["acuse", PROYECTO, "--espera", "0"]) == 4
    assert "no dejó acuse" in capsys.readouterr().out


def test_sin_backend_el_acuse_lleva_el_error_y_msm_lo_dice(
    tmp_path: Path, monkeypatch: Any, capsys: Any
) -> None:
    monkeypatch.setenv("MSM_BACKEND", "http://127.0.0.1:9")
    orden = {"id": 5, "agente": "planificador", "intento": 1}
    comun.guardar_bloqueo(PROYECTO, {"token": "tok", "tipo": "sesion", "caduca": "x"})
    comun.guardar_orden(PROYECTO, orden)
    ruta = transcript(tmp_path, comun.prompt_para_subagente(PROYECTO, orden))
    assert subagente.procesar(evento(ruta, "planificador", "x")) == "registro fallido"
    assert msm.main(["acuse", PROYECTO]) == 3
    assert "no pudo registrar" in capsys.readouterr().out


def test_con_el_contrato_final_va_la_salida_cruda_con_el_sello_y_los_metadatos(
    tmp_path: Path, backend: BackendFalso, monkeypatch: Any
) -> None:
    monkeypatch.setattr(comun, "CONTRATO_RESULTADO", "salida_cruda")
    sello = f"{PROYECTO}:8:g2"
    orden = {"id": 8, "agente": "escritor", "intento": 1, "sello": sello}
    preparar(backend, orden)
    ruta = transcript(tmp_path, comun.prompt_para_subagente(PROYECTO, orden))
    salida = "# T\n\nTexto."  # sin repetir el sello: es opcional
    assert subagente.procesar(evento(ruta, "escritor", salida)) == "registrada"
    [peticion] = backend.peticiones
    assert peticion["cuerpo"]["orden"] == sello
    assert peticion["cuerpo"]["salida_cruda"] == salida
    assert peticion["cuerpo"]["metadatos"]["tokens_salida"] == 50
    assert peticion["cuerpo"]["metadatos"]["modelo"] == "claude-haiku-4-5"


def test_no_toca_subagentes_ajenos_a_la_novela(tmp_path: Path, backend: BackendFalso) -> None:
    ruta = transcript(tmp_path, "Busca en el repo dónde se define X")
    assert subagente.procesar(evento(ruta, "Explore", "…")).startswith("ignorado")
    assert subagente.procesar(evento(ruta, "escritor", "…")).startswith("ignorado")
    assert backend.peticiones == []


def test_no_registra_bajo_la_orden_de_otro_agente(tmp_path: Path, backend: BackendFalso) -> None:
    orden = {"id": 6, "agente": "escritor", "intento": 1}
    preparar(backend, orden)
    ruta = transcript(tmp_path, comun.prompt_para_subagente(PROYECTO, orden))
    assert subagente.procesar(evento(ruta, "revisor", "x")) == "agente distinto del de la orden"
    assert backend.peticiones == []


def test_la_entrega_por_subagent_handback_manda_sobre_el_ultimo_mensaje(
    tmp_path: Path, backend: BackendFalso, estado_temporal: Path
) -> None:
    orden = {"id": 3, "agente": "extractor-hechos", "intento": 1, "registro": "skill"}
    preparar(backend, orden)
    ruta = transcript(tmp_path, comun.prompt_para_subagente(PROYECTO, orden))
    entregada = f'orden: {PROYECTO}:3\n```json\n{{"hechos": []}}\n```'
    bloque = {"type": "tool_use", "name": "SubagentHandback", "input": {"message": entregada}}
    with ruta.open("a", encoding="utf-8") as fichero:
        fichero.write("\n" + json.dumps({"type": "assistant", "message": {"content": [bloque]}}))

    subagente.procesar(evento(ruta, "extractor-hechos", "Entregado correctamente."))

    [peticion] = backend.peticiones
    assert peticion["cuerpo"]["salida_cruda"] == entregada


def test_vale_la_salida_que_trae_la_cabecera_de_orden() -> None:
    entrega = f'orden: {PROYECTO}:3\n```json\n{{"hechos": []}}\n```'
    assert subagente.elegir_salida("Entregado.", [entrega, "Resumen.", "Entregado."]) == entrega
    assert subagente.elegir_salida(entrega, ["Entregado en el mensaje final."]) == entrega
    assert subagente.elegir_salida("Resumen.", ["Otro resumen."]) == "Resumen."
    assert subagente.elegir_salida("", ["Solo el texto."]) == "Solo el texto."
