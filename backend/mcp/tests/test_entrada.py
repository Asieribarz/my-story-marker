"""E-6 · `/mcp/entrada` montada en la aplicación, de extremo a extremo por HTTP (RF-14, V-29).

La aplicación es la de `backend/app.py` con la superficie montada como en producción, con
su reloj y su raíz de proyectos de prueba. Las peticiones entran por HTTP sin socket: el
transporte `StreamingASGITransport` de FastMCP despacha cada una dentro de la aplicación
ASGI, y el cliente de FastMCP hace el mismo intercambio que el de un subagente (initialize,
tools/list, tools/call). Así pasan el montaje, el lifespan combinado, el middleware de
Host y Origin y el transporte HTTP de MCP.

El `TestClient` de Starlette no sirve para esto: es síncrono, y el cliente de MCP es
asíncrono. El lifespan se abre con `app.router.lifespan_context` y no con
`run_asgi_lifespan` de FastMCP, que no ofrece `state` en el ámbito del lifespan y la
aplicación lo usa al combinar lifespans.

Todos los datos son ficticios (`backend/proyecto/tests/apoyo.py`).
"""

import json
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any, Protocol

import anyio
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from fastmcp.utilities.tests import ASGIServer
from mcp_types import TextContent

from backend.app import SUPERFICIES, crear_app
from backend.mcp import entrada
from backend.proyecto import dependencias
from backend.proyecto.errores import EntradaNoCanjeable
from backend.proyecto.tests.apoyo import BRIEF, HECHO, NORMALIZADO, TEXTO_LIBRE
from backend.proyecto.tests.cliente_api import Reloj, con_token

ORIGEN = "http://127.0.0.1"
URL = f"{ORIGEN}{entrada.RUTA}/"
MENSAJE = str(EntradaNoCanjeable())


class RespuestaHttp(Protocol):
    """Lo que las pruebas miran de una respuesta. Un protocolo y no el tipo del cliente HTTP
    que usa FastMCP, que es una dependencia suya y no del proyecto."""

    @property
    def status_code(self) -> int: ...

    @property
    def text(self) -> str: ...

    @property
    def content(self) -> bytes: ...

    @property
    def headers(self) -> Mapping[str, str]: ...

    def json(self, **opciones: Any) -> Any: ...


