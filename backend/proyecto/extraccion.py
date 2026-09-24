"""Extracción de la salida cruda de un subagente (spec-backend-2 §4.1, puntos 3 y 7).

El hook de `SubagentStop` envía `last_assistant_message` sin tocarlo, y aquí, en un solo
sitio, se saca lo que el manejador del agente valida después (RF-77a):

- La primera línea no vacía puede repetir el sello como `orden: <sello>`. Es opcional: si
  viene, se quita; si no viene, no es un fallo. El sello que manda es el del cuerpo de
  `/resultado`, que el harness saca del prompt que envió, no de lo que devuelve el modelo.
- Escritor, Editor y Revisor devuelven Markdown: `# título` en la primera línea y el texto
  después. El manejador recibe ese Markdown como `str`, sin la línea del sello. Si el texto
  trae la línea `<!-- fin del capítulo -->`, el capítulo acaba ahí: lo que venga detrás —notas
  del modelo, un resumen de lo que hizo— se descarta, porque si no se publicaría como prosa.
- El resto devuelve un único bloque JSON delimitado (```json … ```, o ``` … ```), que se lee
  en JSON estricto. Sin delimitadores vale si el texto entero es JSON.

Lo que no encaja da `SalidaMalFormada`: un fallo de forma que gasta intento, con los errores
en el informe y sin repetir el valor recibido, que puede ser un dato excluido (RF-13).
"""

import json
import re
from dataclasses import dataclass

from backend.proyecto import json_estricto
from backend.shared.tipos import Agente

AGENTES_MARKDOWN = frozenset({Agente.ESCRITOR, Agente.EDITOR_ESTILO, Agente.REVISOR})

_SELLO = re.compile(r"orden:\s*(\S+)")
_TITULO = re.compile(r"#[ \t]+\S.*")
_FIN_CAPITULO = re.compile(
    r"^[ \t]*<!--\s*fin del cap[ií]tulo\s*-->[ \t]*$", re.MULTILINE | re.IGNORECASE
)
_BLOQUE = re.compile(r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n?[ \t]*```", re.DOTALL | re.IGNORECASE)


class SalidaMalFormada(ValueError):
    """RF-77a: la salida cruda no tiene la forma que exige su agente."""

    def __init__(self, error: str) -> None:
        super().__init__(error)
        self.errores = [f"(raíz): {error}"]


@dataclass(frozen=True)
class Extraida:
    """El valor que recibe el manejador y el sello que repitió el subagente, si lo hizo."""

    valor: object
    sello: str | None = None


def _sin_sello(texto: str) -> tuple[str, str | None]:
    lineas = texto.strip().splitlines()
    if lineas:
        repetido = _SELLO.fullmatch(lineas[0].strip())
        if repetido is not None:
            return "\n".join(lineas[1:]).strip(), repetido[1]
    return texto.strip(), None


def _markdown(cuerpo: str) -> str:
    fin = _FIN_CAPITULO.search(cuerpo)
    if fin is not None:
        cuerpo = cuerpo[: fin.start()].rstrip()
    lineas = cuerpo.splitlines()
    if not lineas or _TITULO.fullmatch(lineas[0].strip()) is None:
        raise SalidaMalFormada("se esperaba Markdown con `# título` en la primera línea")
    if not "\n".join(lineas[1:]).strip():
        raise SalidaMalFormada("el Markdown no trae texto después del título")
    return cuerpo


def _json(cuerpo: str) -> object:
    bloques = _BLOQUE.findall(cuerpo)
    if len(bloques) > 1:
        raise SalidaMalFormada(f"hay {len(bloques)} bloques delimitados; se espera uno solo")
    fuente = bloques[0] if bloques else cuerpo
    try:
        return json_estricto.cargar(fuente)
    except json.JSONDecodeError as error:
        if not bloques:
            raise SalidaMalFormada("se esperaba un único bloque JSON delimitado") from None
        raise SalidaMalFormada(f"el bloque no es JSON estricto: {error.msg}") from None


def extraer(agente: Agente, salida_cruda: str) -> Extraida:
    """El valor de la salida de `agente` para su manejador, o `SalidaMalFormada`."""
    motivo = json_estricto.infraccion(salida_cruda)
    if motivo is not None:
        raise SalidaMalFormada(motivo)
    cuerpo, sello = _sin_sello(salida_cruda)
    if not cuerpo:
        raise SalidaMalFormada("la salida está vacía")
    valor = _markdown(cuerpo) if agente in AGENTES_MARKDOWN else _json(cuerpo)
    return Extraida(valor, sello)
