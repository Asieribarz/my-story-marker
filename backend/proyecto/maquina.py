"""La máquina del grafo: funciones puras sobre una instantánea del estado persistido.

Aquí se decide todo lo que antes era protocolo de la sesión —qué toca, si se reintenta,
cuándo parar— (RF-08, RF-08a, architecture.md §3.1). Nada de este módulo lee ni escribe la
base: `persistencia.py` arma la `Instantanea` desde las tablas, llama a estas funciones y
escribe lo que devuelven. Así V-33 se prueba con Hypothesis sobre instantáneas generadas y
la especificación TLA+ de §3.4 puede seguir el código rama a rama.

Tres funciones, y ninguna mueve el proyecto sin pasar por `transiciones.arista()`:

- `siguiente_orden(inst)`: la decisión de un paso. `Avanzar` es una transición que se
  deriva del estado (una fase completa) y `resolver` las encadena hasta una decisión final:
  lanzar un agente, esperar al humano, `publicada`, `detenida` o `error` con su causa
  (AJ-5: una orden que no se puede emitir, como un prompt que no cabe, D-9).
- `aplicar_desenlace(inst, orden, desenlace)`: el resultado de la orden vigente, ya
  validado por su manejador, sobre la instantánea que dejó ese manejador. Devuelve el
  estado nuevo del proyecto, del capítulo y de los contadores, y los pasos por la tabla.
- `aplicar_accion_humana(inst, accion)`: la única salida de las paradas (RF-05, RN-3).

Correspondencia rama → fila de la tabla de architecture.md §3.1, para la especificación TLA+:

| Rama del código | Fila o arista de §3.1 |
|---|---|
| `siguiente_orden` · `INTAKE` | `intake`: esperar el brief; Extractor si hay texto |
| | libre sin extraer; esperar la confirmación de hechos; Agente de Contexto |
| `_derivar` · `INTAKE`, brief normalizado y sin pendientes | `intake` → `contexto` |
| `siguiente_orden` · `CONTEXTO` | `contexto`: Agente de Contexto |
| `_derivar` · `CONTEXTO`, contexto validado (RF-22, V-20) | `contexto` → `planificacion` |
| `siguiente_orden` · `PLANIFICACION` | el planificador, una sola orden (AJ-1) |
| `_derivar` · `PLANIFICACION` completa | → `aprobacion_plan` o `escaleta` |
| `siguiente_orden` · `APROBACION_PLAN`, `APROBACION_FINAL` | las dos paradas: esperar |
| `siguiente_orden` · `ESCALETA`; `_derivar` con 10 fichas | `escaleta` → `capitulos` |
| `_en_bucle`, `_desenlace_de_capitulo` (RF-63, Q5) | `capitulos` y `regeneracion` · §5 |
| `_derivar` · bucle acabado, todos aprobados | → `verificacion_manuscrito` |
| `_derivar` · bucle acabado, alguno en revisión (RF-64) | → `detenida`; regenerando, `publicada` |
| `_desenlace_de_capitulo` · veto agotado (RF-72a) | → `detenida`; regenerando, `publicada` |
| `_gates` · verdes | → `aprobacion_final` o `publicacion` |
| `_gates` · fallos, y agotados (RF-64a) | → `revision`; agotados, `detenida` o `publicada` |
| `_en_revision`, `_desenlace_de_paso` · Revisor, Bibliotecario | `revision` (AJ-2): por |
| | capítulo, Revisor → Bibliotecario; sin capítulos, un Revisor |
| `_derivar` · `REVISION`, todos registrados | `revision` → `verificacion_manuscrito` |
| `_transitar` a `verificacion_manuscrito` | AJ-3: `pasadas` + 1 y gates sin evaluar |
| `_desenlace_de_paso` · Exportador | `publicacion` → `publicada` |
| `_desenlace_de_paso` · tope agotado (RF-07a, Q6) | → `detenida`; regenerando, `publicada` |
| `siguiente_orden` · `CAMBIO_SOLICITADO` | Intérprete; con el cambio propuesto, esperar |
| `siguiente_orden` · `PUBLICADA`, `DETENIDA` | `publicada`, `detenida`: sin agente |
| `aplicar_accion_humana` | las aristas humanas, reintentar incluido (RF-64b) |
| `aplicar_fallo_del_worker` (R-4) | → `publicada` con `worker_fallido` |

Los contadores (Q4, Q5): `capitulo.intentos` cuenta los fallos de contenido de un capítulo
y numera los intentos del Escritor; `intentos_paso` numera los de cualquier otra orden y
los de los agentes posteriores al Escritor dentro del capítulo. Los dos tienen tope 3, y
`intentos_paso` vuelve a cero en cada avance: un resultado aceptado, una transición o un
cambio de estado de capítulo.
"""

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, assert_never

from backend.proyecto.errores import DecisionHumanaInvalida, TransicionInvalida
from backend.proyecto.transiciones import (
    DESTINO_DE_REINTENTAR,
    ORIGENES_DE_DETENIDA,
    ORIGENES_DE_WORKER_FALLIDO,
    Causa,
    arista,
)
from backend.shared.tipos import Agente as A
from backend.shared.tipos import EstadoCapitulo as C
from backend.shared.tipos import EstadoProyecto as E