class ClienteHttp(Protocol):
    async def request(
        self,
        method: str,
        url: str,
        *,
        json: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> RespuestaHttp: ...

    async def post(
        self, url: str, *, json: Any = None, headers: Mapping[str, str] | None = None
    ) -> RespuestaHttp: ...


@dataclass
class Montaje:
    """La aplicación en marcha: REST y MCP sobre el mismo reloj y la misma raíz. `vistas`
    guarda el cuerpo de cada respuesta REST, lo que el orquestador llega a ver."""

    rest: ClienteHttp
    servidor: ASGIServer
    reloj: Reloj
    vistas: list[str] = field(default_factory=list)

    async def pedir(
        self,
        metodo: str,
        ruta: str,
        *,
        json: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        respuesta = await self.rest.request(metodo, ruta, json=json, headers=headers)
        self.vistas.append(respuesta.text)
        assert respuesta.status_code < 400, respuesta.text
        return respuesta.json() if respuesta.content else None

    def cliente(self) -> Client[Any]:
        return self.servidor.client()


@asynccontextmanager
async def _montaje(raiz: Path) -> AsyncIterator[Montaje]:
    reloj = Reloj()
    superficie = partial(entrada.superficie, reloj=lambda: reloj.ahora, raiz=lambda: raiz)
    app = crear_app(((entrada.RUTA, superficie),))
    app.dependency_overrides[dependencias.raiz_proyectos] = lambda: raiz
    app.dependency_overrides[dependencias.reloj] = lambda: reloj.ahora
    rest = ASGIServer(url=ORIGEN, app=app, transport_type="http")
    async with app.router.lifespan_context(app), rest.http_client() as http:
        yield Montaje(http, ASGIServer(url=URL, app=app, transport_type="http"), reloj)


def _en_marcha(raiz: Path, prueba: Callable[[Montaje], Awaitable[None]]) -> None:
    async def principal() -> None:
        async with _montaje(raiz) as montaje:
            await prueba(montaje)

    anyio.run(principal)


async def _orden_del_extractor(m: Montaje) -> tuple[str, str, dict[str, Any]]:
    proyecto: str = (await m.pedir("POST", "/proyectos"))["identificador"]
    ruta = f"/proyectos/{proyecto}"
    bloqueo = await m.pedir("POST", f"{ruta}/bloqueo", json={"tipo": "sesion"})
    token: str = bloqueo["token"]
    brief = {"respuestas": BRIEF, "texto_libre": TEXTO_LIBRE}
    await m.pedir("POST", f"{ruta}/brief", json=brief)
    siguiente = await m.pedir("POST", f"{ruta}/siguiente", headers=con_token(token))
    assert siguiente["decision"] == "orden"
    orden: dict[str, Any] = siguiente["orden"]
    assert orden["agente"] == "extractor-hechos"
    return proyecto, token, orden


async def _leer(cliente: Client[Any], identificador: str) -> str:
    resultado = await cliente.call_tool(entrada.HERRAMIENTA, {"identificador": identificador})
    [contenido] = resultado.content
    assert isinstance(contenido, TextContent)
    return contenido.text


def test_la_superficie_esta_en_las_de_la_aplicacion() -> None:
    assert (entrada.RUTA, entrada.superficie) in SUPERFICIES
    assert entrada.RUTA == "/mcp/entrada"


def test_publica_una_sola_herramienta_de_solo_lectura(tmp_path: Path) -> None:
    async def prueba(m: Montaje) -> None:
        async with m.cliente() as cliente:
            [herramienta] = await cliente.list_tools()
        assert herramienta.name == "leer_entrada"
        assert herramienta.annotations is not None
        assert herramienta.annotations.read_only_hint is True
        assert herramienta.annotations.destructive_hint is False
        assert list(herramienta.input_schema["properties"]) == ["identificador"]
        assert herramienta.input_schema["required"] == ["identificador"]

    _en_marcha(tmp_path, prueba)


def _bloque(valor: object) -> str:
    """La salida del subagente como la envía el hook: un bloque JSON (§4.1.3)."""
    return "```json" + chr(10) + json.dumps(valor) + chr(10) + "```"


def test_de_la_orden_al_texto_sin_que_el_orquestador_lo_vea(tmp_path: Path) -> None:
    """El flujo del Extractor: la orden trae el identificador, el subagente lo canjea por
    MCP una sola vez, y ninguna respuesta REST lleva el texto libre."""

    async def prueba(m: Montaje) -> None:
        proyecto, token, orden = await _orden_del_extractor(m)
        identificador = orden["entrada"]["texto_libre"]["identificador"]
        assert re.fullmatch(rf"{proyecto}\.[A-Za-z0-9_-]{{43}}", identificador)
        # RF-14: el estado no exige el bloqueo, así que no enseña el identificador, solo su
        # caducidad; si no, cualquiera que lo leyera podría canjearlo antes que el Extractor.
        estado = await m.pedir("GET", f"/proyectos/{proyecto}/estado")
        vista = estado["orden_vigente"]["entrada"]
        assert vista["texto_libre"] == {"caduca": orden["entrada"]["texto_libre"]["caduca"]}
        assert identificador not in m.vistas[-1]

        async with m.cliente() as cliente:
            assert await _leer(cliente, identificador) == TEXTO_LIBRE
            with pytest.raises(ToolError) as segundo:
                await _leer(cliente, identificador)
            assert str(segundo.value) == MENSAJE

        cuerpo = {"orden": orden["sello"], "salida_cruda": _bloque({"hechos": [HECHO]})}
        resultado = await m.pedir(
            "POST", f"/proyectos/{proyecto}/resultado", json=cuerpo, headers=con_token(token)
        )
        assert resultado["desenlace"] == "aceptada"
        pendientes = (await m.pedir("GET", f"/proyectos/{proyecto}/hechos"))["hechos"]
        decisiones = {"decisiones": [{"hecho": h["id"], "confirmado": True} for h in pendientes]}
        await m.pedir("POST", f"/proyectos/{proyecto}/hechos/confirmacion", json=decisiones)
        normalizar = await m.pedir(
            "POST", f"/proyectos/{proyecto}/siguiente", headers=con_token(token)
        )
        assert normalizar["orden"]["agente"] == "agente-contexto"
        assert "texto_libre" not in normalizar["orden"]["entrada"]
        cuerpo = {"orden": normalizar["orden"]["sello"], "salida_cruda": _bloque(NORMALIZADO)}
        await m.pedir(
            "POST", f"/proyectos/{proyecto}/resultado", json=cuerpo, headers=con_token(token)
        )
        await m.pedir("GET", f"/proyectos/{proyecto}/estado")

        assert len(m.vistas) >= 10
        assert all(TEXTO_LIBRE not in vista for vista in m.vistas)

    _en_marcha(tmp_path, prueba)


def test_por_mcp_todo_identificador_que_no_sirve_da_el_mismo_error(tmp_path: Path) -> None:
    async def prueba(m: Montaje) -> None:
        proyecto, _, orden = await _orden_del_extractor(m)
        valido: str = orden["entrada"]["texto_libre"]["identificador"]
        secreto = valido.split(".")[1]
        async with m.cliente() as cliente:
            for malo in [
                f"{proyecto}.{'A' * 43}",
                f"{'0' * 32}.{secreto}",
                "no es un identificador",
                "",
            ]:
                with pytest.raises(ToolError) as fallo:
                    await _leer(cliente, malo)
                assert str(fallo.value) == MENSAJE
            m.reloj.avanzar(30)
            with pytest.raises(ToolError) as caducado:
                await _leer(cliente, valido)
            assert str(caducado.value) == MENSAJE

    _en_marcha(tmp_path, prueba)


def test_la_url_declarada_lleva_la_barra_final_y_rechaza_un_host_ajeno(tmp_path: Path) -> None:
    """Sin la barra final, el enrutado redirige a la URL declarada. Con un Host que no es
    local, la protección frente a DNS rebinding responde 421 antes de llegar a MCP."""

    async def prueba(m: Montaje) -> None:
        sin_barra = await m.rest.post(entrada.RUTA, json={})
        assert (sin_barra.status_code, sin_barra.headers["location"]) == (307, URL)
        ajeno = await m.rest.post(f"{entrada.RUTA}/", json={}, headers={"host": "atacante.invalid"})
        assert ajeno.status_code == 421

    _en_marcha(tmp_path, prueba)
