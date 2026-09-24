"""Qué se envía a Langfuse de un proyecto, construido desde su base (E-1). Solo lectura.

**Solo metadatos.** Viajan agentes, modelos, tokens, tiempos, desenlaces, nombres de
herramienta y de validador, severidades y puntuaciones. No viaja nada escrito por el
comprador, el lector o un agente: ni el brief ni el texto libre, ni prompts, capítulos,
hallazgos, justificaciones del juez, argumentos de herramienta ni términos vetados
(architecture.md §10). Ese corte se hace aquí, con listas de campos permitidos, y no en
el cliente.

**Forma.** La sesión es el proyecto. Cada generación es una traza: la primera recoge la
entrevista, la planificación, los capítulos, los gates y la publicación; cada cambio del
lector abre otra a partir de su `creado`. Dentro, un span por capítulo agrupa sus órdenes;
cada orden cerrada es una observación `generation` con el nombre de su rol; cada llamada
MCP, una `tool` bajo la orden de su agente que estaba abierta en ese momento; y el
guardarraíl, la policy y los descartes de datos personales, observaciones propias.

**Identificadores deterministas**, derivados del proyecto y de la fila, y **cada span se
envía una vez**: Langfuse duplica un span reenviado con el mismo id (I-09). Por eso los
padres no dependen de lo que venga después: la raíz de cada traza no tiene duración (la
latencia de la traza la calcula Langfuse con sus observaciones), y el span de un capítulo
es definitivo cuando el Bibliotecario lo aprueba en esa traza. Todos los spans llevan la
sesión y el nombre de la traza, para que se agrupen aunque su padre aún no haya llegado.
"""

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

Valor = str | int | float | bool

ROL: Mapping[str, str] = {
    "agente-contexto": "entrevistador",
    "extractor-hechos": "entrevistador",
    "planificador": "planner",
    "escaletista": "planner",
    "escritor": "writer",
    "revisor": "writer",
    "editor-estilo": "editor",
    "juez-capitulo": "editor",
    "juez-manuscrito": "editor",
    "bibliotecario": "bibliotecario",
    "exportador": "exportador",
    "interprete-cambios": "interprete",
}

# RF-77: con un hallazgo alto o bloqueante, el capítulo vuelve al Escritor.
SEVERIDADES_QUE_BLOQUEAN = frozenset({"alta", "bloqueante"})

_USO: Mapping[str, str] = {
    "tokens_entrada": "input",
    "tokens_salida": "output",
    "tokens_cache_lectura": "cache_read_input_tokens",
    "tokens_cache_creacion": "cache_creation_input_tokens",
}


@dataclass(frozen=True)
class Span:
    id: str
    traza: str
    padre: str | None
    nombre: str
    inicio_ns: int
    fin_ns: int
    atributos: dict[str, Valor] = field(default_factory=dict)
    # Si ya no va a cambiar. Langfuse no reemplaza un span reenviado con el mismo id, lo
    # duplica (I-09): `exportar.py` solo envía los definitivos, y cada uno una vez.
    definitivo: bool = True


@dataclass(frozen=True)
class Score:
    id: str
    traza: str
    observacion: str | None
    nombre: str
    valor: float
    tipo: Literal["BOOLEAN", "NUMERIC"]
    comentario: str | None = None
    metadatos: dict[str, Valor] = field(default_factory=dict)


@dataclass(frozen=True)
class Exportacion:
    sesion: str
    spans: list[Span]
    scores: list[Score]


@dataclass
class _Traza:
    clave: str
    nombre: str
    desde: str | None
    cambio: int | None
    id: str = ""
    raiz: str = ""
    spans: list[Span] = field(default_factory=list)
    capitulos: dict[int, list[Span]] = field(default_factory=dict)


def _hex(proyecto: str, *partes: object, longitud: int = 32) -> str:
    semilla = ":".join([proyecto, *map(str, partes)])
    return hashlib.sha256(semilla.encode()).hexdigest()[:longitud]


