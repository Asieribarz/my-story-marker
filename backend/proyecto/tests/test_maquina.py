"""V-33 y V-14 sobre la máquina pura: instantáneas generadas y recorridos aleatorios.

La persistencia se prueba aparte (`test_persistencia.py`); aquí se prueba la función que
decide, que es la que modela la especificación TLA+ (V-25).
"""

from dataclasses import replace

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from backend.proyecto.errores import DecisionHumanaInvalida, TransicionInvalida
from backend.proyecto.maquina import (
    AGENTES_DE_CAPITULO,
    AGENTES_DEL_ESTADO,
    TOPE,
    AccionHumana,
    Avance,
    CapituloInstantanea,
    Desenlace,
    Detenida,
    Efecto,
    Entrada,
    EsperarHumano,
    Instantanea,
    Lanzar,
    MotivoEspera,
    OrdenVigente,
    Paso,
    Publicada,
    ResultadoGates,
    TipoDesenlace,
    ViaRegistro,
    aplicar_accion_humana,
    aplicar_desenlace,
    incoherencias,
    resolver,
)
from backend.proyecto.tests.generadores import (
    desenlaces,
    desenlaces_del_recorrido,
    en_el_bucle,
    fallos,
    instantaneas,
    simular_humano,
    simular_manejador,
)
from backend.proyecto.transiciones import ORIGENES_DE_DETENIDA, Causa, arista
from backend.shared.tipos import Agente as A
from backend.shared.tipos import EstadoCapitulo as C
from backend.shared.tipos import EstadoProyecto as E

# Fases en las que todos los capítulos han pasado el bucle entero (invariante 1 de §3.4).
_TRAS_EL_BUCLE = (E.VERIFICACION_MANUSCRITO, E.REVISION, E.APROBACION_FINAL, E.PUBLICACION)


def _recorrer(pasos: tuple[Paso, ...], desde: E, humana_primero: bool = False) -> E:
    """Cada paso sale de donde acabó el anterior, está en la tabla y es del tipo que toca."""
    estado = desde
    for i, paso in enumerate(pasos):
        assert paso.origen is estado
        assert arista(paso.origen, paso.destino, paso.causa).humana == (humana_primero and i == 0)
        estado = paso.destino
    return estado


def _con_orden(
    inst: Instantanea, lanzar: Lanzar, ident: int = 1
) -> tuple[Instantanea, OrdenVigente]:
    orden = OrdenVigente(ident, inst.estado, lanzar.agente, lanzar.intento, lanzar.capitulo)
    return replace(inst, orden_vigente=orden), orden


def _lanzar(inst: Instantanea) -> tuple[Instantanea, Lanzar]:
    resolucion = resolver(inst)
    assert isinstance(resolucion.decision, Lanzar), resolucion.decision
    return resolucion.instantanea, resolucion.decision


def _aplicar(inst: Instantanea, desenlace: Desenlace) -> Instantanea:
    """Lanza la orden que toque y le aplica el desenlace."""
    base, lanzar = _lanzar(inst)
    con, orden = _con_orden(base, lanzar)
    return aplicar_desenlace(con, orden, desenlace).instantanea


# ─── V-33: propiedades sobre instantáneas generadas ─────────────────────────


@settings(max_examples=400)
@given(instantaneas())
def test_la_decision_respeta_la_tabla_y_los_topes(inst: Instantanea) -> None:
    assert incoherencias(inst) == ()
    resolucion = resolver(inst)
    assert resolucion == resolver(inst)
    assert _recorrer(resolucion.pasos, inst.estado) is resolucion.instantanea.estado
    assert incoherencias(resolucion.instantanea) == ()
    decision = resolucion.decision
    if isinstance(decision, Lanzar):
        assert 1 <= decision.intento <= TOPE
        assert decision.agente in AGENTES_DEL_ESTADO[resolucion.instantanea.estado]
        assert (decision.capitulo is not None) == (decision.agente in AGENTES_DE_CAPITULO)
        assert (Entrada.INFORME_ANTERIOR in decision.entrada) == (decision.intento > 1)
    if inst.orden_vigente is not None:
        assert resolucion.pasos == ()
        assert isinstance(decision, Lanzar)
        assert (decision.agente, decision.intento, decision.capitulo) == (
            inst.orden_vigente.agente,
            inst.orden_vigente.intento,
            inst.orden_vigente.capitulo,
        )


