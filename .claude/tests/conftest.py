"""Pruebas del harness de Claude Code (specs/plan-agentes.md §7): `uv run pytest .claude/tests`.

No forman parte de las cuatro comprobaciones del backend. El estado local de cada prueba va a
un directorio temporal (`MSM_ESTADO`) y el backend es un servidor falso en un hilo.
"""

from __future__ import annotations

import json
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "harness"))
sys.path.insert(0, str(AQUI))

from apoyo import BackendFalso  # noqa: E402


@pytest.fixture(autouse=True)
def estado_temporal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    carpeta = tmp_path / "estado"
    monkeypatch.setenv("MSM_ESTADO", str(carpeta))
    monkeypatch.setenv("MSM_PROYECTOS", str(tmp_path / "proyectos"))
    # Un puerto cerrado: ninguna prueba habla con un backend real que esté arrancado.
    monkeypatch.setenv("MSM_BACKEND", "http://127.0.0.1:9")
    return carpeta


@pytest.fixture
def backend(monkeypatch: pytest.MonkeyPatch) -> Iterator[BackendFalso]:
    falso = BackendFalso()

    class Manejador(BaseHTTPRequestHandler):
        def _responder(self) -> None:
            largo = int(self.headers.get("Content-Length") or 0)
            crudo = self.rfile.read(largo).decode("utf-8") if largo else ""
            falso.peticiones.append(
                {
                    "metodo": self.command,
                    "ruta": self.path,
                    "token": self.headers.get("X-Bloqueo"),
                    "cuerpo": json.loads(crudo) if crudo else None,
                }
            )
            estado, cuerpo = falso.respuestas.get((self.command, self.path), (404, {"x": 1}))
            datos = b"" if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
            self.send_response(estado)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        do_GET = do_POST = do_DELETE = _responder

        def log_message(self, *args: Any) -> None:
            pass

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    falso.url = f"http://127.0.0.1:{servidor.server_address[1]}"
    monkeypatch.setenv("MSM_BACKEND", falso.url)
    yield falso
    servidor.shutdown()
