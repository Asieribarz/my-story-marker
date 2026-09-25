"""Cliente de prueba de la API: la aplicación real de `backend/app.py`, con la raíz de
proyectos en un directorio de la prueba y un reloj que la prueba adelanta.

Todos los datos de persona son ficticios (`apoyo.py`, `backend/contexto/tests/referencia.py`).
`abrir` da acceso directo a la base para colocar el proyecto en una fase (`apoyo.forzar`) o
comparar sus filas; nunca para probar una transición.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from fastapi.testclient import TestClient

from backend.app import crear_app
from backend.proyecto import dependencias
from backend.proyecto.abierto import Proyecto, abrir_proyecto
from backend.proyecto.dependencias import CABECERA_BLOQUEO
from backend.proyecto.tests.apoyo import AHORA, salida_cruda, sello_de
from backend.shared.tipos import Agente


class Respuesta(Protocol):
    """Lo que las pruebas miran de una respuesta del `TestClient`. Un protocolo y no el tipo
    de httpx: el `TestClient` de esta versión de Starlette devuelve el de otro paquete."""

    @property
    def status_code(self) -> int: ...

    @property
    def text(self) -> str: ...

    @property
    def content(self) -> bytes: ...

    def json(self, **opciones: Any) -> Any: ...


@dataclass
class Reloj:
    ahora: datetime = field(default=AHORA)

    def avanzar(self, minutos: int) -> None:
        self.ahora += timedelta(minutes=minutos)


def con_token(token: str) -> dict[str, str]:
    return {CABECERA_BLOQUEO: token}


@dataclass
class ClienteApi:
    http: TestClient
    raiz: Path
    reloj: Reloj

    def crear(self, **paradas: bool) -> str:
        respuesta = self.http.post("/proyectos", json=paradas)
        assert respuesta.status_code == 201, respuesta.text
        identificador: str = respuesta.json()["identificador"]
        return identificador

    def tomar(self, proyecto: str, tipo: str = "sesion") -> str:
        respuesta = self.http.post(f"/proyectos/{proyecto}/bloqueo", json={"tipo": tipo})
        assert respuesta.status_code == 200, respuesta.text
        token: str = respuesta.json()["token"]
        return token

    def estado(self, proyecto: str) -> dict[str, Any]:
        respuesta = self.http.get(f"/proyectos/{proyecto}/estado")
        assert respuesta.status_code == 200, respuesta.text
        cuerpo: dict[str, Any] = respuesta.json()
        return cuerpo

    def pedir(self, proyecto: str, token: str) -> Respuesta:
        return self.http.post(f"/proyectos/{proyecto}/siguiente", headers=con_token(token))

    def siguiente(self, proyecto: str, token: str) -> dict[str, Any]:
        respuesta = self.pedir(proyecto, token)
        assert respuesta.status_code == 200, respuesta.text
        cuerpo: dict[str, Any] = respuesta.json()
        return cuerpo

    def orden(self, proyecto: str, token: str) -> dict[str, Any]:
        decision = self.siguiente(proyecto, token)
        assert decision["decision"] == "orden", decision
        orden: dict[str, Any] = decision["orden"]
        return orden

    def registrar(
        self,
        proyecto: str,
        token: str,
        orden: int,
        resultado: object,
        metadatos: dict[str, Any] | None = None,
    ) -> Respuesta:
        """Registra como el hook: el sello de la orden `orden` y la salida cruda de
        `resultado` (`apoyo.salida_cruda`)."""
        with self.abrir(proyecto) as abierto:
            fila = abierto.conexion.execute(
                "SELECT agente FROM orden WHERE id = ?", (orden,)
            ).fetchone()
            sello = sello_de(abierto.conexion, proyecto, orden)
        agente = Agente(fila["agente"]) if fila is not None else None
        cuerpo: dict[str, Any] = {"orden": sello, "salida_cruda": salida_cruda(agente, resultado)}
        if metadatos is not None:
            cuerpo["metadatos"] = metadatos
        return self.registrar_crudo(proyecto, token, cuerpo)

    def registrar_crudo(self, proyecto: str, token: str, cuerpo: dict[str, Any]) -> Respuesta:
        return self.http.post(
            f"/proyectos/{proyecto}/resultado", json=cuerpo, headers=con_token(token)
        )

    def aceptado(self, proyecto: str, token: str, orden: int, resultado: object) -> dict[str, Any]:
        respuesta = self.registrar(proyecto, token, orden, resultado)
        assert respuesta.status_code == 200, respuesta.text
        registro: dict[str, Any] = respuesta.json()
        assert registro["desenlace"] == "aceptada", registro
        return registro

    def enviar_brief(
        self, proyecto: str, respuestas: dict[str, Any], texto_libre: str | None = None
    ) -> Respuesta:
        cuerpo: dict[str, Any] = {"respuestas": respuestas}
        if texto_libre is not None:
            cuerpo["texto_libre"] = texto_libre
        return self.http.post(f"/proyectos/{proyecto}/brief", json=cuerpo)

    @contextmanager
    def abrir(self, proyecto: str) -> Iterator[Proyecto]:
        with abrir_proyecto(proyecto, self.raiz) as abierto:
            yield abierto


@contextmanager
def cliente_api(raiz: Path) -> Iterator[ClienteApi]:
    app = crear_app()
    reloj = Reloj()
    app.dependency_overrides[dependencias.raiz_proyectos] = lambda: raiz
    app.dependency_overrides[dependencias.reloj] = lambda: reloj.ahora
    with TestClient(app) as http:
        yield ClienteApi(http, raiz, reloj)


def error(respuesta: Respuesta) -> tuple[int, str, str | None]:
    """Estado HTTP, código y requisito de una respuesta de error."""
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"codigo", "requisito", "detalle"}, cuerpo
    assert isinstance(cuerpo["detalle"], str) and cuerpo["detalle"]
    return respuesta.status_code, cuerpo["codigo"], cuerpo["requisito"]
