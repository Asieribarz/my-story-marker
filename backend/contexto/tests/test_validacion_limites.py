"""V-15: casos de límite que matan los supervivientes de mutación de `validacion.py`.

Mismo método que `test_validacion.py` (V-11): la referencia de definitions.md §12 cambiada
en un solo punto, con los casos de control que no deben disparar al lado de los que sí.
Cada bloque fija un borde que la batería por regla no tocaba: el día del cumpleaños y su
víspera, un tramo de un solo capítulo, porcentajes que suman 99 o 101, o dos valores de
un enum cuyo orden alfabético se parece a la regla sin ser la regla.

Los mutantes equivalentes —los que ninguna entrada distingue del código— se anotan al
final, agrupados por razón, para que la próxima ejecución no los vuelva a investigar.

Datos ficticios, como la referencia.
"""

import json
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from backend.contexto.modelos import Ocasion, Publico, TipoFinal
from backend.contexto.tests.referencia import HOY, referencia
from backend.contexto.validacion import (
    InformeContexto,
    publico_por_edad,
    puede_salir_de_contexto,
    validar,
)
from backend.shared.tipos import Hallazgo

DIA = date.fromisoformat(HOY)


def _validar(datos: object, hoy: date = DIA) -> InformeContexto:
    return validar(datos, hoy)


def _n(datos: dict[str, Any]) -> dict[str, Any]:
    novela: dict[str, Any] = datos["novela"]
    return novela


def _de(informe: InformeContexto, regla: str) -> list[Hallazgo]:
    """Los hallazgos de una regla, lleve o no prefijo de requisito (`RF-24 · …`)."""
    return [h for h in informe.hallazgos if h.regla.split(" · ")[-1] == regla]


def _localizaciones(informe: InformeContexto, regla: str) -> list[str]:
    return [h.localizacion for h in _de(informe, regla)]


def _pareja() -> dict[str, Any]:
    """La referencia con un segundo destinatario y su personaje: sigue siendo válida."""
    datos = referencia()
    _n(datos)["personalizacion"]["segundo_destinatario"] = {
        "nombre": "Iker",
        "fecha_nacimiento": "2017-06-01",
        "edad": 9,
        "papel": "coprotagonista",
    }
    _n(datos)["personajes"].append(
        {
            "id": "coprot",
            "origen": {"tipo": "real", "fuente": "segundo_destinatario"},
            "rol": ["protagonista"],
            "arco": "positivo",
        }
    )
    return datos


# ─── El informe y la guarda (RF-21, RF-22) ───────────────────────────────────


def test_un_informe_sin_contexto_ni_hallazgos_no_sale_de_contexto() -> None:
    informe = InformeContexto()
    assert not informe.valido
    assert not puede_salir_de_contexto(informe)


def test_un_informe_con_contexto_y_hallazgos_no_sale_de_contexto() -> None:
    datos = referencia()
    _n(datos)["tono"] = "terror"
    informe = InformeContexto(
        contexto=_validar(referencia()).contexto, hallazgos=_validar(datos).hallazgos
    )
    assert not informe.valido
    assert not puede_salir_de_contexto(informe)


def test_el_informe_no_se_puede_retocar_despues_de_validar() -> None:
    datos = referencia()
    _n(datos)["tono"] = "terror"
    informe = _validar(datos)
    with pytest.raises(ValidationError):
        informe.hallazgos = ()  # type: ignore[misc]
    assert informe.hallazgos


@pytest.mark.parametrize(
    ("largo", "citado"), [(199, 199), (200, 200), (201, 200), (300, 200)], ids=str
)
def test_la_evidencia_se_cita_hasta_200_caracteres(largo: int, citado: int) -> None:
    datos = referencia()
    _n(datos)["tono"] = "x" * largo
    (hallazgo,) = [h for h in _validar(datos).hallazgos if h.localizacion == "novela.tono"]
    assert hallazgo.evidencia == "x" * citado


def test_la_referencia_llegada_como_json_es_valida() -> None:
    # `validar` recibe JSON, y tras `json.loads` cada texto es un objeto nuevo, no la
    # constante del código: una comparación por identidad (`is`) fallaría aquí.
    assert _validar(json.loads(json.dumps(referencia()))).valido


