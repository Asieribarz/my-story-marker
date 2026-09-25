"""Manejador de `escaletista` (RF-40 a RF-43, RF-77a, B-5, B-9, B-16).

Lo agrega `proyecto/manejadores.py`. Como en el planificador, a la primera que falla no se
persiste nada: el esquema (`SalidaEscaletista`, fallo de forma); después las reglas contra el
contexto y el plan (fallo de contenido con hallazgos bloqueantes):

- RF-41: una ficha por capítulo y, en cada acto, un número de capítulos que difiere de
  10·p/100 en menos de 1.
- RF-42: cada hito del catálogo en exactamente una ficha, la que le da el reparto del plan.
- RF-43: todo lo que se planta se cobra una sola vez y más tarde.
- B-5: `tension` y `cierre` son los del contexto, y los traspasos son de objetos del mundo.

Por último se guarda (`guardar_escaleta`, que crea los presagios `previstos` de B-16) y se
pasa B-9 sobre las fichas guardadas, como lo hará el Recuperador; si hay hallazgos, se
deshace. Un hecho obligatorio que no usa ninguna ficha no rechaza la salida: es un aviso.
"""

import sqlite3
from collections.abc import Iterator, Mapping, Sequence

from pydantic import ValidationError

from backend.capitulo.biblia import continuidad_antes_de_escribir
from backend.contexto.modelos import Cierre, Novela, Prioridad
from backend.contexto.persistencia import contexto_vigente
from backend.escaleta.consultas import guardar_escaleta
from backend.escaleta.modelos import SalidaEscaletista
from backend.planificacion.consultas import SalidaIncoherente, leer_planificacion
from backend.planificacion.manejadores import errores_de_forma, hallazgo, rechazo
from backend.planificacion.modelos import SalidaPlanificador
from backend.proyecto.manejadores import ContextoManejo, Manejador, Salida
from backend.proyecto.maquina import Desenlace
from backend.shared.db import transaccion
from backend.shared.tipos import Agente, Hallazgo, Hito, Severidad


class _Discontinua(Exception):
    """B-9 falla sobre las fichas guardadas: deshace la escritura."""

    def __init__(self, hallazgos: Sequence[Hallazgo]) -> None:
        super().__init__(f"{len(hallazgos)} hallazgos de continuidad")
        self.hallazgos = hallazgos


def _fichas_y_actos(n: Novela, s: SalidaEscaletista) -> Iterator[Hallazgo]:
    total = n.formato.capitulos
    numeros = sorted(f.numero for f in s.fichas)
    if numeros != list(range(1, total + 1)):
        yield hallazgo(
            "RF-41 · numero_de_fichas", "fichas", numeros, f"una ficha por capítulo, 1 a {total}"
        )
    e = n.estructura
    for nombre, acto in (
        ("planteamiento", e.planteamiento),
        ("nudo", e.nudo),
        ("desenlace", e.desenlace),
    ):
        inicio, fin = acto.capitulos
        cuantos = sum(1 for f in s.fichas if inicio <= f.numero <= fin)
        previsto = total * acto.porcentaje / 100
        if abs(cuantos - previsto) >= 1:
            yield hallazgo(
                "RF-41 · reparto_por_actos",
                f"estructura.{nombre}",
                f"{cuantos} capítulos",
                f"{previsto:g} capítulos ({acto.porcentaje} %), con diferencia menor que 1",
            )


def _hitos(p: SalidaPlanificador, s: SalidaEscaletista) -> Iterator[Hallazgo]:
    for hito in Hito:
        previsto = p.plan.reparto.capitulo(hito)
        donde = [f.numero for f in s.fichas for suyo in f.hitos if suyo is hito]
        if not donde:
            yield hallazgo("RF-42 · hito_ausente", "fichas", hito.value, f"en la ficha {previsto}")
        elif len(donde) > 1:
            yield hallazgo(
                "RF-42 · hito_duplicado",
                "fichas",
                f"{hito.value} en las fichas {donde}",
                "en exactamente una ficha",
            )
        elif donde[0] != previsto:
            yield hallazgo(
                "RF-42 · hito_fuera_del_plan",
                f"ficha {donde[0]}",
                hito.value,
                f"en la ficha {previsto}, la del reparto del plan",
            )


