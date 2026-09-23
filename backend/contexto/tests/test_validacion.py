"""V-11: batería derivada de definitions.md §12 — una válida y una inválida por regla.

Cada caso inválido parte de la referencia y rompe exactamente una cosa; el caso de control
es la propia referencia, que no debe disparar ninguna regla.
"""

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.contexto.modelos import VERSION_ONTOLOGIA, Contexto
from backend.contexto.persistencia import ContextoInvalido, contexto_vigente, guardar_contexto
from backend.contexto.tests.referencia import HOY, referencia
from backend.contexto.validacion import (
    REGLAS,
    InformeContexto,
    publico_por_edad,
    puede_salir_de_contexto,
    validar,
)
from backend.shared.db import crear_base
from backend.shared.tipos import Severidad

DIA = date.fromisoformat(HOY)
Mutacion = Callable[[dict[str, Any]], None]


def _validar(datos: object) -> InformeContexto:
    return validar(datos, DIA)


def _n(datos: dict[str, Any]) -> dict[str, Any]:
    novela: dict[str, Any] = datos["novela"]
    return novela


# ─── La referencia ───────────────────────────────────────────────────────────


def test_la_referencia_es_valida() -> None:
    informe = _validar(referencia())
    assert informe.hallazgos == ()
    assert informe.valido
    assert puede_salir_de_contexto(informe)
    assert informe.version_ontologia == VERSION_ONTOLOGIA


def test_la_referencia_declara_los_porcentajes_que_rellena() -> None:
    # §12 no trae porcentajes de acto: se rellenan 22/55/23 y se declaran (RF-26).
    informe = _validar(referencia())
    assert informe.rellenados == (
        "novela.estructura.planteamiento.porcentaje",
        "novela.estructura.nudo.porcentaje",
        "novela.estructura.desenlace.porcentaje",
    )
    assert informe.contexto is not None
    e = informe.contexto.novela.estructura
    assert (e.planteamiento.porcentaje, e.nudo.porcentaje, e.desenlace.porcentaje) == (22, 55, 23)


def test_rellena_y_declara_modelo_tiempo_y_papel() -> None:
    datos = referencia()
    del _n(datos)["estructura"]["modelo"]
    del _n(datos)["lenguaje"]["tiempo"]
    del _n(datos)["personalizacion"]["destinatario"]["papel"]
    informe = _validar(datos)
    assert informe.valido
    assert {
        "novela.estructura.modelo",
        "novela.lenguaje.tiempo",
        "novela.personalizacion.destinatario.papel",
    } <= set(informe.rellenados)
    assert informe.contexto is not None
    assert informe.contexto.novela.lenguaje.tiempo == "preterito"


def test_no_modifica_la_entrada() -> None:
    datos = referencia()
    _validar(datos)
    assert datos == referencia()


# ─── Tipos y valores permitidos (RF-23, RF-25, RF-27) ────────────────────────


def _asignar(ruta: str, valor: object) -> Mutacion:
    def mutar(datos: dict[str, Any]) -> None:
        *camino, ultima = ruta.split(".")
        nodo: Any = datos
        for parte in camino:
            nodo = nodo[int(parte)] if parte.isdigit() else nodo[parte]
        if ultima.isdigit():
            nodo[int(ultima)] = valor
        else:
            nodo[ultima] = valor

    return mutar