# ─── Público frente a edad del lector (RF-24) ────────────────────────────────

# (público, edad del lector, dispara). Bajar el público se admite; subirlo, no;
# `crossover` desde los 12 años.
PUBLICO: list[tuple[str, int, bool]] = [
    ("infantil", 11, False),
    ("infantil", 12, False),
    ("infantil", 18, False),
    ("infantil", 40, False),
    ("juvenil", 11, True),
    ("juvenil", 12, False),
    ("juvenil", 17, False),
    ("juvenil", 40, False),
    ("adulto", 11, True),
    ("adulto", 12, True),
    ("adulto", 17, True),
    ("adulto", 18, False),
    ("adulto", 40, False),
    ("crossover", 11, True),
    ("crossover", 12, False),
    ("crossover", 17, False),
    ("crossover", 18, False),
    ("crossover", 40, False),
]


@pytest.mark.parametrize(
    ("publico", "edad", "dispara"), PUBLICO, ids=[f"{p}-{e}" for p, e, _ in PUBLICO]
)
def test_publico_frente_a_edad_del_lector(publico: str, edad: int, dispara: bool) -> None:
    datos = referencia()
    _n(datos)["publico"] = publico
    _n(datos)["personalizacion"]["edad_lector"] = edad
    informe = _validar(datos)
    if dispara:
        assert [h.regla for h in informe.hallazgos] == ["RF-24 · publico_por_edad"]
    else:
        assert informe.valido, informe.hallazgos


@pytest.mark.parametrize("edad", [18, 19, 40, 120])
def test_de_18_en_adelante_el_publico_es_adulto(edad: int) -> None:
    assert publico_por_edad(edad) is Publico.ADULTO


# ─── Contenido según público (RF-25) ─────────────────────────────────────────

CATEGORIAS = ("violencia", "romance", "lenguaje", "sensibles")


@pytest.mark.parametrize("publico", ["juvenil", "adulto", "crossover"])
def test_fuera_de_infantil_el_contenido_admite_2_en_todo(publico: str) -> None:
    datos = referencia()
    _n(datos)["publico"] = publico
    _n(datos)["personalizacion"]["edad_lector"] = 40
    _n(datos)["tipo_aventura"]["contenido"] = dict.fromkeys(CATEGORIAS, 2)
    assert _validar(datos).valido


@pytest.mark.parametrize("categoria", CATEGORIAS)
def test_en_infantil_cada_categoria_admite_1_y_no_2(categoria: str) -> None:
    datos = referencia()
    _n(datos)["tipo_aventura"]["contenido"] = dict.fromkeys(CATEGORIAS, 1)
    assert _validar(datos).valido
    _n(datos)["tipo_aventura"]["contenido"][categoria] = 2
    assert _localizaciones(_validar(datos), "contenido_por_publico") == [
        f"novela.tipo_aventura.contenido.{categoria}"
    ]


# ─── Tono frente a edad del lector (definitions.md §10) ──────────────────────

# (tono, edad del lector, dispara). Solo `melancolico`, y solo por debajo de 12.
TONO: list[tuple[str, int, bool]] = [
    ("epico", 9, False),
    ("ligero", 9, False),
    ("pulp", 9, False),
    ("melancolico", 9, True),
    ("melancolico", 11, True),
    ("melancolico", 12, False),
    ("melancolico", 17, False),
    ("melancolico", 18, False),
]


@pytest.mark.parametrize(("tono", "edad", "dispara"), TONO, ids=[f"{t}-{e}" for t, e, _ in TONO])
def test_tono_frente_a_edad_del_lector(tono: str, edad: int, dispara: bool) -> None:
    datos = referencia()
    _n(datos)["tono"] = tono
    _n(datos)["personalizacion"]["edad_lector"] = edad
    informe = _validar(datos)
    if dispara:
        assert [h.regla for h in informe.hallazgos] == ["RF-24 · tono_por_edad"]
    else:
        assert informe.valido, informe.hallazgos


