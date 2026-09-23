"""Persistencia del grafo (RF-01 a RF-09b): la base es el estado, la sesión no guarda nada.

Toda escritura va en una transacción con lo que la provoca:

- **Emitir** (RF-03, RF-08a): la orden se persiste antes de devolverse, junto con las
  transiciones derivadas que la preceden. Con una vigente, se devuelve esa misma; si su
  identificador de un solo uso ya no se puede entregar (RF-14), la misma orden lleva uno
  nuevo, sin cambiar de id ni gastar intento.
- **Registrar** (RF-06, RF-08a): el manejador del agente, el cierre de la orden, los
  contadores y la transición con su fila de historial van juntos. El mismo resultado para
  la misma orden devuelve lo ya registrado; uno para otra orden se rechaza. Un resultado
  fuera de JSON estricto es un intento fallido de forma (RF-77a).
- **Decidir**: la acción humana, su fila en `decision_humana` y la transición.
- **Reiniciar el paso**: una acción del comprador que cambia la entrada de la fase —volver a
  enviar el brief— cierra la orden vigente sin gastar intento y pone el contador a cero.

Las tres calculan con `maquina.py` sobre la instantánea que leen aquí, y antes de escribir
comprueban cada paso contra la tabla de `transiciones.py`: una transición fuera de ella da
`TransicionInvalida` y la fila no se toca (RF-04).
"""

import hashlib
import json
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.contexto.modelos import VERSION_ONTOLOGIA
from backend.intake.datos_excluidos import depurar
from backend.intake.persistencia import auditar_descartes
from backend.proyecto import json_estricto
from backend.proyecto.abierto import Proyecto, instante
from backend.proyecto.bloqueo import BloqueoVisible, bloqueo_vigente, exigir_bloqueo
from backend.proyecto.errores import (
    BloqueoAjeno,
    DecisionHumanaInvalida,
    OrdenAjena,
    ProyectoEnUso,
    TransicionInvalida,
)
from backend.proyecto.manejadores import (
    ContextoManejo,
    Salida,
    SolicitudEntrada,
    construir_entrada,
    entrada_renovada,
    manejador_de,
)
from backend.proyecto.maquina import (
    TOPE,
    AccionHumana,
    Avance,
    CapituloInstantanea,
    Desenlace,
    Detenida,
    ErrorEnsamblado,
    EsperarHumano,
    Instantanea,
    Lanzar,
    Paso,
    Publicada,
    ResultadoGates,
    TipoDesenlace,
    aplicar_accion_humana,
    aplicar_desenlace,
    resolver,
)
from backend.proyecto.orden import (
    OrdenEmitida,
    orden_de_fila,
    orden_vigente,
    sin_identificadores,
)
from backend.proyecto.transiciones import arista
from backend.shared.db import conectar, crear_base, transaccion
from backend.shared.rutas import DisposicionProyecto, nuevo_identificador
from backend.shared.tipos import Agente, DesenlaceOrden, EstadoCapitulo, EstadoProyecto

Emision = OrdenEmitida | EsperarHumano | Publicada | Detenida | ErrorEnsamblado

# Cómo queda cada acción humana en `decision_humana`. Pedir un cambio no está: lo registra
# la rebanada `cambio/` en `cambio_lector` (paso 9a).
DECISION_DE_ACCION: dict[AccionHumana, tuple[str, str]] = {
    AccionHumana.APROBAR_PLAN: ("aprobacion_plan", "aprobado"),
    AccionHumana.CAMBIOS_PLAN: ("aprobacion_plan", "cambios"),
    AccionHumana.APROBAR_FINAL: ("aprobacion_final", "aprobado"),
    AccionHumana.NOTAS_FINAL: ("aprobacion_final", "cambios"),
    AccionHumana.CONFIRMAR_CAMBIO: ("confirmacion_cambio", "confirmado"),
    AccionHumana.RECHAZAR_CAMBIO: ("confirmacion_cambio", "rechazado"),
    AccionHumana.REINTENTAR: ("reintentar", "reintentar"),
}
_ACCION_DE_DECISION = {valor: accion for accion, valor in DECISION_DE_ACCION.items()}


