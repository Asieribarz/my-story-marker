"""Qué hace el backend con el resultado de cada agente, y qué entrada lleva cada orden.

Registros por agente, para que cada paso del plan añada lo suyo sin tocar la máquina ni la
persistencia:

- Los manejadores (`Manejador`): validan el resultado contra el esquema de salida del agente
  (RF-77a), lo persisten en su rebanada si procede y devuelven el desenlace. Escriben
  **solo** datos de su rebanada: el estado del grafo y los contadores los escribe
  `persistencia.py` con lo que calcula `maquina.aplicar_desenlace`. Corren dentro de la
  transacción del registro, así que sus escrituras, el cierre de la orden y la transición
  van juntos o no van. Cada rebanada con agentes expone los suyos en
  `<rebanada>/manejadores.py` como `MANEJADORES: Mapping[Agente, Manejador]`, y
  `manejador_de` los agrega (ver `_de_las_rebanadas`). Los de `extractor-hechos` y
  `agente-contexto` viven aquí, en `MANEJADORES`, que además es donde las pruebas
  sustituyen uno: manda sobre los de las rebanadas.
- `CONSTRUCTORES_DE_ENTRADA`: completa la entrada de una orden al emitirla, dentro de la
  transacción que la persiste. Es donde el Extractor recibe el identificador de un solo uso
  de `/mcp/entrada` en vez del texto libre (RF-14), el Escritor las rutas de su prompt en
  partes (§4.1.4) y el Bibliotecario empieza sin lo escrito antes para su capítulo (B-16).
  Si la orden no se puede emitir, el constructor lanza `OrdenNoEmitible` con su causa, y la
  decisión es `error` (AJ-5).
- `RENOVACION_DE_ENTRADA`: al devolver otra vez la orden vigente, dice si su entrada todavía
  se puede entregar. Si no —su identificador de un solo uso ya se canjeó o está a punto de
  caducar—, da la entrada nueva: la persistencia la escribe en la misma orden, que conserva
  su id, su agente y su intento (RF-08a), y la devuelve. Si sirve, la orden va idéntica.

Un agente sin manejador da `AgenteSinEsquema` con el paso en que llega; la orden sigue
vigente y no gasta intento (Q8).
"""

import importlib
import json
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from backend.contexto.persistencia import guardar_contexto
from backend.contexto.validacion import puede_salir_de_contexto, validar
from backend.intake.entrada import IdentificadorEmitido, emitir_texto_libre, entregable, retirar
from backend.intake.persistencia import (
    guardar_normalizado,
    hechos_confirmados,
    proponer_hechos,
    registrar_extraccion,
)
from backend.planificacion.materializar import materializar_contexto
from backend.proyecto.abierto import Proyecto, instante
from backend.proyecto.errores import AgenteSinEsquema
from backend.proyecto.maquina import Desenlace, Lanzar
from backend.proyecto.orden import OrdenEmitida
from backend.shared.db import transaccion
from backend.shared.tipos import Agente, EstadoProyecto, RecursoEntrada

# Q8: en qué paso de specs/plan-backend-v1.md llega el esquema de salida de cada agente.
PASO_QUE_LO_TRAE: dict[Agente, str] = {
    Agente.PLANIFICADOR: "paso 4",
    Agente.ESCALETISTA: "paso 4",
    Agente.ESCRITOR: "paso 7",
    Agente.EDITOR_ESTILO: "paso 7",
    Agente.JUEZ_CAPITULO: "paso 7",
    Agente.BIBLIOTECARIO: "paso 8",
    Agente.JUEZ_MANUSCRITO: "paso 8a",
    Agente.REVISOR: "paso 8a",
    Agente.EXPORTADOR: "paso 9",
    Agente.INTERPRETE_CAMBIOS: "paso 9a",
}


@dataclass(frozen=True)
class ContextoManejo:
    proyecto: Proyecto
    orden: OrdenEmitida
    ahora: datetime

    @property
    def conexion(self) -> sqlite3.Connection:
        return self.proyecto.conexion

    @property
    def momento(self) -> str:
        return instante(self.ahora)


