"""RF-98, TC-6: un PDF real desde `lectura.html`, con la página de novedades y sus enlaces
internos comprobados con pypdf. Se salta si no arranca ningún navegador (TC-3)."""

from pathlib import Path

import pytest
from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject

from backend.exportacion import pdf
from backend.exportacion.publicar import publicar
from backend.exportacion.tests.apoyo import METADATOS, escribir_version, proyecto_listo
from backend.proyecto.manejadores import OrdenNoEmitible
from backend.shared.rutas import PDF


def _hay_navegador() -> bool:
    try:
        pdf.comprobar_pdf()
    except OrdenNoEmitible:
        return False
    return True


requiere_navegador = pytest.mark.skipif(not _hay_navegador(), reason="sin navegador (TC-3)")


def _enlaces_internos(lector: PdfReader, pagina: int) -> list[int]:
    """Las páginas de destino de los enlaces internos de una página."""
    destinos: list[int] = []
    for anotacion in lector.pages[pagina].get("/Annots", []) or []:
        objeto = anotacion.get_object()
        if objeto.get("/Subtype") != "/Link":
            continue
        destino = objeto.get("/Dest")
        accion = objeto.get("/A")
        if destino is None and isinstance(accion, DictionaryObject):
            destino = accion.get("/D")
        if destino is None:
            continue
        if isinstance(destino, ArrayObject):
            pagina_destino = lector.get_page_number(destino[0].get_object())
        else:
            nombrado = lector.named_destinations[str(destino)]
            pagina_destino = lector.get_destination_page_number(nombrado)
        assert pagina_destino is not None
        destinos.append(pagina_destino)
    return destinos


@requiere_navegador
def test_pdf_real_con_novedades_y_enlaces_internos(tmp_path: Path) -> None:
    conexion, disposicion = proyecto_listo(tmp_path)
    try:
        publicar(conexion, disposicion, METADATOS, "2026-09-23T12:00:00Z")
        escribir_version(conexion, disposicion, 3, 2)
        escribir_version(conexion, disposicion, 7, 2)
        publicar(conexion, disposicion, METADATOS, "2026-09-24T12:00:00Z")
    finally:
        conexion.close()
    lector = PdfReader(disposicion.fichero_de_version(2, PDF))
    assert "Novedades" in lector.pages[0].extract_text()
    destinos = _enlaces_internos(lector, 0)
    assert len(destinos) == 2
    for numero, pagina in zip((3, 7), destinos, strict=True):
        assert pagina > 0
        assert f"El capítulo {numero}" in lector.pages[pagina].extract_text()
    primera = PdfReader(disposicion.fichero_de_version(1, PDF))
    assert "Novedades" not in primera.pages[0].extract_text()


def test_sin_navegador_orden_no_emitible(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-3: ningún navegador arranca → `pdf_no_disponible`, y se recuerda."""
    monkeypatch.setattr(pdf, "NAVEGADORES", (("ninguno", {"channel": "no-existe"}),))
    pdf.olvidar_comprobacion()
    try:
        with pytest.raises(OrdenNoEmitible) as error:
            pdf.comprobar_pdf()
        assert error.value.causa == "pdf_no_disponible" and error.value.capitulo is None
        with pytest.raises(OrdenNoEmitible):
            pdf.comprobar_pdf()
    finally:
        pdf.olvidar_comprobacion()
