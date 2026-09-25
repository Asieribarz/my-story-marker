"""Rutas de `revision`: la revisión humana del manuscrito (RF-114, spec-backend-2 §3.5).

`POST /proyectos/{id}/manuscrito/juez` queda solo para la revisión humana: el juez de
manuscrito registra por `/resultado`. Una revisión humana usa la misma rúbrica y el mismo
formato que el juez, se asocia a la versión de novela en curso para compararlas, y **no
cambia el estado del proyecto** ni los gates. `GET` devuelve juez y revisiones juntos.
"""

from typing import Annotated

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from backend.proyecto.abierto import instante
from backend.proyecto.dependencias import Ahora, ProyectoAbierto, RutaJsonEstricto
from backend.proyecto.errores import CodigoError
from backend.proyecto.errores_http import documentar
from backend.revision.consultas import evaluaciones, siguiente_evaluacion_humana
from backend.shared.db import transaccion
from backend.verificacion.consultas import guardar_evaluacion, proyecto_en_curso
from backend.verificacion.modelos import Rubrica

router = APIRouter(
    prefix="/proyectos/{id}",
    tags=["revision"],
    responses=documentar(CodigoError.PROYECTO_INEXISTENTE),
    route_class=RutaJsonEstricto,
)


class RevisionHumana(Rubrica):
    """RF-114: la rúbrica, y la versión de novela si no es la que está en curso."""

    version_novela: Annotated[StrictInt, Field(ge=1)] | None = None


class Evaluacion(BaseModel):
    model_config = ConfigDict(frozen=True)

    evaluacion: str
    revisor: str
    version_novela: int
    ciclo: int
    puntuaciones: dict[str, int]
    justificaciones: dict[str, str]
    suma: int
    aprobaria: bool
    momento: str


@router.post("/manuscrito/juez", status_code=status.HTTP_201_CREATED)
def registrar_revision_humana(
    cuerpo: RevisionHumana, proyecto: ProyectoAbierto, ahora: Ahora
) -> Evaluacion:
    """RF-114: guarda la revisión humana; `aprobaria` es el umbral de TC-5 aplicado a ella,
    solo para comparar."""
    conexion = proyecto.conexion
    with transaccion(conexion):
        _, ciclo, en_curso = proyecto_en_curso(conexion)
        version = cuerpo.version_novela or en_curso
        nombre = siguiente_evaluacion_humana(conexion)
        guardar_evaluacion(conexion, nombre, "humano", version, ciclo, cuerpo, instante(ahora))
    guardada = next(e for e in evaluaciones(conexion) if e["evaluacion"] == nombre)
    return Evaluacion.model_validate(guardada)


@router.get("/manuscrito/juez")
def leer_evaluaciones(proyecto: ProyectoAbierto) -> list[Evaluacion]:
    """RF-114: las evaluaciones del juez y las humanas, por versión de novela y momento."""
    return [Evaluacion.model_validate(e) for e in evaluaciones(proyecto.conexion)]
