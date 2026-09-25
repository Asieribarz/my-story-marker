"""TC-7, spec-backend-2 §4.3: el conversor Markdown → HTML de lista blanca, la
titulación (RF-90) y el documento de lectura (RF-97). Datos ficticios."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.capitulo import segmentacion as seg
from backend.exportacion.lectura import (
    CapituloLeido,
    Titulacion,
    encabezado,
    manuscrito_md,
    markdown_a_html,
    titulo_en_lectura,
)
from backend.exportacion.tests.apoyo import errores_html, texto_capitulo


def test_parrafos_numerados_desde_uno_como_b14() -> None:
    cuerpo = "Uno.\n\nDos.\n\n***\n\nTres."
    html = markdown_a_html(cuerpo)
    assert html == '<p data-p="1">Uno.</p><p data-p="2">Dos.</p><hr><p data-p="3">Tres.</p>'
    assert len(seg.parrafos(cuerpo)) == 3


def test_enfasis_fuerza_cita_y_salto_duro() -> None:
    html = markdown_a_html("Con *énfasis*, _otro_ y **fuerza**.\n\n> Cita\n> larga\n\nA  \nB")
    assert html == (
        '<p data-p="1">Con <em>énfasis</em>, <em>otro</em> y <strong>fuerza</strong>.</p>'
        '<blockquote><p data-p="2">Cita larga</p></blockquote>'
        '<p data-p="3">A<br>B</p>'
    )


def test_todo_lo_demas_se_escapa() -> None:
    html = markdown_a_html('<script>alert("x")</script> <a href="y">z</a> & [e](u) `c`\n\n## Sub')
    assert "<script" not in html and "<a " not in html
    assert "&lt;script&gt;" in html and "&amp;" in html
    assert '<p data-p="2">## Sub</p>' in html  # `##` no es título en B-14: es párrafo
    assert errores_html(html) == []


def test_un_titulo_dentro_del_cuerpo_no_es_parrafo() -> None:
    assert markdown_a_html("# Suelto\n\nTexto.") == '<p data-p="1">Texto.</p>'


def test_asteriscos_sueltos_quedan_como_texto() -> None:
    assert markdown_a_html("2 * 3 = 6 y un * solo") == '<p data-p="1">2 * 3 = 6 y un * solo</p>'


_texto = st.text(
    alphabet=st.sampled_from(list("ab cñ*_<>&\"'>#-\n")) | st.characters(codec="utf-8"),
    max_size=200,
)


@settings(max_examples=60, deadline=None)
@given(_texto)
def test_propiedad_lista_blanca_y_numeracion(cuerpo: str) -> None:
    """Para cualquier cuerpo, el HTML solo tiene la lista blanca y tantos `data-p` como
    párrafos cuenta la segmentación única (B-14)."""
    html = markdown_a_html(cuerpo)
    esperados = len(seg.parrafos(cuerpo))
    assert html.count("<p ") == esperados
    if esperados:
        assert errores_html(html) == []


@pytest.mark.parametrize(
    ("titulacion", "esperado", "en_lectura"),
    [
        (Titulacion.NUMERADO, "Capítulo 3", None),
        (Titulacion.TITULADO, "El faro", "El faro"),
        (Titulacion.NUMERADO_Y_TITULADO, "Capítulo 3. El faro", "El faro"),
    ],
)
def test_titulacion(titulacion: Titulacion, esperado: str, en_lectura: str | None) -> None:
    assert encabezado(3, "El faro", titulacion) == esperado
    assert titulo_en_lectura("El faro", titulacion) == en_lectura


def test_titulacion_desconocida_no_pierde_nada() -> None:
    assert Titulacion.de("otra cosa") is Titulacion.NUMERADO_Y_TITULADO


def test_manuscrito_con_titulacion_y_dedicatoria() -> None:
    capitulos = [CapituloLeido.de_markdown(n, texto_capitulo(n, 1)) for n in (1, 2)]
    md = manuscrito_md("Título", "Para alguien", capitulos, Titulacion.NUMERADO)
    assert md.startswith("# Título\n\n*Para alguien*\n\n## Capítulo 1\n\n")
    assert "## Capítulo 2\n\n" in md and "# El capítulo" not in md
