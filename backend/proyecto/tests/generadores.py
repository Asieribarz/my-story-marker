"""Estrategias de Hypothesis para la máquina, y lo que harían los manejadores y el humano.

`instantaneas()` genera instantáneas que cumplen `maquina.incoherencias`: son las que puede
dejar la persistencia, porque `aplicar_*` conservan esas invariantes (lo prueba V-33).
`simular_manejador` y `simular_humano` modelan lo que escriben en sus tablas las rebanadas
que aún no existen, para que el recorrido aleatorio llegue a todas las fases del grafo.
"""

from dataclasses import replace

from hypothesis import strategies as st

from backend.proyecto.maquina import (
    AccionHumana,
    Avance,
    CapituloInstantanea,
    Desenlace,
    Detenida,
    Efecto,
    EsperarHumano,
    Final,
    Instantanea,
    Lanzar,
    MotivoEspera,
    OrdenVigente,
    Publicada,
    ResultadoGates,
    TipoDesenlace,
    aplicar_accion_humana,
    resolver,
)
from backend.proyecto.transiciones import ORIGENES_DE_DETENIDA
from backend.shared.tipos import Agente as A
from backend.shared.tipos import EstadoCapitulo as C
from backend.shared.tipos import EstadoProyecto as E


@st.composite
def capitulo(draw: st.DrawFn, numero: int) -> CapituloInstantanea:
    estado = draw(st.sampled_from(list(C)))
    intentos = draw(st.integers(0, 3 if estado is C.REVISION_HUMANA else 2))
    terminado = estado is C.APROBADO and draw(st.booleans())
    return CapituloInstantanea(numero, estado, intentos, terminado)


avances = st.builds(
    Avance,
    brief=st.booleans(),
    texto_libre=st.booleans(),
    extraccion_hecha=st.booleans(),
    hechos_pendientes=st.booleans(),
    brief_normalizado=st.booleans(),
    contexto_validado=st.booleans(),
    plan=st.booleans(),
    notas_plan_pendientes=st.booleans(),
    personajes=st.booleans(),
    mundo=st.booleans(),
    guia_estilo=st.booleans(),
    fichas=st.integers(0, 10),
    gates=st.sampled_from(list(ResultadoGates)),
    cambio_propuesto=st.booleans(),
    es_regeneracion=st.booleans(),
)


@st.composite
def instantaneas(draw: st.DrawFn, con_vigente: bool = True) -> Instantanea:
    estado = draw(st.sampled_from(list(E)))
    desde = draw(st.sampled_from(sorted(ORIGENES_DE_DETENIDA))) if estado is E.DETENIDA else None
    inst = Instantanea(
        estado=estado,
        capitulos=tuple(draw(capitulo(n)) for n in range(1, 11)),
        avance=draw(avances),
        detenida_desde=desde,
        parada_plan=draw(st.booleans()),
        parada_final=draw(st.booleans()),
        ciclos_revision=draw(st.integers(0, 3)),
        intentos_paso=draw(st.integers(0, 2)),
    )
    if con_vigente and draw(st.booleans()):
        resolucion = resolver(inst)
        decision = resolucion.decision
        if isinstance(decision, Lanzar):
            orden = OrdenVigente(
                draw(st.integers(1, 10_000)),
                resolucion.instantanea.estado,
                decision.agente,
                decision.intento,
                decision.capitulo,
            )
            inst = replace(resolucion.instantanea, orden_vigente=orden)
    return inst


@st.composite
def en_el_bucle(draw: st.DrawFn) -> Instantanea:
    """Una instantánea de `capitulos` o `regeneracion` con al menos un capítulo en curso."""
    inst = draw(instantaneas(con_vigente=False))
    numero = draw(st.integers(1, 10))
    estado = draw(st.sampled_from([C.PENDIENTE, C.BORRADOR, C.EDITADO, C.VERIFICADO, C.APROBADO]))
    en_curso = CapituloInstantanea(numero, estado, draw(st.integers(0, 2)))
    return replace(
        inst,
        estado=draw(st.sampled_from([E.CAPITULOS, E.REGENERACION])),
        detenida_desde=None,
        capitulos=tuple(en_curso if c.numero == numero else c for c in inst.capitulos),
    )


