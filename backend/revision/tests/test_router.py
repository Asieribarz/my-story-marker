"""RF-114: la revisión humana se guarda con la rúbrica del juez y no cambia el estado.

Datos ficticios.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.proyecto.abierto import abrir_proyecto
from backend.proyecto.dependencias import raiz_proyectos, reloj
from backend.revision.router import router
from backend.verificacion.tests.apoyo import IDENTIFICADOR, proyecto
from backend.verificacion.tests.test_juez import AHORA


def _cliente(raiz: Path) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[raiz_proyectos] = lambda: raiz
    app.dependency_overrides[reloj] = lambda: AHORA
    return TestClient(app)


def _rubrica(puntuaciones: list[int]) -> list[dict[str, object]]:
    criterios = ("continuidad", "personajes", "arco_ritmo", "tono", "personalizacion")
    return [
        {"criterio": c, "puntuacion": p, "justificacion": "Ficticia."}
        for c, p in zip(criterios, puntuaciones, strict=True)
    ]


def test_revision_humana_se_guarda_sin_tocar_el_estado(tmp_path: Path) -> None:
    _, conexion = proyecto(tmp_path)
    conexion.close()
    cliente = _cliente(tmp_path)
    url = f"/proyectos/{IDENTIFICADOR}/manuscrito/juez"
    respuesta = cliente.post(url, json={"criterios": _rubrica([4, 4, 3, 3, 4])})
    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert (cuerpo["evaluacion"], cuerpo["revisor"], cuerpo["version_novela"]) == (
        "humano-1",
        "humano",
        1,
    )
    assert (cuerpo["suma"], cuerpo["aprobaria"]) == (18, True)
    assert [e["evaluacion"] for e in cliente.get(url).json()] == ["humano-1"]
    with abrir_proyecto(IDENTIFICADOR, tmp_path) as abierto:
        c = abierto.conexion
        assert c.execute("SELECT estado FROM proyecto").fetchone()[0] == "verificacion_manuscrito"
        assert c.execute("SELECT count(*) FROM gate_resultado").fetchone()[0] == 0


def test_una_rubrica_incompleta_es_422(tmp_path: Path) -> None:
    _, conexion = proyecto(tmp_path)
    conexion.close()
    url = f"/proyectos/{IDENTIFICADOR}/manuscrito/juez"
    respuesta = _cliente(tmp_path).post(url, json={"criterios": _rubrica([4, 4, 4, 4, 4])[:4]})
    assert respuesta.status_code == 422
