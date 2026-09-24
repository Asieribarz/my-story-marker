"""Identificadores de un solo uso de `/mcp/entrada` (RF-14, RF-120, D-11).

El texto no confiable —el texto libre del comprador; la petición del lector, cuando llegue
`cambio/`— no viaja en ninguna orden ni en ninguna respuesta REST: el orquestador no lo
recibe nunca. La orden lleva un identificador opaco, y el agente que necesita el texto lo
canjea una sola vez por la superficie `/mcp/entrada`.

- **Formato**: `<id_proyecto>.<secreto>`, con el secreto de `secrets.token_urlsafe(32)`. El
  secreto no se deriva del proyecto. El prefijo solo sirve para que el canje abra la base de
  su proyecto sin recorrer las demás (V-24): con el prefijo de un proyecto y el secreto de
  otro, la huella no está en esa base.
- **Qué se guarda**: en `identificador_entrada`, la huella SHA-256 del secreto, el recurso,
  la ruta del texto, la emisión y la caducidad (`CADUCIDAD`). El secreto no se guarda ahí:
  el identificador entero solo está en la entrada de la orden que lo lleva, que tiene que
  poder devolverse idéntica mientras siga vigente (RF-08a).
- **Canje**: comprueba el formato y el proyecto, busca la huella, exige que no esté
  consumida ni caducada, la marca consumida y lee el texto, todo en la misma transacción.
  Cualquier fallo da `EntradaNoCanjeable`, siempre con el mismo mensaje: sin oráculo.
- **Entrega**: la orden vigente se devuelve con su identificador mientras este sea
  `entregable`: sin canjear y con al menos `MARGEN_DE_ENTREGA` por delante. Si no —una
  sesión que reanuda tras una caída recibe uno ya canjeado, o a punto de caducar—, la misma
  orden se entrega con uno nuevo y el anterior se `retira`: así el subagente relanzado puede
  canjearlo y no gasta un intento (RNF-01).
- **Invalidación**: volver a enviar el brief retira los identificadores del texto libre que
  nadie ha canjeado: el texto al que apuntaban ya no es el del brief (RF-14).
- **Registro** (RF-105, decisiones-backend §4.1.10): cada canje con un proyecto que existe,
  válido o no, queda en `llamada_mcp` de ese proyecto, sin el texto ni el secreto: el agente
  inferido de la orden vigente (§3, punto 10), el recurso y por qué no sirvió. Es la prueba
  del red team de E2 para un identificador ajeno, usado o caducado. El motivo no llega al
  agente: para él, los cinco casos siguen siendo el mismo error.
"""

import hashlib
import json
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from backend.proyecto.abierto import abrir_proyecto, instante, leer_instante
from backend.proyecto.errores import EntradaNoCanjeable, ProyectoInexistente
from backend.shared.db import transaccion
from backend.shared.rutas import DisposicionProyecto, IdentificadorInvalido
from backend.shared.tipos import RecursoEntrada

CADUCIDAD = timedelta(minutes=30)
# Lo que tiene que quedarle a un identificador para entregarlo con la orden: lo bastante
# para que el subagente arranque y lo canjee.
MARGEN_DE_ENTREGA = timedelta(minutes=5)
BYTES_DEL_SECRETO = 32
# `token_urlsafe(32)` da 43 caracteres del alfabeto base64 para URL, sin relleno.
_FORMATO = re.compile(r"(?P<proyecto>[0-9a-f]{32})\.(?P<secreto>[A-Za-z0-9_-]{43})")


@dataclass(frozen=True)
class IdentificadorEmitido:
    identificador: str
    recurso: RecursoEntrada
    caduca: datetime

    def como_entrada(self) -> dict[str, str]:
        """Cómo va en la entrada de la orden: el identificador y su caducidad, nunca el texto."""
        return {"identificador": self.identificador, "caduca": instante(self.caduca)}


def _huella(secreto: str) -> str:
    return hashlib.sha256(secreto.encode("ascii")).hexdigest()


def emitir(
    conexion: sqlite3.Connection,
    disposicion: DisposicionProyecto,
    recurso: RecursoEntrada,
    ruta: str,
    ahora: datetime,
) -> IdentificadorEmitido:
    """Emite un identificador para el texto de `ruta`, relativa al proyecto.

    Escribe dentro de la transacción de quien llama si la hay: la de emisión de la orden
    que lo lleva, para que orden e identificador existan juntos o no existan (RF-03).
    """
    disposicion.absoluta(ruta)  # una ruta que sale del proyecto no se emite
    secreto = secrets.token_urlsafe(BYTES_DEL_SECRETO)
    caduca = leer_instante(instante(ahora + CADUCIDAD))
    with transaccion(conexion):
        conexion.execute(
            "INSERT INTO identificador_entrada (huella, recurso, ruta, emitido, caduca) "
            "VALUES (?, ?, ?, ?, ?)",
            (_huella(secreto), recurso.value, ruta, instante(ahora), instante(caduca)),
        )
    return IdentificadorEmitido(f"{disposicion.identificador}.{secreto}", recurso, caduca)


