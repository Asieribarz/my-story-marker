"""`/mcp/lectura` y `/mcp/escritura`: V-19, AJ-4, el lado de V-13 que toca al backend,
RF-105 y el contrato de forma de cada herramienta (RF-103, RF-104).

Los servidores se prueban con el cliente de FastMCP en memoria —el mismo intercambio de
tools/list y tools/call que el de un subagente, sin HTTP—; el transporte y el montaje ya los
cubre `test_entrada.py`, y aquí solo se comprueba que las tres superficies están montadas.
La biblia es la de referencia (`capitulo/tests/referencia.py`), con datos ficticios, y la
orden del Bibliotecario se inserta en la tabla `orden` con su sello, como la emite el cerebro.
"""

import json
import sqlite3
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anyio
import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from mcp_types import TextContent
from starlette.routing import Mount

from backend.app import crear_app
from backend.capitulo.biblia import personajes_a_fecha
from backend.capitulo.tests.referencia import MOMENTO, biblia_de_referencia, verificar
from backend.mcp import entrada, escritura, lectura
from backend.proyecto.abierto import Proyecto, abrir_proyecto
from backend.proyecto.bloqueo import tomar_bloqueo
from backend.shared.rutas import DisposicionProyecto, nuevo_identificador
from backend.shared.tipos import TipoEjecutor

AHORA = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)

LECTURA = {
    "leer_contexto": {"proyecto"},
    "leer_plan": {"proyecto"},
    "leer_guia_estilo": {"proyecto"},
    "leer_ficha": {"proyecto", "numero"},
    "leer_personajes": {"proyecto", "antes_de", "ids"},
    "leer_localizacion": {"proyecto", "localizacion", "antes_de"},
    "leer_dia": {"proyecto", "numero"},
    "leer_inventario": {"proyecto", "antes_de"},
    "leer_presagios_pendientes": {"proyecto", "antes_de"},
    "leer_glosario": {"proyecto", "antes_de"},
    "leer_resumen_acumulado": {"proyecto", "antes_de"},
    "leer_reglas_mundo": {"proyecto"},
    "leer_capitulo": {"proyecto", "numero", "version", "intento"},
    "leer_informe": {"proyecto", "numero", "version", "intento"},
}
ESCRITURA = {
    "actualizar_estado_personaje": {"sello", "personaje", "estado"},
    "registrar_saber": {"sello", "personaje", "datos"},
    "actualizar_estado_localizacion": {"sello", "localizacion", "estado"},
    "registrar_traspaso": {"sello", "objeto", "poseedor"},
    "registrar_evento": {"sello", "descripcion", "lugar", "presentes"},
    "plantar_presagio": {"sello", "clave"},
    "cobrar_presagio": {"sello", "clave"},
    "abrir_presagio": {"sello", "clave", "descripcion"},
    "registrar_termino": {"sello", "termino", "categoria", "tipo"},
    "registrar_uso_de_hecho": {"sello", "hecho"},
    "escribir_resumen_capitulo": {"sello", "texto", "dia_fin", "localizacion_fin"},
    "escribir_resumen_acto": {"sello", "texto"},
}
ESTADO_SECRETO = "Herida en el brazo tras la caída"


@dataclass
class Biblia:
    raiz: Path
    disposicion: DisposicionProyecto
    conexion: sqlite3.Connection
    orden: int

    @property
    def proyecto(self) -> str:
        return self.disposicion.identificador

    def sello(self, generacion: int = 0) -> str:
        return f"{self.proyecto}:{self.orden}:{generacion}"

    def uno(self, sql: str) -> Any:
        return self.conexion.execute(sql).fetchone()[0]


@pytest.fixture
def biblia(tmp_path: Path) -> Iterator[Biblia]:
    """Proyecto de referencia con la orden vigente del Bibliotecario para el capítulo 2, que
    aún no está verificado."""
    disposicion = DisposicionProyecto.de(nuevo_identificador(), tmp_path)
    disposicion.crear_directorios()
    conexion = biblia_de_referencia(disposicion.base)
    conexion.execute(
        "INSERT INTO proyecto (id, identificador, estado, creado) VALUES (1, ?, 'capitulos', ?)",
        (disposicion.identificador, MOMENTO),
    )
    orden = conexion.execute(
        "INSERT INTO orden (estado_proyecto, agente, capitulo, intento, entrada, emitida) "
        "VALUES ('capitulos', 'bibliotecario', 2, 1, '{}', ?) RETURNING id",
        (MOMENTO,),
    ).fetchone()[0]
    datos = Biblia(tmp_path, disposicion, conexion, orden)
    conexion.execute("UPDATE orden SET sello = ? WHERE id = ?", (datos.sello(), orden))
    yield datos
    conexion.close()


