"""Estimador conservador de tokens de entrada (RF-52 a RF-52c, architecture §6.3, D-5).

Interfaz estrecha: `estimar_tokens(texto) -> int`. Es `o200k_base` × 1,35 (`FACTOR`,
redondeado hacia arriba), la única función que el resto de la cadena llama. El factor vive
aquí y en ningún otro sitio: el tope de 100.000 no se baja para dejar margen (RF-52b).

Dos caminos para contar `o200k_base`, sobre **el mismo fichero** versionado en
`backend/capitulo/bpe/` y sin red (RF-52c):

1. **`tiktoken`**, si carga. `TIKTOKEN_CACHE_DIR` apunta a `bpe/`, donde el fichero se llama
   como tiktoken lo busca (SHA-1 de su URL) y conserva su SHA-256 (`.gitattributes`).
2. **Respaldo en Python puro**, si `import tiktoken` falla. Existe porque en la máquina de
   desarrollo una directiva de Control de aplicaciones de Windows bloquea la DLL nativa de
   tiktoken (decidido con la persona: no se salta la política). Lee el mismo `.tiktoken`
   (base64 del token y rango por línea), pre-tokeniza con el patrón de `o200k_base` y fusiona
   por rango como `tiktoken` (la pareja adyacente de menor rango, la de más a la izquierda en
   caso de empate), con caché por pre-token. Fidelidad:
   - con el paquete `regex` (dependencia de tiktoken; se usa solo si importa sin error), el
     patrón es el de tiktoken literalmente;
   - si no, con `re`: las clases `\\p{..}` no son expresables y se generan desde
     `unicodedata` recorriendo los puntos de código (misma partición por categoría; solo
     cambia la versión de Unicode de la tabla). `\\s` es el de `re` (`str.isspace`, que
     además incluye U+001C a U+001F). Medido contra `regex` sobre texto español, JSON y
     Markdown: mismas pre-divisiones (`tests/test_estimador.py`);
   - un pre-token de más de `_PIEZA_LARGA` bytes (una tira de espacios o de signos) no se
     fusiona: cuenta un token por byte, que es una cota superior. Nunca infracuenta.
   La paridad con tiktoken (`respaldo == tiktoken`) se prueba donde tiktoken carga.
"""

import base64
import math
import os
import unicodedata
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any

FACTOR = 1.35
DIRECTORIO_BPE = Path(__file__).resolve().parent / "bpe"
FICHERO_O200K = DIRECTORIO_BPE / "fb374d419588a4632f3f557e76b4b70aebbca790"
_PIEZA_LARGA = 256

# El patrón de pre-tokenización de o200k_base, tal cual lo define tiktoken_ext.openai_public.
PATRON_O200K = "|".join(
    [
        r"""[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]*[\p{Ll}\p{Lm}\p{Lo}\p{M}]+(?i:'s|'t|'re|'ve|'m|'ll|'d)?""",
        r"""[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]+[\p{Ll}\p{Lm}\p{Lo}\p{M}]*(?i:'s|'t|'re|'ve|'m|'ll|'d)?""",
        r"""\p{N}{1,3}""",
        r""" ?[^\s\p{L}\p{N}]+[\r\n/]*""",
        r"""\s*[\r\n]+""",
        r"""\s+(?!\S)""",
        r"""\s+""",
    ]
)


def estimar_tokens(texto: str) -> int:
    """RF-52a: tokens de `texto` según o200k_base, multiplicados por `FACTOR` y
    redondeados hacia arriba. Determinista y sin red."""
    return math.ceil(_contador()[1](texto) * FACTOR)


def motor() -> str:
    """Qué cuenta: `tiktoken`, `respaldo-regex` o `respaldo-re` (va en el desglose)."""
    return _contador()[0]


@cache
def _contador() -> tuple[str, Callable[[str], int]]:
    try:
        return "tiktoken", contador_tiktoken()
    except ImportError:
        return _respaldo()


def contador_tiktoken() -> Callable[[str], int]:
    """ImportError si la DLL de tiktoken no carga."""
    os.environ["TIKTOKEN_CACHE_DIR"] = str(DIRECTORIO_BPE)
    import tiktoken

    codificacion = tiktoken.get_encoding("o200k_base")
    return lambda texto: len(codificacion.encode_ordinary(texto))


