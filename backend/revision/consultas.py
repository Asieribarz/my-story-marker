"""Acceso a datos de `revision`: lectura de `informe_juez` agrupada por evaluación (RF-114).

La escritura es la misma que la del juez (`verificacion.consultas.guardar_evaluacion`).
"""

import sqlite3
from typing import Any

from backend.verificacion.modelos import aprueba


def siguiente_evaluacion_humana(conexion: sqlite3.Connection) -> str:
    fila = conexion.execute(
        "SELECT count(DISTINCT evaluacion) AS n FROM informe_juez WHERE revisor = 'humano'"
    ).fetchone()
    return f"humano-{int(fila['n']) + 1}"


def evaluaciones(conexion: sqlite3.Connection) -> list[dict[str, Any]]:
    """Cada evaluación con sus cinco puntuaciones y justificaciones, su suma y si pasaría
    el umbral de TC-5."""
    agrupadas: dict[str, dict[str, Any]] = {}
    for f in conexion.execute(
        "SELECT * FROM informe_juez ORDER BY version_novela, momento, evaluacion, criterio"
    ):
        e = agrupadas.setdefault(
            f["evaluacion"],
            {
                "evaluacion": f["evaluacion"],
                "revisor": f["revisor"],
                "version_novela": f["version_novela"],
                "ciclo": f["ciclo"],
                "puntuaciones": {},
                "justificaciones": {},
                "momento": f["momento"],
            },
        )
        e["puntuaciones"][f["criterio"]] = int(f["puntuacion"])
        e["justificaciones"][f["criterio"]] = f["justificacion"]
    for e in agrupadas.values():
        e["suma"] = sum(e["puntuaciones"].values())
        e["aprobaria"] = aprueba(e["puntuaciones"].values())
    return list(agrupadas.values())
