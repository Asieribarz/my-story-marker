"""E-1: qué sale hacia Langfuse, con qué forma, y que nada con texto sale."""

import base64
import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from backend.observabilidad import exportar, otlp
from backend.observabilidad.cliente import ClienteLangfuse, ScoresRechazados
from backend.observabilidad.configuracion import Configuracion, de_entorno
from backend.observabilidad.exportar import exportar_proyecto, sincronizar_prompts
from backend.observabilidad.traza import Exportacion, Span, construir, ns
from backend.proyecto.persistencia import crear_proyecto
from backend.shared.db import transaccion
from backend.shared.rutas import DisposicionProyecto

AHORA = datetime(2026, 9, 24, 10, 0, tzinfo=UTC)
# Un texto que nunca debe salir: está en todos los campos con texto libre de la base.
CENTINELA = "TEXTO-NO-CONFIABLE-7731"
SHA_ESCRITOR = "a" * 64


def _orden(
    c: sqlite3.Connection,
    id_: int,
    agente: str,
    emitida: str,
    cerrada: str,
    capitulo: int | None = None,
    tipo: str = "aceptado",
    desenlace: str = "aceptada",
    metadatos: dict[str, Any] | None = None,
) -> None:
    c.execute(
        "INSERT INTO orden (id, estado_proyecto, agente, capitulo, intento, entrada, emitida, "
        "cerrada, desenlace, detalle, sello, metadatos) VALUES (?, 'capitulos', ?, ?, 1, ?, ?, "
        "?, ?, ?, ?, ?)",
        (
            id_,
            agente,
            capitulo,
            json.dumps({"texto": CENTINELA}),
            emitida,
            cerrada,
            desenlace,
            json.dumps({"tipo": tipo, "informe": CENTINELA}),
            f"x:{id_}:1",
            None if metadatos is None else json.dumps(metadatos),
        ),
    )


@pytest.fixture
def base(tmp_path: Path) -> Iterator[tuple[str, DisposicionProyecto, sqlite3.Connection]]:
    proyecto = crear_proyecto(AHORA, raiz_proyectos=tmp_path)
    c = proyecto.conexion
    with transaccion(c):
        _orden(c, 1, "agente-contexto", "2026-09-24T10:00:00Z", "2026-09-24T10:01:00Z")
        _orden(
            c,
            2,
            "escritor",
            "2026-09-24T10:02:00Z",
            "2026-09-24T10:05:00Z",
            capitulo=3,
            metadatos={
                "modelo": "claude-opus-5-5",
                "tokens_entrada": 1200,
                "tokens_salida": 800,
                "tokens_cache_lectura": 50,
                "duracion_ms": 60_000,
                "version_prompt": SHA_ESCRITOR,
            },
        )
        _orden(
            c,
            3,
            "editor-estilo",
            "2026-09-24T10:05:00Z",
            "2026-09-24T10:06:00Z",
            capitulo=3,
            tipo="fallo_forma",
            desenlace="rechazada",
        )
        c.execute(
            "INSERT INTO llamada_mcp (momento, agente, herramienta, argumentos, resultado) "
            "VALUES ('2026-09-24T10:05:30Z', 'editor-estilo', 'leer_capitulo', ?, ?)",
            (json.dumps({"proyecto": "p", "nota": CENTINELA}), json.dumps({"t": CENTINELA})),
        )
        c.execute(
            "INSERT INTO auditoria (momento, tipo, detalle) VALUES "
            "('2026-09-24T10:05:00Z', 'guardarrail', ?)",
            (
                json.dumps(
                    {
                        "capitulo": 3,
                        "version": 1,
                        "intento": 1,
                        "nivel": "novela",
                        "palabra": CENTINELA,
                        "offset": 10,
                    }
                ),
            ),
        )
        c.execute("INSERT OR IGNORE INTO capitulo (numero) VALUES (3)")
        c.execute(
            "INSERT INTO capitulo_version (id, capitulo, version, intento, estado, ruta, creado) "
            "VALUES (1, 3, 1, 1, 'borrador', 'r', '2026-09-24T10:05:00Z')"
        )
        c.execute(
            "INSERT INTO informe (capitulo_version, verificador, severidad, hallazgos, momento) "
            "VALUES (1, 'guardarrail', 'bloqueante', ?, '2026-09-24T10:05:00Z')",
            (json.dumps([{"mensaje": CENTINELA}]),),
        )
        c.execute(
            "INSERT INTO transicion (momento, origen, destino, causa) VALUES "
            "('2026-09-24T10:07:00Z', 'capitulos', 'verificacion_manuscrito', 'x')"
        )
        c.execute("INSERT INTO gate_resultado VALUES (1, 'lean', 0, '{}')")
        c.execute(
            "INSERT INTO informe_juez (evaluacion, version_novela, revisor, ciclo, criterio, "
            "puntuacion, justificacion, momento) VALUES ('e1', 1, 'juez', 0, 'tono', 4, ?, "
            "'2026-09-24T10:08:00Z')",
            (CENTINELA,),
        )
        # El cambio del lector abre una traza nueva.
        c.execute(
            "INSERT INTO cambio_lector (id, version_novela, capitulo, ruta_peticion, creado) "
            "VALUES (1, 1, 3, 'cambios/1.txt', '2026-09-24T11:00:00Z')"
        )
        _orden(c, 4, "interprete-cambios", "2026-09-24T11:00:10Z", "2026-09-24T11:00:40Z")
    yield proyecto.identificador, proyecto.disposicion, c
    proyecto.cerrar()


