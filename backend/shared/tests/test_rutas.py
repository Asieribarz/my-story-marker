"""Paso 1: la disposición del directorio de proyecto (spec1.md §5.3, V-24)."""

import re
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from backend.shared.rutas import (
    VARIABLE_RAIZ,
    DisposicionProyecto,
    IdentificadorInvalido,
    nuevo_identificador,
    raiz_de_proyectos,
)


def test_un_identificador_nuevo_es_valido(tmp_path: Path) -> None:
    disposicion = DisposicionProyecto.de(nuevo_identificador(), tmp_path)
    assert disposicion.raiz.parent == tmp_path


@given(st.text())
def test_solo_se_acepta_un_identificador_opaco(texto: str) -> None:
    if re.fullmatch(r"[0-9a-f]{32}", texto):
        assert DisposicionProyecto.de(texto, Path("raiz")).identificador == texto
    else:
        with pytest.raises(IdentificadorInvalido):
            DisposicionProyecto.de(texto, Path("raiz"))


@pytest.mark.parametrize("malicioso", ["..", "../otro", "a/b", "A" * 32, "0" * 31, ""])
def test_no_se_escapa_del_directorio_de_proyectos(malicioso: str) -> None:
    with pytest.raises(IdentificadorInvalido):
        DisposicionProyecto.de(malicioso, Path("raiz"))


def test_la_disposicion_es_la_de_la_spec(tmp_path: Path) -> None:
    d = DisposicionProyecto.de("0" * 32, tmp_path)
    assert d.relativa(d.base) == "proyecto.sqlite"
    assert d.relativa(d.capitulo(3, 2, 1)) == "capitulos/cap-03/v2-intento1.md"
    assert d.relativa(d.prompt(3, 2, 1)) == "prompts/cap-03/v2-intento1.prompt.md"
    assert d.relativa(d.desglose(3, 2, 1)) == "prompts/cap-03/v2-intento1.desglose.json"
    assert d.relativa(d.texto_libre) == "brief/texto_libre.txt"
    assert d.relativa(d.peticion(7)) == "cambios/peticion-7.txt"
    assert d.relativa(d.version_novela(2)) == "export/v2"
    assert d.relativa(d.borrador(3, 2, 1)) == "capitulos/cap-03/v2-intento1.borrador.md"
    assert d.relativa(d.prompt_parte(3, 2, 1, 2)) == "prompts/cap-03/v2-intento1.prompt.parte-2.md"
    assert d.relativa(d.pasada(4)) == "verificacion/pasada-4"


@pytest.mark.parametrize(
    ("numero", "version", "intento"), [(0, 1, 1), (11, 1, 1), (1, 0, 1), (1, 1, 4)]
)
def test_rechaza_claves_de_capitulo_fuera_de_rango(numero: int, version: int, intento: int) -> None:
    with pytest.raises(ValueError):
        DisposicionProyecto.de("0" * 32, Path("raiz")).capitulo(numero, version, intento)


def test_una_ruta_guardada_no_sale_del_proyecto(tmp_path: Path) -> None:
    d = DisposicionProyecto.de("0" * 32, tmp_path)
    assert d.absoluta("capitulos/cap-01/v1-intento1.md") == d.capitulo(1, 1, 1).resolve()
    with pytest.raises(ValueError):
        d.absoluta("../" + "1" * 32 + "/proyecto.sqlite")


def test_crear_directorios(tmp_path: Path) -> None:
    d = DisposicionProyecto.de("0" * 32, tmp_path)
    d.crear_directorios()
    for carpeta in (d.capitulos, d.prompts, d.export, d.verificacion, d.brief, d.cambios):
        assert carpeta.is_dir()


def test_la_raiz_se_configura_por_entorno(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(VARIABLE_RAIZ, str(tmp_path))
    assert raiz_de_proyectos() == tmp_path
    assert DisposicionProyecto.de("0" * 32).raiz == tmp_path / ("0" * 32)