TIPOS: list[tuple[str, Mutacion, str]] = [
    (
        "enum de ocasión",
        _asignar("novela.personalizacion.ocasion", "divorcio"),
        "novela.personalizacion.ocasion",
    ),
    (
        "enum de subgénero",
        _asignar("novela.tipo_aventura.subgenero.primario", "romance"),
        "novela.tipo_aventura.subgenero.primario",
    ),
    ("enum de tono", _asignar("novela.tono", "terror"), "novela.tono"),
    (
        "enum de narrador",
        _asignar("novela.lenguaje.narrador", "segunda"),
        "novela.lenguaje.narrador",
    ),
    (
        "enum de tipo de hecho",
        _asignar("novela.personalizacion.hechos.0.tipo", "mascota"),
        "novela.personalizacion.hechos.0.tipo",
    ),
    (
        "nivel de contenido 3",
        _asignar("novela.tipo_aventura.contenido.violencia", 3),
        "novela.tipo_aventura.contenido.violencia",
    ),
    ("11 capítulos", _asignar("novela.formato.capitulos", 11), "novela.formato.capitulos"),
    (
        "longitud mínima 900",
        _asignar("novela.formato.longitud_capitulo.min", 900),
        "novela.formato.longitud_capitulo.min",
    ),
    (
        "curva de 9 valores",
        _asignar("novela.formato.curva_tension", [5] * 9),
        "novela.formato.curva_tension",
    ),
    (
        "tensión 11",
        _asignar("novela.formato.curva_tension.0", 11),
        "novela.formato.curva_tension.0",
    ),
    ("idioma distinto", _asignar("novela.lenguaje.idioma", "es-MX"), "novela.lenguaje.idioma"),
    (
        "texto libre confiable",
        _asignar("novela.personalizacion.texto_libre.confiable", True),
        "novela.personalizacion.texto_libre.confiable",
    ),
    (
        "ruta de una sola etapa",
        _asignar("novela.mundo.ruta", [{"id": "faro", "dias_viaje": 0}]),
        "novela.mundo.ruta",
    ),
    (
        "momento mal formado",
        _asignar("novela.personalizacion.hechos.1.momento", "julio 2023"),
        "novela.personalizacion.hechos.1.momento",
    ),
    (
        "tres subgéneros secundarios",
        _asignar("novela.tipo_aventura.subgenero.secundarios", ["nautica", "urbana", "steampunk"]),
        "novela.tipo_aventura.subgenero.secundarios",
    ),
    (
        "dato excluido como clave",
        _asignar("novela.personalizacion.destinatario.telefono", "600000000"),
        "novela.personalizacion.destinatario.telefono",
    ),
]


@pytest.mark.parametrize(("nombre", "mutar", "localizacion"), TIPOS, ids=[t[0] for t in TIPOS])
def test_un_valor_no_permitido_da_un_hallazgo_localizado(
    nombre: str, mutar: Mutacion, localizacion: str
) -> None:
    datos = referencia()
    mutar(datos)
    informe = _validar(datos)
    assert not informe.valido
    assert not puede_salir_de_contexto(informe)
    assert localizacion in [h.localizacion for h in informe.hallazgos]
    hallazgo = next(h for h in informe.hallazgos if h.localizacion == localizacion)
    assert hallazgo.severidad is Severidad.BLOQUEANTE
    assert hallazgo.regla.startswith("RF-23")
    assert hallazgo.esperado


def test_una_clave_obligatoria_ausente() -> None:
    datos = referencia()
    del _n(datos)["tipo_aventura"]["mision"]
    informe = _validar(datos)
    assert "novela.tipo_aventura.mision" in [h.localizacion for h in informe.hallazgos]


# ─── Reglas de coherencia: una inválida por regla ────────────────────────────


def _publico_juvenil(d: dict[str, Any]) -> None:
    _n(d)["publico"] = "juvenil"


def _crossover_infantil(d: dict[str, Any]) -> None:
    _n(d)["publico"] = "crossover"


def _contenido_2_infantil(d: dict[str, Any]) -> None:
    _n(d)["tipo_aventura"]["contenido"]["violencia"] = 2


def _melancolico_infantil(d: dict[str, Any]) -> None:
    _n(d)["tono"] = "melancolico"


def _boda_agridulce(d: dict[str, Any]) -> None:
    _n(d)["personalizacion"]["ocasion"] = "boda"
    _n(d)["estructura"]["desenlace"]["final"] = "agridulce"


