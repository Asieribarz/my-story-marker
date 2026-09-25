"""Un proyecto abierto: su disposición en disco y su conexión, derivadas del identificador.

Toda función pública de `proyecto/` recibe un `Proyecto`, así que ninguna puede apuntar a
un proyecto distinto del que la petición identifica (V-24). El tiempo entra siempre como
parámetro (`ahora`), nunca se lee del reloj dentro de la lógica.
"""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

from backend.proyecto.errores import ProyectoInexistente
from backend.shared.db import conectar
from backend.shared.rutas import DisposicionProyecto


@dataclass(frozen=True)
class Proyecto:
    disposicion: DisposicionProyecto
    conexion: sqlite3.Connection

    @property
    def identificador(self) -> str:
        return self.disposicion.identificador

    def cerrar(self) -> None:
        self.conexion.close()

    def __enter__(self) -> "Proyecto":
        return self

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        self.cerrar()


def abrir_proyecto(identificador: str, raiz_proyectos: Path | None = None) -> Proyecto:
    """Abre un proyecto existente. Un identificador mal formado da `IdentificadorInvalido`
    (de `shared/rutas.py`); uno bien formado sin base, `ProyectoInexistente`."""
    disposicion = DisposicionProyecto.de(identificador, raiz_proyectos)
    if not disposicion.base.is_file():
        raise ProyectoInexistente(identificador)
    conexion = conectar(disposicion.base)
    if conexion.execute("SELECT 1 FROM proyecto WHERE id = 1").fetchone() is None:
        conexion.close()
        raise ProyectoInexistente(identificador)
    return Proyecto(disposicion, conexion)


def instante(ahora: datetime) -> str:
    """El instante como se guarda: ISO-8601 en UTC, al segundo (convención de esquema.sql)."""
    if ahora.tzinfo is None:
        raise ValueError("el instante debe llevar zona horaria")
    return ahora.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def leer_instante(texto: str) -> datetime:
    return datetime.fromisoformat(texto)