@dataclass(frozen=True)
class Salida:
    """Lo que devuelve un manejador: el desenlace y su informe, que va a `orden.detalle` y
    es la entrada del intento siguiente si lo hay. Sin valores de datos excluidos (RF-13)."""

    desenlace: Desenlace
    detalle: dict[str, Any] = field(default_factory=dict)


Manejador = Callable[[ContextoManejo, object], Salida]
"""Registra el resultado de la orden `contexto.orden` y devuelve su `Salida`.

El segundo argumento es la salida ya extraída de `salida_cruda` por el cerebro (§4.1.7): el
Markdown como `str`, sin la línea del sello, para Escritor, Editor y Revisor; el valor del
bloque JSON para el resto. El manejador la valida contra el esquema de su agente: si no
encaja, devuelve `Desenlace.forma()` —o `Desenlace.contenido()` si es el Escritor— con los
errores en `detalle`, y no persiste nada (RF-77a). No lanza por una salida mal formada.
"""

MANEJADORES: dict[Agente, Manejador] = {}


def manejador(agente: Agente) -> Callable[[Manejador], Manejador]:
    def registrar(funcion: Manejador) -> Manejador:
        MANEJADORES[agente] = funcion
        return funcion

    return registrar


# Las rebanadas del bloque 3 con agentes: `verificacion` (juez de manuscrito), `exportacion`
# (Exportador) y `cambio` (Intérprete).
REBANADAS_DEL_BLOQUE_3 = ("verificacion", "exportacion", "cambio")


def _manejadores_de(rebanada: str) -> Mapping[Agente, Manejador]:
    """Los `MANEJADORES` de `backend/<rebanada>/manejadores.py`. Una rebanada que todavía no
    existe no aporta ninguno —su agente da `AgenteSinEsquema` (Q8)—; cualquier otro error al
    importarla se propaga."""
    modulo = f"backend.{rebanada}.manejadores"
    try:
        importado = importlib.import_module(modulo)
    except ModuleNotFoundError as error:
        if error.name not in (f"backend.{rebanada}", modulo):
            raise
        return {}
    suyos: Mapping[Agente, Manejador] = importado.MANEJADORES
    return suyos


def _de_las_rebanadas() -> dict[Agente, Manejador]:
    """Los `MANEJADORES` de cada rebanada con agentes, en uno. Se importan aquí dentro y no
    arriba porque cada rebanada importa de este módulo `Manejador`, `ContextoManejo` y
    `Salida`. Un agente con manejador en dos rebanadas es un error de construcción."""
    from backend.capitulo import manejadores as capitulo
    from backend.escaleta import manejadores as escaleta
    from backend.planificacion import manejadores as planificacion

    agregados: dict[Agente, Manejador] = {}
    rebanadas: tuple[Mapping[Agente, Manejador], ...] = (
        planificacion.MANEJADORES,
        escaleta.MANEJADORES,
        capitulo.MANEJADORES,
        *(_manejadores_de(nombre) for nombre in REBANADAS_DEL_BLOQUE_3),
    )
    for suyos in rebanadas:
        repetidos = agregados.keys() & suyos.keys()
        if repetidos:
            raise RuntimeError(f"agentes con manejador en dos rebanadas: {sorted(repetidos)}")
        agregados.update(suyos)
    return agregados


def manejador_de(agente: Agente) -> Manejador:
    encontrado = MANEJADORES.get(agente) or _de_las_rebanadas().get(agente)
    if encontrado is None:
        raise AgenteSinEsquema(agente, PASO_QUE_LO_TRAE.get(agente, "un paso posterior"))
    return encontrado


@dataclass(frozen=True)
class SolicitudEntrada:
    proyecto: Proyecto
    estado: EstadoProyecto
    lanzar: Lanzar
    ahora: datetime
    # El informe del intento fallido inmediatamente anterior, si la orden es un reintento.
    informe_anterior: object | None = None


