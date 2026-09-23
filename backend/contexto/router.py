"""Rutas de `contexto` (spec1.md §5.1): validar un objeto de contexto sin guardarlo.

No hay ruta para guardar el contexto: entra solo como resultado de la orden del Agente de
Contexto (`POST /proyectos/{id}/resultado`), que es donde el grafo decide si sale de
`contexto` (RF-22, V-20). Una sola vía por cosa.
"""

from datetime import UTC
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel

from backend.contexto.validacion import validar
from backend.proyecto.dependencias import Ahora, RutaJsonEstricto, proyecto_abierto
from backend.proyecto.errores import CodigoError
from backend.proyecto.errores_http import documentar
from backend.shared.tipos import Hallazgo

router = APIRouter(
    prefix="/proyectos/{id}/contexto",
    tags=["contexto"],
    responses=documentar(CodigoError.PROYECTO_INEXISTENTE, CodigoError.VALIDACION),
    route_class=RutaJsonEstricto,
)


class InformeValidacion(BaseModel):
    """RF-21, RF-26: los hallazgos con la ruta de la clave, lo recibido y lo esperado, y los
    valores por defecto que se rellenaron. `valido` es la guarda de RF-22."""

    valido: bool
    version_ontologia: str
    hallazgos: list[Hallazgo]
    rellenados: list[str]


@router.post("/validar", dependencies=[Depends(proyecto_abierto)])
def validar_sin_guardar(ahora: Ahora, datos: Annotated[Any, Body()]) -> InformeValidacion:
    """RF-21: valida el objeto de contexto contra la ontología con el `hoy` del reloj.

    Un contexto con hallazgos no es un error de la petición: responde 200 con el informe
    (TC-11). No escribe nada ni mueve el proyecto.
    """
    informe = validar(datos, ahora.astimezone(UTC).date())
    return InformeValidacion(
        valido=informe.valido,
        version_ontologia=informe.version_ontologia,
        hallazgos=list(informe.hallazgos),
        rellenados=list(informe.rellenados),
    )
