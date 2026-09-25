"""Manejador de `planificador` (R-1, RF-30 a RF-33, RF-77a).

Lo agrega `proyecto/manejadores.py`. La salida pasa tres filtros y, al primero que falla,
no se persiste nada:

1. El esquema, `SalidaPlanificador`: si no encaja, fallo de forma.
2. B-1, manda el contexto validado. El planificador añade y no cambia: el plan copia del
   contexto el modelo, el final, la curva, la pregunta dramática y los hitos del nudo y el
   desenlace, y sitúa los dos primeros dentro del planteamiento (B-3); están todos los
   personajes y las localizaciones del contexto con su `origen`, `rol`, `arco`, `nivel` y
   `padre`; lo nuevo es ficticio o `micro`; el nombre de un personaje real es el del
   destinatario o sale literal en su hecho (B-4); y la guía conserva el lenguaje del contexto
   y lleva `lenguaje.prohibidas` en la lista negra. Cada contradicción es un hallazgo
   bloqueante y la salida, un fallo de contenido, con el informe para el intento siguiente.
3. La base, en `guardar_planificacion`, que también siembra el glosario: si aún choca
   (`SalidaIncoherente`), fallo de contenido.

RF-34 se cumple por construcción: una localización es clave si trae `hito`, y el tipo solo
admite hitos del catálogo de B-3.
"""

import sqlite3
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping

from pydantic import ValidationError

from backend.contexto.modelos import Lenguaje, NivelEspacial, Novela
from backend.contexto.persistencia import contexto_vigente
from backend.planificacion.consultas import SalidaIncoherente, guardar_planificacion
from backend.planificacion.modelos import SalidaPlanificador
from backend.proyecto.manejadores import ContextoManejo, Manejador, Salida
from backend.proyecto.maquina import Desenlace
from backend.shared.tipos import Agente, Hallazgo, Hito, Severidad

# RF-77a: estas comprobaciones son las del esquema de salida del agente.
VERIFICADOR = "esquema"


def hallazgo(
    regla: str,
    localizacion: str,
    evidencia: object,
    esperado: str,
    severidad: Severidad = Severidad.BLOQUEANTE,
) -> Hallazgo:
    return Hallazgo(
        verificador=VERIFICADOR,
        severidad=severidad,
        regla=regla,
        localizacion=localizacion,
        evidencia=str(evidencia) if isinstance(evidencia, str) else repr(evidencia),
        esperado=esperado,
    )


def errores_de_forma(error: ValidationError) -> list[str]:
    """Ruta y mensaje de cada error, sin el valor recibido: puede ser un dato excluido."""
    return [
        f"{'.'.join(str(parte) for parte in e['loc']) or '(raíz)'}: {e['msg']}"
        for e in error.errors(include_url=False)
    ]


def rechazo(hallazgos: Iterable[Hallazgo]) -> Salida:
    """Fallo de contenido con los hallazgos, que van al intento siguiente."""
    return Salida(
        Desenlace.contenido(), {"hallazgos": [h.model_dump(mode="json") for h in hallazgos]}
    )


def _plan(n: Novela, s: SalidaPlanificador) -> Iterator[Hallazgo]:
    e, plan = n.estructura, s.plan
    copiados: tuple[tuple[str, object, object], ...] = (
        ("modelo", plan.modelo, e.modelo),
        ("tipo_final", plan.tipo_final, e.desenlace.final),
        ("curva_tension", plan.curva_tension, n.formato.curva_tension),
        ("pregunta_dramatica", plan.pregunta_dramatica, n.tema.pregunta_dramatica),
        ("reparto.punto_medio", plan.reparto.punto_medio, e.nudo.punto_medio),
        ("reparto.crisis", plan.reparto.crisis, e.nudo.crisis),
        ("reparto.climax", plan.reparto.climax, e.desenlace.climax),
    )
    for campo, suyo, fijo in copiados:
        if suyo != fijo:
            yield hallazgo("B-1 · plan_del_contexto", f"plan.{campo}", suyo, f"{fijo!s}")
    inicio, fin = e.planteamiento.capitulos
    for hito in (Hito.DETONANTE, Hito.PRIMER_UMBRAL):
        capitulo = plan.reparto.capitulo(hito)
        if not inicio <= capitulo <= fin:
            yield hallazgo(
                "B-3 · hito_en_planteamiento",
                f"plan.reparto.{hito.value}",
                capitulo,
                f"un capítulo del planteamiento, del {inicio} al {fin}",
            )


