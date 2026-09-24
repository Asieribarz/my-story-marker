"""Los gates deterministas de manuscrito: cobertura y Lean (RF-110 a RF-112, TC-1 a TC-4).

Los ejecuta el backend al calcular la siguiente orden en `verificacion_manuscrito` (TC-4),
una vez por pasada (AJ-3): una fila por gate en `gate_resultado`, y repetir no la duplica.
El `detalle` de cada fila lleva siempre `capitulos`, los capítulos a corregir, que es de
donde el cerebro saca la revisión (M-6).
"""

import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.shared.db import transaccion
from backend.shared.rutas import DisposicionProyecto
from backend.shared.tipos import Gate
from backend.verificacion.consultas import (
    capitulo_con_menos_hechos,
    capitulos_de_eventos,
    guardar_gate,
    hay_gate,
    hechos_sin_uso,
    leer_biblia,
)
from backend.verificacion.cronologia import (
    Cronologia,
    SalidaLeanIlegible,
    eventos_implicados,
    generar,
    leer_informe,
)

# decisiones-backend §2.1: `formal/lean` se localiza desde el propio código.
PROYECTO_LEAN = Path(__file__).resolve().parents[2] / "formal" / "lean"
TIEMPO_MAXIMO_S = 600
NOMBRE_LEAN = "cronologia.lean"
NOMBRE_CORRESPONDENCIA = "cronologia.json"
CAUSA_SIN_LEAN = "lean_no_disponible"
CAUSA_CRONOLOGIA_INVALIDA = "cronologia_invalida"
CAUSA_CONTEXTO_INCOHERENTE = "contexto_incoherente"


@dataclass(frozen=True)
class EjecucionLean:
    codigo: int
    salida: str


def localizar_lake() -> str | None:
    """`lake` del PATH o, si no está, el de `elan` en la carpeta del usuario."""
    encontrado = shutil.which("lake")
    if encontrado:
        return encontrado
    for nombre in ("lake.exe", "lake"):
        candidato = Path.home() / ".elan" / "bin" / nombre
        if candidato.is_file():
            return str(candidato)
    return None


def ejecutar_lean(lake: str, fichero: Path) -> EjecucionLean:
    """plan-formal §3.3: `lake build Cronologia` (no hace nada si ya está compilado) y
    `lake env lean <fichero>`, cada uno con `TIEMPO_MAXIMO_S`. Un tiempo agotado lanza
    `subprocess.TimeoutExpired`."""
    opciones = {
        "cwd": PROYECTO_LEAN,
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": TIEMPO_MAXIMO_S,
        "check": False,
    }
    compilado = subprocess.run([lake, "build", "Cronologia"], **opciones)  # type: ignore[call-overload]
    if compilado.returncode != 0:
        return EjecucionLean(-1, compilado.stdout + compilado.stderr)
    hecho = subprocess.run([lake, "env", "lean", str(fichero.resolve())], **opciones)  # type: ignore[call-overload]
    return EjecucionLean(int(hecho.returncode), hecho.stdout + hecho.stderr)


def _no_emitible(causa: str, pasada: int, motivo: str, **mas: object) -> Exception:
    """TC-3, AJ-5: la orden es `error` con causa; no se escribe la fila de Lean."""
    from backend.proyecto.manejadores import OrdenNoEmitible

    return OrdenNoEmitible(causa, None, {"pasada": pasada, "motivo": motivo, **mas})


def _sin_lean(pasada: int, motivo: str, salida: str = "") -> Exception:
    return _no_emitible(CAUSA_SIN_LEAN, pasada, motivo, salida=salida[-2000:])


def _cobertura(conexion: sqlite3.Connection, pasada: int) -> None:
    """RF-110, V-28: todo hecho obligatorio usado por la versión vigente de algún capítulo.
    Un hecho sin ficha que lo pida va al capítulo con menos hechos en su ficha (el de menor
    número si empatan): nunca hay revisión sin capítulo (M-6)."""
    sin_uso = hechos_sin_uso(conexion)
    if any(not caps for caps in sin_uso.values()):
        destino = capitulo_con_menos_hechos(conexion)
        sin_uso = {h: caps or [destino] for h, caps in sin_uso.items()}
    capitulos = sorted({c for caps in sin_uso.values() for c in caps})
    detalle = {"capitulos": capitulos, "sin_uso": sorted(sin_uso), "por_hecho": sin_uso}
    guardar_gate(conexion, pasada, Gate.COBERTURA, not sin_uso, detalle)


