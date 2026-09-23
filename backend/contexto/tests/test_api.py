"""Paso 3 · `POST /proyectos/{id}/contexto/validar` con `TestClient` (RF-21, TC-11).

Valida sin guardar: un contexto con hallazgos responde 200 con el informe, y ninguno de los
dos mueve el proyecto ni escribe. No hay ruta para guardar el contexto: entra solo como
resultado de la orden del Agente de Contexto. V-20 por la API está en
`backend/proyecto/tests/test_api_grafo.py`, que recorre el grafo.

Pocas peticiones a propósito: cosmic-ray ejecuta esta carpeta con cada mutante. Todos los
datos de persona son ficticios.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from backend.contexto.tests.referencia import referencia
from backend.proyecto.tests.cliente_api import ClienteApi, cliente_api, error


@pytest.fixture
def api(tmp_path: Path) -> Iterator[ClienteApi]:
    with cliente_api(tmp_path) as cliente:
        yield cliente


def test_validar_no_guarda_ni_mueve_el_proyecto(api: ClienteApi) -> None:
    proyecto = api.crear()
    ruta = f"/proyectos/{proyecto}/contexto/validar"

    valido = api.http.post(ruta, json=referencia())
    assert valido.status_code == 200, valido.text
    assert (valido.json()["valido"], valido.json()["hallazgos"]) == (True, [])

    datos = referencia()
    datos["novela"]["publico"] = "adulto"
    invalido = api.http.post(ruta, json=datos)
    assert invalido.status_code == 200, invalido.text
    informe = invalido.json()
    assert informe["valido"] is False
    assert informe["hallazgos"][0]["regla"] == "RF-24 · publico_por_edad"
    assert informe["hallazgos"][0]["severidad"] == "bloqueante"

    no_objeto = api.http.post(ruta, json="texto suelto")
    assert no_objeto.json()["hallazgos"][0]["regla"] == "RF-23 · raiz"

    assert api.estado(proyecto)["estado"] == "intake"
    with api.abrir(proyecto) as abierto:
        assert abierto.conexion.execute("SELECT count(*) FROM contexto").fetchone()[0] == 0


def test_validar_exige_cuerpo_y_proyecto(api: ClienteApi) -> None:
    proyecto = api.crear()
    sin_cuerpo = api.http.post(f"/proyectos/{proyecto}/contexto/validar")
    assert error(sin_cuerpo) == (422, "validacion", None)
    ausente = api.http.post(f"/proyectos/{'0' * 32}/contexto/validar", json=referencia())
    assert error(ausente) == (404, "proyecto_inexistente", "RF-02")


def test_no_hay_ruta_para_guardar_el_contexto(api: ClienteApi) -> None:
    proyecto = api.crear()
    guardar = api.http.put(f"/proyectos/{proyecto}/contexto", json=referencia())
    assert error(guardar) == (404, "no_encontrado", None)