def _por_nombre(exportacion: Exportacion, nombre: str) -> Span:
    return next(s for s in exportacion.spans if s.nombre == nombre)


def test_nada_con_texto_sale_hacia_langfuse(
    base: tuple[str, DisposicionProyecto, sqlite3.Connection],
) -> None:
    identificador, _, c = base
    exportacion = construir(c, identificador)
    todo = json.dumps(otlp.peticion(exportacion.spans)) + json.dumps(
        [exportar._score(s) for s in exportacion.scores]
    )
    assert CENTINELA not in todo


def test_una_sesion_por_proyecto_y_una_traza_por_generacion(
    base: tuple[str, DisposicionProyecto, sqlite3.Connection],
) -> None:
    identificador, _, c = base
    exportacion = construir(c, identificador)
    raices = [s for s in exportacion.spans if s.padre is None]
    assert [r.nombre for r in raices] == ["generacion", "regeneracion"]
    assert {r.atributos["langfuse.session.id"] for r in raices} == {identificador}
    assert _por_nombre(exportacion, "interprete:interprete-cambios").traza == raices[1].traza
    assert _por_nombre(exportacion, "entrevistador:agente-contexto").traza == raices[0].traza


def test_cada_rol_es_una_generacion_con_tokens_modelo_y_prompt(
    base: tuple[str, DisposicionProyecto, sqlite3.Connection],
) -> None:
    identificador, _, c = base
    exportacion = construir(c, identificador, {("escritor", SHA_ESCRITOR): 7})
    escritor = _por_nombre(exportacion, "writer:escritor")
    capitulo = _por_nombre(exportacion, "capitulo-03")
    assert escritor.padre == capitulo.id
    assert escritor.atributos["langfuse.observation.type"] == "generation"
    assert escritor.atributos["langfuse.observation.model.name"] == "claude-opus-5-5"
    assert json.loads(str(escritor.atributos["langfuse.observation.usage_details"])) == {
        "input": 1200,
        "output": 800,
        "cache_read_input_tokens": 50,
    }
    assert escritor.atributos["langfuse.observation.prompt.version"] == 7
    assert escritor.fin_ns - escritor.inicio_ns == 60 * 10**9
    # El capítulo abarca a sus órdenes: ahí se suman tokens y latencia del capítulo.
    editor = _por_nombre(exportacion, "editor:editor-estilo")
    assert capitulo.inicio_ns <= escritor.inicio_ns and capitulo.fin_ns == editor.fin_ns
    assert editor.atributos["langfuse.observation.level"] == "WARNING"


def test_la_llamada_mcp_cuelga_de_la_orden_abierta_de_su_agente(
    base: tuple[str, DisposicionProyecto, sqlite3.Connection],
) -> None:
    identificador, _, c = base
    exportacion = construir(c, identificador)
    herramienta = _por_nombre(exportacion, "tool:leer_capitulo")
    assert herramienta.padre == _por_nombre(exportacion, "editor:editor-estilo").id
    assert herramienta.atributos["langfuse.observation.type"] == "tool"
    assert herramienta.atributos["langfuse.observation.metadata.argumentos"] == "nota,proyecto"


def test_scores_de_validadores_gates_y_juez(
    base: tuple[str, DisposicionProyecto, sqlite3.Connection],
) -> None:
    identificador, _, c = base
    exportacion = construir(c, identificador)
    scores = {s.nombre: s for s in exportacion.scores if s.nombre != "esquema_salida"}
    assert scores["validador:guardarrail"].valor == 0.0
    assert scores["validador:guardarrail"].observacion == _por_nombre(exportacion, "capitulo-03").id
    assert scores["validador:contexto"].valor == 1.0
    assert scores["gate:lean"].valor == 0.0 and scores["gate:lean"].tipo == "BOOLEAN"
    assert scores["juez:tono"].valor == 4.0 and scores["juez:tono"].tipo == "NUMERIC"
    esquema = {
        s.metadatos["agente"]: s.valor for s in exportacion.scores if s.nombre == "esquema_salida"
    }
    assert esquema == {"escritor": 1.0, "editor-estilo": 0.0, "interprete-cambios": 1.0}
    guardarrail = _por_nombre(exportacion, "guardarrail")
    assert guardarrail.atributos["langfuse.observation.metadata.nivel"] == "novela"


