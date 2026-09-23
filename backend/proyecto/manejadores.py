"""Qué hace el backend con el resultado de cada agente, y qué entrada lleva cada orden.

Dos registros, uno por agente, para que cada paso del plan añada lo suyo sin tocar la
máquina ni la persistencia:

- `MANEJADORES`: valida el resultado contra el esquema de salida del agente (RF-77a), lo
  persiste en su rebanada si procede y devuelve el desenlace. Escribe **solo** datos de su
  rebanada: el estado del grafo y los contadores los escribe `persistencia.py` con lo que
  calcula `maquina.aplicar_desenlace`. Corre dentro de la transacción del registro, así que
  sus escrituras, el cierre de la orden y la transición van juntos o no van.
- `CONSTRUCTORES_DE_ENTRADA`: completa la entrada de una orden al emitirla, dentro de la
  transacción que la persiste. Es donde el Extractor recibe el identificador de un solo uso
  de `/mcp/entrada` en vez del texto libre (RF-14).
- `RENOVACION_DE_ENTRADA`: al devolver otra vez la orden vigente, dice si su entrada todavía
  se puede entregar. Si no —su identificador de un solo uso ya se canjeó o está a punto de
  caducar—, da la entrada nueva: la persistencia la escribe en la misma orden, que conserva
  su id, su agente y su intento (RF-08a), y la devuelve. Si sirve, la orden va idéntica.

Un agente sin manejador da `AgenteSinEsquema` con el paso en que llega; la orden sigue
vigente y no gasta intento (Q8). Hoy solo tienen manejador `extractor-hechos` y
`agente-contexto`.
"""

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from backend.contexto.persistencia import guardar_contexto
from backend.contexto.validacion import puede_salir_de_contexto, validar
from backend.intake.entrada import emitir_texto_libre, entregable, retirar
from backend.intake.persistencia import guardar_normalizado, proponer_hechos, registrar_extraccion
from backend.proyecto.abierto import Proyecto, instante
from backend.proyecto.errores import AgenteSinEsquema
from backend.proyecto.maquina import Desenlace, Lanzar
from backend.proyecto.orden import OrdenEmitida
from backend.shared.tipos import Agente, EstadoProyecto, RecursoEntrada

# Q8: en qué paso de specs/plan-backend-v1.md llega el esquema de salida de cada agente.
PASO_QUE_LO_TRAE: dict[Agente, str] = {
    Agente.ARQUITECTO: "paso 4",
    Agente.PERSONAJES: "paso 4",
    Agente.MUNDO: "paso 4",
    Agente.ESTILO: "paso 4",
    Agente.ESCALETISTA: "paso 4",
    Agente.ESCRITOR: "paso 7",
    Agente.EDITOR_ESTILO: "paso 7",
    Agente.JUEZ_CAPITULO: "paso 7",
    Agente.BIBLIOTECARIO: "paso 8",
    Agente.JUEZ_MANUSCRITO: "paso 8a",
    Agente.REVISOR: "paso 8a",
    Agente.EXPORTADOR: "paso 9",
    Agente.INTERPRETE_CAMBIOS: "paso 9a",
}


@dataclass(frozen=True)
class ContextoManejo:
    proyecto: Proyecto
    orden: OrdenEmitida
    ahora: datetime

    @property
    def conexion(self) -> sqlite3.Connection:
        return self.proyecto.conexion

    @property
    def momento(self) -> str:
        return instante(self.ahora)


@dataclass(frozen=True)
class Salida:
    """Lo que devuelve un manejador: el desenlace y su informe, que va a `orden.detalle` y
    es la entrada del intento siguiente si lo hay. Sin valores de datos excluidos (RF-13)."""

    desenlace: Desenlace
    detalle: dict[str, Any] = field(default_factory=dict)


Manejador = Callable[[ContextoManejo, object], Salida]

MANEJADORES: dict[Agente, Manejador] = {}


