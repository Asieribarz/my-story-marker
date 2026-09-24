"""El cliente HTTP de Langfuse: trazas por OTLP, scores en lotes y versiones de prompt.

`Emisor` es la costura de las pruebas: `exportar.py` solo conoce el protocolo, y las
pruebas pasan un emisor en memoria que no abre ninguna conexión.

Los scores van en lotes de `score-create` por `/api/public/ingestion`, y no uno a uno por
`/api/public/scores`: el plan gratuito limita las peticiones, y un proyecto tiene cientos
de scores (I-09). Ese endpoint está obsoleto para trazas, pero sigue aceptando scores
después del 2026-11-16. Un 429 o un 503 se reintenta, con la espera que pida Langfuse.
"""

import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from backend.observabilidad.configuracion import Configuracion

ESPERA_S = 30.0
INTENTOS = 6
ESPERA_MAXIMA_S = 60.0
REINTENTABLES = frozenset({httpx.codes.TOO_MANY_REQUESTS, httpx.codes.SERVICE_UNAVAILABLE})


class ScoresRechazados(RuntimeError):
    """Langfuse aceptó el lote pero rechazó algunos scores (respuesta 207)."""


class Emisor(Protocol):
    def enviar_spans(self, cuerpo: dict[str, Any]) -> None: ...

    def enviar_scores(self, cuerpos: list[dict[str, Any]]) -> None: ...

    def version_de_prompt(self, nombre: str, etiqueta: str) -> int | None: ...

    def crear_prompt(
        self, nombre: str, texto: str, etiquetas: list[str], config: dict[str, Any]
    ) -> int: ...


class ClienteLangfuse:
    def __init__(
        self,
        configuracion: Configuracion,
        transporte: httpx.BaseTransport | None = None,
        dormir: Callable[[float], None] = time.sleep,
    ):
        self._http = httpx.Client(
            base_url=configuracion.url,
            auth=(configuracion.clave_publica, configuracion.clave_secreta),
            timeout=ESPERA_S,
            transport=transporte,
        )
        self._dormir = dormir

    def cerrar(self) -> None:
        self._http.close()

    def _peticion(self, metodo: str, ruta: str, **opciones: Any) -> httpx.Response:
        for intento in range(1, INTENTOS + 1):
            respuesta = self._http.request(metodo, ruta, **opciones)
            if respuesta.status_code not in REINTENTABLES or intento == INTENTOS:
                return respuesta
            self._dormir(_espera(respuesta, intento))
        raise AssertionError("inalcanzable")

    def enviar_spans(self, cuerpo: dict[str, Any]) -> None:
        self._peticion(
            "POST",
            "/api/public/otel/v1/traces",
            json=cuerpo,
            headers={"x-langfuse-ingestion-version": "4"},
        ).raise_for_status()

    def enviar_scores(self, cuerpos: list[dict[str, Any]]) -> None:
        ahora = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        lote = [
            {"id": str(uuid.uuid4()), "type": "score-create", "timestamp": ahora, "body": cuerpo}
            for cuerpo in cuerpos
        ]
        respuesta = self._peticion("POST", "/api/public/ingestion", json={"batch": lote})
        respuesta.raise_for_status()
        errores = respuesta.json().get("errors") or []
        if errores:
            # Solo estado y mensaje: el cuerpo del score no se repite en el log.
            resumen = "; ".join(f"{e.get('status')}: {e.get('message')}" for e in errores[:5])
            raise ScoresRechazados(f"{len(errores)} de {len(lote)} scores rechazados: {resumen}")

    def version_de_prompt(self, nombre: str, etiqueta: str) -> int | None:
        respuesta = self._peticion(
            "GET",
            f"/api/public/v2/prompts/{quote(nombre, safe='')}",
            params={"label": etiqueta, "resolve": "false"},
        )
        if respuesta.status_code == httpx.codes.NOT_FOUND:
            return None
        respuesta.raise_for_status()
        version = respuesta.json().get("version")
        return version if isinstance(version, int) else None

    def crear_prompt(
        self, nombre: str, texto: str, etiquetas: list[str], config: dict[str, Any]
    ) -> int:
        respuesta = self._peticion(
            "POST",
            "/api/public/v2/prompts",
            json={
                "type": "text",
                "name": nombre,
                "prompt": texto,
                "labels": etiquetas,
                "config": config,
                "commitMessage": f"definición de .claude/agents/{nombre}.md",
            },
        )
        respuesta.raise_for_status()
        return int(respuesta.json()["version"])


def _espera(respuesta: httpx.Response, intento: int) -> float:
    """La de `Retry-After` si la trae en segundos; si no, exponencial desde 2 s."""
    cabecera = respuesta.headers.get("retry-after", "")
    try:
        segundos = float(cabecera)
    except ValueError:
        segundos = 2.0**intento
    return min(max(segundos, 0.0), ESPERA_MAXIMA_S)
