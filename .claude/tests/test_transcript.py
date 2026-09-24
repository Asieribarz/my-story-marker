"""El lector de uso del transcript (S-6), sobre un fichero sintético con la forma observada:
cada respuesta en varias líneas con el mismo `message.id`, y el `usage` final en la última."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import transcript


def escribir(ruta: Path, lineas: list[dict[str, Any]]) -> Path:
    ruta.write_text("\n".join(json.dumps(x) for x in lineas) + "\n", encoding="utf-8")
    return ruta


def asistente(
    ident: str, salida: int, entrada: int = 10, cache: int = 0, **extra: Any
) -> dict[str, Any]:
    return {
        "type": "assistant",
        "timestamp": extra.pop("timestamp", None),
        "message": {
            "id": ident,
            "model": extra.pop("model", "claude-haiku-4-5"),
            "usage": {
                "input_tokens": entrada,
                "output_tokens": salida,
                "cache_creation_input_tokens": cache,
                "cache_read_input_tokens": 0,
            },
        },
    }


def test_cada_mensaje_cuenta_una_vez_con_su_ultima_linea(tmp_path: Path) -> None:
    ruta = escribir(
        tmp_path / "t.jsonl",
        [
            {
                "type": "user",
                "timestamp": "2026-09-23T10:00:00Z",
                "message": {"content": "orden: x"},
            },
            asistente("m1", 1, cache=6000),
            asistente("m1", 299, cache=6000),
            {"type": "attachment", "attachment": {}},
            asistente("m2", 88, entrada=8, cache=1112, timestamp="2026-09-23T10:00:05Z"),
            asistente("m2", 88, entrada=8, cache=1112),
        ],
    )
    uso = transcript.uso(ruta)
    assert uso.mensajes == 2
    assert uso.tokens == {
        "input_tokens": 18,
        "output_tokens": 387,
        "cache_creation_input_tokens": 7112,
        "cache_read_input_tokens": 0,
    }
    assert uso.modelo == "claude-haiku-4-5"
    assert uso.duracion_ms == 5000


def test_lineas_rotas_o_sin_uso_no_cuentan(tmp_path: Path) -> None:
    ruta = tmp_path / "t.jsonl"
    ruta.write_text('no es json\n{"type": "assistant", "message": {"id": "m"}}\n', encoding="utf-8")
    assert transcript.uso(ruta).mensajes == 0


def test_el_primer_mensaje_de_usuario_admite_texto_o_bloques(tmp_path: Path) -> None:
    bloques = {"type": "user", "message": {"content": [{"type": "text", "text": "orden: a:1"}]}}
    ruta = escribir(tmp_path / "t.jsonl", [{"type": "attachment"}, bloques])
    assert transcript.primer_mensaje_de_usuario(ruta) == "orden: a:1"


def llamada(nombre: str, entrada: dict[str, Any]) -> dict[str, Any]:
    bloque = {"type": "tool_use", "name": nombre, "input": entrada}
    return {"type": "assistant", "message": {"id": "m", "content": [bloque]}}


def test_los_textos_del_asistente_incluyen_textos_y_entregas_en_orden(tmp_path: Path) -> None:
    texto = {
        "type": "assistant",
        "message": {"id": "t", "content": [{"type": "text", "text": "a"}]},
    }
    ruta = escribir(
        tmp_path / "t.jsonl",
        [
            {"type": "user", "message": {"content": "orden: x"}},
            llamada("mcp__entrada__leer_entrada", {"message": "no cuenta"}),
            texto,
            llamada("SubagentHandback", {"message": "b"}),
            {"type": "assistant", "message": {"id": "n", "content": "c"}},
        ],
    )
    assert transcript.textos_del_asistente(ruta) == ["a", "b", "c"]