def _repetidos(ids: Iterable[str]) -> list[str]:
    return [ident for ident, veces in Counter(ids).items() if veces > 1]


def _personajes(n: Novela, s: SalidaPlanificador) -> Iterator[Hallazgo]:
    suyos = {p.id: p for p in s.personajes}
    for ident in _repetidos(p.id for p in s.personajes):
        yield hallazgo("B-1 · personaje_repetido", "personajes", ident, "ids únicos")
    for fijo in n.personajes:
        p = suyos.get(fijo.id)
        if p is None:
            yield hallazgo("B-1 · personaje_del_contexto", "personajes", fijo.id, "presente")
            continue
        for campo in ("origen", "rol", "arco"):
            if getattr(p, campo) != getattr(fijo, campo):
                yield hallazgo(
                    "B-1 · personaje_del_contexto",
                    f"personajes.{p.id}.{campo}",
                    getattr(p, campo),
                    f"{getattr(fijo, campo)!r}, como en el contexto",
                )
    del_contexto = {p.id for p in n.personajes}
    pers = n.personalizacion
    destinatarios = {"destinatario": pers.destinatario}
    if pers.segundo_destinatario is not None:
        destinatarios["segundo_destinatario"] = pers.segundo_destinatario
    textos = {h.id: h.texto for h in pers.hechos}
    for p in s.personajes:
        fuente = p.origen.fuente or ""
        if p.id not in del_contexto and p.origen.tipo != "ficticio":
            yield hallazgo(
                "B-1 · personaje_nuevo_ficticio",
                f"personajes.{p.id}.origen",
                p.origen.tipo,
                "`ficticio`: los personajes reales los fija el contexto",
            )
        elif p.origen.tipo == "real":
            persona = destinatarios.get(fuente)
            if persona is not None and p.nombre != persona.nombre:
                yield hallazgo(
                    "B-4 · nombre_del_personaje_real",
                    f"personajes.{p.id}.nombre",
                    p.nombre,
                    f"el nombre de `{fuente}`",
                )
            elif persona is None and p.nombre not in textos.get(fuente, ""):
                yield hallazgo(
                    "B-4 · nombre_del_personaje_real",
                    f"personajes.{p.id}.nombre",
                    p.nombre,
                    f"un nombre que aparezca literal en el hecho `{fuente}`",
                )
        for r in p.relaciones:
            if r.destino not in suyos:
                yield hallazgo(
                    "B-4 · referencia_desconocida",
                    f"personajes.{p.id}.relaciones",
                    r.destino,
                    "el id de un personaje de la salida",
                )
    for o in s.mundo.objetos:
        if o.poseedor is not None and o.poseedor not in suyos:
            yield hallazgo(
                "B-4 · referencia_desconocida",
                f"mundo.objetos.{o.id}.poseedor",
                o.poseedor,
                "el id de un personaje de la salida",
            )


