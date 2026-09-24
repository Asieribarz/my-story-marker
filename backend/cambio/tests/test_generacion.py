"""La generación desde la web: la ruta que la encola y el worker que la lanza (TC-8, R-4).

Todos los datos de persona son ficticios (`backend/contexto/tests/referencia.py`). El
`claude` real no se lanza: lo sustituye `claude_falso.py` (TC-10).
"""

import json
import sys
from pathlib import Path

import pytest

from backend.cambio.generacion import encolar_generacion
from backend.cambio.tests.apoyo import abrir, proyecto_publicado
from backend.cambio.worker import CausaFallo, ConfigWorker, procesar_uno
from backend.proyecto.bloqueo import bloqueo_vigente, tomar_bloqueo
from backend.proyecto.persistencia import crear_proyecto
from backend.proyecto.tests.apoyo import AHORA, MOMENTO, forzar
from backend.proyecto.tests.cliente_api import ClienteApi, Respuesta, error
from backend.shared.db import transaccion
from backend.shared.tipos import EstadoProyecto, EstadoTrabajo, TipoEjecutor

FALSO = Path(__file__).resolve().parent / "claude_falso.py"


def _con_brief(raiz: Path, estado: EstadoProyecto = EstadoProyecto.INTAKE) -> str:
    with crear_proyecto(AHORA, raiz_proyectos=raiz) as proyecto:
        with transaccion(proyecto.conexion) as conexion:
            conexion.execute(
                "INSERT INTO brief (id, respuestas, creado) VALUES (1, '{}', ?)", (MOMENTO,)
            )
        desde = EstadoProyecto.CAPITULOS if estado is EstadoProyecto.DETENIDA else None
        forzar(proyecto, estado, detenida_desde=desde)
        return proyecto.identificador


def _proponer_hecho(raiz: Path, identificador: str) -> None:
    with abrir(raiz, identificador) as proyecto, transaccion(proyecto.conexion) as c:
        c.execute(
            "INSERT INTO hecho_propuesto (tipo, texto, prioridad, creado) "
            "VALUES ('objeto', 'una brújula', 'deseable', ?)",
            (MOMENTO,),
        )


def _generar(api: ClienteApi, proyecto: str) -> Respuesta:
    respuesta: Respuesta = api.http.post(f"/proyectos/{proyecto}/generacion")
    return respuesta


# ─── La ruta ─────────────────────────────────────────────────────────────────


def test_generar_encola_un_trabajo_sin_cambio_y_no_lo_duplica(api: ClienteApi) -> None:
    proyecto = _con_brief(api.raiz)
    primera = _generar(api, proyecto)
    assert primera.status_code == 202 and primera.json() == {"trabajo": 1}
    assert _generar(api, proyecto).json() == {"trabajo": 1}
    trabajo = api.http.get(f"/proyectos/{proyecto}/estado").json()["trabajo"]
    assert {k: trabajo[k] for k in ("id", "generacion", "estado", "causa")} == {
        "id": 1,
        "generacion": True,
        "estado": "en_cola",
        "causa": None,
    }


def test_generar_no_cabe_mientras_el_proyecto_espera_a_la_persona(api: ClienteApi) -> None:
    assert error(_generar(api, api.crear())) == (409, "transicion_invalida", "RF-04")
    assert error(_generar(api, proyecto_publicado(api.raiz)))[1] == "transicion_invalida"
    for estado in (EstadoProyecto.APROBACION_PLAN, EstadoProyecto.DETENIDA):
        assert error(_generar(api, _con_brief(api.raiz, estado)))[1] == "transicion_invalida"
    con_hechos = _con_brief(api.raiz)
    _proponer_hecho(api.raiz, con_hechos)
    assert error(_generar(api, con_hechos))[1] == "transicion_invalida"


# ─── El worker ───────────────────────────────────────────────────────────────


@pytest.fixture
def raiz(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / "proyectos"
    raiz.mkdir()
    monkeypatch.setenv("MSM_PROYECTOS", str(raiz))
    monkeypatch.setenv("MSM_CLAUDE_FALSO_REGISTRO", str(tmp_path / "lanzamientos.jsonl"))
    return raiz


def _config(raiz: Path, modo: str, monkeypatch: pytest.MonkeyPatch) -> ConfigWorker:
    monkeypatch.setenv("MSM_CLAUDE_FALSO", modo)
    return ConfigWorker(comando=(sys.executable, str(FALSO)), raiz=raiz, reloj=lambda: AHORA)


def _encolar(raiz: Path, estado: EstadoProyecto = EstadoProyecto.INTAKE) -> str:
    identificador = _con_brief(raiz, estado)
    with abrir(raiz, identificador) as proyecto:
        encolar_generacion(proyecto, AHORA)
    return identificador


def _trabajo(raiz: Path, identificador: str) -> tuple[str, dict[str, object]]:
    with abrir(raiz, identificador) as proyecto:
        fila = proyecto.conexion.execute("SELECT estado, detalle FROM trabajo").fetchone()
        return fila["estado"], json.loads(fila["detalle"])


def _estado(raiz: Path, identificador: str) -> str:
    with abrir(raiz, identificador) as proyecto:
        estado: str = proyecto.conexion.execute("SELECT estado FROM proyecto").fetchone()[0]
        return estado


@pytest.mark.parametrize(("modo", "estado"), [("genera", "publicada"), ("extrae", "intake")])
def test_la_generacion_que_llega_a_una_parada_queda_hecha(
    raiz: Path, monkeypatch: pytest.MonkeyPatch, modo: str, estado: str
) -> None:
    """Publicada, o parada en los hechos del Extractor a la espera del comprador."""
    identificador = _encolar(raiz)
    resultado = procesar_uno(_config(raiz, modo, monkeypatch))
    assert resultado is not None and resultado.estado is EstadoTrabajo.HECHO
    assert _trabajo(raiz, identificador) == ("hecho", {"codigo_salida": 0})
    assert _estado(raiz, identificador) == estado


def test_la_generacion_que_falla_deja_el_proyecto_donde_estaba_y_suelta_el_bloqueo(
    raiz: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-4 en una generación: no hay cambio que deshacer; la posición en el grafo se
    conserva y el bloqueo del worker, cuyo proceso ya no existe, se suelta."""
    identificador = _encolar(raiz, EstadoProyecto.CAPITULOS)
    config = _config(raiz, "sin_parada", monkeypatch)

    def tomar_y_salir(*_: object) -> tuple[None, int]:
        with abrir(raiz, identificador) as proyecto:
            tomar_bloqueo(proyecto, TipoEjecutor.WORKER, AHORA)
        return None, 0

    monkeypatch.setattr("backend.cambio.worker._ejecutar", tomar_y_salir)
    resultado = procesar_uno(config)
    assert resultado is not None and resultado.causa is CausaFallo.SIN_PARADA
    assert _trabajo(raiz, identificador) == (
        "fallido",
        {"codigo_salida": 0, "causa": CausaFallo.SIN_PARADA.value},
    )
    assert _estado(raiz, identificador) == "capitulos"
    with abrir(raiz, identificador) as proyecto:
        assert bloqueo_vigente(proyecto.conexion, AHORA) is None
        # Se vuelve a lanzar desde la web: un trabajo nuevo que reanuda.
        assert encolar_generacion(proyecto, AHORA) == 2
