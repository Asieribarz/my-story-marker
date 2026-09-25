"""Hook `SubagentStop`: registro de salidas y captura de uso (specs/plan-agentes.md §5.3).

Es la única vía de registro de cualquier salida de subagente (spec-backend-2.md §4.1.5,
P-2 cerrada): la skill no registra nada. Solo actúa sobre subagentes de la novela:
`agent_type` de la lista de agentes y un prompt que empieza por la cabecera
`orden: <proyecto>:<n>` (A-4). A los demás —los de las sesiones de desarrollo— no los toca.

Para cada uno:

1. Toma la salida (ver `elegir_salida`) y la guarda en `.claude/estado/`, para diagnosticar
   sin reteclear.
2. Anota el uso leído del transcript y la versión de prompt, el SHA-256 del fichero del
   agente (E-1 b, c). Hasta que exista su contrato (P-6), en `uso.jsonl`.
3. La registra en el backend y deja el acuse, con éxito o con el error, para que
   `msm.py acuse` lo enseñe.

Nunca bloquea: un reintento es una invocación nueva que decide el backend (architecture.md
§3.2), no una continuación de esta. Siempre sale con 0.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import comun  # noqa: E402
import transcript  # noqa: E402


def version_prompt(agente: str) -> str | None:
    ruta = comun.DIR_AGENTES / f"{agente}.md"
    return hashlib.sha256(ruta.read_bytes()).hexdigest() if ruta.exists() else None


def elegir_salida(ultimo: str, textos: list[str]) -> str:
    """La salida que se registra: el último mensaje si empieza por la cabecera `orden:` que
    exige el formato de todos los agentes; si no, el último de `textos` que la traiga,
    porque un subagente en segundo plano puede entregar antes y cerrar con un resumen. Si
    ninguno la trae, el último mensaje, o el último texto si no hay último mensaje."""
    if comun.leer_cabecera(ultimo) is not None:
        return ultimo
    for texto in reversed(textos):
        if comun.leer_cabecera(texto) is not None:
            return texto
    return ultimo or (textos[-1] if textos else "")


def registrar(
    cabecera: comun.Cabecera, orden: int, agente: str, salida: str, meta: dict[str, Any]
) -> dict[str, Any]:
    """El registro por hook. Devuelve el acuse que se guarda, sea cual sea el desenlace.
    El sello sale del prompt que envió el harness, no de la salida del modelo (AJ-4)."""
    proyecto = cabecera.proyecto
    token = comun.leer_token(proyecto)
    if token is None:
        return {"registrado": False, "error": "no hay token de bloqueo guardado para el proyecto"}
    cuerpo = comun.cuerpo_de_resultado(orden, agente, salida, meta, cabecera.sello)
    try:
        respuesta = comun.peticion("POST", f"/proyectos/{proyecto}/resultado", cuerpo, token)
    except comun.ErrorBackend as error:
        return {"registrado": False, "error": str(error), "http": error.estado}
    except comun.SinBackend as error:
        return {"registrado": False, "error": str(error)}
    return {"registrado": True, "respuesta": respuesta}


def procesar(entrada: dict[str, Any]) -> str:
    """Lo que hizo, para la prueba y el registro de errores."""
    agente = entrada.get("agent_type")
    if agente not in comun.AGENTES:
        return "ignorado: no es un agente de la novela"
    ruta = Path(str(entrada.get("agent_transcript_path") or ""))
    prompt = transcript.primer_mensaje_de_usuario(ruta) if ruta.is_file() else None
    cabecera = comun.leer_cabecera(prompt)
    if cabecera is None:
        return "ignorado: el prompt no empieza por la cabecera de orden"
    proyecto, orden = cabecera.proyecto, cabecera.orden
    if orden is None:
        comun.anotar(
            "errores.jsonl",
            {
                "hook": "SubagentStop",
                "proyecto": proyecto,
                "error": "sello de una orden que no pidió msm.py",
            },
        )
        return "sin orden: el sello no es de una orden pedida aquí"
    textos = transcript.textos_del_asistente(ruta) if ruta.is_file() else []
    salida = elegir_salida(str(entrada.get("last_assistant_message") or ""), textos)
    comun.guardar_salida(proyecto, orden, str(agente), salida)

    consumo = transcript.uso(ruta).como_dict() if ruta.is_file() else {}
    version = version_prompt(str(agente))
    comun.anotar(
        "uso.jsonl",
        {
            "proyecto": proyecto,
            "orden": orden,
            "agente": agente,
            "agent_id": entrada.get("agent_id"),
            "version_prompt": version,
            **consumo,
        },
    )
    meta = comun.metadatos(consumo, version)

    # El backend decide si el resultado es de la orden vigente (RF-08a). Aquí solo se evita
    # registrar la salida de un agente bajo la orden de otro, cuando se sabe.
    guardada = comun.leer_orden(proyecto, orden)
    if guardada is not None and guardada.get("agente") != agente:
        comun.guardar_acuse(
            proyecto,
            orden,
            {
                "registrado": False,
                "error": f"la orden {orden} es de {guardada.get('agente')}, no de {agente}",
            },
        )
        return "agente distinto del de la orden"
    acuse = registrar(cabecera, orden, str(agente), salida, meta)
    comun.guardar_acuse(proyecto, orden, acuse)
    return "registrada" if acuse["registrado"] else "registro fallido"


def main() -> int:
    try:
        entrada = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
        procesar(entrada)
    except Exception as error:  # noqa: BLE001 — un hook de registro no tumba la sesión
        try:
            comun.anotar("errores.jsonl", {"hook": "SubagentStop", "error": repr(error)[:500]})
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