class OrdenNoEmitible(Exception):
    """AJ-5, TC-3: la orden que toca no se puede emitir. La persistencia no la guarda y la
    decisión es `error` con `causa`; el estado no cambia y no se gasta intento."""

    def __init__(self, causa: str, capitulo: int | None, detalle: Mapping[str, Any]) -> None:
        super().__init__(causa)
        self.causa = causa
        self.capitulo = capitulo
        self.detalle = dict(detalle)


ConstructorEntrada = Callable[[SolicitudEntrada, dict[str, Any]], dict[str, Any]]

CONSTRUCTORES_DE_ENTRADA: dict[Agente, ConstructorEntrada] = {}


def constructor_de_entrada(agente: Agente) -> Callable[[ConstructorEntrada], ConstructorEntrada]:
    def registrar(funcion: ConstructorEntrada) -> ConstructorEntrada:
        CONSTRUCTORES_DE_ENTRADA[agente] = funcion
        return funcion

    return registrar


def construir_entrada(solicitud: SolicitudEntrada) -> dict[str, Any]:
    """La entrada base —qué necesita el agente y el informe anterior— más lo que añada el
    constructor de su agente. Corre dentro de la transacción que persiste la orden."""
    lanzar = solicitud.lanzar
    base: dict[str, Any] = {
        "estado": solicitud.estado.value,
        "agente": lanzar.agente.value,
        "capitulo": lanzar.capitulo,
        "intento": lanzar.intento,
        "necesita": [e.value for e in lanzar.entrada],
        "informe_anterior": solicitud.informe_anterior,
    }
    constructor = CONSTRUCTORES_DE_ENTRADA.get(lanzar.agente)
    return base if constructor is None else constructor(solicitud, base)


@dataclass(frozen=True)
class FasePrevia:
    """TC-4, M-27: trabajo largo que una orden necesita hecho antes de emitirse —hoy, Lean
    para el juez de manuscrito— y que no puede correr dentro del `BEGIN IMMEDIATE` de la
    emisión. La persistencia pregunta `pendiente` en su transacción; si lo está, la cierra,
    llama a `ejecutar` sin transacción y vuelve a emitir. `ejecutar` puede lanzar
    `OrdenNoEmitible` (la decisión es `error`)."""

    pendiente: Callable[[Proyecto], bool]
    ejecutar: Callable[[Proyecto], None]


FASES_PREVIAS: dict[Agente, FasePrevia] = {}

# Devuelve la entrada nueva de la orden vigente, o `None` si la que tiene aún se entrega.
RenovadorEntrada = Callable[[ContextoManejo], dict[str, Any] | None]

RENOVACION_DE_ENTRADA: dict[Agente, RenovadorEntrada] = {}


def renovacion_de_entrada(agente: Agente) -> Callable[[RenovadorEntrada], RenovadorEntrada]:
    def registrar(funcion: RenovadorEntrada) -> RenovadorEntrada:
        RENOVACION_DE_ENTRADA[agente] = funcion
        return funcion

    return registrar


def entrada_renovada(contexto: ContextoManejo) -> dict[str, Any] | None:
    """La entrada nueva de la orden vigente si la suya ya no se puede entregar. Corre dentro
    de la transacción de emisión. Sin renovador, la entrada no caduca nunca: `None`."""
    renovador = RENOVACION_DE_ENTRADA.get(contexto.orden.agente)
    return None if renovador is None else renovador(contexto)


def _errores(error: ValidationError) -> list[str]:
    """Ruta y mensaje de cada error, sin el valor recibido: puede ser un dato excluido."""
    return [
        f"{'.'.join(str(parte) for parte in e['loc']) or '(raíz)'}: {e['msg']}"
        for e in error.errors(include_url=False)
    ]


# ─── extractor-hechos ────────────────────────────────────────────────────────


