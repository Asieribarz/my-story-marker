"""§4.1.3 y §4.1.7 · la extracción de la salida cruda, en un solo sitio (`extraccion.py`).

Cada regla con un caso que la dispara y otro de control que no (R-5).
"""

import pytest

from backend.proyecto.extraccion import SalidaMalFormada, extraer
from backend.shared.tipos import Agente

SELLO = "0123456789abcdef0123456789abcdef:7:2"
MARKDOWN = "# La brújula\n\nAitana abrió el mapa.\n\nNala ladró."


def test_el_markdown_llega_sin_la_linea_del_sello() -> None:
    extraida = extraer(Agente.ESCRITOR, f"orden: {SELLO}\n\n{MARKDOWN}\n")
    assert (extraida.valor, extraida.sello) == (MARKDOWN, SELLO)


def test_el_sello_repetido_es_opcional() -> None:
    extraida = extraer(Agente.REVISOR, MARKDOWN)
    assert (extraida.valor, extraida.sello) == (MARKDOWN, None)


@pytest.mark.parametrize(
    ("salida", "motivo"),
    [
        ("Aitana abrió el mapa.", "# título"),
        ("# La brújula\n\n   \n", "texto después del título"),
        (f"orden: {SELLO}\n", "vacía"),
    ],
    ids=["sin título", "sin texto", "solo el sello"],
)
def test_un_markdown_mal_formado(salida: str, motivo: str) -> None:
    with pytest.raises(SalidaMalFormada, match=motivo) as error:
        extraer(Agente.EDITOR_ESTILO, salida)
    assert error.value.errores[0].startswith("(raíz): ")


@pytest.mark.parametrize(
    "salida",
    [
        'Aquí va:\n```json\n{"hechos": []}\n```\nListo.',
        f'orden: {SELLO}\n```\n{{"hechos": []}}\n```',
        '{"hechos": []}',
    ],
    ids=["bloque json", "bloque sin lenguaje y con sello", "json sin delimitar"],
)
def test_el_unico_bloque_json(salida: str) -> None:
    assert extraer(Agente.EXTRACTOR_HECHOS, salida).valor == {"hechos": []}


@pytest.mark.parametrize(
    ("salida", "motivo"),
    [
        ('```json\n{"a": 1}\n```\n```json\n{"b": 2}\n```', "se espera uno solo"),
        ("No hay nada que extraer.", "único bloque JSON"),
        ('```json\n{"a": NaN}\n```', "NaN, Infinity"),
        ('```json\n{"a": "\\ud800"}\n```', "sustituto suelto"),
        ('```json\n{"a": \n```', "no es JSON estricto"),
    ],
    ids=["dos bloques", "sin json", "nan", "sustituto escapado", "json roto"],
)
def test_un_json_mal_formado(salida: str, motivo: str) -> None:
    with pytest.raises(SalidaMalFormada, match=motivo):
        extraer(Agente.PLANIFICADOR, salida)


def test_una_salida_que_no_es_texto_utf8() -> None:
    with pytest.raises(SalidaMalFormada, match="sustituto suelto"):
        extraer(Agente.ESCRITOR, "# T\n\na \ud800 b")
