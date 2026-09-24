"""V-35 (RF-77a) por agente de `capitulo/`, RF-77 y B-12 en el Editor, B-15 en el juez y
B-16 en el Bibliotecario. Una salida mal formada no persiste nada y devuelve el fallo que
gasta intento. Todos los textos y datos son ficticios.
"""

import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from backend.capitulo.biblia import actualizar_estado_personaje, escribir_resumen, registrar_fin
from backend.capitulo.tests.referencia import MOMENTO, biblia_de_referencia, verificar
from backend.proyecto.abierto import Proyecto
from backend.proyecto.manejadores import ContextoManejo, Salida, manejador_de
from backend.proyecto.maquina import TipoDesenlace, ViaRegistro
from backend.proyecto.orden import OrdenEmitida
from backend.shared.rutas import DisposicionProyecto
from backend.shared.tipos import Agente, EstadoProyecto

AHORA = datetime(2026, 9, 23, 10, tzinfo=UTC)
TEXTO = "# La brújula\n\nAitana abrió la puerta de la casa.\n\n—¡Vamos! —dijo Nala.\n"


@pytest.fixture
def proyecto(tmp_path: Path) -> Iterator[Proyecto]:
    disposicion = DisposicionProyecto.de("a" * 32, tmp_path)
    disposicion.crear_directorios()
    conexion = biblia_de_referencia(disposicion.base)
    yield Proyecto(disposicion, conexion)
    conexion.close()


def _registrar(
    proyecto: Proyecto,
    agente: Agente,
    salida: object,
    capitulo: int = 1,
    intento: int = 1,
    entrada: dict[str, Any] | None = None,
) -> Salida:
    estado = EstadoProyecto.REVISION if agente is Agente.REVISOR else EstadoProyecto.CAPITULOS
    orden = OrdenEmitida(
        id=1,
        estado=estado,
        agente=agente,
        intento=intento,
        capitulo=capitulo,
        entrada=entrada or {},
        registro=ViaRegistro.SKILL,
        emitida=MOMENTO,
        sello="x:1:1",
    )
    return manejador_de(agente)(ContextoManejo(proyecto, orden, AHORA), salida)


def _versiones(proyecto: Proyecto) -> list[sqlite3.Row]:
    return proyecto.conexion.execute("SELECT * FROM capitulo_version ORDER BY id").fetchall()


def _informes(proyecto: Proyecto) -> dict[str, str | None]:
    filas = proyecto.conexion.execute("SELECT verificador, severidad FROM informe").fetchall()
    return {f["verificador"]: f["severidad"] for f in filas}


# ─── escritor ────────────────────────────────────────────────────────────────


def test_el_escritor_guarda_su_borrador(proyecto: Proyecto) -> None:
    salida = _registrar(proyecto, Agente.ESCRITOR, TEXTO)
    assert salida.desenlace.tipo is TipoDesenlace.ACEPTADO
    (version,) = _versiones(proyecto)
    assert (version["version"], version["intento"], version["estado"]) == (1, 1, "borrador")
    assert version["ruta"] == version["ruta_borrador"] == "capitulos/cap-01/v1-intento1.borrador.md"
    fichero = proyecto.disposicion.absoluta(version["ruta"])
    assert fichero.read_text(encoding="utf-8").startswith("# La brújula\n\nAitana")


@pytest.mark.parametrize("salida", ["Sin título.\n\nTexto.", "# Solo título", {"titulo": "x"}])
def test_el_escritor_mal_formado_es_fallo_de_contenido(proyecto: Proyecto, salida: object) -> None:
    resultado = _registrar(proyecto, Agente.ESCRITOR, salida)
    assert resultado.desenlace.tipo is TipoDesenlace.FALLO_CONTENIDO
    assert resultado.detalle["errores"]
    assert _versiones(proyecto) == []
    assert not any(proyecto.disposicion.capitulos.rglob("*.md"))


# ─── editor-estilo (RF-77) ───────────────────────────────────────────────────


def test_el_editor_verifica_y_acepta(proyecto: Proyecto) -> None:
    _registrar(proyecto, Agente.ESCRITOR, TEXTO)
    salida = _registrar(proyecto, Agente.EDITOR_ESTILO, TEXTO)
    assert salida.desenlace.tipo is TipoDesenlace.ACEPTADO
    (version,) = _versiones(proyecto)
    assert (version["estado"], version["ruta"]) == ("editado", "capitulos/cap-01/v1-intento1.md")
    informes = _informes(proyecto)
    assert set(informes) == {
        "guardarrail",
        "frases_literales",
        "longitud",
        "metricas",
        "lista_negra",
        "nombres",
    }
    assert informes["longitud"] == "media" and informes["guardarrail"] is None
    assert salida.detalle["metricas"]["longitud"]["desviacion_palabras"] < 0


def test_el_editor_mal_formado_no_persiste(proyecto: Proyecto) -> None:
    _registrar(proyecto, Agente.ESCRITOR, TEXTO)
    salida = _registrar(proyecto, Agente.EDITOR_ESTILO, ["no", "es", "markdown"])
    assert salida.desenlace.tipo is TipoDesenlace.FALLO_FORMA
    assert _informes(proyecto) == {}
    assert _versiones(proyecto)[0]["estado"] == "borrador"


