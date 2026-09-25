"""Hook `PreToolUse`: la policy de architecture.md §8 (specs/plan-agentes.md §5.3, A-2).

Decide en local y nunca pregunta al backend: si el backend está caído, lo denegado sigue
denegado. Nunca emite `allow`: solo deniega o deja pasar al flujo normal de permisos.

Reglas, en orden:

1. `mcp__escritura__*`: solo `agent_type == bibliotecario` (RF-102, V-13). Sin `agent_type`
   es la sesión principal, y tampoco.
2. `mcp__entrada__*`: solo el Extractor y el Intérprete (RF-14, RF-120).
3. Escribir con las herramientas de fichero bajo la raíz de proyectos: nunca.
4. Leer `brief/`, `cambios/` o un `texto_libre*.txt`: nunca (E-3). `brief/` y `cambios/`
   cuentan en cualquier nivel bajo la raíz, que es `<raíz>/<grupo>/<proyecto>/`.
5. El Escritor solo lee dentro de `prompts/` de un proyecto (P-3).
6. Bash y PowerShell: las rutas de 3 y 4 por coincidencia de texto. Es una heurística; los
   agentes de la novela no tienen esas herramientas.

Un error inesperado deniega en las herramientas de escritura y de entrada y deja pasar el
resto. Lo que toca un proyecto o una superficie de biblia o de entrada va a la auditoría,
sin el texto de la llamada.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import comun  # noqa: E402

LECTORES_DE_ENTRADA = frozenset({"extractor-hechos", "interprete-cambios"})
ESCRIBEN = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
LEEN = frozenset({"Read", "Grep"})
SHELLS = frozenset({"Bash", "PowerShell"})
PROTEGIDAS = ("brief", "cambios")
_TEXTO_LIBRE = re.compile(r"texto_libre[^\s\"'/\\]*\.txt", re.IGNORECASE)
_ENVIO_PREVISTO = re.compile(r"\.claude/harness/msm\.py[\"']?\s+brief\b")
# La excepción de `msm.py brief` vale para ese comando solo, no para uno encadenado a él.
_ENCADENA = re.compile(r";|&&|\|\||\||`|\$\(|>|<(?!<)|\n")


@dataclass(frozen=True)
class Decision:
    permitir: bool
    regla: str
    motivo: str = ""
    auditar: bool = False
    proyecto: str | None = None


PASA = Decision(True, "sin_regla")


def _ruta_de(entrada: dict[str, Any]) -> Path | None:
    datos = entrada.get("tool_input") or {}
    valor = datos.get("file_path") or datos.get("notebook_path") or datos.get("path")
    if not isinstance(valor, str) or not valor:
        return None
    ruta = Path(valor)
    if not ruta.is_absolute():
        ruta = Path(entrada.get("cwd") or Path.cwd()) / ruta
    return Path(_normalizar(str(ruta)))


def _normalizar(texto: str) -> str:
    return str(PurePath(texto)).replace("\\", "/").rstrip("/").lower()


def _dentro(ruta: Path, raiz: Path) -> PurePath | None:
    """La ruta relativa a `raiz` si `ruta` cae dentro, comparando sin mayúsculas (Windows)."""
    r, b = _normalizar(str(ruta)), _normalizar(str(raiz))
    if r == b:
        return PurePath()
    if r.startswith(b + "/"):
        return PurePath(r[len(b) + 1 :])
    return None


def _partes_del_proyecto(relativa: PurePath | None) -> tuple[str, ...]:
    """La ruta relativa a la raíz sin el grupo: `(<identificador>, <carpeta>, …)`. Una ruta
    sin grupo delante, de antes de los grupos, se toma tal cual."""
    partes = relativa.parts if relativa is not None else ()
    return partes[1:] if partes and partes[0] in comun.GRUPOS else partes


def _proyecto_de(relativa: PurePath | None) -> str | None:
    partes = _partes_del_proyecto(relativa)
    if not partes:
        return None
    return partes[0] if re.fullmatch(r"[0-9a-f]{32}", partes[0]) else None


def _deniega(regla: str, motivo: str, proyecto: str | None = None) -> Decision:
    return Decision(False, regla, motivo, auditar=True, proyecto=proyecto)


def _mcp(herramienta: str, agente: str | None) -> Decision:
    if herramienta.startswith("mcp__escritura__"):
        if agente == "bibliotecario":
            return Decision(True, "escritura_bibliotecario", auditar=True)
        quien = agente or "la sesión principal"
        return _deniega(
            "escritura_solo_bibliotecario",
            f"La escritura en la biblia es solo del Bibliotecario (RF-102); la ha pedido {quien}.",
        )
    if herramienta.startswith("mcp__entrada__"):
        if agente in LECTORES_DE_ENTRADA:
            return Decision(True, "entrada_lector_previsto", auditar=True)
        quien = agente or "la sesión principal"
        return _deniega(
            "entrada_solo_extractor_interprete",
            f"El texto no confiable solo lo leen el Extractor y el Intérprete (RF-14); "
            f"lo ha pedido {quien}.",
        )
    return PASA


def _fichero(entrada: dict[str, Any], herramienta: str, agente: str | None) -> Decision:
    ruta = _ruta_de(entrada)
    if ruta is None:
        return PASA
    raiz = comun.raiz_proyectos(Path(entrada.get("cwd") or Path.cwd()))
    relativa = _dentro(ruta, raiz)
    proyecto = _proyecto_de(relativa)
    if herramienta in ESCRIBEN:
        if relativa is not None:
            return _deniega(
                "sin_escritura_en_proyectos",
                "Los datos del proyecto solo se escriben por la API o el MCP, nunca con las "
                "herramientas de fichero (architecture.md §8).",
                proyecto,
            )
        return PASA
    if herramienta not in LEEN:
        return PASA
    if _TEXTO_LIBRE.search(ruta.name):
        return _deniega(
            "sin_lectura_de_texto_libre",
            "El texto libre es no confiable y no pasa por esta ventana (E-3); solo lo lee el "
            "Extractor por /mcp/entrada.",
            proyecto,
        )
    partes = _partes_del_proyecto(relativa)
    # Cualquier nivel bajo la raíz, no solo el de la carpeta del proyecto: si la disposición
    # vuelve a cambiar, la regla no se queda mirando el nivel equivocado.
    protegida = next((p for p in (relativa.parts if relativa else ()) if p in PROTEGIDAS), None)
    if protegida is not None:
        return _deniega(
            "sin_lectura_de_no_confiable",
            f"`{protegida}/` guarda texto no confiable del comprador o del lector; solo lo "
            "leen el Extractor y el Intérprete por /mcp/entrada (RF-14, RF-120).",
            proyecto,
        )
    if agente == "escritor":
        if len(partes) >= 2 and partes[1] == "prompts":
            return Decision(True, "escritor_lee_su_prompt", auditar=True, proyecto=proyecto)
        return _deniega(
            "escritor_solo_prompts",
            "El Escritor solo lee su prompt ensamblado, en prompts/ del proyecto (§6.3).",
            proyecto,
        )
    if relativa is not None:
        return Decision(True, "lectura_en_proyecto", auditar=True, proyecto=proyecto)
    return PASA


def _sin_heredoc(comando: str) -> str:
    """La primera línea, sin el `<<'EOF'` con que la skill pasa las respuestas por stdin: el
    cuerpo del heredoc son datos, no comandos."""
    primera = comando.split("\n", 1)[0]
    return re.sub(r"<<-?\s*['\"]?\w+['\"]?\s*$", "", primera)


def _shell(entrada: dict[str, Any]) -> Decision:
    comando = str((entrada.get("tool_input") or {}).get("command") or "")
    normal = comando.replace("\\", "/")
    if _ENVIO_PREVISTO.search(normal) and not _ENCADENA.search(_sin_heredoc(normal)):
        return Decision(True, "envio_de_texto_libre", auditar=True)
    raiz = comun.raiz_proyectos(Path(entrada.get("cwd") or Path.cwd()))
    minus = normal.lower()
    nombra_raiz = _normalizar(str(raiz)) in minus or f"{raiz.name.lower()}/" in minus
    if _TEXTO_LIBRE.search(normal) or (
        nombra_raiz and any(f"/{p}/" in minus or f"/{p} " in minus for p in PROTEGIDAS)
    ):
        return _deniega(
            "sin_lectura_de_no_confiable",
            "El comando nombra texto no confiable (brief/, cambios/ o texto_libre*.txt). Para "
            "enviar el texto libre usa `msm.py brief`, que no lo muestra.",
        )
    if nombra_raiz and ".sqlite" in minus:
        return _deniega(
            "sin_escritura_en_proyectos",
            "La base del proyecto solo se toca por la API o el MCP (architecture.md §8).",
        )
    return PASA


def decidir(entrada: dict[str, Any]) -> Decision:
    herramienta = str(entrada.get("tool_name") or "")
    agente = entrada.get("agent_type")
    agente = agente if isinstance(agente, str) and agente else None
    if herramienta.startswith("mcp__"):
        return _mcp(herramienta, agente)
    if herramienta in ESCRIBEN or herramienta in LEEN or herramienta == "Glob":
        return _fichero(entrada, herramienta, agente)
    if herramienta in SHELLS:
        return _shell(entrada)
    return PASA


def _sensible(entrada: dict[str, Any]) -> bool:
    herramienta = str(entrada.get("tool_name") or "")
    return herramienta.startswith(("mcp__escritura__", "mcp__entrada__"))


def _proyecto_de_llamada(entrada: dict[str, Any], decision: Decision) -> str | None:
    if decision.proyecto:
        return decision.proyecto
    candidato = (entrada.get("tool_input") or {}).get("proyecto")
    return (
        candidato
        if isinstance(candidato, str) and re.fullmatch(r"[0-9a-f]{32}", candidato)
        else None
    )


def _auditar(entrada: dict[str, Any], decision: Decision) -> None:
    """P-5: con proyecto conocido, a `POST /proyectos/{id}/auditoria`; si no lo hay o el
    backend no responde, a `auditoria.jsonl`. Nunca con argumentos ni texto de la llamada."""
    texto_decision = "permitida" if decision.permitir else "denegada"
    proyecto = _proyecto_de_llamada(entrada, decision)
    if proyecto is not None:
        try:
            comun.peticion(
                "POST",
                f"/proyectos/{proyecto}/auditoria",
                {
                    "decision": texto_decision,
                    "herramienta": entrada.get("tool_name"),
                    "agente": entrada.get("agent_type"),
                    "motivo": decision.motivo or decision.regla,
                },
                espera=2.0,
            )
            return
        except (comun.ErrorBackend, comun.SinBackend, OSError):
            pass
    comun.anotar(
        "auditoria.jsonl",
        {
            "origen": "policy",
            "decision": texto_decision,
            "regla": decision.regla,
            "herramienta": entrada.get("tool_name"),
            "agent_type": entrada.get("agent_type"),
            "agent_id": entrada.get("agent_id"),
            "proyecto": proyecto,
            "sesion": entrada.get("session_id"),
        },
    )


def main() -> int:
    entrada: dict[str, Any] = {}
    try:
        entrada = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
        decision = decidir(entrada)
    except Exception as error:  # noqa: BLE001 — un fallo de la policy no puede dejar pasar la escritura
        if not _sensible(entrada):
            return 0
        decision = _deniega("error_en_policy", f"La policy falló ({type(error).__name__}).")
    if decision.auditar:
        try:
            _auditar(entrada, decision)
        except OSError:
            pass
    if not decision.permitir:
        sys.stdout.write(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": decision.motivo,
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
