"""Paso 3 · persistencia del grafo: RF-01, RF-04, RF-06, RF-08a, RF-09a, RF-64b, V-2 y V-33.

Todos los datos son ficticios.
"""

import json
import sqlite3
import sys
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from backend.contexto.tests.referencia import referencia
from backend.intake.persistencia import (
    DecisionInvalida,
    confirmar_hechos,
    guardar_brief,
    hechos_pendientes,
)
from backend.proyecto import persistencia
from backend.proyecto.abierto import Proyecto, abrir_proyecto
from backend.proyecto.bloqueo import BloqueoVisible, bloqueo_vigente, tomar_bloqueo
from backend.proyecto.errores import (
    AgenteSinEsquema,
    BloqueoAjeno,
    DecisionHumanaInvalida,
    OrdenAjena,
    ProyectoEnUso,
    ProyectoInexistente,
    TransicionInvalida,
)
from backend.proyecto.manejadores import MANEJADORES, ContextoManejo, Salida
from backend.proyecto.maquina import (
    AGENTES_DE_CAPITULO,
    TOPE,
    AccionHumana,
    Desenlace,
    Detenida,
    EsperarHumano,
    Instantanea,
    Lanzar,
    MotivoEspera,
    Paso,
    Publicada,
    ResultadoGates,
    TipoDesenlace,
    ViaRegistro,
    aplicar_desenlace,
    resolver,
)
from backend.proyecto.orden import OrdenEmitida
from backend.proyecto.persistencia import (
    CapituloLeido,
    _persistir,
    accion_de_decision,
    borrar_proyecto,
    crear_proyecto,
    decidir,
    emitir_siguiente_orden,
    leer_estado,
    leer_instantanea,
    registrar_resultado,
    reintentar,
)
from backend.proyecto.tests.apoyo import (
    AHORA,
    BRIEF,
    HECHO,
    MOMENTO,
    NORMALIZADO,
    TEXTO_LIBRE,
    despues,
    estado,
    forzar,
    proponer_cambio,
    transiciones,
    volcado,
)
from backend.proyecto.tests.generadores import desenlaces, desenlaces_del_recorrido
from backend.proyecto.transiciones import ORIGENES_DE_DETENIDA, Causa
from backend.shared.db import transaccion
from backend.shared.rutas import IdentificadorInvalido
from backend.shared.tipos import Agente as A
from backend.shared.tipos import DesenlaceOrden, TipoEjecutor
from backend.shared.tipos import EstadoCapitulo as C
from backend.shared.tipos import EstadoProyecto as E

_POR_EJEMPLO = settings(
    max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)


def _orden(emision: object) -> OrdenEmitida:
    assert isinstance(emision, OrdenEmitida), emision
    return emision


def _pasos(pasos: tuple[Paso, ...]) -> list[tuple[str, str, str]]:
    return [(p.origen.value, p.destino.value, p.causa.value) for p in pasos]


# ─── RF-01, RF-02, RF-09a ────────────────────────────────────────────────────


def test_crear_un_proyecto_deja_directorio_base_y_fila_en_intake(tmp_path: Path) -> None:
    with crear_proyecto(AHORA, raiz_proyectos=tmp_path, parada_final=True) as proyecto:
        d = proyecto.disposicion
        assert d.base.is_file()
        assert all(c.is_dir() for c in (d.capitulos, d.prompts, d.export, d.brief, d.cambios))
        leido = leer_estado(proyecto, AHORA)
        assert (leido.estado, leido.parada_plan, leido.parada_final) == (E.INTAKE, False, True)
        assert leido.capitulos == tuple(CapituloLeido(n, C.PENDIENTE, 0) for n in range(1, 11))
        assert (leido.orden_vigente, leido.bloqueo, leido.detenida_desde) == (None, None, None)
        assert leer_instantanea(proyecto) == Instantanea(parada_final=True)
    with abrir_proyecto(d.identificador, tmp_path) as otra_vez:
        assert leer_estado(otra_vez, AHORA).identificador == d.identificador


