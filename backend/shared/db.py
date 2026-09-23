"""Fábrica de conexión a la base de un proyecto: los pragmas viven aquí y solo aquí.

Un `PRAGMA foreign_keys` olvidado no da error, solo filas huérfanas (architecture.md §8);
por eso ninguna otra parte de backend/ abre conexiones (V-24).
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

ESQUEMA = Path(__file__).resolve().parent / "esquema.sql"
ESPERA_OCUPADA_MS = 5000

_PRAGMAS = (
    "PRAGMA journal_mode = WAL",
    "PRAGMA foreign_keys = ON",
    f"PRAGMA busy_timeout = {ESPERA_OCUPADA_MS}",
    "PRAGMA synchronous = NORMAL",
)


def conectar(ruta: Path) -> sqlite3.Connection:
    """Abre la base con los pragmas puestos.

    `autocommit=True` deja las transacciones en manos de `transaccion()`, explícitas.
    `check_same_thread=False` porque FastAPI puede resolver la dependencia y ejecutar el
    endpoint en hilos distintos del threadpool; cada petición tiene su propia conexión.
    """
    conexion = sqlite3.connect(ruta, autocommit=True, check_same_thread=False)
    conexion.row_factory = sqlite3.Row
    for pragma in _PRAGMAS:
        conexion.execute(pragma)
    return conexion


@contextmanager
def transaccion(conexion: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Transacción de escritura: `BEGIN IMMEDIATE`, confirmada al salir o deshecha si falla.

    Empieza ya como escritura para que el ascenso de lectura a escritura no pueda fallar
    con `SQLITE_BUSY` a mitad, que `busy_timeout` no salva.
    """
    conexion.execute("BEGIN IMMEDIATE")
    try:
        yield conexion
    except BaseException:
        conexion.execute("ROLLBACK")
        raise
    conexion.execute("COMMIT")


def crear_base(ruta: Path) -> sqlite3.Connection:
    """Crea el fichero del proyecto con el esquema completo y devuelve la conexión."""
    if ruta.exists():
        raise FileExistsError(f"la base {ruta} ya existe")
    conexion = conectar(ruta)
    conexion.executescript(ESQUEMA.read_text(encoding="utf-8"))
    return conexion
