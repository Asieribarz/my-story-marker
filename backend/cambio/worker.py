"""El worker de la cola (RF-124, TC-8, TC-9 simplificado por R-4, TC-10).

Un hilo del `lifespan` de la aplicación con `subprocess` síncrono. Procesa **un trabajo cada
vez**: el más antiguo en cola de todos los proyectos de la raíz. Por cada uno lanza

    claude -p "/regenerar <proyecto> <trabajo>" --permission-prompts none --output-format json

con el id hexadecimal del proyecto y el número del trabajo como únicos datos, nunca
`--bare` y sin `ANTHROPIC_API_KEY` en el entorno: el uso de modelo sale de la suscripción
(RNF-10). El worker no llama a ningún modelo; `claude` toma el bloqueo como `worker` y lleva
el proyecto hasta la próxima parada con la skill `orquestar-novela`.

Hay dos clases de trabajo, y las distingue `trabajo.cambio`: con un cambio, es una
**regeneración** que encolan pedir y confirmar el cambio; sin cambio, es una **generación**
que encola el comprador desde la web (`POST /proyectos/{id}/generacion`). La línea de
`claude -p` es la misma: `/regenerar` solo lleva el proyecto hasta su próxima parada. Cambian
la parada que se espera (`en_parada`) y el tiempo máximo: una novela entera tarda horas.

R-4, **una sola ejecución**: si el proceso sale con error, se cuelga más de `tiempo_maximo`
(se mata) o muere, o termina sin dejar el proyecto en una parada, el trabajo queda
`fallido` con su causa y el proyecto vuelve a `publicada` con causa `worker_fallido`: el
cambio queda fallido y se deshace (AJ-6, `efectos.py`). Se vuelve a encolar a mano, pidiendo
otra vez el cambio. Una generación que falla deja el proyecto donde estaba —la posición en
el grafo nunca se pierde (§3.2)— y suelta el bloqueo del worker: se vuelve a lanzar desde la
web y reanuda. Sin comando `claude`, el trabajo falla con `claude_no_disponible`.

- Con el bloqueo del proyecto tomado —una sesión con `/generar`, o el `claude` de un trabajo
  anterior que sigue vivo— no se lanza: el trabajo espera en cola.
- Un trabajo `en_curso` al arrancar es de un backend que se paró a mitad: vuelve a la cola
  con su antigüedad y se reanuda.
- El comando es configurable (`ConfigWorker.comando`); por defecto, `shutil.which("claude")`.
  Las pruebas lo sustituyen por un `claude` falso (TC-10) y crean la aplicación sin worker.
"""

import json
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from backend.proyecto.abierto import Proyecto, abrir_proyecto, instante
from backend.proyecto.bloqueo import bloqueo_vigente, soltar_bloqueo_del_worker
from backend.proyecto.errores import ProyectoInexistente
from backend.proyecto.persistencia import abandonar_por_worker
from backend.shared.db import transaccion
from backend.shared.rutas import IdentificadorInvalido, identificadores_en, raiz_de_proyectos
from backend.shared.tipos import EstadoCambio, EstadoProyecto, EstadoTrabajo

VARIABLE_ACTIVO = "MSM_WORKER"
TIEMPO_MAXIMO_S = 2 * 60 * 60
# E1 tardó unas tres horas de brief a publicación: el doble de margen.
TIEMPO_MAXIMO_GENERACION_S = 6 * 60 * 60
INTERVALO_S = 5.0
# El directorio del repositorio: `claude` tiene que ver `.claude/` (agentes, skills, hooks).
DIRECTORIO_DE_TRABAJO = Path(__file__).resolve().parents[2]
_IDENTIFICADOR = re.compile(r"[0-9a-f]{32}")
# Variables que el proceso hijo no hereda: el modelo sale de la suscripción, nunca de una
# clave de API (spec-backend-2 §1, «Presupuesto»).
_VARIABLES_PROHIBIDAS = ("ANTHROPIC_API_KEY",)

registro = logging.getLogger(__name__)


class CausaFallo(StrEnum):
    """R-4: por qué un trabajo queda `fallido`. Va en `trabajo.detalle`."""

    CLAUDE_NO_DISPONIBLE = "claude_no_disponible"
    SALIDA_CON_ERROR = "salida_con_error"
    TIEMPO_AGOTADO = "tiempo_agotado"
    CAIDA = "caida"
    SIN_PARADA = "sin_parada"