def ns(instante: str) -> int:
    """Un instante de la base (`AAAA-MM-DDTHH:MM:SSZ`, UTC) en nanosegundos Unix."""
    momento = datetime.strptime(instante, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    return int(momento.timestamp()) * 1_000_000_000


def _json(texto: str | None) -> dict[str, Any]:
    if not texto:
        return {}
    valor = json.loads(texto)
    return valor if isinstance(valor, dict) else {}


def _meta(**campos: Valor | None) -> dict[str, Valor]:
    return {f"langfuse.observation.metadata.{k}": v for k, v in campos.items() if v is not None}


def _trazas(conexion: sqlite3.Connection, proyecto: str) -> list[_Traza]:
    trazas = [_Traza("generacion", "generacion", None, None)]
    for fila in conexion.execute("SELECT id, creado FROM cambio_lector ORDER BY creado, id"):
        trazas.append(
            _Traza(f"cambio-{fila['id']}", "regeneracion", fila["creado"], int(fila["id"]))
        )
    for traza in trazas:
        traza.id = _hex(proyecto, "traza", traza.clave)
        traza.raiz = _hex(proyecto, "raiz", traza.clave, longitud=16)
    return trazas


def _traza_de(trazas: list[_Traza], momento: str) -> _Traza:
    elegida = trazas[0]
    for traza in trazas[1:]:
        if traza.desde is not None and traza.desde <= momento:
            elegida = traza
    return elegida


def construir(
    conexion: sqlite3.Connection,
    proyecto: str,
    versiones_prompt: Mapping[tuple[str, str], int] | None = None,
) -> Exportacion:
    """Todo lo que hay que enviar del proyecto, tal como está ahora en su base.

    `versiones_prompt` traduce (agente, SHA-256 de su definición) a la versión del prompt
    en Langfuse, para enlazar cada observación con el prompt que la produjo.
    """
    versiones_prompt = versiones_prompt or {}
    trazas = _trazas(conexion, proyecto)
    scores: list[Score] = []
    ordenes: list[tuple[sqlite3.Row, Span]] = []

    for fila in conexion.execute(
        "SELECT id, estado_proyecto, agente, capitulo, intento, emitida, cerrada, desenlace, "
        "detalle, metadatos FROM orden WHERE cerrada IS NOT NULL ORDER BY id"
    ):
        traza = _traza_de(trazas, fila["emitida"])
        metadatos, detalle = _json(fila["metadatos"]), _json(fila["detalle"])
        fin = ns(fila["cerrada"])
        duracion = metadatos.get("duracion_ms")
        inicio = (
            fin - int(duracion) * 1_000_000
            if isinstance(duracion, int) and duracion > 0
            else ns(fila["emitida"])
        )
        agente, rol = fila["agente"], ROL.get(fila["agente"], "agente")
        atributos: dict[str, Valor] = {
            "langfuse.observation.type": "generation" if metadatos.get("modelo") else "span",
            **_meta(
                rol=rol,
                agente=agente,
                orden=int(fila["id"]),
                capitulo=fila["capitulo"],
                intento=int(fila["intento"]),
                desenlace=fila["desenlace"],
                tipo=detalle.get("tipo"),
                estado_proyecto=fila["estado_proyecto"],
                version_prompt=metadatos.get("version_prompt"),
            ),
        }
        if metadatos.get("modelo"):
            atributos["langfuse.observation.model.name"] = str(metadatos["modelo"])
        uso = {
            destino: int(metadatos[origen])
            for origen, destino in _USO.items()
            if isinstance(metadatos.get(origen), int)
        }
        if uso:
            atributos["langfuse.observation.usage_details"] = json.dumps(uso)
        version = versiones_prompt.get((agente, str(metadatos.get("version_prompt"))))
        if version is not None:
            atributos["langfuse.observation.prompt.name"] = agente
            atributos["langfuse.observation.prompt.version"] = version
        if fila["desenlace"] != "aceptada":
            atributos["langfuse.observation.level"] = (
                "ERROR" if fila["desenlace"] == "caducada" else "WARNING"
            )
            atributos["langfuse.observation.status_message"] = str(
                detalle.get("tipo") or fila["desenlace"]
            )
        span = Span(
            _hex(proyecto, "orden", fila["id"], longitud=16),
            traza.id,
            None,
            f"{rol}:{agente}",
            inicio,
            fin,
            atributos,
        )
        if fila["capitulo"] is not None:
            traza.capitulos.setdefault(int(fila["capitulo"]), []).append(span)
        else:
            traza.spans.append(span)
        ordenes.append((fila, span))

        # El esquema de salida de cada rol (RF-77a): un fallo de forma es una salida que
        # no cumple el esquema de su agente. El validador de contexto es el desenlace del
        # Agente de Contexto (RF-24).
        nombre = "validador:contexto" if agente == "agente-contexto" else "esquema_salida"
        valor = (
            detalle.get("tipo") == "aceptado"
            if agente == "agente-contexto"
            else detalle.get("tipo") != "fallo_forma"
        )
        scores.append(
            Score(
                _hex(proyecto, "score", nombre, fila["id"]),
                traza.id,
                span.id,
                nombre,
                1.0 if valor else 0.0,
                "BOOLEAN",
                metadatos={"agente": agente, "orden": int(fila["id"])},
            )
        )

    # Un span por capítulo y traza, que abarca sus órdenes: ahí se suman tokens y tiempo
    # del capítulo. Las órdenes cuelgan de él; las demás, de la raíz. Es definitivo cuando
    # el Bibliotecario ha aprobado el capítulo en esta traza.
    span_capitulo: dict[tuple[str, int], str] = {}
    for traza in trazas:
        for numero, hijos in sorted(traza.capitulos.items()):
            id_capitulo = _hex(proyecto, "capitulo", traza.clave, numero, longitud=16)
            span_capitulo[(traza.id, numero)] = id_capitulo
            traza.spans.append(
                Span(
                    id_capitulo,
                    traza.id,
                    traza.raiz,
                    f"capitulo-{numero:02d}",
                    min(h.inicio_ns for h in hijos),
                    max(h.fin_ns for h in hijos),
                    {"langfuse.observation.type": "span", **_meta(capitulo=numero)},
                    definitivo=any(
                        h.atributos.get("langfuse.observation.metadata.agente") == "bibliotecario"
                        and h.atributos.get("langfuse.observation.metadata.desenlace") == "aceptada"
                        for h in hijos
                    ),
                )
            )
            traza.spans.extend(
                Span(h.id, h.traza, id_capitulo, h.nombre, h.inicio_ns, h.fin_ns, h.atributos)
                for h in hijos
            )

    # Llamadas MCP: bajo la orden abierta de su agente en ese instante, si la hay.
    for fila in conexion.execute(
        "SELECT id, momento, agente, herramienta, argumentos FROM llamada_mcp ORDER BY id"
    ):
        traza = _traza_de(trazas, fila["momento"])
        padre = next(
            (
                span.id
                for orden, span in ordenes
                if orden["agente"] == fila["agente"]
                and orden["emitida"] <= fila["momento"] <= orden["cerrada"]
            ),
            traza.raiz,
        )
        momento = ns(fila["momento"])
        argumentos = sorted(_json(fila["argumentos"]))
        traza.spans.append(
            Span(
                _hex(proyecto, "mcp", fila["id"], longitud=16),
                traza.id,
                padre,
                f"tool:{fila['herramienta']}",
                momento,
                momento,
                {
                    "langfuse.observation.type": "tool",
                    **_meta(agente=fila["agente"], argumentos=",".join(argumentos)),
                },
            )
        )

    # Auditoría: coincidencias del guardarraíl (nivel, nunca el término), decisiones de la
    # policy y descartes de datos personales (tipo, nunca el valor).
    for fila in conexion.execute("SELECT id, momento, tipo, detalle FROM auditoria ORDER BY id"):
        traza = _traza_de(trazas, fila["momento"])
        detalle = _json(fila["detalle"])
        momento = ns(fila["momento"])
        if fila["tipo"] == "guardarrail":
            capitulo = detalle.get("capitulo")
            padre = (
                span_capitulo.get((traza.id, capitulo), traza.raiz)
                if isinstance(capitulo, int)
                else traza.raiz
            )
            nombre, tipo = "guardarrail", "guardrail"
            meta = _meta(
                capitulo=capitulo,
                version=detalle.get("version"),
                intento=detalle.get("intento"),
                nivel=detalle.get("nivel"),
            )
        elif fila["tipo"] == "policy":
            padre, tipo = traza.raiz, "guardrail"
            nombre = f"policy:{detalle.get('decision', 'desconocida')}"
            meta = _meta(herramienta=detalle.get("herramienta"), agente=detalle.get("agente"))
        else:
            padre, tipo, nombre = traza.raiz, "event", str(fila["tipo"])
            meta = _meta(tipo_dato=detalle.get("tipo"), origen=detalle.get("origen"))
        traza.spans.append(
            Span(
                _hex(proyecto, "auditoria", fila["id"], longitud=16),
                traza.id,
                padre,
                nombre,
                momento,
                momento,
                {"langfuse.observation.type": tipo, **meta},
            )
        )

    # Validadores deterministas del capítulo: un informe por verificador y versión.
    for fila in conexion.execute(
        "SELECT i.id, i.verificador, i.severidad, i.hallazgos, i.momento, "
        "cv.capitulo, cv.version, cv.intento "
        "FROM informe i JOIN capitulo_version cv ON cv.id = i.capitulo_version ORDER BY i.id"
    ):
        traza = _traza_de(trazas, fila["momento"])
        severidad = fila["severidad"]
        nombre = f"validador:{fila['verificador']}"
        scores.append(
            Score(
                _hex(proyecto, "score", "informe", fila["id"]),
                traza.id,
                span_capitulo.get((traza.id, int(fila["capitulo"]))),
                nombre,
                0.0 if severidad in SEVERIDADES_QUE_BLOQUEAN else 1.0,
                "BOOLEAN",
                f"severidad: {severidad or 'ninguna'} · hallazgos: "
                f"{len(json.loads(fila['hallazgos']))}",
                {
                    "capitulo": int(fila["capitulo"]),
                    "version": int(fila["version"]),
                    "intento": int(fila["intento"]),
                },
            )
        )

    # Gates de manuscrito (cobertura, Lean, juez) por pasada. La pasada p empieza en la
    # p-ésima entrada en `verificacion_manuscrito` (AJ-3).
    entradas = [
        fila["momento"]
        for fila in conexion.execute(
            "SELECT momento FROM transicion WHERE destino = 'verificacion_manuscrito' ORDER BY id"
        )
    ]
    for fila in conexion.execute("SELECT pasada, gate, ok FROM gate_resultado ORDER BY pasada"):
        pasada = int(fila["pasada"])
        entrada = entradas[pasada - 1] if pasada <= len(entradas) else None
        traza = _traza_de(trazas, entrada) if entrada else trazas[-1]
        scores.append(
            Score(
                _hex(proyecto, "score", "gate", pasada, fila["gate"]),
                traza.id,
                None,
                f"gate:{fila['gate']}",
                float(fila["ok"]),
                "BOOLEAN",
                metadatos={"pasada": pasada},
            )
        )

    # Juez de manuscrito y revisión humana, criterio a criterio (RF-113, RF-114). La
    # justificación no viaja: cita el texto de la novela.
    for fila in conexion.execute(
        "SELECT id, evaluacion, version_novela, revisor, ciclo, criterio, puntuacion, momento "
        "FROM informe_juez ORDER BY id"
    ):
        traza = _traza_de(trazas, fila["momento"])
        scores.append(
            Score(
                _hex(proyecto, "score", "juez", fila["id"]),
                traza.id,
                None,
                f"{fila['revisor']}:{fila['criterio']}",
                float(fila["puntuacion"]),
                "NUMERIC",
                metadatos={
                    "evaluacion": str(fila["evaluacion"]),
                    "version_novela": int(fila["version_novela"]),
                    "ciclo": int(fila["ciclo"]),
                },
            )
        )

    spans: list[Span] = []
    for traza in trazas:
        if not traza.spans:
            continue
        de_la_raiz: dict[str, Valor] = {
            "langfuse.session.id": proyecto,
            "langfuse.trace.name": traza.nombre,
            "langfuse.observation.type": "agent",
            "langfuse.trace.metadata.proyecto": proyecto,
        }
        if traza.cambio is not None:
            de_la_raiz["langfuse.trace.metadata.cambio"] = traza.cambio
        inicio = min(s.inicio_ns for s in traza.spans)
        spans.append(Span(traza.raiz, traza.id, None, traza.nombre, inicio, inicio, de_la_raiz))
        de_la_traza = {"langfuse.session.id": proyecto, "langfuse.trace.name": traza.nombre}
        spans.extend(
            Span(
                s.id,
                s.traza,
                s.padre if s.padre is not None else traza.raiz,
                s.nombre,
                s.inicio_ns,
                s.fin_ns,
                {**s.atributos, **de_la_traza},
                s.definitivo,
            )
            for s in traza.spans
        )
    trazas_con_spans = {s.traza for s in spans}
    return Exportacion(proyecto, spans, [s for s in scores if s.traza in trazas_con_spans])
