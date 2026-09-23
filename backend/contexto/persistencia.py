"""RF-28: persistir el contexto validado con la versión de ontología con que se validó."""

import sqlite3

from backend.contexto.modelos import Contexto
from backend.contexto.validacion import InformeContexto


class ContextoInvalido(ValueError):
    """RF-22: un contexto con hallazgos no se persiste como validado."""


def guardar_contexto(conexion: sqlite3.Connection, informe: InformeContexto, momento: str) -> int:
    if not informe.valido or informe.contexto is None:
        raise ContextoInvalido(f"{len(informe.hallazgos)} hallazgos bloqueantes")
    fila = conexion.execute(
        "INSERT INTO contexto (version_ontologia, contenido, validado) VALUES (?, ?, ?) "
        "RETURNING id",
        (informe.version_ontologia, informe.contexto.model_dump_json(), momento),
    ).fetchone()
    return int(fila["id"])


def contexto_vigente(conexion: sqlite3.Connection) -> tuple[str, Contexto] | None:
    """El último contexto validado y su versión de ontología."""
    fila = conexion.execute(
        "SELECT version_ontologia, contenido FROM contexto ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if fila is None:
        return None
    return fila["version_ontologia"], Contexto.model_validate_json(fila["contenido"])
