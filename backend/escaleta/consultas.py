"""Guardar y leer las fichas de capítulo (RF-40, B-5) y sembrar los presagios (B-16).

`guardar_escaleta` sustituye la escaleta anterior entera: fichas, hitos, personajes con su
papel, hechos y los presagios que nacen de `ficha.plantar`, `previstos` en el capítulo 0.
Lo que el Bibliotecario abrió por su cuenta no se toca. Leer una ficha la reconstruye de
sus tablas: es lo que consulta el Recuperador, y sale igual que entró.
"""

import json
import sqlite3
from typing import Any

from backend.escaleta.modelos import FichaCapitulo, SalidaEscaletista
from backend.planificacion.consultas import SalidaIncoherente
from backend.shared.db import transaccion
from backend.shared.tipos import EstadoPresagio, Hito, PapelEnFicha


def _json(valor: object) -> str:
    return json.dumps(valor, ensure_ascii=False)


def guardar_escaleta(conexion: sqlite3.Connection, salida: SalidaEscaletista) -> None:
    """RF-40. Una clave ajena que no existe, un hito en dos fichas, un personaje presente y
    mencionado a la vez o una clave de presagio repetida dan `SalidaIncoherente`."""
    cobro = {clave: f.numero for f in salida.fichas for clave in f.cobrar}
    try:
        with transaccion(conexion):
            conexion.execute(
                "DELETE FROM presagio_estado WHERE presagio IN "
                "(SELECT id FROM presagio WHERE plantar_en IS NOT NULL)"
            )
            conexion.execute("DELETE FROM presagio WHERE plantar_en IS NOT NULL")
            conexion.execute("DELETE FROM ficha_capitulo_hito")
            conexion.execute("DELETE FROM ficha_capitulo_personaje")
            conexion.execute("DELETE FROM ficha_capitulo_hecho")
            conexion.execute("DELETE FROM ficha_capitulo")
            for ficha in salida.fichas:
                _escribir(conexion, ficha, cobro)
    except sqlite3.IntegrityError as error:
        raise SalidaIncoherente(str(error)) from error


def _escribir(conexion: sqlite3.Connection, f: FichaCapitulo, cobro: dict[str, int]) -> None:
    conexion.execute(
        "INSERT INTO ficha_capitulo (numero, objetivo, escenas, pov, localizacion, dia, tension, "
        "palabras_objetivo, cierre, plantar, cobrar, traspasos) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            f.numero,
            f.objetivo,
            _json([e.model_dump() for e in f.escenas]),
            f.pov,
            f.localizacion,
            f.dia,
            f.tension,
            f.palabras_objetivo,
            f.cierre.value,
            _json([p.model_dump() for p in f.plantar]),
            _json(list(f.cobrar)),
            _json([t.model_dump() for t in f.traspasos]),
        ),
    )
    conexion.executemany(
        "INSERT INTO ficha_capitulo_hito (capitulo, hito) VALUES (?, ?)",
        [(f.numero, h.value) for h in f.hitos],
    )
    papeles = [(p, PapelEnFicha.PRESENTE) for p in f.presentes]
    papeles += [(p, PapelEnFicha.MENCIONADO) for p in f.mencionados]
    conexion.executemany(
        "INSERT INTO ficha_capitulo_personaje (capitulo, personaje, papel) VALUES (?, ?, ?)",
        [(f.numero, p, papel.value) for p, papel in papeles],
    )
    conexion.executemany(
        "INSERT INTO ficha_capitulo_hecho (capitulo, hecho) VALUES (?, ?)",
        [(f.numero, h) for h in f.hechos],
    )
    for presagio in f.plantar:
        fila = conexion.execute(
            "INSERT INTO presagio (clave, descripcion, plantar_en, cobrar_en) VALUES (?, ?, ?, ?) "
            "RETURNING id",
            (presagio.clave, presagio.descripcion, f.numero, cobro.get(presagio.clave)),
        ).fetchone()
        conexion.execute(
            "INSERT INTO presagio_estado (presagio, capitulo, estado) VALUES (?, 0, ?)",
            (fila["id"], EstadoPresagio.PREVISTO.value),
        )


def _ficha_de_fila(conexion: sqlite3.Connection, fila: sqlite3.Row) -> FichaCapitulo:
    numero = fila["numero"]
    hitos = {
        h["hito"]
        for h in conexion.execute(
            "SELECT hito FROM ficha_capitulo_hito WHERE capitulo = ?", (numero,)
        )
    }
    personajes = conexion.execute(
        "SELECT personaje, papel FROM ficha_capitulo_personaje WHERE capitulo = ? ORDER BY rowid",
        (numero,),
    ).fetchall()
    hechos = conexion.execute(
        "SELECT hecho FROM ficha_capitulo_hecho WHERE capitulo = ? ORDER BY rowid", (numero,)
    ).fetchall()
    datos: dict[str, Any] = {
        "numero": numero,
        "hitos": [h.value for h in Hito if h.value in hitos],
        "objetivo": fila["objetivo"],
        "escenas": json.loads(fila["escenas"]),
        "pov": fila["pov"],
        "localizacion": fila["localizacion"],
        "presentes": [p["personaje"] for p in personajes if p["papel"] == PapelEnFicha.PRESENTE],
        "mencionados": [
            p["personaje"] for p in personajes if p["papel"] == PapelEnFicha.MENCIONADO
        ],
        "dia": fila["dia"],
        "tension": fila["tension"],
        "palabras_objetivo": fila["palabras_objetivo"],
        "cierre": fila["cierre"],
        "plantar": json.loads(fila["plantar"]),
        "cobrar": json.loads(fila["cobrar"]),
        "hechos": [h["hecho"] for h in hechos],
        "traspasos": json.loads(fila["traspasos"]),
    }
    return FichaCapitulo.model_validate(datos)


def leer_ficha(conexion: sqlite3.Connection, numero: int) -> FichaCapitulo | None:
    fila = conexion.execute("SELECT * FROM ficha_capitulo WHERE numero = ?", (numero,)).fetchone()
    return None if fila is None else _ficha_de_fila(conexion, fila)


def leer_escaleta(conexion: sqlite3.Connection) -> tuple[FichaCapitulo, ...]:
    filas = conexion.execute("SELECT * FROM ficha_capitulo ORDER BY numero").fetchall()
    return tuple(_ficha_de_fila(conexion, fila) for fila in filas)