# ─── Final según ocasión (definitions.md §10) ────────────────────────────────

FINALES = [(o.value, f.value) for o in Ocasion for f in TipoFinal]


@pytest.mark.parametrize(("ocasion", "final"), FINALES, ids=[f"{o}-{f}" for o, f in FINALES])
def test_final_frente_a_ocasion(ocasion: str, final: str) -> None:
    datos = referencia()
    _n(datos)["personalizacion"]["ocasion"] = ocasion
    _n(datos)["estructura"]["desenlace"]["final"] = final
    informe = _validar(datos)
    if ocasion in ("boda", "jubilacion") and final == "agridulce":
        assert [h.regla for h in informe.hallazgos] == ["RF-24 · final_por_ocasion"]
    else:
        assert informe.valido, informe.hallazgos


# ─── Edad declarada frente a fecha de nacimiento (definitions.md §10) ────────

EDAD = "novela.personalizacion.destinatario.edad"

# La referencia nace el 2017-04-12. (día de la validación, edad declarada, se admite): la
# cumplida y la que está a punto de cumplir. Se repite en 2027 porque la paridad de la
# diferencia de años importa: con 9 años de diferencia, restar 1 y alternar el último bit
# dan lo mismo; con 10, no.
CUMPLEANOS: list[tuple[str, int, bool]] = [
    # La víspera del noveno cumpleaños: tiene 8.
    ("2026-04-11", 7, False),
    ("2026-04-11", 8, True),
    ("2026-04-11", 9, True),
    ("2026-04-11", 10, False),
    # El día del noveno cumpleaños: ya tiene 9.
    ("2026-04-12", 8, False),
    ("2026-04-12", 9, True),
    ("2026-04-12", 10, True),
    ("2026-04-12", 11, False),
    # La víspera del décimo: tiene 9.
    ("2027-04-11", 8, False),
    ("2027-04-11", 9, True),
    ("2027-04-11", 10, True),
    ("2027-04-11", 11, False),
    # El día del décimo: ya tiene 10.
    ("2027-04-12", 9, False),
    ("2027-04-12", 10, True),
    ("2027-04-12", 11, True),
    ("2027-04-12", 12, False),
    # El día en que nace: la fecha no es futura, y tiene 0.
    ("2017-04-12", 0, True),
    ("2017-04-12", 1, True),
    ("2017-04-12", 2, False),
]


@pytest.mark.parametrize(
    ("hoy", "edad", "admitida"), CUMPLEANOS, ids=[f"{h}-{e}" for h, e, _ in CUMPLEANOS]
)
def test_edad_declarada_frente_a_nacimiento(hoy: str, edad: int, admitida: bool) -> None:
    datos = referencia()
    _n(datos)["personalizacion"]["destinatario"]["edad"] = edad
    informe = _validar(datos, date.fromisoformat(hoy))
    if admitida:
        assert informe.valido, informe.hallazgos
    else:
        assert _localizaciones(informe, "edad_frente_a_nacimiento") == [EDAD]


def test_la_vispera_de_nacer_la_fecha_es_futura() -> None:
    datos = referencia()
    _n(datos)["personalizacion"]["destinatario"]["edad"] = 0
    informe = _validar(datos, date(2017, 4, 11))
    assert _localizaciones(informe, "edad_frente_a_nacimiento") == [
        "novela.personalizacion.destinatario.fecha_nacimiento"
    ]


@pytest.mark.parametrize(("nacimiento", "edad"), [("1000-01-01", 26), ("1900-01-01", 120)])
def test_un_nacimiento_de_hace_mas_de_120_anos_no_admite_ninguna_edad(
    nacimiento: str, edad: int
) -> None:
    # 26 es 2026 mod 1000: lo que saldría si la cuenta de años tomase un resto en vez de
    # restar, cosa que con nacimientos recientes da lo mismo.
    datos = referencia()
    _n(datos)["personalizacion"]["destinatario"]["fecha_nacimiento"] = nacimiento
    _n(datos)["personalizacion"]["destinatario"]["edad"] = edad
    assert _localizaciones(_validar(datos), "edad_frente_a_nacimiento") == [EDAD]


