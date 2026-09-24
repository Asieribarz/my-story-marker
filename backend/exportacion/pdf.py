"""TC-6, RF-98: el PDF de una versión, imprimiendo su `lectura.html` con Playwright.

Primero el Chromium de Playwright (`uv run playwright install --only-shell chromium`); si
no arranca, el plan B escrito: `channel="msedge"`. `comprobar_pdf` lo averigua una vez por
proceso y lo recuerda; el integrador la llama antes de emitir la orden del Exportador
(TC-3), así que un navegador que falta es una orden `error` con causa `pdf_no_disponible`
que no cambia el estado ni gasta intento.
"""

from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Playwright, sync_playwright
from playwright.sync_api import Error as ErrorPlaywright

from backend.proyecto.manejadores import OrdenNoEmitible

CAUSA = "pdf_no_disponible"
ESPERA_ARRANQUE_MS = 30_000

# (nombre, argumentos de `chromium.launch`), en orden de preferencia.
NAVEGADORES: tuple[tuple[str, dict[str, Any]], ...] = (
    ("chromium", {}),
    ("msedge", {"channel": "msedge"}),
)

_elegido: str | None = None
_fallos: list[str] | None = None


def _no_disponible(motivos: list[str]) -> OrdenNoEmitible:
    return OrdenNoEmitible(CAUSA, None, {"requisito": "RF-98", "intentos": list(motivos)})


def _lanzar(p: Playwright, nombre: str) -> Browser:
    argumentos = dict(NAVEGADORES)[nombre]
    return p.chromium.launch(timeout=ESPERA_ARRANQUE_MS, **argumentos)


def olvidar_comprobacion() -> None:
    """Solo para pruebas: vuelve a averiguar el navegador en la próxima llamada."""
    global _elegido, _fallos
    _elegido, _fallos = None, None


def comprobar_pdf() -> None:
    """TC-3: lanza `OrdenNoEmitible("pdf_no_disponible", None, …)` si no arranca ningún
    navegador. El resultado, bueno o malo, se recuerda en el proceso."""
    navegador_elegido()


def navegador_elegido() -> str:
    """El nombre del primer navegador de `NAVEGADORES` que arranca."""
    global _elegido, _fallos
    if _elegido is not None:
        return _elegido
    if _fallos is not None:
        raise _no_disponible(_fallos)
    fallos: list[str] = []
    try:
        with sync_playwright() as p:
            for nombre, _ in NAVEGADORES:
                try:
                    _lanzar(p, nombre).close()
                except ErrorPlaywright as error:
                    fallos.append(f"{nombre}: {str(error).splitlines()[0][:200]}")
                    continue
                _elegido = nombre
                return nombre
    except ErrorPlaywright as error:
        fallos.append(f"playwright: {str(error).splitlines()[0][:200]}")
    _fallos = fallos
    raise _no_disponible(fallos)


def imprimir_pdf(html: Path, destino: Path) -> None:
    """RF-98: imprime `html` (un fichero local autocontenido) en `destino`, en A4 y con los
    enlaces internos `#cap-NN` como enlaces del PDF. Si no hay navegador o falla la
    impresión, `OrdenNoEmitible` con causa `pdf_no_disponible`."""
    nombre = navegador_elegido()
    try:
        with sync_playwright() as p:
            navegador = _lanzar(p, nombre)
            try:
                pagina = navegador.new_page()
                pagina.goto(html.resolve().as_uri(), wait_until="load")
                pagina.pdf(
                    path=str(destino),
                    format="A4",
                    print_background=True,
                    margin={"top": "2cm", "bottom": "2cm", "left": "2cm", "right": "2cm"},
                )
            finally:
                navegador.close()
    except ErrorPlaywright as error:
        raise _no_disponible([f"{nombre}: {str(error).splitlines()[0][:200]}"]) from error