def test_un_veto_de_la_novela_corta_por_el_guardarrail_y_se_audita(proyecto: Proyecto) -> None:
    texto = TEXTO + "\nDe pequeña pasó muchos días en Hospitales.\n"
    _registrar(proyecto, Agente.ESCRITOR, texto)
    salida = _registrar(proyecto, Agente.EDITOR_ESTILO, texto)
    assert salida.desenlace.tipo is TipoDesenlace.FALLO_CONTENIDO
    assert salida.desenlace.guardarrail
    assert _versiones(proyecto)[0]["estado"] == "borrador"  # §3 punto 2: no pasa a editado
    (fila,) = proyecto.conexion.execute("SELECT detalle FROM auditoria WHERE tipo = 'guardarrail'")
    detalle: dict[str, Any] = json.loads(fila["detalle"])
    assert set(detalle) == {"capitulo", "version", "intento", "nivel", "palabra", "offset"}
    assert detalle["nivel"] == "novela" and detalle["offset"] == "p3:31"
    assert "hospital" not in fila["detalle"].lower()


def test_una_frase_literal_ausente_corta_sin_ser_del_guardarrail(proyecto: Proyecto) -> None:
    _registrar(proyecto, Agente.ESCRITOR, TEXTO, capitulo=10)
    salida = _registrar(proyecto, Agente.EDITOR_ESTILO, TEXTO, capitulo=10)
    assert salida.desenlace.tipo is TipoDesenlace.FALLO_CONTENIDO
    assert not salida.desenlace.guardarrail
    assert _informes(proyecto)["frases_literales"] == "alta"
    con_frase = TEXTO + "\n—¡A la aventura, Nala! —gritó Aitana.\n"
    salida = _registrar(proyecto, Agente.EDITOR_ESTILO, con_frase, capitulo=10)
    assert salida.desenlace.tipo is TipoDesenlace.ACEPTADO


def test_el_editor_guarda_en_la_version_e_intento_que_leyo(proyecto: Proyecto) -> None:
    """RF-60: el Editor edita el texto que su entrada le mandó leer, aunque haya otro intento
    del Escritor posterior; no el último por id."""
    _registrar(proyecto, Agente.ESCRITOR, TEXTO)
    _registrar(proyecto, Agente.ESCRITOR, TEXTO, intento=2)
    entrada = {"version": 1, "intento_texto": 1, "etapa": "borrador"}
    salida = _registrar(proyecto, Agente.EDITOR_ESTILO, TEXTO, entrada=entrada)
    assert salida.desenlace.tipo is TipoDesenlace.ACEPTADO
    primero, segundo = _versiones(proyecto)
    assert (primero["estado"], primero["ruta"]) == ("editado", "capitulos/cap-01/v1-intento1.md")
    assert segundo["estado"] == "borrador"


# ─── juez-capitulo (B-15) ────────────────────────────────────────────────────


def _juicio(**fallos: list[dict[str, Any]]) -> dict[str, Any]:
    criterios = ("hito", "coherencia", "voz", "contenido")
    return {
        "criterios": [
            {"criterio": c, "cumple": c not in fallos, "hallazgos": fallos.get(c, [])}
            for c in criterios
        ]
    }


_CITA = {"parrafo": 1, "cita": "abrió la puerta", "motivo": "La puerta estaba tapiada."}


@pytest.fixture
def verificado(proyecto: Proyecto) -> Proyecto:
    _registrar(proyecto, Agente.ESCRITOR, TEXTO)
    assert (
        _registrar(proyecto, Agente.EDITOR_ESTILO, TEXTO).desenlace.tipo is TipoDesenlace.ACEPTADO
    )
    return proyecto


def test_el_juez_que_aprueba(verificado: Proyecto) -> None:
    salida = _registrar(verificado, Agente.JUEZ_CAPITULO, _juicio())
    assert salida.desenlace.tipo is TipoDesenlace.ACEPTADO
    assert _versiones(verificado)[0]["estado"] == "verificado"


def test_el_juez_con_un_fallo_de_voz_solo_lo_registra(verificado: Proyecto) -> None:
    salida = _registrar(verificado, Agente.JUEZ_CAPITULO, _juicio(voz=[_CITA]))
    assert salida.desenlace.tipo is TipoDesenlace.ACEPTADO
    assert _informes(verificado)["juez-capitulo"] == "media"


def test_el_juez_con_un_fallo_de_coherencia_rechaza(verificado: Proyecto) -> None:
    salida = _registrar(verificado, Agente.JUEZ_CAPITULO, _juicio(coherencia=[_CITA]))
    assert salida.desenlace.tipo is TipoDesenlace.FALLO_CONTENIDO
    assert _informes(verificado)["juez-capitulo"] == "alta"
    assert salida.detalle["hallazgos"][0]["localizacion"] == "p1"