def test_el_hallazgo_de_edad_nombra_las_dos_edades_admitidas() -> None:
    # Con 9 cumplidos, impar, «10» no sale de ninguna operación con 9 que no sea sumar 1.
    datos = referencia()
    _n(datos)["personalizacion"]["destinatario"]["edad"] = 12
    (hallazgo,) = _de(_validar(datos), "edad_frente_a_nacimiento")
    assert hallazgo.esperado == "9 o 10 según la fecha de nacimiento"


def test_la_pareja_de_control_es_valida() -> None:
    assert _validar(_pareja()).valido


@pytest.mark.parametrize("fecha", [None, "2027-01-01"], ids=["sin fecha", "fecha futura"])
def test_la_edad_del_segundo_destinatario_se_comprueba_aunque_la_del_primero_no(
    fecha: str | None,
) -> None:
    datos = _pareja()
    personalizacion = _n(datos)["personalizacion"]
    personalizacion["destinatario"]["fecha_nacimiento"] = fecha
    personalizacion["destinatario"]["edad"] = None
    personalizacion["segundo_destinatario"]["edad"] = 15
    assert "novela.personalizacion.segundo_destinatario.edad" in _localizaciones(
        _validar(datos), "edad_frente_a_nacimiento"
    )


# ─── Eventos frente a nacimiento (definitions.md §10) ────────────────────────

# (momento del evento h2, dispara) frente al nacimiento del 2017-04-12. Un momento se
# compara con la fecha de nacimiento recortada a su misma precisión.
MOMENTOS: list[tuple[str, bool]] = [
    ("2016", True),
    ("2017", False),
    ("2017-03", True),
    ("2017-04", False),
    ("2017-04-11", True),
    ("2017-04-12", False),
    ("2017-04-13", False),
    ("infancia", False),
]


@pytest.mark.parametrize(("momento", "dispara"), MOMENTOS, ids=[m for m, _ in MOMENTOS])
def test_un_evento_no_es_anterior_al_nacimiento(momento: str, dispara: bool) -> None:
    datos = referencia()
    _n(datos)["personalizacion"]["hechos"][1]["momento"] = momento
    informe = _validar(datos)
    if dispara:
        assert _localizaciones(informe, "evento_antes_de_nacer") == [
            "novela.personalizacion.hechos.1.momento"
        ]
    else:
        assert informe.valido, informe.hallazgos


@pytest.mark.parametrize("indice", [0, 2, 3, 4], ids=["ser_querido", "lugar", "objeto", "frase"])
def test_solo_los_eventos_se_comparan_con_el_nacimiento(indice: int) -> None:
    # La casa de la abuela puede ser de 1950: un hecho que no es `evento` no es un recuerdo.
    datos = referencia()
    _n(datos)["personalizacion"]["hechos"][indice]["momento"] = "1950"
    assert _validar(datos).valido


def test_un_evento_sin_momento_da_su_hallazgo_y_no_se_compara() -> None:
    datos = referencia()
    del _n(datos)["personalizacion"]["hechos"][1]["momento"]
    informe = _validar(datos)
    assert [h.regla for h in informe.hallazgos] == ["evento_con_momento_y_lugar"]


# ─── Hechos obligatorios (definitions.md §9) ─────────────────────────────────


@pytest.mark.parametrize(("total", "dispara"), [(5, False), (6, True)], ids=["5", "6"])
def test_a_lo_sumo_cinco_obligatorios(total: int, dispara: bool) -> None:
    # La referencia trae 4 obligatorios y h5 `deseable`, que se queda: la cuenta es de
    # obligatorios, no de hechos.
    datos = referencia()
    hechos = _n(datos)["personalizacion"]["hechos"]
    for k in range(total - 4):
        hechos.append(
            {
                "id": f"r{k}",
                "tipo": "rasgo",
                "texto": "Colecciona conchas",
                "prioridad": "obligatorio",
                "origen": "entrevista",
            }
        )
    informe = _validar(datos)
    if dispara:
        assert [h.regla for h in informe.hallazgos] == ["hechos_obligatorios"]
    else:
        assert informe.valido, informe.hallazgos