def _edad_incoherente(d: dict[str, Any]) -> None:
    _n(d)["personalizacion"]["destinatario"]["edad"] = 12


def _nacimiento_futuro(d: dict[str, Any]) -> None:
    _n(d)["personalizacion"]["destinatario"]["fecha_nacimiento"] = "2027-01-01"
    _n(d)["personalizacion"]["destinatario"]["edad"] = None


def _evento_antes_de_nacer(d: dict[str, Any]) -> None:
    _n(d)["personalizacion"]["hechos"][1]["momento"] = "2017-03"


def _evento_sin_lugar(d: dict[str, Any]) -> None:
    del _n(d)["personalizacion"]["hechos"][1]["lugar"]


def _evento_fuera_del_mundo(d: dict[str, Any]) -> None:
    _n(d)["personalizacion"]["hechos"][1]["lugar"] = "marte"


def _hecho_duplicado(d: dict[str, Any]) -> None:
    _n(d)["personalizacion"]["hechos"][4]["id"] = "h1"


def _seis_obligatorios(d: dict[str, Any]) -> None:
    hechos = _n(d)["personalizacion"]["hechos"]
    hechos[4]["prioridad"] = "obligatorio"
    hechos.append(
        {
            "id": "h6",
            "tipo": "rasgo",
            "texto": "Colecciona conchas",
            "prioridad": "obligatorio",
            "origen": "entrevista",
        }
    )


def _secundario_repite_primario(d: dict[str, Any]) -> None:
    _n(d)["tipo_aventura"]["subgenero"]["secundarios"] = ["tesoro"]


def _tramos_con_hueco(d: dict[str, Any]) -> None:
    _n(d)["estructura"]["nudo"]["capitulos"] = [4, 8]


def _climax_fuera_del_desenlace(d: dict[str, Any]) -> None:
    _n(d)["estructura"]["desenlace"]["climax"] = 7


def _porcentajes_que_no_suman(d: dict[str, Any]) -> None:
    _n(d)["estructura"]["planteamiento"]["porcentaje"] = 30


def _fuente_inexistente(d: dict[str, Any]) -> None:
    _n(d)["personajes"][1]["origen"]["fuente"] = "h9"


def _ficticio_con_fuente(d: dict[str, Any]) -> None:
    _n(d)["personajes"][2]["origen"]["fuente"] = "h3"


def _sin_destinatario(d: dict[str, Any]) -> None:
    _n(d)["personajes"].pop(0)


def _destinatario_corrupto(d: dict[str, Any]) -> None:
    _n(d)["personajes"][0]["arco"] = "corrupcion"


def _destinatario_sin_protagonismo(d: dict[str, Any]) -> None:
    _n(d)["personajes"][0]["rol"] = ["aliado"]


def _micro_colgando_de_macro(d: dict[str, Any]) -> None:
    _n(d)["mundo"]["localizaciones"][4]["padre"] = "comarca"


def _ruta_por_lugar_inexistente(d: dict[str, Any]) -> None:
    _n(d)["mundo"]["ruta"][2]["id"] = "castillo"


def _reglas_en_mundo_contemporaneo(d: dict[str, Any]) -> None:
    _n(d)["mundo"]["reglas"] = [{"regla": "magia", "limites": "una vez", "costes": "cansancio"}]