TOPE = 3
NUMERO_DE_CAPITULOS = 10


class ResultadoGates(StrEnum):
    """Desenlace de los tres gates de manuscrito de la pasada en curso (paso 8a)."""

    SIN_EVALUAR = "sin_evaluar"
    VERDES = "verdes"
    FALLOS = "fallos"


class TipoDesenlace(StrEnum):
    """Q5: qué hace un resultado con los contadores.

    - `FALLO_CONTENIDO`: deterministas altos o bloqueantes, guardarraíl, juez de capítulo
      que rechaza, o salida inválida del Escritor. Gasta `capitulo.intentos` y vuelve al
      Escritor.
    - `FALLO_FORMA`: salida inválida de un agente posterior al Escritor. Repite solo ese
      agente sobre el mismo borrador y gasta `intentos_paso`.

    Fuera del bucle de capítulo los dos gastan `intentos_paso`.
    """

    ACEPTADO = "aceptado"
    FALLO_CONTENIDO = "fallo_contenido"
    FALLO_FORMA = "fallo_forma"


class Entrada(StrEnum):
    """Qué necesita el agente de la orden: la persistencia lo convierte en la entrada real."""

    TEXTO_LIBRE = "texto_libre"
    BRIEF = "brief"
    HECHOS_CONFIRMADOS = "hechos_confirmados"
    BRIEF_NORMALIZADO = "brief_normalizado"
    CONTEXTO = "contexto"
    NOTAS_PLAN = "notas_plan"
    PLAN = "plan"
    PERSONAJES = "personajes"
    MUNDO = "mundo"
    GUIA_ESTILO = "guia_estilo"
    PROMPT_ENSAMBLADO = "prompt_ensamblado"
    BORRADOR = "borrador"
    BIBLIA = "biblia"
    MANUSCRITO = "manuscrito"
    INFORME_GATES = "informe_gates"
    PETICION = "peticion"
    INFORME_ANTERIOR = "informe_anterior"


class ViaRegistro(StrEnum):
    """Dónde se registra el resultado (architecture.md §8): los borradores de capítulo los
    registra el hook de validación; lo demás, la skill `orquestar-novela`."""

    SKILL = "skill"
    HOOK_VALIDACION = "hook_validacion"


class MotivoEspera(StrEnum):
    BRIEF = "brief"
    CONFIRMACION_HECHOS = "confirmacion_hechos"
    APROBACION_PLAN = "aprobacion_plan"
    APROBACION_FINAL = "aprobacion_final"
    CONFIRMACION_CAMBIO = "confirmacion_cambio"


class AccionHumana(StrEnum):
    APROBAR_PLAN = "aprobar_plan"
    CAMBIOS_PLAN = "cambios_plan"
    APROBAR_FINAL = "aprobar_final"
    NOTAS_FINAL = "notas_final"
    PEDIR_CAMBIO = "pedir_cambio"
    CONFIRMAR_CAMBIO = "confirmar_cambio"
    RECHAZAR_CAMBIO = "rechazar_cambio"
    REINTENTAR = "reintentar"


# ─── La instantánea ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CapituloInstantanea:
    numero: int
    estado: C = C.PENDIENTE
    intentos: int = 0
    # §3 punto 2: el Bibliotecario registró la biblia y el capítulo quedó `aprobado`: sale del
    # bucle. Va si y solo si el estado es `aprobado`.
    terminado: bool = False

    @property
    def fuera_del_bucle(self) -> bool:
        """RF-64: terminado, o en `revision_humana`, que no bloquea el bucle."""
        return self.terminado or self.estado is C.REVISION_HUMANA


@dataclass(frozen=True)
class OrdenVigente:
    id: int
    estado: E
    agente: A
    intento: int
    capitulo: int | None = None


@dataclass(frozen=True)
class Avance:
    """Banderas de avance leídas de las tablas de cada rebanada, no de la sesión."""

    brief: bool = False
    texto_libre: bool = False
    extraccion_hecha: bool = False
    hechos_pendientes: bool = False
    brief_normalizado: bool = False
    contexto_validado: bool = False
    plan: bool = False
    # Hay notas de «cambios» del comprador en aprobacion_plan que el planificador no ha atendido.
    notas_plan_pendientes: bool = False
    guia_estilo: bool = False
    fichas: int = 0
    gates: ResultadoGates = ResultadoGates.SIN_EVALUAR
    cambio_propuesto: bool = False
    # Existe al menos una versión de novela publicada.
    es_regeneracion: bool = False

    @property
    def plan_completo(self) -> bool:
        """AJ-1: el planificador deja plan y guía en la misma salida. Personajes y mundo no
        cuentan: los materializa el contexto (B-1) antes de planificar."""
        return self.plan and self.guia_estilo and not self.notas_plan_pendientes


@dataclass(frozen=True)
class CapituloRevision:
    """AJ-2: un capítulo que corregir en el ciclo de `revision` en curso. `revisado`: el
    Revisor entregó y pasó los deterministas; `registrado`: el Bibliotecario, después."""

    numero: int
    revisado: bool = False
    registrado: bool = False


def _capitulos_iniciales() -> tuple[CapituloInstantanea, ...]:
    return tuple(CapituloInstantanea(n) for n in range(1, NUMERO_DE_CAPITULOS + 1))


