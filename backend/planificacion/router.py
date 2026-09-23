"""Rutas de `planificacion` (spec1.md §5.1): el plan completo para la aprobación.

Solo lectura. El plan entra como resultado de la orden del planificador
(`POST /proyectos/{id}/resultado`): no hay `PUT`, una sola vía por cosa. La decisión del
comprador en `aprobacion_plan` (RF-36) va por la ruta de decisiones de `proyecto/`.
"""

from fastapi import APIRouter

from backend.planificacion.consultas import leer_planificacion
from backend.planificacion.modelos import SalidaPlanificador
from backend.proyecto.dependencias import ProyectoAbierto, RutaJsonEstricto
from backend.proyecto.errores import CodigoError, NoEncontrado
from backend.proyecto.errores_http import documentar

router = APIRouter(
    prefix="/proyectos/{id}",
    tags=["planificacion"],
    responses=documentar(CodigoError.PROYECTO_INEXISTENTE, CodigoError.NO_ENCONTRADO),
    route_class=RutaJsonEstricto,
)


@router.get("/plan")
def leer_plan(proyecto: ProyectoAbierto) -> SalidaPlanificador:
    """RF-35: plan, personajes, mundo y guía de estilo en una sola lectura. Sin plan todavía,
    `no_encontrado`."""
    salida = leer_planificacion(proyecto.conexion)
    if salida is None:
        raise NoEncontrado("el proyecto aún no tiene plan: lo escribe el planificador")
    return salida