def _servidor(modulo: Any, raiz: Path) -> FastMCP[Any]:
    servidor: FastMCP[Any] = modulo.crear_servidor(reloj=lambda: AHORA, raiz=lambda: raiz)
    return servidor


def _con(servidor: FastMCP[Any], prueba: Callable[[Client[Any]], Awaitable[None]]) -> None:
    async def principal() -> None:
        async with Client(servidor) as cliente:
            await prueba(cliente)

    anyio.run(principal)


async def _llamar(cliente: Client[Any], herramienta: str, argumentos: dict[str, Any]) -> Any:
    resultado = await cliente.call_tool(herramienta, argumentos)
    [contenido] = resultado.content
    assert isinstance(contenido, TextContent)
    return json.loads(contenido.text)


# ─── Contrato de forma y V-13 (lado del backend) ─────────────────────────────


@pytest.mark.parametrize(
    ("modulo", "esperadas"), [(lectura, LECTURA), (escritura, ESCRITURA)], ids=["lec", "esc"]
)
def test_cada_herramienta_tiene_el_contrato_de_forma(
    tmp_path: Path, modulo: Any, esperadas: dict[str, set[str]]
) -> None:
    """RF-100, RF-103, RF-104: los nombres y los parámetros obligatorios, exactos. Ninguna
    escritura recibe el capítulo (B-16) y todas reciben el sello (AJ-4)."""

    async def prueba(cliente: Client[Any]) -> None:
        herramientas = {h.name: h for h in await cliente.list_tools()}
        assert set(herramientas) == set(esperadas)
        for nombre, requeridos in esperadas.items():
            esquema = herramientas[nombre].input_schema
            assert set(esquema.get("required", [])) == requeridos, nombre
            assert "capitulo" not in esquema["properties"], nombre
            lectura_pura = herramientas[nombre].annotations
            assert lectura_pura is not None
            assert lectura_pura.read_only_hint is (modulo is lectura), nombre

    _con(_servidor(modulo, tmp_path), prueba)


def test_la_escritura_solo_existe_en_su_superficie() -> None:
    """V-13, lado del backend: ninguna herramienta de escritura se sirve en `/mcp/lectura` ni
    en `/mcp/entrada`, y las tres superficies están montadas en la aplicación."""
    assert not set(ESCRITURA) & (set(LECTURA) | {entrada.HERRAMIENTA})
    montajes = {r.path for r in crear_app().routes if isinstance(r, Mount)}
    assert {lectura.RUTA, escritura.RUTA, entrada.RUTA} <= montajes


# ─── V-19 y AJ-4 ─────────────────────────────────────────────────────────────


def test_v19_la_escritura_se_rechaza_antes_de_verificar_y_se_acepta_despues(
    biblia: Biblia,
) -> None:
    """RF-106: con el capítulo de la orden sin verificar, se rechaza y no escribe; verificado,
    la misma llamada entra etiquetada con el capítulo de la orden (B-16)."""
    argumentos = {"sello": biblia.sello(), "personaje": "nala", "estado": ESTADO_SECRETO}

    async def prueba(cliente: Client[Any]) -> None:
        with pytest.raises(ToolError, match="no verificado"):
            await cliente.call_tool("actualizar_estado_personaje", argumentos)
        (nala,) = personajes_a_fecha(biblia.conexion, 3, ["nala"])
        assert nala.estado != ESTADO_SECRETO
        verificar(biblia.conexion, 2)
        respuesta = await _llamar(cliente, "actualizar_estado_personaje", argumentos)
        assert respuesta == {"ok": True, "capitulo": 2}
        (nala,) = personajes_a_fecha(biblia.conexion, 3, ["nala"])
        assert nala.estado == ESTADO_SECRETO

    _con(_servidor(escritura, biblia.raiz), prueba)


def test_el_sello_viejo_no_escribe_y_el_vigente_si(biblia: Biblia) -> None:
    """AJ-4: tras volver a sellar la orden (otra generación del bloqueo), el sello anterior se
    rechaza; el nuevo escribe."""
    verificar(biblia.conexion, 2)
    biblia.conexion.execute("UPDATE proyecto SET generacion_bloqueo = 1")
    biblia.conexion.execute(
        "UPDATE orden SET sello = ? WHERE id = ?", (biblia.sello(1), biblia.orden)
    )
    hecho = biblia.uno("SELECT id FROM hecho ORDER BY id LIMIT 1")

    async def prueba(cliente: Client[Any]) -> None:
        with pytest.raises(ToolError, match="sello"):
            await cliente.call_tool(
                "registrar_uso_de_hecho", {"sello": biblia.sello(0), "hecho": hecho}
            )
        assert biblia.uno("SELECT count(*) FROM hecho_uso") == 0
        await _llamar(cliente, "registrar_uso_de_hecho", {"sello": biblia.sello(1), "hecho": hecho})
        assert biblia.uno("SELECT count(*) FROM hecho_uso") == 1

    _con(_servidor(escritura, biblia.raiz), prueba)


