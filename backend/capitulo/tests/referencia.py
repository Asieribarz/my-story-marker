"""La biblia de referencia: contexto, plan y escaleta de referencia ya guardados.

Para las pruebas de `capitulo/` (biblia, Recuperador, verificadores): parte de datos
ficticios y pasa por el camino real —validar, materializar (B-1), guardar la planificación
y la escaleta—. `verificar` pone capítulos en `verificado` con una versión, para escribir
como el Bibliotecario.
"""

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from backend.contexto.persistencia import guardar_contexto
from backend.contexto.tests.referencia import HOY, referencia
from backend.contexto.validacion import validar
from backend.escaleta.consultas import guardar_escaleta
from backend.escaleta.modelos import SalidaEscaletista
from backend.escaleta.tests.referencia import salida_escaletista
from backend.planificacion.consultas import guardar_planificacion
from backend.planificacion.materializar import materializar_contexto
from backend.planificacion.modelos import SalidaPlanificador
from backend.planificacion.tests.referencia import salida_planificador
from backend.shared.db import crear_base

MOMENTO = "2026-09-23T10:00:00Z"


def biblia_de_referencia(ruta: Path, contexto: dict[str, Any] | None = None) -> sqlite3.Connection:
    """Crea la base en `ruta` con todo guardado hasta la escaleta. `contexto` sustituye al de
    referencia (por ejemplo, con un `excluye`); tiene que seguir siendo válido."""
    conexion = crear_base(ruta)
    informe = validar(contexto if contexto is not None else referencia(), date.fromisoformat(HOY))
    assert informe.contexto is not None, informe.hallazgos
    guardar_contexto(conexion, informe, MOMENTO)
    materializar_contexto(conexion, informe.contexto, MOMENTO)
    guardar_planificacion(conexion, SalidaPlanificador.model_validate(salida_planificador()))
    guardar_escaleta(conexion, SalidaEscaletista.model_validate(salida_escaletista()))
    conexion.executemany("INSERT INTO capitulo (numero) VALUES (?)", [(n,) for n in range(1, 11)])
    return conexion


def verificar(conexion: sqlite3.Connection, *capitulos: int) -> None:
    """Cada capítulo, en `verificado` con su versión 1, intento 1."""
    for numero in capitulos:
        conexion.execute("UPDATE capitulo SET estado = 'verificado' WHERE numero = ?", (numero,))
        conexion.execute(
            "INSERT INTO capitulo_version (capitulo, version, intento, estado, ruta, creado) "
            "VALUES (?, 1, 1, 'verificado', ?, ?)",
            (numero, f"capitulos/cap-{numero:02d}/v1-intento1.md", MOMENTO),
        )