@dataclass(frozen=True)
class Instantanea:
    estado: E = E.INTAKE
    capitulos: tuple[CapituloInstantanea, ...] = field(default_factory=_capitulos_iniciales)
    avance: Avance = field(default_factory=Avance)
    detenida_desde: E | None = None
    parada_plan: bool = False
    parada_final: bool = False
    ciclos_revision: int = 0
    intentos_paso: int = 0
    orden_vigente: OrdenVigente | None = None
    # AJ-3: cuántas veces se ha entrado en verificacion_manuscrito; nunca vuelve a cero.
    pasadas: int = 0
    # AJ-2: los capítulos que corregir en el ciclo de revisión en curso, de los gates.
    revision: tuple[CapituloRevision, ...] = ()

    def capitulo(self, numero: int) -> CapituloInstantanea:
        return self.capitulos[numero - 1]


# ─── Decisiones y efectos ────────────────────────────────────────────────────


@dataclass(frozen=True)
class Lanzar:
    agente: A
    intento: int
    capitulo: int | None = None
    entrada: tuple[Entrada, ...] = ()
    registro: ViaRegistro = ViaRegistro.SKILL


@dataclass(frozen=True)
class Avanzar:
    destino: E
    causa: Causa


@dataclass(frozen=True)
class EsperarHumano:
    motivo: MotivoEspera


@dataclass(frozen=True)
class Publicada:
    """El proyecto está en `publicada`: no hay nada que lanzar hasta que el lector pida."""


@dataclass(frozen=True)
class Detenida:
    desde: E


@dataclass(frozen=True)
class ErrorConCausa:
    """AJ-5, TC-3: la orden que toca no se puede emitir —el prompt no cabe (D-9), una
    inconsistencia de continuidad antes de escribir (B-9), falta una herramienta—. No la
    decide la máquina sino quien construye la entrada: el estado no cambia y no gasta
    intento ni ciclo de revisión."""

    causa: str
    capitulo: int | None = None
    detalle: dict[str, Any] = field(default_factory=dict)


Final = Lanzar | EsperarHumano | Publicada | Detenida | ErrorConCausa
Decision = Final | Avanzar


@dataclass(frozen=True)
class Paso:
    origen: E
    destino: E
    causa: Causa


@dataclass(frozen=True)
class Desenlace:
    tipo: TipoDesenlace
    # El fallo de contenido es del guardarraíl de palabras prohibidas (RF-72a).
    guardarrail: bool = False

    @classmethod
    def aceptado(cls) -> "Desenlace":
        return cls(TipoDesenlace.ACEPTADO)

    @classmethod
    def contenido(cls, guardarrail: bool = False) -> "Desenlace":
        return cls(TipoDesenlace.FALLO_CONTENIDO, guardarrail)

    @classmethod
    def forma(cls) -> "Desenlace":
        return cls(TipoDesenlace.FALLO_FORMA)


@dataclass(frozen=True)
class Efecto:
    instantanea: Instantanea
    pasos: tuple[Paso, ...] = ()


@dataclass(frozen=True)
class Resolucion:
    instantanea: Instantanea
    pasos: tuple[Paso, ...]
    decision: Final


# ─── Datos de la máquina ─────────────────────────────────────────────────────

AGENTES_DEL_ESTADO: dict[E, tuple[A, ...]] = {
    E.INTAKE: (A.EXTRACTOR_HECHOS, A.AGENTE_CONTEXTO),
    E.CONTEXTO: (A.AGENTE_CONTEXTO,),
    E.PLANIFICACION: (A.PLANIFICADOR,),
    E.ESCALETA: (A.ESCALETISTA,),
    E.CAPITULOS: (A.ESCRITOR, A.EDITOR_ESTILO, A.JUEZ_CAPITULO, A.BIBLIOTECARIO),
    E.REGENERACION: (A.ESCRITOR, A.EDITOR_ESTILO, A.JUEZ_CAPITULO, A.BIBLIOTECARIO),
    E.VERIFICACION_MANUSCRITO: (A.JUEZ_MANUSCRITO,),
    E.REVISION: (A.REVISOR, A.BIBLIOTECARIO),
    E.PUBLICACION: (A.EXPORTADOR,),
    E.CAMBIO_SOLICITADO: (A.INTERPRETE_CAMBIOS,),
}

AGENTES_DE_CAPITULO = frozenset({A.ESCRITOR, A.EDITOR_ESTILO, A.JUEZ_CAPITULO, A.BIBLIOTECARIO})

# Qué estado de capítulo recibe cada agente del bucle de §5.
_ESTADOS_DEL_AGENTE: dict[A, frozenset[C]] = {
    A.ESCRITOR: frozenset({C.PENDIENTE}),
    A.EDITOR_ESTILO: frozenset({C.BORRADOR}),
    A.JUEZ_CAPITULO: frozenset({C.EDITADO}),
    A.BIBLIOTECARIO: frozenset({C.VERIFICADO}),
}

REGISTRADOS_POR_HOOK = frozenset({A.ESCRITOR, A.EDITOR_ESTILO, A.REVISOR})

