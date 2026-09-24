"""Cuerpos de `cambio/`: la salida del Intérprete (RF-121) y las rutas (RF-120, RF-122, §4.3).

La salida del Intérprete es un esquema cerrado de tres casos, el de
`.claude/agents/interprete-cambios.md`: `cambio` (un hecho vigente con su valor anterior y
el nuevo), `nuevo` (un hecho que no existe, con el capítulo del fragmento como destino) y
`ninguno` (la petición no es un cambio de hechos).
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from backend.contexto.modelos import Prioridad, TipoHecho
from backend.proyecto.modelos import ENTERO_MAXIMO
from backend.shared.tipos import EstadoCambio

TOPE_TEXTO = 2_000
TOPE_PETICION = 4_000

# ─── Salida del Intérprete ───────────────────────────────────────────────────


class _Cerrado(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CambioDeHecho(_Cerrado):
    tipo: Literal["cambio"]
    hecho: Annotated[str, Field(pattern=r"^[a-z0-9_]{1,32}$")]
    valor_anterior: Annotated[str, Field(min_length=1, max_length=TOPE_TEXTO)]
    valor_nuevo: Annotated[str, Field(min_length=1, max_length=TOPE_TEXTO)]


class HechoPropuesto(_Cerrado):
    tipo: TipoHecho
    texto: Annotated[str, Field(min_length=1, max_length=TOPE_TEXTO)]
    prioridad: Prioridad = Prioridad.DESEABLE
    momento: str | None = None
    lugar: str | None = None


class HechoNuevo(_Cerrado):
    tipo: Literal["nuevo"]
    hecho: HechoPropuesto
    capitulo: Annotated[int, Field(ge=1, le=10)]


class NingunCambio(_Cerrado):
    tipo: Literal["ninguno"]
    motivo: Annotated[str, Field(min_length=1, max_length=500)]


SalidaInterprete = Annotated[CambioDeHecho | HechoNuevo | NingunCambio, Field(discriminator="tipo")]
VALIDADOR_INTERPRETE: TypeAdapter[CambioDeHecho | HechoNuevo | NingunCambio] = TypeAdapter(
    SalidaInterprete
)

# ─── Rutas ───────────────────────────────────────────────────────────────────


class PeticionCambio(_Cerrado):
    """RF-120: versión, capítulo, fragmento citado, sus párrafos (`data-p`, B-14) y la
    petición. Fragmento y petición son del lector: van a `cambios/`, nunca a la base."""

    version: Annotated[int, Field(ge=1, le=ENTERO_MAXIMO)]
    capitulo: Annotated[int, Field(ge=1, le=10)]
    fragmento: Annotated[str, Field(min_length=1, max_length=TOPE_PETICION)]
    parrafos: tuple[Annotated[int, Field(ge=1, le=10_000)], ...] | None = None
    peticion: Annotated[str, Field(min_length=1, max_length=TOPE_PETICION)]

    @model_validator(mode="after")
    def _parrafos(self) -> "PeticionCambio":
        if self.parrafos is not None and (
            len(self.parrafos) != 2 or self.parrafos[0] > self.parrafos[1]
        ):
            raise ValueError("`parrafos` es [primero, último], con primero ≤ último")
        return self


class ConfirmacionCambio(_Cerrado):
    """RF-122: la decisión del comprador sobre el cambio propuesto."""

    decision: Literal["confirmado", "rechazado"]


class PropuestaRespuesta(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    tipo: Literal["cambio", "nuevo"]
    hecho: str
    valor_anterior: str | None
    valor_nuevo: str


class CambioRespuesta(BaseModel):
    """§4.3: el estado del cambio. `propuesta` desde `propuesto`; `capitulos`, los que
    reabrió la confirmación (V-31); `version_nueva`, la que lo publicó; `motivo`, por qué
    quedó `obsoleto` o `fallido`. Nunca la petición ni el fragmento (V-29)."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    estado: EstadoCambio
    version: int
    capitulo: int
    parrafos: tuple[int, int] | None
    propuesta: PropuestaRespuesta | None
    capitulos: list[int]
    version_nueva: int | None
    motivo: str | None
