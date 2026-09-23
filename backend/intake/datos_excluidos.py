"""RF-13 y C-8: los datos personales que la novela no necesita se descartan siempre.

Se descartan sin rechazar el brief, y cada descarte se registra con el tipo de dato y la
ruta del campo, **nunca con el valor**. Dos detectores:

- Por clave: una respuesta de la entrevista cuya clave nombra un dato excluido.
- Por forma: un valor con la forma de un email, un teléfono, un documento de identidad,
  un IBAN o una tarjeta.

Límite declarado: la dirección exacta y los datos de salud escritos en prosa no tienen una
forma reconocible; ahí la defensa es el esquema cerrado del Extractor y el red teaming
de V-29, no este módulo.
"""

import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

# Tipos de dato excluido de definitions.md §9, y las claves que los nombran.
CLAVES_EXCLUIDAS: dict[str, frozenset[str]] = {
    "documento_identidad": frozenset(
        {"dni", "nie", "nif", "pasaporte", "documento", "documento_identidad"}
    ),
    "telefono": frozenset({"telefono", "movil", "celular", "tel", "whatsapp"}),
    "email": frozenset({"email", "correo", "correo_electronico", "mail", "e_mail"}),
    "direccion": frozenset({"direccion", "domicilio", "calle", "codigo_postal", "cp"}),
    "datos_bancarios": frozenset(
        {"iban", "cuenta", "cuenta_bancaria", "tarjeta", "numero_tarjeta", "banco"}
    ),
    "salud": frozenset(
        {
            "salud",
            "enfermedad",
            "diagnostico",
            "alergia",
            "alergias",
            "medicacion",
            "tratamiento_medico",
        }
    ),
}

FORMAS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+"),
    "documento_identidad": re.compile(r"\b(\d{8}|[XYZxyz]\d{7})[- ]?[A-Za-z]\b"),
    "datos_bancarios": re.compile(
        r"\b[A-Z]{2}\d{2}(?: ?[0-9A-Z]{4}){4,7}\b|\b(?:\d[ -]?){13,19}\b"
    ),
    # Nueve cifras españolas en grupos 3-3-3 o 3-2-2-2, con o sin prefijo +34.
    "telefono": re.compile(
        r"(?<![\w+])(?:\+34[ -]?)?[6789]\d{2}(?:(?:[ -]?\d{3}){2}|(?:[ -]?\d{2}){3})(?![\w])"
    ),
}


@dataclass(frozen=True)
class Descarte:
    """Lo que se audita: tipo de dato y ruta del campo. El valor no viaja aquí."""

    tipo: str
    campo: str


def _normalizar_clave(clave: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", clave).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", sin_acentos.lower()).strip("_")


def tipo_por_clave(clave: str) -> str | None:
    normalizada = _normalizar_clave(clave)
    for tipo, claves in CLAVES_EXCLUIDAS.items():
        if normalizada in claves:
            return tipo
    return None


def tipo_por_forma(texto: str) -> str | None:
    for tipo, patron in FORMAS.items():
        if patron.search(texto):
            return tipo
    return None


def depurar(valor: Any, ruta: str = "") -> tuple[Any, list[Descarte]]:
    """Devuelve una copia sin los datos excluidos y la lista de descartes.

    Un campo con un dato excluido se elimina entero, no se enmascara: un teléfono a medio
    borrar sigue siendo un dato que la novela no necesita.
    """
    descartes: list[Descarte] = []
    if isinstance(valor, dict):
        limpio: dict[Any, Any] = {}
        for clave, hijo in valor.items():
            campo = f"{ruta}.{clave}" if ruta else str(clave)
            tipo = tipo_por_clave(str(clave)) or tipo_por_forma(str(clave))
            if tipo is not None:
                descartes.append(Descarte(tipo, campo))
                continue
            depurado, suyos = depurar(hijo, campo)
            descartes.extend(suyos)
            if depurado is not _DESCARTADO:
                limpio[clave] = depurado
        return limpio, descartes
    if isinstance(valor, list):
        lista = []
        for i, hijo in enumerate(valor):
            depurado, suyos = depurar(hijo, f"{ruta}.{i}" if ruta else str(i))
            descartes.extend(suyos)
            if depurado is not _DESCARTADO:
                lista.append(depurado)
        return lista, descartes
    if isinstance(valor, str):
        tipo = tipo_por_forma(valor)
        if tipo is not None:
            return _DESCARTADO, [Descarte(tipo, ruta or "(raíz)")]
    return valor, descartes


class _Descartado:
    def __repr__(self) -> str:
        return "<descartado>"


_DESCARTADO: Any = _Descartado()


def descartes_de_texto(texto: str, campo: str) -> Iterator[Descarte]:
    tipo = tipo_por_forma(texto)
    if tipo is not None:
        yield Descarte(tipo, campo)
