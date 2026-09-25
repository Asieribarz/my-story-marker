"""V-13, parte A: análisis estático de las definiciones de agente, `.mcp.json` y los hooks
(specs/plan-agentes.md §5 y §7). PyYAML llega como dependencia transitiva del entorno."""

from __future__ import annotations

import json
import re
import sys
from typing import Any

import pytest

yaml = pytest.importorskip("yaml")

import comun  # noqa: E402

RAIZ = comun.RAIZ_REPO
AGENTES = RAIZ / ".claude" / "agents"

MODELOS = {
    "agente-contexto": "sonnet",
    "extractor-hechos": "haiku",
    "planificador": "sonnet",
    "escaletista": "sonnet",
    "escritor": "opus",
    "editor-estilo": "sonnet",
    "juez-capitulo": "sonnet",
    "bibliotecario": "sonnet",
    "juez-manuscrito": "sonnet",
    "revisor": "opus",
    "exportador": "haiku",
    "interprete-cambios": "haiku",
}
PROHIBIDAS = {
    "Bash",
    "PowerShell",
    "Write",
    "Edit",
    "MultiEdit",
    "NotebookEdit",
    "Agent",
    "Task",
    "WebFetch",
    "WebSearch",
}
ENTRADA = {"extractor-hechos", "interprete-cambios"}


def definicion(nombre: str) -> tuple[dict[str, Any], str]:
    texto = (AGENTES / f"{nombre}.md").read_text(encoding="utf-8")
    _, cabecera, cuerpo = texto.split("---", 2)
    return yaml.safe_load(cabecera), cuerpo


def herramientas(frontmatter: dict[str, Any]) -> list[str]:
    valor = frontmatter.get("tools")
    if isinstance(valor, list):
        return [str(x).strip() for x in valor]
    return [x.strip() for x in str(valor or "").split(",") if x.strip()]


def servidores(frontmatter: dict[str, Any]) -> set[str]:
    valor = frontmatter.get("mcpServers") or []
    nombres: set[str] = set()
    for entrada in valor if isinstance(valor, list) else [valor]:
        if isinstance(entrada, dict):
            nombres.update(entrada)
        else:
            nombres.add(str(entrada))
    return nombres


def test_hay_exactamente_un_fichero_por_agente() -> None:
    assert {p.stem for p in AGENTES.glob("*.md")} == set(MODELOS) == set(comun.AGENTES)


def test_los_nombres_son_los_del_backend() -> None:
    sys.path.insert(0, str(RAIZ))
    from backend.shared.tipos import Agente

    del_backend = {a.value for a in Agente}
    if {"arquitecto", "personajes", "mundo", "estilo"} & del_backend:
        pytest.skip("el backend aún no ha aplicado R-1 (spec-backend-2.md §0)")
    assert del_backend == set(MODELOS)


def test_los_grupos_de_proyecto_son_los_del_backend() -> None:
    """La policy protege `<raíz>/<grupo>/<proyecto>/`: si el backend añade un grupo que el
    harness no conoce, sus rutas se leerían con el nivel equivocado."""
    sys.path.insert(0, str(RAIZ))
    from backend.shared.rutas import GrupoProyecto

    assert tuple(g.value for g in GrupoProyecto) == comun.GRUPOS


@pytest.mark.parametrize("nombre", sorted(MODELOS))
def test_cada_definicion_tiene_nombre_modelo_herramientas_y_formato(nombre: str) -> None:
    frontmatter, cuerpo = definicion(nombre)
    assert frontmatter["name"] == nombre
    assert frontmatter["model"] == MODELOS[nombre]
    lista = herramientas(frontmatter)
    assert lista, (
        "sin lista `tools` hereda los conectores de la cuenta (S-4) y vacía no arranca (S-3)"
    )
    assert not PROHIBIDAS & set(lista)
    assert "## Formato de salida" in cuerpo
    assert "orden:" in cuerpo


def test_solo_el_bibliotecario_declara_la_escritura() -> None:
    for nombre in MODELOS:
        frontmatter, _ = definicion(nombre)
        declara = "escritura" in servidores(frontmatter) or "mcp__escritura" in herramientas(
            frontmatter
        )
        assert declara == (nombre == "bibliotecario"), nombre


def test_solo_extractor_e_interprete_declaran_la_entrada_y_nada_mas() -> None:
    for nombre in MODELOS:
        frontmatter, _ = definicion(nombre)
        if nombre in ENTRADA:
            assert servidores(frontmatter) == {"entrada"}
            assert herramientas(frontmatter) == ["mcp__entrada"]
        else:
            assert "entrada" not in servidores(frontmatter)
            assert "mcp__entrada" not in herramientas(frontmatter)


def test_el_escritor_no_declara_mcp() -> None:
    frontmatter, _ = definicion("escritor")
    assert not servidores(frontmatter)
    assert not [h for h in herramientas(frontmatter) if h.startswith("mcp__")]


def test_las_superficies_propias_apuntan_al_backend_local() -> None:
    for nombre in (*ENTRADA, "bibliotecario"):
        frontmatter, _ = definicion(nombre)
        for entrada in frontmatter["mcpServers"]:
            for servidor, config in entrada.items():
                assert config["type"] == "http"
                assert re.fullmatch(rf"http://127\.0\.0\.1:8000/mcp/{servidor}/", config["url"])


def test_mcp_json_no_trae_escritura_ni_entrada() -> None:
    datos = json.loads((RAIZ / ".mcp.json").read_text(encoding="utf-8"))
    assert not {"escritura", "entrada"} & set(datos["mcpServers"])


def test_settings_engancha_los_dos_hooks_y_apaga_el_plugin() -> None:
    datos = json.loads((RAIZ / ".claude" / "settings.json").read_text(encoding="utf-8"))
    pre = datos["hooks"]["PreToolUse"][0]
    assert "politica.py" in pre["hooks"][0]["command"]
    assert "mcp__" in pre["matcher"] and "Read" in pre["matcher"] and "Bash" in pre["matcher"]
    assert "subagente.py" in datos["hooks"]["SubagentStop"][0]["hooks"][0]["command"]
    assert datos["enabledPlugins"]["langfuse-observability@langfuse-observability"] is False
