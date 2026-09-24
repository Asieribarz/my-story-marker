"""B-20: la salida del Agente de Contexto conserva lo que fijó el comprador.

Cada regla tiene una prueba que la dispara y otra de control que no (V-15, R-5). El brief de
las pruebas es la personalización de la instancia de referencia, tal como la daría la
entrevista: la referencia sin tocar es el control de todas.
"""

import copy
from collections.abc import Callable
from typing import Any

import pytest

from backend.contexto.conservacion import REGLA, en_el_contexto, en_la_normalizacion
from backend.contexto.tests.referencia import referencia


def _brief() -> dict[str, Any]:
    novela = referencia()["novela"]
    personalizacion = {k: v for k, v in novela["personalizacion"].items() if k != "texto_libre"}
    for hecho in personalizacion["hechos"]:
        hecho.pop("lugar", None)
    return {"personalizacion": personalizacion, "preferencias": {"tono": novela["tono"]}}


def _contexto(cambio: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    datos = referencia()
    cambio(datos["novela"])
    return datos


def _localizaciones(hallazgos: tuple[Any, ...]) -> list[str]:
    assert all(h.regla == REGLA for h in hallazgos)
    return [h.localizacion for h in hallazgos]


def test_la_referencia_conserva_su_brief() -> None:
    assert en_el_contexto(_brief(), [], referencia()) == ()


def _nombre(n: dict[str, Any]) -> None:
    n["personalizacion"]["destinatario"]["nombre"] = "[NOMBRE_ANONIMIZADO]"


def _edad(n: dict[str, Any]) -> None:
    n["personalizacion"]["destinatario"]["edad"] += 1


def _veto(n: dict[str, Any]) -> None:
    n["personalizacion"]["vetos"]["palabras"].append("otra")


def _tono(n: dict[str, Any]) -> None:
    n["tono"] = "epico"


def _texto_de_hecho(n: dict[str, Any]) -> None:
    n["personalizacion"]["hechos"][0]["texto"] += " (retocado)"


def _hecho_perdido(n: dict[str, Any]) -> None:
    n["personalizacion"]["hechos"].pop(0)


@pytest.mark.parametrize(
    ("cambio", "localizacion"),
    [
        (_nombre, "novela.personalizacion.destinatario.nombre"),
        (_edad, "novela.personalizacion.destinatario.edad"),
        (_veto, "novela.personalizacion.vetos"),
        (_tono, "novela.tono"),
        (_texto_de_hecho, "novela.personalizacion.hechos[h1].texto"),
        (_hecho_perdido, "novela.personalizacion.hechos[h1]"),
    ],
)
def test_un_cambio_en_lo_que_fijo_el_comprador_salta(
    cambio: Callable[[dict[str, Any]], None], localizacion: str
) -> None:
    assert localizacion in _localizaciones(en_el_contexto(_brief(), [], _contexto(cambio)))


def test_la_evidencia_no_copia_el_valor() -> None:
    hallazgos = en_el_contexto(_brief(), [], _contexto(_nombre))
    assert [h.evidencia for h in hallazgos] == [
        "cambia respecto al brief",
        "marcador de anonimización en lugar de un dato del comprador",
    ]
    assert all("Aitana" not in (h.esperado or "") for h in hallazgos)


def test_un_marcador_en_cualquier_clave_salta() -> None:
    datos = _contexto(lambda n: n["tema"].update(central="La amistad con [NOMBRE_ANONIMIZADO]"))
    assert _localizaciones(en_el_contexto(_brief(), [], datos)) == ["novela.tema.central"]


def test_control_un_marcador_que_ya_traia_el_brief_no_salta() -> None:
    brief = _brief()
    brief["personalizacion"]["dedicatoria"] = "Para [NOMBRE_ANONIMIZADO]"
    datos = _contexto(
        lambda n: n["personalizacion"].update(dedicatoria="Para [NOMBRE_ANONIMIZADO]")
    )
    assert en_el_contexto(brief, [], datos) == ()


def test_control_el_lugar_de_un_evento_puede_pasar_a_ser_un_id() -> None:
    brief = _brief()
    brief["personalizacion"]["hechos"][1]["lugar"] = "la playa del pueblo"
    assert en_el_contexto(brief, [], referencia()) == ()


def test_control_una_clave_que_el_comprador_no_dio_se_puede_derivar() -> None:
    brief = _brief()
    del brief["personalizacion"]["destinatario"]["papel"]
    del brief["personalizacion"]["edad_lector"]
    del brief["preferencias"]
    assert en_el_contexto(brief, [], _contexto(_tono)) == ()


def test_control_una_ocasion_con_las_palabras_del_comprador_se_traduce() -> None:
    brief = _brief()
    brief["personalizacion"]["ocasion"] = "su cumple"
    assert en_el_contexto(brief, [], referencia()) == ()


def test_una_ocasion_ya_permitida_no_se_cambia() -> None:
    datos = _contexto(lambda n: n["personalizacion"].update(ocasion="graduacion"))
    assert _localizaciones(en_el_contexto(_brief(), [], datos)) == [
        "novela.personalizacion.ocasion"
    ]


def test_un_hecho_confirmado_tiene_que_llegar() -> None:
    confirmado = {"tipo": "rasgo", "texto": "Colecciona piedras con forma de corazón"}
    assert _localizaciones(en_el_contexto(_brief(), [confirmado], referencia())) == [
        "novela.personalizacion.hechos[confirmado 1]"
    ]


def test_control_un_hecho_confirmado_que_llega_no_salta() -> None:
    confirmado = {"tipo": "rasgo", "texto": "Colecciona piedras con forma de corazón"}
    datos = _contexto(
        lambda n: n["personalizacion"]["hechos"].append(
            {**confirmado, "id": "h9", "prioridad": "deseable", "origen": "texto_libre"}
        )
    )
    assert en_el_contexto(_brief(), [confirmado], datos) == ()


def _normalizado(brief: dict[str, Any]) -> dict[str, Any]:
    salida = copy.deepcopy(brief)
    return {**salida, "notas": [], "faltan": []}


def test_control_la_normalizacion_fiel_no_salta() -> None:
    assert en_la_normalizacion(_brief(), [], _normalizado(_brief())) == ()


def test_la_normalizacion_que_anonimiza_un_veto_salta() -> None:
    brief = _brief()
    brief["personalizacion"]["vetos"]["palabras"] = ["Rodrigo"]
    salida = _normalizado(brief)
    salida["personalizacion"]["vetos"]["palabras"] = ["[NOMBRE_ANONIMIZADO]"]
    assert _localizaciones(en_la_normalizacion(brief, [], salida)) == [
        "personalizacion.vetos",
        "personalizacion.vetos.palabras[0]",
    ]


def test_la_normalizacion_que_cambia_una_preferencia_salta() -> None:
    salida = _normalizado(_brief())
    salida["preferencias"]["tono"] = "epico"
    assert _localizaciones(en_la_normalizacion(_brief(), [], salida)) == ["preferencias.tono"]