def accion_de_decision(tipo: str, decision: str) -> AccionHumana:
    """La acción de una decisión tal como la nombra `decision_humana` (RF-36)."""
    accion = _ACCION_DE_DECISION.get((tipo, decision))
    if accion is None:
        raise DecisionHumanaInvalida(f"no hay decisión «{decision}» para «{tipo}»")
    return accion


# ─── Crear, abrir y borrar ───────────────────────────────────────────────────


def crear_proyecto(
    ahora: datetime,
    *,
    parada_plan: bool = False,
    parada_final: bool = False,
    raiz_proyectos: Path | None = None,
) -> Proyecto:
    """RF-01: directorio, base y fila en `intake`, con los 10 capítulos en `pendiente`.

    Las paradas se eligen al crear y están inactivas por defecto (RF-05).
    """
    disposicion = DisposicionProyecto.de(nuevo_identificador(), raiz_proyectos)
    disposicion.crear_directorios()
    conexion: sqlite3.Connection | None = None
    try:
        conexion = crear_base(disposicion.base)
        with transaccion(conexion):
            conexion.execute(
                "INSERT INTO proyecto (id, identificador, version_ontologia, parada_plan, "
                "parada_final, creado) VALUES (1, ?, ?, ?, ?, ?)",
                (
                    disposicion.identificador,
                    VERSION_ONTOLOGIA,
                    int(parada_plan),
                    int(parada_final),
                    instante(ahora),
                ),
            )
            conexion.executemany(
                "INSERT INTO capitulo (numero) VALUES (?)",
                [(n,) for n in range(1, 11)],
            )
    except BaseException:
        if conexion is not None:
            conexion.close()
        shutil.rmtree(disposicion.raiz, ignore_errors=True)
        raise
    return Proyecto(disposicion, conexion)


def borrar_proyecto(proyecto: Proyecto, ahora: datetime) -> None:
    """RF-09a: borra la base y el directorio enteros, o no borra nada. Con un bloqueo vigente
    se deniega (Q7). Cierra la conexión del proyecto.

    El directorio se aparta primero con un renombrado, que no se queda a medias: o se mueve
    entero o sigue en su sitio. En Windows no se puede mover mientras otra conexión tenga la
    base abierta —una petición en curso, un canje de `/mcp/entrada`—: entonces
    `ProyectoEnUso`, y el proyecto queda intacto. Una vez apartado, nadie lo abre por su
    identificador, así que el bloqueo se vuelve a comprobar ahí sin carrera: si alguien lo
    tomó entre la primera comprobación y el renombrado, el directorio vuelve a su sitio.
    """
    vigente = bloqueo_vigente(proyecto.conexion, ahora)
    if vigente is not None:
        raise BloqueoAjeno(vigente.tipo, vigente.caduca)
    proyecto.cerrar()
    original = proyecto.disposicion
    apartada = original.apartada()
    try:
        original.raiz.rename(apartada.raiz)
    except OSError as error:
        raise ProyectoEnUso(original.identificador) from error
    conexion = conectar(apartada.base)
    try:
        tomado = bloqueo_vigente(conexion, ahora)
    finally:
        conexion.close()
    if tomado is not None:
        apartada.raiz.rename(original.raiz)
        raise BloqueoAjeno(tomado.tipo, tomado.caduca)
    shutil.rmtree(apartada.raiz)


# ─── Lectura ─────────────────────────────────────────────────────────────────


