"""Cuándo y cómo se envía un proyecto a Langfuse.

- **Tras cada `/resultado`**, en segundo plano (`programar`): la ruta responde sin esperar,
  y un fallo de Langfuse se anota en el log y no toca la generación. Si llega otro
  resultado mientras se envía, se repite una vez al terminar, así que el último estado
  siempre sale.
- **A mano**: `uv run python -m backend.observabilidad <proyecto>|--todos`, para enviar lo
  que ya existía —la revisión humana, que entra por otra ruta, o las novelas anteriores—.

Langfuse duplica un span o un score reenviado con el mismo id (I-09), así que cada uno se
envía **una sola vez**: la base del proyecto guarda en `cache`, bajo `langfuse:enviado`, los
identificadores ya enviados, y solo salen los spans definitivos que faltan (`traza.py`).
Es la única escritura de `observabilidad/` en la base, y no toca datos del proyecto.

Las definiciones de `.claude/agents/` se suben como versiones de prompt, con la etiqueta
`sha-<12 primeros del SHA-256>`, que es lo que el hook manda como `version_prompt`: así
cada observación queda enlazada con la versión del prompt que la produjo.
"""

import hashlib
import json
import logging
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.observabilidad import otlp
from backend.observabilidad.cliente import ClienteLangfuse, Emisor
from backend.observabilidad.configuracion import de_entorno
from backend.observabilidad.traza import Exportacion, Score, construir
from backend.shared.db import conectar, transaccion
from backend.shared.rutas import DIR_AGENTES, DisposicionProyecto

registro = logging.getLogger(__name__)

SPANS_POR_PETICION = 200
SCORES_POR_PETICION = 100


@dataclass(frozen=True)
class Resumen:
    proyecto: str
    spans: int
    scores: int


def etiqueta(sha: str) -> str:
    return f"sha-{sha[:12]}"


def sincronizar_prompts(
    emisor: Emisor, directorio: Path = DIR_AGENTES
) -> dict[tuple[str, str], int]:
    """Sube la definición vigente de cada agente si Langfuse aún no tiene su versión."""
    versiones: dict[tuple[str, str], int] = {}
    for fichero in sorted(directorio.glob("*.md")):
        contenido = fichero.read_bytes()
        sha = hashlib.sha256(contenido).hexdigest()
        nombre = fichero.stem
        version = emisor.version_de_prompt(nombre, etiqueta(sha))
        if version is None:
            version = emisor.crear_prompt(
                nombre, contenido.decode("utf-8"), [etiqueta(sha)], {"sha256": sha}
            )
        versiones[(nombre, sha)] = version
    return versiones


def _score(score: Score) -> dict[str, Any]:
    cuerpo: dict[str, Any] = {
        "id": score.id,
        "traceId": score.traza,
        "name": score.nombre,
        "value": score.valor,
        "dataType": score.tipo,
        "metadata": score.metadatos,
    }
    if score.observacion is not None:
        cuerpo["observationId"] = score.observacion
    if score.comentario is not None:
        cuerpo["comment"] = score.comentario
    return cuerpo


def _versiones_que_faltan(
    exportacion_previa: Exportacion, emisor: Emisor, conocidas: dict[tuple[str, str], int]
) -> None:
    """Resuelve las versiones de prompt que usaron las órdenes y aún no se conocen (una
    definición antigua ya subida en otra ejecución, por ejemplo)."""
    prefijo = "langfuse.observation.metadata."
    for span in exportacion_previa.spans:
        agente = span.atributos.get(prefijo + "agente")
        sha = span.atributos.get(prefijo + "version_prompt")
        if isinstance(agente, str) and isinstance(sha, str) and (agente, sha) not in conocidas:
            version = emisor.version_de_prompt(agente, etiqueta(sha))
            if version is not None:
                conocidas[(agente, sha)] = version


def exportar_proyecto(
    disposicion: DisposicionProyecto,
    emisor: Emisor,
    versiones: dict[tuple[str, str], int] | None = None,
) -> Resumen:
    # `conectar` crearía una base vacía en una ruta que no existe.
    if not disposicion.base.is_file():
        raise FileNotFoundError(f"el proyecto {disposicion.identificador} no tiene base")
    identificador = disposicion.identificador
    conexion = conectar(disposicion.base)
    try:
        conocidas = versiones if versiones is not None else {}
        _versiones_que_faltan(construir(conexion, identificador), emisor, conocidas)
        exportacion = construir(conexion, identificador, conocidas)
        enviados = _enviados(conexion)
        spans = [s for s in exportacion.spans if s.definitivo and s.id not in enviados]
        scores = [s for s in exportacion.scores if s.id not in enviados]
        for inicio in range(0, len(spans), SPANS_POR_PETICION):
            lote = spans[inicio : inicio + SPANS_POR_PETICION]
            emisor.enviar_spans(otlp.peticion(lote))
            _anotar(conexion, enviados, [s.id for s in lote])
        for inicio in range(0, len(scores), SCORES_POR_PETICION):
            lote_scores = scores[inicio : inicio + SCORES_POR_PETICION]
            emisor.enviar_scores([_score(s) for s in lote_scores])
            _anotar(conexion, enviados, [s.id for s in lote_scores])
    finally:
        conexion.close()
    return Resumen(identificador, len(spans), len(scores))


CLAVE_ENVIADOS = "langfuse:enviado"


def _enviados(conexion: sqlite3.Connection) -> set[str]:
    fila = conexion.execute("SELECT valor FROM cache WHERE clave = ?", (CLAVE_ENVIADOS,)).fetchone()
    return set(json.loads(fila["valor"])) if fila is not None else set()


def _anotar(conexion: sqlite3.Connection, enviados: set[str], nuevos: list[str]) -> None:
    """Tras cada lote aceptado: si el siguiente falla, lo ya enviado no se repite."""
    enviados.update(nuevos)
    with transaccion(conexion):
        conexion.execute(
            "INSERT INTO cache (clave, valor, creado) VALUES (?, ?, ?) "
            "ON CONFLICT (clave) DO UPDATE SET valor = excluded.valor",
            (
                CLAVE_ENVIADOS,
                json.dumps(sorted(enviados)),
                datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
        )


# ─── En segundo plano, tras cada resultado ──────────────────────────────────────────────

_cerrojo = threading.Lock()
_pendientes: dict[str, bool] = {}
_versiones: dict[tuple[str, str], int] = {}
_prompts_sincronizados = False


@contextmanager
def _cliente() -> Iterator[ClienteLangfuse | None]:
    configuracion = de_entorno()
    if configuracion is None:
        yield None
        return
    cliente = ClienteLangfuse(configuracion)
    try:
        yield cliente
    finally:
        cliente.cerrar()


def programar(disposicion: DisposicionProyecto) -> None:
    """Envía el proyecto; nunca lanza. Sin claves de Langfuse no hace nada."""
    global _prompts_sincronizados
    identificador = disposicion.identificador
    with _cerrojo:
        if identificador in _pendientes:
            _pendientes[identificador] = True
            return
        _pendientes[identificador] = False
    try:
        with _cliente() as cliente:
            if cliente is None:
                return
            if not _prompts_sincronizados:
                _versiones.update(sincronizar_prompts(cliente))
                _prompts_sincronizados = True
            while True:
                exportar_proyecto(disposicion, cliente, _versiones)
                with _cerrojo:
                    if not _pendientes[identificador]:
                        return
                    _pendientes[identificador] = False
    except Exception:
        registro.warning(
            "no se pudo enviar el proyecto %s a Langfuse", identificador, exc_info=True
        )
    finally:
        with _cerrojo:
            _pendientes.pop(identificador, None)
