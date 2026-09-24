"""Común a todas las pruebas de backend/."""

from collections.abc import Iterator

import pytest

from backend.observabilidad.configuracion import VARIABLE_INTERRUPTOR


@pytest.fixture(autouse=True)
def sin_langfuse(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Ninguna prueba envía nada a Langfuse, aunque la máquina tenga claves en `.env`."""
    monkeypatch.setenv(VARIABLE_INTERRUPTOR, "0")
    yield
