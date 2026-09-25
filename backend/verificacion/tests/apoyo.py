"""Un proyecto mínimo en `verificacion_manuscrito`, con datos ficticios, para los gates."""

import sqlite3
from pathlib import Path

from backend.shared.db import crear_base
from backend.shared.rutas import DisposicionProyecto

IDENTIFICADOR = "0123456789abcdef0123456789abcdef"
MOMENTO = "2026-09-23T10:00:00Z"


def proyecto(raiz: Path) -> tuple[DisposicionProyecto, sqlite3.Connection]:
    disposicion = DisposicionProyecto.de(IDENTIFICADOR, raiz)
    disposicion.crear_directorios()
    c = crear_base(disposicion.base)
    c.execute(
        "INSERT INTO proyecto (id, identificador, estado, pasadas, creado) "
        "VALUES (1, ?, 'verificacion_manuscrito', 1, ?)",
        (IDENTIFICADOR, MOMENTO),
    )
    c.executemany(
        "INSERT INTO localizacion (id, nivel, padre) VALUES (?, ?, ?)",
        [("pueblo", "macro", None), ("casa", "meso", "pueblo"), ("isla", "macro", None)],
    )
    c.executemany(
        "INSERT INTO personaje (id, origen, ficha, arco, fecha_nacimiento) "
        "VALUES (?, 'ficticio', '{}', 'plano', ?)",
        [("ana", "1990-05-01"), ("leo", None)],
    )
    c.executemany(
        "INSERT INTO hecho (id, tipo, texto, prioridad, origen) VALUES (?, 'evento', ?, ?, "
        "'entrevista')",
        [("h_faro", "Un faro ficticio", "obligatorio"), ("h_gato", "Un gato", "deseable")],
    )
    for n in range(1, 11):
        c.execute(
            "INSERT INTO ficha_capitulo (numero, objetivo, escenas, pov, localizacion, dia, "
            "tension, palabras_objetivo, cierre) VALUES (?, 'x', '[]', 'ana', 'casa', ?, 5, "
            "1200, 'pausa')",
            (n, n),
        )
        c.execute(
            "INSERT INTO capitulo (numero, estado, version_vigente) VALUES (?, 'aprobado', 2)",
            (n,),
        )
        for version in (1, 2):
            c.execute(
                "INSERT INTO capitulo_version (capitulo, version, intento, estado, ruta, creado) "
                "VALUES (?, ?, 1, 'aprobado', 'x.md', ?)",
                (n, version, MOMENTO),
            )
    c.executemany(
        "INSERT INTO ficha_capitulo_hecho (capitulo, hecho) VALUES (?, 'h_faro')", [(5,), (3,)]
    )
    return disposicion, c


def evento(
    c: sqlite3.Connection,
    capitulo: int | None,
    lugar: str,
    presentes: list[str],
    *,
    dia: int | None = None,
    franja: str | None = None,
    momento: str | None = None,
    excluye: str | None = None,
) -> int:
    fila = c.execute(
        "INSERT INTO evento (descripcion, momento, dia, franja, lugar, capitulo, excluye, "
        "tipo_exclusion) VALUES ('e', ?, ?, ?, ?, ?, ?, ?) RETURNING id",
        (momento, dia, franja, lugar, capitulo, excluye, "partida" if excluye else None),
    ).fetchone()
    c.executemany(
        "INSERT INTO evento_personaje (evento, personaje) VALUES (?, ?)",
        [(fila["id"], p) for p in presentes],
    )
    return int(fila["id"])
