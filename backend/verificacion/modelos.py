"""Rúbrica del juez de manuscrito y de la revisión humana (RF-113, RF-114, TC-5).

Una sola forma para los dos: cinco criterios de enum cerrado, cada uno una vez, con una
puntuación entera de 1 a 5 y su justificación. El juez añade `capitulos`, los que señalan
sus justificaciones (decisiones-backend §3 punto 7). El umbral lo aplica el backend, no el
juez: `aprueba`.
"""

from collections.abc import Iterable
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from backend.shared.tipos import CriterioManuscrito

# TC-5: la media 3,5 de architecture §4.1 no es alcanzable con cinco enteros: suma ≥ 18.
SUMA_MINIMA = 18
MINIMO_POR_CRITERIO = 3


class CriterioPuntuado(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    criterio: CriterioManuscrito
    puntuacion: Annotated[StrictInt, Field(ge=1, le=5)]
    justificacion: Annotated[str, Field(min_length=1)]


class Rubrica(BaseModel):
    """RF-113, RF-114: los cinco criterios, cada uno exactamente una vez."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    criterios: tuple[CriterioPuntuado, ...]

    @model_validator(mode="after")
    def _cinco_criterios(self) -> "Rubrica":
        vistos = [c.criterio for c in self.criterios]
        if sorted(vistos) != sorted(CriterioManuscrito):
            raise ValueError("los cinco criterios de la rúbrica, cada uno una vez")
        return self

    @property
    def puntuaciones(self) -> dict[str, int]:
        return {c.criterio.value: c.puntuacion for c in self.criterios}

    @property
    def suma(self) -> int:
        return sum(c.puntuacion for c in self.criterios)

    @property
    def aprueba(self) -> bool:
        return aprueba(self.puntuaciones.values())


class SalidaJuezManuscrito(Rubrica):
    """La salida del juez de manuscrito (`.claude/agents/juez-manuscrito.md`)."""

    capitulos: tuple[Annotated[StrictInt, Field(ge=1, le=10)], ...] = ()

    @model_validator(mode="after")
    def _suspende_con_capitulos(self) -> "SalidaJuezManuscrito":
        """M-6: un juez que suspende señala al menos un capítulo; si no, no hay Revisor
        que lanzar."""
        if not self.aprueba and not self.capitulos:
            raise ValueError("un manuscrito que no aprueba señala al menos un capítulo")
        return self


def aprueba(puntuaciones: Iterable[int]) -> bool:
    """TC-5, V-32: suma ≥ 18 y ningún criterio por debajo de 3."""
    lista = list(puntuaciones)
    return sum(lista) >= SUMA_MINIMA and min(lista) >= MINIMO_POR_CRITERIO