desenlaces = st.builds(
    Desenlace,
    tipo=st.sampled_from(list(TipoDesenlace)),
    guardarrail=st.booleans(),
)

fallos = st.builds(
    Desenlace,
    tipo=st.sampled_from([TipoDesenlace.FALLO_CONTENIDO, TipoDesenlace.FALLO_FORMA]),
    guardarrail=st.booleans(),
)

# El recorrido aleatorio acepta más de lo que falla, para llegar lejos en el grafo.
desenlaces_del_recorrido = st.one_of(
    st.just(Desenlace.aceptado()),
    st.just(Desenlace.aceptado()),
    st.just(Desenlace.aceptado()),
    desenlaces,
)


def simular_manejador(
    inst: Instantanea, orden: OrdenVigente, desenlace: Desenlace, data: st.DataObject
) -> Instantanea:
    """Lo que dejaría escrito en sus tablas el manejador del agente, antes del desenlace."""
    if desenlace.tipo is not TipoDesenlace.ACEPTADO:
        return inst
    a = inst.avance
    match orden.agente:
        case A.EXTRACTOR_HECHOS:
            a = replace(a, hechos_pendientes=data.draw(st.booleans()))
        case A.AGENTE_CONTEXTO if orden.estado is E.INTAKE:
            a = replace(a, brief_normalizado=True)
        case A.AGENTE_CONTEXTO:
            a = replace(a, contexto_validado=True)
        case A.PLANIFICADOR:
            a = replace(a, plan=True, personajes=True, mundo=True, guia_estilo=True)
        case A.ESCALETISTA:
            a = replace(a, fichas=10)
        case A.JUEZ_MANUSCRITO:
            gates = data.draw(st.sampled_from([ResultadoGates.VERDES, ResultadoGates.FALLOS]))
            a = replace(a, gates=gates)
        case A.EXPORTADOR:
            a = replace(a, es_regeneracion=True)
        case A.INTERPRETE_CAMBIOS:
            a = replace(a, cambio_propuesto=True)
        case _:
            pass
    return replace(inst, avance=a)


def simular_humano(inst: Instantanea, decision: Final, data: st.DataObject) -> Efecto | None:
    """La respuesta humana a una decisión que espera, o `None` si el humano no vuelve."""
    a = inst.avance
    match decision:
        case EsperarHumano(MotivoEspera.BRIEF):
            avance = replace(a, brief=True, texto_libre=data.draw(st.booleans()))
            return Efecto(replace(inst, avance=avance))
        case EsperarHumano(MotivoEspera.CONFIRMACION_HECHOS):
            return Efecto(replace(inst, avance=replace(a, hechos_pendientes=False)))
        case EsperarHumano(MotivoEspera.APROBACION_PLAN):
            accion = data.draw(
                st.sampled_from([AccionHumana.APROBAR_PLAN, AccionHumana.CAMBIOS_PLAN])
            )
            return aplicar_accion_humana(inst, accion)
        case EsperarHumano(MotivoEspera.APROBACION_FINAL):
            accion = data.draw(
                st.sampled_from([AccionHumana.APROBAR_FINAL, AccionHumana.NOTAS_FINAL])
            )
            return aplicar_accion_humana(inst, accion)
        case EsperarHumano(MotivoEspera.CONFIRMACION_CAMBIO):
            if data.draw(st.booleans()):
                return aplicar_accion_humana(inst, AccionHumana.RECHAZAR_CAMBIO)
            # El paso 9a reabre los capítulos que usan el hecho antes de confirmar.
            afectados = data.draw(st.sets(st.integers(1, 10), min_size=1))
            capitulos = tuple(
                CapituloInstantanea(c.numero) if c.numero in afectados else c
                for c in inst.capitulos
            )
            return aplicar_accion_humana(
                replace(inst, capitulos=capitulos), AccionHumana.CONFIRMAR_CAMBIO
            )
        case Publicada():
            if data.draw(st.booleans()):
                return aplicar_accion_humana(inst, AccionHumana.PEDIR_CAMBIO)
            return None
        case Detenida():
            if data.draw(st.booleans()):
                return aplicar_accion_humana(inst, AccionHumana.REINTENTAR)
            return None
        case _:
            raise AssertionError(f"decisión sin respuesta humana: {decision}")