def manejador(agente: Agente) -> Callable[[Manejador], Manejador]:
    def registrar(funcion: Manejador) -> Manejador:
        MANEJADORES[agente] = funcion
        return funcion

    return registrar


def manejador_de(agente: Agente) -> Manejador:
    encontrado = MANEJADORES.get(agente)
    if encontrado is None:
        raise AgenteSinEsquema(agente, PASO_QUE_LO_TRAE.get(agente, "un paso posterior"))
    return encontrado


@dataclass(frozen=True)
class SolicitudEntrada:
    proyecto: Proyecto
    estado: EstadoProyecto
    lanzar: Lanzar
    ahora: datetime
    # El informe del intento fallido inmediatamente anterior, si la orden es un reintento.
    informe_anterior: object | None = None


ConstructorEntrada = Callable[[SolicitudEntrada, dict[str, Any]], dict[str, Any]]

CONSTRUCTORES_DE_ENTRADA: dict[Agente, ConstructorEntrada] = {}


def constructor_de_entrada(agente: Agente) -> Callable[[ConstructorEntrada], ConstructorEntrada]:
    def registrar(funcion: ConstructorEntrada) -> ConstructorEntrada:
        CONSTRUCTORES_DE_ENTRADA[agente] = funcion
        return funcion

    return registrar


def construir_entrada(solicitud: SolicitudEntrada) -> dict[str, Any]:
    """La entrada base —qué necesita el agente y el informe anterior— más lo que añada el
    constructor de su agente. Corre dentro de la transacción que persiste la orden."""
    lanzar = solicitud.lanzar
    base: dict[str, Any] = {
        "estado": solicitud.estado.value,
        "agente": lanzar.agente.value,
        "capitulo": lanzar.capitulo,
        "intento": lanzar.intento,
        "necesita": [e.value for e in lanzar.entrada],
        "informe_anterior": solicitud.informe_anterior,
    }
    constructor = CONSTRUCTORES_DE_ENTRADA.get(lanzar.agente)
    return base if constructor is None else constructor(solicitud, base)


# Devuelve la entrada nueva de la orden vigente, o `None` si la que tiene aún se entrega.
RenovadorEntrada = Callable[[ContextoManejo], dict[str, Any] | None]

RENOVACION_DE_ENTRADA: dict[Agente, RenovadorEntrada] = {}


def renovacion_de_entrada(agente: Agente) -> Callable[[RenovadorEntrada], RenovadorEntrada]:
    def registrar(funcion: RenovadorEntrada) -> RenovadorEntrada:
        RENOVACION_DE_ENTRADA[agente] = funcion
        return funcion

    return registrar


def entrada_renovada(contexto: ContextoManejo) -> dict[str, Any] | None:
    """La entrada nueva de la orden vigente si la suya ya no se puede entregar. Corre dentro
    de la transacción de emisión. Sin renovador, la entrada no caduca nunca: `None`."""
    renovador = RENOVACION_DE_ENTRADA.get(contexto.orden.agente)
    return None if renovador is None else renovador(contexto)


def _errores(error: ValidationError) -> list[str]:
    """Ruta y mensaje de cada error, sin el valor recibido: puede ser un dato excluido."""
    return [
        f"{'.'.join(str(parte) for parte in e['loc']) or '(raíz)'}: {e['msg']}"
        for e in error.errors(include_url=False)
    ]


# ─── extractor-hechos ────────────────────────────────────────────────────────


