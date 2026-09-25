"""El panel del comprador (architecture.md §1, U1): la lista de proyectos y las métricas de
creación de uno. Solo lectura: nada de aquí escribe en la base ni mueve el grafo.

Las métricas salen de lo que el proyecto ya guarda, sin contadores propios:
- `orden`: cada intento de cada agente, con su desenlace y los `metadatos` que envía el hook
  (§4.1.8: modelo, tokens y duración). Un intento con `intento > 1` es un reintento.
- `transicion`: el historial de fases (RF-09). El tiempo de una fase va de la transición que
  entra en ella a la que sale; la primera, `intake`, empieza al crear el proyecto.
- `capitulo_version`, `informe` e `informe_juez`: versiones de cada capítulo, hallazgos por
  verificador y la última puntuación del juez de manuscrito.
- `version_novela`, `cambio_lector` y `trabajo`: versiones publicadas, cambios del lector y
  regeneraciones del worker.

El gasto es de suscripción (architecture.md §10): se mide en tokens y en tiempo de agente,
nunca en dinero.
"""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from backend.proyecto.abierto import Proyecto, abrir_proyecto, leer_instante
from backend.proyecto.errores import ProyectoInexistente
from backend.shared.rutas import METADATOS, GrupoProyecto, identificadores_en
from backend.shared.tipos import EstadoProyecto

# ─── Salida ──────────────────────────────────────────────────────────────────


class _Salida(BaseModel):
    model_config = ConfigDict(frozen=True)


class ProyectoListado(_Salida):
    """Una fila del selector: `titulo` es el de la última versión publicada, si la hay;
    `etiqueta`, la que se puso al crear el proyecto, si se puso; `grupo`, su carpeta."""

    identificador: str
    grupo: GrupoProyecto
    etiqueta: str | None
    estado: EstadoProyecto
    creado: str
    versiones: int
    titulo: str | None


class Proyectos(_Salida):
    proyectos: list[ProyectoListado]


class Consumo(_Salida):
    """Lo que el hook registró de los intentos que lo traían. `con_metadatos` dice cuántos:
    un intento sin metadatos no suma, y no por eso costó cero."""

    tokens_entrada: int
    tokens_salida: int
    tokens_cache_creacion: int
    tokens_cache_lectura: int
    duracion_ms: int
    con_metadatos: int


class Intentos(_Salida):
    ordenes: int
    aceptadas: int
    rechazadas: int
    caducadas: int
    reintentos: int


class Resumen(_Salida):
    estado: EstadoProyecto
    creado: str
    # De la creación a la última publicación; si no está publicada, hasta ahora.
    duracion_s: int
    intentos: Intentos
    consumo: Consumo
    ciclos_revision: int
    pasadas_manuscrito: int
    versiones_publicadas: int


class MetricaAgente(_Salida):
    agente: str
    modelos: list[str]
    intentos: Intentos
    consumo: Consumo


class MetricaFase(_Salida):
    fase: EstadoProyecto
    entradas: int
    duracion_s: int
    en_curso: bool


class MetricaCapitulo(_Salida):
    capitulo: int
    versiones: int
    intentos: Intentos
    consumo: Consumo


class MetricaVerificador(_Salida):
    verificador: str
    informes: int
    hallazgos: int
    graves: int


class PuntuacionJuez(_Salida):
    criterio: str
    puntuacion: int


class EvaluacionJuez(_Salida):
    version_novela: int
    ciclo: int
    puntuaciones: list[PuntuacionJuez]


class Cambios(_Salida):
    pedidos: int
    publicados: int
    rechazados: int
    fallidos: int
    regeneraciones: int


class Metricas(_Salida):
    resumen: Resumen
    fases: list[MetricaFase]
    agentes: list[MetricaAgente]
    capitulos: list[MetricaCapitulo]
    verificadores: list[MetricaVerificador]
    juez: EvaluacionJuez | None
    cambios: Cambios


# ─── Lista de proyectos ──────────────────────────────────────────────────────


def _titulo(proyecto: Proyecto, version: int) -> str | None:
    ruta = proyecto.disposicion.fichero_de_version(version, METADATOS)
    try:
        titulo = json.loads(ruta.read_text(encoding="utf-8")).get("titulo")
    except (OSError, ValueError, AttributeError):
        return None
    return titulo if isinstance(titulo, str) else None