@settings(max_examples=600)
@given(instantaneas(con_vigente=False), desenlaces, st.integers(1, 1000))
def test_el_desenlace_respeta_la_tabla_y_los_topes(
    inst: Instantanea, desenlace: Desenlace, ident: int
) -> None:
    resolucion = resolver(inst)
    assume(isinstance(resolucion.decision, Lanzar))
    assert isinstance(resolucion.decision, Lanzar)
    con, orden = _con_orden(resolucion.instantanea, resolucion.decision, ident)
    sin_gates = con.avance.gates is ResultadoGates.SIN_EVALUAR
    if orden.agente is A.JUEZ_MANUSCRITO and desenlace.tipo is TipoDesenlace.ACEPTADO and sin_gates:
        with pytest.raises(ValueError, match="gates"):
            aplicar_desenlace(con, orden, desenlace)
        return
    efecto = aplicar_desenlace(con, orden, desenlace)
    despues = efecto.instantanea
    assert _recorrer(efecto.pasos, con.estado) is despues.estado
    assert despues.orden_vigente is None
    assert incoherencias(despues) == ()
    siguiente = resolver(despues).decision
    if isinstance(siguiente, Lanzar):
        assert 1 <= siguiente.intento <= TOPE


@given(en_el_bucle(), fallos)
def test_un_fallo_de_contenido_gasta_intento_de_capitulo_y_uno_de_forma_de_paso(
    inst: Instantanea, desenlace: Desenlace
) -> None:
    """Q5, sobre cualquier orden del bucle de capítulo."""
    resolucion = resolver(inst)
    decision = resolucion.decision
    assert isinstance(decision, Lanzar) and decision.capitulo is not None
    con, orden = _con_orden(resolucion.instantanea, decision)
    antes = con.capitulo(decision.capitulo)
    despues = aplicar_desenlace(con, orden, desenlace).instantanea
    ahora = despues.capitulo(decision.capitulo)
    contenido = decision.agente is A.ESCRITOR or (
        desenlace.tipo is TipoDesenlace.FALLO_CONTENIDO and decision.agente is not A.BIBLIOTECARIO
    )
    if contenido:
        assert ahora.intentos == antes.intentos + 1
        assert ahora.estado is (C.REVISION_HUMANA if ahora.intentos == TOPE else C.PENDIENTE)
    elif con.intentos_paso + 1 < TOPE:
        assert ahora == antes
        assert despues.intentos_paso == con.intentos_paso + 1
    else:
        assert (ahora.estado, ahora.intentos) == (C.REVISION_HUMANA, antes.intentos)


@settings(max_examples=150, deadline=None)
@given(st.data(), st.booleans(), st.booleans())
def test_un_recorrido_aleatorio_nunca_se_sale_de_la_tabla_ni_de_los_topes(
    data: st.DataObject, parada_plan: bool, parada_final: bool
) -> None:
    inst = Instantanea(parada_plan=parada_plan, parada_final=parada_final)
    for ident in range(1, 400):
        resolucion = resolver(inst)
        _recorrer(resolucion.pasos, inst.estado)
        inst = resolucion.instantanea
        assert incoherencias(inst) == ()
        if inst.estado in _TRAS_EL_BUCLE:
            assert all(c.terminado for c in inst.capitulos)
        decision = resolucion.decision
        if isinstance(decision, Lanzar):
            assert 1 <= decision.intento <= TOPE
            orden = OrdenVigente(
                ident, inst.estado, decision.agente, decision.intento, decision.capitulo
            )
            desenlace = data.draw(desenlaces_del_recorrido)
            escrita = simular_manejador(inst, orden, desenlace, data)
            efecto = aplicar_desenlace(replace(escrita, orden_vigente=orden), orden, desenlace)
            _recorrer(efecto.pasos, inst.estado)
        else:
            respuesta = simular_humano(inst, decision, data)
            if respuesta is None:
                break
            efecto = respuesta
            _recorrer(efecto.pasos, inst.estado, humana_primero=bool(efecto.pasos))
        inst = efecto.instantanea


