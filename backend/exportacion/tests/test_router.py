"""Rutas de `exportacion` (plan-frontend §5.1, decisiones-backend §4.3). Datos ficticios."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.exportacion.publicar import publicar_con
from backend.exportacion.router import router
from backend.exportacion.tests.apoyo import (
    IDENTIFICADOR,
    METADATOS,
    contrato_lectura,
    escribir_version,
    impresora_falsa,
    proyecto_listo,
)
from backend.proyecto.dependencias import raiz_proyectos
from backend.proyecto.errores_http import MANEJADORES_DE_ERROR

BASE = f"/proyectos/{IDENTIFICADOR}"


@pytest.fixture
def cliente(tmp_path: Path) -> Iterator[TestClient]:
    conexion, disposicion = proyecto_listo(tmp_path)
    publicar_con(conexion, disposicion, METADATOS, "2026-09-23T12:00:00Z", impresora_falsa)
    escribir_version(conexion, disposicion, 5, 2)
    publicar_con(conexion, disposicion, METADATOS, "2026-09-24T12:00:00Z", impresora_falsa)
    conexion.close()
    app = FastAPI(exception_handlers=MANEJADORES_DE_ERROR)
    app.include_router(router)
    app.dependency_overrides[raiz_proyectos] = lambda: tmp_path
    with TestClient(app) as c:
        yield c


def test_versiones(cliente: TestClient) -> None:
    respuesta = cliente.get(f"{BASE}/versiones")
    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "versiones": [
            {"version": 1, "publicada": "2026-09-23T12:00:00Z", "cambiados": []},
            {"version": 2, "publicada": "2026-09-24T12:00:00Z", "cambiados": [5]},
        ]
    }


def test_lectura_y_capitulo(cliente: TestClient) -> None:
    lectura = cliente.get(f"{BASE}/versiones/2/lectura")
    assert lectura.status_code == 200 and lectura.headers["content-type"] == "application/json"
    assert contrato_lectura(lectura.json()) == []
    capitulo = cliente.get(f"{BASE}/versiones/2/capitulos/5").json()
    assert capitulo == lectura.json()["capitulos"][4]


def test_manuscrito_y_pdf(cliente: TestClient) -> None:
    md = cliente.get(f"{BASE}/versiones/1/manuscrito")
    assert md.status_code == 200 and md.headers["content-type"].startswith("text/markdown")
    assert md.text.startswith(f"# {METADATOS.titulo}")
    pdf = cliente.get(f"{BASE}/versiones/1/pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"


@pytest.mark.parametrize(
    "ruta", ["/versiones/3/lectura", "/versiones/3/pdf", "/versiones/3/capitulos/5"]
)
def test_version_o_capitulo_inexistente_es_no_encontrado(cliente: TestClient, ruta: str) -> None:
    respuesta = cliente.get(BASE + ruta)
    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "no_encontrado"


def test_proyecto_inexistente(cliente: TestClient) -> None:
    respuesta = cliente.get("/proyectos/" + "f" * 32 + "/versiones")
    assert respuesta.status_code == 404
    assert set(respuesta.json()) == {"codigo", "requisito", "detalle"}


@pytest.mark.parametrize(
    "ruta",
    [
        "versiones/99999999999999999999/lectura",
        "versiones/0/manuscrito",
        "versiones/99999999999999999999/pdf",
        "versiones/1/capitulos/11",
        "versiones/1/capitulos/99999999999999999999",
    ],
)
def test_un_entero_fuera_de_rango_es_422(cliente: TestClient, ruta: str) -> None:
    assert cliente.get(f"{BASE}/{ruta}").status_code == 422