# ─── Subgéneros (definitions.md §2) ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("secundarios", "dispara"),
    [([], False), (["expedicion", "nautica"], False), (["nautica", "nautica"], True)],
    ids=["ninguno", "dos distintos", "dos iguales"],
)
def test_secundarios_distintos_entre_si(secundarios: list[str], dispara: bool) -> None:
    datos = referencia()
    _n(datos)["tipo_aventura"]["subgenero"]["secundarios"] = secundarios
    informe = _validar(datos)
    if dispara:
        assert [h.regla for h in informe.hallazgos] == ["subgeneros_distintos"]
    else:
        assert informe.valido, informe.hallazgos


# ─── Estructura (definitions.md §10) ─────────────────────────────────────────

Tramo = tuple[int, int]


def _repartir(
    datos: dict[str, Any], tramos: tuple[Tramo, Tramo, Tramo], hitos: tuple[int, int, int]
) -> None:
    """Tramos de planteamiento, nudo y desenlace; hitos punto medio, crisis y clímax."""
    e = _n(datos)["estructura"]
    (planteamiento, nudo, desenlace), (punto_medio, crisis, climax) = tramos, hitos
    e["planteamiento"]["capitulos"] = list(planteamiento)
    e["nudo"].update(capitulos=list(nudo), punto_medio=punto_medio, crisis=crisis)
    e["desenlace"].update(capitulos=list(desenlace), climax=climax)


REPARTOS_VALIDOS: list[tuple[str, tuple[Tramo, Tramo, Tramo], tuple[int, int, int]]] = [
    ("tramos de un capítulo", ((1, 1), (2, 9), (10, 10)), (5, 9, 10)),
    ("planteamiento que acaba en impar", ((1, 3), (4, 8), (9, 10)), (5, 8, 9)),
    ("nudo que acaba en impar", ((1, 2), (3, 7), (8, 10)), (5, 7, 9)),
]


@pytest.mark.parametrize(
    ("nombre", "tramos", "hitos"), REPARTOS_VALIDOS, ids=[r[0] for r in REPARTOS_VALIDOS]
)
def test_repartos_contiguos_de_los_diez_capitulos(
    nombre: str, tramos: tuple[Tramo, Tramo, Tramo], hitos: tuple[int, int, int]
) -> None:
    datos = referencia()
    _repartir(datos, tramos, hitos)
    assert _validar(datos).valido, _validar(datos).hallazgos


REPARTOS_INVALIDOS: list[tuple[str, tuple[Tramo, Tramo, Tramo], tuple[int, int, int], str]] = [
    ("nudo que empieza un capítulo antes", ((1, 2), (2, 8), (9, 10)), (5, 8, 9), "nudo"),
    ("nudo que acaba antes de empezar", ((1, 2), (3, 2), (3, 10)), (5, 8, 9), "nudo"),
    ("desenlace que acaba en el 9", ((1, 2), (3, 8), (9, 9)), (5, 8, 9), "desenlace"),
]


@pytest.mark.parametrize(
    ("nombre", "tramos", "hitos", "tramo"),
    REPARTOS_INVALIDOS,
    ids=[r[0] for r in REPARTOS_INVALIDOS],
)
def test_repartos_que_no_cubren_los_diez_capitulos(
    nombre: str, tramos: tuple[Tramo, Tramo, Tramo], hitos: tuple[int, int, int], tramo: str
) -> None:
    datos = referencia()
    _repartir(datos, tramos, hitos)
    localizacion = f"novela.estructura.{tramo}.capitulos"
    assert localizacion in _localizaciones(_validar(datos), "estructura_tramos")


