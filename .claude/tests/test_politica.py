"""V-13, parte T: el hook de policy (specs/plan-agentes.md §5.3)."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import politica
import pytest
from apoyo import PROYECTO


def llamada(herramienta: str, agente: str | None = None, **entrada: Any) -> dict[str, Any]:
    datos: dict[str, Any] = {
        "hook_event_name": "PreToolUse",
        "tool_name": herramienta,
        "tool_input": entrada,
        "cwd": str(Path.cwd()),
        "session_id": "s",
    }
    if agente is not None:
        datos["agent_type"] = agente
        datos["agent_id"] = "a1"
    return datos


def raiz() -> Path:
    import comun

    return comun.raiz_proyectos()


def del_proyecto(grupo: str = "novelas") -> Path:
    """La carpeta del proyecto de prueba: `<raíz>/<grupo>/<proyecto>`."""
    return raiz() / grupo / PROYECTO


# Las dos disposiciones con grupo y la de antes, sin él: la policy protege las tres.
DISPOSICIONES = [("novelas",), ("evals",), ()]


def ejecutar(entrada: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> dict[str, Any] | None:
    """El hook de punta a punta: stdin JSON → stdout, como lo lanza Claude Code."""
    crudo = io.BytesIO(json.dumps(entrada).encode("utf-8"))
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(crudo, encoding="utf-8"))
    salida = io.StringIO()
    monkeypatch.setattr(sys, "stdout", salida)
    assert politica.main() == 0
    texto = salida.getvalue()
    return json.loads(texto) if texto else None


def auditoria(estado: Path) -> list[dict[str, Any]]:
    ruta = estado / "auditoria.jsonl"
    if not ruta.exists():
        return []
    return [json.loads(linea) for linea in ruta.read_text(encoding="utf-8").splitlines()]


# ─── Escritura en la biblia (RF-102) ─────────────────────────────────────────


@pytest.mark.parametrize("agente", [None, "escritor", "revisor", "juez-capitulo", "Bibliotecario"])
def test_la_escritura_se_deniega_a_quien_no_es_el_bibliotecario(
    agente: str | None, monkeypatch: pytest.MonkeyPatch, estado_temporal: Path
) -> None:
    salida = ejecutar(llamada("mcp__escritura__registrar_resumen", agente), monkeypatch)
    assert salida is not None
    assert salida["hookSpecificOutput"]["permissionDecision"] == "deny"
    [registro] = auditoria(estado_temporal)
    assert registro["decision"] == "denegada"
    assert registro["regla"] == "escritura_solo_bibliotecario"
    assert registro["agent_type"] == agente


def test_la_escritura_del_bibliotecario_pasa_y_queda_auditada(
    monkeypatch: pytest.MonkeyPatch, estado_temporal: Path
) -> None:
    assert (
        ejecutar(llamada("mcp__escritura__registrar_resumen", "bibliotecario"), monkeypatch) is None
    )
    [registro] = auditoria(estado_temporal)
    assert registro["decision"] == "permitida"


# ─── Entrada no confiable (RF-14) ────────────────────────────────────────────


@pytest.mark.parametrize("agente", ["extractor-hechos", "interprete-cambios"])
def test_la_entrada_pasa_a_sus_dos_lectores(agente: str) -> None:
    assert politica.decidir(llamada("mcp__entrada__canjear", agente)).permitir


@pytest.mark.parametrize("agente", [None, "agente-contexto", "bibliotecario"])
def test_la_entrada_se_deniega_al_resto(agente: str | None) -> None:
    decision = politica.decidir(llamada("mcp__entrada__canjear", agente))
    assert not decision.permitir
    assert decision.auditar


def test_la_lectura_de_la_biblia_no_la_toca_la_policy() -> None:
    decision = politica.decidir(llamada("mcp__lectura__ficha_capitulo", "escritor"))
    assert decision.permitir and not decision.auditar


# ─── Ficheros del proyecto ───────────────────────────────────────────────────


@pytest.mark.parametrize("grupo", DISPOSICIONES)
@pytest.mark.parametrize("herramienta", ["Write", "Edit", "MultiEdit"])
def test_no_se_escribe_bajo_la_raiz_de_proyectos(herramienta: str, grupo: tuple[str, ...]) -> None:
    ruta = raiz().joinpath(*grupo, PROYECTO, "capitulos", "cap-01", "v1-intento1.md")
    decision = politica.decidir(llamada(herramienta, None, file_path=str(ruta)))
    assert not decision.permitir
    assert decision.proyecto == PROYECTO


def test_fuera_de_la_raiz_se_escribe_normal() -> None:
    decision = politica.decidir(llamada("Write", None, file_path=str(Path.cwd() / "notas.md")))
    assert decision.permitir and not decision.auditar


@pytest.mark.parametrize("grupo", DISPOSICIONES)
@pytest.mark.parametrize("carpeta", ["brief", "cambios"])
def test_no_se_lee_el_texto_no_confiable_del_proyecto(carpeta: str, grupo: tuple[str, ...]) -> None:
    for ruta in (
        raiz().joinpath(*grupo, PROYECTO, carpeta, "peticion-7.txt"),
        raiz().joinpath(*grupo, PROYECTO, carpeta),
    ):
        for herramienta, clave in (("Read", "file_path"), ("Grep", "path")):
            decision = politica.decidir(llamada(herramienta, None, **{clave: str(ruta)}))
            assert not decision.permitir, (herramienta, ruta)
            assert decision.regla == "sin_lectura_de_no_confiable"
            assert decision.proyecto == PROYECTO


@pytest.mark.parametrize("grupo", ["novelas", "evals"])
def test_leer_el_resto_del_proyecto_pasa_y_se_audita(grupo: str) -> None:
    ruta = del_proyecto(grupo) / "capitulos" / "cap-01" / "v1-intento1.md"
    decision = politica.decidir(llamada("Read", None, file_path=str(ruta)))
    assert (decision.permitir, decision.regla, decision.proyecto) == (
        True,
        "lectura_en_proyecto",
        PROYECTO,
    )


@pytest.mark.parametrize("nombre", ["texto_libre.txt", "TEXTO_LIBRE_e2.txt"])
def test_no_se_lee_un_texto_libre_este_donde_este(nombre: str, tmp_path: Path) -> None:
    decision = politica.decidir(llamada("Read", None, file_path=str(tmp_path / nombre)))
    assert not decision.permitir
    assert decision.regla == "sin_lectura_de_texto_libre"


@pytest.mark.parametrize("grupo", DISPOSICIONES)
def test_el_escritor_solo_lee_sus_prompts(grupo: tuple[str, ...]) -> None:
    prompt = raiz().joinpath(*grupo, PROYECTO, "prompts", "cap-03", "v1-intento1.prompt.md")
    assert politica.decidir(llamada("Read", "escritor", file_path=str(prompt))).permitir
    capitulo = raiz().joinpath(*grupo, PROYECTO, "capitulos", "cap-02", "v1-intento1.md")
    assert not politica.decidir(llamada("Read", "escritor", file_path=str(capitulo))).permitir
    assert not politica.decidir(
        llamada("Read", "escritor", file_path=str(Path.cwd() / "AGENTS.md"))
    ).permitir


def test_una_ruta_relativa_se_resuelve_desde_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MSM_PROYECTOS", "proyectos")
    entrada = llamada("Read", None, file_path=f"proyectos/evals/{PROYECTO}/brief/texto.txt")
    assert not politica.decidir(entrada).permitir


# ─── Bash y PowerShell ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "comando",
    [
        f"cat proyectos/{PROYECTO}/brief/texto_libre.txt",
        f"cat proyectos/evals/{PROYECTO}/brief/otro.txt",
        f"ls proyectos/novelas/{PROYECTO}/cambios/",
        "type evals\\E2\\texto_libre.txt",
        f"sqlite3 proyectos/{PROYECTO}/proyecto.sqlite 'delete from hecho'",
        f"sqlite3 proyectos/evals/{PROYECTO}/proyecto.sqlite 'delete from hecho'",
    ],
)
def test_la_shell_no_toca_lo_protegido(comando: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MSM_PROYECTOS", "proyectos")
    for herramienta in ("Bash", "PowerShell"):
        assert not politica.decidir(llamada(herramienta, None, command=comando)).permitir


ENVIO = (
    "uv run --project . --no-sync --quiet python .claude/harness/msm.py brief "
    f"{PROYECTO} --respuestas - --texto-libre evals/e2-injection/input/texto_libre.txt"
)


def test_el_envio_previsto_del_texto_libre_pasa() -> None:
    assert politica.decidir(llamada("Bash", None, command=ENVIO)).permitir
    con_heredoc = ENVIO + ' <<\'EOF\'\n{"destinatario": {"nombre": "X"}}\nEOF'
    assert politica.decidir(llamada("Bash", None, command=con_heredoc)).permitir


@pytest.mark.parametrize(
    "cola", ["; cat evals/e2-injection/input/texto_libre.txt", " && type texto_libre.txt", " | tee x"]
)
def test_encadenar_algo_al_envio_no_aprovecha_la_excepcion(cola: str) -> None:
    decision = politica.decidir(llamada("Bash", None, command=ENVIO + cola))
    assert not decision.permitir


@pytest.mark.parametrize(
    "comando", ["uv run pytest backend/intake", "grep -rn texto_libre backend", "ls proyectos"]
)
def test_la_shell_de_las_sesiones_de_desarrollo_pasa(comando: str) -> None:
    assert politica.decidir(llamada("Bash", None, command=comando)).permitir


# ─── Auditoría (P-5) ─────────────────────────────────────────────────────────


def test_con_proyecto_conocido_la_auditoria_va_al_backend(
    monkeypatch: pytest.MonkeyPatch, backend: Any, estado_temporal: Path
) -> None:
    ruta = f"/proyectos/{PROYECTO}/auditoria"
    backend.respuestas[("POST", ruta)] = (201, {"ok": True})
    escribir = del_proyecto("evals") / "export" / "v1" / "x.md"
    ejecutar(llamada("Write", "escritor", file_path=str(escribir)), monkeypatch)
    [peticion] = backend.peticiones
    assert peticion["ruta"] == ruta
    assert peticion["cuerpo"]["decision"] == "denegada"
    assert peticion["cuerpo"]["agente"] == "escritor"
    assert set(peticion["cuerpo"]) == {"decision", "herramienta", "agente", "motivo"}
    assert auditoria(estado_temporal) == []


def test_si_el_backend_no_la_acepta_la_auditoria_queda_en_local(
    monkeypatch: pytest.MonkeyPatch, estado_temporal: Path
) -> None:
    escribir = del_proyecto("evals") / "export" / "v1" / "x.md"
    ejecutar(llamada("Write", None, file_path=str(escribir)), monkeypatch)
    [registro] = auditoria(estado_temporal)
    assert registro["proyecto"] == PROYECTO and registro["decision"] == "denegada"


# ─── Fallo de la propia policy ───────────────────────────────────────────────


def test_un_fallo_de_la_policy_deniega_la_escritura(monkeypatch: pytest.MonkeyPatch) -> None:
    def rompe(_: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(politica, "decidir", rompe)
    salida = ejecutar(llamada("mcp__escritura__x", "bibliotecario"), monkeypatch)
    assert salida is not None and salida["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert ejecutar(llamada("Read", None, file_path="x.md"), monkeypatch) is None