@contextmanager
def _lectura(conexion: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Una transacción de lectura: todas las consultas ven el mismo estado de la base."""
    if conexion.in_transaction:
        yield conexion
        return
    conexion.execute("BEGIN")
    try:
        yield conexion
    finally:
        conexion.execute("COMMIT")


@dataclass(frozen=True)
class CapituloLeido:
    numero: int
    estado: EstadoCapitulo
    intentos: int


@dataclass(frozen=True)
class EstadoLeido:
    """RF-02: el estado para la reanudación y el panel. El bloqueo, sin su token; la orden
    vigente, sin sus identificadores de un solo uso (RF-14): solo los recibe quien la pide con
    el token del bloqueo."""

    identificador: str
    estado: EstadoProyecto
    detenida_desde: EstadoProyecto | None
    parada_plan: bool
    parada_final: bool
    ciclos_revision: int
    intentos_paso: int
    capitulos: tuple[CapituloLeido, ...]
    orden_vigente: OrdenEmitida | None
    bloqueo: BloqueoVisible | None
    creado: str


def leer_estado(proyecto: Proyecto, ahora: datetime) -> EstadoLeido:
    with _lectura(proyecto.conexion) as conexion:
        fila = conexion.execute("SELECT * FROM proyecto WHERE id = 1").fetchone()
        capitulos = conexion.execute(
            "SELECT numero, estado, intentos FROM capitulo ORDER BY numero"
        ).fetchall()
        vigente = orden_vigente(conexion)
        bloqueo = bloqueo_vigente(conexion, ahora)
    desde = fila["detenida_desde"]
    return EstadoLeido(
        identificador=fila["identificador"],
        estado=EstadoProyecto(fila["estado"]),
        detenida_desde=EstadoProyecto(desde) if desde is not None else None,
        parada_plan=bool(fila["parada_plan"]),
        parada_final=bool(fila["parada_final"]),
        ciclos_revision=int(fila["ciclos_revision"]),
        intentos_paso=int(fila["intentos_paso"]),
        capitulos=tuple(
            CapituloLeido(int(c["numero"]), EstadoCapitulo(c["estado"]), int(c["intentos"]))
            for c in capitulos
        ),
        orden_vigente=sin_identificadores(vigente) if vigente is not None else None,
        bloqueo=bloqueo,
        creado=fila["creado"],
    )


_AVANCE = """
SELECT
  EXISTS (SELECT 1 FROM brief) AS brief,
  EXISTS (SELECT 1 FROM brief WHERE ruta_texto_libre IS NOT NULL) AS texto_libre,
  EXISTS (SELECT 1 FROM brief WHERE extraccion IS NOT NULL) AS extraccion_hecha,
  EXISTS (SELECT 1 FROM hecho_propuesto WHERE estado = 'pendiente') AS hechos_pendientes,
  EXISTS (SELECT 1 FROM brief WHERE normalizado IS NOT NULL) AS brief_normalizado,
  EXISTS (SELECT 1 FROM contexto) AS contexto_validado,
  EXISTS (SELECT 1 FROM plan) AS plan,
  (SELECT count(*) FROM decision_humana WHERE tipo = 'aprobacion_plan' AND decision = 'cambios')
    AS cambios_plan,
  (SELECT count(*) FROM orden WHERE agente = :arquitecto AND desenlace = 'aceptada')
    AS planes,
  EXISTS (SELECT 1 FROM personaje) AS personajes,
  EXISTS (SELECT 1 FROM localizacion) AND EXISTS (SELECT 1 FROM ruta) AS mundo,
  EXISTS (SELECT 1 FROM guia_estilo) AS guia_estilo,
  (SELECT count(*) FROM ficha_capitulo) AS fichas,
  EXISTS (SELECT 1 FROM cambio_lector WHERE estado = 'propuesto') AS cambio_propuesto,
  EXISTS (SELECT 1 FROM version_novela) AS es_regeneracion
"""

# Un capítulo aprobado está terminado cuando el Bibliotecario registró su biblia después
# del último borrador aceptado del Escritor: una regeneración lo vuelve a abrir.
_CAPITULOS = """
SELECT c.numero, c.estado, c.intentos,
  EXISTS (
    SELECT 1 FROM orden b
    WHERE b.agente = :bibliotecario AND b.capitulo = c.numero AND b.desenlace = 'aceptada'
      AND b.id > coalesce((
        SELECT max(e.id) FROM orden e
        WHERE e.agente = :escritor AND e.capitulo = c.numero AND e.desenlace = 'aceptada'
      ), 0)
  ) AS biblia_registrada
FROM capitulo c ORDER BY c.numero
"""


def _gates(conexion: sqlite3.Connection) -> ResultadoGates:
    """El desenlace de los gates de la pasada en curso. Los evalúa el paso 8a, que leerá
    aquí sus tablas; hasta entonces no hay gates que evaluar."""
    return ResultadoGates.SIN_EVALUAR


def _instantanea(conexion: sqlite3.Connection) -> Instantanea:
    fila = conexion.execute("SELECT * FROM proyecto WHERE id = 1").fetchone()
    a = conexion.execute(_AVANCE, {"arquitecto": Agente.ARQUITECTO.value}).fetchone()
    capitulos = conexion.execute(
        _CAPITULOS,
        {"bibliotecario": Agente.BIBLIOTECARIO.value, "escritor": Agente.ESCRITOR.value},
    ).fetchall()
    vigente = orden_vigente(conexion)
    desde = fila["detenida_desde"]
    return Instantanea(
        estado=EstadoProyecto(fila["estado"]),
        capitulos=tuple(
            CapituloInstantanea(
                numero=int(c["numero"]),
                estado=EstadoCapitulo(c["estado"]),
                intentos=int(c["intentos"]),
                terminado=c["estado"] == EstadoCapitulo.APROBADO and bool(c["biblia_registrada"]),
            )
            for c in capitulos
        ),
        avance=Avance(
            brief=bool(a["brief"]),
            texto_libre=bool(a["texto_libre"]),
            extraccion_hecha=bool(a["extraccion_hecha"]),
            hechos_pendientes=bool(a["hechos_pendientes"]),
            brief_normalizado=bool(a["brief_normalizado"]),
            contexto_validado=bool(a["contexto_validado"]),
            plan=bool(a["plan"]),
            # Cada «cambios» pide un plan más: pendiente hasta que el Arquitecto lo entrega.
            notas_plan_pendientes=a["cambios_plan"] > 0 and a["cambios_plan"] >= a["planes"],
            personajes=bool(a["personajes"]),
            mundo=bool(a["mundo"]),
            guia_estilo=bool(a["guia_estilo"]),
            fichas=int(a["fichas"]),
            gates=_gates(conexion),
            cambio_propuesto=bool(a["cambio_propuesto"]),
            es_regeneracion=bool(a["es_regeneracion"]),
        ),
        detenida_desde=EstadoProyecto(desde) if desde is not None else None,
        parada_plan=bool(fila["parada_plan"]),
        parada_final=bool(fila["parada_final"]),
        ciclos_revision=int(fila["ciclos_revision"]),
        intentos_paso=int(fila["intentos_paso"]),
        orden_vigente=vigente.vigente if vigente is not None else None,
    )


def leer_instantanea(proyecto: Proyecto) -> Instantanea:
    """La instantánea inmutable del estado persistido sobre la que decide `maquina.py`."""
    with _lectura(proyecto.conexion) as conexion:
        return _instantanea(conexion)


# ─── Escritura del grafo ─────────────────────────────────────────────────────


def _persistir(
    conexion: sqlite3.Connection,
    antes: Instantanea,
    despues: Instantanea,
    pasos: tuple[Paso, ...],
    momento: str,
) -> None:
    """Escribe transiciones, fila del proyecto y capítulos. Comprueba la cadena de pasos
    contra la tabla antes de tocar nada (RF-04)."""
    estado = antes.estado
    for paso in pasos:
        if paso.origen is not estado:
            raise TransicionInvalida(paso.origen, paso.destino, paso.causa.value)
        arista(paso.origen, paso.destino, paso.causa)
        estado = paso.destino
    if estado is not despues.estado:
        raise TransicionInvalida(antes.estado, despues.estado, "sin paso por la tabla")
    conexion.executemany(
        "INSERT INTO transicion (momento, origen, destino, causa) VALUES (?, ?, ?, ?)",
        [(momento, p.origen.value, p.destino.value, p.causa.value) for p in pasos],
    )
    conexion.execute(
        "UPDATE proyecto SET estado = ?, detenida_desde = ?, intentos_paso = ?, "
        "ciclos_revision = ? WHERE id = 1",
        (
            despues.estado.value,
            despues.detenida_desde.value if despues.detenida_desde is not None else None,
            despues.intentos_paso,
            despues.ciclos_revision,
        ),
    )
    conexion.executemany(
        "UPDATE capitulo SET estado = ?, intentos = ? WHERE numero = ?",
        [
            (d.estado.value, d.intentos, d.numero)
            for a, d in zip(antes.capitulos, despues.capitulos, strict=True)
            if (a.estado, a.intentos) != (d.estado, d.intentos)
        ],
    )


# ─── Siguiente orden ─────────────────────────────────────────────────────────


def _informe_anterior(
    conexion: sqlite3.Connection, estado: EstadoProyecto, lanzar: Lanzar
) -> object | None:
    """RF-07a y §3.2: un reintento lleva el informe del intento fallido que lo provocó.

    Es el de la última orden con resultado, si se rechazó y es del mismo paso: la misma fase
    y el mismo capítulo. Fuera del bucle, además, del mismo agente; dentro, el Escritor recibe
    el informe de quien rechazó su borrador (el juez, los deterministas). Una orden caducada
    no fue un intento y se salta.
    """
    if lanzar.intento <= 1:
        return None
    fila = conexion.execute(
        "SELECT estado_proyecto, agente, capitulo, desenlace, detalle FROM orden "
        "WHERE desenlace IS NOT ? ORDER BY id DESC LIMIT 1",
        (DesenlaceOrden.CADUCADA.value,),
    ).fetchone()
    if fila is None or fila["desenlace"] != DesenlaceOrden.RECHAZADA:
        return None
    if fila["estado_proyecto"] != estado or fila["capitulo"] != lanzar.capitulo:
        return None
    if lanzar.capitulo is None and fila["agente"] != lanzar.agente:
        return None
    detalle: dict[str, Any] = json.loads(fila["detalle"])
    return detalle.get("informe")


def _emitir(
    proyecto: Proyecto, estado: EstadoProyecto, lanzar: Lanzar, ahora: datetime
) -> OrdenEmitida:
    if not 1 <= lanzar.intento <= TOPE:
        raise AssertionError(f"orden con intento {lanzar.intento}: la máquina respeta el tope")
    conexion = proyecto.conexion
    informe = _informe_anterior(conexion, estado, lanzar)
    entrada = construir_entrada(SolicitudEntrada(proyecto, estado, lanzar, ahora, informe))
    fila = conexion.execute(
        "INSERT INTO orden (estado_proyecto, agente, capitulo, intento, entrada, emitida) "
        "VALUES (?, ?, ?, ?, ?, ?) RETURNING *",
        (
            estado.value,
            lanzar.agente.value,
            lanzar.capitulo,
            lanzar.intento,
            json.dumps(entrada, ensure_ascii=False),
            instante(ahora),
        ),
    ).fetchone()
    return orden_de_fila(fila)


def emitir_siguiente_orden(proyecto: Proyecto, token: str, ahora: datetime) -> Emision:
    """RF-03, RF-08, RF-08a: la siguiente orden, persistida antes de devolverla.

    Exige el token del bloqueo vigente (RF-09b). Con una orden vigente, devuelve esa misma.
    Si su identificador de un solo uso de `/mcp/entrada` ya no se puede entregar —se canjeó,
    o caduca antes de que el subagente relanzado llegue a usarlo (RF-14, RNF-01)—, la misma
    orden lleva uno nuevo: el mismo id, agente e intento, y la entrada se reescribe antes de
    devolverla. Sin vigente, escribe las transiciones derivadas del estado y emite la orden, o
    devuelve esperar al humano, `publicada`, `detenida` o `error_ensamblado`, que no se
    persisten.
    """
    with transaccion(proyecto.conexion) as conexion:
        exigir_bloqueo(conexion, token, ahora)
        vigente = orden_vigente(conexion)
        if vigente is not None:
            renovada = entrada_renovada(ContextoManejo(proyecto, vigente, ahora))
            if renovada is None:
                return vigente
            conexion.execute(
                "UPDATE orden SET entrada = ? WHERE id = ?",
                (json.dumps(renovada, ensure_ascii=False), vigente.id),
            )
            return replace(vigente, entrada=renovada)
        antes = _instantanea(conexion)
        resolucion = resolver(antes)
        if resolucion.pasos:
            _persistir(conexion, antes, resolucion.instantanea, resolucion.pasos, instante(ahora))
        decision = resolucion.decision
        if not isinstance(decision, Lanzar):
            return decision
        return _emitir(proyecto, resolucion.instantanea.estado, decision, ahora)


# ─── Registro de resultados ──────────────────────────────────────────────────


@dataclass(frozen=True)
class Registro:
    """Lo que quedó registrado para una orden. `repetido` si es un reenvío idempotente."""

    orden: int
    agente: Agente
    desenlace: DesenlaceOrden
    tipo: TipoDesenlace
    estado: EstadoProyecto
    capitulo: int | None
    estado_capitulo: EstadoCapitulo | None
    detalle: dict[str, Any]
    repetido: bool = False


def _huella(resultado: object) -> str:
    """La huella del JSON canónico del resultado. `surrogatepass`, porque un resultado fuera
    de JSON estricto también se registra, como intento fallido, y se reconoce al repetirlo."""
    canonico = json.dumps(resultado, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8", errors="surrogatepass")).hexdigest()


def _registro_de_fila(fila: sqlite3.Row, repetido: bool) -> Registro:
    detalle: dict[str, Any] = json.loads(fila["detalle"])
    estado_capitulo = detalle.get("estado_capitulo")
    return Registro(
        orden=int(fila["id"]),
        agente=Agente(fila["agente"]),
        desenlace=DesenlaceOrden(fila["desenlace"]),
        tipo=TipoDesenlace(detalle["tipo"]),
        estado=EstadoProyecto(detalle["estado"]),
        capitulo=fila["capitulo"],
        estado_capitulo=EstadoCapitulo(estado_capitulo) if estado_capitulo else None,
        detalle=detalle["informe"],
        repetido=repetido,
    )


def registrar_resultado(
    proyecto: Proyecto, orden: int, resultado: object, token: str, ahora: datetime
) -> Registro:
    """RF-03, RF-06, RF-08a: registra el resultado de la orden vigente y avanza el grafo.

    - La orden cerrada con el mismo resultado devuelve lo ya registrado, sin escribir.
    - Una orden que no existe, que no es la vigente o que se cerró con otro resultado da
      `OrdenAjena`.
    - Un agente sin esquema de salida todavía da `AgenteSinEsquema`: nada cambia (Q8).
    - Un resultado fuera de JSON estricto —`NaN`, `Infinity`, un sustituto suelto— es un
      intento fallido de forma, sin pasar por el manejador (RF-77a): la base no lo guardaría.
    """
    momento = instante(ahora)
    huella = _huella(resultado)
    with transaccion(proyecto.conexion) as conexion:
        exigir_bloqueo(conexion, token, ahora)
        fila = conexion.execute("SELECT * FROM orden WHERE id = ?", (orden,)).fetchone()
        vigente = orden_vigente(conexion)
        if fila is None:
            raise OrdenAjena(orden, vigente.id if vigente else None, "la orden no existe")
        if fila["cerrada"] is not None:
            detalle = json.loads(fila["detalle"] or "{}")
            if fila["desenlace"] != DesenlaceOrden.CADUCADA and detalle.get("huella") == huella:
                return _registro_de_fila(fila, repetido=True)
            motivo = (
                "la orden caducó sin resultado"
                if fila["desenlace"] == DesenlaceOrden.CADUCADA
                else "la orden ya se cerró con otro resultado"
            )
            raise OrdenAjena(orden, vigente.id if vigente else None, motivo)
        emitida = orden_de_fila(fila)
        manejar = manejador_de(emitida.agente)
        fuera_de_json = json_estricto.infraccion(resultado)
        if fuera_de_json is None:
            salida = manejar(ContextoManejo(proyecto, emitida, ahora), resultado)
        else:
            salida = Salida(Desenlace.forma(), {"errores": [f"(raíz): {fuera_de_json}"]})
        antes = _instantanea(conexion)
        efecto = aplicar_desenlace(antes, emitida.vigente, salida.desenlace)
        informe, descartes = depurar(salida.detalle)
        auditar_descartes(conexion, descartes, "orden.detalle", momento)
        despues = efecto.instantanea
        estado_capitulo = (
            despues.capitulo(emitida.capitulo).estado if emitida.capitulo is not None else None
        )
        aceptada = salida.desenlace.tipo is TipoDesenlace.ACEPTADO
        registro = {
            "huella": huella,
            "tipo": salida.desenlace.tipo.value,
            "guardarrail": salida.desenlace.guardarrail,
            "informe": informe,
            "estado": despues.estado.value,
            "estado_capitulo": estado_capitulo.value if estado_capitulo is not None else None,
        }
        conexion.execute(
            "UPDATE orden SET cerrada = ?, desenlace = ?, detalle = ? WHERE id = ?",
            (
                momento,
                (DesenlaceOrden.ACEPTADA if aceptada else DesenlaceOrden.RECHAZADA).value,
                json.dumps(registro, ensure_ascii=False),
                orden,
            ),
        )
        _persistir(conexion, antes, despues, efecto.pasos, momento)
        cerrada = conexion.execute("SELECT * FROM orden WHERE id = ?", (orden,)).fetchone()
    return _registro_de_fila(cerrada, repetido=False)


# ─── Acciones humanas ────────────────────────────────────────────────────────


def decidir(
    proyecto: Proyecto, accion: AccionHumana, ahora: datetime, notas: str | None = None
) -> EstadoLeido:
    """RF-05, RF-36, RF-64b: la acción humana que saca el proyecto de una parada.

    No exige el bloqueo (Q7). Queda en `decision_humana` y en el historial de transiciones.
    Una orden vigente —no la hay en una parada— se cierra como `caducada`. Las rebanadas que
    añaden efectos propios a una decisión (el cambio del lector, paso 9a) llaman a esta
    función dentro de su transacción.
    """
    momento = instante(ahora)
    with transaccion(proyecto.conexion) as conexion:
        antes = _instantanea(conexion)
        efecto = aplicar_accion_humana(antes, accion)
        if antes.orden_vigente is not None:
            _caducar(conexion, antes.orden_vigente.id, {"accion": accion.value}, momento)
        tipo_y_decision = DECISION_DE_ACCION.get(accion)
        if tipo_y_decision is not None:
            conexion.execute(
                "INSERT INTO decision_humana (momento, tipo, decision, notas) VALUES (?, ?, ?, ?)",
                (momento, *tipo_y_decision, notas),
            )
        _persistir(conexion, antes, efecto.instantanea, efecto.pasos, momento)
    return leer_estado(proyecto, ahora)


def reintentar(proyecto: Proyecto, ahora: datetime, notas: str | None = None) -> EstadoLeido:
    """RF-64b y Q6: desde `detenida`, vuelve a la fase de la que vino."""
    return decidir(proyecto, AccionHumana.REINTENTAR, ahora, notas)


def reiniciar_paso(conexion: sqlite3.Connection, accion: str, momento: str) -> None:
    """RF-07a: una acción del comprador que cambia la entrada de la fase —volver a enviar el
    brief— empieza el paso de nuevo. La orden vigente, que trabajaba con la entrada anterior,
    se cierra como `caducada` sin gastar intento, y `intentos_paso` vuelve a cero: el agente
    que toque ahora no hereda los intentos ni el informe de otro.

    Se llama dentro de la transacción que escribe la acción, tras `exigir_fase`.
    """
    vigente = orden_vigente(conexion)
    if vigente is not None:
        _caducar(conexion, vigente.id, {"accion": accion}, momento)
    conexion.execute("UPDATE proyecto SET intentos_paso = 0 WHERE id = 1")


def exigir_fase(conexion: sqlite3.Connection, fase: EstadoProyecto, accion: str) -> None:
    """Una acción del comprador ajena al grafo —enviar el brief, confirmar hechos— solo cabe
    en su fase; fuera de ella, `TransicionInvalida` y nada se escribe (RF-04).

    Se llama dentro de la transacción que escribe la acción, para que el proyecto no cambie
    de fase entre la comprobación y la escritura.
    """
    fila = conexion.execute("SELECT estado FROM proyecto WHERE id = 1").fetchone()
    estado = EstadoProyecto(fila["estado"])
    if estado is not fase:
        raise TransicionInvalida(estado, None, accion, f"solo se admite en {fase.value}")


def _caducar(
    conexion: sqlite3.Connection, orden: int, detalle: dict[str, str], momento: str
) -> None:
    """Cierra la orden sin resultado porque una acción humana movió el proyecto o cambió su
    entrada. No gasta intento; `detalle` dice qué acción fue."""
    conexion.execute(
        "UPDATE orden SET cerrada = ?, desenlace = ?, detalle = ? WHERE id = ?",
        (momento, DesenlaceOrden.CADUCADA.value, json.dumps(detalle), orden),
    )