def listar_proyectos(raiz_proyectos: Path | None = None) -> Proyectos:
    """Los proyectos de la raíz, del más reciente al más antiguo. Uno que no se puede abrir
    —a medio crear o a medio borrar— no se lista."""
    filas: list[ProyectoListado] = []
    for identificador in identificadores_en(raiz_proyectos):
        try:
            proyecto = abrir_proyecto(identificador, raiz_proyectos)
        except (ProyectoInexistente, sqlite3.Error):
            continue
        with proyecto:
            # `SELECT *`: una base creada antes de la etiqueta no tiene la columna, y no hay
            # migraciones en la v1 (spec-backend-1.md §2.5). Sin columna, sin etiqueta.
            fila = proyecto.conexion.execute("SELECT * FROM proyecto").fetchone()
            versiones = int(
                proyecto.conexion.execute(
                    "SELECT coalesce(max(numero), 0) FROM version_novela"
                ).fetchone()[0]
            )
            filas.append(
                ProyectoListado(
                    identificador=identificador,
                    grupo=proyecto.disposicion.grupo,
                    etiqueta=fila["etiqueta"] if "etiqueta" in fila.keys() else None,
                    estado=EstadoProyecto(fila["estado"]),
                    creado=fila["creado"],
                    versiones=versiones,
                    titulo=_titulo(proyecto, versiones) if versiones else None,
                )
            )
    filas.sort(key=lambda p: p.creado, reverse=True)
    return Proyectos(proyectos=filas)


# ─── Métricas ────────────────────────────────────────────────────────────────