COHERENCIA: list[tuple[str, Mutacion, str]] = [
    ("público mayor que el lector", _publico_juvenil, "publico_por_edad"),
    ("crossover para un niño", _crossover_infantil, "publico_por_edad"),
    ("contenido 2 en infantil", _contenido_2_infantil, "contenido_por_publico"),
    ("tono melancólico infantil", _melancolico_infantil, "tono_por_edad"),
    ("boda con final agridulce", _boda_agridulce, "final_por_ocasion"),
    ("edad frente a nacimiento", _edad_incoherente, "edad_frente_a_nacimiento"),
    ("nacimiento en el futuro", _nacimiento_futuro, "edad_frente_a_nacimiento"),
    ("evento antes de nacer", _evento_antes_de_nacer, "evento_antes_de_nacer"),
    ("evento sin lugar", _evento_sin_lugar, "evento_con_momento_y_lugar"),
    ("evento fuera del mundo", _evento_fuera_del_mundo, "evento_en_localizacion"),
    ("hecho duplicado", _hecho_duplicado, "hecho_id_unico"),
    ("seis obligatorios", _seis_obligatorios, "hechos_obligatorios"),
    ("secundario repite primario", _secundario_repite_primario, "subgeneros_distintos"),
    ("tramos con hueco", _tramos_con_hueco, "estructura_tramos"),
    ("clímax fuera del desenlace", _climax_fuera_del_desenlace, "estructura_hitos"),
    ("porcentajes que no suman 100", _porcentajes_que_no_suman, "estructura_porcentajes"),
    ("fuente real inexistente", _fuente_inexistente, "personaje_real_con_fuente"),
    ("ficticio con fuente", _ficticio_con_fuente, "personaje_ficticio_sin_fuente"),
    ("destinatario ausente", _sin_destinatario, "destinatario_en_la_novela"),
    ("arco del destinatario", _destinatario_corrupto, "arco_del_destinatario"),
    ("destinatario sin protagonismo", _destinatario_sin_protagonismo, "papel_del_destinatario"),
    ("micro colgando de macro", _micro_colgando_de_macro, "arbol_de_localizaciones"),
    ("ruta por lugar inexistente", _ruta_por_lugar_inexistente, "ruta_sobre_localizaciones"),
    (
        "reglas en mundo realista",
        _reglas_en_mundo_contemporaneo,
        "reglas_solo_en_mundos_no_realistas",
    ),
]


@pytest.mark.parametrize(("nombre", "mutar", "regla"), COHERENCIA, ids=[c[0] for c in COHERENCIA])
def test_cada_regla_de_coherencia_dispara_con_su_caso(
    nombre: str, mutar: Mutacion, regla: str
) -> None:
    datos = referencia()
    mutar(datos)
    informe = _validar(datos)
    assert not informe.valido
    assert informe.contexto is None
    reglas = [h.regla for h in informe.hallazgos]
    assert any(r.endswith(regla) for r in reglas), reglas
    assert all(h.severidad is Severidad.BLOQUEANTE for h in informe.hallazgos)


def test_toda_regla_tiene_su_caso_invalido() -> None:
    # Una regla nueva sin caso en COHERENCIA haría fallar esta prueba.
    sin_caso = set(REGLAS)
    for _, mutar, _ in COHERENCIA:
        datos = referencia()
        mutar(datos)
        for acto, porcentaje in (("planteamiento", 22), ("nudo", 55), ("desenlace", 23)):
            _n(datos)["estructura"][acto].setdefault("porcentaje", porcentaje)
        novela = Contexto.model_validate(datos).novela
        sin_caso -= {r for r in REGLAS if list(r(novela, DIA))}
    assert sin_caso == set()


INVALIDOS: list[tuple[str, Mutacion]] = [(n, m) for n, m, _ in TIPOS + COHERENCIA]


@pytest.mark.parametrize(("nombre", "mutar"), INVALIDOS, ids=[i[0] for i in INVALIDOS])
def test_todo_hallazgo_del_validador_es_bloqueante(nombre: str, mutar: Mutacion) -> None:
    # RF-22: sostiene que `puede_salir_de_contexto` sea solo `informe.valido`. Un hallazgo
    # no bloqueante haría que la guarda tuviera que volver a mirar la severidad.
    datos = referencia()
    mutar(datos)
    informe = _validar(datos)
    assert informe.hallazgos
    assert all(h.severidad is Severidad.BLOQUEANTE for h in informe.hallazgos)