@pytest.mark.parametrize(
    "salida",
    [
        {"criterios": _juicio()["criterios"][:3]},
        {"criterios": [{**c, "cumple": False} for c in _juicio()["criterios"]]},
        _juicio(hito=[{**_CITA, "cita": "cerró la ventana"}]),
        _juicio(hito=[{**_CITA, "parrafo": 9}]),
    ],
    ids=["falta un criterio", "cumple sin cuadrar", "cita inventada", "párrafo inexistente"],
)
def test_el_juez_mal_formado_no_persiste(verificado: Proyecto, salida: dict[str, Any]) -> None:
    resultado = _registrar(verificado, Agente.JUEZ_CAPITULO, salida)
    assert resultado.desenlace.tipo is TipoDesenlace.FALLO_FORMA
    assert "juez-capitulo" not in _informes(verificado)
    assert _versiones(verificado)[0]["estado"] == "editado"


# ─── bibliotecario (B-16) ────────────────────────────────────────────────────

_RECUENTO = {"registrado": {"eventos": 1, "resumen_capitulo": True}}


def test_el_bibliotecario_sin_lo_exigido_falla_y_con_ello_se_acepta(proyecto: Proyecto) -> None:
    verificar(proyecto.conexion, 1)
    salida = _registrar(proyecto, Agente.BIBLIOTECARIO, _RECUENTO)
    assert salida.desenlace.tipo is TipoDesenlace.FALLO_FORMA
    assert salida.detalle["faltan"] == ["resumen", "dia_fin", "localizacion_fin"]
    escribir_resumen(proyecto.conexion, 1, "capitulo", "Aitana encuentra el mapa.", MOMENTO)
    registrar_fin(proyecto.conexion, 1, 1, "casa_abuela")
    salida = _registrar(proyecto, Agente.BIBLIOTECARIO, _RECUENTO)
    assert salida.desenlace.tipo is TipoDesenlace.ACEPTADO


def test_el_bibliotecario_que_agota_el_tope_no_deja_nada_en_la_biblia(proyecto: Proyecto) -> None:
    """B-16, RF-07a: lo escrito por un Bibliotecario rechazado se queda hasta el siguiente
    intento, que lo borra al emitirse; en el último intento del tope se borra al rechazarlo,
    para que el capítulo siguiente no lo lea."""
    verificar(proyecto.conexion, 1)
    actualizar_estado_personaje(proyecto.conexion, 1, "nala", "herida")
    cuenta = "SELECT count(*) FROM personaje_estado WHERE capitulo = 1"
    _registrar(proyecto, Agente.BIBLIOTECARIO, _RECUENTO, intento=2)
    assert proyecto.conexion.execute(cuenta).fetchone()[0] == 1
    salida = _registrar(proyecto, Agente.BIBLIOTECARIO, {"recuento": 3}, intento=3)
    assert salida.desenlace.tipo is TipoDesenlace.FALLO_FORMA
    assert proyecto.conexion.execute(cuenta).fetchone()[0] == 0


def test_el_bibliotecario_mal_formado(proyecto: Proyecto) -> None:
    verificar(proyecto.conexion, 1)
    salida = _registrar(proyecto, Agente.BIBLIOTECARIO, {"recuento": 3})
    assert salida.desenlace.tipo is TipoDesenlace.FALLO_FORMA


# ─── revisor ─────────────────────────────────────────────────────────────────


def test_el_revisor_crea_una_version_nueva_y_la_verifica(verificado: Proyecto) -> None:
    salida = _registrar(verificado, Agente.REVISOR, TEXTO)
    assert salida.desenlace.tipo is TipoDesenlace.ACEPTADO
    nueva = _versiones(verificado)[-1]
    assert (nueva["version"], nueva["estado"], nueva["ruta_borrador"]) == (2, "editado", None)
    assert verificado.disposicion.absoluta(nueva["ruta"]).is_file()


def test_el_revisor_mal_formado_no_crea_version(verificado: Proyecto) -> None:
    salida = _registrar(verificado, Agente.REVISOR, "")
    assert salida.desenlace.tipo is TipoDesenlace.FALLO_FORMA
    assert len(_versiones(verificado)) == 1


def test_el_revisor_rechazado_repite_en_la_misma_version(verificado: Proyecto) -> None:
    """Un intento del Revisor que los deterministas rechazan no deja hueco: el siguiente va
    en la misma versión, y ninguna queda `editado` sin haber pasado."""
    vetado = TEXTO + "\nDe pequeña pasó muchos días en Hospitales.\n"
    assert (
        _registrar(verificado, Agente.REVISOR, vetado).desenlace.tipo
        is TipoDesenlace.FALLO_CONTENIDO
    )
    salida = _registrar(verificado, Agente.REVISOR, TEXTO, intento=2)
    assert salida.desenlace.tipo is TipoDesenlace.ACEPTADO
    assert [(v["version"], v["intento"], v["estado"]) for v in _versiones(verificado)] == [
        (1, 1, "editado"),
        (2, 1, "borrador"),
        (2, 2, "editado"),
    ]
