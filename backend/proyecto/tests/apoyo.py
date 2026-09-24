"""Apoyo de las pruebas de `proyecto/`: reloj fijo, datos ficticios y acceso directo a la base.

Todos los datos de persona son ficticios, como en `backend/contexto/tests/referencia.py`.
`forzar` escribe el estado del grafo saltándose la máquina: sirve para colocar el proyecto
en una fase sin recorrer las anteriores, nunca para probar una transición.
"""

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.contexto.tests.referencia import referencia
from backend.proyecto.abierto import Proyecto
from backend.proyecto.extraccion import AGENTES_MARKDOWN
from backend.proyecto.persistencia import Registro, registrar_resultado
from backend.shared.db import transaccion
from backend.shared.tipos import Agente, EstadoCapitulo, EstadoProyecto

AHORA = datetime(2026, 9, 23, 10, 0, tzinfo=UTC)
MOMENTO = "2026-09-23T10:00:00Z"
BRIEF: dict[str, Any] = {"destinatario": {"nombre": "Aitana", "edad": 9}, "ocasion": "cumpleanos"}
TEXTO_LIBRE = "Le encantan los mapas y su perra se llama Nala."
HECHO: dict[str, Any] = {
    "tipo": "objeto",
    "texto": "Una brújula del abuelo",
    "prioridad": "obligatorio",
}
# El brief normalizado lleva el hecho confirmado, como pide el Agente de Contexto (B-20). Sin
# hechos confirmados, un hecho de más no incumple nada.
NORMALIZADO: dict[str, Any] = {
    "destinatario": {"nombre": "Aitana", "edad": 9},
    "tono": "ligero",
    "personalizacion": {"hechos": [{"id": "h1", **HECHO, "origen": "texto_libre"}]},
}


def contexto_con_el_hecho() -> dict[str, Any]:
    """La instancia de referencia con `HECHO` confirmado dentro, como la devolvería un Agente
    de Contexto fiel (B-20) tras confirmar el comprador el hecho de su texto libre."""
    datos = referencia()
    hecho = {"id": "h9", **HECHO, "prioridad": "deseable", "origen": "texto_libre"}
    datos["novela"]["personalizacion"]["hechos"].append(hecho)
    return datos


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
            "INSERT INTO cambio_lector (version_novela, capitulo, ruta_peticion, estado, "
            "creado) VALUES (1, 3, 'cambios/peticion-1.txt', 'propuesto', ?)",
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


# ─── Registrar como lo hace el hook (§4.1.7) ─────────────────────────────────

TITULO_DE_ENSAYO = "# Ensayo"


def sello_de(conexion: sqlite3.Connection, identificador: str, orden: int) -> str:
    """El sello de la orden `orden`; el de una orden que no existe, inventado con su forma."""
    fila = conexion.execute("SELECT sello FROM orden WHERE id = ?", (orden,)).fetchone()
    return fila["sello"] if fila is not None and fila["sello"] else f"{identificador}:{orden}:0"


def salida_cruda(agente: Agente | None, resultado: object) -> str:
    """Lo que devolvería el subagente con `resultado`: un texto va tal cual; un valor, en su
    bloque JSON, o como Markdown con título si el agente devuelve Markdown."""
    if isinstance(resultado, str):
        return resultado
    if agente in AGENTES_MARKDOWN:
        return f"{TITULO_DE_ENSAYO}\n\n{json.dumps(resultado, ensure_ascii=False)}"
    return f"```json\n{json.dumps(resultado, ensure_ascii=False)}\n```"


def valor_de_ensayo(resultado: object) -> Any:
    """El inverso de `salida_cruda` para los manejadores de ensayo de las pruebas."""
    if isinstance(resultado, str) and resultado.startswith(TITULO_DE_ENSAYO):
        return json.loads(resultado.removeprefix(TITULO_DE_ENSAYO))
    return resultado


def registrar(
    proyecto: Proyecto, orden: int, resultado: object, token: str, ahora: datetime
) -> Registro:
    """`registrar_resultado` con el sello de la orden y la salida cruda de `resultado`."""
    fila = proyecto.conexion.execute("SELECT agente FROM orden WHERE id = ?", (orden,)).fetchone()
    agente = Agente(fila["agente"]) if fila is not None else None
    sello = sello_de(proyecto.conexion, proyecto.identificador, orden)
    return registrar_resultado(proyecto, sello, salida_cruda(agente, resultado), token, ahora)
