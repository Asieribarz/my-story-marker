"""Verificadores deterministas de capítulo (spec1 §4.6.3, architecture §4).

Todos tienen la misma firma, `(cuerpo, vista) -> Informe` (resolución 15 de §3): el cuerpo
es el Markdown del capítulo sin el título, y la vista reúne contexto, ficha, guía, biblia a
fecha N−1 y listas. Devuelven un informe con severidad y localización y **nunca corrigen**
(RN-6). No hay verificador de Repeticiones (R-3) ni de continuidad sobre el texto (R-2).
"""

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

from backend.capitulo.biblia import ReferenciaDesconocida, Termino, glosario_a_fecha
from backend.capitulo.verificadores import lexico, medidas, nombres
from backend.contexto.modelos import Novela
from backend.contexto.persistencia import contexto_vigente
from backend.escaleta.consultas import leer_ficha
from backend.escaleta.modelos import FichaCapitulo
from backend.planificacion.consultas import leer_guia
from backend.planificacion.modelos import GuiaEstilo
from backend.shared.tipos import Informe


@dataclass(frozen=True)
class Vista:
    numero: int
    novela: Novela
    ficha: FichaCapitulo
    guia: GuiaEstilo
    glosario: tuple[Termino, ...]
    prohibidas: tuple[lexico.Prohibida, ...]
    # (id, texto) de los hechos `frase` que la ficha asigna al capítulo (RF-73a).
    frases: tuple[tuple[str, str], ...]

    @property
    def tolerancia(self) -> int:
        propia = self.novela.formato.tolerancia
        return medidas.TOLERANCIA_POR_DEFECTO if propia is None else propia


def vista_de(conexion: sqlite3.Connection, numero: int, momento: str) -> Vista:
    """La vista del capítulo `numero`. Copia antes las listas del guardarraíl si el proyecto
    aún no las tiene (B-12). Sin contexto, ficha o guía, `ReferenciaDesconocida`."""
    vigente = contexto_vigente(conexion)
    ficha = leer_ficha(conexion, numero)
    guia = leer_guia(conexion)
    if vigente is None:
        raise ReferenciaDesconocida("contexto", "vigente")
    if ficha is None or guia is None:
        raise ReferenciaDesconocida("ficha", str(numero))
    novela = vigente[1].novela
    lexico.asegurar_listas(conexion, novela.publico, momento)
    marcas = ",".join("?" * len(ficha.hechos))
    filas = conexion.execute(
        f"SELECT id, texto FROM hecho WHERE tipo = 'frase' AND id IN ({marcas}) ORDER BY id",
        ficha.hechos,
    ).fetchall()
    return Vista(
        numero=numero,
        novela=novela,
        ficha=ficha,
        guia=guia,
        glosario=glosario_a_fecha(conexion, numero),
        prohibidas=lexico.prohibidas(conexion, novela.publico),
        frases=tuple((f["id"], f["texto"]) for f in filas),
    )


def longitud(cuerpo: str, vista: Vista) -> Informe:
    rango = vista.novela.formato.longitud_capitulo
    return medidas.longitud(
        cuerpo, rango.min, rango.max, vista.ficha.palabras_objetivo, vista.tolerancia
    )


def metricas(cuerpo: str, vista: Vista) -> Informe:
    m = vista.guia.metricas
    minimo = max(m.legibilidad_min, medidas.UMBRAL_DE_LEGIBILIDAD[vista.novela.publico])
    return medidas.metricas(
        cuerpo,
        frase_media=m.frase_media_palabras,
        proporcion_dialogo=m.proporcion_dialogo,
        legibilidad_min=minimo,
        convencion=vista.guia.dialogo.convencion,
        tolerancia=vista.tolerancia,
    )


def lista_negra(cuerpo: str, vista: Vista) -> Informe:
    return lexico.lista_negra(cuerpo, tuple(dict.fromkeys(vista.guia.lista_negra)))


def guardarrail(cuerpo: str, vista: Vista) -> Informe:
    return lexico.guardarrail(cuerpo, vista.prohibidas)


def grafia(cuerpo: str, vista: Vista) -> Informe:
    return nombres.grafia(cuerpo, vista.glosario)


def frases_literales(cuerpo: str, vista: Vista) -> Informe:
    return nombres.frases_literales(cuerpo, vista.frases)


Verificador = Callable[[str, Vista], Informe]

VERIFICADORES: tuple[Verificador, ...] = (
    guardarrail,
    frases_literales,
    longitud,
    metricas,
    lista_negra,
    grafia,
)


def ejecutar(cuerpo: str, vista: Vista) -> tuple[Informe, ...]:
    """RF-77: todos, siempre, en el mismo orden."""
    return tuple(verificador(cuerpo, vista) for verificador in VERIFICADORES)