@pytest.mark.parametrize(
    ("porcentajes", "dispara"),
    [((22, 55, 23), False), ((20, 60, 20), False), ((21, 55, 23), True), ((23, 55, 23), True)],
    ids=["100", "100 de otro modo", "99", "101"],
)
def test_porcentajes_que_suman_100(porcentajes: tuple[int, int, int], dispara: bool) -> None:
    datos = referencia()
    for acto, porcentaje in zip(("planteamiento", "nudo", "desenlace"), porcentajes, strict=True):
        _n(datos)["estructura"][acto]["porcentaje"] = porcentaje
    informe = _validar(datos)
    if dispara:
        assert [h.regla for h in informe.hallazgos] == ["estructura_porcentajes"]
    else:
        assert informe.valido, informe.hallazgos


# ─── Personajes (definitions.md §4 y §10) ────────────────────────────────────


def test_dos_personajes_con_el_mismo_id() -> None:
    datos = referencia()
    _n(datos)["personajes"][2]["id"] = "nala"
    (hallazgo,) = _de(_validar(datos), "personaje_id_unico")
    assert hallazgo.evidencia == "nala"


@pytest.mark.parametrize(
    ("fuente", "valida"),
    [("h1", True), ("h2", False), ("h3", False), ("h4", False), ("h5", False)],
    ids=["ser_querido", "evento", "lugar", "objeto", "frase"],
)
def test_un_personaje_real_solo_viene_de_un_hecho_ser_querido(fuente: str, valida: bool) -> None:
    datos = referencia()
    _n(datos)["personajes"][1]["origen"]["fuente"] = fuente
    informe = _validar(datos)
    if valida:
        assert informe.valido, informe.hallazgos
    else:
        assert _localizaciones(informe, "personaje_real_con_fuente") == [
            "novela.personajes.1.origen.fuente"
        ]


def test_la_fuente_destinatario_vale_aunque_un_hecho_se_llame_igual() -> None:
    # Un hecho con id `destinatario` es ambiguo, pero no puede quitarle la fuente al
    # personaje del destinatario.
    datos = referencia()
    _n(datos)["personalizacion"]["hechos"].append(
        {
            "id": "destinatario",
            "tipo": "ser_querido",
            "texto": "Su primo, que vive en la costa",
            "prioridad": "deseable",
            "origen": "entrevista",
        }
    )
    assert _de(_validar(datos), "personaje_real_con_fuente") == []


def test_sin_segundo_destinatario_su_fuente_no_vale() -> None:
    datos = referencia()
    _n(datos)["personajes"][1]["origen"]["fuente"] = "segundo_destinatario"
    assert _localizaciones(_validar(datos), "personaje_real_con_fuente") == [
        "novela.personajes.1.origen.fuente"
    ]


def test_dos_personajes_con_fuente_destinatario() -> None:
    datos = referencia()
    _n(datos)["personajes"].append(
        {
            "id": "prot_bis",
            "origen": {"tipo": "real", "fuente": "destinatario"},
            "rol": ["aliado"],
            "arco": "plano",
        }
    )
    (hallazgo,) = _de(_validar(datos), "destinatario_en_la_novela")
    assert hallazgo.evidencia == "2 personajes con fuente `destinatario`"


def test_sin_personaje_del_destinatario_se_revisa_igual_el_del_segundo() -> None:
    datos = _pareja()
    personajes = _n(datos)["personajes"]
    personajes.pop(0)
    personajes[-1]["arco"] = "corrupcion"
    informe = _validar(datos)
    assert _de(informe, "destinatario_en_la_novela")
    assert _localizaciones(informe, "arco_del_destinatario") == [
        f"novela.personajes.{len(personajes) - 1}.arco"
    ]


@pytest.mark.parametrize(
    ("papel", "dispara"),
    [("protagonista", True), ("coprotagonista", False), ("secundario_clave", False)],
)
def test_solo_el_papel_protagonista_exige_el_rol_protagonista(papel: str, dispara: bool) -> None:
    datos = referencia()
    _n(datos)["personalizacion"]["destinatario"]["papel"] = papel
    _n(datos)["personajes"][0]["rol"] = ["aliado"]
    informe = _validar(datos)
    if dispara:
        assert _localizaciones(informe, "papel_del_destinatario") == ["novela.personajes.0.rol"]
    else:
        assert informe.valido, informe.hallazgos


# ─── Mundo (definitions.md §5 y §10) ─────────────────────────────────────────