def test_abrir_un_proyecto_que_no_existe(tmp_path: Path) -> None:
    with pytest.raises(ProyectoInexistente):
        abrir_proyecto("0" * 32, tmp_path)
    with pytest.raises(IdentificadorInvalido):
        abrir_proyecto("../otro", tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_borrar_elimina_la_base_y_el_directorio_enteros(tmp_path: Path) -> None:
    proyecto = crear_proyecto(AHORA, raiz_proyectos=tmp_path)
    guardar_brief(proyecto.conexion, proyecto.disposicion, BRIEF, TEXTO_LIBRE, MOMENTO)
    raiz, identificador = proyecto.disposicion.raiz, proyecto.identificador
    borrar_proyecto(proyecto, AHORA)
    assert not raiz.exists()
    with pytest.raises(ProyectoInexistente):
        abrir_proyecto(identificador, tmp_path)


def test_no_se_borra_un_proyecto_con_el_bloqueo_vigente(tmp_path: Path) -> None:
    proyecto = crear_proyecto(AHORA, raiz_proyectos=tmp_path)
    tomar_bloqueo(proyecto, TipoEjecutor.WORKER, AHORA)
    with pytest.raises(BloqueoAjeno, match="worker"):
        borrar_proyecto(proyecto, despues(10))
    assert proyecto.disposicion.base.is_file()
    borrar_proyecto(proyecto, despues(31))
    assert not proyecto.disposicion.raiz.exists()


def _intacto(raiz: Path, identificador: str) -> None:
    """El proyecto sigue en su sitio, entero, y solo él: ni a medias ni apartado."""
    assert sorted(p.name for p in raiz.iterdir()) == [identificador]
    with abrir_proyecto(identificador, raiz) as proyecto:
        assert leer_estado(proyecto, AHORA).estado is E.INTAKE
        assert proyecto.disposicion.texto_libre.read_text(encoding="utf-8") == TEXTO_LIBRE


def _con_brief(raiz: Path) -> Proyecto:
    proyecto = crear_proyecto(AHORA, raiz_proyectos=raiz)
    guardar_brief(proyecto.conexion, proyecto.disposicion, BRIEF, TEXTO_LIBRE, MOMENTO)
    return proyecto


def test_si_el_directorio_no_se_puede_apartar_no_se_borra_nada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RF-09a: el borrado es entero o no es. En Windows, apartar falla con la base abierta."""
    proyecto = _con_brief(tmp_path)

    def abierto_por_otro(self: Path, destino: Path) -> Path:
        raise PermissionError(32, "el archivo está siendo utilizado por otro proceso")

    monkeypatch.setattr(Path, "rename", abierto_por_otro)
    with pytest.raises(ProyectoEnUso, match="no se ha borrado nada"):
        borrar_proyecto(proyecto, AHORA)
    monkeypatch.undo()
    _intacto(tmp_path, proyecto.identificador)


@pytest.mark.skipif(sys.platform != "win32", reason="solo Windows impide mover una base abierta")
def test_con_otra_conexion_abierta_no_se_borra_nada(tmp_path: Path) -> None:
    proyecto = _con_brief(tmp_path)
    identificador = proyecto.identificador
    with abrir_proyecto(identificador, tmp_path) as otra:
        with pytest.raises(ProyectoEnUso):
            borrar_proyecto(proyecto, AHORA)
        assert leer_estado(otra, AHORA).estado is E.INTAKE
    _intacto(tmp_path, identificador)
    with abrir_proyecto(identificador, tmp_path) as sin_otras:
        borrar_proyecto(sin_otras, AHORA)
    assert list(tmp_path.iterdir()) == []


def test_si_otro_toma_el_bloqueo_mientras_se_aparta_el_proyecto_vuelve_a_su_sitio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La segunda comprobación, ya apartado, no tiene carrera: nadie más lo abre por su id."""
    proyecto = _con_brief(tmp_path)
    tomar_bloqueo(proyecto, TipoEjecutor.WORKER, AHORA)
    vistas: list[datetime] = []

    def libre_la_primera_vez(
        conexion: sqlite3.Connection, ahora: datetime
    ) -> BloqueoVisible | None:
        vistas.append(ahora)
        return None if len(vistas) == 1 else bloqueo_vigente(conexion, ahora)

    monkeypatch.setattr(persistencia, "bloqueo_vigente", libre_la_primera_vez)
    with pytest.raises(BloqueoAjeno, match="worker"):
        borrar_proyecto(proyecto, despues(1))
    assert len(vistas) == 2
    _intacto(tmp_path, proyecto.identificador)


# ─── El flujo de intake y contexto, con sus dos agentes ─────────────────────


def test_intake_y_contexto_de_punta_a_punta(proyecto: Proyecto, token: str) -> None:
    conexion = proyecto.conexion
    assert emitir_siguiente_orden(proyecto, token, AHORA) == EsperarHumano(MotivoEspera.BRIEF)
    guardar_brief(conexion, proyecto.disposicion, BRIEF, TEXTO_LIBRE, MOMENTO)

    extraccion = _orden(emitir_siguiente_orden(proyecto, token, AHORA))
    assert (extraccion.agente, extraccion.intento, extraccion.estado) == (
        A.EXTRACTOR_HECHOS,
        1,
        E.INTAKE,
    )
    assert extraccion.entrada["necesita"] == ["texto_libre"]
    assert extraccion.registro is ViaRegistro.SKILL
    registro = registrar_resultado(proyecto, extraccion.id, {"hechos": [HECHO]}, token, AHORA)
    assert (registro.desenlace, registro.estado) == (DesenlaceOrden.ACEPTADA, E.INTAKE)

    espera = emitir_siguiente_orden(proyecto, token, AHORA)
    assert espera == EsperarHumano(MotivoEspera.CONFIRMACION_HECHOS)
    confirmar_hechos(conexion, {f["id"]: True for f in hechos_pendientes(conexion)}, MOMENTO)

    normalizar = _orden(emitir_siguiente_orden(proyecto, token, AHORA))
    assert normalizar.agente is A.AGENTE_CONTEXTO
    assert normalizar.entrada["necesita"] == ["brief", "hechos_confirmados"]
    registro = registrar_resultado(proyecto, normalizar.id, NORMALIZADO, token, AHORA)
    assert registro.estado is E.CONTEXTO
    assert transiciones(conexion) == [("intake", "contexto", "brief_normalizado")]

    instanciar = _orden(emitir_siguiente_orden(proyecto, token, AHORA))
    assert (instanciar.agente, instanciar.estado) == (A.AGENTE_CONTEXTO, E.CONTEXTO)
    registro = registrar_resultado(proyecto, instanciar.id, referencia(), token, AHORA)
    assert registro.estado is E.PLANIFICACION
    assert conexion.execute("SELECT count(*) FROM contexto").fetchone()[0] == 1

    planificar = _orden(emitir_siguiente_orden(proyecto, token, AHORA))
    assert planificar.agente is A.ARQUITECTO


def test_el_tope_de_una_orden_detiene_y_reintentar_vuelve_a_la_fase(
    proyecto: Proyecto, token: str
) -> None:
    guardar_brief(proyecto.conexion, proyecto.disposicion, BRIEF, TEXTO_LIBRE, MOMENTO)
    informes = []
    for intento in (1, 2, 3):
        orden = _orden(emitir_siguiente_orden(proyecto, token, AHORA))
        assert (orden.agente, orden.intento) == (A.EXTRACTOR_HECHOS, intento)
        informes.append(orden.entrada["informe_anterior"])
        registro = registrar_resultado(proyecto, orden.id, ["no es un sobre"], token, AHORA)
        assert (registro.desenlace, registro.tipo) == (
            DesenlaceOrden.RECHAZADA,
            TipoDesenlace.FALLO_FORMA,
        )
    assert informes[0] is None
    assert informes[1] == informes[2]
    assert informes[1]["errores"][0].startswith("(raíz): ")
    assert emitir_siguiente_orden(proyecto, token, AHORA) == Detenida(E.INTAKE)

    leido = reintentar(proyecto, despues(1), notas="probamos otra vez")
    assert (leido.estado, leido.detenida_desde, leido.intentos_paso) == (E.INTAKE, None, 0)
    otra = _orden(emitir_siguiente_orden(proyecto, token, despues(1)))
    assert (otra.intento, otra.entrada["informe_anterior"]) == (1, None)
    assert transiciones(proyecto.conexion)[-2:] == [
        ("intake", "detenida", "tope_agotado"),
        ("detenida", "intake", "reintentar"),
    ]
    decision = proyecto.conexion.execute(
        "SELECT tipo, decision, notas FROM decision_humana"
    ).fetchone()
    assert tuple(decision) == ("reintentar", "reintentar", "probamos otra vez")


# ─── RF-06, RF-08a: idempotencia, orden ajena y agentes sin esquema ─────────


def _extraccion_vigente(proyecto: Proyecto, token: str) -> OrdenEmitida:
    guardar_brief(proyecto.conexion, proyecto.disposicion, BRIEF, TEXTO_LIBRE, MOMENTO)
    return _orden(emitir_siguiente_orden(proyecto, token, AHORA))


def test_registrar_el_mismo_resultado_dos_veces_devuelve_lo_registrado(
    proyecto: Proyecto, token: str
) -> None:
    orden = _extraccion_vigente(proyecto, token)
    primero = registrar_resultado(proyecto, orden.id, {"hechos": [HECHO]}, token, AHORA)
    antes = volcado(proyecto.conexion)
    segundo = registrar_resultado(proyecto, orden.id, {"hechos": [HECHO]}, token, despues(5))
    assert volcado(proyecto.conexion) == antes
    assert not primero.repetido
    assert segundo == replace(primero, repetido=True)


def test_un_resultado_para_otra_orden_se_rechaza(proyecto: Proyecto, token: str) -> None:
    orden = _extraccion_vigente(proyecto, token)
    antes = volcado(proyecto.conexion)
    with pytest.raises(OrdenAjena, match="no existe"):
        registrar_resultado(proyecto, orden.id + 1, {"hechos": []}, token, AHORA)
    assert volcado(proyecto.conexion) == antes

    registrar_resultado(proyecto, orden.id, {"hechos": [HECHO]}, token, AHORA)
    antes = volcado(proyecto.conexion)
    with pytest.raises(OrdenAjena, match="otro resultado"):
        registrar_resultado(proyecto, orden.id, {"hechos": []}, token, AHORA)
    assert volcado(proyecto.conexion) == antes


def test_un_agente_sin_esquema_no_gasta_intento_ni_cierra_la_orden(
    proyecto: Proyecto, token: str
) -> None:
    forzar(proyecto, E.PLANIFICACION, intentos_paso=1)
    orden = _orden(emitir_siguiente_orden(proyecto, token, AHORA))
    assert (orden.agente, orden.intento) == (A.ARQUITECTO, 2)
    antes = volcado(proyecto.conexion)
    with pytest.raises(AgenteSinEsquema, match="paso 4"):
        registrar_resultado(proyecto, orden.id, {"plan": "lo que sea"}, token, AHORA)
    assert volcado(proyecto.conexion) == antes
    assert emitir_siguiente_orden(proyecto, token, AHORA) == orden


def test_el_informe_del_intento_no_guarda_datos_excluidos(proyecto: Proyecto, token: str) -> None:
    """RF-13: la evidencia de un hallazgo puede traer un dato excluido; no llega a la base."""
    movil = "600 12 34 56"
    forzar(proyecto, E.CONTEXTO)
    orden = _orden(emitir_siguiente_orden(proyecto, token, AHORA))
    contexto = referencia()
    contexto["novela"]["personalizacion"]["destinatario"]["contacto"] = movil
    registro = registrar_resultado(proyecto, orden.id, contexto, token, AHORA)
    assert registro.tipo is TipoDesenlace.FALLO_CONTENIDO
    assert movil not in "\n".join(proyecto.conexion.iterdump())
    auditado = proyecto.conexion.execute("SELECT detalle FROM auditoria").fetchone()
    assert json.loads(auditado["detalle"])["origen"] == "orden.detalle"


# ─── V-33: la orden persistida es la que decide la máquina ──────────────────


@st.composite
def _forzables(draw: st.DrawFn) -> dict[str, Any]:
    estado_proyecto = draw(st.sampled_from(list(E)))
    capitulos = {}
    for n in range(1, 11):
        estado_capitulo = draw(st.sampled_from(list(C)))
        tope = 3 if estado_capitulo is C.REVISION_HUMANA else 2
        capitulos[n] = (estado_capitulo, draw(st.integers(0, tope)))
    desde = None
    if estado_proyecto is E.DETENIDA:
        desde = draw(st.sampled_from(sorted(ORIGENES_DE_DETENIDA)))
    return {
        "estado": estado_proyecto,
        "detenida_desde": desde,
        "intentos_paso": draw(st.integers(0, 2)),
        "ciclos_revision": draw(st.integers(0, 3)),
        "parada_plan": draw(st.booleans()),
        "parada_final": draw(st.booleans()),
        "capitulos": capitulos,
    }


def _ensayo(contexto: ContextoManejo, resultado: object) -> Salida:
    """Manejador de ensayo: el desenlace viene escrito en el resultado."""
    assert isinstance(resultado, dict)
    desenlace = Desenlace(TipoDesenlace(resultado["tipo"]), bool(resultado["veto"]))
    return Salida(desenlace, {"eco": resultado["n"]})


@pytest.fixture
def agentes_de_ensayo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Todos los agentes con el manejador de ensayo, para registrar en cualquier fase."""
    for agente in A:
        monkeypatch.setitem(MANEJADORES, agente, _ensayo)


def _resultado(desenlace: Desenlace, n: int) -> dict[str, object]:
    return {"tipo": desenlace.tipo.value, "veto": desenlace.guardarrail, "n": n}


def _registrar_otra_vez_no_cambia_nada(
    proyecto: Proyecto,
    token: str,
    registro: Any,
    resultado: dict[str, object],
    anterior: int | None,
) -> None:
    """RF-06, RF-08a, V-33: tras registrar, el mismo resultado otra vez devuelve lo registrado;
    uno distinto para esa orden, o cualquiera para una orden anterior, se rechaza. Ninguno de
    los tres escribe."""
    antes = volcado(proyecto.conexion)
    otra_vez = registrar_resultado(proyecto, registro.orden, resultado, token, AHORA)
    assert otra_vez == replace(registro, repetido=True)
    with pytest.raises(OrdenAjena):
        registrar_resultado(proyecto, registro.orden, {**resultado, "n": -1}, token, AHORA)
    if anterior is not None:
        with pytest.raises(OrdenAjena):
            registrar_resultado(proyecto, anterior, {**resultado, "n": -2}, token, AHORA)
    assert volcado(proyecto.conexion) == antes


@_POR_EJEMPLO
@given(forzado=_forzables(), desenlace=desenlaces)
def test_pedir_la_orden_dos_veces_devuelve_la_misma_persistida(
    tmp_path: Path, agentes_de_ensayo: None, forzado: dict[str, Any], desenlace: Desenlace
) -> None:
    with crear_proyecto(AHORA, raiz_proyectos=tmp_path) as proyecto:
        token = tomar_bloqueo(proyecto, TipoEjecutor.SESION, AHORA).token
        forzar(proyecto, **forzado)
        esperado = resolver(leer_instantanea(proyecto))
        primera = emitir_siguiente_orden(proyecto, token, AHORA)
        tras_la_primera = volcado(proyecto.conexion)
        assert emitir_siguiente_orden(proyecto, token, despues(1)) == primera
        assert volcado(proyecto.conexion) == tras_la_primera
        assert transiciones(proyecto.conexion) == _pasos(esperado.pasos)
        leida = leer_instantanea(proyecto)
        decision = esperado.decision
        if not isinstance(decision, Lanzar):
            assert primera == decision
            assert leida == esperado.instantanea
            return
        orden = _orden(primera)
        assert (orden.agente, orden.capitulo, orden.intento) == (
            decision.agente,
            decision.capitulo,
            decision.intento,
        )
        assert orden.entrada["necesita"] == [e.value for e in decision.entrada]
        assert leida.orden_vigente == orden.vigente
        assert leida.estado is orden.estado is esperado.instantanea.estado

        # Y registrar su resultado, en cualquier fase: lo que predice la máquina, idempotente.
        sin_gates = leida.avance.gates is ResultadoGates.SIN_EVALUAR
        if orden.agente is A.JUEZ_MANUSCRITO and sin_gates:
            desenlace = Desenlace.forma()  # aceptado exige los gates del paso 8a
        efecto = aplicar_desenlace(leida, orden.vigente, desenlace)
        resultado = _resultado(desenlace, 0)
        registro = registrar_resultado(proyecto, orden.id, resultado, token, despues(2))
        assert leer_instantanea(proyecto) == efecto.instantanea
        assert registro.estado is efecto.instantanea.estado
        _registrar_otra_vez_no_cambia_nada(proyecto, token, registro, resultado, None)


@pytest.fixture
def agentes_del_bucle_de_prueba(monkeypatch: pytest.MonkeyPatch) -> None:
    """Manejadores de ensayo para el bucle: el desenlace viene escrito en el resultado."""
    for agente in AGENTES_DE_CAPITULO:
        monkeypatch.setitem(MANEJADORES, agente, _ensayo)


@settings(
    max_examples=6, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(data=st.data())
def test_el_bucle_persistido_sigue_paso_a_paso_a_la_maquina(
    tmp_path: Path, agentes_del_bucle_de_prueba: None, data: st.DataObject
) -> None:
    """La instantánea que se lee tras cada registro es la que predijo `aplicar_desenlace`:
    contadores, estados de capítulo, «terminado» derivado de las órdenes y transiciones. Y
    tras cada registro, repetirlo, cambiarlo o mandarlo a la orden anterior no escribe nada."""
    with crear_proyecto(AHORA, raiz_proyectos=tmp_path) as proyecto:
        token = tomar_bloqueo(proyecto, TipoEjecutor.SESION, AHORA).token
        forzar(proyecto, E.CAPITULOS)
        anterior: int | None = None
        for n in range(400):
            emision = emitir_siguiente_orden(proyecto, token, AHORA)
            if not isinstance(emision, OrdenEmitida) or emision.agente not in AGENTES_DE_CAPITULO:
                break
            desenlace = data.draw(desenlaces_del_recorrido)
            esperado = aplicar_desenlace(leer_instantanea(proyecto), emision.vigente, desenlace)
            previas = len(transiciones(proyecto.conexion))
            resultado = _resultado(desenlace, n)
            registro = registrar_resultado(proyecto, emision.id, resultado, token, AHORA)
            assert leer_instantanea(proyecto) == esperado.instantanea
            assert transiciones(proyecto.conexion)[previas:] == _pasos(esperado.pasos)
            assert registro.estado is esperado.instantanea.estado
            _registrar_otra_vez_no_cambia_nada(proyecto, token, registro, resultado, anterior)
            anterior = emision.id
        assert estado(proyecto.conexion) in (E.VERIFICACION_MANUSCRITO, E.DETENIDA)


# ─── V-2: repetir un paso N veces deja las mismas filas ─────────────────────


def _una_sola_vez(accion: Callable[[], object]) -> Callable[[], object]:
    """Una acción humana repetida ya no está en su parada, o ya no tiene qué decidir: se
    rechaza sin escribir. Repetirla deja las mismas filas que hacerla una vez."""

    def ejecutar() -> object:
        try:
            return accion()
        except (TransicionInvalida, DecisionHumanaInvalida, DecisionInvalida):
            return None

    return ejecutar


# Los pasos del bucle de capítulo que se repiten, con el desenlace que se registra.
_EN_EL_BUCLE: dict[str, tuple[C, Desenlace]] = {
    "escritor": (C.PENDIENTE, Desenlace.aceptado()),
    "editor_mal_formado": (C.BORRADOR, Desenlace.forma()),
    "juez_rechaza": (C.VERIFICADO, Desenlace.contenido()),
    "bibliotecario": (C.APROBADO, Desenlace.aceptado()),
}


def _preparar(proyecto: Proyecto, token: str, paso: str) -> Callable[[], object]:
    conexion, disposicion = proyecto.conexion, proyecto.disposicion
    if paso == "emitir":
        guardar_brief(conexion, disposicion, BRIEF, TEXTO_LIBRE, MOMENTO)
        return lambda: emitir_siguiente_orden(proyecto, token, AHORA)
    if paso in _EN_EL_BUCLE:
        capitulo, desenlace = _EN_EL_BUCLE[paso]
        forzar(proyecto, E.CAPITULOS, capitulos={1: (capitulo, 0)})
        orden = _orden(emitir_siguiente_orden(proyecto, token, AHORA))
        del_bucle = _resultado(desenlace, 0)
        return lambda: registrar_resultado(proyecto, orden.id, del_bucle, token, AHORA)
    if paso == "aprobar_plan":
        forzar(proyecto, E.APROBACION_PLAN, parada_plan=True)
        return _una_sola_vez(lambda: decidir(proyecto, AccionHumana.APROBAR_PLAN, AHORA))
    if paso == "reintentar":
        forzar(proyecto, E.DETENIDA, detenida_desde=E.CONTEXTO, intentos_paso=2)
        return _una_sola_vez(lambda: reintentar(proyecto, AHORA))
    if paso == "confirmar_hechos":
        extraccion = _extraccion_vigente(proyecto, token)
        registrar_resultado(proyecto, extraccion.id, {"hechos": [HECHO]}, token, AHORA)
        pendientes = {f["id"]: True for f in hechos_pendientes(conexion)}
        return _una_sola_vez(lambda: confirmar_hechos(conexion, pendientes, MOMENTO))
    resultados: dict[str, tuple[E, bool, object]] = {
        "extractor": (E.INTAKE, True, {"hechos": [HECHO, {"tipo": "mascota"}]}),
        "extractor_mal_formado": (E.INTAKE, True, "texto suelto"),
        "normalizar": (E.INTAKE, False, NORMALIZADO),
        "contexto_valido": (E.CONTEXTO, False, referencia()),
        "contexto_invalido": (E.CONTEXTO, False, {"novela": {"publico": "adulto"}}),
    }
    fase, con_texto, resultado = resultados[paso]
    guardar_brief(conexion, disposicion, BRIEF, TEXTO_LIBRE if con_texto else None, MOMENTO)
    forzar(proyecto, fase)
    orden = _orden(emitir_siguiente_orden(proyecto, token, AHORA))
    return lambda: registrar_resultado(proyecto, orden.id, resultado, token, AHORA)


_PASOS_REPETIBLES = [
    "emitir",
    "extractor",
    "extractor_mal_formado",
    "normalizar",
    "contexto_valido",
    "contexto_invalido",
    *_EN_EL_BUCLE,
    "aprobar_plan",
    "reintentar",
    "confirmar_hechos",
]


@_POR_EJEMPLO
@given(paso=st.sampled_from(_PASOS_REPETIBLES), veces=st.integers(2, 5))
def test_repetir_un_paso_deja_el_mismo_conjunto_de_filas(
    tmp_path: Path, agentes_del_bucle_de_prueba: None, paso: str, veces: int
) -> None:
    with crear_proyecto(AHORA, raiz_proyectos=tmp_path) as proyecto:
        token = tomar_bloqueo(proyecto, TipoEjecutor.SESION, AHORA).token
        ejecutar = _preparar(proyecto, token, paso)
        primero = ejecutar()
        filas = volcado(proyecto.conexion)
        for _ in range(veces - 1):
            repetido = ejecutar()
            assert volcado(proyecto.conexion) == filas
            if isinstance(primero, OrdenEmitida):
                assert repetido == primero


# ─── RF-04: una transición fuera de la tabla no modifica la fila ────────────


def test_una_accion_fuera_de_su_parada_no_modifica_nada(proyecto: Proyecto) -> None:
    antes = volcado(proyecto.conexion)
    with pytest.raises(TransicionInvalida, match="intake a escaleta"):
        decidir(proyecto, AccionHumana.APROBAR_PLAN, AHORA)
    with pytest.raises(TransicionInvalida):
        reintentar(proyecto, AHORA)
    assert volcado(proyecto.conexion) == antes


def test_un_paso_que_no_esta_en_la_tabla_no_se_escribe(proyecto: Proyecto) -> None:
    antes = volcado(proyecto.conexion)
    inst = leer_instantanea(proyecto)
    salto = Instantanea(estado=E.PUBLICADA)
    with pytest.raises(TransicionInvalida), transaccion(proyecto.conexion):
        _persistir(
            proyecto.conexion,
            inst,
            salto,
            (Paso(E.INTAKE, E.PUBLICADA, Causa.VERSION_PUBLICADA),),
            MOMENTO,
        )
    assert volcado(proyecto.conexion) == antes


# ─── V-14: las paradas persistidas solo salen con la acción humana ──────────

_SALIDA_HUMANA = {
    E.APROBACION_PLAN: AccionHumana.APROBAR_PLAN,
    E.APROBACION_FINAL: AccionHumana.APROBAR_FINAL,
    E.PUBLICADA: AccionHumana.PEDIR_CAMBIO,
    E.CAMBIO_SOLICITADO: AccionHumana.CONFIRMAR_CAMBIO,
    E.DETENIDA: AccionHumana.REINTENTAR,
}


@_POR_EJEMPLO
@given(
    parada=st.sampled_from(sorted(_SALIDA_HUMANA)),
    llamadas=st.lists(st.one_of(st.just(0), st.integers(1, 5)), max_size=8),
)
def test_ninguna_secuencia_automatica_sale_de_una_parada(
    tmp_path: Path, parada: E, llamadas: list[int]
) -> None:
    with crear_proyecto(AHORA, raiz_proyectos=tmp_path, parada_plan=True) as proyecto:
        token = tomar_bloqueo(proyecto, TipoEjecutor.SESION, AHORA).token
        desde = E.CONTEXTO if parada is E.DETENIDA else None
        forzar(proyecto, parada, detenida_desde=desde, parada_plan=True, parada_final=True)
        if parada is E.CAMBIO_SOLICITADO:
            proponer_cambio(proyecto)
        antes = volcado(proyecto.conexion)
        for llamada in llamadas:
            if llamada == 0:
                decision = emitir_siguiente_orden(proyecto, token, AHORA)
                assert isinstance(decision, EsperarHumano | Publicada | Detenida)
            else:
                with pytest.raises(OrdenAjena):
                    registrar_resultado(proyecto, llamada, {"hechos": []}, token, AHORA)
        assert volcado(proyecto.conexion) == antes
        decidir(proyecto, _SALIDA_HUMANA[parada], AHORA)
        assert estado(proyecto.conexion) is not parada


# ─── Acciones humanas ────────────────────────────────────────────────────────


def _interprete_de_ensayo(contexto: ContextoManejo, resultado: object) -> Salida:
    """El Intérprete de ensayo: aceptado, deja el cambio propuesto (lo hará el paso 9a)."""
    salida = _ensayo(contexto, resultado)
    if salida.desenlace.tipo is TipoDesenlace.ACEPTADO:
        proponer_cambio(contexto.proyecto)
    return salida


@pytest.fixture
def interprete_de_ensayo(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setitem(MANEJADORES, A.INTERPRETE_CAMBIOS, _interprete_de_ensayo)
    yield


@_POR_EJEMPLO
@given(resultados=st.lists(desenlaces_del_recorrido, min_size=1, max_size=8))
def test_cambio_solicitado_sin_propuesta_solo_sale_sin_humano_por_el_tope_del_interprete(
    tmp_path: Path, interprete_de_ensayo: None, resultados: list[Desenlace]
) -> None:
    """V-14 sin el cambio propuesto (RF-05a, Q6): mientras el Intérprete trabaja, la única
    salida sin acción humana es `publicada` por el tope agotado, al tercer fallo seguido y
    nunca antes. Con la propuesta hecha, la parada espera al humano."""
    with crear_proyecto(AHORA, raiz_proyectos=tmp_path) as proyecto:
        token = tomar_bloqueo(proyecto, TipoEjecutor.SESION, AHORA).token
        forzar(proyecto, E.CAMBIO_SOLICITADO)
        seguidos = 0
        for n, desenlace in enumerate(resultados):
            orden = _orden(emitir_siguiente_orden(proyecto, token, AHORA))
            assert (orden.agente, orden.intento) == (A.INTERPRETE_CAMBIOS, seguidos + 1)
            registrar_resultado(proyecto, orden.id, _resultado(desenlace, n), token, AHORA)
            seguidos = 0 if desenlace.tipo is TipoDesenlace.ACEPTADO else seguidos + 1
            if seguidos == TOPE:
                assert transiciones(proyecto.conexion) == [
                    ("cambio_solicitado", "publicada", "tope_agotado")
                ]
                return
            assert transiciones(proyecto.conexion) == []
            if seguidos == 0:
                espera = emitir_siguiente_orden(proyecto, token, AHORA)
                assert espera == EsperarHumano(MotivoEspera.CONFIRMACION_CAMBIO)
                return
        assert estado(proyecto.conexion) is E.CAMBIO_SOLICITADO


# ─── El informe del intento anterior ─────────────────────────────────────────


def test_un_agente_no_recibe_el_informe_del_fallo_de_otro(proyecto: Proyecto, token: str) -> None:
    """RF-07a: fuera del bucle de capítulo, el informe es del mismo agente. Aunque el
    contador no se hubiera puesto a cero, el Agente de Contexto no hereda el del Extractor."""
    extraccion = _extraccion_vigente(proyecto, token)
    registrar_resultado(proyecto, extraccion.id, "no es un sobre", token, AHORA)
    guardar_brief(proyecto.conexion, proyecto.disposicion, BRIEF, None, MOMENTO)
    normalizar = _orden(emitir_siguiente_orden(proyecto, token, AHORA))
    assert (normalizar.agente, normalizar.intento) == (A.AGENTE_CONTEXTO, 2)
    assert normalizar.entrada["informe_anterior"] is None


def test_reintentar_desde_el_bucle_reabre_los_capitulos_en_revision_humana(
    proyecto: Proyecto,
) -> None:
    """RF-64b, sin bloqueo: las acciones humanas no lo exigen (Q7)."""
    tomar_bloqueo(proyecto, TipoEjecutor.WORKER, AHORA)
    capitulos = {n: (C.APROBADO, 0) for n in range(1, 11)}
    capitulos |= {3: (C.REVISION_HUMANA, 3), 7: (C.REVISION_HUMANA, 1)}
    forzar(
        proyecto,
        E.DETENIDA,
        detenida_desde=E.CAPITULOS,
        ciclos_revision=2,
        capitulos=capitulos,
    )
    leido = reintentar(proyecto, AHORA)
    assert (leido.estado, leido.ciclos_revision, leido.detenida_desde) == (E.CAPITULOS, 0, None)
    por_numero = {c.numero: c for c in leido.capitulos}
    assert por_numero[3] == CapituloLeido(3, C.PENDIENTE, 0)
    assert por_numero[7] == CapituloLeido(7, C.PENDIENTE, 0)
    assert por_numero[1] == CapituloLeido(1, C.APROBADO, 0)
    assert transiciones(proyecto.conexion) == [("detenida", "capitulos", "reintentar")]


def test_una_accion_humana_caduca_la_orden_vigente(proyecto: Proyecto, token: str) -> None:
    forzar(proyecto, E.CAMBIO_SOLICITADO)
    orden = _orden(emitir_siguiente_orden(proyecto, token, AHORA))
    assert orden.agente is A.INTERPRETE_CAMBIOS
    with pytest.raises(DecisionHumanaInvalida):
        decidir(proyecto, AccionHumana.RECHAZAR_CAMBIO, AHORA)
    proponer_cambio(proyecto)
    leido = decidir(proyecto, AccionHumana.RECHAZAR_CAMBIO, AHORA, notas="se queda como está")
    assert (leido.estado, leido.orden_vigente) == (E.PUBLICADA, None)
    fila = proyecto.conexion.execute("SELECT desenlace FROM orden").fetchone()
    assert fila["desenlace"] == DesenlaceOrden.CADUCADA
    with pytest.raises(OrdenAjena):
        registrar_resultado(proyecto, orden.id, {"cambio": {}}, token, AHORA)


def test_las_decisiones_se_nombran_como_en_decision_humana() -> None:
    assert accion_de_decision("aprobacion_plan", "cambios") is AccionHumana.CAMBIOS_PLAN
    assert accion_de_decision("reintentar", "reintentar") is AccionHumana.REINTENTAR
    with pytest.raises(DecisionHumanaInvalida):
        accion_de_decision("confirmacion_hechos", "confirmado")
    with pytest.raises(DecisionHumanaInvalida):
        accion_de_decision("aprobacion_plan", "confirmado")
