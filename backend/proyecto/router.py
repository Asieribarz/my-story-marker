"""Rutas transversales del proyecto (spec1.md §5.1): crearlo, su estado, la siguiente orden,
el registro de resultados, el bloqueo, reintentar y borrarlo.

Son la superficie de `persistencia.py` y `bloqueo.py`, sin lógica propia: cada ruta abre el
proyecto de la petición, llama al núcleo con el `ahora` del reloj y traduce lo que devuelve.
Las excepciones del núcleo las convierte en `{codigo, requisito, detalle}` el modelo de
error de `errores_http.py`.

`siguiente` y `resultado` exigen el token del bloqueo en la cabecera `X-Bloqueo`; las
acciones humanas (`reintentar`) no lo exigen (Q7).

Todas leen el cuerpo en JSON estricto (`RutaJsonEstricto`) salvo `resultado`: lo que devolvió
el agente fuera de JSON estricto es un intento fallido de forma, y lo decide el núcleo.
"""

from fastapi import APIRouter
from fastapi.routing import APIRoute

from backend.proyecto.bloqueo import renovar_bloqueo, soltar_bloqueo, tomar_bloqueo
from backend.proyecto.dependencias import (
    Ahora,
    CabeceraBloqueo,
    ProyectoAbierto,
    Raiz,
    RutaJsonEstricto,
    Token,
)
from backend.proyecto.errores import CodigoError, EntradaInvalida
from backend.proyecto.errores_http import documentar
from backend.proyecto.modelos import (
    BloqueoRespuesta,
    EstadoRespuesta,
    Notas,
    NuevoProyecto,
    PeticionBloqueo,
    RegistroRespuesta,
    ResultadoOrden,
    Siguiente,
    siguiente_de,
)
from backend.proyecto.persistencia import (
    borrar_proyecto,
    crear_proyecto,
    emitir_siguiente_orden,
    leer_estado,
    registrar_resultado,
    reintentar,
)

C = CodigoError

router = APIRouter(
    prefix="/proyectos",
    tags=["proyecto"],
    responses=documentar(C.PROYECTO_INEXISTENTE, C.VALIDACION),
    route_class=RutaJsonEstricto,
)


@router.post("", status_code=201)
def crear(ahora: Ahora, raiz: Raiz, cuerpo: NuevoProyecto | None = None) -> EstadoRespuesta:
    """RF-01, RF-05: directorio, base y fila en `intake`, con las paradas elegidas."""
    pedido = cuerpo if cuerpo is not None else NuevoProyecto()
    with crear_proyecto(
        ahora,
        parada_plan=pedido.parada_plan,
        parada_final=pedido.parada_final,
        raiz_proyectos=raiz,
    ) as proyecto:
        return EstadoRespuesta.model_validate(leer_estado(proyecto, ahora))


@router.get("/{id}/estado")
def estado(proyecto: ProyectoAbierto, ahora: Ahora) -> EstadoRespuesta:
    """RF-02: el estado persistido, para reanudar. Sin el token del bloqueo."""
    return EstadoRespuesta.model_validate(leer_estado(proyecto, ahora))


@router.post(
    "/{id}/siguiente",
    response_model=Siguiente,
    responses=documentar(C.BLOQUEO_AJENO, C.BLOQUEO_REQUERIDO),
)
def siguiente(proyecto: ProyectoAbierto, token: Token, ahora: Ahora) -> Siguiente:
    """RF-03, RF-08, RF-08a: la siguiente orden, persistida antes de devolverla.

    Con una orden vigente devuelve esa misma. Si no hay agente que lanzar, la decisión es
    `esperar_humano`, `publicada`, `detenida` o `error_ensamblado`.
    """
    return siguiente_de(emitir_siguiente_orden(proyecto, token, ahora))


def resultado(
    proyecto: ProyectoAbierto, token: Token, ahora: Ahora, cuerpo: ResultadoOrden
) -> RegistroRespuesta:
    """RF-03, RF-06, RF-08a, RF-77a: registra el resultado de la orden vigente.

    Un resultado fuera del esquema del agente es un intento fallido, no un error: responde
    200 con el desenlace `rechazada` y el informe que irá al intento siguiente (TC-11). El
    mismo resultado otra vez devuelve lo registrado con `repetido`.
    """
    registro = registrar_resultado(proyecto, cuerpo.orden, cuerpo.resultado, token, ahora)
    return RegistroRespuesta.model_validate(registro)


# Con la ruta por defecto de FastAPI, no con `RutaJsonEstricto`: un `NaN` o un sustituto
# suelto en la salida del agente no es un 422 que la sesión repetiría sin fin, sino un intento
# fallido que el núcleo registra (RF-77a, TC-11).
router.add_api_route(
    "/{id}/resultado",
    resultado,
    methods=["POST"],
    responses=documentar(C.BLOQUEO_AJENO, C.BLOQUEO_REQUERIDO, C.ORDEN_AJENA, C.AGENTE_SIN_ESQUEMA),
    route_class_override=APIRoute,
)


@router.post(
    "/{id}/bloqueo",
    responses=documentar(C.BLOQUEO_AJENO, C.BLOQUEO_REQUERIDO),
)
def tomar_o_renovar_bloqueo(
    proyecto: ProyectoAbierto,
    ahora: Ahora,
    cabecera: CabeceraBloqueo = None,
    cuerpo: PeticionBloqueo | None = None,
) -> BloqueoRespuesta:
    """RF-09b, Q7: sin cabecera, toma el bloqueo para el `tipo` del cuerpo; con la cabecera
    `X-Bloqueo` de su token, lo renueva otros 30 minutos."""
    if cabecera:
        return BloqueoRespuesta.model_validate(renovar_bloqueo(proyecto, cabecera, ahora))
    if cuerpo is None:
        raise EntradaInvalida(
            'para tomar el bloqueo el cuerpo lleva el tipo de ejecutor: {"tipo": "sesion"} '
            'o {"tipo": "worker"}; para renovarlo, la cabecera X-Bloqueo con su token'
        )
    return BloqueoRespuesta.model_validate(tomar_bloqueo(proyecto, cuerpo.tipo, ahora))


@router.delete(
    "/{id}/bloqueo",
    status_code=204,
    responses=documentar(C.BLOQUEO_AJENO, C.BLOQUEO_REQUERIDO),
)
def soltar(proyecto: ProyectoAbierto, token: Token, ahora: Ahora) -> None:
    """RF-09b: suelta el bloqueo propio. Sin bloqueo, no hace nada."""
    soltar_bloqueo(proyecto, token, ahora)


@router.post("/{id}/reintentar", responses=documentar(C.TRANSICION_INVALIDA))
def reintentar_desde_detenida(
    proyecto: ProyectoAbierto, ahora: Ahora, cuerpo: Notas | None = None
) -> EstadoRespuesta:
    """RF-64b, Q6: desde `detenida`, vuelve a la fase de la que vino con su contador a
    cero. Es una acción humana: no exige el bloqueo."""
    notas = cuerpo.notas if cuerpo is not None else None
    return EstadoRespuesta.model_validate(reintentar(proyecto, ahora, notas))


@router.delete("/{id}", status_code=204, responses=documentar(C.BLOQUEO_AJENO, C.PROYECTO_EN_USO))
def borrar(proyecto: ProyectoAbierto, ahora: Ahora) -> None:
    """RF-09a: borra la base y el directorio enteros, o nada. Con un bloqueo vigente, o con
    otra petición que tenga abierta la base, se deniega."""
    borrar_proyecto(proyecto, ahora)