def _reloj() -> datetime:
    return datetime.now(UTC)


def comando_por_defecto() -> tuple[str, ...] | None:
    """TC-10: `claude` del PATH, o nada si no está."""
    ruta = shutil.which("claude")
    return (ruta,) if ruta is not None else None


@dataclass(frozen=True)
class ConfigWorker:
    """`comando=None` usa `comando_por_defecto()` en cada lanzamiento; `raiz=None`, la de
    `MSM_PROYECTOS`. El reloj entra como parámetro, como en el resto del backend."""

    comando: Sequence[str] | None = None
    tiempo_maximo: float = TIEMPO_MAXIMO_S
    tiempo_maximo_generacion: float = TIEMPO_MAXIMO_GENERACION_S
    intervalo: float = INTERVALO_S
    raiz: Path | None = None
    reloj: Callable[[], datetime] = field(default=_reloj)

    def raiz_efectiva(self) -> Path:
        return self.raiz if self.raiz is not None else raiz_de_proyectos()


@dataclass(frozen=True)
class Resultado:
    proyecto: str
    trabajo: int
    estado: EstadoTrabajo
    causa: CausaFallo | None = None


def argumentos(comando: Sequence[str], proyecto: str, trabajo: int) -> list[str]:
    """TC-10: la línea de `claude -p`. Como datos, solo el id hexadecimal del proyecto y el
    número del trabajo; `--permission-prompts none` y `--output-format json`; nunca
    `--bare`, que ignoraría la suscripción, los hooks y los agentes del repositorio."""
    if not _IDENTIFICADOR.fullmatch(proyecto) or isinstance(trabajo, bool) or trabajo < 1:
        raise ValueError("el worker solo lanza con un id de proyecto y un número de trabajo")
    linea = [
        *comando,
        "-p",
        f"/regenerar {proyecto} {int(trabajo)}",
        "--permission-prompts",
        "none",
        "--output-format",
        "json",
    ]
    if "--bare" in linea:
        raise ValueError("el worker nunca lanza claude con --bare")
    return linea


def _entorno() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in _VARIABLES_PROHIBIDAS}


def _proyectos(raiz: Path) -> list[str]:
    return identificadores_en(raiz)


def _abrir(identificador: str, raiz: Path) -> Proyecto | None:
    try:
        return abrir_proyecto(identificador, raiz)
    except (IdentificadorInvalido, ProyectoInexistente):
        return None


def reanudar_en_curso(raiz: Path) -> int:
    """TC-9: los trabajos que un backend parado dejó `en_curso` vuelven a la cola, con su
    antigüedad. Devuelve cuántos."""
    total = 0
    for identificador in _proyectos(raiz):
        proyecto = _abrir(identificador, raiz)
        if proyecto is None:
            continue
        with proyecto, transaccion(proyecto.conexion) as conexion:
            cursor = conexion.execute(
                "UPDATE trabajo SET estado = ?, empezado = NULL WHERE estado = ?",
                (EstadoTrabajo.EN_COLA.value, EstadoTrabajo.EN_CURSO.value),
            )
            total += cursor.rowcount
    return total


def siguiente_trabajo(raiz: Path, ahora: datetime) -> tuple[str, int] | None:
    """El trabajo en cola más antiguo de todos los proyectos cuyo bloqueo está libre."""
    candidatos: list[tuple[str, str, int]] = []
    for identificador in _proyectos(raiz):
        proyecto = _abrir(identificador, raiz)
        if proyecto is None:
            continue
        with proyecto:
            fila = proyecto.conexion.execute(
                "SELECT id, creado FROM trabajo WHERE estado = ? ORDER BY creado, id LIMIT 1",
                (EstadoTrabajo.EN_COLA.value,),
            ).fetchone()
            if fila is None or bloqueo_vigente(proyecto.conexion, ahora) is not None:
                continue
            candidatos.append((fila["creado"], identificador, int(fila["id"])))
    if not candidatos:
        return None
    _, identificador, trabajo = min(candidatos)
    return identificador, trabajo


def _marcar_en_curso(proyecto: Proyecto, trabajo: int, ahora: datetime) -> bool:
    with transaccion(proyecto.conexion) as conexion:
        cursor = conexion.execute(
            "UPDATE trabajo SET estado = ?, empezado = ? WHERE id = ? AND estado = ?",
            (EstadoTrabajo.EN_CURSO.value, instante(ahora), trabajo, EstadoTrabajo.EN_COLA.value),
        )
        return cursor.rowcount == 1