def test_repetir_da_los_mismos_identificadores(
    base: tuple[str, DisposicionProyecto, sqlite3.Connection],
) -> None:
    identificador, _, c = base
    assert construir(c, identificador) == construir(c, identificador)


def test_una_base_sin_ordenes_no_envia_nada(tmp_path: Path) -> None:
    proyecto = crear_proyecto(AHORA, raiz_proyectos=tmp_path)
    try:
        assert construir(proyecto.conexion, proyecto.identificador) == Exportacion(
            proyecto.identificador, [], []
        )
    finally:
        proyecto.cerrar()


class EmisorEnMemoria:
    def __init__(self, prompts: dict[tuple[str, str], int] | None = None) -> None:
        self.spans: list[dict[str, Any]] = []
        self.scores: list[dict[str, Any]] = []
        self.prompts = dict(prompts or {})
        self.creados: list[str] = []

    def enviar_spans(self, cuerpo: dict[str, Any]) -> None:
        self.spans.extend(cuerpo["resourceSpans"][0]["scopeSpans"][0]["spans"])

    def enviar_scores(self, cuerpos: list[dict[str, Any]]) -> None:
        self.scores.extend(cuerpos)

    def version_de_prompt(self, nombre: str, etiqueta: str) -> int | None:
        return self.prompts.get((nombre, etiqueta))

    def crear_prompt(
        self, nombre: str, texto: str, etiquetas: list[str], config: dict[str, Any]
    ) -> int:
        self.creados.append(nombre)
        self.prompts[(nombre, etiquetas[0])] = 1
        return 1


def test_exportar_envia_spans_y_scores_y_resuelve_el_prompt(
    base: tuple[str, DisposicionProyecto, sqlite3.Connection],
) -> None:
    _, disposicion, _ = base
    emisor = EmisorEnMemoria({("escritor", exportar.etiqueta(SHA_ESCRITOR)): 3})
    resumen = exportar_proyecto(disposicion, emisor)
    assert resumen.spans == len(emisor.spans) and resumen.scores == len(emisor.scores)
    escritor = next(s for s in emisor.spans if s["name"] == "writer:escritor")
    atributos = {a["key"]: a["value"] for a in escritor["attributes"]}
    assert atributos["langfuse.observation.prompt.version"] == {"intValue": "3"}
    assert len(escritor["spanId"]) == 16 and len(escritor["traceId"]) == 32
    assert all(s["traceId"] and s["name"] for s in emisor.scores)


def test_sincronizar_prompts_solo_sube_lo_que_falta(tmp_path: Path) -> None:
    (tmp_path / "escritor.md").write_text("definición", encoding="utf-8")
    (tmp_path / "revisor.md").write_text("otra", encoding="utf-8")
    emisor = EmisorEnMemoria()
    primera = sincronizar_prompts(emisor, tmp_path)
    assert sorted(emisor.creados) == ["escritor", "revisor"]
    assert sincronizar_prompts(emisor, tmp_path) == primera
    assert sorted(emisor.creados) == ["escritor", "revisor"]


def test_configuracion_de_env_y_de_entorno(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        '# comentario\nLANGFUSE_PUBLIC_KEY="pk-lf-prueba"\nLANGFUSE_SECRET_KEY=sk-lf-prueba\n',
        encoding="utf-8",
    )
    configuracion = de_entorno({}, env)
    assert configuracion == Configuracion(
        "pk-lf-prueba", "sk-lf-prueba", "https://cloud.langfuse.com"
    )
    assert "sk-lf-prueba" not in repr(configuracion)
    assert de_entorno({"LANGFUSE_BASE_URL": "https://eu.x/"}, env).url == "https://eu.x"  # type: ignore[union-attr]
    assert de_entorno({"MSM_LANGFUSE": "0"}, env) is None
    assert de_entorno({}, tmp_path / "no-existe") is None
    ejemplo = {"LANGFUSE_PUBLIC_KEY": "pk-lf-TU_CLAVE_AQUI", "LANGFUSE_SECRET_KEY": "x"}
    assert de_entorno(ejemplo, tmp_path / "no-existe") is None


