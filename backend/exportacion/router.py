"""Rutas de `exportacion` (spec-backend-1.md §5.1, plan-frontend §5.1): las versiones publicadas.

Solo lectura. Publicar no tiene ruta propia: se publica al registrar el resultado del
Exportador (TC-4), y el manuscrito lo escribe la publicación y lo sirve
`GET /versiones/{v}/manuscrito` (§3 punto 6), no un `POST /exportar`.
"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter
from fastapi import Path as EnRuta
from fastapi.responses import FileResponse, Response

from backend.exportacion.modelos import CapituloDeVersion, Lectura, Versiones
from backend.exportacion.publicar import leer_fichero, version_existe, versiones_publicadas
from backend.proyecto.abierto import Proyecto
from backend.proyecto.dependencias import ProyectoAbierto, RutaJsonEstricto
from backend.proyecto.errores import CodigoError, NoEncontrado
from backend.proyecto.errores_http import documentar
from backend.proyecto.modelos import ENTERO_MAXIMO
from backend.shared.rutas import LECTURA_JSON, MANUSCRITO, PDF

# Como en /cambios: un entero fuera de rango es 422, no un OverflowError de SQLite (500).
Version = Annotated[int, EnRuta(ge=1, le=ENTERO_MAXIMO)]
Numero = Annotated[int, EnRuta(ge=1, le=10)]

router = APIRouter(
    prefix="/proyectos/{id}",
    tags=["exportacion"],
    responses=documentar(CodigoError.PROYECTO_INEXISTENTE, CodigoError.NO_ENCONTRADO),
    route_class=RutaJsonEstricto,
)


def _fichero(proyecto: Proyecto, version: int, nombre: str) -> Path:
    """El fichero de una versión publicada; `no_encontrado` si la versión no existe."""
    if version < 1 or not version_existe(proyecto.conexion, version):
        raise NoEncontrado(f"no hay una versión {version} publicada")
    ruta = leer_fichero(proyecto.disposicion, version, nombre)
    if ruta is None:
        raise NoEncontrado(f"la versión {version} no tiene {nombre}")
    return ruta


def _lectura(proyecto: Proyecto, version: int) -> Lectura:
    ruta = _fichero(proyecto, version, LECTURA_JSON)
    return Lectura.model_validate_json(ruta.read_text(encoding="utf-8"))


@router.get("/versiones")
def listar_versiones(proyecto: ProyectoAbierto) -> Versiones:
    """RF-96: `{versiones: [{version, publicada, cambiados[]}]}`, ascendentes."""
    return Versiones(versiones=tuple(versiones_publicadas(proyecto.conexion)))


@router.get("/versiones/{version}/lectura", response_class=Response)
def leer_lectura(proyecto: ProyectoAbierto, version: Version) -> Response:
    """RF-97, TC-7: el `lectura.json` de la versión, tal cual está en disco."""
    ruta = _fichero(proyecto, version, LECTURA_JSON)
    return Response(ruta.read_bytes(), media_type="application/json")


@router.get("/versiones/{version}/capitulos/{numero}")
def leer_capitulo(proyecto: ProyectoAbierto, version: Version, numero: Numero) -> CapituloDeVersion:
    """plan-frontend §5.1: un capítulo de la versión, `{numero, titulo, html}`."""
    lectura = _lectura(proyecto, version)
    for capitulo in lectura.capitulos:
        if capitulo.numero == numero:
            return CapituloDeVersion(
                numero=capitulo.numero, titulo=capitulo.titulo, html=capitulo.html
            )
    raise NoEncontrado(f"la versión {version} no tiene capítulo {numero}")


@router.get("/versiones/{version}/manuscrito", response_class=Response)
def leer_manuscrito(proyecto: ProyectoAbierto, version: Version) -> Response:
    """RF-90, §3 punto 6: el manuscrito en Markdown escrito al publicar."""
    ruta = _fichero(proyecto, version, MANUSCRITO)
    return Response(ruta.read_bytes(), media_type="text/markdown; charset=utf-8")


@router.get("/versiones/{version}/pdf", response_class=FileResponse)
def leer_pdf(proyecto: ProyectoAbierto, version: Version) -> FileResponse:
    """RF-98: el PDF de la versión."""
    ruta = _fichero(proyecto, version, PDF)
    return FileResponse(ruta, media_type="application/pdf", filename=f"novela-v{version}.pdf")
