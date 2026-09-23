from collections.abc import Iterator
from pathlib import Path

import pytest

from backend.proyecto.abierto import Proyecto
from backend.proyecto.bloqueo import tomar_bloqueo
from backend.proyecto.persistencia import crear_proyecto
from backend.proyecto.tests.apoyo import AHORA
from backend.shared.tipos import TipoEjecutor


@pytest.fixture
def proyecto(tmp_path: Path) -> Iterator[Proyecto]:
    abierto = crear_proyecto(AHORA, raiz_proyectos=tmp_path)
    yield abierto
    abierto.cerrar()


@pytest.fixture
def token(proyecto: Proyecto) -> str:
    return tomar_bloqueo(proyecto, TipoEjecutor.SESION, AHORA).token