def es_generacion(proyecto: Proyecto, trabajo: int) -> bool:
    """Un trabajo sin cambio es una generación; con cambio, una regeneración."""
    fila = proyecto.conexion.execute(
        "SELECT cambio FROM trabajo WHERE id = ?", (trabajo,)
    ).fetchone()
    return fila is not None and fila["cambio"] is None


def en_parada(proyecto: Proyecto, generacion: bool = False) -> bool:
    """Si el proyecto ha llegado a la próxima parada de su trabajo: `publicada`, `detenida`,
    una parada humana o el cambio ya propuesto, esperando su confirmación. En una generación,
    también `aprobacion_plan` y el `intake` que espera al comprador: sin brief, o con hechos
    extraídos pendientes de confirmar."""
    conexion = proyecto.conexion
    estado = EstadoProyecto(
        conexion.execute("SELECT estado FROM proyecto WHERE id = 1").fetchone()["estado"]
    )
    if estado in (EstadoProyecto.PUBLICADA, EstadoProyecto.APROBACION_FINAL):
        return True
    if estado is EstadoProyecto.DETENIDA:
        return True
    if generacion:
        if estado is EstadoProyecto.APROBACION_PLAN:
            return True
        if estado is EstadoProyecto.INTAKE:
            fila = conexion.execute(
                "SELECT NOT EXISTS (SELECT 1 FROM brief) "
                "OR EXISTS (SELECT 1 FROM hecho_propuesto WHERE estado = 'pendiente') AS espera"
            ).fetchone()
            return bool(fila["espera"])
        return False
    if estado is EstadoProyecto.CAMBIO_SOLICITADO:
        fila = conexion.execute(
            "SELECT 1 FROM cambio_lector WHERE estado = ?", (EstadoCambio.PROPUESTO.value,)
        ).fetchone()
        return fila is not None
    return False


def _cerrar(
    proyecto: Proyecto,
    trabajo: int,
    ahora: datetime,
    causa: CausaFallo | None,
    codigo: int | None,
    aviso: bool = False,
    generacion: bool = False,
) -> None:
    """Cierra el trabajo. Si una regeneración falló, el proyecto vuelve a `publicada` en la
    misma transacción (R-4), con el cambio fallido y deshecho (AJ-6); si falló una
    generación, el proyecto se queda donde está y solo se suelta el bloqueo del worker, cuyo
    proceso ya no existe. Con `aviso`, el proceso
    falló pero el proyecto ya estaba en su parada: el trabajo queda hecho, con la causa en
    `detalle.aviso`, y no se abandona nada."""
    detalle: dict[str, Any] = {"codigo_salida": codigo}
    if causa is not None:
        detalle["aviso" if aviso else "causa"] = causa.value
    if aviso:
        causa = None
    estado = EstadoTrabajo.HECHO if causa is None else EstadoTrabajo.FALLIDO
    with transaccion(proyecto.conexion) as conexion:
        conexion.execute(
            "UPDATE trabajo SET estado = ?, terminado = ?, detalle = ? WHERE id = ?",
            (estado.value, instante(ahora), json.dumps(detalle), trabajo),
        )
        if causa is not None and generacion:
            soltar_bloqueo_del_worker(conexion)
        elif causa is not None:
            abandonar_por_worker(proyecto, ahora)