_ENTRADAS: dict[A, tuple[Entrada, ...]] = {
    A.EXTRACTOR_HECHOS: (Entrada.TEXTO_LIBRE,),
    A.PLANIFICADOR: (Entrada.CONTEXTO,),
    A.ESCALETISTA: (
        Entrada.CONTEXTO,
        Entrada.PLAN,
        Entrada.PERSONAJES,
        Entrada.MUNDO,
        Entrada.GUIA_ESTILO,
    ),
    A.ESCRITOR: (Entrada.PROMPT_ENSAMBLADO,),
    A.EDITOR_ESTILO: (Entrada.BORRADOR, Entrada.GUIA_ESTILO),
    A.JUEZ_CAPITULO: (Entrada.BORRADOR, Entrada.BIBLIA),
    A.BIBLIOTECARIO: (Entrada.BORRADOR,),
    A.JUEZ_MANUSCRITO: (Entrada.MANUSCRITO, Entrada.BIBLIA),
    A.REVISOR: (Entrada.MANUSCRITO, Entrada.INFORME_GATES),
    A.EXPORTADOR: (Entrada.MANUSCRITO,),
    A.INTERPRETE_CAMBIOS: (Entrada.PETICION,),
}

# El Agente de Contexto hace dos trabajos: normalizar el brief e instanciar el contexto.
_ENTRADAS_DEL_AGENTE_DE_CONTEXTO: dict[E, tuple[Entrada, ...]] = {
    E.INTAKE: (Entrada.BRIEF, Entrada.HECHOS_CONFIRMADOS),
    E.CONTEXTO: (Entrada.BRIEF_NORMALIZADO, Entrada.HECHOS_CONFIRMADOS),
}

_ACCIONES: dict[AccionHumana, tuple[Causa, E | None]] = {
    AccionHumana.APROBAR_PLAN: (Causa.PLAN_APROBADO, E.ESCALETA),
    AccionHumana.CAMBIOS_PLAN: (Causa.PLAN_CON_CAMBIOS, E.PLANIFICACION),
    AccionHumana.APROBAR_FINAL: (Causa.FINAL_APROBADO, E.PUBLICACION),
    AccionHumana.NOTAS_FINAL: (Causa.FINAL_CON_NOTAS, E.REVISION),
    AccionHumana.PEDIR_CAMBIO: (Causa.PETICION_LECTOR, E.CAMBIO_SOLICITADO),
    AccionHumana.CONFIRMAR_CAMBIO: (Causa.CAMBIO_CONFIRMADO, E.REGENERACION),
    AccionHumana.RECHAZAR_CAMBIO: (Causa.CAMBIO_RECHAZADO, E.PUBLICADA),
    # El destino de reintentar depende de la fase de la que vino `detenida`.
    AccionHumana.REINTENTAR: (Causa.REINTENTAR, None),
}


# ─── Piezas comunes ──────────────────────────────────────────────────────────


def via_de_registro(agente: A) -> ViaRegistro:
    return ViaRegistro.HOOK_VALIDACION if agente in REGISTRADOS_POR_HOOK else ViaRegistro.SKILL


def _lanzar(inst: Instantanea, agente: A, intento: int, capitulo: int | None = None) -> Lanzar:
    if agente is A.AGENTE_CONTEXTO:
        base = _ENTRADAS_DEL_AGENTE_DE_CONTEXTO[inst.estado]
    else:
        base = _ENTRADAS[agente]
    extra: list[Entrada] = []
    if agente is A.PLANIFICADOR and inst.avance.notas_plan_pendientes:
        extra.append(Entrada.NOTAS_PLAN)
    if intento > 1:
        extra.append(Entrada.INFORME_ANTERIOR)
    return Lanzar(agente, intento, capitulo, (*base, *extra), via_de_registro(agente))


def _transitar(inst: Instantanea, destino: E, causa: Causa) -> tuple[Instantanea, Paso]:
    """Un paso por la tabla. Toda transición es un avance: `intentos_paso` a cero."""
    arista(inst.estado, destino, causa)
    nuevo = replace(
        inst,
        estado=destino,
        detenida_desde=inst.estado if destino is E.DETENIDA else None,
        intentos_paso=0,
    )
    if destino is E.VERIFICACION_MANUSCRITO:
        # AJ-3: una pasada nueva, con sus gates por evaluar.
        avance = replace(nuevo.avance, gates=ResultadoGates.SIN_EVALUAR)
        nuevo = replace(nuevo, pasadas=inst.pasadas + 1, avance=avance)
    if causa is Causa.GATES_CON_FALLOS:
        # AJ-2: un ciclo de revisión nuevo empieza sin capítulos corregidos; reintentar
        # desde `detenida` sigue donde se quedó.
        nuevo = replace(nuevo, revision=tuple(CapituloRevision(c.numero) for c in inst.revision))
    return nuevo, Paso(inst.estado, destino, causa)


def _con_capitulo(inst: Instantanea, capitulo: CapituloInstantanea) -> Instantanea:
    capitulos = tuple(capitulo if c.numero == capitulo.numero else c for c in inst.capitulos)
    return replace(inst, capitulos=capitulos)


def _capitulo_en_curso(inst: Instantanea) -> CapituloInstantanea | None:
    """El capítulo no terminado de menor número; los de `revision_humana` se saltan (RF-64)."""
    return next((c for c in inst.capitulos if not c.fuera_del_bucle), None)


