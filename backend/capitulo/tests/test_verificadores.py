"""V-15 por regla (R-5), V-26, V-28 y V-7: cada regla de cada verificador con un caso que la
dispara y otro de control que no. Todos los textos y datos son ficticios.
"""

import sqlite3
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from backend.capitulo.biblia import Termino
from backend.capitulo.tests.referencia import MOMENTO, biblia_de_referencia
from backend.capitulo.verificadores import ejecutar, lexico, medidas, nombres, vista_de
from backend.contexto.modelos import Publico
from backend.shared.tipos import CategoriaTermino, Informe, Severidad, TipoTermino


def _reglas(informe: Informe) -> list[str]:
    return [h.regla for h in informe.hallazgos]


def _frases(n: int, frase: str = "Ana mira el mar.") -> str:
    return " ".join([frase] * n)


@pytest.fixture
def conexion(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    base = biblia_de_referencia(tmp_path / "proyecto.sqlite")
    yield base
    base.close()


# ─── RF-70 y RF-79 · longitud ────────────────────────────────────────────────


def test_longitud_fuera_de_rango_y_lejos_del_objetivo() -> None:
    informe = medidas.longitud(_frases(200), 1000, 1500, 1200, 10)  # 800 palabras
    assert _reglas(informe) == ["RF-70 · fuera_de_rango", "RF-70 · lejos_del_objetivo"]
    assert {h.severidad for h in informe.hallazgos} == {Severidad.MEDIA}
    assert informe.metricas == {
        "palabras": 800.0,
        "objetivo": 1200.0,
        "desviacion_palabras": -400.0,
        "desviacion_porcentaje": -33.33,
    }


def test_longitud_dentro_de_rango_pero_lejos_del_objetivo() -> None:
    informe = medidas.longitud(_frases(260), 1000, 1500, 1200, 10)  # 1040 palabras
    assert _reglas(informe) == ["RF-70 · lejos_del_objetivo"]


def test_longitud_de_control() -> None:
    informe = medidas.longitud(_frases(300), 1000, 1500, 1200, 10)
    assert informe.hallazgos == ()
    assert informe.metricas is not None and informe.metricas["desviacion_palabras"] == 0.0


# ─── RF-71 · métricas ────────────────────────────────────────────────────────

_DIALOGO = (
    "—Ven al faro —dijo Ana.\n\nAna mira el mar. Ana mira el mar."  # 3 de 13 palabras, en 3 frases
)


def _metricas(cuerpo: str, **cambios: float) -> Informe:
    valores: dict[str, float] = {
        "frase_media": 4,
        "proporcion_dialogo": 0,
        "legibilidad_min": 0,
    }
    valores.update(cambios)
    return medidas.metricas(
        cuerpo,
        frase_media=valores["frase_media"],
        proporcion_dialogo=int(valores["proporcion_dialogo"]),
        legibilidad_min=valores["legibilidad_min"],
        convencion="raya",
        tolerancia=10,
    )


def test_frase_media_baja_hasta_dos_tolerancias_y_media_por_encima() -> None:
    assert _metricas(_frases(10), frase_media=4.6).hallazgos[0].severidad is Severidad.BAJA
    assert _metricas(_frases(10), frase_media=8).hallazgos[0].severidad is Severidad.MEDIA
    assert _metricas(_frases(10)).hallazgos == ()


def test_proporcion_de_dialogo() -> None:
    informe = _metricas(_DIALOGO, frase_media=13 / 3, proporcion_dialogo=60)
    assert _reglas(informe) == ["RF-71 · proporcion_dialogo"]
    assert informe.metricas is not None and informe.metricas["proporcion_dialogo"] == 23.08
    assert _metricas(_DIALOGO, frase_media=13 / 3, proporcion_dialogo=23).hallazgos == ()


def test_legibilidad_bajo_el_minimo() -> None:
    informe = _metricas(_frases(10), legibilidad_min=150)
    assert _reglas(informe) == ["RF-71 · legibilidad"]
    assert informe.hallazgos[0].severidad is Severidad.MEDIA
    assert _metricas(_frases(10), legibilidad_min=90).hallazgos == ()


# ─── RF-72 · lista negra ─────────────────────────────────────────────────────


def test_lista_negra_con_su_localizacion() -> None:
    informe = lexico.lista_negra("Nada.\n\nY, De repente, llovió.", ("de repente",))
    assert [(h.regla, h.localizacion, h.evidencia) for h in informe.hallazgos] == [
        ("RF-72 · lista_negra", "p2:3", "De repente")
    ]
    assert informe.hallazgos[0].severidad is Severidad.BAJA
    assert lexico.lista_negra("Llovió de pronto.", ("de repente",)).hallazgos == ()


# ─── RF-72a · guardarraíl (V-26) ─────────────────────────────────────────────

_LISTAS = (
    lexico.Prohibida(1, "gilipollas", "global"),
    lexico.Prohibida(2, "porro", "publico"),
    lexico.Prohibida(3, "hospitales", "novela"),
    lexico.Prohibida(4, "imbécil", "global"),
)


@pytest.mark.parametrize(
    ("texto", "regla"),
    [
        ("Le llamó gilipollas.", "RF-72a · global"),
        ("Encontraron porros en la cueva.", "RF-72a · publico"),
        ("Pasó la tarde en el Hospital.", "RF-72a · novela"),
        ("Gritó: ¡IMBECIL!", "RF-72a · global"),
        ("Eran unos imbéciles.", "RF-72a · global"),
    ],
    ids=["global", "publico con plural", "novela en singular", "sin tilde", "plural"],
)
def test_el_guardarrail_dispara_en_cada_nivel_y_variante(texto: str, regla: str) -> None:
    informe = lexico.guardarrail(texto, _LISTAS)
    assert _reglas(informe) == [regla]
    assert informe.hallazgos[0].severidad is Severidad.BLOQUEANTE


@pytest.mark.parametrize(
    "texto", ["El guarda hospitalario les abrió.", "Fumaba en pipa.", "Un porrón de vino."]
)
def test_el_guardarrail_compara_palabras_enteras(texto: str) -> None:
    assert lexico.guardarrail(texto, _LISTAS).hallazgos == ()


def test_las_listas_se_copian_una_vez_con_su_hash(conexion: sqlite3.Connection) -> None:
    lexico.asegurar_listas(conexion, Publico.INFANTIL, MOMENTO)
    lexico.asegurar_listas(conexion, Publico.INFANTIL, MOMENTO)
    copiadas = dict(conexion.execute("SELECT lista, hash FROM lista_guardarrail").fetchall())
    assert copiadas == {"global": lexico.huella("global"), "infantil": lexico.huella("infantil")}
    listas = lexico.prohibidas(conexion, Publico.INFANTIL)
    niveles = {p.nivel for p in listas}
    assert niveles == {"global", "publico", "novela"}
    assert 100 <= sum(p.nivel == "global" for p in listas) <= 200
    # La heroína es la protagonista: la lista infantil no la veta.
    assert lexico.guardarrail("La heroína cruzó el bosque.", listas).hallazgos == ()
    assert lexico.guardarrail("Había un porro en la mesa.", listas).hallazgos != ()


# ─── RF-73 · grafía ──────────────────────────────────────────────────────────

_GLOSARIO = (
    Termino("Aitana", CategoriaTermino.PERSONAJE, "prot", TipoTermino.CANONICO),
    Termino("el Buscador", CategoriaTermino.PERSONAJE, "antag", TipoTermino.ALIAS),
    Termino("Bosque de las Hayas", CategoriaTermino.LOCALIZACION, "bosque", TipoTermino.CANONICO),
)


def test_la_grafia_distinta_de_un_termino_conocido() -> None:
    informe = nombres.grafia("Aitána y el buscador entraron al Bosque De Las Hayas.", _GLOSARIO)
    assert [(h.evidencia, h.localizacion) for h in informe.hallazgos] == [
        ("Aitána", "p1:0"),
        ("Bosque De Las Hayas", "p1:33"),
    ]
    assert {h.severidad for h in informe.hallazgos} == {Severidad.MEDIA}


def test_la_grafia_de_control_no_senala_lo_desconocido() -> None:
    texto = "Aitana y el Buscador entraron al Bosque de las Hayas. Luego llegó Marta."
    assert nombres.grafia(texto, _GLOSARIO).hallazgos == ()


# ─── RF-73a · frases literales (V-28) ────────────────────────────────────────

_FRASE = (("h5", "¡A la aventura, Nala!"),)


def test_la_frase_literal_ausente_es_alta() -> None:
    informe = nombres.frases_literales("—¡A la aventura Nala! —gritó.", _FRASE)
    assert _reglas(informe) == ["RF-73a · frase_ausente"]
    assert informe.hallazgos[0].severidad is Severidad.ALTA
    assert "aventura" not in informe.hallazgos[0].evidencia


def test_la_frase_literal_presente_admite_otros_espacios() -> None:
    texto = "Aitana gritó:\n«¡A la   aventura,\nNala!»"
    assert nombres.frases_literales(texto, _FRASE).hallazgos == ()


# ─── Marcadores de anonimización ─────────────────────────────────────────────


def test_un_marcador_de_anonimizacion_es_bloqueante() -> None:
    informe = nombres.marcadores("Aitana miró.\n\n[NOMBRE_ANONIMIZADO] se levantó.")
    assert _reglas(informe) == ["marcador_de_anonimizacion"]
    assert informe.hallazgos[0].severidad is Severidad.BLOQUEANTE
    assert informe.hallazgos[0].localizacion.startswith("p2")


def test_los_corchetes_de_la_prosa_no_son_marcadores() -> None:
    texto = "Aitana leyó la nota [ilegible] y el cartel [CERRADO] de la cabaña."
    assert nombres.marcadores(texto).hallazgos == ()


# ─── Todos juntos, sobre la vista (V-7) ──────────────────────────────────────


def test_los_deterministas_de_un_capitulo_maximo_terminan_en_segundos(
    conexion: sqlite3.Connection,
) -> None:
    vista = vista_de(conexion, 1, MOMENTO)
    parrafo = "—Vamos al Bosque de las Hayas —dijo Aitana, y sin embargo esperó a Nala."
    cuerpo = "\n\n".join([parrafo] * 250)  # 3.500 palabras: más del doble del máximo
    inicio = time.perf_counter()
    informes = ejecutar(cuerpo, vista)
    assert time.perf_counter() - inicio < 2.0
    assert [i.verificador for i in informes] == [
        "guardarrail",
        "marcadores",
        "frases_literales",
        "longitud",
        "metricas",
        "lista_negra",
        "nombres",
    ]
    assert any(h.regla == "RF-72 · lista_negra" for i in informes for h in i.hallazgos)
