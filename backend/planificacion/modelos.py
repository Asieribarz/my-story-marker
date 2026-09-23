"""Salida del planificador (R-1, B-3, B-4): plan, personajes, mundo y guía en un solo JSON.

Extiende los modelos del contexto (D-4: una sola fuente de tipos). Aquí solo van tipos y
valores permitidos; las reglas que cruzan con el contexto —B-1 (añade, no cambia), RF-34,
el nombre de los personajes reales, que la lista negra incluya `lenguaje.prohibidas`— son
del manejador del planificador. Los ids siguen el patrón de los del contexto.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import Field

from backend.contexto.modelos import (
    Capitulo,
    Lenguaje,
    Localizacion,
    Modelo,
    ModeloEstructural,
    Personaje,
    Porcentaje,
    Texto,
    TipoFinal,
)
from backend.shared.tipos import Hito

TOPE_DESCRIPCION = 600
TOPE_EJEMPLO = 600
MAX_EJEMPLOS = 3

Id = Annotated[str, Field(pattern=r"^[a-z0-9_]{1,32}$")]
Descripcion = Annotated[str, Field(min_length=1, max_length=TOPE_DESCRIPCION)]


class Reparto(Modelo):
    """B-3: en qué capítulo cae cada hito del catálogo."""

    detonante: Capitulo
    primer_umbral: Capitulo
    punto_medio: Capitulo
    crisis: Capitulo
    climax: Capitulo

    def capitulo(self, hito: Hito) -> int:
        valor: int = getattr(self, hito.value)
        return valor


class Plan(Modelo):
    """RF-30: el plan estructural."""

    modelo: ModeloEstructural
    reparto: Reparto
    curva_tension: Annotated[
        tuple[Annotated[int, Field(ge=0, le=10)], ...], Field(min_length=10, max_length=10)
    ]
    pregunta_dramatica: Texto
    tipo_final: TipoFinal


class TipoRelacion(StrEnum):
    ALIANZA = "alianza"
    RIVALIDAD = "rivalidad"
    MENTORIA = "mentoria"
    FAMILIAR = "familiar"
    ROMANCE = "romance"
    DEUDA = "deuda"


class RelacionPersonaje(Modelo):
    """RF-31: una arista del grafo dirigido; el origen es el personaje que la declara."""

    destino: Id
    tipo: TipoRelacion
    estado_inicial: str | None = None
    estado_final: str | None = None


class PersonajePlan(Personaje):
    """B-4: el personaje del contexto con lo que añade el planificador. `estado_inicial` y
    `sabe` son el capítulo 0 de la biblia (B-2); nombre y alias siembran el glosario."""

    nombre: Texto
    alias: tuple[Texto, ...] = ()
    descripcion: Descripcion | None = None
    estado_inicial: Texto
    sabe: tuple[Texto, ...] = ()
    relaciones: tuple[RelacionPersonaje, ...] = ()


class LocalizacionPlan(Localizacion):
    """B-4: la localización con nombre, descripción con tope e hito, si es clave (RF-34)."""

    nombre: Texto
    descripcion: Descripcion
    hito: Hito | None = None
    estado_inicial: str | None = None


class Objeto(Modelo):
    """B-4: un objeto del mundo y su poseedor inicial (inventario en el capítulo 0)."""

    id: Id
    nombre: Texto
    alias: tuple[Texto, ...] = ()
    poseedor: Id | None = None


class MundoPlan(Modelo):
    """B-4: todas las localizaciones —las del contexto con su nombre, y las `micro` que
    añade— y los objetos. La ruta y las reglas son las del contexto, ya materializadas."""

    localizaciones: Annotated[tuple[LocalizacionPlan, ...], Field(min_length=1)]
    objetos: tuple[Objeto, ...] = ()


class Metricas(Modelo):
    frase_media_palabras: Annotated[float, Field(gt=0, le=60)]
    proporcion_dialogo: Porcentaje
    descriptivo: Porcentaje
    legibilidad_min: Annotated[float, Field(ge=0, le=100)]


class GuiaEstilo(Lenguaje):
    """RF-33, B-4: el lenguaje del contexto con métricas, lista negra, onomástica y
    ejemplos con tope."""

    metricas: Metricas
    lista_negra: tuple[Texto, ...] = ()
    onomastica: str | None = None
    ejemplos: Annotated[
        tuple[Annotated[str, Field(min_length=1, max_length=TOPE_EJEMPLO)], ...],
        Field(max_length=MAX_EJEMPLOS),
    ] = ()


class SalidaPlanificador(Modelo):
    """R-1: la salida única del planificador (RF-77a)."""

    plan: Plan
    personajes: Annotated[tuple[PersonajePlan, ...], Field(min_length=1)]
    mundo: MundoPlan
    estilo: GuiaEstilo
