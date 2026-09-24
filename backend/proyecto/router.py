"""Rutas transversales del proyecto (spec1.md §5.1): crearlo, su estado, la siguiente orden,
el registro de resultados, el bloqueo, las paradas (RF-05, RF-36), reintentar, la auditoría
de la policy (§4.1.9) y borrarlo.

Son la superficie de `persistencia.py` y `bloqueo.py`, sin lógica propia: cada ruta abre el
proyecto de la petición, llama al núcleo con el `ahora` del reloj y traduce lo que devuelve.
Las excepciones del núcleo las convierte en `{codigo, requisito, detalle}` el modelo de
error de `errores_http.py`.

`siguiente` y `resultado` exigen el token del bloqueo en la cabecera `X-Bloqueo`; las
acciones humanas (paradas y `reintentar`) y la auditoría del hook no lo exigen (Q7).

Todas leen el cuerpo en JSON estricto (`RutaJsonEstricto`) salvo `resultado`: lo que devolvió
el agente fuera de JSON estricto es un intento fallido de forma, y lo decide el núcleo.
"""

from fastapi import APIRouter
from fastapi.routing import APIRoute

from backend.proyecto.abierto import instante
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
    Auditoria,
    BloqueoRespuesta,
    DecisionFinal,
    DecisionParada,
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
    auditar_policy,
    borrar_proyecto,
    crear_proyecto,
    decidir_parada,
    emitir_siguiente_orden,
    leer_estado,
    registrar_resultado,
    reintentar,
)
from backend.shared.db import transaccion

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

    Con una orden vigente devuelve esa misma, con su sello (AJ-4). Si no hay agente que
    lanzar, la decisión es `esperar_humano`, `publicada`, `detenida` o `error` con su causa.
    """
    return siguiente_de(emitir_siguiente_orden(proyecto, token, ahora))


def resultado(
    proyecto: ProyectoAbierto, token: Token, ahora: Ahora, cuerpo: ResultadoOrden
) -> RegistroRespuesta:
    """RF-03, RF-06, RF-08a, RF-77a, §4.1.7: registra la salida cruda de la orden del sello.

    Una salida mal formada o fuera del esquema del agente es un intento fallido, no un
    error: responde 200 con el desenlace `rechazada` y el informe que irá al intento
    siguiente (TC-11). La misma salida otra vez devuelve lo registrado con `repetido`. Un
    sello viejo da `sello_invalido` (AJ-4).
    """
    metadatos = None if cuerpo.metadatos is None else cuerpo.metadatos.model_dump(exclude_none=True)
    registro = registrar_resultado(
        proyecto, cuerpo.orden, cuerpo.salida_cruda, token, ahora, metadatos
    )
    return RegistroRespuesta.model_validate(registro)


# Con la ruta por defecto de FastAPI, no con `RutaJsonEstricto`: un `NaN` o un sustituto
# suelto en la salida del agente no es un 422 que la sesión repetiría sin fin, sino un intento
# fallido que el núcleo registra (RF-77a, TC-11).
router.add_api_route(
    "/{id}/resultado",
    resultado,
    methods=["POST"],
    responses=documentar(
        C.BLOQUEO_AJENO,
        C.BLOQUEO_REQUERIDO,
        C.ORDEN_AJENA,
        C.SELLO_INVALIDO,
        C.AGENTE_SIN_ESQUEMA,
        C.TRANSICION_INVALIDA,
        C.HERRAMIENTA_NO_DISPONIBLE,
    ),
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


@router.post("/{id}/plan/aprobacion", responses=documentar(C.TRANSICION_INVALIDA))
def aprobar_plan(
    proyecto: ProyectoAbierto, ahora: Ahora, cuerpo: DecisionParada
) -> EstadoRespuesta:
    """RF-36: la decisión del comprador en `aprobacion_plan`, única salida de la parada.
    `aprobado` pasa a la escaleta; `cambios`, con notas, vuelve al planificador."""
    estado = decidir_parada(proyecto, "aprobacion_plan", cuerpo.decision, ahora, cuerpo.notas)
    return EstadoRespuesta.model_validate(estado)


@router.post("/{id}/aprobacion-final", responses=documentar(C.TRANSICION_INVALIDA))
def aprobar_final(
    proyecto: ProyectoAbierto, ahora: Ahora, cuerpo: DecisionFinal
) -> EstadoRespuesta:
    """RF-05: la decisión del comprador en `aprobacion_final`. `aprobado` publica; `cambios`,
    con notas, va a `revision` con los `capitulos` que diga, o con todos (M-6)."""
    # TC-8: en una regeneración, la decisión deja trabajo que nadie lanzaría —el Exportador
    # o la revisión—: se encola otro para el worker, en la misma transacción.
    from backend.cambio.consultas import encolar_si_regenera

    with transaccion(proyecto.conexion) as conexion:
        estado = decidir_parada(
            proyecto, "aprobacion_final", cuerpo.decision, ahora, cuerpo.notas, cuerpo.capitulos
        )
        encolar_si_regenera(conexion, instante(ahora))
    return EstadoRespuesta.model_validate(estado)


@router.post("/{id}/auditoria", status_code=204)
def auditoria(proyecto: ProyectoAbierto, ahora: Ahora, cuerpo: Auditoria) -> None:
    """§4.1.9: registra una decisión de la policy del harness, con tipo `policy`."""
    auditar_policy(proyecto, cuerpo.model_dump(), ahora)


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
