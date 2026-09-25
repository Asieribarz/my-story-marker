"""Segmentación única del texto de un capítulo (B-14): párrafo, frase, palabra y diálogo.

**Párrafo** es un bloque del Markdown del capítulo separado por una línea en blanco, sin
contar el título (`# …`) ni el separador de escena (una línea de tres o más `*`, `-` o `_`).
Se numeran desde 1: son el `p<n>` de los hallazgos, el `data-p` del frontend y el `parrafo`
del juez. Un hallazgo se localiza como `p<n>:<offset>`, con el offset en caracteres dentro
del párrafo. Todos los verificadores segmentan con este módulo y con nada más.
"""

import re
from dataclasses import dataclass
from typing import Literal

_BLOQUES = re.compile(r"\n[ \t]*\n")
_SEPARADOR = re.compile(r"(?:[*\-_][ \t]*){3,}")
_TITULO = re.compile(r"#[ \t]+(\S.*)")
_PALABRA = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*|\d+(?:[.,]\d+)*")
_FIN_DE_FRASE = re.compile(r"[.!?…]+[»”\"')\]]*(?=\s)")
_RAYA = "—"
_COMILLAS = re.compile(r"«[^»]*»|“[^”]*”|\"[^\"]*\"")

# Una abreviatura con punto no cierra frase (B-14). Se comparan en minúsculas y sin punto.
ABREVIATURAS = frozenset(
    {"sr", "sra", "srta", "sres", "dr", "dra", "d", "dña", "ud", "uds", "vd", "vds", "st"}
    | {"sto", "sta", "núm", "pág", "cap", "aprox", "p", "ej", "av", "avda", "c", "prof"}
)


@dataclass(frozen=True)
class Parrafo:
    numero: int
    texto: str


@dataclass(frozen=True)
class Palabra:
    parrafo: int
    inicio: int
    texto: str


@dataclass(frozen=True)
class Frase:
    parrafo: int
    inicio: int
    texto: str


def separar_titulo(markdown: str) -> tuple[str | None, str]:
    """El título del encabezado `#` de la primera línea con texto, y el cuerpo sin él."""
    lineas = markdown.replace("\r\n", "\n").strip("\n").split("\n")
    while lineas and not lineas[0].strip():
        lineas.pop(0)
    if lineas:
        cabecera = _TITULO.fullmatch(lineas[0].strip())
        if cabecera:
            return cabecera.group(1).strip(), "\n".join(lineas[1:]).strip("\n")
    return None, "\n".join(lineas)


def parrafos(cuerpo: str) -> tuple[Parrafo, ...]:
    """Los párrafos del cuerpo, desde 1. Un título que quede dentro tampoco cuenta."""
    bloques = (b.strip() for b in _BLOQUES.split(cuerpo.replace("\r\n", "\n")))
    utiles = [b for b in bloques if b and not _SEPARADOR.fullmatch(b) and not _TITULO.fullmatch(b)]
    return tuple(Parrafo(n, " ".join(b.split())) for n, b in enumerate(utiles, start=1))


def palabras(parrafo: Parrafo) -> tuple[Palabra, ...]:
    return tuple(
        Palabra(parrafo.numero, m.start(), m.group()) for m in _PALABRA.finditer(parrafo.texto)
    )


def tokens(texto: str) -> list[str]:
    return _PALABRA.findall(texto)


def contar_palabras(texto: str) -> int:
    return len(_PALABRA.findall(texto))


def frases(parrafo: Parrafo) -> tuple[Frase, ...]:
    """Frases del párrafo. Un signo de cierre no corta tras una abreviatura, ni si lo que
    sigue empieza en minúscula (el inciso de «—¿Vienes? —preguntó»)."""
    texto = parrafo.texto
    resultado: list[Frase] = []
    inicio = 0
    for cierre in _FIN_DE_FRASE.finditer(texto):
        previa = texto[inicio : cierre.start()].split()
        ultima = previa[-1].lower() if previa else ""
        if cierre.group().startswith(".") and ultima.strip('(«"') in ABREVIATURAS:
            continue
        resto = texto[cierre.end() :].lstrip()
        siguiente = resto.lstrip(_RAYA + "–")[:1]
        if siguiente.islower():
            continue
        resultado.append(Frase(parrafo.numero, inicio, texto[inicio : cierre.end()].strip()))
        inicio = cierre.end() + (len(texto) - cierre.end() - len(resto))
    if texto[inicio:].strip():
        resultado.append(Frase(parrafo.numero, inicio, texto[inicio:].strip()))
    return tuple(resultado)


def dialogo(parrafo: Parrafo, convencion: Literal["raya", "comillas"]) -> tuple[str, ...]:
    """Los fragmentos de diálogo del párrafo según la convención del contexto. Con raya, el
    párrafo empieza por `—` y los incisos del narrador van entre rayas; con comillas, lo
    que va entre «», “” o ""."""
    texto = parrafo.texto
    if convencion == "comillas":
        return tuple(m.group()[1:-1] for m in _COMILLAS.finditer(texto))
    if not texto.startswith(_RAYA):
        return ()
    return tuple(t for i, t in enumerate(texto.split(_RAYA)) if i % 2 == 1 and t.strip())


def localizacion(parrafo: int, offset: int) -> str:
    return f"p{parrafo}:{offset}"