def _destino_de_fracaso(inst: Instantanea) -> E:
    """RF-07a, RF-64, RF-64a: `detenida` en la generación inicial; `publicada` con el cambio
    fallido en una regeneración. `cambio_solicitado` y `regeneracion` solo existen en una."""
    if inst.estado in (E.CAMBIO_SOLICITADO, E.REGENERACION):
        return E.PUBLICADA
    regenerable = (E.VERIFICACION_MANUSCRITO, E.REVISION, E.PUBLICACION)
    if inst.estado in regenerable and inst.avance.es_regeneracion:
        return E.PUBLICADA
    return E.DETENIDA


# ─── Siguiente orden ─────────────────────────────────────────────────────────


def _derivar(inst: Instantanea) -> Avanzar | None:
    """Las transiciones que se leen del estado: una fase ha dejado hecho lo que la cierra."""
    a = inst.avance
    match inst.estado:
        case E.INTAKE:
            extraido = a.extraccion_hecha or not a.texto_libre
            if a.brief and a.brief_normalizado and extraido and not a.hechos_pendientes:
                return Avanzar(E.CONTEXTO, Causa.BRIEF_NORMALIZADO)
        case E.CONTEXTO:
            if a.contexto_validado:
                return Avanzar(E.PLANIFICACION, Causa.CONTEXTO_VALIDADO)
        case E.PLANIFICACION:
            if a.plan_completo:
                destino = E.APROBACION_PLAN if inst.parada_plan else E.ESCALETA
                return Avanzar(destino, Causa.PLAN_COMPLETO)
        case E.ESCALETA:
            if a.fichas >= NUMERO_DE_CAPITULOS:
                return Avanzar(E.CAPITULOS, Causa.ESCALETA_COMPLETA)
        case E.CAPITULOS | E.REGENERACION:
            if _capitulo_en_curso(inst) is None:
                if any(c.estado is C.REVISION_HUMANA for c in inst.capitulos):
                    return Avanzar(_destino_de_fracaso(inst), Causa.CAPITULO_AGOTADO)
                return Avanzar(E.VERIFICACION_MANUSCRITO, Causa.CAPITULOS_APROBADOS)
        case E.REVISION:
            if inst.revision and all(c.registrado for c in inst.revision):
                return Avanzar(E.VERIFICACION_MANUSCRITO, Causa.REVISION_HECHA)
        case _:
            pass
    return None


def _en_bucle(inst: Instantanea) -> Lanzar:
    """§5: Escritor → Editor (+ deterministas al registrar) → juez → Bibliotecario.

    §3 punto 2: `editado` = Editor y deterministas en verde; `verificado` = además el juez;
    el Bibliotecario trabaja sobre `verificado` y al aceptarlo el capítulo queda `aprobado`.
    """
    capitulo = _capitulo_en_curso(inst)
    if capitulo is None:
        raise ValueError("bucle sin capítulo en curso: la derivación debía haberlo cerrado")
    siguiente = inst.intentos_paso + 1
    match capitulo.estado:
        case C.PENDIENTE:
            return _lanzar(inst, A.ESCRITOR, capitulo.intentos + 1, capitulo.numero)
        case C.BORRADOR:
            return _lanzar(inst, A.EDITOR_ESTILO, siguiente, capitulo.numero)
        case C.EDITADO:
            return _lanzar(inst, A.JUEZ_CAPITULO, siguiente, capitulo.numero)
        case C.VERIFICADO:
            return _lanzar(inst, A.BIBLIOTECARIO, siguiente, capitulo.numero)
        case C.APROBADO | C.REVISION_HUMANA:
            raise ValueError(f"un capítulo en {capitulo.estado.value} no está en curso")
    assert_never(capitulo.estado)


def _en_revision(inst: Instantanea) -> Lanzar | ErrorConCausa:
    """AJ-2, §3 punto 7: por cada capítulo que corregir, Revisor (con los deterministas al
    registrar) → Bibliotecario sobre la versión nueva. M-6: nunca hay Revisor sin capítulo;
    los señalan los gates rojos o, tras «cambios» en `aprobacion_final`, la decisión (todos
    si no dice cuáles). Sin ninguno, `error` sin gastar ciclo."""
    siguiente = inst.intentos_paso + 1
    pendiente = next((c for c in inst.revision if not c.registrado), None)
    if pendiente is None:
        return ErrorConCausa("revision_sin_capitulos")
    agente = A.BIBLIOTECARIO if pendiente.revisado else A.REVISOR
    return _lanzar(inst, agente, siguiente, pendiente.numero)


