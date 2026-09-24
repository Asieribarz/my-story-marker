"""Cuerpos de las rutas de `proyecto/` (spec1.md §5.1): lo que entra y lo que sale.

Los de salida se construyen desde los tipos del núcleo (`EstadoLeido`, `OrdenEmitida`,
`Registro`, `Bloqueo`) con `from_attributes`: la API no recalcula nada, solo lo expone. El
bloqueo se enseña sin su token salvo a quien lo acaba de tomar o renovar.
"""

from datetime import datetime
from typing import Annotated, Any, Literal, assert_never

from pydantic import BaseModel, ConfigDict, Field

from backend.proyecto.maquina import (
    Detenida,
    ErrorConCausa,
    EsperarHumano,
    MotivoEspera,
    Publicada,
    TipoDesenlace,
    ViaRegistro,
)
from backend.proyecto.orden import OrdenEmitida
from backend.proyecto.persistencia import Emision
from backend.shared.tipos import (
    Agente,
    DesenlaceOrden,
    EstadoCapitulo,
    EstadoProyecto,
    TipoEjecutor,
)

# ─── Entrada ─────────────────────────────────────────────────────────────────

# El mayor INTEGER de SQLite. Un id por encima no existe, y pasárselo a `sqlite3` lanza
# `OverflowError`: se rechaza como error de validación antes de llegar a la base.
ENTERO_MAXIMO = 2**63 - 1


