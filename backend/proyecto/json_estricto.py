"""JSON estricto (RFC 8259): lo que la base puede guardar y el `json` de Python deja pasar.

`json.loads` acepta `NaN`, `Infinity` y `-Infinity`, que no son JSON, y los escapes de un
sustituto suelto (`"\\ud800"`), que dan una cadena que no se puede codificar en UTF-8. Los dos
llegan hasta la base y rompen allí: el `CHECK (json_valid(...))` rechaza el número, y
`sqlite3` no puede codificar la cadena. Aquí se detectan antes:

- En la API, `cargar` sustituye al `json.loads` del cuerpo de la petición (la clase de ruta
  de `dependencias.py`): un cuerpo así es un error de validación, 422.
- En el registro de resultados, `infraccion` mira la salida del agente: fuera de JSON estricto
  es un intento fallido de forma, no un error de la petición (RF-77a, TC-11). Por eso
  `/resultado` lee su cuerpo sin la restricción.
"""

import json
import math
from typing import Any

_NO_ES_JSON = "NaN, Infinity y -Infinity no son JSON según la RFC 8259"
_SUSTITUTO = "una cadena con un carácter sustituto suelto no es texto UTF-8"


def infraccion(valor: object) -> str | None:
    """Por qué `valor` no es JSON estricto, o `None` si lo es. Sin repetir el valor: puede
    ser un dato excluido (RF-13). Recorre sin recursión, sea cual sea la profundidad."""
    pendientes: list[object] = [valor]
    while pendientes:
        actual = pendientes.pop()
        if isinstance(actual, str):
            if not _codificable(actual):
                return _SUSTITUTO
        elif isinstance(actual, float):
            if not math.isfinite(actual):
                return _NO_ES_JSON
        elif isinstance(actual, dict):
            pendientes.extend(actual.keys())
            pendientes.extend(actual.values())
        elif isinstance(actual, list | tuple):
            pendientes.extend(actual)
    return None


def _codificable(texto: str) -> bool:
    try:
        texto.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _rechazar_constante(nombre: str) -> Any:
    raise json.JSONDecodeError(_NO_ES_JSON, nombre, 0)


def cargar(cuerpo: bytes | str) -> Any:
    """`json.loads` en estricto. Lo que no es JSON estricto da `json.JSONDecodeError`, la
    misma excepción que un JSON mal formado, para que quien llama lo trate igual."""
    valor = json.loads(cuerpo, parse_constant=_rechazar_constante)
    motivo = infraccion(valor)
    if motivo is not None:
        raise json.JSONDecodeError(motivo, "", 0)
    return valor
