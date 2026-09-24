"""B-14: la segmentación única, y el silabeo propio de INFLESZ (D-6, validators §2.6)."""

import pytest

from backend.capitulo import segmentacion as seg
from backend.capitulo.verificadores.medidas import silabas

CAPITULO = """# El faro

Primer párrafo
en dos líneas.

* * *

—¿Vienes? —preguntó el Sr. Gómez—. Ven ya.

---

Tercer párrafo. Con dos frases.
"""


def test_el_parrafo_no_cuenta_el_titulo_ni_el_separador() -> None:
    titulo, cuerpo = seg.separar_titulo(CAPITULO)
    parrafos = seg.parrafos(cuerpo)
    assert titulo == "El faro"
    assert [p.numero for p in parrafos] == [1, 2, 3]
    assert parrafos[0].texto == "Primer párrafo en dos líneas."
    assert parrafos[2].texto.startswith("Tercer")


def test_la_frase_no_se_corta_tras_abreviatura_ni_ante_inciso() -> None:
    parrafo = seg.parrafos(seg.separar_titulo(CAPITULO)[1])[1]
    assert [f.texto for f in seg.frases(parrafo)] == [
        "—¿Vienes? —preguntó el Sr. Gómez—.",
        "Ven ya.",
    ]


def test_el_dialogo_sigue_la_convencion() -> None:
    raya = seg.Parrafo(1, "—Hola —dijo Ana—. ¿Vienes?")
    assert seg.dialogo(raya, "raya") == ("Hola ", ". ¿Vienes?")
    assert seg.dialogo(seg.Parrafo(1, "Ana dijo «hola» y calló."), "comillas") == ("hola",)
    assert seg.dialogo(seg.Parrafo(1, "Sin diálogo."), "raya") == ()


@pytest.mark.parametrize(
    ("palabra", "esperadas"),
    [
        ("casa", 2),
        ("aéreo", 4),
        ("ciudad", 2),
        ("día", 2),
        ("poeta", 3),
        ("buey", 1),
        ("hoy", 1),
        ("murciélago", 4),
        ("país", 2),
        ("ahora", 3),
        ("y", 1),
    ],
)
def test_silabas_de_silabeo_conocido(palabra: str, esperadas: int) -> None:
    assert silabas(palabra) == esperadas