def test_el_cliente_usa_otlp_con_la_cabecera_v4_y_basic_auth() -> None:
    vistas: list[httpx.Request] = []

    def responder(peticion: httpx.Request) -> httpx.Response:
        vistas.append(peticion)
        if peticion.url.path.startswith("/api/public/v2/prompts/"):
            return httpx.Response(404)
        if peticion.url.path == "/api/public/ingestion":
            return httpx.Response(207, json={"successes": [{"id": "a"}], "errors": []})
        return httpx.Response(200, json={"version": 2})

    cliente = ClienteLangfuse(
        Configuracion("pk-lf-prueba", "sk-lf-prueba", "https://lf.test"),
        httpx.MockTransport(responder),
    )
    cliente.enviar_spans({"resourceSpans": []})
    cliente.enviar_scores([{"name": "x", "value": 1}])
    assert cliente.version_de_prompt("escritor", "sha-abc") is None
    assert cliente.crear_prompt("escritor", "t", ["sha-abc"], {}) == 2
    cliente.cerrar()
    rutas = [p.url.path for p in vistas]
    assert rutas == [
        "/api/public/otel/v1/traces",
        "/api/public/ingestion",
        "/api/public/v2/prompts/escritor",
        "/api/public/v2/prompts",
    ]
    assert vistas[0].headers["x-langfuse-ingestion-version"] == "4"
    esperada = base64.b64encode(b"pk-lf-prueba:sk-lf-prueba").decode()
    assert vistas[0].headers["authorization"] == f"Basic {esperada}"
    lote = json.loads(vistas[1].content)["batch"]
    assert [e["type"] for e in lote] == ["score-create"] and lote[0]["body"]["name"] == "x"


def test_el_cliente_reintenta_un_429_con_la_espera_que_pide() -> None:
    respuestas = iter([httpx.Response(429, headers={"retry-after": "3"}), httpx.Response(200)])
    esperas: list[float] = []
    cliente = ClienteLangfuse(
        Configuracion("pk", "sk", "https://lf.test"),
        httpx.MockTransport(lambda _: next(respuestas)),
        dormir=esperas.append,
    )
    cliente.enviar_spans({"resourceSpans": []})
    cliente.cerrar()
    assert esperas == [3.0]


def test_un_score_rechazado_en_el_lote_es_un_error() -> None:
    cliente = ClienteLangfuse(
        Configuracion("pk", "sk", "https://lf.test"),
        httpx.MockTransport(
            lambda _: httpx.Response(207, json={"errors": [{"id": "a", "status": 400}]})
        ),
    )
    with pytest.raises(ScoresRechazados):
        cliente.enviar_scores([{"name": "x", "value": 1}])
    cliente.cerrar()


def test_programar_sin_claves_no_hace_nada(
    base: tuple[str, DisposicionProyecto, sqlite3.Connection],
) -> None:
    _, disposicion, _ = base
    exportar.programar(disposicion)  # MSM_LANGFUSE=0 por backend/conftest.py
    assert exportar._pendientes == {}


def test_un_proyecto_sin_base_no_se_crea_al_exportar(tmp_path: Path) -> None:
    disposicion = DisposicionProyecto.de("0" * 32, tmp_path)
    with pytest.raises(FileNotFoundError):
        exportar_proyecto(disposicion, EmisorEnMemoria())
    assert not disposicion.base.exists()


def test_cada_span_y_cada_score_se_envian_una_sola_vez(
    base: tuple[str, DisposicionProyecto, sqlite3.Connection],
) -> None:
    _, disposicion, _ = base
    emisor = EmisorEnMemoria()
    primera = exportar_proyecto(disposicion, emisor)
    assert primera.spans > 0 and primera.scores > 0
    segunda = exportar_proyecto(disposicion, emisor)
    assert (segunda.spans, segunda.scores) == (0, 0)
    ids = [s["spanId"] for s in emisor.spans]
    assert len(ids) == len(set(ids))


def test_el_capitulo_sale_cuando_el_bibliotecario_lo_aprueba(
    base: tuple[str, DisposicionProyecto, sqlite3.Connection],
) -> None:
    identificador, disposicion, c = base
    emisor = EmisorEnMemoria()
    exportar_proyecto(disposicion, emisor)
    assert "capitulo-03" not in {s["name"] for s in emisor.spans}
    with transaccion(c):
        _orden(c, 5, "bibliotecario", "2026-09-24T10:06:10Z", "2026-09-24T10:07:00Z", capitulo=3)
    exportar_proyecto(disposicion, emisor)
    capitulos = [s for s in emisor.spans if s["name"] == "capitulo-03"]
    assert len(capitulos) == 1
    assert capitulos[0]["endTimeUnixNano"] == str(ns("2026-09-24T10:07:00Z"))


def test_la_raiz_no_tiene_duracion_y_todos_llevan_la_sesion(
    base: tuple[str, DisposicionProyecto, sqlite3.Connection],
) -> None:
    identificador, _, c = base
    exportacion = construir(c, identificador)
    for raiz in (s for s in exportacion.spans if s.padre is None):
        assert raiz.inicio_ns == raiz.fin_ns
    assert all(s.atributos["langfuse.session.id"] == identificador for s in exportacion.spans)
