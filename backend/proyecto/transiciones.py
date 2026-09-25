"""La tabla de transiciones del proyecto, como dato (architecture.md §3.1, RF-04, RN-3).

Cada arista es `(origen, destino, causa)`, y la causa dice si la escribe el backend
(automática) o una acción humana. Es la única fuente: la máquina de `maquina.py` no mueve
el proyecto sin pasar por `arista()`, la persistencia vuelve a comprobar cada paso antes
de escribirlo, y la especificación TLA+ de §3.4 modela esta misma tabla.

Las paradas humanas no se hacen cumplir con una comprobación, sino con la ausencia de la
arista: de `aprobacion_plan`, `aprobacion_final`, `publicada` y `detenida` no sale ninguna
automática (RF-05, RF-05a). `cambio_solicitado` tiene dos: la del tope agotado del
Intérprete y la del worker fallido (R-4). La parada es la confirmación del cambio ya
propuesto, y de ahí solo se sale confirmando o rechazando.

Además de las aristas del diagrama de §3.1, están las del tope de intentos (RF-07a): de
cada fase con agente a `detenida` en la generación inicial, y a `publicada` con el cambio
fallido en una regeneración; y «reintentar» vuelve a la fase de la que vino `detenida`
(`DESTINO_DE_REINTENTAR`), salvo `verificacion_manuscrito`, que vuelve a `capitulos`
porque se aplica RF-64b.
"""

from dataclasses import dataclass
from enum import StrEnum

from backend.proyecto.errores import TransicionInvalida
from backend.shared.tipos import EstadoProyecto as E


class Causa(StrEnum):
    """Lo que se escribe en `transicion.causa` (RF-09): quién y por qué movió el proyecto."""

    # Automáticas: el backend, al registrar un resultado o al derivar el estado de las tablas.
    BRIEF_NORMALIZADO = "brief_normalizado"
    CONTEXTO_VALIDADO = "contexto_validado"
    PLAN_COMPLETO = "plan_completo"
    ESCALETA_COMPLETA = "escaleta_completa"
    CAPITULOS_APROBADOS = "capitulos_aprobados"
    CAPITULO_AGOTADO = "capitulo_agotado"
    VETO_AGOTADO = "veto_agotado"
    GATES_VERDES = "gates_verdes"
    GATES_CON_FALLOS = "gates_con_fallos"
    REVISIONES_AGOTADAS = "revisiones_agotadas"
    REVISION_HECHA = "revision_hecha"
    VERSION_PUBLICADA = "version_publicada"
    TOPE_AGOTADO = "tope_agotado"
    # R-4: el `claude -p` del worker falló, se colgó o murió a mitad de una regeneración.
    WORKER_FALLIDO = "worker_fallido"
    # Humanas: la única salida de las paradas.
    PLAN_APROBADO = "plan_aprobado"
    PLAN_CON_CAMBIOS = "plan_con_cambios"
    FINAL_APROBADO = "final_aprobado"
    FINAL_CON_NOTAS = "final_con_notas"
    PETICION_LECTOR = "peticion_lector"
    CAMBIO_CONFIRMADO = "cambio_confirmado"
    CAMBIO_RECHAZADO = "cambio_rechazado"
    REINTENTAR = "reintentar"

    @property
    def humana(self) -> bool:
        return self in CAUSAS_HUMANAS


CAUSAS_HUMANAS = frozenset(
    {
        Causa.PLAN_APROBADO,
        Causa.PLAN_CON_CAMBIOS,
        Causa.FINAL_APROBADO,
        Causa.FINAL_CON_NOTAS,
        Causa.PETICION_LECTOR,
        Causa.CAMBIO_CONFIRMADO,
        Causa.CAMBIO_RECHAZADO,
        Causa.REINTENTAR,
    }
)


@dataclass(frozen=True)
class Arista:
    origen: E
    destino: E
    causa: Causa

    @property
    def humana(self) -> bool:
        return self.causa.humana


# RF-64b y Q6: «reintentar» vuelve a la fase de origen; desde el bucle o los gates, al bucle.
DESTINO_DE_REINTENTAR: dict[E, E] = {
    E.INTAKE: E.INTAKE,
    E.CONTEXTO: E.CONTEXTO,
    E.PLANIFICACION: E.PLANIFICACION,
    E.ESCALETA: E.ESCALETA,
    E.CAPITULOS: E.CAPITULOS,
    E.VERIFICACION_MANUSCRITO: E.CAPITULOS,
    E.REVISION: E.REVISION,
    E.PUBLICACION: E.PUBLICACION,
}

# RF-07a: fases cuya orden, agotada, detiene la generación inicial…
_DETENIBLES_POR_TOPE = (
    E.INTAKE,
    E.CONTEXTO,
    E.PLANIFICACION,
    E.ESCALETA,
    E.VERIFICACION_MANUSCRITO,
    E.REVISION,
    E.PUBLICACION,
)
# …y las que, en una regeneración, vuelven a `publicada` con el cambio fallido.
_FALLIDAS_POR_TOPE = (E.VERIFICACION_MANUSCRITO, E.REVISION, E.PUBLICACION, E.CAMBIO_SOLICITADO)
# R-4, TC-9: las fases que recorre un trabajo del worker; si su `claude -p` falla, el proyecto
# vuelve a `publicada` con el cambio fallido (AJ-6).
ORIGENES_DE_WORKER_FALLIDO = (
    E.CAMBIO_SOLICITADO,
    E.REGENERACION,
    E.VERIFICACION_MANUSCRITO,
    E.REVISION,
    E.PUBLICACION,
)


