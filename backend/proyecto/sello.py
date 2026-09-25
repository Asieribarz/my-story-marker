"""El sello de la orden (AJ-4, spec-backend-2 §4.1.2 y §4.1.7).

`<proyecto>:<orden>:<generación>`, opaco salvo el primer segmento, que es el proyecto. La
generación es `proyecto.generacion_bloqueo`, que suma 1 cada vez que alguien toma el bloqueo
(un titular nuevo, o el mismo tras caducar: tomarlo siempre da un token nuevo).

- Al emitir una orden se sella con la generación vigente (`sellar`).
- Al tomar el bloqueo con una orden vigente, se vuelve a sellar (`volver_a_sellar`): el
  sello anterior deja de valer, así que el resultado o la escritura MCP de un ejecutor caído
  —o de un subagente suyo que acaba tarde— se rechaza con `SelloInvalido`. Si la orden es
  del Bibliotecario, se borra lo escrito para su capítulo (B-16); si es del Extractor o del
  Intérprete, se retira su identificador de `/mcp/entrada` y se emite otro si su agente
  tiene renovador (hoy, el Extractor).
- `orden_de_sello` es la orden vigente de un sello, para las herramientas de
  `/mcp/escritura`, que lo reciben como argumento; `fila_de_sello`, la orden de un sello,
  vigente o cerrada, para `/resultado`, que reconoce un reenvío idempotente.
"""

import json
import secrets
import sqlite3
from datetime import datetime

from backend.intake.entrada import retirar
from backend.proyecto.abierto import Proyecto
from backend.proyecto.errores import SelloInvalido
from backend.proyecto.manejadores import ContextoManejo, entrada_renovada
from backend.proyecto.orden import OrdenEmitida, orden_vigente
from backend.shared.tipos import Agente, RecursoEntrada

_CON_IDENTIFICADOR = frozenset({Agente.EXTRACTOR_HECHOS, Agente.INTERPRETE_CAMBIOS})
_RECURSOS = frozenset(r.value for r in RecursoEntrada)


def _generacion(conexion: sqlite3.Connection) -> int:
    fila = conexion.execute("SELECT generacion_bloqueo FROM proyecto WHERE id = 1").fetchone()
    return int(fila["generacion_bloqueo"])


def sellar(conexion: sqlite3.Connection, proyecto: str, orden: int) -> str:
    """Sella la orden con la generación vigente del bloqueo y devuelve el sello."""
    sello = f"{proyecto}:{orden}:{_generacion(conexion)}"
    conexion.execute("UPDATE orden SET sello = ? WHERE id = ?", (sello, orden))
    return sello


def _iguales(a: str, b: str) -> bool:
    return secrets.compare_digest(
        a.encode("utf-8", errors="surrogatepass"), b.encode("utf-8", errors="surrogatepass")
    )


def orden_de_sello(conexion: sqlite3.Connection, sello: str) -> OrdenEmitida:
    """AJ-4: la orden vigente, si `sello` es el suyo; si no, `SelloInvalido`."""
    vigente = orden_vigente(conexion)
    if vigente is None:
        raise SelloInvalido("no hay orden vigente")
    if vigente.sello is None or not _iguales(vigente.sello, sello):
        raise SelloInvalido("es de otra orden o de una generación anterior del bloqueo")
    return vigente


def fila_de_sello(conexion: sqlite3.Connection, proyecto: str, sello: str) -> sqlite3.Row:
    """La orden que lleva `sello`, vigente o cerrada. Un sello de otro proyecto, o que ya no
    lleva ninguna orden —se volvió a sellar—, da `SelloInvalido`."""
    if sello.split(":", 1)[0] != proyecto:
        raise SelloInvalido("el primer segmento no es este proyecto")
    fila: sqlite3.Row | None = conexion.execute(
        "SELECT * FROM orden WHERE sello = ?", (sello,)
    ).fetchone()
    if fila is None:
        raise SelloInvalido("no es el de ninguna orden: es de una generación anterior")
    return fila


def volver_a_sellar(proyecto: Proyecto, ahora: datetime) -> None:
    """AJ-4: sube la generación y vuelve a sellar la orden vigente, con sus efectos. Se llama
    dentro de la transacción que toma el bloqueo."""
    conexion = proyecto.conexion
    conexion.execute("UPDATE proyecto SET generacion_bloqueo = generacion_bloqueo + 1")
    vigente = orden_vigente(conexion)
    if vigente is None:
        return
    sellar(conexion, proyecto.identificador, vigente.id)
    if vigente.agente is Agente.BIBLIOTECARIO and vigente.capitulo is not None:
        from backend.capitulo.biblia import borrar_lo_escrito

        borrar_lo_escrito(conexion, vigente.capitulo)
    if vigente.agente in _CON_IDENTIFICADOR:
        for clave, valor in vigente.entrada.items():
            if clave in _RECURSOS and isinstance(valor, dict):
                identificador = valor.get("identificador")
                if isinstance(identificador, str):
                    retirar(conexion, identificador)
        renovada = entrada_renovada(ContextoManejo(proyecto, vigente, ahora))
        if renovada is not None:
            conexion.execute(
                "UPDATE orden SET entrada = ? WHERE id = ?",
                (json.dumps(renovada, ensure_ascii=False), vigente.id),
            )
