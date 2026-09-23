"""Auxiliares de las pruebas del harness. El repo usa `--import-mode=importlib`, así que
`conftest.py` no se puede importar: lo compartido vive aquí."""

from __future__ import annotations

from typing import Any

PROYECTO = "0123456789abcdef0123456789abcdef"


class BackendFalso:
    """Guarda cada petición y responde lo que diga `respuestas[(metodo, ruta)]`."""

    def __init__(self) -> None:
        self.peticiones: list[dict[str, Any]] = []
        self.respuestas: dict[tuple[str, str], tuple[int, Any]] = {}
        self.url = ""
