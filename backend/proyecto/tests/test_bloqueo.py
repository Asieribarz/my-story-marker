"""V-34 (RF-09b, Q7): un solo ejecutor por proyecto, con el reloj inyectado.

Las pruebas de concurrencia abren dos conexiones sobre la misma base, como dos peticiones
en paralelo, y las lanzan desde dos hilos a la vez. La lectura que precede a la escritura se
hace lenta a propósito: sin la transacción, los dos hilos leerían «libre» antes de que
ninguno escribiese, y los dos tomarían el bloqueo o emitirían una orden.
"""

import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pytest

from backend.intake.persistencia import guardar_brief
from backend.proyecto import bloqueo, persistencia
from backend.proyecto.abierto import Proyecto, abrir_proyecto
from backend.proyecto.bloqueo import (
    DURACION,
    Bloqueo,
    BloqueoVisible,
    renovar_bloqueo,
    soltar_bloqueo,
    tomar_bloqueo,
)
from backend.proyecto.errores import BloqueoAjeno, BloqueoRequerido
from backend.proyecto.maquina import AccionHumana, EsperarHumano
from backend.proyecto.orden import OrdenEmitida, orden_vigente
from backend.proyecto.persistencia import (
    crear_proyecto,
    decidir,
    emitir_siguiente_orden,
    leer_estado,
    registrar_resultado,
)
from backend.proyecto.tests.apoyo import AHORA, BRIEF, MOMENTO, TEXTO_LIBRE, despues, forzar
from backend.shared.tipos import EstadoProyecto as E
from backend.shared.tipos import TipoEjecutor

# Lo bastante para que el otro hilo llegue a su lectura; muy por debajo de `busy_timeout`.
_PAUSA = 0.3


def test_con_el_bloqueo_tomado_otro_ejecutor_no_recibe_orden(proyecto: Proyecto) -> None:
    sesion = tomar_bloqueo(proyecto, TipoEjecutor.SESION, AHORA)
    assert sesion.caduca == AHORA + DURACION
    with pytest.raises(BloqueoAjeno) as denegado:
        tomar_bloqueo(proyecto, TipoEjecutor.WORKER, despues(10))
    assert (denegado.value.tipo, denegado.value.caduca) == (TipoEjecutor.SESION, sesion.caduca)
    assert "sesion" in str(denegado.value)
    with pytest.raises(BloqueoAjeno):
        emitir_siguiente_orden(proyecto, "token-inventado", despues(10))
    assert isinstance(emitir_siguiente_orden(proyecto, sesion.token, despues(10)), EsperarHumano)


def test_al_caducar_otro_ejecutor_puede_tomarlo(proyecto: Proyecto) -> None:
    sesion = tomar_bloqueo(proyecto, TipoEjecutor.SESION, AHORA)
    worker = tomar_bloqueo(proyecto, TipoEjecutor.WORKER, despues(31))
    assert worker.token != sesion.token
    with pytest.raises(BloqueoAjeno) as denegado:
        emitir_siguiente_orden(proyecto, sesion.token, despues(32))
    assert denegado.value.tipo is TipoEjecutor.WORKER
    assert isinstance(emitir_siguiente_orden(proyecto, worker.token, despues(32)), EsperarHumano)


def test_renovar_alarga_el_bloqueo(proyecto: Proyecto) -> None:
    sesion = tomar_bloqueo(proyecto, TipoEjecutor.SESION, AHORA)
    renovado = renovar_bloqueo(proyecto, sesion.token, despues(20))
    assert renovado.caduca == despues(20) + DURACION
    with pytest.raises(BloqueoAjeno):
        tomar_bloqueo(proyecto, TipoEjecutor.WORKER, despues(40))
    emitir_siguiente_orden(proyecto, sesion.token, despues(45))


def test_sin_bloqueo_o_con_el_propio_caducado_no_hay_orden(proyecto: Proyecto) -> None:
    with pytest.raises(BloqueoRequerido, match="nadie lo ha tomado"):
        emitir_siguiente_orden(proyecto, "cualquiera", AHORA)
    sesion = tomar_bloqueo(proyecto, TipoEjecutor.SESION, AHORA)
    with pytest.raises(BloqueoRequerido, match="caducó"):
        emitir_siguiente_orden(proyecto, sesion.token, despues(30))
    with pytest.raises(BloqueoRequerido):
        renovar_bloqueo(proyecto, sesion.token, despues(30))


def test_registrar_un_resultado_exige_el_bloqueo(proyecto: Proyecto) -> None:
    guardar_brief(proyecto.conexion, proyecto.disposicion, BRIEF, TEXTO_LIBRE, MOMENTO)
    sesion = tomar_bloqueo(proyecto, TipoEjecutor.SESION, AHORA)
    orden = emitir_siguiente_orden(proyecto, sesion.token, AHORA)
    assert isinstance(orden, OrdenEmitida)
    soltar_bloqueo(proyecto, sesion.token, despues(1))
    worker = tomar_bloqueo(proyecto, TipoEjecutor.WORKER, despues(2))
    with pytest.raises(BloqueoAjeno):
        registrar_resultado(proyecto, orden.id, {"hechos": []}, sesion.token, despues(3))
    registro = registrar_resultado(proyecto, orden.id, {"hechos": []}, worker.token, despues(3))
    assert registro.orden == orden.id


