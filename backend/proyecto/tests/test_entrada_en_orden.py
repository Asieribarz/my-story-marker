"""E-6 · el identificador de `/mcp/entrada` en la orden del Extractor (RF-14, RF-08a, RNF-01).

- La orden lleva el identificador, nunca el texto, emitido en la misma transacción que la
  persiste: si la emisión falla, no queda ni orden ni identificador.
- Pedir otra vez la orden vigente devuelve la misma orden, con el mismo identificador
  mientras se pueda entregar.
- Si ya se canjeó —el subagente que lo hizo murió con su sesión— o le queda menos de
  `MARGEN_DE_ENTREGA`, la misma orden (mismo id, agente e intento) lleva uno nuevo y el
  anterior se retira. El resultado se sigue registrando contra esa orden, y no se gasta
  intento.

Todos los datos son ficticios.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from backend.intake.entrada import CADUCIDAD, MARGEN_DE_ENTREGA, canjear
from backend.intake.persistencia import guardar_brief
from backend.proyecto import persistencia
from backend.proyecto.abierto import Proyecto
from backend.proyecto.bloqueo import renovar_bloqueo, tomar_bloqueo
from backend.proyecto.errores import EntradaNoCanjeable
from backend.proyecto.orden import OrdenEmitida, orden_vigente
from backend.proyecto.persistencia import (
    emitir_siguiente_orden,
    leer_estado,
    registrar_resultado,
)
from backend.proyecto.tests.apoyo import (
    AHORA,
    BRIEF,
    HECHO,
    MOMENTO,
    TEXTO_LIBRE,
    despues,
    transiciones,
)
from backend.shared.tipos import Agente, DesenlaceOrden, TipoEjecutor
from backend.shared.tipos import EstadoProyecto as E


@pytest.fixture
def con_texto(proyecto: Proyecto) -> Proyecto:
    guardar_brief(proyecto.conexion, proyecto.disposicion, BRIEF, TEXTO_LIBRE, MOMENTO)
    return proyecto


def _orden(emision: object) -> OrdenEmitida:
    assert isinstance(emision, OrdenEmitida), emision
    return emision


def _identificador(orden: OrdenEmitida) -> str:
    entrada: dict[str, Any] = orden.entrada["texto_libre"]
    identificador: str = entrada["identificador"]
    return identificador


def _identificadores(proyecto: Proyecto) -> int:
    fila = proyecto.conexion.execute("SELECT count(*) FROM identificador_entrada").fetchone()
    return int(fila[0])


def _ordenes(proyecto: Proyecto) -> int:
    return int(proyecto.conexion.execute("SELECT count(*) FROM orden").fetchone()[0])


def _renovar_el_bloqueo(proyecto: Proyecto, token: str) -> None:
    """El bloqueo dura lo mismo que el identificador: renovarlo antes deja al mismo
    ejecutor pedir la orden cuando el identificador ya no se puede entregar."""
    renovar_bloqueo(proyecto, token, despues(29))


def _misma_orden(renovada: OrdenEmitida, primera: OrdenEmitida) -> None:
    assert (renovada.id, renovada.agente, renovada.intento, renovada.estado) == (
        primera.id,
        primera.agente,
        primera.intento,
        primera.estado,
    )
    assert _identificador(renovada) != _identificador(primera)
    assert {k: v for k, v in renovada.entrada.items() if k != "texto_libre"} == {
        k: v for k, v in primera.entrada.items() if k != "texto_libre"
    }


def test_la_orden_del_extractor_lleva_el_identificador_y_no_el_texto(
    con_texto: Proyecto, token: str, tmp_path: Path
) -> None:
    orden = _orden(emitir_siguiente_orden(con_texto, token, AHORA))
    assert orden.agente is Agente.EXTRACTOR_HECHOS
    assert set(orden.entrada["texto_libre"]) == {"identificador", "caduca"}
    assert orden.entrada["texto_libre"]["caduca"] == "2026-09-23T10:30:00Z"
    assert TEXTO_LIBRE not in json.dumps(orden.entrada, ensure_ascii=False)
    assert _identificadores(con_texto) == 1
    assert canjear(_identificador(orden), despues(1), tmp_path) == TEXTO_LIBRE


def test_pedir_otra_vez_la_orden_vigente_devuelve_el_mismo_identificador(
    con_texto: Proyecto, token: str
) -> None:
    primera = _orden(emitir_siguiente_orden(con_texto, token, AHORA))
    for minutos in (1, 15, 25):
        assert emitir_siguiente_orden(con_texto, token, despues(minutos)) == primera
    assert _identificadores(con_texto) == 1


def test_si_la_emision_falla_no_queda_ni_orden_ni_identificador(
    con_texto: Proyecto, token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def rota(fila: object) -> OrdenEmitida:
        raise RuntimeError("fallo después de emitir el identificador")

    monkeypatch.setattr(persistencia, "orden_de_fila", rota)
    with pytest.raises(RuntimeError):
        emitir_siguiente_orden(con_texto, token, AHORA)
    assert _identificadores(con_texto) == 0
    assert _ordenes(con_texto) == 0


def test_un_identificador_ya_canjeado_se_renueva_en_la_misma_orden(
    con_texto: Proyecto, token: str, tmp_path: Path
) -> None:
    """RNF-01: quien lo canjeó murió con su sesión; el relanzado necesita uno que sirva."""
    primera = _orden(emitir_siguiente_orden(con_texto, token, AHORA))
    canjear(_identificador(primera), despues(1), tmp_path)
    renovada = _orden(emitir_siguiente_orden(con_texto, token, despues(2)))
    _misma_orden(renovada, primera)
    assert renovada.entrada["texto_libre"]["caduca"] == "2026-09-23T10:32:00Z"
    # Persistida antes de devolverla: pedirla otra vez da la misma, con el identificador nuevo.
    assert orden_vigente(con_texto.conexion) == renovada
    assert emitir_siguiente_orden(con_texto, token, despues(3)) == renovada
    assert canjear(_identificador(renovada), despues(3), tmp_path) == TEXTO_LIBRE
    assert (_ordenes(con_texto), leer_estado(con_texto, despues(3)).intentos_paso) == (1, 0)
    assert transiciones(con_texto.conexion) == []


def test_cerca_de_caducar_la_misma_orden_lleva_un_identificador_nuevo(
    con_texto: Proyecto, token: str, tmp_path: Path
) -> None:
    primera = _orden(emitir_siguiente_orden(con_texto, token, AHORA))
    limite = AHORA + CADUCIDAD - MARGEN_DE_ENTREGA
    assert emitir_siguiente_orden(con_texto, token, limite) == primera
    renovada = _orden(emitir_siguiente_orden(con_texto, token, despues(26)))
    _misma_orden(renovada, primera)
    # El anterior, sin canjear, se retira: ya no lo lleva ninguna orden.
    with pytest.raises(EntradaNoCanjeable):
        canjear(_identificador(primera), despues(26), tmp_path)
    assert canjear(_identificador(renovada), despues(26), tmp_path) == TEXTO_LIBRE
    assert _identificadores(con_texto) == 1


def test_con_el_identificador_caducado_la_misma_orden_se_renueva_sin_gastar_intento(
    con_texto: Proyecto, token: str, tmp_path: Path
) -> None:
    primera = _orden(emitir_siguiente_orden(con_texto, token, AHORA))
    _renovar_el_bloqueo(con_texto, token)
    limite = AHORA + CADUCIDAD
    renovada = _orden(emitir_siguiente_orden(con_texto, token, limite))
    _misma_orden(renovada, primera)
    assert renovada.entrada["texto_libre"]["caduca"] == "2026-09-23T11:00:00Z"
    assert (_ordenes(con_texto), leer_estado(con_texto, limite).intentos_paso) == (1, 0)
    assert transiciones(con_texto.conexion) == []
    assert canjear(_identificador(renovada), limite, tmp_path) == TEXTO_LIBRE


def test_el_resultado_se_registra_contra_la_orden_renovada(con_texto: Proyecto, token: str) -> None:
    """RF-08a: es la misma orden, así que su resultado vale aunque se pidiera antes."""
    primera = _orden(emitir_siguiente_orden(con_texto, token, AHORA))
    _renovar_el_bloqueo(con_texto, token)
    emitir_siguiente_orden(con_texto, token, despues(30))
    registro = registrar_resultado(con_texto, primera.id, {"hechos": [HECHO]}, token, despues(31))
    assert registro.desenlace is DesenlaceOrden.ACEPTADA


def test_un_resultado_que_llega_antes_de_pedir_otra_orden_se_registra_aunque_caduque(
    con_texto: Proyecto, token: str
) -> None:
    """La entrega se mira al devolver la orden vigente, no al registrar: el Extractor ya
    canjeó el texto y su resultado vale."""
    orden = _orden(emitir_siguiente_orden(con_texto, token, AHORA))
    _renovar_el_bloqueo(con_texto, token)
    registro = registrar_resultado(con_texto, orden.id, {"hechos": [HECHO]}, token, despues(35))
    assert registro.desenlace is DesenlaceOrden.ACEPTADA


def test_un_reintento_renovado_conserva_su_intento_y_su_informe(
    con_texto: Proyecto, token: str
) -> None:
    primera = _orden(emitir_siguiente_orden(con_texto, token, AHORA))
    fallo = registrar_resultado(con_texto, primera.id, "no es un sobre", token, AHORA)
    assert fallo.desenlace is DesenlaceOrden.RECHAZADA
    segunda = _orden(emitir_siguiente_orden(con_texto, token, AHORA))
    assert segunda.intento == 2 and segunda.entrada["informe_anterior"] is not None

    _renovar_el_bloqueo(con_texto, token)
    renovada = _orden(emitir_siguiente_orden(con_texto, token, despues(30)))
    _misma_orden(renovada, segunda)
    assert renovada.entrada["informe_anterior"] == segunda.entrada["informe_anterior"]
    assert leer_estado(con_texto, despues(30)).intentos_paso == 1


@pytest.mark.parametrize("canjeado", [True, False])
def test_una_sesion_que_reanuda_recibe_un_identificador_que_puede_canjear(
    con_texto: Proyecto, tmp_path: Path, canjeado: bool
) -> None:
    """RNF-01, V-1: la sesión toma el bloqueo, emite la orden un minuto después y muere, con
    el identificador canjeado o sin canjear. La sesión nueva entra al caducar el bloqueo, que
    es cuando al identificador le queda un minuto: recibe la misma orden con uno que sirve, y
    el Extractor relanzado no gasta un intento."""
    muerta = tomar_bloqueo(con_texto, TipoEjecutor.SESION, AHORA).token
    primera = _orden(emitir_siguiente_orden(con_texto, muerta, despues(1)))
    if canjeado:
        canjear(_identificador(primera), despues(2), tmp_path)

    nueva = tomar_bloqueo(con_texto, TipoEjecutor.SESION, despues(30)).token
    reanudada = _orden(emitir_siguiente_orden(con_texto, nueva, despues(30)))
    _misma_orden(reanudada, primera)
    assert canjear(_identificador(reanudada), despues(31), tmp_path) == TEXTO_LIBRE
    registro = registrar_resultado(con_texto, reanudada.id, {"hechos": [HECHO]}, nueva, despues(32))
    assert (registro.desenlace, registro.estado) == (DesenlaceOrden.ACEPTADA, E.INTAKE)
    assert leer_estado(con_texto, despues(32)).intentos_paso == 0
