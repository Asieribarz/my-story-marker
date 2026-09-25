"""La petición del lector como texto no confiable (RF-120, V-29).

La petición y el fragmento que cita los escribe el lector: no van a la base ni a ninguna
respuesta REST, ni en la orden del Intérprete. Se guardan en `cambios/peticion-<c>.txt` del
proyecto y el Intérprete los canjea una sola vez por `/mcp/entrada`, con el mismo mecanismo
de identificador de un solo uso que el texto libre del Extractor (RF-14,
`intake/entrada.py`).

El fichero es un documento JSON con lo que el Intérprete necesita para decidir —la
petición, el fragmento, su capítulo y sus párrafos, y los hechos vigentes—, que es lo que
promete la definición del agente (`.claude/agents/interprete-cambios.md`).
"""

import json
import sqlite3
from datetime import datetime

from backend.intake.entrada import IdentificadorEmitido, emitir
from backend.shared.rutas import DisposicionProyecto
from backend.shared.tipos import EstadoCambio, RecursoEntrada


def guardar_peticion(
    conexion: sqlite3.Connection,
    disposicion: DisposicionProyecto,
    cambio: int,
    capitulo: int,
    parrafos: tuple[int, int] | None,
    fragmento: str,
    peticion: str,
) -> str:
    """Escribe el documento de la petición y devuelve su ruta relativa al proyecto."""
    hechos = [
        {"id": f["id"], "tipo": f["tipo"], "texto": f["texto"]}
        for f in conexion.execute("SELECT id, tipo, texto FROM hecho ORDER BY id")
    ]
    documento = {
        "peticion": peticion,
        "fragmento": fragmento,
        "capitulo": capitulo,
        "parrafos": list(parrafos) if parrafos is not None else None,
        "hechos": hechos,
    }
    ruta = disposicion.peticion(cambio)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        json.dumps(documento, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    return disposicion.relativa(ruta)


def emitir_peticion(
    conexion: sqlite3.Connection, disposicion: DisposicionProyecto, ahora: datetime
) -> IdentificadorEmitido:
    """RF-120: el identificador de la petición del cambio que se interpreta, para la orden del
    Intérprete. Se emite en la transacción que persiste la orden."""
    fila = conexion.execute(
        "SELECT ruta_peticion FROM cambio_lector WHERE estado = ? ORDER BY id DESC LIMIT 1",
        (EstadoCambio.INTERPRETANDO.value,),
    ).fetchone()
    if fila is None or fila["ruta_peticion"] is None:
        raise LookupError("no hay petición que entregar: ningún cambio se está interpretando")
    return emitir(conexion, disposicion, RecursoEntrada.PETICION, fila["ruta_peticion"], ahora)
