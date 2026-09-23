"""Salida del escaletista (B-5, RF-40): las fichas de capítulo.

Solo tipos y valores permitidos. Las reglas —RF-41 y RF-42 (V-21), RF-43, que `tension` y
`cierre` coincidan con el contexto, B-9 antes de escribir— son del manejador del
escaletista; B-9 tiene sus dos comprobaciones en `capitulo/biblia.py`.
"""

from typing import Annotated, Literal

from pydantic import Field

from backend.contexto.modelos import Capitulo, Cierre, Modelo, Texto
from backend.planificacion.modelos import Id
from backend.shared.tipos import Hito

IdHecho = Annotated[str, Field(pattern=r"^[a-z0-9_]{1,32}$")]


class Escena(Modelo):
    tipo: Literal["escena", "secuela"]
    texto: Texto


class PresagioPrevisto(Modelo):
    """B-16: un presagio que la ficha planta; nace `previsto` al registrar la escaleta."""

    clave: Id
    descripcion: Texto


class Traspaso(Modelo):
    """Un objeto que cambia de manos en el capítulo; `a` NULL: deja de tenerlo nadie."""

    objeto: Id
    a: Id | None = None


class FichaCapitulo(Modelo):
    """B-5. `presentes` actúan en el presente del capítulo; `mencionados` solo salen en un
    recuerdo o una analepsis y no se bloquean (R-2). `dia` es el día previsto (B-6)."""

    numero: Capitulo
    hitos: tuple[Hito, ...] = ()
    objetivo: Texto
    escenas: Annotated[tuple[Escena, ...], Field(min_length=1)]
    pov: Id
    localizacion: Id
    presentes: Annotated[tuple[Id, ...], Field(min_length=1)]
    mencionados: tuple[Id, ...] = ()
    dia: Annotated[int, Field(ge=1)]
    tension: Annotated[int, Field(ge=0, le=10)]
    palabras_objetivo: Annotated[int, Field(ge=1000, le=1500)]
    cierre: Cierre
    plantar: tuple[PresagioPrevisto, ...] = ()
    cobrar: tuple[Id, ...] = ()
    hechos: tuple[IdHecho, ...] = ()
    traspasos: tuple[Traspaso, ...] = ()


class SalidaEscaletista(Modelo):
    """La salida del escaletista (RF-77a). Cuántas fichas y en qué orden lo mira RF-41."""

    fichas: Annotated[tuple[FichaCapitulo, ...], Field(min_length=1)]