class _Entrada(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class NuevoProyecto(_Entrada):
    """RF-01, RF-05: las paradas se eligen al crear y están inactivas por defecto."""

    parada_plan: bool = False
    parada_final: bool = False


class PeticionBloqueo(_Entrada):
    """Q7: quién toma el bloqueo. Solo hace falta al tomarlo; al renovarlo no se mira."""

    tipo: TipoEjecutor


class Metadatos(BaseModel):
    """§4.1.8: lo que el hook sabe de la ejecución del subagente. Todo es opcional y se
    guarda con la orden; un campo que no se conoce se ignora, para que un hook más nuevo no
    deje una salida sin registrar."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    modelo: str | None = Field(default=None, max_length=200)
    tokens_entrada: int | None = Field(default=None, ge=0, le=ENTERO_MAXIMO)
    tokens_salida: int | None = Field(default=None, ge=0, le=ENTERO_MAXIMO)
    tokens_cache_creacion: int | None = Field(default=None, ge=0, le=ENTERO_MAXIMO)
    tokens_cache_lectura: int | None = Field(default=None, ge=0, le=ENTERO_MAXIMO)
    duracion_ms: int | None = Field(default=None, ge=0, le=ENTERO_MAXIMO)
    version_prompt: str | None = Field(default=None, max_length=200)


class ResultadoOrden(_Entrada):
    """RF-03, RF-08a, §4.1.7: la salida de la orden con sello `orden`, sin tocar.

    La API no mira `salida_cruda`: la extrae `extraccion.py` y la valida el manejador de su
    agente (RF-77a); una mal formada es un intento fallido, no un error de la petición.
    """

    orden: str = Field(min_length=1, max_length=200)
    salida_cruda: str
    metadatos: Metadatos | None = None


class Auditoria(_Entrada):
    """§4.1.9: una decisión de la policy del harness sobre una herramienta. Sin argumentos ni
    texto de la llamada: solo qué se decidió, sobre qué herramienta, qué agente y por qué."""

    decision: Literal["permitida", "denegada"]
    herramienta: str | None = Field(default=None, max_length=200)
    agente: str | None = Field(default=None, max_length=200)
    motivo: str | None = Field(default=None, max_length=500)


class DecisionParada(_Entrada):
    """RF-05, RF-36: la decisión del comprador en una parada. `cambios` lleva notas."""

    decision: Literal["aprobado", "cambios"]
    notas: str | None = Field(default=None, max_length=10_000)


class DecisionFinal(DecisionParada):
    """RF-05, M-6: en `aprobacion_final`, «cambios» puede decir qué capítulos revisar; sin
    `capitulos`, se revisan todos."""

    capitulos: list[Annotated[int, Field(ge=1, le=10)]] | None = Field(
        default=None, min_length=1, max_length=10
    )


class Notas(_Entrada):
    """Las notas de una acción humana, que quedan en `decision_humana`."""

    notas: str | None = None


# ─── Salida ──────────────────────────────────────────────────────────────────


class _Salida(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)


class CapituloRespuesta(_Salida):
    numero: int
    estado: EstadoCapitulo
    intentos: int


class OrdenRespuesta(_Salida):
    """RF-08: qué subagente lanzar, con qué entrada y por dónde se registra su resultado."""

    id: int
    estado: EstadoProyecto
    agente: Agente
    intento: int
    capitulo: int | None
    entrada: dict[str, Any]
    registro: ViaRegistro
    emitida: str
    # AJ-4, §4.1.2: la primera línea del prompt. `None` en el estado (RF-02), que no lo enseña.
    sello: str | None


class BloqueoVisibleRespuesta(_Salida):
    tipo: TipoEjecutor
    caduca: datetime


class BloqueoRespuesta(_Salida):
    """El bloqueo recién tomado o renovado, con el token que exigen `siguiente` y `resultado`."""

    token: str
    tipo: TipoEjecutor
    caduca: datetime


class EstadoRespuesta(_Salida):
    """RF-02: el estado para la reanudación y el panel. El bloqueo, sin su token."""

    identificador: str
    estado: EstadoProyecto
    detenida_desde: EstadoProyecto | None
    parada_plan: bool
    parada_final: bool
    ciclos_revision: int
    intentos_paso: int
    capitulos: list[CapituloRespuesta]
    orden_vigente: OrdenRespuesta | None
    bloqueo: BloqueoVisibleRespuesta | None
    creado: str


class RegistroRespuesta(_Salida):
    """RF-06: lo que quedó registrado. `detalle` es el informe, que va al intento siguiente;
    `repetido`, si el mismo resultado ya estaba registrado para esa orden."""

    orden: int
    agente: Agente
    desenlace: DesenlaceOrden
    tipo: TipoDesenlace
    estado: EstadoProyecto
    capitulo: int | None
    estado_capitulo: EstadoCapitulo | None
    detalle: dict[str, Any]
    repetido: bool


# ─── La siguiente orden (RF-08) ──────────────────────────────────────────────


class DecisionOrden(_Salida):
    decision: Literal["orden"] = "orden"
    orden: OrdenRespuesta


class DecisionEsperarHumano(_Salida):
    decision: Literal["esperar_humano"] = "esperar_humano"
    motivo: MotivoEspera


class DecisionPublicada(_Salida):
    decision: Literal["publicada"] = "publicada"


class DecisionDetenida(_Salida):
    decision: Literal["detenida"] = "detenida"
    desde: EstadoProyecto


class DecisionError(_Salida):
    """AJ-5, TC-3: la orden que toca no se puede emitir; `causa` dice por qué (D-9 es una)."""

    decision: Literal["error"] = "error"
    causa: str
    capitulo: int | None
    detalle: dict[str, Any]


Siguiente = Annotated[
    DecisionOrden | DecisionEsperarHumano | DecisionPublicada | DecisionDetenida | DecisionError,
    Field(discriminator="decision"),
]


def siguiente_de(emision: Emision) -> Siguiente:
    """La decisión del núcleo con el nombre que le da RF-08."""
    match emision:
        case OrdenEmitida():
            return DecisionOrden(orden=OrdenRespuesta.model_validate(emision))
        case EsperarHumano(motivo=motivo):
            return DecisionEsperarHumano(motivo=motivo)
        case Publicada():
            return DecisionPublicada()
        case Detenida(desde=desde):
            return DecisionDetenida(desde=desde)
        case ErrorConCausa(causa=causa, capitulo=capitulo, detalle=detalle):
            return DecisionError(causa=causa, capitulo=capitulo, detalle=detalle)
    assert_never(emision)