def siguiente_orden(inst: Instantanea) -> Decision:
    """RF-08, RF-08a: la decisión, función determinista de la instantánea.

    Con una orden vigente, la decisión es esa orden: pedirla otra vez no cambia nada.
    """
    vigente = inst.orden_vigente
    if vigente is not None:
        return _lanzar(inst, vigente.agente, vigente.intento, vigente.capitulo)
    derivada = _derivar(inst)
    if derivada is not None:
        return derivada
    a = inst.avance
    siguiente = inst.intentos_paso + 1
    match inst.estado:
        case E.INTAKE:
            if not a.brief:
                return EsperarHumano(MotivoEspera.BRIEF)
            if a.texto_libre and not a.extraccion_hecha:
                return _lanzar(inst, A.EXTRACTOR_HECHOS, siguiente)
            if a.hechos_pendientes:
                return EsperarHumano(MotivoEspera.CONFIRMACION_HECHOS)
            return _lanzar(inst, A.AGENTE_CONTEXTO, siguiente)
        case E.CONTEXTO:
            return _lanzar(inst, A.AGENTE_CONTEXTO, siguiente)
        case E.PLANIFICACION:
            # AJ-1: una sola orden; el planificador escribe plan, personajes, mundo y guía.
            return _lanzar(inst, A.PLANIFICADOR, siguiente)
        case E.APROBACION_PLAN:
            return EsperarHumano(MotivoEspera.APROBACION_PLAN)
        case E.ESCALETA:
            return _lanzar(inst, A.ESCALETISTA, siguiente)
        case E.CAPITULOS | E.REGENERACION:
            return _en_bucle(inst)
        case E.VERIFICACION_MANUSCRITO:
            return _lanzar(inst, A.JUEZ_MANUSCRITO, siguiente)
        case E.REVISION:
            return _en_revision(inst)
        case E.APROBACION_FINAL:
            return EsperarHumano(MotivoEspera.APROBACION_FINAL)
        case E.PUBLICACION:
            return _lanzar(inst, A.EXPORTADOR, siguiente)
        case E.PUBLICADA:
            return Publicada()
        case E.CAMBIO_SOLICITADO:
            if a.cambio_propuesto:
                return EsperarHumano(MotivoEspera.CONFIRMACION_CAMBIO)
            return _lanzar(inst, A.INTERPRETE_CAMBIOS, siguiente)
        case E.DETENIDA:
            if inst.detenida_desde is None:
                raise ValueError("detenida sin la fase de la que viene")
            return Detenida(inst.detenida_desde)
    assert_never(inst.estado)


def _derivaciones(inst: Instantanea) -> tuple[Instantanea, tuple[Paso, ...], Final]:
    pasos: list[Paso] = []
    # Las derivaciones no forman ciclos: cada una lleva a una fase posterior.
    for _ in range(len(E) + 1):
        decision = siguiente_orden(inst)
        if not isinstance(decision, Avanzar):
            return inst, tuple(pasos), decision
        inst, paso = _transitar(inst, decision.destino, decision.causa)
        pasos.append(paso)
    raise AssertionError("las derivaciones del grafo no convergen")


def resolver(inst: Instantanea) -> Resolucion:
    """Encadena las transiciones derivadas hasta una decisión final."""
    final, pasos, decision = _derivaciones(inst)
    return Resolucion(final, pasos, decision)


# ─── Desenlace de una orden ──────────────────────────────────────────────────


def _gates(inst: Instantanea) -> tuple[Instantanea, tuple[Paso, ...]]:
    """RF-64a: el juez puntúa y el backend decide con los gates (paso 8a)."""
    match inst.avance.gates:
        case ResultadoGates.VERDES:
            destino = E.APROBACION_FINAL if inst.parada_final else E.PUBLICACION
            nuevo, paso = _transitar(inst, destino, Causa.GATES_VERDES)
        case ResultadoGates.FALLOS if inst.ciclos_revision < TOPE:
            nuevo, paso = _transitar(inst, E.REVISION, Causa.GATES_CON_FALLOS)
            nuevo = replace(nuevo, ciclos_revision=inst.ciclos_revision + 1)
        case ResultadoGates.FALLOS:
            nuevo, paso = _transitar(inst, _destino_de_fracaso(inst), Causa.REVISIONES_AGOTADAS)
        case ResultadoGates.SIN_EVALUAR:
            raise ValueError("juez-manuscrito aceptado sin gates evaluados: los aplica el paso 8a")
        case _:
            assert_never(inst.avance.gates)
    return nuevo, (paso,)


def _marcar_revision(
    inst: Instantanea, numero: int, *, revisado: bool = False, registrado: bool = False
) -> Instantanea:
    """AJ-2: el Revisor o el Bibliotecario de revisión dejan hecho su paso del capítulo."""
    revision = tuple(
        replace(c, revisado=c.revisado or revisado, registrado=c.registrado or registrado)
        if c.numero == numero
        else c
        for c in inst.revision
    )
    return replace(inst, revision=revision)


def _desenlace_de_paso(
    inst: Instantanea, orden: OrdenVigente, desenlace: Desenlace
) -> tuple[Instantanea, tuple[Paso, ...]]:
    if desenlace.tipo is not TipoDesenlace.ACEPTADO:
        intentos = inst.intentos_paso + 1
        if intentos < TOPE:
            return replace(inst, intentos_paso=intentos), ()
        nuevo, paso = _transitar(inst, _destino_de_fracaso(inst), Causa.TOPE_AGOTADO)
        return nuevo, (paso,)
    aceptado = replace(inst, intentos_paso=0)
    match orden.agente:
        case A.EXTRACTOR_HECHOS:
            avance = replace(aceptado.avance, extraccion_hecha=True)
            return replace(aceptado, avance=avance), ()
        case A.PLANIFICADOR:
            avance = replace(aceptado.avance, notas_plan_pendientes=False)
            return replace(aceptado, avance=avance), ()
        case A.JUEZ_MANUSCRITO:
            return _gates(aceptado)
        case A.REVISOR if orden.capitulo is not None:
            return _marcar_revision(aceptado, orden.capitulo, revisado=True), ()
        case A.REVISOR:
            nuevo, paso = _transitar(aceptado, E.VERIFICACION_MANUSCRITO, Causa.REVISION_HECHA)
            return nuevo, (paso,)
        case A.BIBLIOTECARIO if orden.capitulo is not None:
            return _marcar_revision(aceptado, orden.capitulo, registrado=True), ()
        case A.EXPORTADOR:
            nuevo, paso = _transitar(aceptado, E.PUBLICADA, Causa.VERSION_PUBLICADA)
            return nuevo, (paso,)
        case _:
            # El resto deja su rastro en las tablas de su rebanada, que ya lee la instantánea.
            return aceptado, ()