def _matar_arbol(proceso: subprocess.Popen[bytes]) -> None:
    """R-4: al agotar el tiempo muere el árbol entero, no solo el hijo directo. En Windows,
    `claude` es `claude.cmd`: matar `cmd.exe` deja vivo al nieto, así que `taskkill /T /F`;
    en POSIX, el grupo de procesos de la sesión nueva. Después se espera a que termine."""
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proceso.pid)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(proceso.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    proceso.kill()
    proceso.wait()


def _ejecutar(linea: list[str], tiempo_maximo: float) -> tuple[CausaFallo | None, int | None]:
    """Una sola ejecución (R-4). La salida del proceso no se guarda: no hace falta para
    decidir, y así no se registra nada de lo que haya escrito. El proceso va en su propio
    grupo para poder matar el árbol entero si se cuelga (`_matar_arbol`)."""
    aparte: dict[str, Any] = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if sys.platform == "win32"
        else {"start_new_session": True}
    )
    try:
        proceso = subprocess.Popen(
            linea,
            cwd=DIRECTORIO_DE_TRABAJO,
            env=_entorno(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **aparte,
        )
    except OSError:
        return CausaFallo.CAIDA, None
    try:
        codigo = proceso.wait(timeout=tiempo_maximo)
    except subprocess.TimeoutExpired:
        _matar_arbol(proceso)
        return CausaFallo.TIEMPO_AGOTADO, None
    if codigo == 0:
        return None, 0
    # Un código negativo es una señal (POSIX); uno de 128 o más, una muerte del proceso
    # (128 + señal, o un código de excepción de Windows).
    return (
        CausaFallo.CAIDA if codigo < 0 or codigo >= 128 else CausaFallo.SALIDA_CON_ERROR
    ), codigo


def procesar_uno(config: ConfigWorker) -> Resultado | None:
    """Procesa el trabajo más antiguo que se pueda lanzar, o devuelve `None` si no hay."""
    raiz = config.raiz_efectiva()
    elegido = siguiente_trabajo(raiz, config.reloj())
    if elegido is None:
        return None
    identificador, trabajo = elegido
    proyecto = _abrir(identificador, raiz)
    if proyecto is None:
        return None
    with proyecto:
        if not _marcar_en_curso(proyecto, trabajo, config.reloj()):
            return None
        generacion = es_generacion(proyecto, trabajo)
    tiempo_maximo = config.tiempo_maximo_generacion if generacion else config.tiempo_maximo
    comando = tuple(config.comando) if config.comando is not None else comando_por_defecto()
    if comando is None:
        causa: CausaFallo | None = CausaFallo.CLAUDE_NO_DISPONIBLE
        codigo: int | None = None
    else:
        registro.info("trabajo %s del proyecto %s: lanzando claude -p", trabajo, identificador)
        causa, codigo = _ejecutar(argumentos(comando, identificador, trabajo), tiempo_maximo)
    proyecto = _abrir(identificador, raiz)
    if proyecto is None:  # borrado mientras corría: no hay nada que cerrar
        return Resultado(identificador, trabajo, EstadoTrabajo.FALLIDO, causa)
    with proyecto:
        # R-4: lo que decide es dónde quedó el proyecto. En su parada —el cambio ya
        # propuesto, por ejemplo— un código de salida distinto de 0 no deshace nada.
        parada = en_parada(proyecto, generacion)
        if causa is None and not parada:
            causa = CausaFallo.SIN_PARADA
        aviso = causa is not None and parada
        _cerrar(proyecto, trabajo, config.reloj(), causa, codigo, aviso, generacion)
    estado = EstadoTrabajo.HECHO if causa is None or aviso else EstadoTrabajo.FALLIDO
    if causa is not None:
        registro.warning("trabajo %s del proyecto %s: %s", trabajo, identificador, causa.value)
    return Resultado(identificador, trabajo, estado, causa)


class Worker:
    """El hilo del worker: reanuda lo que quedó `en_curso` y procesa la cola hasta parar."""

    def __init__(self, config: ConfigWorker) -> None:
        self.config = config
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None

    def arrancar(self) -> None:
        reanudar_en_curso(self.config.raiz_efectiva())
        self._hilo = threading.Thread(target=self._bucle, name="msm-worker", daemon=True)
        self._hilo.start()

    def parar(self, espera: float = 5.0) -> None:
        self._parar.set()
        if self._hilo is not None:
            self._hilo.join(espera)

    def _bucle(self) -> None:
        while not self._parar.is_set():
            try:
                hecho = procesar_uno(self.config)
            except Exception:
                registro.exception("el worker no pudo procesar un trabajo")
                hecho = None
            if hecho is None:
                self._parar.wait(self.config.intervalo)


def activo_por_entorno() -> bool:
    """El worker arranca con la aplicación salvo con `MSM_WORKER=0`."""
    return os.environ.get(VARIABLE_ACTIVO, "1") != "0"


def lifespan_del_worker(
    config: ConfigWorker,
) -> Callable[[Any], AbstractAsyncContextManager[None]]:
    """El `lifespan` que arranca el hilo del worker con la aplicación y lo para al cerrarla."""

    @asynccontextmanager
    async def lifespan(app: Any) -> AsyncIterator[None]:
        worker = Worker(config)
        worker.arrancar()
        try:
            yield
        finally:
            worker.parar()

    return lifespan
