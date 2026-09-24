"""Rutas de `cambio` (spec1.md §5.1, TC-12): pedir un cambio, su estado y la confirmación.

Son acciones del lector y del comprador, no del orquestador: no exigen el bloqueo (Q7). El
trabajo lo hace el worker, que encolan pedir y confirmar (TC-8). La petición del lector se
recibe y no se devuelve nunca: ninguna respuesta la lleva, ni el fragmento (V-29).
"""

from typing import Annotated

from fastapi import APIRouter
from fastapi import Path as EnRuta

from backend.cambio.consultas import Peticion, decidir_cambio, leer_cambio, pedir_cambio
from backend.cambio.modelos import CambioRespuesta, ConfirmacionCambio, PeticionCambio
from backend.proyecto.dependencias import Ahora, ProyectoAbierto, RutaJsonEstricto
from backend.proyecto.errores import CodigoError
from backend.proyecto.errores_http import documentar
from backend.proyecto.modelos import ENTERO_MAXIMO

C = CodigoError

router = APIRouter(
    prefix="/proyectos/{id}/cambios",
    tags=["cambio"],
    responses=documentar(C.PROYECTO_INEXISTENTE, C.VALIDACION),
    route_class=RutaJsonEstricto,
)

# El número del cambio en la ruta: por encima del mayor INTEGER de SQLite no existe.
Cambio = Annotated[int, EnRuta(ge=1, le=ENTERO_MAXIMO)]


def _respuesta(proyecto: ProyectoAbierto, cambio: int) -> CambioRespuesta:
    return CambioRespuesta.model_validate(leer_cambio(proyecto.conexion, cambio))


@router.post("", status_code=201, responses=documentar(C.TRANSICION_INVALIDA))
def pedir(proyecto: ProyectoAbierto, ahora: Ahora, cuerpo: PeticionCambio) -> CambioRespuesta:
    """RF-120, RF-123: la petición del lector sobre la versión publicada. Solo cabe en
    `publicada`. Sobre una versión que ya no es la vigente, el cambio queda `obsoleto`; si
    no, `interpretando`, el proyecto pasa a `cambio_solicitado` y se encola un trabajo."""
    numero = pedir_cambio(
        proyecto,
        Peticion(
            version=cuerpo.version,
            capitulo=cuerpo.capitulo,
            parrafos=(cuerpo.parrafos[0], cuerpo.parrafos[1]) if cuerpo.parrafos else None,
            fragmento=cuerpo.fragmento,
            peticion=cuerpo.peticion,
        ),
        ahora,
    )
    return _respuesta(proyecto, numero)


@router.get("/{cambio}", responses=documentar(C.CAMBIO_INEXISTENTE))
def estado(proyecto: ProyectoAbierto, cambio: Cambio) -> CambioRespuesta:
    """§4.3: `interpretando`, `propuesto` (hecho, valor anterior y nuevo), `obsoleto`,
    `rechazado`, `regenerando`, `fallido` o `publicado` (con la versión nueva)."""
    return _respuesta(proyecto, cambio)


@router.post(
    "/{cambio}/confirmacion",
    responses=documentar(C.CAMBIO_INEXISTENTE, C.DECISION_HUMANA_INVALIDA, C.TRANSICION_INVALIDA),
)
def confirmar(
    proyecto: ProyectoAbierto, ahora: Ahora, cambio: Cambio, cuerpo: ConfirmacionCambio
) -> CambioRespuesta:
    """RF-122: confirmar aplica el cambio, reabre los capítulos que usan el hecho y encola
    la regeneración; rechazar vuelve a `publicada` sin tocar nada."""
    decidir_cambio(proyecto, cambio, cuerpo.decision == "confirmado", ahora)
    return _respuesta(proyecto, cambio)
