"""La orden tal como se persiste y se entrega a la sesión (RF-03, RF-08, RF-08a)."""

import json
import sqlite3
from dataclasses import dataclass, replace
from typing import Any

from backend.proyecto.maquina import OrdenVigente, ViaRegistro, via_de_registro
from backend.shared.tipos import Agente, EstadoProyecto, RecursoEntrada

_RECURSOS = frozenset(recurso.value for recurso in RecursoEntrada)
# RF-36: las notas de «cambios» del plan viajan a quien pide la orden, no al estado (RF-02).
_SOLO_PARA_EL_EJECUTOR = frozenset({"notas_plan", "notas"})


@dataclass(frozen=True)
class OrdenEmitida:
    """Qué subagente lanzar, con qué entrada y dónde registrar el resultado.

    `entrada` es la persistida: pedir otra vez la orden vigente devuelve esta misma, con los
    mismos identificadores de un solo uso mientras se puedan entregar. `sello` es
    `<proyecto>:<orden>:<generación>` (AJ-4, `sello.py`): cambia al volver a sellarla, y
    solo lo recibe quien pide la orden con el token del bloqueo.
    """

    id: int
    estado: EstadoProyecto
    agente: Agente
    intento: int
    capitulo: int | None
    entrada: dict[str, Any]
    registro: ViaRegistro
    emitida: str
    sello: str | None

    @property
    def vigente(self) -> OrdenVigente:
        return OrdenVigente(self.id, self.estado, self.agente, self.intento, self.capitulo)


def orden_de_fila(fila: sqlite3.Row) -> OrdenEmitida:
    agente = Agente(fila["agente"])
    entrada: dict[str, Any] = json.loads(fila["entrada"])
    return OrdenEmitida(
        id=int(fila["id"]),
        estado=EstadoProyecto(fila["estado_proyecto"]),
        agente=agente,
        intento=int(fila["intento"]),
        capitulo=fila["capitulo"],
        entrada=entrada,
        registro=via_de_registro(agente),
        emitida=fila["emitida"],
        sello=fila["sello"],
    )


def sin_identificadores(orden: OrdenEmitida) -> OrdenEmitida:
    """RF-14: la orden como la enseña el estado (RF-02), sin los identificadores de un solo uso
    de `/mcp/entrada`; de cada recurso queda su caducidad. El identificador solo lo recibe
    quien pide la orden con el token del bloqueo: si no, cualquiera que lea el estado podría
    canjearlo antes que el subagente. Tampoco lleva el sello: con él, las herramientas de
    `/mcp/escritura` escriben en la biblia (AJ-4). Ni las notas de una parada (RF-36,
    M-6)."""
    entrada = {
        clave: (
            {k: v for k, v in valor.items() if k != "identificador"}
            if clave in _RECURSOS and isinstance(valor, dict)
            else valor
        )
        for clave, valor in orden.entrada.items()
        if clave not in _SOLO_PARA_EL_EJECUTOR
    }
    return replace(orden, entrada=entrada, sello=None)


def orden_vigente(conexion: sqlite3.Connection) -> OrdenEmitida | None:
    fila = conexion.execute("SELECT * FROM orden WHERE cerrada IS NULL").fetchone()
    return None if fila is None else orden_de_fila(fila)