def _camino_feliz(inst: Instantanea) -> tuple[list[A], Instantanea]:
    """Todo se acepta, los gates salen verdes y el humano aprueba lo que le pongan delante."""
    agentes: list[A] = []
    for ident in range(1, 200):
        resolucion = resolver(inst)
        inst = resolucion.instantanea
        decision = resolucion.decision
        match decision:
            case Lanzar():
                agentes.append(decision.agente)
                orden = OrdenVigente(
                    ident, inst.estado, decision.agente, decision.intento, decision.capitulo
                )
                a = inst.avance
                escrita = replace(
                    inst,
                    avance=replace(
                        a,
                        brief_normalizado=a.brief_normalizado or inst.estado is E.INTAKE,
                        contexto_validado=a.contexto_validado or inst.estado is E.CONTEXTO,
                        plan=a.plan or decision.agente is A.PLANIFICADOR,
                        personajes=a.personajes or decision.agente is A.PLANIFICADOR,
                        mundo=a.mundo or decision.agente is A.PLANIFICADOR,
                        guia_estilo=a.guia_estilo or decision.agente is A.PLANIFICADOR,
                        fichas=10 if decision.agente is A.ESCALETISTA else a.fichas,
                        gates=ResultadoGates.VERDES,
                    ),
                    orden_vigente=orden,
                )
                inst = aplicar_desenlace(escrita, orden, Desenlace.aceptado()).instantanea
            case EsperarHumano(MotivoEspera.BRIEF):
                inst = replace(inst, avance=replace(inst.avance, brief=True))
            case EsperarHumano(MotivoEspera.APROBACION_PLAN):
                inst = aplicar_accion_humana(inst, AccionHumana.APROBAR_PLAN).instantanea
            case EsperarHumano(MotivoEspera.APROBACION_FINAL):
                inst = aplicar_accion_humana(inst, AccionHumana.APROBAR_FINAL).instantanea
            case Publicada():
                return agentes, inst
            case _:
                raise AssertionError(f"el camino feliz no espera {decision}")
    raise AssertionError("el camino feliz no llega a publicada")


@pytest.mark.parametrize("paradas", [False, True])
def test_el_camino_feliz_llega_a_publicada(paradas: bool) -> None:
    agentes, final = _camino_feliz(Instantanea(parada_plan=paradas, parada_final=paradas))
    assert final.estado is E.PUBLICADA
    assert agentes[:3] == [A.AGENTE_CONTEXTO, A.AGENTE_CONTEXTO, A.PLANIFICADOR]
    del_bucle = [A.ESCRITOR, A.EDITOR_ESTILO, A.JUEZ_CAPITULO, A.BIBLIOTECARIO]
    assert agentes[3:] == [A.ESCALETISTA, *del_bucle * 10, A.JUEZ_MANUSCRITO, A.EXPORTADOR]
    assert all(c.terminado for c in final.capitulos)


# ─── V-14: las paradas no se salen sin la acción humana ─────────────────────

_PARADAS = [E.APROBACION_PLAN, E.APROBACION_FINAL, E.PUBLICADA, E.DETENIDA, E.CAMBIO_SOLICITADO]


@settings(max_examples=300)
@given(instantaneas(con_vigente=False), st.sampled_from(_PARADAS), st.data())
def test_ninguna_llamada_automatica_sale_de_una_parada(
    inst: Instantanea, parada: E, data: st.DataObject
) -> None:
    desde = (
        data.draw(st.sampled_from(sorted(ORIGENES_DE_DETENIDA))) if parada is E.DETENIDA else None
    )
    avance = replace(inst.avance, cambio_propuesto=True)
    en_parada = replace(inst, estado=parada, detenida_desde=desde, avance=avance)
    resolucion = resolver(en_parada)
    assert resolucion.pasos == ()
    assert resolucion.instantanea == en_parada
    assert isinstance(resolucion.decision, EsperarHumano | Publicada | Detenida)
    # Ni con una orden que nadie ha emitido: ningún agente trabaja en una parada.
    agente = data.draw(st.sampled_from(list(A)))
    orden = OrdenVigente(1, parada, agente, 1, 1 if agente in AGENTES_DE_CAPITULO else None)
    if parada is not E.CAMBIO_SOLICITADO or agente is not A.INTERPRETE_CAMBIOS:
        with pytest.raises(ValueError):
            aplicar_desenlace(replace(en_parada, orden_vigente=orden), orden, Desenlace.forma())


