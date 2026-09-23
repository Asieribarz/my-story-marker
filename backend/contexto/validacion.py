"""Validación del objeto de contexto: devuelve un informe, nunca una excepción (RF-21).

Tres pasadas, en este orden:
1. Valores por defecto derivables (RF-26), que el informe declara uno a uno: rellenar en
   silencio es la versión amable del truncado silencioso.
2. Tipos y valores permitidos, con los modelos de `modelos.py` (RF-20, RF-23, RF-27).
3. Reglas de coherencia entre campos (RF-24, RF-25 y la integridad de estructura,
   personajes y mundo). Cada regla es una función que devuelve sus hallazgos, así que el
   informe las recoge todas en vez de pararse en la primera.

Todo hallazgo es bloqueante: el proyecto no sale de `contexto` con uno (RF-22).
"""

import copy
from collections import Counter
from collections.abc import Callable, Iterator
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from backend.contexto.modelos import (
    VERSION_ONTOLOGIA,
    Arco,
    Contexto,
    Destinatario,
    NivelEspacial,
    Novela,
    Ocasion,
    Papel,
    Prioridad,
    Publico,
    Rol,
    TipoFinal,
    TipoHecho,
    TipoMundo,
    Tono,
    es_fecha,
)
from backend.shared.tipos import Hallazgo, Severidad

VERIFICADOR = "esquema"
MAX_OBLIGATORIOS = 5
_MAX_EVIDENCIA = 200

# (ruta, valor): se rellena si falta la clave y existe el objeto que la contiene.
DEFECTOS: tuple[tuple[tuple[str, ...], object], ...] = (
    (("novela", "estructura", "modelo"), "tres_actos"),
    (("novela", "estructura", "planteamiento", "porcentaje"), 22),
    (("novela", "estructura", "nudo", "porcentaje"), 55),
    (("novela", "estructura", "desenlace", "porcentaje"), 23),
    (("novela", "lenguaje", "tiempo"), "preterito"),
    (("novela", "personalizacion", "destinatario", "papel"), Papel.PROTAGONISTA.value),
    (("novela", "personalizacion", "segundo_destinatario", "papel"), Papel.COPROTAGONISTA.value),
)


