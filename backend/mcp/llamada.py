"""Ejecución y auditoría de una llamada a `/mcp/lectura` o `/mcp/escritura` (RF-105).

Cada llamada abre el proyecto que la identifica, ejecuta la operación y deja una fila en
`llamada_mcp` —acierte o falle— con la herramienta (`<superficie>.<nombre>`), los
argumentos sin texto libre y el resultado reducido a `ok` y la clase del error. El agente
no viaja en MCP: se infiere de la orden vigente y se marca como inferido (decisiones-backend
§3, punto 10).

Los errores esperados (una referencia que la biblia no conoce, un capítulo sin verificar, un
sello viejo, un rango fuera de límites) llegan al agente como `ToolError` con su mensaje; el
resto, enmascarado por `mask_error_details`. Los argumentos que FastMCP rechaza antes de
llegar a la herramienta también quedan, con `AuditarRechazos` (RF-105).
"""

import json
import sqlite3
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import mcp_types as mt
from fastmcp.exceptions import ToolError
from fastmcp.exceptions import ValidationError as ArgumentosInvalidos
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools import ToolResult

from backend.capitulo.biblia import ErrorBiblia
from backend.proyecto.abierto import Proyecto, abrir_proyecto, instante
from backend.proyecto.errores import ProyectoInexistente
from backend.proyecto.orden import orden_vigente
from backend.shared.db import transaccion
from backend.shared.rutas import IdentificadorInvalido

LIBRES = frozenset({"estado", "datos", "descripcion", "texto", "momento"})
"""Argumentos que el modelo redacta: en la auditoría solo queda su tamaño (RF-105)."""


def sin_texto_libre(argumentos: Mapping[str, Any]) -> dict[str, Any]:
    limpios: dict[str, Any] = {}
    for clave, valor in argumentos.items():
        if clave in LIBRES and isinstance(valor, str):
            limpios[clave] = {"caracteres": len(valor)}
        elif clave in LIBRES and isinstance(valor, list | tuple):
            limpios[clave] = {"elementos": len(valor)}
        else:
            limpios[clave] = valor
    return limpios


def _registrar(
    conexion: sqlite3.Connection,
    momento: str,
    herramienta: str,
    argumentos: Mapping[str, Any],
    error: str | None,
) -> None:
    vigente = orden_vigente(conexion)
    resultado = {"ok": error is None, "error": error, "agente_inferido": True}
    with transaccion(conexion):
        conexion.execute(
            "INSERT INTO llamada_mcp (momento, agente, herramienta, argumentos, resultado) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                momento,
                vigente.agente.value if vigente is not None else None,
                herramienta,
                json.dumps(sin_texto_libre(argumentos), ensure_ascii=False, default=str),
                json.dumps(resultado),
            ),
        )


def ejecutar[T](
    raiz: Path,
    ahora: datetime,
    proyecto: str,
    herramienta: str,
    argumentos: Mapping[str, Any],
    operacion: Callable[[Proyecto], T],
) -> T:
    """Abre el proyecto `proyecto` (su id, o un sello: vale el primer segmento), ejecuta la
    operación y registra la llamada. Sin proyecto no hay dónde registrar: solo el error."""
    try:
        abierto = abrir_proyecto(proyecto.split(":", 1)[0], raiz)
    except (IdentificadorInvalido, ProyectoInexistente):
        raise ToolError("proyecto desconocido: usa el primer segmento del sello") from None
    with abierto:
        momento = instante(ahora)
        try:
            resultado = operacion(abierto)
        except ToolError:
            _registrar(abierto.conexion, momento, herramienta, argumentos, "ToolError")
            raise
        except (ErrorBiblia, ValueError) as error:
            nombre = type(error).__name__
            _registrar(abierto.conexion, momento, herramienta, argumentos, nombre)
            raise ToolError(str(error)) from None
        _registrar(abierto.conexion, momento, herramienta, argumentos, None)
        return resultado


class AuditarRechazos(Middleware):
    """RF-105: una llamada cuyos argumentos no pasan la validación de FastMCP no llega a
    `ejecutar`; aquí queda igualmente en `llamada_mcp`, con el error `ArgumentosInvalidos`.
    El proyecto sale de `proyecto` o del primer segmento de `sello`; sin él, no hay dónde."""

    def __init__(
        self, superficie: str, raiz: Callable[[], Path], reloj: Callable[[], datetime]
    ) -> None:
        self.superficie, self.raiz, self.reloj = superficie, raiz, reloj

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        try:
            return await call_next(context)
        except ArgumentosInvalidos:
            self._auditar(context.message)
            raise

    def _auditar(self, mensaje: mt.CallToolRequestParams) -> None:
        argumentos = dict(mensaje.arguments or {})
        proyecto = argumentos.pop("proyecto", None) or argumentos.pop("sello", None)
        argumentos.pop("sello", None)
        if not isinstance(proyecto, str):
            return
        try:
            abierto = abrir_proyecto(proyecto.split(":", 1)[0], self.raiz())
        except (IdentificadorInvalido, ProyectoInexistente):
            return
        with abierto:
            herramienta = f"{self.superficie}.{mensaje.name}"
            momento = instante(self.reloj())
            _registrar(abierto.conexion, momento, herramienta, argumentos, "ArgumentosInvalidos")
