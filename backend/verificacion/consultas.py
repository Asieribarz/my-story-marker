"""Acceso a datos de `verificacion`: lecturas de la biblia para los gates y escrituras de
`gate_resultado` e `informe_juez`.

Las lecturas de la cronología entera (todos los eventos con sus presentes, todas las
localizaciones con su padre, las fechas de nacimiento) no existen en `capitulo/biblia.py`,
que lee «a fecha N−1»: aquí van como SQL de solo lectura.
"""

import json
import sqlite3
from collections.abc import Mapping, Sequence
from typing import Any

from backend.shared.db import transaccion
from backend.shared.tipos import EstadoProyecto, Gate
from backend.verificacion.cronologia import Biblia, EventoBiblia
from backend.verificacion.modelos import Rubrica

# RF-110, supuesto menor de decisiones-backend §2.1: un hecho obligatorio está cubierto si
# lo usa la versión vigente de algún capítulo. Los capítulos que deberían usarlo son los de
# su ficha (`ficha_capitulo_hecho`, §3 punto 7).
_SIN_USO = """
SELECT h.id AS hecho, f.capitulo AS capitulo
FROM hecho h LEFT JOIN ficha_capitulo_hecho f ON f.hecho = h.id
WHERE h.prioridad = 'obligatorio' AND NOT EXISTS (
  SELECT 1 FROM hecho_uso u JOIN capitulo c ON c.numero = u.capitulo
  WHERE u.hecho = h.id AND u.version = c.version_vigente
)
ORDER BY h.id, f.capitulo
"""


def hechos_sin_uso(conexion: sqlite3.Connection) -> dict[str, list[int]]:
    """RF-110: cada hecho obligatorio sin uso, con los capítulos de su ficha."""
    sin_uso: dict[str, list[int]] = {}
    for fila in conexion.execute(_SIN_USO):
        capitulos = sin_uso.setdefault(fila["hecho"], [])
        if fila["capitulo"] is not None:
            capitulos.append(int(fila["capitulo"]))
    return sin_uso


def capitulo_con_menos_hechos(conexion: sqlite3.Connection) -> int:
    """M-6: el capítulo cuya ficha tiene menos hechos asignados; a igualdad, el de menor
    número. Sin fichas, el 1."""
    fila = conexion.execute(
        "SELECT f.numero FROM ficha_capitulo f LEFT JOIN ficha_capitulo_hecho h "
        "ON h.capitulo = f.numero GROUP BY f.numero ORDER BY count(h.hecho), f.numero LIMIT 1"
    ).fetchone()
    return 1 if fila is None else int(fila["numero"])


def leer_biblia(conexion: sqlite3.Connection) -> Biblia:
    """RF-111: localizaciones con su padre, personajes con su fecha de nacimiento y todos
    los eventos con sus presentes."""
    presentes: dict[int, list[str]] = {}
    for fila in conexion.execute(
        "SELECT evento, personaje FROM evento_personaje ORDER BY evento, personaje"
    ):
        presentes.setdefault(int(fila["evento"]), []).append(fila["personaje"])
    eventos = tuple(
        EventoBiblia(
            id=int(f["id"]),
            capitulo=f["capitulo"],
            momento=f["momento"],
            dia=f["dia"],
            franja=f["franja"],
            lugar=f["lugar"],
            presentes=tuple(presentes.get(int(f["id"]), ())),
            excluye=f["excluye"],
        )
        for f in conexion.execute(
            "SELECT id, capitulo, momento, dia, franja, lugar, excluye FROM evento ORDER BY id"
        )
    )
    return Biblia(
        localizaciones=tuple(
            (f["id"], f["padre"])
            for f in conexion.execute("SELECT id, padre FROM localizacion ORDER BY id")
        ),
        personajes=tuple(
            (f["id"], f["fecha_nacimiento"])
            for f in conexion.execute("SELECT id, fecha_nacimiento FROM personaje ORDER BY id")
        ),
        eventos=eventos,
    )


def capitulos_de_eventos(conexion: sqlite3.Connection, eventos: Sequence[int]) -> list[int]:
    """§3 punto 7: `evento.capitulo` de los eventos implicados; los del contexto (NULL,
    capítulo 0) no se pueden revisar y no cuentan."""
    if not eventos:
        return []
    marcas = ", ".join("?" for _ in eventos)
    filas = conexion.execute(
        f"SELECT DISTINCT capitulo FROM evento WHERE id IN ({marcas}) AND capitulo IS NOT NULL "
        "ORDER BY capitulo",
        tuple(eventos),
    )
    return [int(f["capitulo"]) for f in filas]


def hay_gate(conexion: sqlite3.Connection, pasada: int, gate: Gate) -> bool:
    fila = conexion.execute(
        "SELECT 1 FROM gate_resultado WHERE pasada = ? AND gate = ?", (pasada, gate.value)
    ).fetchone()
    return fila is not None


def guardar_gate(
    conexion: sqlite3.Connection,
    pasada: int,
    gate: Gate,
    ok: bool,
    detalle: Mapping[str, Any],
    *,
    reemplazar: bool = False,
) -> None:
    """TC-4, AJ-3: una fila por gate y pasada. Sin `reemplazar`, la primera se queda."""
    conflicto = (
        "DO UPDATE SET ok = excluded.ok, detalle = excluded.detalle" if reemplazar else "DO NOTHING"
    )
    with transaccion(conexion):
        conexion.execute(
            "INSERT INTO gate_resultado (pasada, gate, ok, detalle) VALUES (?, ?, ?, ?) "
            f"ON CONFLICT (pasada, gate) {conflicto}",
            (pasada, gate.value, int(ok), json.dumps(detalle, ensure_ascii=False)),
        )


def proyecto_en_curso(conexion: sqlite3.Connection) -> tuple[int, int, int]:
    """(pasada, ciclo de revisión, versión de novela en curso). La versión es la N+1 que se
    verifica, o la última publicada si el proyecto está en `publicada` (RF-114)."""
    fila = conexion.execute(
        "SELECT pasadas, ciclos_revision, estado, "
        "(SELECT coalesce(max(numero), 0) FROM version_novela) AS publicada "
        "FROM proyecto WHERE id = 1"
    ).fetchone()
    publicada = int(fila["publicada"])
    en_curso = (
        publicada if fila["estado"] == EstadoProyecto.PUBLICADA and publicada else publicada + 1
    )
    return int(fila["pasadas"]), int(fila["ciclos_revision"]), en_curso


def guardar_evaluacion(
    conexion: sqlite3.Connection,
    evaluacion: str,
    revisor: str,
    version_novela: int,
    ciclo: int,
    rubrica: Rubrica,
    momento: str,
) -> None:
    """RF-113, RF-114: una fila de `informe_juez` por criterio."""
    with transaccion(conexion):
        conexion.executemany(
            "INSERT INTO informe_juez (evaluacion, version_novela, revisor, ciclo, criterio, "
            "puntuacion, justificacion, momento) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    evaluacion,
                    version_novela,
                    revisor,
                    ciclo,
                    c.criterio.value,
                    c.puntuacion,
                    c.justificacion,
                    momento,
                )
                for c in rubrica.criterios
            ],
        )