def _generar_lean(
    conexion: sqlite3.Connection, disposicion: DisposicionProyecto, pasada: int
) -> tuple[Cronologia, Path]:
    """RF-111: el fichero de la pasada y su correspondencia. Una biblia que no se puede
    traducir (una fecha imposible) es `cronologia_invalida`, no un 500."""
    try:
        cronologia = generar(leer_biblia(conexion))
    except ValueError as error:
        raise _no_emitible(CAUSA_CRONOLOGIA_INVALIDA, pasada, str(error)) from error
    carpeta = disposicion.pasada(pasada)
    carpeta.mkdir(parents=True, exist_ok=True)
    fichero = carpeta / NOMBRE_LEAN
    fichero.write_bytes(cronologia.lean_bytes)
    (carpeta / NOMBRE_CORRESPONDENCIA).write_bytes(cronologia.correspondencia_bytes)
    return cronologia, fichero


def _comprobar_lean(pasada: int, fichero: Path) -> dict[str, list[dict[str, Any]]]:
    """RF-112: ejecuta Lean sobre el fichero y lee su informe. Sin transacción abierta."""
    lake = localizar_lake()
    if lake is None:
        raise _sin_lean(pasada, "no se encuentra `lake` (elan)")
    try:
        ejecucion = ejecutar_lean(lake, fichero)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise _sin_lean(pasada, f"{type(error).__name__}: {error}") from error
    try:
        return leer_informe(ejecucion.codigo, ejecucion.salida)
    except SalidaLeanIlegible as error:
        raise _sin_lean(pasada, str(error), ejecucion.salida) from error


def _guardar_lean(
    conexion: sqlite3.Connection,
    disposicion: DisposicionProyecto,
    pasada: int,
    cronologia: Cronologia,
    fichero: Path,
    informe: dict[str, list[dict[str, Any]]],
) -> None:
    """El informe con los eventos traducidos a filas de `evento` y sus capítulos. Un rojo
    que solo implica eventos del contexto no lo corrige ningún Revisor: `contexto_incoherente`
    (M-6), sin fila y sin gastar ciclo de revisión."""
    filas = {e["id"]: e["evento"] for e in cronologia.correspondencia["eventos"]}
    eventos = sorted(filas[i] for i in eventos_implicados(informe))
    capitulos = capitulos_de_eventos(conexion, eventos)
    ok = not any(informe.values())
    if not ok and not capitulos:
        raise _no_emitible(CAUSA_CONTEXTO_INCOHERENTE, pasada, "sin capítulos", eventos=eventos)
    detalle = {
        "capitulos": capitulos,
        "eventos": eventos,
        "violaciones": informe,
        "fichero": disposicion.relativa(fichero),
    }
    guardar_gate(conexion, pasada, Gate.LEAN, ok, detalle)


def ejecutar_gates(
    conexion: sqlite3.Connection, disposicion: DisposicionProyecto, pasada: int, momento: str
) -> None:
    """TC-4, AJ-3: cobertura y Lean de la pasada `pasada`, cada uno una sola vez, en la
    transacción de quien llama. Lo normal es que ya estén: los escribe `preparar_gates`
    antes de emitir la orden del juez, fuera de la transacción de escritura (M-27).

    Si Lean no está disponible, no termina o su salida no se lee, lanza `OrdenNoEmitible`
    con causa `lean_no_disponible` sin escribir la fila de Lean (TC-3). `momento` no se
    guarda hoy: `gate_resultado` no tiene columna de instante.
    """
    del momento
    if not hay_gate(conexion, pasada, Gate.COBERTURA):
        _cobertura(conexion, pasada)
    if not hay_gate(conexion, pasada, Gate.LEAN):
        cronologia, fichero = _generar_lean(conexion, disposicion, pasada)
        informe = _comprobar_lean(pasada, fichero)
        _guardar_lean(conexion, disposicion, pasada, cronologia, fichero, informe)


def gates_pendientes(conexion: sqlite3.Connection, pasada: int) -> bool:
    """Si a la pasada le falta la fila de cobertura o la de Lean."""
    return not all(hay_gate(conexion, pasada, g) for g in (Gate.COBERTURA, Gate.LEAN))


def preparar_gates(
    conexion: sqlite3.Connection, disposicion: DisposicionProyecto, pasada: int
) -> None:
    """TC-4, M-27: lo mismo que `ejecutar_gates`, pero Lean (hasta 2 × `TIEMPO_MAXIMO_S`)
    corre sin transacción abierta: leer la biblia y generar el fichero, ejecutar, y guardar
    la fila en una transacción corta que vuelve a mirar si ya estaba (`hay_gate`)."""
    with transaccion(conexion):
        if not hay_gate(conexion, pasada, Gate.COBERTURA):
            _cobertura(conexion, pasada)
    if hay_gate(conexion, pasada, Gate.LEAN):
        return
    cronologia, fichero = _generar_lean(conexion, disposicion, pasada)
    informe = _comprobar_lean(pasada, fichero)
    with transaccion(conexion):
        if not hay_gate(conexion, pasada, Gate.LEAN):
            _guardar_lean(conexion, disposicion, pasada, cronologia, fichero, informe)