def test_dos_localizaciones_con_el_mismo_id() -> None:
    datos = referencia()
    _n(datos)["mundo"]["localizaciones"].append({"id": "faro", "nivel": "micro", "padre": "costa"})
    (hallazgo,) = _de(_validar(datos), "localizacion_id_unico")
    assert hallazgo.evidencia == "faro"


# (caso, índice en la referencia, padre nuevo). El 6 es `faro` (micro) y el 2 `bosque`
# (meso); cada caso rompe la cadena macro → meso → micro en un solo eslabón.
PADRES: list[tuple[str, int, str | None]] = [
    ("micro bajo micro", 6, "playa"),
    ("meso bajo meso", 2, "pueblo"),
    ("micro bajo un id inexistente", 6, "castillo"),
    ("micro sin padre", 6, None),
    ("meso sin padre", 2, None),
]


@pytest.mark.parametrize(("nombre", "indice", "padre"), PADRES, ids=[p[0] for p in PADRES])
def test_el_arbol_encadena_macro_meso_micro(nombre: str, indice: int, padre: str | None) -> None:
    datos = referencia()
    _n(datos)["mundo"]["localizaciones"][indice]["padre"] = padre
    assert _localizaciones(_validar(datos), "arbol_de_localizaciones") == [
        f"novela.mundo.localizaciones.{indice}.padre"
    ]


# ─── Mutantes equivalentes ───────────────────────────────────────────────────
# Supervivientes de cosmic-ray (ejecución del 2026-09-23) que ninguna entrada distingue
# del código. Se citan por función y no por línea, porque las líneas se mueven.
#
# - `is` → `==`, e `is not` → `!=`, entre miembros de un enum: cada miembro es único, así
#   que identidad e igualdad coinciden. Aparece en casi todas las reglas y en `_mundo`
#   también con `None` (`nivel_de.get(...) != esperado`).
# - `is` → `<=` o `>=`, e `is not` → `>`, cuando el orden alfabético del StrEnum no separa
#   nada que la regla separe: `evento` es el menor de TipoHecho (`_hechos`,
#   `_eventos_tras_el_nacimiento`), `ser_querido` el mayor (`_personajes`) y `obligatorio`
#   el mayor de Prioridad (`_hechos`).
# - `origen.tipo == "real"` → `>=`, y `== "ficticio"` → `<=`: el Literal solo admite esos
#   dos valores, y `"ficticio" < "real"`.
# - `origen.tipo == "real"` → `is`, y `== "ficticio"` → `is`: pydantic devuelve el objeto
#   declarado en el Literal, que es la misma constante internada que la del código.
#   Con `origen.fuente`, un `str`, sí se nota: lo mata la referencia llegada como JSON.
# - `veces > 1` → `veces != 1` en los tres recuentos de ids: un Counter no cuenta ceros.
# - `len(set(x)) != len(x)` → `<` en `_subgeneros`: un conjunto nunca es más largo.
# - `!=` → `is not` entre enteros pequeños en `_subgeneros` y `_estructura`: CPython
#   guarda una sola instancia de cada entero entre -5 y 256.
# - `esperado_inicio != 11` → `< 11` en `_estructura`: el tipo Capitulo acota el último
#   capítulo a 10, así que `esperado_inicio` no pasa de 11.
# - `_RANGO_PUBLICO` con ADULTO 3 o INFANTIL -1: la regla solo compara, y el orden se
#   conserva.
# - `error.errors(include_url=True)` en `_hallazgos_de_tipo`: añade la clave `url`, que
#   nadie lee.
# - `suyos[0]` → `suyos[-1]` en `_personajes`: se lee solo cuando la lista tiene un
#   elemento.
# - `continue` → `break` al saltar un destinatario ausente en `_personajes`: el primero
#   es obligatorio en el modelo, así que solo falta el segundo, que es el último.
# - `puede_salir_de_contexto`: sus ocho supervivientes desaparecen con la simplificación a
#   `informe.valido`, que sostiene `test_todo_hallazgo_del_validador_es_bloqueante`.
