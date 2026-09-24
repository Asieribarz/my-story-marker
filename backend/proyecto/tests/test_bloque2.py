"""Bloque 2 · el cerebro con las rebanadas: el sello con la generación del bloqueo (AJ-4,
V-34), la entrada del Escritor y la decisión `error` (§4.1.4, AJ-5), la revisión capítulo a
capítulo con las pasadas (AJ-2, AJ-3) y el registro de los canjes de `/mcp/entrada`
(§4.1.10).

Todos los datos son ficticios.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from backend.capitulo import biblia, ensamblado
from backend.intake.entrada import canjear
from backend.intake.persistencia import guardar_brief
from backend.proyecto import manejadores
from backend.proyecto.abierto import Proyecto
from backend.proyecto.bloqueo import renovar_bloqueo, tomar_bloqueo
from backend.proyecto.errores import EntradaInvalida, EntradaNoCanjeable, SelloInvalido
from backend.proyecto.maquina import Desenlace, ErrorConCausa, Lanzar
from backend.proyecto.modelos import siguiente_de
from backend.proyecto.orden import OrdenEmitida
from backend.proyecto.persistencia import (
    decidir_parada,
    emitir_siguiente_orden,
    leer_estado,
    registrar_resultado,
)
from backend.proyecto.sello import orden_de_sello
from backend.proyecto.tests.apoyo import (
    AHORA,
    BRIEF,
    MOMENTO,
    TEXTO_LIBRE,
    despues,
    forzar,
    registrar,
    volcado,
)
from backend.shared.db import transaccion
from backend.shared.tipos import Agente, TipoEjecutor
from backend.shared.tipos import EstadoCapitulo as C
from backend.shared.tipos import EstadoProyecto as E

HECHOS = '```json\n{"hechos": []}\n```'


def _orden(emision: object) -> OrdenEmitida:
    assert isinstance(emision, OrdenEmitida), emision
    return emision


@pytest.fixture
def con_texto(proyecto: Proyecto) -> Proyecto:
    guardar_brief(proyecto.conexion, proyecto.disposicion, BRIEF, TEXTO_LIBRE, MOMENTO)
    return proyecto


# ─── V-34 con la generación: AJ-4 ────────────────────────────────────────────


def test_el_sello_viejo_se_rechaza_al_cambiar_el_titular_del_bloqueo(con_texto: Proyecto) -> None:
    sesion = tomar_bloqueo(con_texto, TipoEjecutor.SESION, AHORA)
    orden = _orden(emitir_siguiente_orden(con_texto, sesion.token, AHORA))
    viejo = orden.sello
    assert viejo == f"{con_texto.identificador}:{orden.id}:1"
    assert orden_de_sello(con_texto.conexion, viejo).id == orden.id

    # Control: renovar el bloqueo no es cambiar de titular; el sello sigue valiendo.
    renovar_bloqueo(con_texto, sesion.token, despues(10))
    assert _orden(emitir_siguiente_orden(con_texto, sesion.token, despues(11))).sello == viejo

    # La sesión muere; el worker toma el bloqueo caducado y la orden se vuelve a sellar.
    worker = tomar_bloqueo(con_texto, TipoEjecutor.WORKER, despues(41))
    reanudada = _orden(emitir_siguiente_orden(con_texto, worker.token, despues(41)))
    assert (reanudada.id, reanudada.intento) == (orden.id, orden.intento)
    assert reanudada.sello == f"{con_texto.identificador}:{orden.id}:2"
    with pytest.raises(SelloInvalido):
        orden_de_sello(con_texto.conexion, viejo)
    antes = volcado(con_texto.conexion)
    with pytest.raises(SelloInvalido):
        registrar_resultado(con_texto, viejo, HECHOS, worker.token, despues(42))
    assert volcado(con_texto.conexion) == antes
    registro = registrar_resultado(con_texto, reanudada.sello or "", HECHOS, worker.token, AHORA)
    assert registro.orden == orden.id and not registro.repetido


def test_al_volver_a_sellar_el_extractor_recibe_otro_identificador(con_texto: Proyecto) -> None:
    """AJ-4: el identificador de la orden anterior queda invalidado; el nuevo se canjea, y
    cada canje, válido o no, queda en `llamada_mcp` sin el identificador (§4.1.10)."""
    raiz = con_texto.disposicion.raiz_proyectos
    sesion = tomar_bloqueo(con_texto, TipoEjecutor.SESION, AHORA)
    orden = _orden(emitir_siguiente_orden(con_texto, sesion.token, AHORA))
    viejo = orden.entrada["texto_libre"]["identificador"]
    worker = tomar_bloqueo(con_texto, TipoEjecutor.WORKER, despues(31))
    nuevo = _orden(emitir_siguiente_orden(con_texto, worker.token, despues(31)))
    identificador = nuevo.entrada["texto_libre"]["identificador"]
    assert identificador != viejo
    with pytest.raises(EntradaNoCanjeable):
        canjear(viejo, despues(32), raiz)
    assert canjear(identificador, despues(32), raiz) == TEXTO_LIBRE
    with pytest.raises(EntradaNoCanjeable):
        canjear(identificador, despues(33), raiz)
    filas = con_texto.conexion.execute(
        "SELECT agente, herramienta, argumentos, resultado FROM llamada_mcp ORDER BY id"
    ).fetchall()
    assert [(f["agente"], f["herramienta"]) for f in filas] == [
        ("extractor-hechos", "entrada.leer_entrada")
    ] * 3
    assert [json.loads(f["resultado"])["error"] for f in filas] == ["desconocido", None, "usado"]
    assert all(identificador not in f["argumentos"] for f in filas)
    assert all(viejo.split(".")[1] not in f["argumentos"] for f in filas)


def test_al_volver_a_sellar_al_bibliotecario_se_borra_lo_escrito(
    proyecto: Proyecto, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B-16 al emitir, y AJ-4 al volver a sellar: un Bibliotecario caído no duplica la biblia."""
    borrados: list[int] = []
    monkeypatch.setattr(biblia, "borrar_lo_escrito", lambda _c, capitulo: borrados.append(capitulo))
    forzar(proyecto, E.CAPITULOS, capitulos={1: (C.VERIFICADO, 0)})
    sesion = tomar_bloqueo(proyecto, TipoEjecutor.SESION, AHORA)
    orden = _orden(emitir_siguiente_orden(proyecto, sesion.token, AHORA))
    assert (orden.agente, orden.capitulo, borrados) == (Agente.BIBLIOTECARIO, 1, [1])
    tomar_bloqueo(proyecto, TipoEjecutor.WORKER, despues(31))
    assert borrados == [1, 1]