def test_una_orden_que_no_es_del_bibliotecario_no_escribe(biblia: Biblia) -> None:
    verificar(biblia.conexion, 2)
    biblia.conexion.execute(
        "UPDATE orden SET agente = 'juez-capitulo' WHERE id = ?", (biblia.orden,)
    )
    argumentos = {"sello": biblia.sello(), "personaje": "nala", "estado": "alegre"}

    async def prueba(cliente: Client[Any]) -> None:
        with pytest.raises(ToolError, match="Bibliotecario"):
            await cliente.call_tool("actualizar_estado_personaje", argumentos)

    _con(_servidor(escritura, biblia.raiz), prueba)


def test_el_resumen_respeta_el_tope_y_registra_el_fin(biblia: Biblia) -> None:
    """B-17: por encima de 240 palabras se rechaza sin registrar el fin; dentro del tope, el
    resumen y `dia_fin`/`localizacion_fin` entran juntos."""
    verificar(biblia.conexion, 2)
    lugar = biblia.uno("SELECT localizacion FROM ficha_capitulo WHERE numero = 2")
    base = {"sello": biblia.sello(), "dia_fin": 3, "localizacion_fin": lugar}

    async def prueba(cliente: Client[Any]) -> None:
        with pytest.raises(ToolError, match="240"):
            await cliente.call_tool("escribir_resumen_capitulo", base | {"texto": "a " * 241})
        assert biblia.uno("SELECT count(*) FROM capitulo_version WHERE dia_fin IS NOT NULL") == 0
        await _llamar(cliente, "escribir_resumen_capitulo", base | {"texto": "Pasa algo."})
        fila = biblia.conexion.execute(
            "SELECT dia_fin, localizacion_fin FROM capitulo_version WHERE capitulo = 2"
        ).fetchone()
        assert tuple(fila) == (3, lugar)

    _con(_servidor(escritura, biblia.raiz), prueba)