@pytest.mark.parametrize("raiz", [None, [], "novela", 3], ids=["None", "lista", "texto", "número"])
def test_una_raiz_que_no_es_objeto_da_un_hallazgo_bloqueante(raiz: object) -> None:
    informe = _validar(raiz)
    assert [h.severidad for h in informe.hallazgos] == [Severidad.BLOQUEANTE]
    assert not puede_salir_de_contexto(informe)


def test_el_informe_recoge_todos_los_fallos_no_solo_el_primero() -> None:
    datos = referencia()
    _melancolico_infantil(datos)
    _boda_agridulce(datos)
    _ruta_por_lugar_inexistente(datos)
    reglas = {h.regla.split(" · ")[-1] for h in _validar(datos).hallazgos}
    assert {"tono_por_edad", "final_por_ocasion", "ruta_sobre_localizaciones"} <= reglas


def test_la_edad_que_cumple_se_admite() -> None:
    datos = referencia()
    _n(datos)["personalizacion"]["destinatario"]["edad"] = 10
    assert _validar(datos).valido


def test_un_publico_mas_joven_que_el_lector_se_admite() -> None:
    datos = referencia()
    _n(datos)["personalizacion"]["edad_lector"] = 40
    assert _validar(datos).valido


@pytest.mark.parametrize(
    ("edad", "publico"),
    [(0, "infantil"), (11, "infantil"), (12, "juvenil"), (17, "juvenil"), (18, "adulto")],
)
def test_publico_por_edad_en_sus_bordes(edad: int, publico: str) -> None:
    assert publico_por_edad(edad) == publico


# ─── Propiedades: nunca excepción, siempre informe ───────────────────────────

_json = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(max_size=20),
    lambda hijos: (
        st.lists(hijos, max_size=4) | st.dictionaries(st.text(max_size=10), hijos, max_size=4)
    ),
    max_leaves=20,
)


@given(_json)
def test_cualquier_entrada_da_un_informe(datos: object) -> None:
    informe = _validar(datos)
    assert informe.valido == (not informe.hallazgos and informe.contexto is not None)


@settings(max_examples=200)
@given(st.data())
def test_romper_una_hoja_de_la_referencia_nunca_lanza(data: st.DataObject) -> None:
    datos = referencia()
    nodo: Any = _n(datos)
    while isinstance(nodo, dict | list) and nodo:
        claves = list(nodo.keys()) if isinstance(nodo, dict) else list(range(len(nodo)))
        clave = data.draw(st.sampled_from(claves))
        if not isinstance(nodo[clave], dict | list) or data.draw(st.booleans()):
            nodo[clave] = data.draw(_json)
            break
        nodo = nodo[clave]
    informe = _validar(datos)
    assert informe.valido or informe.hallazgos


# ─── Persistencia (RF-28) y esquema generado (D-4) ───────────────────────────


def test_persiste_el_contexto_con_su_version_de_ontologia(tmp_path: Path) -> None:
    conexion = crear_base(tmp_path / "proyecto.sqlite")
    informe = _validar(referencia())
    guardar_contexto(conexion, informe, "2026-09-23T10:00:00Z")
    vigente = contexto_vigente(conexion)
    assert vigente is not None
    assert vigente == (VERSION_ONTOLOGIA, informe.contexto)


def test_un_contexto_invalido_no_se_persiste(tmp_path: Path) -> None:
    conexion = crear_base(tmp_path / "proyecto.sqlite")
    datos = referencia()
    _melancolico_infantil(datos)
    with pytest.raises(ContextoInvalido):
        guardar_contexto(conexion, _validar(datos), "2026-09-23T10:00:00Z")
    assert contexto_vigente(conexion) is None


def test_el_json_schema_se_genera_desde_los_modelos() -> None:
    esquema = Contexto.model_json_schema()
    assert esquema["properties"]["novela"]
    assert "Personalizacion" in esquema["$defs"]
