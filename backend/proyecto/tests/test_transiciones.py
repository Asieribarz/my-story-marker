"""RF-04, RF-05, RF-05a, RN-3: la tabla de transiciones como dato.

Las paradas humanas se hacen cumplir con la ausencia de aristas automáticas; estas pruebas
lo comprueban sobre la tabla y la cotejan con el diagrama de architecture.md §3.1.
"""

import re
from pathlib import Path

import pytest

from backend.proyecto.errores import TransicionInvalida
from backend.proyecto.transiciones import (
    DESTINO_DE_REINTENTAR,
    ORIGENES_DE_DETENIDA,
    PARADAS_HUMANAS,
    TRANSICIONES,
    Causa,
    arista,
    salidas,
)
from backend.shared.tipos import EstadoProyecto as E

ARQUITECTURA = Path(__file__).resolve().parents[3] / "docs" / "architecture.md"


def test_las_paradas_humanas_no_tienen_salida_automatica() -> None:
    for parada in PARADAS_HUMANAS:
        assert salidas(parada), parada
        assert all(a.humana for a in salidas(parada)), parada


def test_cambio_solicitado_sale_sin_humano_por_el_tope_del_interprete_o_el_worker() -> None:
    automaticas = [a for a in salidas(E.CAMBIO_SOLICITADO) if not a.humana]
    assert [(a.destino, a.causa) for a in automaticas] == [
        (E.PUBLICADA, Causa.TOPE_AGOTADO),
        (E.PUBLICADA, Causa.WORKER_FALLIDO),
    ]


def test_las_aristas_humanas_solo_salen_de_paradas() -> None:
    origenes = {a.origen for a in TRANSICIONES if a.humana}
    assert origenes == PARADAS_HUMANAS | {E.CAMBIO_SOLICITADO}


def test_reintentar_cubre_todo_origen_de_detenida() -> None:
    assert set(DESTINO_DE_REINTENTAR) == ORIGENES_DE_DETENIDA
    for destino in DESTINO_DE_REINTENTAR.values():
        assert arista(E.DETENIDA, destino, Causa.REINTENTAR).humana
    assert DESTINO_DE_REINTENTAR[E.VERIFICACION_MANUSCRITO] is E.CAPITULOS


def test_no_hay_aristas_repetidas() -> None:
    assert len(set(TRANSICIONES)) == len(TRANSICIONES)


def test_una_arista_que_no_esta_se_rechaza() -> None:
    with pytest.raises(TransicionInvalida, match="intake a publicada"):
        arista(E.INTAKE, E.PUBLICADA, Causa.VERSION_PUBLICADA)
    with pytest.raises(TransicionInvalida):
        arista(E.APROBACION_PLAN, E.ESCALETA, Causa.PLAN_COMPLETO)


def test_todo_estado_es_alcanzable_desde_intake() -> None:
    alcanzados = {E.INTAKE}
    frontera = [E.INTAKE]
    while frontera:
        for a in salidas(frontera.pop()):
            if a.destino not in alcanzados:
                alcanzados.add(a.destino)
                frontera.append(a.destino)
    assert alcanzados == set(E)


def _aristas_del_diagrama() -> set[tuple[E, E]]:
    texto = ARQUITECTURA.read_text(encoding="utf-8")
    inicio = texto.index("### 3.1 El grafo de estados")
    bloque = texto[inicio:].split("```mermaid", 1)[1].split("```", 1)[0]
    nombres = {
        identificador: E(etiqueta)
        for identificador, etiqueta in re.findall(r"(\w+)[\[{]\"([a-z_]+)", bloque)
    }
    pares = re.findall(r"^\s*(\w+)\S*\s*-->(?:\|[^|]*\|)?\s*(\w+)", bloque, flags=re.MULTILINE)
    return {(nombres[origen], nombres[destino]) for origen, destino in pares}


def test_toda_arista_del_diagrama_esta_en_la_tabla() -> None:
    del_diagrama = _aristas_del_diagrama()
    assert len(del_diagrama) > 20
    en_la_tabla = {(a.origen, a.destino) for a in TRANSICIONES}
    assert del_diagrama - en_la_tabla == set()


# Pares de Q6 que la tabla ya tiene y el diagrama de §3.1 todavía no dibuja: el tope agotado
# desde cada fase con agente (a `detenida`; en una regeneración, `revision` a `publicada`) y
# «reintentar» de vuelta a esas fases. Cuando architecture.md §3.1 los recoja, este conjunto
# se vacía y la prueba de abajo queda en tabla igual a diagrama (RF-04).
_Q6_AUN_SIN_DIAGRAMA = {
    *((origen, E.DETENIDA) for origen in (E.INTAKE, E.CONTEXTO, E.PLANIFICACION, E.ESCALETA)),
    (E.REVISION, E.DETENIDA),
    (E.PUBLICACION, E.DETENIDA),
    (E.REVISION, E.PUBLICADA),
    *((E.DETENIDA, destino) for destino in (E.INTAKE, E.CONTEXTO, E.PLANIFICACION)),
    (E.DETENIDA, E.ESCALETA),
    (E.DETENIDA, E.REVISION),
    (E.DETENIDA, E.PUBLICACION),
}


def test_toda_arista_de_la_tabla_esta_en_el_diagrama_salvo_las_de_q6_por_dibujar() -> None:
    """RF-04: las transiciones son exactamente las de §3.1. La tabla no puede ganar aristas
    que el diagrama no dibuje; las únicas que faltan hoy son las de Q6, contadas una a una."""
    en_la_tabla = {(a.origen, a.destino) for a in TRANSICIONES}
    sin_dibujar = en_la_tabla - _aristas_del_diagrama()
    assert sin_dibujar <= _Q6_AUN_SIN_DIAGRAMA, sorted(sin_dibujar - _Q6_AUN_SIN_DIAGRAMA)
    assert _Q6_AUN_SIN_DIAGRAMA <= en_la_tabla