def emitir_texto_libre(
    conexion: sqlite3.Connection, disposicion: DisposicionProyecto, ahora: datetime
) -> IdentificadorEmitido:
    """RF-14: el identificador del texto libre del brief, para la orden del Extractor."""
    fila = conexion.execute("SELECT ruta_texto_libre FROM brief WHERE id = 1").fetchone()
    if fila is None or fila["ruta_texto_libre"] is None:
        raise LookupError("no hay texto libre que entregar: el brief no lo trae")
    return emitir(
        conexion, disposicion, RecursoEntrada.TEXTO_LIBRE, fila["ruta_texto_libre"], ahora
    )


def entregable(conexion: sqlite3.Connection, identificador: str, ahora: datetime) -> bool:
    """Si el identificador todavía sirve para entregarlo con la orden: está en la base, nadie
    lo ha canjeado y le queda al menos `MARGEN_DE_ENTREGA`.

    Lo mira la persistencia al devolver otra vez la orden vigente. Uno mal formado o que no
    está en la base no es entregable: la orden no sirve con él.
    """
    partes = _FORMATO.fullmatch(identificador)
    if partes is None:
        return False
    fila = conexion.execute(
        "SELECT caduca, consumido FROM identificador_entrada WHERE huella = ?",
        (_huella(partes["secreto"]),),
    ).fetchone()
    if fila is None or fila["consumido"] is not None:
        return False
    return leer_instante(fila["caduca"]) - ahora >= MARGEN_DE_ENTREGA


def retirar(conexion: sqlite3.Connection, identificador: str) -> None:
    """Deja sin efecto un identificador que nadie ha canjeado: su canje dará el mismo error
    que uno desconocido. Uno ya canjeado se conserva como registro del canje."""
    partes = _FORMATO.fullmatch(identificador)
    if partes is not None:
        conexion.execute(
            "DELETE FROM identificador_entrada WHERE huella = ? AND consumido IS NULL",
            (_huella(partes["secreto"]),),
        )


def invalidar(conexion: sqlite3.Connection, recurso: RecursoEntrada) -> None:
    """Retira todos los identificadores sin canjear de un recurso: el texto al que apuntan
    ha cambiado o ya no existe."""
    conexion.execute(
        "DELETE FROM identificador_entrada WHERE recurso = ? AND consumido IS NULL",
        (recurso.value,),
    )


HERRAMIENTA = "leer_entrada"
# Como la nombra `llamada_mcp`: `<superficie>.<nombre>`, el formato de `backend/mcp/llamada.py`.
_HERRAMIENTA_EN_AUDITORIA = f"entrada.{HERRAMIENTA}"


def _registrar_canje(
    conexion: sqlite3.Connection, momento: str, recurso: str | None, motivo: str | None
) -> None:
    """§4.1.10: el canje en `llamada_mcp`, sin el identificador ni el texto, con la forma de
    fila de `backend/mcp/llamada.py`. No se registra con `llamada.ejecutar`: su error para un
    proyecto desconocido es distinto del de `EntradaNoCanjeable`, y sería un oráculo (V-29)."""
    vigente = conexion.execute("SELECT agente FROM orden WHERE cerrada IS NULL").fetchone()
    conexion.execute(
        "INSERT INTO llamada_mcp (momento, agente, herramienta, argumentos, resultado) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            momento,
            vigente["agente"] if vigente is not None else None,
            _HERRAMIENTA_EN_AUDITORIA,
            json.dumps({"recurso": recurso}),
            json.dumps({"ok": motivo is None, "error": motivo, "agente_inferido": True}),
        ),
    )


def canjear(identificador: str, ahora: datetime, raiz_proyectos: Path | None = None) -> str:
    """RF-14: el texto al que da acceso el identificador, una sola vez.

    Desconocido, usado, caducado, mal formado o de un proyecto que no existe dan
    `EntradaNoCanjeable`, la misma para los cinco. Un canje que falla no consume nada, pero
    queda registrado en su proyecto si el proyecto existe (§4.1.10).
    """
    momento = instante(ahora)
    partes = _FORMATO.fullmatch(identificador)
    if partes is None:
        raise EntradaNoCanjeable()
    try:
        proyecto = abrir_proyecto(partes["proyecto"], raiz_proyectos)
    except (IdentificadorInvalido, ProyectoInexistente):
        raise EntradaNoCanjeable() from None
    texto: str | None = None
    with proyecto, transaccion(proyecto.conexion) as conexion:
        huella = _huella(partes["secreto"])
        fila = conexion.execute(
            "SELECT recurso, ruta, caduca, consumido FROM identificador_entrada WHERE huella = ?",
            (huella,),
        ).fetchone()
        motivo: str | None = None
        if fila is None:
            motivo = "desconocido"
        elif fila["consumido"] is not None:
            motivo = "usado"
        elif leer_instante(fila["caduca"]) <= ahora:
            motivo = "caducado"
        else:
            try:
                texto = proyecto.disposicion.absoluta(fila["ruta"]).read_text(encoding="utf-8")
            except (OSError, ValueError):
                motivo = "ilegible"
        if texto is not None:
            conexion.execute(
                "UPDATE identificador_entrada SET consumido = ? WHERE huella = ?",
                (momento, huella),
            )
        _registrar_canje(conexion, momento, fila["recurso"] if fila else None, motivo)
    if texto is None:
        raise EntradaNoCanjeable()
    return texto