TRANSICIONES: tuple[Arista, ...] = (
    # §3.1 · intake → contexto → planificacion
    Arista(E.INTAKE, E.CONTEXTO, Causa.BRIEF_NORMALIZADO),
    Arista(E.CONTEXTO, E.PLANIFICACION, Causa.CONTEXTO_VALIDADO),
    # §3.1 · planificacion, con la parada activa o inactiva
    Arista(E.PLANIFICACION, E.APROBACION_PLAN, Causa.PLAN_COMPLETO),
    Arista(E.PLANIFICACION, E.ESCALETA, Causa.PLAN_COMPLETO),
    Arista(E.APROBACION_PLAN, E.ESCALETA, Causa.PLAN_APROBADO),
    Arista(E.APROBACION_PLAN, E.PLANIFICACION, Causa.PLAN_CON_CAMBIOS),
    # §3.1 · escaleta → capitulos, y la salida del bucle
    Arista(E.ESCALETA, E.CAPITULOS, Causa.ESCALETA_COMPLETA),
    Arista(E.CAPITULOS, E.VERIFICACION_MANUSCRITO, Causa.CAPITULOS_APROBADOS),
    Arista(E.CAPITULOS, E.DETENIDA, Causa.CAPITULO_AGOTADO),
    Arista(E.CAPITULOS, E.DETENIDA, Causa.VETO_AGOTADO),
    # §3.1 · gates de manuscrito y revisión
    Arista(E.VERIFICACION_MANUSCRITO, E.REVISION, Causa.GATES_CON_FALLOS),
    Arista(E.REVISION, E.VERIFICACION_MANUSCRITO, Causa.REVISION_HECHA),
    Arista(E.VERIFICACION_MANUSCRITO, E.DETENIDA, Causa.REVISIONES_AGOTADAS),
    Arista(E.VERIFICACION_MANUSCRITO, E.PUBLICADA, Causa.REVISIONES_AGOTADAS),
    Arista(E.VERIFICACION_MANUSCRITO, E.APROBACION_FINAL, Causa.GATES_VERDES),
    Arista(E.VERIFICACION_MANUSCRITO, E.PUBLICACION, Causa.GATES_VERDES),
    Arista(E.APROBACION_FINAL, E.REVISION, Causa.FINAL_CON_NOTAS),
    Arista(E.APROBACION_FINAL, E.PUBLICACION, Causa.FINAL_APROBADO),
    # §3.1 · publicación y cambio del lector
    Arista(E.PUBLICACION, E.PUBLICADA, Causa.VERSION_PUBLICADA),
    Arista(E.PUBLICADA, E.CAMBIO_SOLICITADO, Causa.PETICION_LECTOR),
    Arista(E.CAMBIO_SOLICITADO, E.PUBLICADA, Causa.CAMBIO_RECHAZADO),
    Arista(E.CAMBIO_SOLICITADO, E.REGENERACION, Causa.CAMBIO_CONFIRMADO),
    Arista(E.REGENERACION, E.VERIFICACION_MANUSCRITO, Causa.CAPITULOS_APROBADOS),
    Arista(E.REGENERACION, E.PUBLICADA, Causa.CAPITULO_AGOTADO),
    Arista(E.REGENERACION, E.PUBLICADA, Causa.VETO_AGOTADO),
    # RF-07a y Q6 · el tope de una orden que no es ciclo de capítulo
    *(Arista(origen, E.DETENIDA, Causa.TOPE_AGOTADO) for origen in _DETENIBLES_POR_TOPE),
    *(Arista(origen, E.PUBLICADA, Causa.TOPE_AGOTADO) for origen in _FALLIDAS_POR_TOPE),
    # R-4 · el worker falla a mitad de un trabajo
    *(Arista(origen, E.PUBLICADA, Causa.WORKER_FALLIDO) for origen in ORIGENES_DE_WORKER_FALLIDO),
    # RF-64b y Q6 · reintentar desde detenida
    *(
        Arista(E.DETENIDA, destino, Causa.REINTENTAR)
        for destino in dict.fromkeys(DESTINO_DE_REINTENTAR.values())
    ),
)

_INDICE: dict[tuple[E, E, Causa], Arista] = {
    (a.origen, a.destino, a.causa): a for a in TRANSICIONES
}

ORIGENES_DE_DETENIDA = frozenset(a.origen for a in TRANSICIONES if a.destino is E.DETENIDA)

# RF-05, RF-05a: de aquí no sale ninguna arista automática.
PARADAS_HUMANAS = frozenset({E.APROBACION_PLAN, E.APROBACION_FINAL, E.PUBLICADA, E.DETENIDA})


def arista(origen: E, destino: E, causa: Causa) -> Arista:
    """La arista de la tabla, o `TransicionInvalida` si no existe (RF-04)."""
    encontrada = _INDICE.get((origen, destino, causa))
    if encontrada is None:
        raise TransicionInvalida(origen, destino, causa.value)
    return encontrada


def salidas(origen: E) -> tuple[Arista, ...]:
    return tuple(a for a in TRANSICIONES if a.origen is origen)
