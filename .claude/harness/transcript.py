"""Lectura del transcript de un subagente (specs/plan-agentes.md, S-6).

El formato no está documentado: esto es lo único que lo lee, y lo que se sabe de él está en
la prueba (`test_transcript.py`). Cada respuesta del modelo ocupa varias líneas `assistant`
con el mismo `message.id`, y la última trae el `usage` final: se cuenta una vez por id.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

CLAVES_TOKENS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


@dataclass(frozen=True)
class Uso:
    modelo: str | None
    mensajes: int
    tokens: dict[str, int] = field(default_factory=dict)
    duracion_ms: int | None = None

    def como_dict(self) -> dict[str, Any]:
        return {
            "modelo": self.modelo,
            "mensajes": self.mensajes,
            "tokens": self.tokens,
            "duracion_ms": self.duracion_ms,
        }


def _lineas(ruta: Path) -> Iterator[dict[str, Any]]:
    with ruta.open(encoding="utf-8") as entrada:
        for linea in entrada:
            try:
                datos = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if isinstance(datos, dict):
                yield datos


def _texto(contenido: Any) -> str:
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, list):
        return "\n".join(
            b.get("text", "") for b in contenido if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def primer_mensaje_de_usuario(ruta: Path) -> str | None:
    """El prompt con el que se lanzó el subagente: la primera línea `user` con texto."""
    for datos in _lineas(ruta):
        if datos.get("type") == "user":
            mensaje = datos.get("message")
            if isinstance(mensaje, dict):
                texto = _texto(mensaje.get("content"))
                if texto.strip():
                    return texto
    return None


def _instante(valor: Any) -> datetime | None:
    if not isinstance(valor, str):
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None


def uso(ruta: Path) -> Uso:
    por_mensaje: dict[str, dict[str, Any]] = {}
    instantes: list[datetime] = []
    for datos in _lineas(ruta):
        instante = _instante(datos.get("timestamp"))
        if instante is not None:
            instantes.append(instante)
        mensaje = datos.get("message")
        if datos.get("type") != "assistant" or not isinstance(mensaje, dict):
            continue
        identificador, consumo = mensaje.get("id"), mensaje.get("usage")
        if not isinstance(identificador, str) or not isinstance(consumo, dict):
            continue
        por_mensaje[identificador] = consumo  # la última línea del mensaje manda
    tokens = {
        clave: sum(int(c.get(clave) or 0) for c in por_mensaje.values()) for clave in CLAVES_TOKENS
    }
    modelo = _modelo_mayoritario(ruta)
    duracion = None
    if len(instantes) >= 2:
        duracion = int((max(instantes) - min(instantes)).total_seconds() * 1000)
    return Uso(modelo, len(por_mensaje), tokens, duracion)


def _modelo_mayoritario(ruta: Path) -> str | None:
    cuenta: dict[str, set[str]] = {}
    for datos in _lineas(ruta):
        mensaje = datos.get("message")
        if datos.get("type") == "assistant" and isinstance(mensaje, dict):
            modelo, identificador = mensaje.get("model"), mensaje.get("id")
            if isinstance(modelo, str) and isinstance(identificador, str):
                cuenta.setdefault(modelo, set()).add(identificador)
    if not cuenta:
        return None
    return max(cuenta, key=lambda m: (len(cuenta[m]), m))
