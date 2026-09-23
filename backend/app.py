"""Raíz de composición (Q9): crea la aplicación, incluye el router de cada carpeta, instala
el modelo de error y monta las superficies MCP con sus lifespans combinados. Sin lógica
propia: la de cada ruta está en su rebanada.

Arranque: `uv run uvicorn backend.app:app`. La raíz de proyectos la fija `MSM_PROYECTOS`.

Las superficies MCP (`/mcp/lectura`, `/mcp/escritura`, `/mcp/entrada`, architecture.md §7
y §8) se añaden a `SUPERFICIES` como (ruta, fábrica de la aplicación ASGI). Starlette no
arranca el lifespan de una subaplicación montada, así que el de cada una se combina con el
de la aplicación. Van como fábricas y no como aplicaciones hechas porque el gestor de
sesiones de una superficie solo arranca una vez: cada `crear_app()` —las pruebas crean
una por caso— necesita las suyas.

Hoy está montada `/mcp/entrada` (E-6, RF-14): su URL es `/mcp/entrada/`, con la barra final.
"""

from collections.abc import Callable, Sequence

from fastapi import APIRouter, FastAPI
from fastmcp.utilities.lifespan import combine_lifespans
from starlette.applications import Starlette

from backend.contexto.router import router as router_contexto
from backend.intake.router import router as router_intake
from backend.mcp import entrada as mcp_entrada
from backend.proyecto.errores_http import MANEJADORES_DE_ERROR
from backend.proyecto.router import router as router_proyecto

ROUTERS: tuple[APIRouter, ...] = (router_proyecto, router_intake, router_contexto)

Superficie = tuple[str, Callable[[], Starlette]]

SUPERFICIES: tuple[Superficie, ...] = ((mcp_entrada.RUTA, mcp_entrada.superficie),)


def crear_app(superficies: Sequence[Superficie] = SUPERFICIES) -> FastAPI:
    """La aplicación entera. `superficies` solo cambia en las pruebas, para montar las
    mismas superficies con su reloj y su raíz de proyectos."""
    montajes = [(ruta, fabrica()) for ruta, fabrica in superficies]
    app = FastAPI(
        title="my-story-marker",
        summary="Backend del generador de novelas de aventura personalizadas.",
        lifespan=combine_lifespans(*(sub.router.lifespan_context for _, sub in montajes)),
        exception_handlers=MANEJADORES_DE_ERROR,
    )
    for router in ROUTERS:
        app.include_router(router)
    for ruta, sub in montajes:
        app.mount(ruta, sub)
    return app


app = crear_app()
