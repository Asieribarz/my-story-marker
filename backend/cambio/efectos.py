"""Lo que le pasa al cambio del lector cuando el proyecto vuelve a `publicada` (AJ-6, R-4).

`proyecto.persistencia` llama a `tras_volver_a_publicada` dentro de la transacción que
escribe esa transición, con su causa:

- `version_publicada`: el cambio que se regeneraba queda `publicado`, con el número de la
  versión nueva.
- `cambio_rechazado`: el propuesto queda `rechazado`; no se había tocado nada.
- cualquier otra —el tope del Intérprete (RF-05a, Q6), un capítulo o un veto agotados,
  las revisiones agotadas, el tope de un paso o el worker fallido (R-4)—: el cambio queda
  `fallido` con esa causa como motivo. Si ya se había confirmado, se deshace (AJ-6): el
  hecho vuelve a su valor anterior, los punteros de los diez capítulos vuelven a los de la
  versión publicada N, y los capítulos salen de `revision_humana`, para que el cambio
  siguiente pueda empezar.

Límite declarado: la biblia no se restaura. Su historia va por capítulo (B-2), y el
Bibliotecario de la versión fallida ya borró y reescribió lo de sus capítulos (B-16); el
cambio siguiente los reescribe otra vez si los regenera.
"""

import json
import sqlite3
from typing import Any

from backend.cambio import hechos
from backend.cambio.consultas import cambio_en_curso, version_vigente
from backend.proyecto.transiciones import Causa
from backend.shared.tipos import EstadoCambio


def restaurar_punteros(conexion: sqlite3.Connection) -> None:
    """AJ-6: cada capítulo vuelve a la versión que publica la versión de novela vigente,
    `aprobado` y con sus contadores a cero."""
    conexion.execute(
        "UPDATE capitulo SET estado = 'aprobado', intentos = 0, version_vigente = ("
        "  SELECT cv.version FROM version_novela_capitulo vnc "
        "  JOIN capitulo_version cv ON cv.id = vnc.capitulo_version "
        "  WHERE vnc.capitulo = capitulo.numero "
        "  AND vnc.version_novela = (SELECT max(numero) FROM version_novela)) "
        "WHERE EXISTS (SELECT 1 FROM version_novela)"
    )


def deshacer(conexion: sqlite3.Connection, fila: sqlite3.Row, momento: str) -> None:
    """AJ-6: deshace un cambio confirmado: el hecho y los punteros de los capítulos."""
    if fila["hecho"] is not None:
        hechos.cambiar_texto(conexion, fila["hecho"], fila["valor_anterior"], momento)
    elif fila["hecho_nuevo"] is not None:
        nuevo: dict[str, Any] = json.loads(fila["hecho_nuevo"])
        hechos.quitar(conexion, str(nuevo["id"]), momento)
    restaurar_punteros(conexion)


def tras_volver_a_publicada(conexion: sqlite3.Connection, causa: Causa, momento: str) -> None:
    fila = cambio_en_curso(conexion)
    if fila is None:
        return
    estado = EstadoCambio(fila["estado"])
    if causa is Causa.VERSION_PUBLICADA:
        if estado is EstadoCambio.REGENERANDO:
            conexion.execute(
                "UPDATE cambio_lector SET estado = ?, version_publicada = ? WHERE id = ?",
                (EstadoCambio.PUBLICADO.value, version_vigente(conexion), fila["id"]),
            )
        return
    if causa is Causa.CAMBIO_RECHAZADO:
        conexion.execute(
            "UPDATE cambio_lector SET estado = ? WHERE id = ?",
            (EstadoCambio.RECHAZADO.value, fila["id"]),
        )
        return
    if estado is EstadoCambio.REGENERANDO:
        deshacer(conexion, fila, momento)
    conexion.execute(
        "UPDATE cambio_lector SET estado = ?, motivo = ? WHERE id = ?",
        (EstadoCambio.FALLIDO.value, causa.value, fila["id"]),
    )