class SalidaExtractor(BaseModel):
    """RF-15, RF-77a: el sobre de la salida del Extractor. Cada hecho se valida después,
    uno a uno, contra definitions.md §9: uno que no encaja se rechaza sin tumbar al resto."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hechos: list[Any]


@constructor_de_entrada(Agente.EXTRACTOR_HECHOS)
def _entrada_del_extractor(solicitud: SolicitudEntrada, base: dict[str, Any]) -> dict[str, Any]:
    """RF-14: el texto libre no va en la orden. Va un identificador de un solo uso, emitido en
    la transacción que persiste la orden, que el Extractor canjea por `/mcp/entrada`."""
    proyecto = solicitud.proyecto
    emitido = emitir_texto_libre(proyecto.conexion, proyecto.disposicion, solicitud.ahora)
    return {**base, RecursoEntrada.TEXTO_LIBRE.value: emitido.como_entrada()}


def _renovar(
    contexto: ContextoManejo,
    recurso: RecursoEntrada,
    emitir: Callable[[Proyecto, datetime], IdentificadorEmitido],
) -> dict[str, Any] | None:
    """RF-14, RF-120, RNF-01: la orden vigente del Extractor o del Intérprete se entrega con
    un identificador que se pueda canjear. El que lleva deja de valer si ya se canjeó —el
    subagente que lo hizo murió con su sesión—, si caduca antes de que el relanzado llegue a
    usarlo o si se retiró al volver a sellar la orden (AJ-4); entonces se retira y va uno
    nuevo en la misma orden."""
    entrada = contexto.orden.entrada
    actual = entrada.get(recurso.value)
    identificador = actual.get("identificador") if isinstance(actual, dict) else None
    if isinstance(identificador, str):
        if entregable(contexto.conexion, identificador, contexto.ahora):
            return None
        retirar(contexto.conexion, identificador)
    emitido = emitir(contexto.proyecto, contexto.ahora)
    return {**entrada, recurso.value: emitido.como_entrada()}


def _emitir_texto_libre(proyecto: Proyecto, ahora: datetime) -> IdentificadorEmitido:
    return emitir_texto_libre(proyecto.conexion, proyecto.disposicion, ahora)


@renovacion_de_entrada(Agente.EXTRACTOR_HECHOS)
def _renovar_texto_libre(contexto: ContextoManejo) -> dict[str, Any] | None:
    return _renovar(contexto, RecursoEntrada.TEXTO_LIBRE, _emitir_texto_libre)


@manejador(Agente.EXTRACTOR_HECHOS)
def _extractor_de_hechos(contexto: ContextoManejo, resultado: object) -> Salida:
    try:
        salida = SalidaExtractor.model_validate(resultado)
    except ValidationError as error:
        return Salida(Desenlace.forma(), {"errores": _errores(error)})
    propuesta = proponer_hechos(contexto.conexion, list(salida.hechos), contexto.momento)
    registrar_extraccion(contexto.conexion, contexto.orden.id)
    return Salida(
        Desenlace.aceptado(),
        {
            "aceptados": list(propuesta.aceptados),
            "rechazados": [[indice, motivo] for indice, motivo in propuesta.rechazados],
            "descartes": [{"tipo": d.tipo, "campo": d.campo} for d in propuesta.descartes],
        },
    )


# ─── agente-contexto ─────────────────────────────────────────────────────────


@manejador(Agente.AGENTE_CONTEXTO)
def _agente_de_contexto(contexto: ContextoManejo, resultado: object) -> Salida:
    """En `intake` normaliza el brief (RF-11); en `contexto` instancia la ontología.

    El contexto se valida con el `hoy` del instante inyectado. Con un hallazgo bloqueante
    no se persiste (RF-22): es un fallo de contenido y el informe va al intento siguiente.
    Sin contexto persistido, la transición a `planificacion` no se deriva (V-20).
    """
    if contexto.orden.estado is EstadoProyecto.INTAKE:
        if not isinstance(resultado, dict) or not resultado:
            return Salida(Desenlace.forma(), {"errores": ["(raíz): un objeto no vacío"]})
        descartes = guardar_normalizado(contexto.conexion, resultado, contexto.momento)
        return Salida(
            Desenlace.aceptado(),
            {"descartes": [{"tipo": d.tipo, "campo": d.campo} for d in descartes]},
        )
    informe = validar(resultado, contexto.ahora.astimezone(UTC).date())
    if not puede_salir_de_contexto(informe):
        return Salida(
            Desenlace.contenido(),
            {
                "hallazgos": [h.model_dump(mode="json") for h in informe.hallazgos],
                "rellenados": list(informe.rellenados),
            },
        )
    try:
        with transaccion(contexto.conexion) as conexion:
            guardar_contexto(conexion, informe, contexto.momento)
            if informe.contexto is not None:
                # B-1: al salir de `contexto`, lo que fija el contexto entra en la biblia.
                materializar_contexto(conexion, informe.contexto, contexto.momento)
    except ValueError as error:
        return Salida(Desenlace.contenido(), {"errores": [f"(raíz): {error}"]})
    return Salida(Desenlace.aceptado(), {"rellenados": list(informe.rellenados)})


@constructor_de_entrada(Agente.AGENTE_CONTEXTO)
def _entrada_del_agente_de_contexto(
    solicitud: SolicitudEntrada, base: dict[str, Any]
) -> dict[str, Any]:
    """RF-11: el brief, su normalización y los hechos confirmados van en la orden, como las
    notas del planificador: `/mcp/lectura` no los expone. El texto libre no va nunca (RF-14):
    solo los hechos que el Extractor sacó de él y el comprador confirmó."""
    from backend.proyecto.maquina import Entrada

    conexion = solicitud.proyecto.conexion
    necesita = base["necesita"]
    entrada = dict(base)
    fila = conexion.execute("SELECT respuestas, normalizado FROM brief WHERE id = 1").fetchone()
    if Entrada.BRIEF.value in necesita:
        entrada[Entrada.BRIEF.value] = None if fila is None else json.loads(fila["respuestas"])
    if Entrada.BRIEF_NORMALIZADO.value in necesita:
        normalizado = None if fila is None else fila["normalizado"]
        entrada[Entrada.BRIEF_NORMALIZADO.value] = (
            None if normalizado is None else json.loads(normalizado)
        )
    if Entrada.HECHOS_CONFIRMADOS.value in necesita:
        entrada[Entrada.HECHOS_CONFIRMADOS.value] = [
            {
                clave: valor
                for clave, valor in {
                    "tipo": h["tipo"],
                    "texto": h["texto"],
                    "prioridad": h["prioridad"],
                    "origen": "texto_libre",
                    "momento": h["momento"],
                    "lugar": h["lugar"],
                }.items()
                if valor is not None
            }
            for h in hechos_confirmados(conexion)
        ]
    return entrada


# ─── escritor y bibliotecario: la entrada ────────────────────────────────────


@constructor_de_entrada(Agente.ESCRITOR)
def _entrada_del_escritor(solicitud: SolicitudEntrada, base: dict[str, Any]) -> dict[str, Any]:
    """§4.1.4, RF-50 a RF-59b: el Recuperador guarda el prompt en partes y la orden lleva sus
    rutas absolutas, en orden. Si no cabe (D-9) o la continuidad no lo permite (B-9), la
    orden no se emite: `OrdenNoEmitible` con la causa del Recuperador (AJ-5)."""
    from backend.capitulo.ensamblado import ErrorEnsamblado, preparar_prompt

    numero = solicitud.lanzar.capitulo
    if numero is None:
        raise ValueError("una orden del Escritor sin capítulo")
    proyecto = solicitud.proyecto
    version = _version_del_escritor(proyecto.conexion, numero, solicitud.lanzar.intento)
    informe = solicitud.informe_anterior
    texto = (
        informe
        if informe is None or isinstance(informe, str)
        else json.dumps(informe, ensure_ascii=False, sort_keys=True)
    )
    try:
        preparado = preparar_prompt(
            proyecto.conexion,
            proyecto.disposicion,
            numero,
            version,
            solicitud.lanzar.intento,
            texto,
            instante(solicitud.ahora),
        )
    except ErrorEnsamblado as error:
        raise OrdenNoEmitible(error.causa, numero, error.detalle) from error
    return {
        **base,
        "version": version,
        "rutas_prompt": [str(ruta.resolve()) for ruta in preparado.rutas_partes],
        "tokens_estimados": preparado.tokens_estimados,
    }


@constructor_de_entrada(Agente.BIBLIOTECARIO)
def _entrada_del_bibliotecario(solicitud: SolicitudEntrada, base: dict[str, Any]) -> dict[str, Any]:
    """B-16: al emitir su orden se borra lo escrito antes para ese capítulo, así que un
    Bibliotecario repetido no duplica la biblia. Lee el texto vigente de la versión en curso."""
    from backend.capitulo.biblia import borrar_lo_escrito

    if solicitud.lanzar.capitulo is not None:
        borrar_lo_escrito(solicitud.proyecto.conexion, solicitud.lanzar.capitulo)
    return _con_texto_a_leer(solicitud, base, "editado")


@constructor_de_entrada(Agente.EDITOR_ESTILO)
def _entrada_del_editor(solicitud: SolicitudEntrada, base: dict[str, Any]) -> dict[str, Any]:
    """RF-60, §3 punto 2: el Editor lee el borrador del último intento del Escritor."""
    return _con_texto_a_leer(solicitud, base, "borrador")


@constructor_de_entrada(Agente.JUEZ_CAPITULO)
def _entrada_del_juez(solicitud: SolicitudEntrada, base: dict[str, Any]) -> dict[str, Any]:
    """B-15: el juez lee el texto editado del último intento, el que dejó el Editor."""
    return _con_texto_a_leer(solicitud, base, "editado")


@constructor_de_entrada(Agente.REVISOR)
def _entrada_del_revisor(solicitud: SolicitudEntrada, base: dict[str, Any]) -> dict[str, Any]:
    """§3 punto 7: el Revisor de un capítulo corrige su versión vigente (la aprobada), no un
    intento suyo rechazado ni el de un cambio fallido. Lleva el manuscrito, el informe de
    los gates de la pasada en curso y, si la revisión viene de «cambios» en
    `aprobacion_final`, sus notas (M-6)."""
    conexion = solicitud.proyecto.conexion
    entrada = _con_texto_a_leer(solicitud, base, "editado", vigente=True)
    entrada = {**entrada, "manuscrito": _manuscrito(conexion), "informe_gates": _gates(conexion)}
    if not any(g["ok"] is False for g in entrada["informe_gates"]["gates"].values()):
        fila = conexion.execute(
            "SELECT notas FROM decision_humana WHERE tipo = 'aprobacion_final' "
            "AND decision = 'cambios' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if fila is not None:
            entrada["notas"] = fila["notas"]
    return entrada


def _manuscrito(conexion: sqlite3.Connection) -> list[dict[str, Any]]:
    """RF-113, RF-90: dónde está el manuscrito, para leerlo con `leer_capitulo`: la versión
    vigente aprobada de cada capítulo que la tenga, con su intento y etapa."""
    filas = conexion.execute(
        "SELECT c.numero, v.version, v.intento FROM capitulo c JOIN capitulo_version v "
        "ON v.id = (SELECT max(id) FROM capitulo_version WHERE capitulo = c.numero "
        "AND version = c.version_vigente AND estado = 'aprobado') ORDER BY c.numero"
    ).fetchall()
    return [
        {
            "capitulo": f["numero"],
            "version": f["version"],
            "intento": f["intento"],
            "etapa": "editado",
        }
        for f in filas
    ]


def _gates(conexion: sqlite3.Connection) -> dict[str, Any]:
    """AJ-2, RF-113: el informe de los gates de la pasada en curso —el detalle de cada fila de
    `gate_resultado`— y las justificaciones del juez de manuscrito (`informe_juez`)."""
    pasada = int(conexion.execute("SELECT pasadas FROM proyecto WHERE id = 1").fetchone()[0])
    gates: dict[str, Any] = {}
    evaluacion = None
    for f in conexion.execute(
        "SELECT gate, ok, detalle FROM gate_resultado WHERE pasada = ? ORDER BY gate", (pasada,)
    ):
        detalle = json.loads(f["detalle"])
        gates[f["gate"]] = {"ok": bool(f["ok"]), "detalle": detalle}
        if f["gate"] == "juez":
            evaluacion = detalle.get("evaluacion")
    juez = [
        {
            "criterio": f["criterio"],
            "puntuacion": f["puntuacion"],
            "justificacion": f["justificacion"],
        }
        for f in conexion.execute(
            "SELECT criterio, puntuacion, justificacion FROM informe_juez WHERE evaluacion = ? "
            "ORDER BY criterio",
            (evaluacion,),
        )
    ]
    return {"pasada": pasada, "gates": gates, "juez": juez}


def _con_texto_a_leer(
    solicitud: SolicitudEntrada, base: dict[str, Any], etapa: str, *, vigente: bool = False
) -> dict[str, Any]:
    """Qué texto lee el agente con `leer_capitulo` (RF-100): versión, intento del texto y
    etapa. El `intento` de la orden es el del paso; el del texto, el de `capitulo_version`.
    Sin versión registrada (o sin capítulo) la entrada va como está."""
    numero = solicitud.lanzar.capitulo
    if numero is None:
        return base
    filtro = "AND v.version = c.version_vigente AND v.estado = 'aprobado' " if vigente else ""
    fila = solicitud.proyecto.conexion.execute(
        "SELECT v.version, v.intento FROM capitulo_version v JOIN capitulo c "
        f"ON c.numero = v.capitulo WHERE v.capitulo = ? {filtro}ORDER BY v.id DESC LIMIT 1",
        (numero,),
    ).fetchone()
    if fila is None:
        return base
    return {**base, "version": fila["version"], "intento_texto": fila["intento"], "etapa": etapa}


@constructor_de_entrada(Agente.PLANIFICADOR)
def _entrada_del_planificador(solicitud: SolicitudEntrada, base: dict[str, Any]) -> dict[str, Any]:
    """RF-36: con «cambios» en `aprobacion_plan`, el planificador recibe las notas de la última
    decisión en `notas_plan`. Son de quien aprueba, no texto del comprador, y /estado no las
    enseña (`orden.sin_identificadores`)."""
    from backend.proyecto.maquina import Entrada

    if Entrada.NOTAS_PLAN.value not in base["necesita"]:
        return base
    fila = solicitud.proyecto.conexion.execute(
        "SELECT notas FROM decision_humana WHERE tipo = 'aprobacion_plan' "
        "AND decision = 'cambios' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return {**base, Entrada.NOTAS_PLAN.value: None if fila is None else fila["notas"]}


def _version_del_escritor(conexion: sqlite3.Connection, numero: int, intento: int) -> int:
    """La versión que escribe el Escritor en su intento `intento`: la que fijó la
    confirmación del cambio en curso para un capítulo reabierto (AJ-6, `cambio_capitulo`),
    que no pisa la de un cambio fallido anterior; si no, la siguiente a la vigente.

    RF-06, RF-64b: tras «reintentar» el contador vuelve a 1 y ese intento ya existe en esa
    versión; entonces va a la siguiente a la última escrita, para no pisar su prompt, su
    borrador ni sus informes. El intento sigue en 1..3 (esquema y `shared/rutas.py`)."""
    fila = conexion.execute(
        "SELECT coalesce((SELECT cc.version FROM cambio_capitulo cc JOIN cambio_lector cl "
        "ON cl.id = cc.cambio WHERE cl.estado = 'regenerando' AND cc.capitulo = :n), "
        "(SELECT coalesce(version_vigente, 0) + 1 FROM capitulo WHERE numero = :n), 1) "
        "AS version",
        {"n": numero},
    ).fetchone()
    base = int(fila["version"])
    ultima = conexion.execute(
        "SELECT version, intento FROM capitulo_version WHERE capitulo = ? AND version >= ? "
        "ORDER BY id DESC LIMIT 1",
        (numero, base),
    ).fetchone()
    if ultima is None:
        return base
    return int(ultima["version"]) + (0 if int(ultima["intento"]) < intento else 1)


# ─── gates, exportador e intérprete: la entrada (bloque 3) ───────────────────


@constructor_de_entrada(Agente.JUEZ_MANUSCRITO)
def _entrada_del_juez_de_manuscrito(
    solicitud: SolicitudEntrada, base: dict[str, Any]
) -> dict[str, Any]:
    """TC-4, AJ-3: antes de emitir la orden del juez, el backend corre los gates de cobertura
    y Lean de la pasada en curso; el del juez lo escribe su manejador. Es idempotente, así
    que repetir la orden no hace daño. Si falta Lean, `OrdenNoEmitible` con su causa
    (`lean_no_disponible`, TC-3): la decisión es `error` y no se gasta ciclo de revisión."""
    from backend.verificacion.gates import ejecutar_gates

    proyecto = solicitud.proyecto
    fila = proyecto.conexion.execute("SELECT pasadas FROM proyecto WHERE id = 1").fetchone()
    pasada = int(fila["pasadas"])
    ejecutar_gates(proyecto.conexion, proyecto.disposicion, pasada, instante(solicitud.ahora))
    return {**base, "pasada": pasada, "manuscrito": _manuscrito(proyecto.conexion)}


def _gates_pendientes_del_juez(proyecto: Proyecto) -> bool:
    from backend.verificacion.gates import gates_pendientes

    fila = proyecto.conexion.execute("SELECT pasadas FROM proyecto WHERE id = 1").fetchone()
    return gates_pendientes(proyecto.conexion, int(fila["pasadas"]))


def _preparar_gates_del_juez(proyecto: Proyecto) -> None:
    from backend.verificacion.gates import preparar_gates

    fila = proyecto.conexion.execute("SELECT pasadas FROM proyecto WHERE id = 1").fetchone()
    preparar_gates(proyecto.conexion, proyecto.disposicion, int(fila["pasadas"]))


FASES_PREVIAS[Agente.JUEZ_MANUSCRITO] = FasePrevia(
    _gates_pendientes_del_juez, _preparar_gates_del_juez
)


@constructor_de_entrada(Agente.EXPORTADOR)
def _entrada_del_exportador(solicitud: SolicitudEntrada, base: dict[str, Any]) -> dict[str, Any]:
    """TC-3, TC-6: el Exportador solo se lanza si se podrá imprimir el PDF al publicar. Si
    falta Chromium, `OrdenNoEmitible` con `pdf_no_disponible`."""
    from backend.exportacion.pdf import comprobar_pdf

    comprobar_pdf()
    return {**base, "manuscrito": _manuscrito(solicitud.proyecto.conexion)}


def _emitir_peticion(proyecto: Proyecto, ahora: datetime) -> IdentificadorEmitido:
    from backend.cambio.entrada import emitir_peticion

    try:
        return emitir_peticion(proyecto.conexion, proyecto.disposicion, ahora)
    except LookupError as error:
        raise OrdenNoEmitible("peticion_no_disponible", None, {"requisito": "RF-120"}) from error


@constructor_de_entrada(Agente.INTERPRETE_CAMBIOS)
def _entrada_del_interprete(solicitud: SolicitudEntrada, base: dict[str, Any]) -> dict[str, Any]:
    """RF-120: la petición del lector no va en la orden. Va un identificador de un solo uso,
    emitido en la transacción que persiste la orden, que el Intérprete canjea por
    `/mcp/entrada`, igual que el Extractor con el texto libre (RF-14)."""
    emitido = _emitir_peticion(solicitud.proyecto, solicitud.ahora)
    return {**base, RecursoEntrada.PETICION.value: emitido.como_entrada()}


@renovacion_de_entrada(Agente.INTERPRETE_CAMBIOS)
def _renovar_peticion(contexto: ContextoManejo) -> dict[str, Any] | None:
    """El renovador del Intérprete: al pedir otra vez su orden y al volver a sellarla (AJ-4).
    Sin cambio que interpretar no hay petición que renovar: la orden va como está."""
    interpretando = contexto.conexion.execute(
        "SELECT 1 FROM cambio_lector WHERE estado = 'interpretando'"
    ).fetchone()
    if interpretando is None:
        return None
    return _renovar(contexto, RecursoEntrada.PETICION, _emitir_peticion)