def _mundo(n: Novela, s: SalidaPlanificador) -> Iterator[Hallazgo]:
    locs = s.mundo.localizaciones
    suyas = {loc.id: loc for loc in locs}
    for ident in _repetidos(loc.id for loc in locs):
        yield hallazgo("B-1 · localizacion_repetida", "mundo.localizaciones", ident, "ids únicos")
    for fija in n.mundo.localizaciones:
        loc = suyas.get(fija.id)
        if loc is None or (loc.nivel, loc.padre) != (fija.nivel, fija.padre):
            yield hallazgo(
                "B-1 · localizacion_del_contexto",
                f"mundo.localizaciones.{fija.id}",
                "ausente" if loc is None else f"{loc.nivel.value} bajo {loc.padre}",
                f"{fija.nivel.value} bajo {fija.padre}, como en el contexto",
            )
    fijas = {loc.id for loc in n.mundo.localizaciones}
    for loc in locs:
        padre = suyas.get(loc.padre or "")
        bajo_meso = padre is not None and padre.nivel is NivelEspacial.MESO
        if loc.id not in fijas and not (loc.nivel is NivelEspacial.MICRO and bajo_meso):
            yield hallazgo(
                "B-1 · localizacion_nueva_micro",
                f"mundo.localizaciones.{loc.id}",
                f"{loc.nivel.value} bajo {loc.padre}",
                "una localización `micro` bajo una `meso`",
            )


def _estilo(n: Novela, s: SalidaPlanificador) -> Iterator[Hallazgo]:
    fijo, guia = n.lenguaje, s.estilo
    for campo in Lenguaje.model_fields:
        suyo, del_contexto = getattr(guia, campo), getattr(fijo, campo)
        if isinstance(del_contexto, tuple):
            faltan = [t for t in del_contexto if t not in suyo]
            if faltan:
                yield hallazgo(
                    "B-1 · estilo_del_contexto", f"estilo.{campo}", faltan, "lo del contexto"
                )
        elif suyo != del_contexto:
            yield hallazgo(
                "B-1 · estilo_del_contexto", f"estilo.{campo}", suyo, f"{del_contexto!r}"
            )
    if guia.metricas.proporcion_dialogo != fijo.dialogo.proporcion:
        yield hallazgo(
            "B-1 · estilo_del_contexto",
            "estilo.metricas.proporcion_dialogo",
            guia.metricas.proporcion_dialogo,
            f"{fijo.dialogo.proporcion}, la de `lenguaje.dialogo`",
        )
    faltan = [t for t in fijo.prohibidas if t not in guia.lista_negra]
    if faltan:
        yield hallazgo(
            "B-4 · lista_negra_sin_prohibidas",
            "estilo.lista_negra",
            faltan,
            "todas las de `lenguaje.prohibidas`",
        )


def contradicciones(novela: Novela, salida: SalidaPlanificador) -> list[Hallazgo]:
    """B-1, B-3 y B-4: lo que la salida contradice del contexto validado."""
    reglas = (_plan, _personajes, _mundo, _estilo)
    return [h for regla in reglas for h in regla(novela, salida)]


def registrar_planificacion(conexion: sqlite3.Connection, resultado: object) -> Salida:
    """RF-77a y B-1: valida la salida del planificador y, si vale, la guarda con su siembra."""
    try:
        salida = SalidaPlanificador.model_validate(resultado)
    except ValidationError as error:
        return Salida(Desenlace.forma(), {"errores": errores_de_forma(error)})
    vigente = contexto_vigente(conexion)
    if vigente is None:
        return rechazo(
            [hallazgo("B-1 · sin_contexto", "(raíz)", "sin contexto", "un contexto validado")]
        )
    hallazgos = contradicciones(vigente[1].novela, salida)
    if hallazgos:
        return rechazo(hallazgos)
    try:
        guardar_planificacion(conexion, salida)
    except SalidaIncoherente as error:
        return rechazo(
            [hallazgo("RF-77a · incoherente_con_la_base", "(raíz)", str(error), "sin choques")]
        )
    return Salida(Desenlace.aceptado())


def _planificador(contexto: ContextoManejo, resultado: object) -> Salida:
    return registrar_planificacion(contexto.conexion, resultado)


MANEJADORES: Mapping[Agente, Manejador] = {Agente.PLANIFICADOR: _planificador}
