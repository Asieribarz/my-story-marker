"""Apoyo de las pruebas de `proyecto/`: reloj fijo, datos ficticios y acceso directo a la base.

Todos los datos de persona son ficticios, como en `backend/contexto/tests/referencia.py`.
`forzar` escribe el estado del grafo saltándose la máquina: sirve para colocar el proyecto
en una fase sin recorrer las anteriores, nunca para probar una transición.
"""

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.proyecto.abierto import Proyecto
from backend.shared.db import transaccion
from backend.shared.tipos import EstadoCapitulo, EstadoProyecto

AHORA = datetime(2026, 9, 23, 10, 0, tzinfo=UTC)
MOMENTO = "2026-09-23T10:00:00Z"
BRIEF: dict[str, Any] = {"destinatario": {"nombre": "Aitana", "edad": 9}, "ocasion": "cumpleanos"}
NORMALIZADO: dict[str, Any] = {"destinatario": {"nombre": "Aitana", "edad": 9}, "tono": "ligero"}
TEXTO_LIBRE = "Le encantan los mapas y su perra se llama Nala."
HECHO: dict[str, Any] = {
    "tipo": "objeto",
    "texto": "Una brújula del abuelo",
    "prioridad": "obligatorio",
}


def despues(minutos: int) -> datetime:
    return AHORA + timedelta(minutes=minutos)


def forzar(
    proyecto: Proyecto,
    estado: EstadoProyecto,
    *,
    detenida_desde: EstadoProyecto | None = None,
    intentos_paso: int = 0,
    ciclos_revision: int = 0,
    parada_plan: bool = False,
    parada_final: bool = False,
    capitulos: dict[int, tuple[EstadoCapitulo, int]] | None = None,
) -> None:
    with transaccion(proyecto.conexion) as conexion:
        conexion.execute(
            "UPDATE proyecto SET estado = ?, detenida_desde = ?, intentos_paso = ?, "
            "ciclos_revision = ?, parada_plan = ?, parada_final = ? WHERE id = 1",
            (
                estado.value,
                detenida_desde.value if detenida_desde is not None else None,
                intentos_paso,
                ciclos_revision,
                int(parada_plan),
                int(parada_final),
            ),
        )
        conexion.executemany(
            "UPDATE capitulo SET estado = ?, intentos = ? WHERE numero = ?",
            [(e.value, i, n) for n, (e, i) in (capitulos or {}).items()],
        )


def proponer_cambio(proyecto: Proyecto) -> None:
    """Deja un cambio del lector ya propuesto por el Intérprete (lo hará el paso 9a)."""
    with transaccion(proyecto.conexion) as conexion:
        conexion.execute(
            "INSERT INTO cambio_lector (version_novela, capitulo, fragmento, ruta_peticion, "
            "estado, creado) VALUES (1, 3, 'la perra blanca', 'cambios/peticion-1.txt', "
            "'propuesto', ?)",
            (MOMENTO,),
        )


def volcado(conexion: sqlite3.Connection) -> dict[str, list[tuple[object, ...]]]:
    """Todas las filas de todas las tablas, para comparar el antes y el después (V-2)."""
    tablas = [
        f["name"]
        for f in conexion.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
    ]
    return {
        tabla: [tuple(f) for f in conexion.execute(f'SELECT * FROM "{tabla}" ORDER BY rowid')]
        for tabla in tablas
    }


def transiciones(conexion: sqlite3.Connection) -> list[tuple[str, str, str]]:
    return [
        (f["origen"], f["destino"], f["causa"])
        for f in conexion.execute("SELECT origen, destino, causa FROM transicion ORDER BY id")
    ]


def estado(conexion: sqlite3.Connection) -> EstadoProyecto:
    return EstadoProyecto(conexion.execute("SELECT estado FROM proyecto").fetchone()[0])
