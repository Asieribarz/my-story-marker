"""Bloqueo por proyecto (RF-09b, Q7): un solo ejecutor a la vez, sesión o worker.

- Tomarlo devuelve un token opaco y guarda quién lo tiene (`sesion` o `worker`).
- Caduca a los `DURACION` si nadie lo renueva, para que una sesión muerta no deje el
  proyecto bloqueado para siempre; renovarlo lo alarga otro tanto.
- Pedir la siguiente orden y registrar un resultado exigen el token vigente. Con el
  bloqueo de otro, `BloqueoAjeno` dice quién lo tiene y cuándo caduca.
- Las acciones humanas no lo exigen. Borrar el proyecto se deniega con uno vigente.
- Tomarlo sube la generación del bloqueo y vuelve a sellar la orden vigente (AJ-4,
  `sello.py`): lo que llegue con el sello anterior se rechaza.
"""

import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.proyecto.abierto import Proyecto, instante, leer_instante
from backend.proyecto.errores import BloqueoAjeno, BloqueoRequerido
from backend.proyecto.sello import volver_a_sellar
from backend.shared.db import transaccion
from backend.shared.tipos import TipoEjecutor

DURACION = timedelta(minutes=30)


@dataclass(frozen=True)
class Bloqueo:
    token: str
    tipo: TipoEjecutor
    caduca: datetime


@dataclass(frozen=True)
class BloqueoVisible:
    """Lo que se enseña del bloqueo: quién y hasta cuándo, nunca el token."""

    tipo: TipoEjecutor
    caduca: datetime


def _fila(conexion: sqlite3.Connection) -> tuple[str, TipoEjecutor, datetime] | None:
    fila = conexion.execute(
        "SELECT bloqueo_titular, bloqueo_tipo, bloqueo_caduca FROM proyecto WHERE id = 1"
    ).fetchone()
    if fila is None or fila["bloqueo_titular"] is None:
        return None
    return (
        fila["bloqueo_titular"],
        TipoEjecutor(fila["bloqueo_tipo"]),
        leer_instante(fila["bloqueo_caduca"]),
    )


def bloqueo_vigente(conexion: sqlite3.Connection, ahora: datetime) -> BloqueoVisible | None:
    fila = _fila(conexion)
    if fila is None or fila[2] <= ahora:
        return None
    return BloqueoVisible(fila[1], fila[2])


def _escribir(conexion: sqlite3.Connection, bloqueo: Bloqueo | None) -> None:
    if bloqueo is None:
        valores: tuple[str | None, ...] = (None, None, None)
    else:
        valores = (bloqueo.token, bloqueo.tipo.value, instante(bloqueo.caduca))
    conexion.execute(
        "UPDATE proyecto SET bloqueo_titular = ?, bloqueo_tipo = ?, bloqueo_caduca = ? "
        "WHERE id = 1",
        valores,
    )


def _caducidad(ahora: datetime) -> datetime:
    return leer_instante(instante(ahora + DURACION))


def _es_el_titular(titular: str, token: str) -> bool:
    """Compara en tiempo constante sobre bytes: `compare_digest` no admite cadenas con
    caracteres no ASCII, y la cabecera `X-Bloqueo` puede traer cualquiera. Un token así no es
    el de nadie: da `BloqueoAjeno`, no un error interno (RF-09b)."""
    return secrets.compare_digest(
        titular.encode("utf-8"), token.encode("utf-8", errors="surrogatepass")
    )


def tomar_bloqueo(proyecto: Proyecto, tipo: TipoEjecutor, ahora: datetime) -> Bloqueo:
    """Toma el bloqueo si está libre o caducado. Con uno vigente, sea de quien sea,
    `BloqueoAjeno`: quien ya lo tiene lo renueva con su token."""
    with transaccion(proyecto.conexion) as conexion:
        vigente = bloqueo_vigente(conexion, ahora)
        if vigente is not None:
            raise BloqueoAjeno(vigente.tipo, vigente.caduca)
        bloqueo = Bloqueo(secrets.token_urlsafe(24), tipo, _caducidad(ahora))
        _escribir(conexion, bloqueo)
        volver_a_sellar(proyecto, ahora)
    return bloqueo


def exigir_bloqueo(conexion: sqlite3.Connection, token: str, ahora: datetime) -> Bloqueo:
    """El bloqueo vigente, si es de este token. Se llama dentro de la transacción de quien
    lo exige, para que nadie lo tome entre la comprobación y la escritura."""
    fila = _fila(conexion)
    if fila is None:
        raise BloqueoRequerido("nadie lo ha tomado; tómalo antes de pedir la siguiente orden")
    titular, tipo, caduca = fila
    if caduca <= ahora:
        raise BloqueoRequerido(f"caducó a las {caduca.isoformat()}; vuelve a tomarlo")
    if not _es_el_titular(titular, token):
        raise BloqueoAjeno(tipo, caduca)
    return Bloqueo(titular, tipo, caduca)


def renovar_bloqueo(proyecto: Proyecto, token: str, ahora: datetime) -> Bloqueo:
    with transaccion(proyecto.conexion) as conexion:
        actual = exigir_bloqueo(conexion, token, ahora)
        renovado = Bloqueo(actual.token, actual.tipo, _caducidad(ahora))
        _escribir(conexion, renovado)
    return renovado


def soltar_bloqueo(proyecto: Proyecto, token: str, ahora: datetime) -> None:
    """Suelta el bloqueo propio, vigente o caducado. Soltar sin bloqueo no hace nada."""
    with transaccion(proyecto.conexion) as conexion:
        fila = _fila(conexion)
        if fila is None:
            return
        titular, tipo, caduca = fila
        if not _es_el_titular(titular, token):
            if caduca > ahora:
                raise BloqueoAjeno(tipo, caduca)
            return
        _escribir(conexion, None)


def soltar_bloqueo_del_worker(conexion: sqlite3.Connection) -> None:
    """R-4: el worker suelta el bloqueo que tomó su `claude -p` cuando ese proceso ya no
    existe —falló, se colgó y se mató, o murió—. Solo uno de tipo `worker`: el de una sesión
    no es suyo. Se llama dentro de la transacción de quien abandona el trabajo."""
    fila = _fila(conexion)
    if fila is not None and fila[1] is TipoEjecutor.WORKER:
        _escribir(conexion, None)