def _desenlace_de_capitulo(
    inst: Instantanea, orden: OrdenVigente, desenlace: Desenlace
) -> tuple[Instantanea, tuple[Paso, ...]]:
    if orden.capitulo is None:
        raise ValueError(f"una orden de {orden.agente.value} sin capítulo")
    capitulo = inst.capitulo(orden.capitulo)
    if capitulo.estado not in _ESTADOS_DEL_AGENTE[orden.agente] or capitulo.terminado:
        raise ValueError(
            f"{orden.agente.value} no trabaja sobre un capítulo en {capitulo.estado.value}"
        )
    tipo = desenlace.tipo
    if orden.agente is A.ESCRITOR and tipo is TipoDesenlace.FALLO_FORMA:
        tipo = TipoDesenlace.FALLO_CONTENIDO  # Q5: la salida inválida del Escritor es de contenido
    if orden.agente is A.BIBLIOTECARIO and tipo is TipoDesenlace.FALLO_CONTENIDO:
        tipo = TipoDesenlace.FALLO_FORMA  # Q5: el Bibliotecario solo falla en la forma

    if tipo is TipoDesenlace.ACEPTADO:
        avanzado = {
            A.ESCRITOR: replace(capitulo, estado=C.BORRADOR),
            A.EDITOR_ESTILO: replace(capitulo, estado=C.EDITADO),
            A.JUEZ_CAPITULO: replace(capitulo, estado=C.VERIFICADO),
            A.BIBLIOTECARIO: replace(capitulo, estado=C.APROBADO, terminado=True),
        }[orden.agente]
        return _con_capitulo(replace(inst, intentos_paso=0), avanzado), ()

    if tipo is TipoDesenlace.FALLO_CONTENIDO:
        intentos = capitulo.intentos + 1
        if intentos < TOPE:
            reescribir = replace(capitulo, estado=C.PENDIENTE, intentos=intentos)
            return _con_capitulo(replace(inst, intentos_paso=0), reescribir), ()
        agotado = replace(capitulo, estado=C.REVISION_HUMANA, intentos=intentos)
        nuevo = _con_capitulo(replace(inst, intentos_paso=0), agotado)
        if desenlace.guardarrail:
            # RF-72a: el veto agotado detiene la generación sin esperar al final del bucle.
            nuevo, paso = _transitar(nuevo, _destino_de_fracaso(nuevo), Causa.VETO_AGOTADO)
            return nuevo, (paso,)
        return nuevo, ()

    intentos_paso = inst.intentos_paso + 1
    if intentos_paso < TOPE:
        return replace(inst, intentos_paso=intentos_paso), ()
    agotado = replace(capitulo, estado=C.REVISION_HUMANA)
    return _con_capitulo(replace(inst, intentos_paso=0), agotado), ()


def aplicar_desenlace(inst: Instantanea, orden: OrdenVigente, desenlace: Desenlace) -> Efecto:
    """Aplica el desenlace de la orden vigente a la instantánea que dejó su manejador.

    Devuelve el estado nuevo y los pasos por la tabla, incluidas las transiciones que se
    derivan del resultado (una fase que queda completa). Una orden que no es la vigente,
    o que no corresponde al estado, es un error de programación: `ValueError`.
    """
    if inst.orden_vigente != orden:
        raise ValueError(f"el desenlace no es de la orden vigente: {orden.id}")
    if orden.estado is not inst.estado or orden.agente not in AGENTES_DEL_ESTADO.get(
        inst.estado, ()
    ):
        raise ValueError(f"{orden.agente.value} no tiene orden en {inst.estado.value}")
    base = replace(inst, orden_vigente=None)
    # AJ-2: el Bibliotecario de `revision` tiene su propio desenlace, no el del bucle.
    if orden.agente in AGENTES_DE_CAPITULO and orden.estado in (E.CAPITULOS, E.REGENERACION):
        nuevo, pasos = _desenlace_de_capitulo(base, orden, desenlace)
    else:
        nuevo, pasos = _desenlace_de_paso(base, orden, desenlace)
    final, derivados, _ = _derivaciones(nuevo)
    return Efecto(final, (*pasos, *derivados))


# ─── Acciones humanas ────────────────────────────────────────────────────────


def _reabrir(inst: Instantanea) -> Instantanea:
    """RF-64b: los capítulos en `revision_humana` vuelven a empezar, con su contador a cero."""
    capitulos = tuple(
        CapituloInstantanea(c.numero) if c.estado is C.REVISION_HUMANA else c
        for c in inst.capitulos
    )
    return replace(inst, capitulos=capitulos, ciclos_revision=0)


