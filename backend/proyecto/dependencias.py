"""Dependencias comunes de los routers: reloj, raíz de proyectos, proyecto abierto y token.

- **Reloj.** Es el único sitio de la API que lee la hora; la lógica la recibe como `ahora`
  y las pruebas lo sustituyen con `app.dependency_overrides`.
- **Raíz de proyectos.** La fija `MSM_PROYECTOS` (`shared/rutas.py`); las pruebas la
  sustituyen por `tmp_path`.
- **Proyecto abierto.** Cada petición abre su propia conexión con `shared.db.conectar` y la
  cierra al acabar: nada vive en memoria entre peticiones (RF-02). Un identificador mal
  formado o sin proyecto da `ProyectoInexistente` (404). Por eso los endpoints son `def` y
  no `async def`: `sqlite3` bloquea y FastAPI los ejecuta en su threadpool.
- **Token del bloqueo.** Viaja en la cabecera `X-Bloqueo` (RF-09b, Q7). Sin ella, pedir la
  siguiente orden o registrar un resultado da `BloqueoRequerido`.
- **Cuerpo en JSON estricto.** Los routers usan `RutaJsonEstricto`: un cuerpo con `NaN`,
  `Infinity` o un sustituto suelto es un error de validación (422), no un error interno al
  escribirlo en la base. `/resultado` es la excepción declarada: lo que el agente devolvió
  fuera de JSON estricto es un intento fallido, y eso lo decide el núcleo (RF-77a).
"""

from collections.abc import Callable, Coroutine, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, Header, Request, Response
from fastapi.routing import APIRoute

from backend.proyecto import json_estricto
from backend.proyecto.abierto import Proyecto, abrir_proyecto
from backend.proyecto.errores import BloqueoRequerido, ProyectoInexistente
from backend.shared.rutas import IdentificadorInvalido, raiz_de_proyectos

CABECERA_BLOQUEO = "X-Bloqueo"


class _PeticionJsonEstricto(Request):
    async def json(self) -> Any:
        if not hasattr(self, "_json"):
            self._json = json_estricto.cargar(await self.body())
        return self._json


class RutaJsonEstricto(APIRoute):
    """La ruta de FastAPI con el cuerpo leído por `json_estricto.cargar`. Lo que no es JSON
    estricto da `json.JSONDecodeError`, y FastAPI lo convierte en el mismo 422 que un JSON
    mal formado."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def manejar(peticion: Request) -> Response:
            return await original(_PeticionJsonEstricto(peticion.scope, peticion.receive))

        return manejar


def reloj() -> datetime:
    return datetime.now(UTC)


def raiz_proyectos() -> Path:
    return raiz_de_proyectos()


def proyecto_abierto(id: str, raiz: Annotated[Path, Depends(raiz_proyectos)]) -> Iterator[Proyecto]:
    try:
        proyecto = abrir_proyecto(id, raiz)
    except IdentificadorInvalido:
        raise ProyectoInexistente(id) from None
    try:
        yield proyecto
    finally:
        proyecto.cerrar()


CabeceraBloqueo = Annotated[str | None, Header(alias=CABECERA_BLOQUEO)]


def token_bloqueo(cabecera: CabeceraBloqueo = None) -> str:
    if not cabecera:
        raise BloqueoRequerido(
            f"falta la cabecera {CABECERA_BLOQUEO} con el token que devolvió "
            "POST /proyectos/{id}/bloqueo"
        )
    return cabecera


Ahora = Annotated[datetime, Depends(reloj)]
Raiz = Annotated[Path, Depends(raiz_proyectos)]
ProyectoAbierto = Annotated[Proyecto, Depends(proyecto_abierto)]
Token = Annotated[str, Depends(token_bloqueo)]