def test_cada_parada_sale_con_su_accion_humana() -> None:
    plan = aplicar_accion_humana(Instantanea(estado=E.APROBACION_PLAN), AccionHumana.APROBAR_PLAN)
    assert plan.pasos[0] == Paso(E.APROBACION_PLAN, E.ESCALETA, Causa.PLAN_APROBADO)
    final = aplicar_accion_humana(Instantanea(estado=E.APROBACION_FINAL), AccionHumana.NOTAS_FINAL)
    assert final.instantanea.estado is E.REVISION
    pedida = aplicar_accion_humana(Instantanea(estado=E.PUBLICADA), AccionHumana.PEDIR_CAMBIO)
    assert pedida.instantanea.estado is E.CAMBIO_SOLICITADO


def test_una_accion_humana_fuera_de_su_parada_es_una_transicion_invalida() -> None:
    with pytest.raises(TransicionInvalida):
        aplicar_accion_humana(Instantanea(), AccionHumana.APROBAR_PLAN)
    with pytest.raises(TransicionInvalida):
        aplicar_accion_humana(Instantanea(estado=E.CAPITULOS), AccionHumana.REINTENTAR)


def test_no_se_confirma_un_cambio_que_aun_no_esta_propuesto() -> None:
    inst = Instantanea(estado=E.CAMBIO_SOLICITADO)
    with pytest.raises(DecisionHumanaInvalida):
        aplicar_accion_humana(inst, AccionHumana.CONFIRMAR_CAMBIO)
    assert resolver(inst).decision == Lanzar(
        A.INTERPRETE_CAMBIOS, 1, None, (Entrada.PETICION,), ViaRegistro.SKILL
    )


# ─── Casos concretos de Q5, Q6, RF-64 y RF-64a ──────────────────────────────


def _en_capitulos(**cambios: tuple[C, int, bool]) -> Instantanea:
    capitulos = tuple(
        CapituloInstantanea(n, *cambios.get(f"c{n}", (C.APROBADO, 0, True))) for n in range(1, 11)
    )
    return Instantanea(estado=E.CAPITULOS, capitulos=capitulos)


def test_tres_fallos_de_contenido_mandan_el_capitulo_a_revision_humana_y_el_bucle_sigue() -> None:
    inst = _en_capitulos(c3=(C.PENDIENTE, 0, False), c4=(C.PENDIENTE, 0, False))
    for intento in (1, 2, 3):
        base, lanzar = _lanzar(inst)
        assert (lanzar.agente, lanzar.capitulo, lanzar.intento) == (A.ESCRITOR, 3, intento)
        inst = _aplicar(inst, Desenlace.contenido())
    assert inst.capitulo(3) == CapituloInstantanea(3, C.REVISION_HUMANA, 3)
    assert inst.estado is E.CAPITULOS
    _, lanzar = _lanzar(inst)
    assert (lanzar.agente, lanzar.capitulo, lanzar.intento) == (A.ESCRITOR, 4, 1)


def test_el_editor_repite_sobre_el_mismo_borrador_con_su_propio_contador() -> None:
    inst = _en_capitulos(c1=(C.BORRADOR, 1, False))
    for intento in (1, 2):
        _, lanzar = _lanzar(inst)
        assert (lanzar.agente, lanzar.intento) == (A.EDITOR_ESTILO, intento)
        inst = _aplicar(inst, Desenlace.forma())
        assert inst.capitulo(1) == CapituloInstantanea(1, C.BORRADOR, 1)
    inst = _aplicar(inst, Desenlace.forma())
    assert inst.capitulo(1) == CapituloInstantanea(1, C.REVISION_HUMANA, 1)
    assert inst.intentos_paso == 0
    # Era el único capítulo en curso: el bucle acaba y el proyecto se detiene (RF-64).
    assert (inst.estado, inst.detenida_desde) == (E.DETENIDA, E.CAPITULOS)


def test_el_capitulo_termina_con_el_bibliotecario_y_el_siguiente_empieza() -> None:
    inst = _en_capitulos(c2=(C.PENDIENTE, 0, False), c3=(C.PENDIENTE, 0, False))
    recorrido = []
    for _ in range(4):
        _, lanzar = _lanzar(inst)
        recorrido.append((lanzar.agente, lanzar.capitulo))
        inst = _aplicar(inst, Desenlace.aceptado())
    assert recorrido == [
        (A.ESCRITOR, 2),
        (A.EDITOR_ESTILO, 2),
        (A.JUEZ_CAPITULO, 2),
        (A.BIBLIOTECARIO, 2),
    ]
    assert inst.capitulo(2) == CapituloInstantanea(2, C.APROBADO, 0, terminado=True)
    assert _lanzar(inst)[1].capitulo == 3