# ─── La entrada del Escritor y la decisión `error` (§4.1.4, AJ-5) ────────────


@pytest.fixture
def escritor_real(monkeypatch: pytest.MonkeyPatch) -> None:
    constructor = manejadores._entrada_del_escritor
    monkeypatch.setitem(manejadores.CONSTRUCTORES_DE_ENTRADA, Agente.ESCRITOR, constructor)


def test_la_orden_del_escritor_lleva_las_rutas_absolutas_del_prompt(
    proyecto: Proyecto, token: str, escritor_real: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    llamadas: list[tuple[Any, ...]] = []

    def preparar(conexion: Any, disposicion: Any, *argumentos: Any) -> ensamblado.PromptPreparado:
        llamadas.append(argumentos)
        numero, version, intento = argumentos[:3]
        partes = tuple(disposicion.prompt_parte(numero, version, intento, p) for p in (1, 2))
        return ensamblado.PromptPreparado(partes, partes[0], partes[1], 31_000)

    monkeypatch.setattr(ensamblado, "preparar_prompt", preparar)
    forzar(proyecto, E.CAPITULOS)
    orden = _orden(emitir_siguiente_orden(proyecto, token, AHORA))
    assert (orden.agente, orden.capitulo) == (Agente.ESCRITOR, 1)
    assert (orden.entrada["version"], orden.entrada["intento"]) == (1, 1)
    assert llamadas == [(1, 1, 1, None, MOMENTO)]
    rutas = [Path(r) for r in orden.entrada["rutas_prompt"]]
    assert [r.name for r in rutas] == [
        "v1-intento1.prompt.parte-1.md",
        "v1-intento1.prompt.parte-2.md",
    ]
    assert all(r.is_absolute() for r in rutas)


def test_un_prompt_que_no_cabe_es_la_decision_error_y_no_emite(
    proyecto: Proyecto, token: str, escritor_real: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_cabe(*_argumentos: Any) -> ensamblado.PromptPreparado:
        raise ensamblado.ErrorEnsamblado("no_cabe", {"tokens": 120_000})

    monkeypatch.setattr(ensamblado, "preparar_prompt", no_cabe)
    forzar(proyecto, E.CAPITULOS)
    antes = volcado(proyecto.conexion)
    decision = emitir_siguiente_orden(proyecto, token, AHORA)
    assert decision == ErrorConCausa("no_cabe", 1, {"tokens": 120_000})
    assert volcado(proyecto.conexion) == antes
    assert siguiente_de(decision).model_dump() == {
        "decision": "error",
        "causa": "no_cabe",
        "capitulo": 1,
        "detalle": {"tokens": 120_000},
    }


# ─── AJ-2 y AJ-3 persistidos ─────────────────────────────────────────────────


def test_la_revision_persistida_va_capitulo_a_capitulo_y_suma_una_pasada(
    proyecto: Proyecto, token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    for agente in (Agente.REVISOR, Agente.BIBLIOTECARIO):
        monkeypatch.setitem(
            manejadores.MANEJADORES, agente, lambda _c, _r: manejadores.Salida(Desenlace.aceptado())
        )
    forzar(proyecto, E.REVISION, capitulos={n: (C.APROBADO, 0) for n in range(1, 11)})
    with transaccion(proyecto.conexion) as conexion:
        conexion.execute("UPDATE proyecto SET pasadas = 1")
        conexion.execute(
            "INSERT INTO gate_resultado (pasada, gate, ok, detalle) VALUES "
            "(1, 'cobertura', 0, '{\"capitulos\": [7, 3]}'), (1, 'lean', 1, '{}'), "
            "(1, 'juez', 0, '{\"capitulos\": [3]}')"
        )
    pasos = []
    for _ in range(4):
        orden = _orden(emitir_siguiente_orden(proyecto, token, AHORA))
        pasos.append((orden.agente, orden.capitulo))
        registrar(proyecto, orden.id, {"ok": True}, token, AHORA)
    assert pasos == [
        (Agente.REVISOR, 3),
        (Agente.BIBLIOTECARIO, 3),
        (Agente.REVISOR, 7),
        (Agente.BIBLIOTECARIO, 7),
    ]
    assert leer_estado(proyecto, AHORA).estado is E.VERIFICACION_MANUSCRITO
    assert proyecto.conexion.execute("SELECT pasadas FROM proyecto").fetchone()[0] == 2


# ─── Qué texto lee cada agente del capítulo, y las notas del plan ────────────


def _versiones(proyecto: Proyecto, *filas: tuple[int, int, str]) -> None:
    with transaccion(proyecto.conexion) as conexion:
        conexion.executemany(
            "INSERT INTO capitulo_version (capitulo, version, intento, estado, ruta, creado) "
            "VALUES (1, ?, ?, ?, 'capitulos/cap-01/x.md', ?)",
            [(*f, MOMENTO) for f in filas],
        )


def _entrada(proyecto: Proyecto, agente: Agente, intento: int = 1) -> dict[str, Any]:
    lanzar = Lanzar(agente, intento, 1)
    solicitud = manejadores.SolicitudEntrada(proyecto, E.CAPITULOS, lanzar, AHORA)
    return manejadores.construir_entrada(solicitud)


def test_cada_agente_del_capitulo_recibe_la_version_y_el_intento_del_texto(
    proyecto: Proyecto, token: str
) -> None:
    """RF-60, B-15, B-16: tras un rechazo del juez, el Editor del intento 2 lee v1-intento2,
    no v1-intento1; el `intento` de la orden es el del paso, no el del texto."""
    _versiones(proyecto, (1, 1, "borrador"), (1, 2, "borrador"))
    forzar(proyecto, E.CAPITULOS, capitulos={1: (C.BORRADOR, 1)})
    orden = _orden(emitir_siguiente_orden(proyecto, token, AHORA))
    assert orden.agente is Agente.EDITOR_ESTILO and orden.intento == 1
    assert (orden.entrada["version"], orden.entrada["intento_texto"]) == (1, 2)
    assert orden.entrada["etapa"] == "borrador"
    for agente in (Agente.JUEZ_CAPITULO, Agente.BIBLIOTECARIO):
        entrada = _entrada(proyecto, agente)
        assert (entrada["version"], entrada["intento_texto"], entrada["etapa"]) == (1, 2, "editado")
    # El Revisor corrige la vigente aprobada, no un intento posterior sin aprobar.
    with transaccion(proyecto.conexion) as conexion:
        conexion.execute("UPDATE capitulo_version SET estado = 'aprobado' WHERE intento = 1")
        conexion.execute("UPDATE capitulo SET version_vigente = 1 WHERE numero = 1")
    assert _entrada(proyecto, Agente.REVISOR)["intento_texto"] == 1


def test_tras_reintentar_el_escritor_no_pisa_los_intentos_anteriores(proyecto: Proyecto) -> None:
    """RF-06, RF-64b: con el contador a cero tras «reintentar», v1-intento1 ya existe; el
    Escritor va a la versión siguiente, y sus intentos siguen en ella."""
    version = manejadores._version_del_escritor
    assert version(proyecto.conexion, 1, 1) == 1
    _versiones(proyecto, (1, 1, "borrador"))
    assert version(proyecto.conexion, 1, 2) == 1
    _versiones(proyecto, (1, 2, "borrador"), (1, 3, "borrador"))
    assert version(proyecto.conexion, 1, 1) == 2
    _versiones(proyecto, (2, 1, "borrador"))
    assert version(proyecto.conexion, 1, 2) == 2


def test_las_notas_de_cambios_del_plan_llegan_al_planificador_y_no_al_estado(
    proyecto: Proyecto, token: str
) -> None:
    """RF-36: las notas de «cambios» en `aprobacion_plan` van en `entrada.notas_plan`; el
    estado (RF-02) enseña la orden sin ellas."""
    forzar(proyecto, E.PLANIFICACION)
    with transaccion(proyecto.conexion) as conexion:
        conexion.execute(
            "INSERT INTO decision_humana (momento, tipo, decision, notas) VALUES "
            "(?, 'aprobacion_plan', 'cambios', 'Que el faro tenga más peso.')",
            (MOMENTO,),
        )
    orden = _orden(emitir_siguiente_orden(proyecto, token, AHORA))
    assert orden.agente is Agente.PLANIFICADOR and "notas_plan" in orden.entrada["necesita"]
    assert orden.entrada["notas_plan"] == "Que el faro tenga más peso."
    vigente = leer_estado(proyecto, AHORA).orden_vigente
    assert vigente is not None and "notas_plan" not in vigente.entrada


# ─── M-6: la revisión tras «cambios» en aprobacion_final ─────────────────────


def _revisar_todo(proyecto: Proyecto, token: str, monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    for agente in (Agente.REVISOR, Agente.BIBLIOTECARIO):
        monkeypatch.setitem(
            manejadores.MANEJADORES, agente, lambda _c, _r: manejadores.Salida(Desenlace.aceptado())
        )
    pasos = []
    while leer_estado(proyecto, AHORA).estado is E.REVISION:
        orden = _orden(emitir_siguiente_orden(proyecto, token, AHORA))
        pasos.append((orden.agente, orden.capitulo, orden.entrada.get("notas")))
        registrar(proyecto, orden.id, {"ok": True}, token, AHORA)
    return pasos


@pytest.mark.parametrize(("capitulos", "esperados"), [([7, 2], [2, 7]), (None, list(range(1, 11)))])
def test_cambios_en_la_aprobacion_final_revisan_los_capitulos_que_dice_o_todos(
    proyecto: Proyecto,
    token: str,
    monkeypatch: pytest.MonkeyPatch,
    capitulos: list[int] | None,
    esperados: list[int],
) -> None:
    """M-6: nunca un Revisor sin capítulo. Con `capitulos`, esos; sin ellos, los diez; y las
    notas viajan en la entrada del Revisor, no en /estado."""
    forzar(
        proyecto,
        E.APROBACION_FINAL,
        parada_final=True,
        capitulos={n: (C.APROBADO, 0) for n in range(1, 11)},
    )
    with transaccion(proyecto.conexion) as conexion:
        conexion.execute("UPDATE proyecto SET pasadas = 1")
        conexion.executemany(
            "INSERT INTO gate_resultado (pasada, gate, ok, detalle) VALUES (1, ?, 1, '{}')",
            [("cobertura",), ("lean",), ("juez",)],
        )
    decidir_parada(proyecto, "aprobacion_final", "cambios", AHORA, "Más faro.", capitulos)
    pasos = _revisar_todo(proyecto, token, monkeypatch)
    revisores = [(c, n) for a, c, n in pasos if a is Agente.REVISOR]
    assert revisores == [(c, "Más faro.") for c in esperados]
    assert len(pasos) == 2 * len(esperados)
    assert leer_estado(proyecto, AHORA).estado is E.VERIFICACION_MANUSCRITO


def test_capitulos_solo_con_cambios_en_la_aprobacion_final(proyecto: Proyecto) -> None:
    forzar(proyecto, E.APROBACION_FINAL, parada_final=True)
    with pytest.raises(EntradaInvalida):
        decidir_parada(proyecto, "aprobacion_final", "aprobado", AHORA, None, [3])


def test_el_revisor_recibe_el_manuscrito_y_el_informe_de_los_gates(proyecto: Proyecto) -> None:
    """RF-113, AJ-2: dónde está cada capítulo vigente y qué dijeron los tres gates de la
    pasada en curso, con las justificaciones del juez. Sin notas: los gates fallaron."""
    with transaccion(proyecto.conexion) as conexion:
        conexion.execute("UPDATE proyecto SET pasadas = 1")
        conexion.execute(
            "INSERT INTO capitulo_version (capitulo, version, intento, estado, ruta, creado) "
            "VALUES (1, 1, 2, 'aprobado', 'x.md', ?)",
            (MOMENTO,),
        )
        conexion.execute("UPDATE capitulo SET version_vigente = 1 WHERE numero = 1")
        conexion.executemany(
            "INSERT INTO gate_resultado (pasada, gate, ok, detalle) VALUES (1, ?, ?, ?)",
            [
                ("cobertura", 0, '{"capitulos": [1]}'),
                ("lean", 1, '{"capitulos": []}'),
                ("juez", 1, '{"capitulos": [], "evaluacion": "juez-orden-9"}'),
            ],
        )
        conexion.execute(
            "INSERT INTO informe_juez (evaluacion, version_novela, revisor, ciclo, criterio, "
            "puntuacion, justificacion, momento) VALUES ('juez-orden-9', 1, 'juez', 0, 'tono', "
            "4, 'El tono aguanta.', ?)",
            (MOMENTO,),
        )
    entrada = _entrada(proyecto, Agente.REVISOR)
    assert entrada["manuscrito"] == [
        {"capitulo": 1, "version": 1, "intento": 2, "etapa": "editado"}
    ]
    informe = entrada["informe_gates"]
    assert informe["pasada"] == 1
    assert informe["gates"]["cobertura"] == {"ok": False, "detalle": {"capitulos": [1]}}
    assert informe["juez"] == [
        {"criterio": "tono", "puntuacion": 4, "justificacion": "El tono aguanta."}
    ]
    assert "notas" not in entrada
