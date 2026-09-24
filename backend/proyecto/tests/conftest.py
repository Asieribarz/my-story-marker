from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from backend.proyecto import manejadores
from backend.proyecto.abierto import Proyecto
from backend.proyecto.bloqueo import tomar_bloqueo
from backend.proyecto.persistencia import crear_proyecto
from backend.proyecto.tests.apoyo import AHORA
from backend.shared.tipos import Agente, TipoEjecutor


@pytest.fixture
def proyecto(tmp_path: Path) -> Iterator[Proyecto]:
    abierto = crear_proyecto(AHORA, raiz_proyectos=tmp_path)
    yield abierto
    abierto.cerrar()


@pytest.fixture
def token(proyecto: Proyecto) -> str:
    return tomar_bloqueo(proyecto, TipoEjecutor.SESION, AHORA).token


def _entrada_de_ensayo_del_escritor(
    solicitud: manejadores.SolicitudEntrada, base: dict[str, Any]
) -> dict[str, Any]:
    return {**base, "rutas_prompt": [], "tokens_estimados": 0}


@pytest.fixture(autouse=True)
def escritor_sin_recuperador(monkeypatch: pytest.MonkeyPatch) -> None:
    """Las pruebas de `proyecto/` colocan el bucle sin ficha ni biblia: el Escritor recibe su
    orden sin pasar por el Recuperador. Las que prueban esa entrada lo sustituyen aparte."""
    monkeypatch.setitem(
        manejadores.CONSTRUCTORES_DE_ENTRADA, Agente.ESCRITOR, _entrada_de_ensayo_del_escritor
    )


def _sin_herramientas(
    solicitud: manejadores.SolicitudEntrada, base: dict[str, Any]
) -> dict[str, Any]:
    return base


@pytest.fixture(autouse=True)
def gates_y_pdf_de_ensayo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Las pruebas de `proyecto/` escriben los gates a mano (`gate_resultado`) y no imprimen
    PDF: el juez de manuscrito y el Exportador reciben su orden sin ejecutar Lean ni mirar
    Chromium (TC-3, TC-4), y el Intérprete sin petición en `cambios/` (RF-120). Las de
    `cambio/` y las de integración los sustituyen aparte."""
    for agente in (Agente.JUEZ_MANUSCRITO, Agente.EXPORTADOR, Agente.INTERPRETE_CAMBIOS):
        monkeypatch.setitem(manejadores.CONSTRUCTORES_DE_ENTRADA, agente, _sin_herramientas)
    # M-27: sin fase previa de Lean; los gates los escriben las pruebas.
    monkeypatch.delitem(manejadores.FASES_PREVIAS, Agente.JUEZ_MANUSCRITO, raising=False)
