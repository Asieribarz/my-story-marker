"""Rutas de `intake` (spec-backend-1.md §5.1): el brief del comprador y la confirmación de hechos.

Son acciones del comprador, no del orquestador: no exigen el bloqueo (Q7) y solo caben en
`intake`; fuera de esa fase dan `TransicionInvalida` y no escriben nada (RF-04). Ninguna
mueve el grafo por sí misma: la transición la deriva la siguiente orden, cuando el brief
está normalizado y no quedan hechos pendientes.

Todo dato de persona que viaja por aquí es del comprador; los excluidos por C-8 se
descartan y se auditan sin su valor (RF-13), y la respuesta solo dice su tipo y su campo.
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.contexto.modelos import Prioridad, TipoHecho
from backend.intake.persistencia import (
    DecisionInvalida,
    confirmar_hechos,
    guardar_brief,
    hechos_pendientes,
)
from backend.proyecto.abierto import Proyecto, instante
from backend.proyecto.dependencias import Ahora, ProyectoAbierto, RutaJsonEstricto
from backend.proyecto.errores import CodigoError, DecisionHumanaInvalida
from backend.proyecto.errores_http import documentar
from backend.proyecto.modelos import ENTERO_MAXIMO
from backend.proyecto.persistencia import exigir_fase, reiniciar_paso
from backend.shared.db import transaccion
from backend.shared.tipos import EstadoProyecto

router = APIRouter(
    prefix="/proyectos/{id}",
    tags=["intake"],
    responses=documentar(
        CodigoError.PROYECTO_INEXISTENTE,
        CodigoError.VALIDACION,
        CodigoError.TRANSICION_INVALIDA,
    ),
    route_class=RutaJsonEstricto,
)


class HechosNoPendientes(DecisionHumanaInvalida):
    """RF-15: se decide sobre un hecho que no existe o que ya no está pendiente."""

    requisito = "RF-15"


# ─── Cuerpos ─────────────────────────────────────────────────────────────────


class Brief(BaseModel):
    """RF-10, RF-14: las respuestas de la entrevista y, si lo hay, el texto libre, que se
    guarda aparte como no confiable. Volver a enviarlo sustituye el anterior."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    respuestas: dict[str, Any] = Field(min_length=1)
    texto_libre: str | None = Field(default=None, min_length=1)


class Descarte(BaseModel):
    tipo: str
    campo: str


class BriefGuardado(BaseModel):
    descartes: list[Descarte]
    texto_libre: bool


class HechoPendiente(BaseModel):
    id: int
    tipo: TipoHecho
    texto: str
    prioridad: Prioridad
    momento: str | None
    lugar: str | None


class Hechos(BaseModel):
    """Los hechos que el Extractor propuso y el comprador aún no ha decidido (RF-15)."""

    hechos: list[HechoPendiente]


class DecisionHecho(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    hecho: int = Field(ge=1, le=ENTERO_MAXIMO)
    confirmado: bool


class Confirmacion(BaseModel):
    """RF-15: confirmar o rechazar hechos pendientes, uno a uno. Los que no se nombran
    siguen pendientes y el proyecto sigue esperando la confirmación."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decisiones: list[DecisionHecho] = Field(min_length=1)

    @field_validator("decisiones")
    @classmethod
    def _una_por_hecho(cls, decisiones: list[DecisionHecho]) -> list[DecisionHecho]:
        hechos = [d.hecho for d in decisiones]
        if len(set(hechos)) != len(hechos):
            raise ValueError("cada hecho se decide una sola vez")
        return decisiones


# ─── Rutas ───────────────────────────────────────────────────────────────────


def _pendientes(proyecto: Proyecto) -> Hechos:
    return Hechos(
        hechos=[
            HechoPendiente(
                id=fila["id"],
                tipo=fila["tipo"],
                texto=fila["texto"],
                prioridad=fila["prioridad"],
                momento=fila["momento"],
                lugar=fila["lugar"],
            )
            for fila in hechos_pendientes(proyecto.conexion)
        ]
    )


@router.post("/brief")
def enviar_brief(proyecto: ProyectoAbierto, ahora: Ahora, cuerpo: Brief) -> BriefGuardado:
    """RF-10, RF-13, RF-14: guarda la entrevista y el texto libre del comprador.

    Volver a enviarlo sustituye el anterior y empieza `intake` de nuevo: la orden vigente se
    cierra sin gastar intento, el contador de paso vuelve a cero (RF-07a) y, si el texto libre
    cambia, lo extraído del anterior deja de valer (RF-15).
    """
    with transaccion(proyecto.conexion) as conexion:
        exigir_fase(conexion, EstadoProyecto.INTAKE, "enviar el brief")
        reiniciar_paso(conexion, "enviar_brief", instante(ahora))
        descartes = guardar_brief(
            conexion,
            proyecto.disposicion,
            dict(cuerpo.respuestas),
            cuerpo.texto_libre,
            instante(ahora),
        )
    return BriefGuardado(
        descartes=[Descarte(tipo=d.tipo, campo=d.campo) for d in descartes],
        texto_libre=cuerpo.texto_libre is not None,
    )


@router.get("/hechos")
def leer_hechos_pendientes(proyecto: ProyectoAbierto) -> Hechos:
    """RF-15: los hechos propuestos que esperan la decisión del comprador."""
    return _pendientes(proyecto)


@router.post(
    "/hechos/confirmacion",
    responses=documentar(CodigoError.DECISION_HUMANA_INVALIDA),
)
def confirmar(proyecto: ProyectoAbierto, ahora: Ahora, cuerpo: Confirmacion) -> Hechos:
    """RF-15: confirma o rechaza hechos pendientes y devuelve los que siguen pendientes.

    Solo los confirmados entran en el contexto. Un hecho que no está pendiente da
    `decision_humana_invalida` y no se decide ninguno.
    """
    with transaccion(proyecto.conexion) as conexion:
        exigir_fase(conexion, EstadoProyecto.INTAKE, "confirmar hechos")
        try:
            confirmar_hechos(
                conexion, {d.hecho: d.confirmado for d in cuerpo.decisiones}, instante(ahora)
            )
        except DecisionInvalida as error:
            raise HechosNoPendientes(str(error)) from error
    return _pendientes(proyecto)
