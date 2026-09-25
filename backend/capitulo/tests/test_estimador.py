"""RF-52a a RF-52c: el estimador y su respaldo en Python puro (docstring de estimador.py)."""

import importlib
import math
import time
from pathlib import Path

import pytest

from backend.capitulo import estimador

RAIZ = Path(__file__).resolve().parents[3]
MUESTRA = (
    "Érase una vez, en Valdeluna, una niña llamada Aitana que guardaba la Brújula del Abuelo.\n"
    "—¿Quién anda ahí? —preguntó, y el eco de la cueva le devolvió «ahí, ahí».\n\n"
    '```json\n{"presentes": ["prot", "nala"], "dia": 12345, "tension": 9}\n```\n'
    "CamelCase DON'T ñandú Ünïcödé 3,14 ½ ٣ 𝒜 \t  \r\n\n  x—y ¡Ay! «hola»…\n"
)


def _con_regex() -> object:
    try:
        return estimador.patron_con_regex()
    except ImportError as error:
        pytest.skip(f"`regex` no importa: {error}")


def test_el_factor_se_aplica_y_redondea_hacia_arriba() -> None:
    cuenta = estimador.contador_respaldo(estimador.patron_con_re())
    assert cuenta("Hello, world!") == 4  # [13225, 11, 2375, 0] en o200k_base
    assert estimador.estimar_tokens("Hello, world!") == math.ceil(4 * 1.35)
    assert estimador.estimar_tokens("") == 0


def test_el_respaldo_da_cuentas_razonables_en_espanol() -> None:
    texto = (RAIZ / "docs" / "architecture.md").read_text(encoding="utf-8")
    tokens = estimador.contador_respaldo(estimador.patron_con_re())(texto)
    # o200k_base en prosa española: entre 3 y 5 caracteres por token.
    assert len(texto) / 5 < tokens < len(texto) / 3


def test_re_y_regex_pre_tokenizan_igual() -> None:
    texto = MUESTRA + (RAIZ / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert estimador.patron_con_re().findall(texto) == _con_regex().findall(texto)  # type: ignore[attr-defined]


def test_una_pieza_larga_no_infracuenta() -> None:
    tabla = estimador.rangos()
    pieza = ("¡" * 300).encode()
    assert estimador.contar_pieza(pieza, tabla) == len(pieza)


def test_cien_mil_tokens_en_pocos_segundos() -> None:
    texto = (RAIZ / "docs" / "architecture.md").read_text(encoding="utf-8") * 5
    inicio = time.perf_counter()
    tokens = estimador.estimar_tokens(texto + "fin")
    assert tokens > 100_000
    assert time.perf_counter() - inicio < 10


def test_paridad_con_tiktoken() -> None:
    try:
        importlib.import_module("tiktoken")
        exacto = estimador.contador_tiktoken()
    except ImportError as error:
        pytest.skip(f"tiktoken no carga en esta máquina: {error}")
    respaldo = estimador.contador_respaldo(estimador.patron_con_re())
    textos = [MUESTRA, (RAIZ / "docs" / "architecture.md").read_text(encoding="utf-8")]
    for texto in textos:
        assert respaldo(texto) == exacto(texto)
