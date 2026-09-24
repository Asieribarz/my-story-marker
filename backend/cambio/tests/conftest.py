from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from backend.proyecto import manejadores
from backend.proyecto.tests.cliente_api import ClienteApi, cliente_api
from backend.shared.tipos import Agente


def _escritor_de_ensayo(
    solicitud: manejadores.SolicitudEntrada, base: dict[str, Any]
) -> dict[str, Any]:
    """El Escritor sin Recuperador, con la versión que le toca (AJ-6)."""
    numero = solicitud.lanzar.capitulo
    assert numero is not None
    version = manejadores._version_del_escritor(
        solicitud.proyecto.conexion, numero, solicitud.lanzar.intento
    )
    return {**base, "version": version, "rutas_prompt": [], "tokens_estimados": 0}


def _sin_herramientas(
    solicitud: manejadores.SolicitudEntrada, base: dict[str, Any]
) -> dict[str, Any]:
    return base


@pytest.fixture(autouse=True)
def sin_recuperador_ni_herramientas(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin ficha ni biblia, sin Lean y sin Chromium: el bucle, los gates y la publicación los
    sustituyen las pruebas que los recorren."""
    monkeypatch.setitem(manejadores.CONSTRUCTORES_DE_ENTRADA, Agente.ESCRITOR, _escritor_de_ensayo)
    for agente in (Agente.JUEZ_MANUSCRITO, Agente.EXPORTADOR):
        monkeypatch.setitem(manejadores.CONSTRUCTORES_DE_ENTRADA, agente, _sin_herramientas)
    # M-27: sin fase previa de Lean; los gates los escriben las pruebas.
    monkeypatch.delitem(manejadores.FASES_PREVIAS, Agente.JUEZ_MANUSCRITO, raising=False)


@pytest.fixture
def api(tmp_path: Path) -> Iterator[ClienteApi]:
    with cliente_api(tmp_path) as cliente:
        yield cliente