def aplicar_accion_humana(inst: Instantanea, accion: AccionHumana) -> Efecto:
    """La única salida de las paradas (RF-05, RF-05a, RN-3).

    Una acción que la tabla no admite desde el estado actual da `TransicionInvalida`
    (RF-04); una que la tabla admite pero aún no procede —confirmar un cambio que el
    Intérprete no ha propuesto— da `DecisionHumanaInvalida`.
    """
    causa, fijo = _ACCIONES[accion]
    base = replace(inst, orden_vigente=None)
    if fijo is None:
        # Reintentar: vuelve a la fase de origen; desde el bucle o los gates, RF-64b.
        if inst.estado is not E.DETENIDA or inst.detenida_desde is None:
            raise TransicionInvalida(inst.estado, None, causa.value)
        destino = DESTINO_DE_REINTENTAR[inst.detenida_desde]
        if destino is E.CAPITULOS:
            base = _reabrir(base)
    else:
        destino = fijo
        arista(inst.estado, destino, causa)
        if accion in (AccionHumana.CONFIRMAR_CAMBIO, AccionHumana.RECHAZAR_CAMBIO):
            if not inst.avance.cambio_propuesto:
                raise DecisionHumanaInvalida(
                    "el Intérprete aún no ha propuesto el cambio: no hay nada que confirmar"
                )
            base = replace(base, avance=replace(base.avance, cambio_propuesto=False))
        if accion is AccionHumana.CAMBIOS_PLAN:
            base = replace(base, avance=replace(base.avance, notas_plan_pendientes=True))
        if accion is AccionHumana.CONFIRMAR_CAMBIO:
            # Cada regeneración cuenta sus propios ciclos de revisión (RF-64a).
            base = replace(base, ciclos_revision=0)
    nuevo, paso = _transitar(base, destino, causa)
    final, derivados, _ = _derivaciones(nuevo)
    return Efecto(final, (paso, *derivados))


def aplicar_fallo_del_worker(inst: Instantanea) -> Efecto:
    """R-4, TC-9: el `claude -p` de un trabajo falló, se colgó o murió. El proyecto vuelve a
    `publicada` con el cambio fallido (AJ-6 lo deshace `cambio/`) y la orden vigente, si la
    hay, deja de serlo. Solo en una regeneración: fuera de sus fases, `TransicionInvalida`."""
    if inst.estado not in ORIGENES_DE_WORKER_FALLIDO or not inst.avance.es_regeneracion:
        raise TransicionInvalida(inst.estado, E.PUBLICADA, Causa.WORKER_FALLIDO.value)
    nuevo, paso = _transitar(replace(inst, orden_vigente=None), E.PUBLICADA, Causa.WORKER_FALLIDO)
    return Efecto(nuevo, (paso,))


# ─── Invariantes ─────────────────────────────────────────────────────────────


def incoherencias(inst: Instantanea) -> tuple[str, ...]:
    """Lo que la máquina supone de una instantánea, y que `aplicar_*` conservan (V-33).

    Las restricciones de la base (CHECK) son más anchas: admiten, por ejemplo, un 3 en
    `intentos_paso`, que la máquina solo usa como valor de paso antes de transitar.
    """
    fallos: list[str] = []
    if not 0 <= inst.intentos_paso < TOPE:
        fallos.append(f"intentos_paso={inst.intentos_paso}")
    if not 0 <= inst.ciclos_revision <= TOPE:
        fallos.append(f"ciclos_revision={inst.ciclos_revision}")
    if (inst.estado is E.DETENIDA) != (inst.detenida_desde is not None):
        fallos.append("detenida_desde solo acompaña a detenida")
    if inst.detenida_desde is not None and inst.detenida_desde not in ORIGENES_DE_DETENIDA:
        fallos.append(f"detenida_desde={inst.detenida_desde.value}")
    if [c.numero for c in inst.capitulos] != list(range(1, NUMERO_DE_CAPITULOS + 1)):
        fallos.append("los capítulos no son 1..10")
    for c in inst.capitulos:
        tope = TOPE if c.estado is C.REVISION_HUMANA else TOPE - 1
        if not 0 <= c.intentos <= tope:
            fallos.append(f"capítulo {c.numero}: intentos={c.intentos} en {c.estado.value}")
        if c.terminado != (c.estado is C.APROBADO):
            fallos.append(f"capítulo {c.numero}: terminado={c.terminado} en {c.estado.value}")
    if inst.pasadas < 0:
        fallos.append(f"pasadas={inst.pasadas}")
    numeros = [c.numero for c in inst.revision]
    if len(set(numeros)) != len(numeros) or not all(1 <= n <= NUMERO_DE_CAPITULOS for n in numeros):
        fallos.append(f"revision={numeros}")
    if any(c.registrado and not c.revisado for c in inst.revision):
        fallos.append("un capítulo registrado en revisión sin revisar")
    orden = inst.orden_vigente
    if orden is not None:
        if orden.estado is not inst.estado:
            fallos.append(f"orden vigente de {orden.estado.value} en {inst.estado.value}")
        if not 1 <= orden.intento <= TOPE:
            fallos.append(f"orden vigente con intento {orden.intento}")
    return tuple(fallos)