def test_el_juez_que_rechaza_devuelve_el_capitulo_al_escritor_con_el_informe() -> None:
    inst = _en_capitulos(c5=(C.VERIFICADO, 0, False))
    inst = _aplicar(inst, Desenlace.contenido())
    assert inst.capitulo(5) == CapituloInstantanea(5, C.PENDIENTE, 1)
    _, lanzar = _lanzar(inst)
    assert (lanzar.agente, lanzar.intento, lanzar.registro) == (
        A.ESCRITOR,
        2,
        ViaRegistro.HOOK_VALIDACION,
    )
    assert Entrada.INFORME_ANTERIOR in lanzar.entrada


def test_el_veto_agotado_detiene_sin_esperar_al_final_del_bucle() -> None:
    inst = _en_capitulos(c2=(C.BORRADOR, 2, False), c3=(C.PENDIENTE, 0, False))
    inst = _aplicar(inst, Desenlace.contenido(guardarrail=True))
    assert (inst.estado, inst.detenida_desde) == (E.DETENIDA, E.CAPITULOS)
    assert inst.capitulo(3).estado is C.PENDIENTE
    regenerando = replace(
        _en_capitulos(c2=(C.BORRADOR, 2, False), c3=(C.PENDIENTE, 0, False)),
        estado=E.REGENERACION,
    )
    assert _aplicar(regenerando, Desenlace.contenido(guardarrail=True)).estado is E.PUBLICADA


def test_al_acabar_el_bucle_con_un_capitulo_en_revision_humana() -> None:
    inst = _en_capitulos(c4=(C.REVISION_HUMANA, 3, False), c10=(C.APROBADO, 0, False))
    detenida = _aplicar(inst, Desenlace.aceptado())
    assert (detenida.estado, detenida.detenida_desde) == (E.DETENIDA, E.CAPITULOS)
    publicada = _aplicar(replace(inst, estado=E.REGENERACION), Desenlace.aceptado())
    assert publicada.estado is E.PUBLICADA


def test_tres_ciclos_de_revision_y_despues_se_detiene_o_vuelve_a_publicada() -> None:
    fallos = replace(Avance(), gates=ResultadoGates.FALLOS)
    inst = replace(_en_capitulos(), estado=E.VERIFICACION_MANUSCRITO, avance=fallos)
    for ciclo in (1, 2, 3):
        inst = _aplicar(inst, Desenlace.aceptado())
        assert (inst.estado, inst.ciclos_revision) == (E.REVISION, ciclo)
        inst = _aplicar(inst, Desenlace.aceptado())
        assert inst.estado is E.VERIFICACION_MANUSCRITO
    assert _aplicar(inst, Desenlace.aceptado()).estado is E.DETENIDA
    regenerando = replace(inst, avance=replace(fallos, es_regeneracion=True))
    assert _aplicar(regenerando, Desenlace.aceptado()).estado is E.PUBLICADA


@pytest.mark.parametrize(
    ("estado", "regeneracion", "destino"),
    [
        (E.INTAKE, False, E.DETENIDA),
        (E.CONTEXTO, False, E.DETENIDA),
        (E.PUBLICACION, False, E.DETENIDA),
        (E.PUBLICACION, True, E.PUBLICADA),
        (E.REVISION, True, E.PUBLICADA),
        (E.CAMBIO_SOLICITADO, True, E.PUBLICADA),
    ],
)
def test_el_tope_de_una_orden_que_no_es_de_capitulo(
    estado: E, regeneracion: bool, destino: E
) -> None:
    avance = Avance(brief=True, es_regeneracion=regeneracion)
    inst = replace(_en_capitulos(), estado=estado, avance=avance)
    for intento in (1, 2):
        _, lanzar = _lanzar(inst)
        assert lanzar.intento == intento
        inst = _aplicar(inst, Desenlace.forma())
        assert (inst.estado, inst.intentos_paso) == (estado, intento)
    inst = _aplicar(inst, Desenlace.contenido())
    assert (inst.estado, inst.intentos_paso) == (destino, 0)
    assert inst.detenida_desde == (estado if destino is E.DETENIDA else None)