def _presagios(s: SalidaEscaletista) -> Iterator[Hallazgo]:
    plantados: dict[str, int] = {}
    cobros: dict[str, list[int]] = {}
    for f in s.fichas:
        for presagio in f.plantar:
            plantados.setdefault(presagio.clave, f.numero)
        for clave in f.cobrar:
            cobros.setdefault(clave, []).append(f.numero)
    for clave, numero in plantados.items():
        if not any(m > numero for m in cobros.get(clave, [])):
            yield hallazgo(
                "RF-43 · presagio_sin_cobro",
                f"ficha {numero}",
                clave,
                "una ficha posterior que lo cobre",
            )
    for clave, donde in cobros.items():
        if clave not in plantados or len(donde) > 1 or donde[0] <= plantados[clave]:
            yield hallazgo(
                "RF-43 · cobro_incoherente",
                f"ficha {donde[0]}",
                f"{clave} cobrado en las fichas {donde}",
                "un solo cobro, posterior a la ficha que lo planta",
            )


def _segun_contexto(n: Novela, p: SalidaPlanificador, s: SalidaEscaletista) -> Iterator[Hallazgo]:
    curva, cierres = n.formato.curva_tension, n.formato.cierre_capitulo
    objetos = {o.id for o in p.mundo.objetos}
    personajes = {x.id for x in p.personajes}
    for f in s.fichas:
        tension = curva[f.numero - 1]
        cierre = cierres if isinstance(cierres, Cierre) else cierres[f.numero - 1]
        if f.tension != tension:
            yield hallazgo(
                "B-5 · tension_del_contexto", f"ficha {f.numero}", f.tension, f"{tension}"
            )
        if f.cierre is not cierre:
            yield hallazgo("B-5 · cierre_del_contexto", f"ficha {f.numero}", f.cierre, cierre.value)
        for t in f.traspasos:
            if t.objeto not in objetos or (t.a is not None and t.a not in personajes):
                yield hallazgo(
                    "B-5 · traspaso_desconocido",
                    f"ficha {f.numero}",
                    f"{t.objeto} → {t.a}",
                    "un objeto del mundo que pasa a un personaje del plan, o a nadie",
                )


def incoherencias(
    novela: Novela, planificacion: SalidaPlanificador, salida: SalidaEscaletista
) -> list[Hallazgo]:
    """RF-41, RF-42, RF-43 y B-5: lo que la escaleta contradice del contexto o del plan."""
    return [
        *_fichas_y_actos(novela, salida),
        *_hitos(planificacion, salida),
        *_presagios(salida),
        *_segun_contexto(novela, planificacion, salida),
    ]


def hechos_sin_ficha(novela: Novela, salida: SalidaEscaletista) -> list[Hallazgo]:
    """B-5: aviso por cada hecho obligatorio que no usa ninguna ficha."""
    usados = {h for f in salida.fichas for h in f.hechos}
    return [
        hallazgo(
            "B-5 · hecho_obligatorio_sin_ficha",
            "fichas",
            h.id,
            "en la ficha de algún capítulo",
            Severidad.MEDIA,
        )
        for h in novela.personalizacion.hechos
        if h.prioridad is Prioridad.OBLIGATORIO and h.id not in usados
    ]


def registrar_escaleta(conexion: sqlite3.Connection, resultado: object) -> Salida:
    """RF-40 y RF-77a: valida la escaleta y, si vale, la guarda con sus presagios previstos."""
    try:
        salida = SalidaEscaletista.model_validate(resultado)
    except ValidationError as error:
        return Salida(Desenlace.forma(), {"errores": errores_de_forma(error)})
    vigente, planificacion = contexto_vigente(conexion), leer_planificacion(conexion)
    if vigente is None or planificacion is None:
        return rechazo([hallazgo("RF-40 · sin_plan", "(raíz)", "sin plan", "el plan guardado")])
    novela = vigente[1].novela
    hallazgos = incoherencias(novela, planificacion, salida)
    if hallazgos:
        return rechazo(hallazgos)
    try:
        with transaccion(conexion):
            guardar_escaleta(conexion, salida)
            continuidad = [
                h for f in salida.fichas for h in continuidad_antes_de_escribir(conexion, f.numero)
            ]
            if continuidad:
                raise _Discontinua(continuidad)
    except SalidaIncoherente as error:
        return rechazo(
            [hallazgo("RF-77a · incoherente_con_la_base", "(raíz)", str(error), "sin choques")]
        )
    except _Discontinua as error:
        return rechazo(error.hallazgos)
    avisos = hechos_sin_ficha(novela, salida)
    return Salida(Desenlace.aceptado(), {"avisos": [h.model_dump(mode="json") for h in avisos]})


def _escaletista(contexto: ContextoManejo, resultado: object) -> Salida:
    return registrar_escaleta(contexto.conexion, resultado)


MANEJADORES: Mapping[Agente, Manejador] = {Agente.ESCALETISTA: _escaletista}
