"""El modelo de error de la API (spec1.md §5.1, TC-11): `{codigo, requisito, detalle}`.

Traduce al mismo cuerpo las excepciones del núcleo (`ErrorProyecto`) y las de FastAPI, con
el estado HTTP de cada código de `CodigoError`. Tres cosas que un 422 genérico confundiría
quedan separadas: una transición inválida (409, RF-04), un bloqueo ajeno (423, RF-09b) y
un error de validación de entrada (422).

Un intento fallido de un agente **no** es un error: `POST /resultado` responde 200 con el
desenlace `rechazada` (RF-77a). Un contexto con hallazgos tampoco: `POST /contexto/validar`
devuelve el informe con 200.

El detalle de un error de validación lleva la ruta del campo y el mensaje, nunca el valor
recibido: puede ser un dato excluido (RF-13).
"""

from collections.abc import Callable, Coroutine, Sequence
from typing import Any

from fastapi import Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.proyecto.errores import CodigoError, ErrorProyecto, NoEncontrado

ESTADO_HTTP: dict[CodigoError, int] = {
    CodigoError.PROYECTO_INEXISTENTE: 404,
    CodigoError.NO_ENCONTRADO: 404,
    CodigoError.TRANSICION_INVALIDA: 409,
    CodigoError.ORDEN_AJENA: 409,
    CodigoError.DECISION_HUMANA_INVALIDA: 409,
    CodigoError.BLOQUEO_AJENO: 423,
    # Falta la cabecera del token, nadie ha tomado el bloqueo o caducó: hay que tomarlo antes.
    CodigoError.BLOQUEO_REQUERIDO: 428,
    CodigoError.VALIDACION: 422,
    # Q8: el agente aún no tiene esquema de salida; llega en un paso posterior del plan.
    CodigoError.AGENTE_SIN_ESQUEMA: 501,
    # RF-14: solo se da por `/mcp/entrada`, nunca por REST. Si una ruta lo diera, 404 para
    # todos los casos por igual: no distingue un identificador usado de uno inexistente.
    CodigoError.ENTRADA_NO_CANJEABLE: 404,
    # RF-09a: otra petición tiene abierta la base; el borrado no ha empezado.
    CodigoError.PROYECTO_EN_USO: 409,
}


class ErrorApi(BaseModel):
    """El cuerpo de toda respuesta de error. `requisito` es `None` en los errores de entrada."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    codigo: CodigoError
    requisito: str | None
    detalle: str


def respuesta_de_error(codigo: CodigoError, requisito: str | None, detalle: str) -> JSONResponse:
    cuerpo = ErrorApi(codigo=codigo, requisito=requisito, detalle=detalle)
    return JSONResponse(cuerpo.model_dump(mode="json"), status_code=ESTADO_HTTP[codigo])


def documentar(*codigos: CodigoError) -> dict[int | str, dict[str, Any]]:
    """Las respuestas de error de una ruta para OpenAPI, agrupadas por estado HTTP."""
    por_estado: dict[int, list[str]] = {}
    for codigo in codigos:
        por_estado.setdefault(ESTADO_HTTP[codigo], []).append(codigo.value)
    return {
        estado: {"model": ErrorApi, "description": " · ".join(nombres)}
        for estado, nombres in sorted(por_estado.items())
    }


async def _de_error_proyecto(peticion: Request, error: Exception) -> Response:
    if not isinstance(error, ErrorProyecto):
        raise error
    return respuesta_de_error(error.codigo, error.requisito, str(error))


def _sin_valores(errores: Sequence[Any]) -> str:
    """Ruta y mensaje de cada error de validación, sin el valor recibido. Un cuerpo que no
    es JSON (estricto) añade el motivo del analizador, que nunca repite el texto recibido."""
    partes = []
    for e in errores:
        ruta = ".".join(str(parte) for parte in e.get("loc", ())) or "(raíz)"
        mensaje = str(e.get("msg", ""))
        motivo = (e.get("ctx") or {}).get("error") if e.get("type") == "json_invalid" else None
        partes.append(f"{ruta}: {mensaje}" + (f" ({motivo})" if motivo else ""))
    return "; ".join(partes)


async def _de_validacion(peticion: Request, error: Exception) -> Response:
    if not isinstance(error, RequestValidationError):
        raise error
    return respuesta_de_error(CodigoError.VALIDACION, None, _sin_valores(error.errors()))


async def _de_http(peticion: Request, error: Exception) -> Response:
    """Una ruta que no existe da el mismo cuerpo que el resto; los demás errores del
    enrutado (405) siguen con la respuesta por defecto de FastAPI."""
    if not isinstance(error, StarletteHTTPException):
        raise error
    if error.status_code == 404:
        ausente = NoEncontrado(f"no existe la ruta {peticion.method} {peticion.url.path}")
        return respuesta_de_error(ausente.codigo, ausente.requisito, str(ausente))
    return await http_exception_handler(peticion, error)


Manejador = Callable[[Request, Exception], Coroutine[Any, Any, Response]]

MANEJADORES_DE_ERROR: dict[int | type[Exception], Manejador] = {
    ErrorProyecto: _de_error_proyecto,
    RequestValidationError: _de_validacion,
    StarletteHTTPException: _de_http,
}