# ─── Respaldo en Python puro ─────────────────────────────────────────────────


@cache
def rangos() -> dict[bytes, int]:
    """El fichero .tiktoken: una línea por token, `base64 rango`."""
    resultado: dict[bytes, int] = {}
    for linea in FICHERO_O200K.read_bytes().splitlines():
        if linea:
            token, rango = linea.split()
            resultado[base64.b64decode(token)] = int(rango)
    return resultado


def contar_pieza(pieza: bytes, tabla: dict[bytes, int]) -> int:
    """Fusión BPE por rango, como `tiktoken._byte_pair_merge`; devuelve cuántos tokens."""
    if pieza in tabla:
        return 1
    if len(pieza) > _PIEZA_LARGA:
        return len(pieza)
    partes = [pieza[i : i + 1] for i in range(len(pieza))]
    while len(partes) > 1:
        mejor, indice = None, -1
        for i in range(len(partes) - 1):
            rango = tabla.get(partes[i] + partes[i + 1])
            if rango is not None and (mejor is None or rango < mejor):
                mejor, indice = rango, i
        if mejor is None:
            break
        partes[indice : indice + 2] = [partes[indice] + partes[indice + 1]]
    return len(partes)


def patron_con_re() -> Any:
    """El patrón para `re`: cada `\\p{..}` sustituido por su clase generada."""
    import re

    return re.compile(_traducir(PATRON_O200K, _clases_unicode()))


def patron_con_regex() -> Any:
    import regex  # type: ignore[import-untyped]  # dependencia de tiktoken

    return regex.compile(PATRON_O200K)


def _respaldo() -> tuple[str, Callable[[str], int]]:
    try:
        nombre, patron = "respaldo-regex", patron_con_regex()
    except ImportError:
        nombre, patron = "respaldo-re", patron_con_re()
    return nombre, contador_respaldo(patron)


def contador_respaldo(patron: Any) -> Callable[[str], int]:
    """Cuenta con `patron` (de `regex` o de `re`) y la tabla de rangos, con caché."""
    tabla = rangos()
    memoria: dict[str, int] = {}

    def contar(texto: str) -> int:
        total = 0
        for pieza in patron.findall(texto):
            cuenta = memoria.get(pieza)
            if cuenta is None:
                cuenta = memoria[pieza] = contar_pieza(pieza.encode("utf-8"), tabla)
            total += cuenta
        return total

    return contar


def _clases_unicode() -> dict[str, str]:
    """Rangos de puntos de código por categoría general, en sintaxis de clase de `re`."""
    por_categoria: dict[str, list[int]] = {}
    for punto in range(0x110000):
        por_categoria.setdefault(unicodedata.category(chr(punto)), []).append(punto)

    def clase(*categorias: str) -> str:
        puntos = sorted(p for c, lista in por_categoria.items() if c in categorias for p in lista)
        trozos, i = [], 0
        while i < len(puntos):
            j = i
            while j + 1 < len(puntos) and puntos[j + 1] == puntos[j] + 1:
                j += 1
            trozos.append(f"\\U{puntos[i]:08x}-\\U{puntos[j]:08x}")
            i = j + 1
        return "".join(trozos)

    marcas = ("Mn", "Mc", "Me")
    return {
        r"\p{L}": clase("Lu", "Ll", "Lt", "Lm", "Lo"),
        r"\p{N}": clase("Nd", "Nl", "No"),
        r"\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}": clase("Lu", "Lt", "Lm", "Lo", *marcas),
        r"\p{Ll}\p{Lm}\p{Lo}\p{M}": clase("Ll", "Lm", "Lo", *marcas),
    }


def _traducir(patron: str, clases: dict[str, str]) -> str:
    # Primero las combinaciones largas, para que `\p{L}` no se coma el principio de `\p{Lu}`.
    for clave in sorted(clases, key=len, reverse=True):
        patron = patron.replace(clave, clases[clave])
    # `\p{N}{1,3}` fuera de corchetes: tras sustituir queda un rango suelto; se encierra.
    patron = patron.replace(clases[r"\p{N}"] + "{1,3}", "[" + clases[r"\p{N}"] + "]{1,3}")
    return patron
