"""Esquemas de salida de los agentes de `capitulo/` (RF-77a, V-35).

- Escritor, Editor de estilo y Revisor devuelven Markdown (§4.1.3): `# título` y el texto.
  `capitulo_de_markdown` lo convierte en `SalidaCapitulo {titulo, texto}`.
- Juez de capítulo (B-15): un juicio por criterio, `{criterio, cumple, hallazgos[{parrafo,
  cita, motivo}]}`. La severidad la pone el backend (`SEVERIDAD_DEL_CRITERIO`, architecture
  §4). Es inválida si falta o se repite un criterio, si `cumple` no cuadra con sus hallazgos
  o si una cita no está en el texto (`citas_ausentes`).
- Bibliotecario (B-16): casi vacía, `{registrado: {...}}` con el recuento; lo que cuenta es
  lo escrito por `/mcp/escritura`, que se comprueba con `pendiente_del_bibliotecario`.
"""

from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.capitulo import segmentacion as seg
from backend.capitulo.verificadores.nombres import literal
from backend.shared.tipos import Severidad

_NoVacio = Annotated[str, Field(min_length=1)]


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class SalidaCapitulo(_Modelo):
    titulo: _NoVacio
    texto: _NoVacio

    @property
    def markdown(self) -> str:
        return f"# {self.titulo}\n\n{self.texto}\n"


def capitulo_de_markdown(salida: object) -> SalidaCapitulo:
    """`ValueError` (o `ValidationError`, que lo es) si no es texto, si la primera línea no es
    un encabezado `#` o si no hay texto debajo."""
    if not isinstance(salida, str):
        raise ValueError("(raíz): se esperaba el Markdown del capítulo")
    titulo, cuerpo = seg.separar_titulo(salida)
    if titulo is None:
        raise ValueError("(raíz): la primera línea tiene que ser el título, `# …`")
    if not seg.parrafos(cuerpo):
        raise ValueError("texto: el capítulo no tiene ningún párrafo")
    return SalidaCapitulo(titulo=titulo, texto=cuerpo)


class CriterioJuez(StrEnum):
    HITO = "hito"
    COHERENCIA = "coherencia"
    VOZ = "voz"
    CONTENIDO = "contenido"


# architecture §4; `contenido` en alta por B-15.
SEVERIDAD_DEL_CRITERIO = {
    CriterioJuez.HITO: Severidad.ALTA,
    CriterioJuez.COHERENCIA: Severidad.ALTA,
    CriterioJuez.VOZ: Severidad.MEDIA,
    CriterioJuez.CONTENIDO: Severidad.ALTA,
}


class HallazgoJuez(_Modelo):
    parrafo: Annotated[int, Field(ge=1)]
    cita: _NoVacio
    motivo: _NoVacio


class Juicio(_Modelo):
    criterio: CriterioJuez
    cumple: bool
    hallazgos: tuple[HallazgoJuez, ...] = ()

    @model_validator(mode="after")
    def _cuadra(self) -> "Juicio":
        if self.cumple == bool(self.hallazgos):
            raise ValueError("`cumple` es verdadero si y solo si no hay hallazgos")
        return self


class SalidaJuez(_Modelo):
    criterios: tuple[Juicio, ...]

    @model_validator(mode="after")
    def _uno_por_criterio(self) -> "SalidaJuez":
        vistos = [j.criterio for j in self.criterios]
        if sorted(vistos) != sorted(CriterioJuez):
            raise ValueError(f"un juicio por criterio: {', '.join(CriterioJuez)}")
        return self


def citas_ausentes(salida: SalidaJuez, cuerpo: str) -> list[str]:
    """B-15: cada cita tiene que estar en el texto, y su párrafo, existir."""
    parrafos = seg.parrafos(cuerpo)
    texto = literal(" ".join(p.texto for p in parrafos))
    errores = []
    for juicio in salida.criterios:
        for i, h in enumerate(juicio.hallazgos):
            donde = f"criterios.{juicio.criterio.value}.hallazgos.{i}"
            if h.parrafo > len(parrafos):
                errores.append(f"{donde}.parrafo: el capítulo tiene {len(parrafos)} párrafos")
            if literal(h.cita) not in texto:
                errores.append(f"{donde}.cita: no aparece en el texto")
    return errores


class SalidaBibliotecario(_Modelo):
    registrado: dict[str, Any]