def test_soltar_libera_y_solo_lo_suelta_quien_lo_tiene(proyecto: Proyecto) -> None:
    sesion = tomar_bloqueo(proyecto, TipoEjecutor.SESION, AHORA)
    with pytest.raises(BloqueoAjeno):
        soltar_bloqueo(proyecto, "ajeno", despues(1))
    soltar_bloqueo(proyecto, sesion.token, despues(1))
    assert leer_estado(proyecto, despues(1)).bloqueo is None
    soltar_bloqueo(proyecto, sesion.token, despues(2))
    tomar_bloqueo(proyecto, TipoEjecutor.WORKER, despues(2))


def test_el_estado_dice_quien_tiene_el_bloqueo_pero_no_su_token(proyecto: Proyecto) -> None:
    sesion = tomar_bloqueo(proyecto, TipoEjecutor.SESION, AHORA)
    visible = leer_estado(proyecto, despues(5)).bloqueo
    assert visible is not None
    assert (visible.tipo, visible.caduca) == (TipoEjecutor.SESION, sesion.caduca)
    assert sesion.token not in repr(leer_estado(proyecto, despues(5)))
    assert leer_estado(proyecto, despues(31)).bloqueo is None


def test_las_acciones_humanas_no_exigen_el_bloqueo(proyecto: Proyecto) -> None:
    tomar_bloqueo(proyecto, TipoEjecutor.WORKER, AHORA)
    forzar(proyecto, E.APROBACION_PLAN, parada_plan=True)
    leido = decidir(proyecto, AccionHumana.CAMBIOS_PLAN, despues(1), notas="más dragones")
    assert leido.estado is E.PLANIFICACION


@pytest.mark.parametrize("ajeno", ["é", "ñandú", "\ud800", "€" * 40])
def test_un_token_con_caracteres_no_ascii_es_un_bloqueo_ajeno(
    proyecto: Proyecto, ajeno: str
) -> None:
    """La cabecera `X-Bloqueo` puede traer cualquier carácter: no es el token de nadie."""
    sesion = tomar_bloqueo(proyecto, TipoEjecutor.SESION, AHORA)
    with pytest.raises(BloqueoAjeno):
        emitir_siguiente_orden(proyecto, ajeno, despues(1))
    with pytest.raises(BloqueoAjeno):
        renovar_bloqueo(proyecto, ajeno, despues(1))
    with pytest.raises(BloqueoAjeno):
        soltar_bloqueo(proyecto, ajeno, despues(1))
    assert renovar_bloqueo(proyecto, sesion.token, despues(2)).token == sesion.token


# ─── Dos ejecutores a la vez, con dos conexiones ─────────────────────────────


@pytest.fixture
def dos_conexiones(tmp_path: Path) -> Iterator[tuple[Proyecto, Proyecto]]:
    with crear_proyecto(AHORA, raiz_proyectos=tmp_path) as creado:
        identificador = creado.identificador
    with (
        abrir_proyecto(identificador, tmp_path) as uno,
        abrir_proyecto(identificador, tmp_path) as otro,
    ):
        yield uno, otro


def _a_la_vez[T](
    primera: Callable[[], T], segunda: Callable[[], T]
) -> tuple[T | Exception, T | Exception]:
    """Lanza las dos llamadas desde dos hilos que arrancan juntos; devuelve lo que dé cada una,
    valor o excepción."""
    salida = threading.Barrier(2)

    def lanzar(llamada: Callable[[], T]) -> T | Exception:
        salida.wait()
        try:
            return llamada()
        except Exception as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as hilos:
        a, b = hilos.submit(lanzar, primera), hilos.submit(lanzar, segunda)
        return a.result(), b.result()


def test_dos_ejecutores_a_la_vez_solo_uno_toma_el_bloqueo(
    dos_conexiones: tuple[Proyecto, Proyecto], monkeypatch: pytest.MonkeyPatch
) -> None:
    uno, otro = dos_conexiones
    leer = bloqueo.bloqueo_vigente

    def lento(conexion: sqlite3.Connection, ahora: datetime) -> BloqueoVisible | None:
        visto = leer(conexion, ahora)
        time.sleep(_PAUSA)
        return visto

    monkeypatch.setattr(bloqueo, "bloqueo_vigente", lento)
    resultados = _a_la_vez(
        lambda: tomar_bloqueo(uno, TipoEjecutor.SESION, AHORA),
        lambda: tomar_bloqueo(otro, TipoEjecutor.WORKER, AHORA),
    )
    tomados = [r for r in resultados if isinstance(r, Bloqueo)]
    denegados = [r for r in resultados if isinstance(r, BloqueoAjeno)]
    assert (len(tomados), len(denegados)) == (1, 1), resultados
    assert denegados[0].tipo is tomados[0].tipo
    monkeypatch.undo()
    visible = leer_estado(uno, AHORA).bloqueo
    assert visible is not None and visible.tipo is tomados[0].tipo


def test_dos_peticiones_a_la_vez_emiten_una_sola_orden(
    dos_conexiones: tuple[Proyecto, Proyecto], monkeypatch: pytest.MonkeyPatch
) -> None:
    uno, otro = dos_conexiones
    token = tomar_bloqueo(uno, TipoEjecutor.SESION, AHORA).token
    forzar(uno, E.CONTEXTO)
    leer = orden_vigente

    def lenta(conexion: sqlite3.Connection) -> OrdenEmitida | None:
        vista = leer(conexion)
        time.sleep(_PAUSA)
        return vista

    monkeypatch.setattr(persistencia, "orden_vigente", lenta)
    primera, segunda = _a_la_vez(
        lambda: emitir_siguiente_orden(uno, token, despues(1)),
        lambda: emitir_siguiente_orden(otro, token, despues(1)),
    )
    assert isinstance(primera, OrdenEmitida), primera
    assert primera == segunda
    filas = uno.conexion.execute("SELECT count(*) FROM orden").fetchone()[0]
    assert filas == 1