@contextmanager
def _lectura(conexion: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Una transacción de lectura: todas las consultas ven el mismo estado de la base."""
    conexion.execute("BEGIN")
    try:
        yield conexion
    finally:
        conexion.execute("COMMIT")


_AGREGADOS = """
  count(*) AS ordenes,
  coalesce(sum(desenlace = 'aceptada'), 0) AS aceptadas,
  coalesce(sum(desenlace = 'rechazada'), 0) AS rechazadas,
  coalesce(sum(desenlace = 'caducada'), 0) AS caducadas,
  coalesce(sum(intento > 1), 0) AS reintentos,
  coalesce(sum(json_extract(metadatos, '$.tokens_entrada')), 0) AS tokens_entrada,
  coalesce(sum(json_extract(metadatos, '$.tokens_salida')), 0) AS tokens_salida,
  coalesce(sum(json_extract(metadatos, '$.tokens_cache_creacion')), 0) AS tokens_cache_creacion,
  coalesce(sum(json_extract(metadatos, '$.tokens_cache_lectura')), 0) AS tokens_cache_lectura,
  coalesce(sum(json_extract(metadatos, '$.duracion_ms')), 0) AS duracion_ms,
  count(metadatos) AS con_metadatos
"""


def _intentos(fila: sqlite3.Row) -> Intentos:
    return Intentos(
        ordenes=int(fila["ordenes"]),
        aceptadas=int(fila["aceptadas"]),
        rechazadas=int(fila["rechazadas"]),
        caducadas=int(fila["caducadas"]),
        reintentos=int(fila["reintentos"]),
    )


def _consumo(fila: sqlite3.Row) -> Consumo:
    return Consumo(
        tokens_entrada=int(fila["tokens_entrada"]),
        tokens_salida=int(fila["tokens_salida"]),
        tokens_cache_creacion=int(fila["tokens_cache_creacion"]),
        tokens_cache_lectura=int(fila["tokens_cache_lectura"]),
        duracion_ms=int(fila["duracion_ms"]),
        con_metadatos=int(fila["con_metadatos"]),
    )


def _segundos(desde: str, hasta: datetime) -> int:
    return max(0, int((hasta - leer_instante(desde)).total_seconds()))


def _fases(
    conexion: sqlite3.Connection, creado: str, estado: EstadoProyecto, ahora: datetime
) -> tuple[list[MetricaFase], int]:
    """El tiempo en cada fase y la duración total. La fase actual cuenta hasta `ahora` salvo
    `publicada`, que es reposo: la duración total acaba en la última publicación."""
    duracion: dict[EstadoProyecto, int] = {}
    entradas: dict[EstadoProyecto, int] = {EstadoProyecto.INTAKE: 1}
    fase, inicio = EstadoProyecto.INTAKE, creado
    fin_total: str | None = None
    for fila in conexion.execute("SELECT momento, destino FROM transicion ORDER BY id"):
        duracion[fase] = duracion.get(fase, 0) + _segundos(inicio, leer_instante(fila["momento"]))
        fase, inicio = EstadoProyecto(fila["destino"]), fila["momento"]
        entradas[fase] = entradas.get(fase, 0) + 1
        if fase is EstadoProyecto.PUBLICADA:
            fin_total = fila["momento"]
    en_curso = estado is not EstadoProyecto.PUBLICADA
    if en_curso:
        duracion[fase] = duracion.get(fase, 0) + _segundos(inicio, ahora)
    total = _segundos(creado, ahora if en_curso or fin_total is None else leer_instante(fin_total))
    orden_de_fase = list(EstadoProyecto)
    fases = [
        MetricaFase(
            fase=f,
            entradas=entradas[f],
            duracion_s=duracion.get(f, 0),
            en_curso=en_curso and f is fase,
        )
        for f in sorted(entradas, key=orden_de_fase.index)
    ]
    return fases, total


def leer_metricas(proyecto: Proyecto, ahora: datetime) -> Metricas:
    with _lectura(proyecto.conexion) as conexion:
        fila = conexion.execute("SELECT * FROM proyecto WHERE id = 1").fetchone()
        estado = EstadoProyecto(fila["estado"])
        total = conexion.execute(f"SELECT {_AGREGADOS} FROM orden").fetchone()
        agentes = conexion.execute(
            f"SELECT agente, {_AGREGADOS}, "
            "json_group_array(DISTINCT json_extract(metadatos, '$.modelo')) AS modelos "
            "FROM orden GROUP BY agente ORDER BY min(id)"
        ).fetchall()
        capitulos = conexion.execute(
            f"SELECT capitulo, {_AGREGADOS}, "
            "(SELECT count(DISTINCT version) FROM capitulo_version v "
            " WHERE v.capitulo = orden.capitulo) AS versiones "
            "FROM orden WHERE capitulo IS NOT NULL GROUP BY capitulo ORDER BY capitulo"
        ).fetchall()
        verificadores = conexion.execute(
            "SELECT verificador, count(*) AS informes, "
            "coalesce(sum(json_array_length(hallazgos)), 0) AS hallazgos, "
            "coalesce(sum(severidad IN ('alta', 'bloqueante')), 0) AS graves "
            "FROM informe GROUP BY verificador ORDER BY verificador"
        ).fetchall()
        ultima = conexion.execute(
            "SELECT evaluacion, version_novela, ciclo FROM informe_juez WHERE revisor = 'juez' "
            "ORDER BY momento DESC, id DESC LIMIT 1"
        ).fetchone()
        puntuaciones = (
            conexion.execute(
                "SELECT criterio, puntuacion FROM informe_juez WHERE evaluacion = ? ORDER BY id",
                (ultima["evaluacion"],),
            ).fetchall()
            if ultima is not None
            else []
        )
        cambios = conexion.execute(
            "SELECT count(*) AS pedidos, "
            "coalesce(sum(estado = 'publicado'), 0) AS publicados, "
            "coalesce(sum(estado IN ('rechazado', 'obsoleto')), 0) AS rechazados, "
            "coalesce(sum(estado = 'fallido'), 0) AS fallidos, "
            "(SELECT count(*) FROM trabajo WHERE cambio IS NOT NULL) AS regeneraciones "
            "FROM cambio_lector"
        ).fetchone()
        versiones = int(conexion.execute("SELECT count(*) FROM version_novela").fetchone()[0])
        fases, duracion = _fases(conexion, fila["creado"], estado, ahora)

    return Metricas(
        resumen=Resumen(
            estado=estado,
            creado=fila["creado"],
            duracion_s=duracion,
            intentos=_intentos(total),
            consumo=_consumo(total),
            ciclos_revision=int(fila["ciclos_revision"]),
            pasadas_manuscrito=int(fila["pasadas"]),
            versiones_publicadas=versiones,
        ),
        fases=fases,
        agentes=[
            MetricaAgente(
                agente=a["agente"],
                modelos=sorted(m for m in json.loads(a["modelos"]) if isinstance(m, str)),
                intentos=_intentos(a),
                consumo=_consumo(a),
            )
            for a in agentes
        ],
        capitulos=[
            MetricaCapitulo(
                capitulo=int(c["capitulo"]),
                versiones=int(c["versiones"]),
                intentos=_intentos(c),
                consumo=_consumo(c),
            )
            for c in capitulos
        ],
        verificadores=[
            MetricaVerificador(
                verificador=v["verificador"],
                informes=int(v["informes"]),
                hallazgos=int(v["hallazgos"]),
                graves=int(v["graves"]),
            )
            for v in verificadores
        ],
        juez=EvaluacionJuez(
            version_novela=int(ultima["version_novela"]),
            ciclo=int(ultima["ciclo"]),
            puntuaciones=[
                PuntuacionJuez(criterio=p["criterio"], puntuacion=int(p["puntuacion"]))
                for p in puntuaciones
            ],
        )
        if ultima is not None
        else None,
        cambios=Cambios(
            pedidos=int(cambios["pedidos"]),
            publicados=int(cambios["publicados"]),
            rechazados=int(cambios["rechazados"]),
            fallidos=int(cambios["fallidos"]),
            regeneraciones=int(cambios["regeneraciones"]),
        ),
    )