def test_el_sello_se_valida_en_la_transaccion_que_escribe(
    biblia: Biblia, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AJ-4: entre validar el sello y escribir nadie puede tomar el bloqueo —y volver a sellar
    la orden—; si pudiera, la escritura entraría con un sello que ya no vale."""
    verificar(biblia.conexion, 2)
    original = escritura._capitulo_de
    tomas: list[bool] = []

    def con_toma_intercalada(p: Proyecto, sello: str) -> int:
        capitulo = original(p, sello)
        with abrir_proyecto(biblia.proyecto, biblia.raiz) as otro:
            otro.conexion.execute("PRAGMA busy_timeout = 0")
            try:
                tomar_bloqueo(otro, TipoEjecutor.SESION, AHORA)
                tomas.append(True)
            except sqlite3.OperationalError:
                tomas.append(False)
        return capitulo

    monkeypatch.setattr(escritura, "_capitulo_de", con_toma_intercalada)
    argumentos = {"sello": biblia.sello(), "personaje": "nala", "estado": "alegre"}

    async def prueba(cliente: Client[Any]) -> None:
        await _llamar(cliente, "actualizar_estado_personaje", argumentos)

    _con(_servidor(escritura, biblia.raiz), prueba)
    assert tomas == [False]
    assert biblia.uno("SELECT generacion_bloqueo FROM proyecto") == 0
    assert biblia.uno("SELECT estado FROM personaje_estado WHERE capitulo = 2") == "alegre"


# ─── RF-105 ──────────────────────────────────────────────────────────────────


def test_cada_llamada_queda_en_llamada_mcp_sin_texto_libre(biblia: Biblia) -> None:
    """RF-105: aciertos y fallos, con el agente inferido de la orden vigente y sin el texto
    que redacta el modelo."""
    argumentos = {"sello": biblia.sello(), "personaje": "nala", "estado": ESTADO_SECRETO}

    async def escribir(cliente: Client[Any]) -> None:
        with pytest.raises(ToolError):
            await cliente.call_tool("actualizar_estado_personaje", argumentos)

    async def leer(cliente: Client[Any]) -> None:
        await _llamar(cliente, "leer_ficha", {"proyecto": biblia.proyecto, "numero": 1})

    _con(_servidor(escritura, biblia.raiz), escribir)
    _con(_servidor(lectura, biblia.raiz), leer)
    filas = biblia.conexion.execute(
        "SELECT agente, herramienta, argumentos, resultado FROM llamada_mcp ORDER BY id"
    ).fetchall()
    assert [(f["agente"], f["herramienta"]) for f in filas] == [
        ("bibliotecario", "escritura.actualizar_estado_personaje"),
        ("bibliotecario", "lectura.leer_ficha"),
    ]
    assert ESTADO_SECRETO not in filas[0]["argumentos"]
    assert json.loads(filas[0]["resultado"])["error"] == "CapituloNoVerificado"
    assert json.loads(filas[1]["resultado"])["ok"] is True


# ─── Lectura ─────────────────────────────────────────────────────────────────


def test_cada_lectura_responde_con_la_biblia(biblia: Biblia) -> None:
    """RF-103, §4.1.6: cada herramienta de lectura devuelve su objeto; un proyecto que no
    existe o algo que aún no existe es un error para el agente, no un fallo del servidor."""
    verificar(biblia.conexion, 1)
    ruta = biblia.disposicion.capitulo(1, 1, 1)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("# Uno\n\nTexto.\n", encoding="utf-8", newline="\n")
    lugar = biblia.uno("SELECT localizacion FROM ficha_capitulo WHERE numero = 1")
    p = {"proyecto": biblia.sello()}
    llamadas: dict[str, tuple[dict[str, Any], str]] = {
        "leer_contexto": (p, "novela"),
        "leer_plan": (p, "plan"),
        "leer_guia_estilo": (p, "metricas"),
        "leer_ficha": (p | {"numero": 1}, "presentes"),
        "leer_personajes": (p | {"antes_de": 2, "ids": ["nala"]}, "personajes"),
        "leer_localizacion": (p | {"localizacion": lugar, "antes_de": 2}, "lugares"),
        "leer_dia": (p | {"numero": 1}, "dia"),
        "leer_inventario": (p | {"antes_de": 2, "objeto": "brujula"}, "posesiones"),
        "leer_presagios_pendientes": (p | {"antes_de": 2}, "presagios"),
        "leer_glosario": (p | {"antes_de": 2}, "terminos"),
        "leer_resumen_acumulado": (p | {"antes_de": 2}, "resumenes"),
        "leer_reglas_mundo": (p, "reglas"),
        "leer_capitulo": (p | {"numero": 1, "version": 1, "intento": 1}, "texto"),
        "leer_informe": (p | {"numero": 1, "version": 1, "intento": 1}, "informes"),
    }
    assert set(llamadas) == set(LECTURA)

    async def prueba(cliente: Client[Any]) -> None:
        for nombre, (argumentos, clave) in llamadas.items():
            assert clave in await _llamar(cliente, nombre, argumentos), nombre
        assert (await _llamar(cliente, "leer_capitulo", llamadas["leer_capitulo"][0]))[
            "texto"
        ].startswith("# Uno")
        with pytest.raises(ToolError, match="proyecto desconocido"):
            await cliente.call_tool("leer_plan", {"proyecto": nuevo_identificador()})
        with pytest.raises(ToolError, match="no hay texto"):
            await cliente.call_tool("leer_capitulo", p | {"numero": 2, "version": 1, "intento": 1})

    _con(_servidor(lectura, biblia.raiz), prueba)


def test_los_argumentos_que_rechaza_fastmcp_tambien_quedan(biblia: Biblia) -> None:
    """RF-105: una llamada que no pasa la validación de argumentos no llega a la herramienta,
    pero queda en `llamada_mcp`, sin el sello ni el texto libre."""

    async def leer(cliente: Client[Any]) -> None:
        with pytest.raises(ToolError):
            await cliente.call_tool("leer_ficha", {"proyecto": biblia.proyecto, "numero": 99})

    async def escribir(cliente: Client[Any]) -> None:
        with pytest.raises(ToolError):
            await cliente.call_tool(
                "registrar_saber", {"sello": biblia.sello(), "personaje": "nala", "datos": []}
            )

    _con(_servidor(lectura, biblia.raiz), leer)
    _con(_servidor(escritura, biblia.raiz), escribir)
    filas = biblia.conexion.execute(
        "SELECT herramienta, argumentos, resultado FROM llamada_mcp ORDER BY id"
    ).fetchall()
    assert [f["herramienta"] for f in filas] == ["lectura.leer_ficha", "escritura.registrar_saber"]
    assert json.loads(filas[0]["argumentos"]) == {"numero": 99}
    assert json.loads(filas[1]["argumentos"]) == {"personaje": "nala", "datos": {"elementos": 0}}
    assert {json.loads(f["resultado"])["error"] for f in filas} == {"ArgumentosInvalidos"}