class SalidaExtractor(BaseModel):
    """RF-15, RF-77a: el sobre de la salida del Extractor. Cada hecho se valida después,
    uno a uno, contra definitions.md §9: uno que no encaja se rechaza sin tumbar al resto."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hechos: list[Any]


@constructor_de_entrada(Agente.EXTRACTOR_HECHOS)
def _entrada_del_extractor(solicitud: SolicitudEntrada, base: dict[str, Any]) -> dict[str, Any]:
    """RF-14: el texto libre no va en la orden. Va un identificador de un solo uso, emitido en
    la transacción que persiste la orden, que el Extractor canjea por `/mcp/entrada`."""
    proyecto = solicitud.proyecto
    emitido = emitir_texto_libre(proyecto.conexion, proyecto.disposicion, solicitud.ahora)
    return {**base, RecursoEntrada.TEXTO_LIBRE.value: emitido.como_entrada()}


@renovacion_de_entrada(Agente.EXTRACTOR_HECHOS)
def _renovar_texto_libre(contexto: ContextoManejo) -> dict[str, Any] | None:
    """RF-14, RNF-01: la orden vigente del Extractor se entrega con un identificador que se
    pueda canjear. El que lleva deja de valer si ya se canjeó —el subagente que lo hizo murió
    con su sesión— o si caduca antes de que el relanzado llegue a usarlo; entonces se retira
    y va uno nuevo en la misma orden."""
    entrada = contexto.orden.entrada
    actual = entrada.get(RecursoEntrada.TEXTO_LIBRE.value)
    identificador = actual.get("identificador") if isinstance(actual, dict) else None
    if isinstance(identificador, str):
        if entregable(contexto.conexion, identificador, contexto.ahora):
            return None
        retirar(contexto.conexion, identificador)
    proyecto = contexto.proyecto
    emitido = emitir_texto_libre(proyecto.conexion, proyecto.disposicion, contexto.ahora)
    return {**entrada, RecursoEntrada.TEXTO_LIBRE.value: emitido.como_entrada()}


@manejador(Agente.EXTRACTOR_HECHOS)
def _extractor_de_hechos(contexto: ContextoManejo, resultado: object) -> Salida:
    try:
        salida = SalidaExtractor.model_validate(resultado)
    except ValidationError as error:
        return Salida(Desenlace.forma(), {"errores": _errores(error)})
    propuesta = proponer_hechos(contexto.conexion, list(salida.hechos), contexto.momento)
    registrar_extraccion(contexto.conexion, contexto.orden.id)
    return Salida(
        Desenlace.aceptado(),
        {
            "aceptados": list(propuesta.aceptados),
            "rechazados": [[indice, motivo] for indice, motivo in propuesta.rechazados],
            "descartes": [{"tipo": d.tipo, "campo": d.campo} for d in propuesta.descartes],
        },
    )


# ─── agente-contexto ─────────────────────────────────────────────────────────


@manejador(Agente.AGENTE_CONTEXTO)
def _agente_de_contexto(contexto: ContextoManejo, resultado: object) -> Salida:
    """En `intake` normaliza el brief (RF-11); en `contexto` instancia la ontología.

    El contexto se valida con el `hoy` del instante inyectado. Con un hallazgo bloqueante
    no se persiste (RF-22): es un fallo de contenido y el informe va al intento siguiente.
    Sin contexto persistido, la transición a `planificacion` no se deriva (V-20).
    """
    if contexto.orden.estado is EstadoProyecto.INTAKE:
        if not isinstance(resultado, dict) or not resultado:
            return Salida(Desenlace.forma(), {"errores": ["(raíz): un objeto no vacío"]})
        descartes = guardar_normalizado(contexto.conexion, resultado, contexto.momento)
        return Salida(
            Desenlace.aceptado(),
            {"descartes": [{"tipo": d.tipo, "campo": d.campo} for d in descartes]},
        )
    informe = validar(resultado, contexto.ahora.astimezone(UTC).date())
    if not puede_salir_de_contexto(informe):
        return Salida(
            Desenlace.contenido(),
            {
                "hallazgos": [h.model_dump(mode="json") for h in informe.hallazgos],
                "rellenados": list(informe.rellenados),
            },
        )
    guardar_contexto(contexto.conexion, informe, contexto.momento)
    return Salida(Desenlace.aceptado(), {"rellenados": list(informe.rellenados)})