def test_cada_avance_pone_a_cero_el_contador_de_paso() -> None:
    inst = Instantanea(estado=E.PLANIFICACION)
    inst = _aplicar(_aplicar(inst, Desenlace.forma()), Desenlace.forma())
    assert inst.intentos_paso == 2
    base, lanzar = _lanzar(inst)
    con, orden = _con_orden(base, lanzar)
    inst = aplicar_desenlace(con, orden, Desenlace.aceptado()).instantanea
    assert inst.intentos_paso == 0
    _, lanzar = _lanzar(inst)
    assert (lanzar.agente, lanzar.intento) == (A.PLANIFICADOR, 1)


def test_los_cambios_del_plan_vuelven_al_planificador_con_las_notas() -> None:
    completo = Avance(plan=True, personajes=True, mundo=True, guia_estilo=True)
    inst = Instantanea(estado=E.APROBACION_PLAN, avance=completo, parada_plan=True)
    efecto = aplicar_accion_humana(inst, AccionHumana.CAMBIOS_PLAN)
    assert efecto.instantanea.estado is E.PLANIFICACION
    _, lanzar = _lanzar(efecto.instantanea)
    assert lanzar.agente is A.PLANIFICADOR
    assert Entrada.NOTAS_PLAN in lanzar.entrada
    # Con el plan revisado, la parada vuelve a pedir la aprobación.
    revisado = _aplicar(efecto.instantanea, Desenlace.aceptado())
    assert revisado.estado is E.APROBACION_PLAN


def test_reintentar_reabre_los_capitulos_en_revision_humana() -> None:
    """RF-64b: contador a cero, ciclos de revisión a cero y vuelta a `capitulos`."""
    inst = replace(
        _en_capitulos(c3=(C.REVISION_HUMANA, 3, False), c7=(C.REVISION_HUMANA, 1, False)),
        estado=E.DETENIDA,
        detenida_desde=E.CAPITULOS,
        ciclos_revision=2,
    )
    efecto = aplicar_accion_humana(inst, AccionHumana.REINTENTAR)
    despues = efecto.instantanea
    assert efecto.pasos == (Paso(E.DETENIDA, E.CAPITULOS, Causa.REINTENTAR),)
    assert despues.capitulo(3) == CapituloInstantanea(3)
    assert despues.capitulo(7) == CapituloInstantanea(7)
    assert despues.capitulo(1) == inst.capitulo(1)
    assert (despues.ciclos_revision, despues.detenida_desde) == (0, None)


def test_reintentar_desde_los_gates_vuelve_al_bucle_y_de_ahi_a_verificar() -> None:
    inst = replace(_en_capitulos(), estado=E.DETENIDA, detenida_desde=E.VERIFICACION_MANUSCRITO)
    efecto = aplicar_accion_humana(inst, AccionHumana.REINTENTAR)
    assert [p.destino for p in efecto.pasos] == [E.CAPITULOS, E.VERIFICACION_MANUSCRITO]


def test_reintentar_desde_otra_fase_vuelve_a_ella_con_el_contador_a_cero() -> None:
    inst = Instantanea(estado=E.DETENIDA, detenida_desde=E.CONTEXTO)
    despues = aplicar_accion_humana(inst, AccionHumana.REINTENTAR).instantanea
    assert (despues.estado, despues.intentos_paso) == (E.CONTEXTO, 0)


def test_un_desenlace_de_otra_orden_es_un_error() -> None:
    base, lanzar = _lanzar(Instantanea(avance=Avance(brief=True)))
    con, orden = _con_orden(base, lanzar)
    with pytest.raises(ValueError, match="vigente"):
        aplicar_desenlace(con, replace(orden, id=orden.id + 1), Desenlace.aceptado())


def test_la_confirmacion_de_un_cambio_regenera_solo_los_capitulos_reabiertos() -> None:
    inst = replace(
        _en_capitulos(c6=(C.PENDIENTE, 0, False)),
        estado=E.CAMBIO_SOLICITADO,
        avance=Avance(cambio_propuesto=True, es_regeneracion=True),
        ciclos_revision=3,
    )
    efecto: Efecto = aplicar_accion_humana(inst, AccionHumana.CONFIRMAR_CAMBIO)
    assert efecto.instantanea.estado is E.REGENERACION
    assert efecto.instantanea.ciclos_revision == 0
    _, lanzar = _lanzar(efecto.instantanea)
    assert (lanzar.agente, lanzar.capitulo) == (A.ESCRITOR, 6)
