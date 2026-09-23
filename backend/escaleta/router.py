"""Rutas de `escaleta` (spec1.md §5.1): las fichas de capítulo.

Solo lectura. La escaleta entra como resultado de la orden del escaletista
(`POST /proyectos/{id}/resultado`), que es donde se valida (RF-41 a RF-43): no hay `PUT`.
"""

from fastapi import APIRouter

from backend.escaleta.consultas import leer_escaleta
from backend.escaleta.modelos import SalidaEscaletista
from backend.proyecto.dependencias import ProyectoAbierto, RutaJsonEstricto
from backend.proyecto.errores import CodigoError, NoEncontrado
from backend.proyecto.errores_http import documentar

router = APIRouter(
    prefix="/proyectos/{id}",
    tags=["escaleta"],
    responses=documentar(CodigoError.PROYECTO_INEXISTENTE, CodigoError.NO_ENCONTRADO),
    route_class=RutaJsonEstricto,
)


@router.get("/escaleta")
def leer_fichas(proyecto: ProyectoAbierto) -> SalidaEscaletista:
    """RF-40: las fichas de capítulo en orden, tal como entraron. Sin escaleta todavía,
    `no_encontrado`."""
    fichas = leer_escaleta(proyecto.conexion)
    if not fichas:
        raise NoEncontrado("el proyecto aún no tiene escaleta: la escribe el escaletista")
    return SalidaEscaletista(fichas=fichas)