class InformeContexto(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version_ontologia: str = VERSION_ONTOLOGIA
    hallazgos: tuple[Hallazgo, ...] = ()
    rellenados: tuple[str, ...] = ()
    contexto: Contexto | None = None

    @property
    def valido(self) -> bool:
        return self.contexto is not None and not self.hallazgos


def puede_salir_de_contexto(informe: InformeContexto) -> bool:
    """RF-22: la guarda de la transición `contexto` → `planificacion` (V-20)."""
    return informe.valido and not any(
        h.severidad is Severidad.BLOQUEANTE for h in informe.hallazgos
    )


def _hallazgo(regla: str, localizacion: str, evidencia: object, esperado: str) -> Hallazgo:
    texto = evidencia if isinstance(evidencia, str) else repr(evidencia)
    return Hallazgo(
        verificador=VERIFICADOR,
        severidad=Severidad.BLOQUEANTE,
        regla=regla,
        localizacion=localizacion,
        evidencia=texto[:_MAX_EVIDENCIA],
        esperado=esperado,
    )


def _rellenar_defectos(datos: dict[str, Any]) -> list[str]:
    rellenados = []
    for ruta, valor in DEFECTOS:
        contenedor: Any = datos
        for clave in ruta[:-1]:
            contenedor = contenedor.get(clave) if isinstance(contenedor, dict) else None
        if isinstance(contenedor, dict) and ruta[-1] not in contenedor:
            contenedor[ruta[-1]] = valor
            rellenados.append(".".join(ruta))
    return rellenados


def _hallazgos_de_tipo(error: ValidationError) -> list[Hallazgo]:
    return [
        _hallazgo(
            regla="RF-23 · " + detalle["type"],
            localizacion=".".join(str(parte) for parte in detalle["loc"]) or "(raíz)",
            evidencia=detalle.get("input"),
            esperado=detalle["msg"],
        )
        for detalle in error.errors(include_url=False)
    ]


# ─── Reglas de coherencia ────────────────────────────────────────────────────

Regla = Callable[[Novela, date], Iterator[Hallazgo]]
_REGLAS: list[Regla] = []


def regla(funcion: Regla) -> Regla:
    _REGLAS.append(funcion)
    return funcion


_RANGO_PUBLICO = {Publico.INFANTIL: 0, Publico.JUVENIL: 1, Publico.ADULTO: 2}


def publico_por_edad(edad: int) -> Publico:
    """definitions.md §2: infantil <12, juvenil 12-17, adulto ≥18."""
    if edad < 12:
        return Publico.INFANTIL
    if edad < 18:
        return Publico.JUVENIL
    return Publico.ADULTO


@regla
def _publico_segun_edad_del_lector(n: Novela, hoy: date) -> Iterator[Hallazgo]:
    """RF-24: el entrevistador puede bajar el público, nunca subirlo sobre la edad."""
    edad = n.personalizacion.edad_lector
    derivado = publico_por_edad(edad)
    if n.publico is Publico.CROSSOVER:
        if derivado is Publico.INFANTIL:
            yield _hallazgo(
                "RF-24 · publico_por_edad",
                "novela.publico",
                f"crossover con lector de {edad} años",
                "crossover solo para lectores de 12 años o más",
            )
    elif _RANGO_PUBLICO[n.publico] > _RANGO_PUBLICO[derivado]:
        yield _hallazgo(
            "RF-24 · publico_por_edad",
            "novela.publico",
            f"{n.publico.value} con lector de {edad} años",
            f"{derivado.value} o un público más joven",
        )


@regla
def _contenido_segun_publico(n: Novela, hoy: date) -> Iterator[Hallazgo]:
    """RF-25: infantil ≤1 por categoría; el tope de 2 para el resto lo fija el tipo."""
    if n.publico is not Publico.INFANTIL:
        return
    for categoria, nivel in n.tipo_aventura.contenido.model_dump().items():
        if nivel > 1:
            yield _hallazgo(
                "RF-25 · contenido_por_publico",
                f"novela.tipo_aventura.contenido.{categoria}",
                nivel,
                "≤1 para público infantil",
            )


@regla
def _tono_segun_edad_del_lector(n: Novela, hoy: date) -> Iterator[Hallazgo]:
    """definitions.md §10: un lector infantil con tono `melancolico` es una contradicción."""
    infantil = publico_por_edad(n.personalizacion.edad_lector) is Publico.INFANTIL
    if infantil and n.tono is Tono.MELANCOLICO:
        yield _hallazgo(
            "RF-24 · tono_por_edad",
            "novela.tono",
            n.tono.value,
            "un tono distinto de `melancolico` para un lector menor de 12 años",
        )


@regla
def _final_segun_ocasion(n: Novela, hoy: date) -> Iterator[Hallazgo]:
    """definitions.md §10: una `boda` o una `jubilacion` no admiten final `agridulce`."""
    ocasion = n.personalizacion.ocasion
    final = n.estructura.desenlace.final
    if ocasion in (Ocasion.BODA, Ocasion.JUBILACION) and final is TipoFinal.AGRIDULCE:
        yield _hallazgo(
            "RF-24 · final_por_ocasion",
            "novela.estructura.desenlace.final",
            f"{final.value} en una {ocasion.value}",
            "un final distinto de `agridulce`",
        )


def _edad_en(nacimiento: date, dia: date) -> int:
    return dia.year - nacimiento.year - ((dia.month, dia.day) < (nacimiento.month, nacimiento.day))


def _destinatarios(n: Novela) -> Iterator[tuple[str, Destinatario]]:
    base = "novela.personalizacion"
    yield f"{base}.destinatario", n.personalizacion.destinatario
    if n.personalizacion.segundo_destinatario is not None:
        yield f"{base}.segundo_destinatario", n.personalizacion.segundo_destinatario


@regla
def _edad_frente_a_nacimiento(n: Novela, hoy: date) -> Iterator[Hallazgo]:
    """definitions.md §10. Se admite la edad que cumple: el regalo suele ser de cumpleaños."""
    for ruta, persona in _destinatarios(n):
        nacimiento = persona.fecha_nacimiento
        if nacimiento is None:
            continue
        if nacimiento > hoy:
            yield _hallazgo(
                "RF-24 · edad_frente_a_nacimiento",
                f"{ruta}.fecha_nacimiento",
                nacimiento.isoformat(),
                f"una fecha no posterior a {hoy.isoformat()}",
            )
            continue
        cumplida = _edad_en(nacimiento, hoy)
        if persona.edad is not None and persona.edad not in (cumplida, cumplida + 1):
            yield _hallazgo(
                "RF-24 · edad_frente_a_nacimiento",
                f"{ruta}.edad",
                persona.edad,
                f"{cumplida} o {cumplida + 1} según la fecha de nacimiento",
            )


@regla
def _eventos_tras_el_nacimiento(n: Novela, hoy: date) -> Iterator[Hallazgo]:
    """definitions.md §10: no hay recuerdos anteriores a nacer. Solo eventos con fecha."""
    nacimiento = n.personalizacion.destinatario.fecha_nacimiento
    if nacimiento is None:
        return
    for i, hecho in enumerate(n.personalizacion.hechos):
        if hecho.tipo is TipoHecho.EVENTO and hecho.momento and es_fecha(hecho.momento):
            if hecho.momento < nacimiento.isoformat()[: len(hecho.momento)]:
                yield _hallazgo(
                    "RF-24 · evento_antes_de_nacer",
                    f"novela.personalizacion.hechos.{i}.momento",
                    hecho.momento,
                    f"un momento no anterior a {nacimiento.isoformat()}",
                )


@regla
def _hechos(n: Novela, hoy: date) -> Iterator[Hallazgo]:
    """definitions.md §9: ids únicos, eventos con momento y lugar, a lo sumo 5 obligatorios."""
    base = "novela.personalizacion.hechos"
    hechos = n.personalizacion.hechos
    for hid, veces in Counter(h.id for h in hechos).items():
        if veces > 1:
            yield _hallazgo("hecho_id_unico", base, hid, "ids de hecho únicos")
    lugares = {loc.id for loc in n.mundo.localizaciones}
    for i, hecho in enumerate(hechos):
        if hecho.tipo is not TipoHecho.EVENTO:
            continue
        if not hecho.momento or not hecho.lugar:
            yield _hallazgo(
                "evento_con_momento_y_lugar",
                f"{base}.{i}",
                hecho.id,
                "un `evento` lleva `momento` y `lugar`",
            )
        elif hecho.lugar not in lugares:
            yield _hallazgo(
                "evento_en_localizacion",
                f"{base}.{i}.lugar",
                hecho.lugar,
                "el id de una localización del mundo: todo evento necesita un lugar",
            )
    obligatorios = sum(h.prioridad is Prioridad.OBLIGATORIO for h in hechos)
    if obligatorios > MAX_OBLIGATORIOS:
        yield _hallazgo(
            "hechos_obligatorios",
            base,
            f"{obligatorios} obligatorios",
            f"a lo sumo {MAX_OBLIGATORIOS}; el resto, `deseable`",
        )


@regla
def _subgeneros(n: Novela, hoy: date) -> Iterator[Hallazgo]:
    s = n.tipo_aventura.subgenero
    if s.primario in s.secundarios or len(set(s.secundarios)) != len(s.secundarios):
        yield _hallazgo(
            "subgeneros_distintos",
            "novela.tipo_aventura.subgenero.secundarios",
            [x.value for x in s.secundarios],
            "hasta dos secundarios, distintos entre sí y del primario",
        )


@regla
def _estructura(n: Novela, hoy: date) -> Iterator[Hallazgo]:
    """Los tres tramos cubren los 10 capítulos, contiguos, con cada hito dentro del suyo."""
    e = n.estructura
    tramos = (
        ("planteamiento", e.planteamiento.capitulos),
        ("nudo", e.nudo.capitulos),
        ("desenlace", e.desenlace.capitulos),
    )
    esperado_inicio = 1
    for nombre, (inicio, fin) in tramos:
        if inicio != esperado_inicio or fin < inicio:
            yield _hallazgo(
                "estructura_tramos",
                f"novela.estructura.{nombre}.capitulos",
                [inicio, fin],
                f"un tramo que empiece en el capítulo {esperado_inicio}",
            )
        esperado_inicio = fin + 1
    if esperado_inicio != 11:
        yield _hallazgo(
            "estructura_tramos",
            "novela.estructura.desenlace.capitulos",
            e.desenlace.capitulos,
            "que el desenlace termine en el capítulo 10",
        )
    hitos = (
        ("nudo.punto_medio", e.nudo.punto_medio, e.nudo.capitulos),
        ("nudo.crisis", e.nudo.crisis, e.nudo.capitulos),
        ("desenlace.climax", e.desenlace.climax, e.desenlace.capitulos),
    )
    for ruta, capitulo, (inicio, fin) in hitos:
        if not inicio <= capitulo <= fin:
            yield _hallazgo(
                "estructura_hitos",
                f"novela.estructura.{ruta}",
                capitulo,
                f"un capítulo entre {inicio} y {fin}",
            )
    suma = e.planteamiento.porcentaje + e.nudo.porcentaje + e.desenlace.porcentaje
    if suma != 100:
        yield _hallazgo(
            "estructura_porcentajes",
            "novela.estructura",
            f"suman {suma}",
            "porcentajes de acto que sumen 100",
        )


@regla
def _personajes(n: Novela, hoy: date) -> Iterator[Hallazgo]:
    """definitions.md §4: origen real con fuente válida y el destinatario en la novela."""
    base = "novela.personajes"
    personajes = n.personajes
    for pid, veces in Counter(p.id for p in personajes).items():
        if veces > 1:
            yield _hallazgo("personaje_id_unico", base, pid, "ids de personaje únicos")

    seres_queridos = {h.id for h in n.personalizacion.hechos if h.tipo is TipoHecho.SER_QUERIDO}
    fuentes_validas = {"destinatario"} | seres_queridos
    if n.personalizacion.segundo_destinatario is not None:
        fuentes_validas.add("segundo_destinatario")
    for i, p in enumerate(personajes):
        fuente = p.origen.fuente
        if p.origen.tipo == "real" and fuente not in fuentes_validas:
            yield _hallazgo(
                "personaje_real_con_fuente",
                f"{base}.{i}.origen.fuente",
                fuente,
                "`destinatario`, `segundo_destinatario` o el id de un hecho `ser_querido`",
            )
        if p.origen.tipo == "ficticio" and fuente is not None:
            yield _hallazgo(
                "personaje_ficticio_sin_fuente",
                f"{base}.{i}.origen.fuente",
                fuente,
                "sin fuente: un personaje ficticio no viene de un dato aportado",
            )

    for fuente, persona in (
        ("destinatario", n.personalizacion.destinatario),
        ("segundo_destinatario", n.personalizacion.segundo_destinatario),
    ):
        if persona is None:
            continue
        suyos = [(i, p) for i, p in enumerate(personajes) if p.origen.fuente == fuente]
        if len(suyos) != 1:
            yield _hallazgo(
                "destinatario_en_la_novela",
                base,
                f"{len(suyos)} personajes con fuente `{fuente}`",
                f"exactamente un personaje con fuente `{fuente}`",
            )
            continue
        i, p = suyos[0]
        if p.arco not in (Arco.POSITIVO, Arco.PLANO):
            yield _hallazgo(
                "arco_del_destinatario",
                f"{base}.{i}.arco",
                p.arco.value,
                "`positivo` o `plano`: el arco del destinatario no puede leerse como reproche",
            )
        if persona.papel is Papel.PROTAGONISTA and Rol.PROTAGONISTA not in p.rol:
            yield _hallazgo(
                "papel_del_destinatario",
                f"{base}.{i}.rol",
                [r.value for r in p.rol],
                "el rol `protagonista`, que es el papel del destinatario",
            )


_PADRE_ESPERADO = {NivelEspacial.MESO: NivelEspacial.MACRO, NivelEspacial.MICRO: NivelEspacial.MESO}
_MUNDOS_REALISTAS = (TipoMundo.REAL_HISTORICO, TipoMundo.CONTEMPORANEO)


@regla
def _mundo(n: Novela, hoy: date) -> Iterator[Hallazgo]:
    """definitions.md §5: árbol macro → meso → micro, ruta sobre él, reglas solo si no realista."""
    base = "novela.mundo"
    locs = n.mundo.localizaciones
    for lid, veces in Counter(loc.id for loc in locs).items():
        if veces > 1:
            yield _hallazgo("localizacion_id_unico", f"{base}.localizaciones", lid, "ids únicos")
    nivel_de = {loc.id: loc.nivel for loc in locs}
    for i, loc in enumerate(locs):
        esperado = _PADRE_ESPERADO.get(loc.nivel)
        if esperado is None:
            if loc.padre is not None:
                yield _hallazgo(
                    "arbol_de_localizaciones",
                    f"{base}.localizaciones.{i}.padre",
                    loc.padre,
                    "una localización `macro` no tiene padre",
                )
        elif nivel_de.get(loc.padre or "") is not esperado:
            yield _hallazgo(
                "arbol_de_localizaciones",
                f"{base}.localizaciones.{i}.padre",
                loc.padre,
                f"el id de una localización `{esperado.value}`",
            )
    for i, etapa in enumerate(n.mundo.ruta):
        if etapa.id not in nivel_de:
            yield _hallazgo(
                "ruta_sobre_localizaciones",
                f"{base}.ruta.{i}.id",
                etapa.id,
                "el id de una localización del mundo",
            )
    if n.mundo.tipo in _MUNDOS_REALISTAS and n.mundo.reglas:
        yield _hallazgo(
            "reglas_solo_en_mundos_no_realistas",
            f"{base}.reglas",
            f"{len(n.mundo.reglas)} reglas en un mundo {n.mundo.tipo.value}",
            "sin reglas del mundo en `real_historico` o `contemporaneo`",
        )


REGLAS: tuple[Regla, ...] = tuple(_REGLAS)


def validar(datos: object, hoy: date) -> InformeContexto:
    """Valida una instancia de contexto. `hoy` se inyecta para que el resultado sea
    determinista: la edad frente a la fecha de nacimiento depende del día."""
    if not isinstance(datos, dict):
        return InformeContexto(
            hallazgos=(_hallazgo("RF-23 · raiz", "(raíz)", type(datos).__name__, "un objeto"),)
        )
    copia = copy.deepcopy(datos)
    rellenados = tuple(_rellenar_defectos(copia))
    try:
        contexto = Contexto.model_validate(copia)
    except ValidationError as error:
        return InformeContexto(hallazgos=tuple(_hallazgos_de_tipo(error)), rellenados=rellenados)
    hallazgos = tuple(h for r in REGLAS for h in r(contexto.novela, hoy))
    return InformeContexto(
        hallazgos=hallazgos,
        rellenados=rellenados,
        contexto=None if hallazgos else contexto,
    )
