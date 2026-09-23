"""Persistencia de la entrevista (RF-10, RF-11, RF-13, RF-15).

- Las respuestas se guardan íntegras salvo los datos excluidos, que se descartan y se
  auditan (C-8 manda sobre RF-10: minimizar es la regla, no la excepción).
- El texto libre se guarda como fichero aparte y no confiable (RF-14). Este módulo solo
  lo escribe; entregarlo es cosa de `/mcp/entrada`, en el paso 5.
- Los hechos que extrae el Extractor quedan `pendiente` hasta que el comprador los
  confirma; solo los confirmados entran en el contexto.
"""

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from backend.contexto.modelos import Hecho, TipoHecho
from backend.intake.datos_excluidos import Descarte, depurar, descartes_de_texto
from backend.shared.db import transaccion
from backend.shared.rutas import DisposicionProyecto


@dataclass(frozen=True)
class Propuesta:
    aceptados: tuple[int, ...]
    rechazados: tuple[tuple[int, str], ...]
    descartes: tuple[Descarte, ...] = field(default=())


class DecisionInvalida(ValueError):
    pass


def auditar_descartes(
    conexion: sqlite3.Connection, descartes: Iterable[Descarte], origen: str, momento: str
) -> None:
    conexion.executemany(
        "INSERT INTO auditoria (momento, tipo, detalle) VALUES (?, 'descarte_dato_personal', ?)",
        [
            (momento, json.dumps({"tipo": d.tipo, "campo": d.campo, "origen": origen}))
            for d in descartes
        ],
    )


def guardar_brief(
    conexion: sqlite3.Connection,
    disposicion: DisposicionProyecto,
    respuestas: dict[str, Any],
    texto_libre: str | None,
    momento: str,
) -> tuple[Descarte, ...]:
    """RF-10: guarda la entrevista. Volver a enviarla sustituye la anterior."""
    limpias, descartes = depurar(respuestas)
    ruta_texto = None
    if texto_libre is not None:
        disposicion.texto_libre.parent.mkdir(parents=True, exist_ok=True)
        disposicion.texto_libre.write_text(texto_libre, encoding="utf-8")
        ruta_texto = disposicion.relativa(disposicion.texto_libre)
    with transaccion(conexion):
        conexion.execute(
            "INSERT INTO brief (id, respuestas, ruta_texto_libre, creado) VALUES (1, ?, ?, ?) "
            "ON CONFLICT (id) DO UPDATE SET respuestas = excluded.respuestas, "
            "ruta_texto_libre = excluded.ruta_texto_libre, normalizado = NULL, "
            "creado = excluded.creado",
            (json.dumps(limpias, ensure_ascii=False), ruta_texto, momento),
        )
        auditar_descartes(conexion, descartes, "entrevista", momento)
    return tuple(descartes)


def guardar_normalizado(
    conexion: sqlite3.Connection, normalizado: dict[str, Any], momento: str
) -> tuple[Descarte, ...]:
    """RF-11: el brief normalizado va junto al original, sin sustituirlo."""
    limpio, descartes = depurar(normalizado)
    with transaccion(conexion):
        cambiadas = conexion.execute(
            "UPDATE brief SET normalizado = ? WHERE id = 1",
            (json.dumps(limpio, ensure_ascii=False),),
        ).rowcount
        if cambiadas != 1:
            raise LookupError("no hay brief que normalizar")
        auditar_descartes(conexion, descartes, "brief_normalizado", momento)
    return tuple(descartes)


def _validar_propuesto(indice: int, propuesto: object) -> Hecho | str:
    """RF-15: todo hecho propuesto encaja en el esquema de definitions.md §9 o se rechaza.

    El id y el origen no los decide el Extractor: el id se asigna al confirmar y el origen
    es siempre `texto_libre`.
    """
    if not isinstance(propuesto, dict):
        return "no es un objeto"
    try:
        hecho = Hecho.model_validate({**propuesto, "id": f"p{indice}", "origen": "texto_libre"})
    except ValidationError as error:
        return "; ".join(
            f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors(include_url=False)
        )
    if hecho.tipo is TipoHecho.EVENTO and not (hecho.momento and hecho.lugar):
        return "un `evento` lleva `momento` y `lugar`"
    return hecho


def proponer_hechos(
    conexion: sqlite3.Connection, propuestos: list[object], momento: str
) -> Propuesta:
    aceptados: list[int] = []
    rechazados: list[tuple[int, str]] = []
    descartes: list[Descarte] = []
    with transaccion(conexion):
        for i, propuesto in enumerate(propuestos):
            resultado = _validar_propuesto(i, propuesto)
            if isinstance(resultado, str):
                rechazados.append((i, resultado))
                continue
            suyos = [
                d
                for campo, texto in (("texto", resultado.texto), ("lugar", resultado.lugar))
                if texto
                for d in descartes_de_texto(texto, f"hechos.{i}.{campo}")
            ]
            if suyos:
                descartes.extend(suyos)
                continue
            fila = conexion.execute(
                "INSERT INTO hecho_propuesto (tipo, texto, prioridad, momento, lugar, creado) "
                "VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
                (
                    resultado.tipo.value,
                    resultado.texto,
                    resultado.prioridad.value,
                    resultado.momento,
                    resultado.lugar,
                    momento,
                ),
            ).fetchone()
            aceptados.append(int(fila["id"]))
        auditar_descartes(conexion, descartes, "texto_libre", momento)
    return Propuesta(tuple(aceptados), tuple(rechazados), tuple(descartes))


def confirmar_hechos(
    conexion: sqlite3.Connection, decisiones: dict[int, bool], momento: str
) -> None:
    """RF-15: el comprador confirma o rechaza cada hecho pendiente; queda registrado."""
    with transaccion(conexion):
        pendientes = {
            fila["id"]
            for fila in conexion.execute(
                "SELECT id FROM hecho_propuesto WHERE estado = 'pendiente'"
            )
        }
        desconocidos = set(decisiones) - pendientes
        if desconocidos:
            raise DecisionInvalida(f"hechos no pendientes: {sorted(desconocidos)}")
        conexion.executemany(
            "UPDATE hecho_propuesto SET estado = ? WHERE id = ?",
            [("confirmado" if si else "rechazado", hid) for hid, si in decisiones.items()],
        )
        resumen = {str(hid): si for hid, si in sorted(decisiones.items())}
        conexion.execute(
            "INSERT INTO decision_humana (momento, tipo, decision, notas) "
            "VALUES (?, 'confirmacion_hechos', 'confirmado', ?)",
            (momento, json.dumps(resumen)),
        )


def hechos_pendientes(conexion: sqlite3.Connection) -> list[sqlite3.Row]:
    return conexion.execute(
        "SELECT * FROM hecho_propuesto WHERE estado = 'pendiente' ORDER BY id"
    ).fetchall()


def hechos_confirmados(conexion: sqlite3.Connection) -> list[sqlite3.Row]:
    return conexion.execute(
        "SELECT * FROM hecho_propuesto WHERE estado = 'confirmado' ORDER BY id"
    ).fetchall()
