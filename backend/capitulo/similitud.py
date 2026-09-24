"""Recuperación por similitud del Recuperador (RF-50b, RF-57, RF-59, architecture §6.3).

Interfaz estrecha: entra una `Consulta` derivada de la ficha, sale una tupla ordenada de
`Fragmento`. En la v1 devuelve **siempre la tupla vacía** hasta que se decida D-1 (RF-57):
es el caso vacío de su contrato, válido, que no emite encabezado ni cuenta como recorte
(RF-50c). Cuando llegue el índice, cambia solo este módulo.
"""

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass

from backend.escaleta.modelos import FichaCapitulo


@dataclass(frozen=True)
class Consulta:
    """RF-59: el texto sale de los hitos y las escenas de la ficha; los filtros son duros y
    `antes_de` es un número de capítulo, no un orden de escritura."""

    texto: str
    presentes: tuple[str, ...]
    localizacion: str
    antes_de: int


@dataclass(frozen=True)
class Fragmento:
    capitulo: int
    posicion: int
    puntuacion: float
    texto: str


def consulta_de_ficha(ficha: FichaCapitulo) -> Consulta:
    texto = "\n".join([*(str(h) for h in ficha.hitos), *(e.texto for e in ficha.escenas)])
    return Consulta(texto, tuple(ficha.presentes), ficha.localizacion, ficha.numero)


def ordenar(fragmentos: Iterable[Fragmento]) -> tuple[Fragmento, ...]:
    """RF-50b: desempate explícito y estable: puntuación, capítulo y posición."""
    return tuple(sorted(fragmentos, key=lambda f: (-f.puntuacion, f.capitulo, f.posicion)))


def buscar(conexion: sqlite3.Connection, consulta: Consulta) -> tuple[Fragmento, ...]:
    """RF-57: siempre vacío en la v1 (D-1 sin decidir)."""
    return ()
