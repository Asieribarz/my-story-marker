"""Encolar la generación desde la web (TC-8, architecture.md §3.2 y §7).

El comprador pulsa «Generar» y se encola un trabajo sin cambio: el worker lo lanza con la
misma línea de `claude -p` que una regeneración y lleva el proyecto hasta su próxima parada.
Es una acción humana: no exige el bloqueo (Q7). Si una sesión con `/generar` lo tiene, el
trabajo espera en cola hasta que lo suelte.

Solo cabe mientras el proyecto tiene trabajo de agente por delante. En una parada —falta el
brief, hay hechos por confirmar, las dos aprobaciones, `detenida`, `publicada`— o durante un
cambio del lector, la decisión es de la persona y se rechaza con `TransicionInvalida`. Pedirla
otra vez con un trabajo aún en cola o en curso devuelve ese mismo: no se duplica.
"""

from datetime import datetime

from backend.cambio.consultas import encolar_trabajo
from backend.proyecto.abierto import Proyecto, instante
from backend.proyecto.errores import TransicionInvalida
from backend.shared.db import transaccion
from backend.shared.tipos import EstadoProyecto, EstadoTrabajo

ACCION = "generar"

# Paradas humanas y el ciclo de cambio del lector: ahí no hay nada que generar.
_SIN_GENERACION = frozenset(
    {
        EstadoProyecto.APROBACION_PLAN,
        EstadoProyecto.APROBACION_FINAL,
        EstadoProyecto.PUBLICADA,
        EstadoProyecto.CAMBIO_SOLICITADO,
        EstadoProyecto.REGENERACION,
        EstadoProyecto.DETENIDA,
    }
)


def encolar_generacion(proyecto: Proyecto, ahora: datetime) -> int:
    """Encola la generación y devuelve el número del trabajo, o el del que ya espera."""
    with transaccion(proyecto.conexion) as conexion:
        pendiente = conexion.execute(
            "SELECT id FROM trabajo WHERE estado IN (?, ?) ORDER BY id LIMIT 1",
            (EstadoTrabajo.EN_COLA.value, EstadoTrabajo.EN_CURSO.value),
        ).fetchone()
        if pendiente is not None:
            return int(pendiente["id"])
        fila = conexion.execute(
            "SELECT estado, "
            "NOT EXISTS (SELECT 1 FROM brief) AS sin_brief, "
            "EXISTS (SELECT 1 FROM hecho_propuesto WHERE estado = 'pendiente') AS hechos, "
            "EXISTS (SELECT 1 FROM cambio_lector WHERE estado IN ('interpretando', "
            "'propuesto', 'regenerando')) AS cambio "
            "FROM proyecto WHERE id = 1"
        ).fetchone()
        estado = EstadoProyecto(fila["estado"])
        if estado in _SIN_GENERACION or fila["cambio"]:
            raise TransicionInvalida(estado, None, ACCION, "el proyecto espera a la persona")
        if estado is EstadoProyecto.INTAKE and fila["sin_brief"]:
            raise TransicionInvalida(estado, None, ACCION, "falta el brief")
        if estado is EstadoProyecto.INTAKE and fila["hechos"]:
            raise TransicionInvalida(estado, None, ACCION, "hay hechos por confirmar")
        return encolar_trabajo(conexion, None, instante(ahora))
