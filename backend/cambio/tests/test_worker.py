"""El worker con un `claude` falso (TC-10, R-4, TC-8, RF-124).

Éxito, error, cuelgue con tiempo máximo, caída, bloqueo ocupado, sin `claude`, reanudación
de un trabajo `en_curso` y el orden entre proyectos. La prueba real de `claude -p` es manual
y la hace la persona (TC-10).
"""

import json
import sys
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app import crear_app
from backend.cambio import worker
from backend.cambio.consultas import Peticion, decidir_cambio, pedir_cambio
from backend.cambio.tests.apoyo import abrir, proyecto_publicado
from backend.cambio.worker import CausaFallo, ConfigWorker, procesar_uno, reanudar_en_curso
from backend.proyecto.bloqueo import tomar_bloqueo
from backend.proyecto.tests.apoyo import AHORA
from backend.shared.db import transaccion
from backend.shared.tipos import EstadoCambio, EstadoTrabajo, TipoEjecutor

FALSO = Path(__file__).resolve().parent / "claude_falso.py"
PERRA = "Su perra se llama Kira, una galga blanca"


@pytest.fixture
def raiz(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / "proyectos"
    raiz.mkdir()
    monkeypatch.setenv("MSM_PROYECTOS", str(raiz))
    monkeypatch.setenv("MSM_CLAUDE_FALSO_REGISTRO", str(tmp_path / "lanzamientos.jsonl"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-de-prueba-que-no-debe-heredarse")
    return raiz


def _config(raiz: Path, modo: str, monkeypatch: pytest.MonkeyPatch, **otros: Any) -> ConfigWorker:
    monkeypatch.setenv("MSM_CLAUDE_FALSO", modo)
    return ConfigWorker(
        comando=(sys.executable, str(FALSO)), raiz=raiz, reloj=lambda: AHORA, **otros
    )


def _lanzamientos(raiz: Path) -> list[dict[str, Any]]:
    registro = raiz.parent / "lanzamientos.jsonl"
    if not registro.exists():
        return []
    return [json.loads(linea) for linea in registro.read_text(encoding="utf-8").splitlines()]


def _con_cambio(raiz: Path, confirmado: bool = False) -> str:
    identificador = proyecto_publicado(raiz)
    with abrir(raiz, identificador) as proyecto:
        cambio = pedir_cambio(proyecto, Peticion(1, 2, None, "frag", "que se llame Kira"), AHORA)
        if confirmado:
            with transaccion(proyecto.conexion) as c:
                c.execute(
                    "UPDATE cambio_lector SET estado = 'propuesto', hecho = 'h1', "
                    "valor_anterior = (SELECT texto FROM hecho WHERE id = 'h1'), valor_nuevo = ? "
                    "WHERE id = ?",
                    (PERRA, cambio),
                )
                # El trabajo de interpretar ya acabó: el Intérprete propuso.
                c.execute("UPDATE trabajo SET estado = 'hecho', detalle = '{}'")
            decidir_cambio(proyecto, cambio, True, AHORA)
    return identificador


def _trabajos(raiz: Path, identificador: str) -> list[tuple[str, str | None]]:
    with abrir(raiz, identificador) as proyecto:
        return [
            (f["estado"], json.loads(f["detalle"] or "{}").get("causa"))
            for f in proyecto.conexion.execute("SELECT * FROM trabajo ORDER BY id")
        ]


def _estados(raiz: Path, identificador: str) -> tuple[str, str]:
    with abrir(raiz, identificador) as proyecto:
        c = proyecto.conexion
        estado = c.execute("SELECT estado FROM proyecto").fetchone()[0]
        cambio = c.execute("SELECT estado FROM cambio_lector ORDER BY id DESC").fetchone()[0]
        return estado, cambio


def test_un_exito_lanza_una_vez_sin_bare_ni_clave_y_deja_el_trabajo_hecho(
    raiz: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identificador = _con_cambio(raiz)
    resultado = procesar_uno(_config(raiz, "exito", monkeypatch))
    assert resultado is not None and resultado.estado is EstadoTrabajo.HECHO
    lanzamientos = _lanzamientos(raiz)
    assert len(lanzamientos) == 1
    assert lanzamientos[0]["argumentos"] == [
        "-p",
        f"/regenerar {identificador} 1",
        "--permission-prompts",
        "none",
        "--output-format",
        "json",
    ]
    assert lanzamientos[0]["clave"] is False
    assert _trabajos(raiz, identificador) == [(EstadoTrabajo.HECHO, None)]
    assert _estados(raiz, identificador) == ("cambio_solicitado", EstadoCambio.PROPUESTO)
    assert procesar_uno(_config(raiz, "exito", monkeypatch)) is None


@pytest.mark.parametrize(
    ("modo", "causa", "extra"),
    [
        ("error", CausaFallo.SALIDA_CON_ERROR, {}),
        ("bloqueo", CausaFallo.SALIDA_CON_ERROR, {}),
        ("caida", CausaFallo.CAIDA, {}),
        ("cuelgue", CausaFallo.TIEMPO_AGOTADO, {"tiempo_maximo": 2}),
        ("sin_parada", CausaFallo.SIN_PARADA, {}),
    ],
)
def test_un_fallo_se_lanza_una_sola_vez_y_devuelve_el_proyecto_a_publicada(
    raiz: Path, monkeypatch: pytest.MonkeyPatch, modo: str, causa: CausaFallo, extra: Any
) -> None:
    """R-4: una sola ejecución; el trabajo queda fallido y el cambio, fallido y deshecho."""
    identificador = _con_cambio(raiz, confirmado=True)
    resultado = procesar_uno(_config(raiz, modo, monkeypatch, **extra))
    assert resultado is not None and resultado.causa is causa
    assert len(_lanzamientos(raiz)) == 1
    assert _trabajos(raiz, identificador)[0] == (EstadoTrabajo.HECHO, None)  # el de pedir
    assert _trabajos(raiz, identificador)[1] == (EstadoTrabajo.FALLIDO, causa.value)
    assert _estados(raiz, identificador) == ("publicada", EstadoCambio.FALLIDO)
    with abrir(raiz, identificador) as proyecto:
        c = proyecto.conexion
        assert c.execute("SELECT texto FROM hecho WHERE id = 'h1'").fetchone()[0] != PERRA
        assert {tuple(f) for f in c.execute("SELECT estado, version_vigente FROM capitulo")} == {
            ("aprobado", 1)
        }
        ultima = c.execute("SELECT causa FROM transicion ORDER BY id DESC").fetchone()[0]
        assert ultima == "worker_fallido"


def test_un_fallo_con_el_proyecto_ya_en_su_parada_no_deshace_el_cambio(
    raiz: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-4: si `claude` propone el cambio y luego sale con 1, el proyecto está en su parada:
    el trabajo queda hecho, con la causa como aviso, y el cambio sigue propuesto."""
    identificador = _con_cambio(raiz)
    resultado = procesar_uno(_config(raiz, "propone_y_falla", monkeypatch))
    assert resultado is not None and resultado.estado is EstadoTrabajo.HECHO
    assert _estados(raiz, identificador) == ("cambio_solicitado", EstadoCambio.PROPUESTO)
    with abrir(raiz, identificador) as proyecto:
        (detalle,) = proyecto.conexion.execute("SELECT detalle FROM trabajo").fetchone()
    assert json.loads(detalle) == {"codigo_salida": 1, "aviso": CausaFallo.SALIDA_CON_ERROR.value}


def test_al_agotar_el_tiempo_muere_el_arbol_entero(
    raiz: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """R-4: un `claude` colgado se mata con sus descendientes (en Windows, `claude.cmd`
    deja a `claude` como nieto de `cmd.exe`); el nieto no llega a escribir su marca."""
    marca = tmp_path / "marca.txt"
    monkeypatch.setenv("MSM_CLAUDE_FALSO_MARCA", str(marca))
    _con_cambio(raiz, confirmado=True)
    config = _config(raiz, "nieto_colgado", monkeypatch, tiempo_maximo=2)
    resultado = procesar_uno(config)
    assert resultado is not None and resultado.causa is CausaFallo.TIEMPO_AGOTADO
    time.sleep(4)
    assert not marca.exists()


def test_sin_claude_el_trabajo_falla_con_su_causa(
    raiz: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identificador = _con_cambio(raiz)
    monkeypatch.setattr("backend.cambio.worker.shutil.which", lambda nombre: None)
    resultado = procesar_uno(ConfigWorker(raiz=raiz, reloj=lambda: AHORA))
    assert resultado is not None and resultado.causa is CausaFallo.CLAUDE_NO_DISPONIBLE
    assert _estados(raiz, identificador) == ("publicada", EstadoCambio.FALLIDO)


def test_con_el_bloqueo_tomado_no_se_lanza(raiz: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    identificador = _con_cambio(raiz)
    with abrir(raiz, identificador) as proyecto:
        tomar_bloqueo(proyecto, TipoEjecutor.SESION, AHORA)
    assert procesar_uno(_config(raiz, "exito", monkeypatch)) is None
    assert _lanzamientos(raiz) == []
    assert _trabajos(raiz, identificador) == [(EstadoTrabajo.EN_COLA, None)]
    # Caducado el bloqueo, se lanza.
    tarde = ConfigWorker(
        comando=(sys.executable, str(FALSO)), raiz=raiz, reloj=lambda: AHORA + timedelta(hours=1)
    )
    assert procesar_uno(tarde) is not None


def test_un_trabajo_en_curso_al_arrancar_se_reanuda(
    raiz: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identificador = _con_cambio(raiz)
    with abrir(raiz, identificador) as proyecto, transaccion(proyecto.conexion) as c:
        c.execute("UPDATE trabajo SET estado = 'en_curso', empezado = '2026-09-23T09:00:00Z'")
    assert procesar_uno(_config(raiz, "exito", monkeypatch)) is None
    assert reanudar_en_curso(raiz) == 1
    resultado = procesar_uno(_config(raiz, "exito", monkeypatch))
    assert resultado is not None and resultado.estado is EstadoTrabajo.HECHO


def test_procesa_el_trabajo_mas_antiguo_de_todos_los_proyectos(
    raiz: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    primero = _con_cambio(raiz)
    segundo = _con_cambio(raiz)
    with abrir(raiz, segundo) as proyecto, transaccion(proyecto.conexion) as c:
        c.execute("UPDATE trabajo SET creado = '2026-09-23T08:00:00Z'")
    resultado = procesar_uno(_config(raiz, "exito", monkeypatch))
    assert resultado is not None and resultado.proyecto == segundo
    resultado = procesar_uno(_config(raiz, "exito", monkeypatch))
    assert resultado is not None and resultado.proyecto == primero


def test_los_argumentos_solo_llevan_el_id_y_el_numero_y_nunca_bare() -> None:
    with pytest.raises(ValueError):
        worker.argumentos(("claude",), "../otro", 1)
    with pytest.raises(ValueError):
        worker.argumentos(("claude",), "0" * 32, 0)
    with pytest.raises(ValueError):
        worker.argumentos(("claude", "--bare"), "0" * 32, 1)


def test_la_aplicacion_arranca_y_para_el_worker_con_su_lifespan(
    raiz: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identificador = _con_cambio(raiz)
    app = crear_app(worker=_config(raiz, "exito", monkeypatch, intervalo=0.05))
    with TestClient(app):
        for _ in range(200):
            if _trabajos(raiz, identificador)[0][0] == EstadoTrabajo.HECHO:
                break
            time.sleep(0.05)
    assert _trabajos(raiz, identificador) == [(EstadoTrabajo.HECHO, None)]
