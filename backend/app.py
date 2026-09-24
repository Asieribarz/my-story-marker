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

Están montadas `/mcp/lectura/` (RF-103), `/mcp/escritura/` (RF-104) y `/mcp/entrada/` (E-6,
RF-14), con la barra final.
"""

from collections.abc import Callable, Sequence

from fastapi import APIRouter, FastAPI
from fastmcp.utilities.lifespan import combine_lifespans
from starlette.applications import Starlette

from backend.cambio.router import router as router_cambio
from backend.cambio.worker import ConfigWorker, activo_por_entorno, lifespan_del_worker
from backend.contexto.router import router as router_contexto
from backend.escaleta.router import router as router_escaleta
from backend.exportacion.router import router as router_exportacion
from backend.intake.router import router as router_intake
from backend.mcp import entrada as mcp_entrada
from backend.mcp import escritura as mcp_escritura
from backend.mcp import lectura as mcp_lectura
from backend.planificacion.router import router as router_planificacion
from backend.proyecto.errores_http import MANEJADORES_DE_ERROR
from backend.proyecto.router import router as router_proyecto
from backend.revision.router import router as router_revision

ROUTERS: tuple[APIRouter, ...] = (
    router_proyecto,
    router_intake,
    router_contexto,
    router_planificacion,
    router_escaleta,
    router_exportacion,
    router_revision,
    router_cambio,
)

Superficie = tuple[str, Callable[[], Starlette]]

SUPERFICIES: tuple[Superficie, ...] = (
    (mcp_lectura.RUTA, mcp_lectura.superficie),
    (mcp_escritura.RUTA, mcp_escritura.superficie),
    (mcp_entrada.RUTA, mcp_entrada.superficie),
)


def crear_app(
    superficies: Sequence[Superficie] = SUPERFICIES, worker: ConfigWorker | None = None
) -> FastAPI:
    """La aplicación entera. `superficies` solo cambia en las pruebas, para montar las
    mismas superficies con su reloj y su raíz de proyectos. Con `worker`, el `lifespan`
    arranca el worker de regeneración (RF-124, TC-9); sin él —las pruebas— no hay hilo."""
    montajes = [(ruta, fabrica()) for ruta, fabrica in superficies]
    lifespans = [sub.router.lifespan_context for _, sub in montajes]
    if worker is not None:
        lifespans.append(lifespan_del_worker(worker))
    app = FastAPI(
        title="my-story-marker",
        summary="Backend del generador de novelas de aventura personalizadas.",
        lifespan=combine_lifespans(*lifespans),
        exception_handlers=MANEJADORES_DE_ERROR,
    )
    for router in ROUTERS:
        app.include_router(router)
    for ruta, sub in montajes:
        app.mount(ruta, sub)
    return app


# `uvicorn backend.app:app` arranca con el worker salvo con `MSM_WORKER=0`.
app = crear_app(worker=ConfigWorker() if activo_por_entorno() else None)
