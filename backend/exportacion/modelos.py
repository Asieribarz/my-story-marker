"""Modelos de `exportacion`: la salida del Exportador, `lectura.json` y `GET /versiones`.

`Lectura` es la forma exacta de specs/plan-frontend.md §5.2, adoptada tal cual por
decisiones-backend §4.3; `Versiones`, la de §5.3.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.capitulo.segmentacion import contar_palabras
from backend.contexto.modelos import Rol

MAX_PALABRAS_SINOPSIS = 120
NUMERO_CAPITULOS = 10

Texto = Annotated[str, Field(min_length=1)]
NumeroCapitulo = Annotated[int, Field(ge=1, le=NUMERO_CAPITULOS)]


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SalidaExportador(_Modelo):
    """RF-91, RF-77a: los metadatos editoriales que produce el Exportador
    (`.claude/agents/exportador.md`). `serie` y `volumen` los pide el fichero del agente,
    `null` salvo saga; se aceptan opcionales para que su salida no sea inválida."""

    titulo: Annotated[str, Field(min_length=1, max_length=200)]
    sinopsis: Texto
    palabras_clave: Annotated[tuple[Texto, ...], Field(min_length=5, max_length=8)]
    serie: Annotated[str, Field(min_length=1)] | None = None
    volumen: Annotated[int, Field(ge=1)] | None = None

    @field_validator("titulo", "sinopsis")
    @classmethod
    def _sin_blancos(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            raise ValueError("no puede estar en blanco")
        return limpio

    @field_validator("sinopsis")
    @classmethod
    def _sinopsis_corta(cls, valor: str) -> str:
        if contar_palabras(valor) > MAX_PALABRAS_SINOPSIS:
            raise ValueError(f"la sinopsis pasa de {MAX_PALABRAS_SINOPSIS} palabras")
        return valor

    @field_validator("palabras_clave")
    @classmethod
    def _en_minusculas(cls, valor: tuple[str, ...]) -> tuple[str, ...]:
        """Se guardan en minúsculas y sin blancos; repetidas son inválidas."""
        limpias = tuple(p.strip().lower() for p in valor)
        if any(not p for p in limpias):
            raise ValueError("una palabra clave en blanco")
        if len(set(limpias)) != len(limpias):
            raise ValueError("palabras clave repetidas")
        return limpias


class Portada(_Modelo):
    titulo: Texto
    dedicatoria: str | None


class CapituloLectura(_Modelo):
    numero: NumeroCapitulo
    titulo: str | None
    html: str


class PersonajeLectura(_Modelo):
    """Sin deseo, necesidad, herida ni defecto: plan-frontend §5.2, «qué no lleva»."""

    id: Texto
    nombre: Texto
    rol: Annotated[tuple[Rol, ...], Field(min_length=1)]
    descripcion: str | None = None
    capitulos: tuple[NumeroCapitulo, ...]


class LugarLectura(_Modelo):
    id: Texto
    nombre: Texto
    descripcion: str | None = None
    padre: str | None
    capitulos: tuple[NumeroCapitulo, ...]


class Lectura(_Modelo):
    """RF-97, TC-7: `lectura.json`, uno por versión en `export/vN/`."""

    version: Annotated[int, Field(ge=1)]
    anterior: int | None
    cambiados: tuple[NumeroCapitulo, ...]
    portada: Portada
    capitulos: Annotated[
        tuple[CapituloLectura, ...],
        Field(min_length=NUMERO_CAPITULOS, max_length=NUMERO_CAPITULOS),
    ]
    personajes: tuple[PersonajeLectura, ...]
    lugares: tuple[LugarLectura, ...]


class VersionPublicada(_Modelo):
    version: Annotated[int, Field(ge=1)]
    publicada: str
    cambiados: tuple[NumeroCapitulo, ...]


class Versiones(_Modelo):
    """RF-96: `GET /proyectos/{id}/versiones`, ascendentes; la última es la vigente."""

    versiones: tuple[VersionPublicada, ...]


class CapituloDeVersion(_Modelo):
    """`GET /versiones/{v}/capitulos/{n}` de plan-frontend §5.1."""

    numero: NumeroCapitulo
    titulo: str | None
    html: str
