"""Un proyecto de referencia listo para publicar, con datos ficticios.

Parte de la biblia de referencia de `capitulo/` (contexto, plan y escaleta guardados por el
camino real), le añade la fila de proyecto en `publicacion` y los diez capítulos aprobados
con su texto en disco. `contrato_lectura` replica el validador del frontend
(`frontend/src/lectura/contrato.js`, plan-frontend §5.2) para comprobar `lectura.json`
sin node.
"""

import re
import sqlite3
from pathlib import Path
from typing import Any

from backend.capitulo.tests.referencia import MOMENTO, biblia_de_referencia
from backend.exportacion.modelos import SalidaExportador
from backend.shared.rutas import DisposicionProyecto

IDENTIFICADOR = "0123456789abcdef0123456789abcdef"

METADATOS = SalidaExportador(
    titulo="La brújula del faro",
    sinopsis="Una niña sigue la aguja de una brújula que no apunta al norte.",
    palabras_clave=("aventura", "faro", "brújula", "mar", "amistad"),
)


def texto_capitulo(numero: int, version: int) -> str:
    """Texto ficticio con todo lo que convierte el conversor, y algo que debe escapar."""
    return (
        f"# El capítulo {numero}\n\n"
        f"Primer párrafo de la versión {version}, con *énfasis* y **fuerza**.\n"
        "Sigue en la misma línea lógica.\n\n"
        "***\n\n"
        "> Una cita del cuaderno.\n\n"
        "Un verso  \nroto <script>alert(1)</script> & fin.\n"
    )


def escribir_version(
    conexion: sqlite3.Connection,
    disposicion: DisposicionProyecto,
    numero: int,
    version: int,
) -> None:
    """La versión `version` del capítulo, aprobada y vigente, con su texto en disco."""
    ruta = disposicion.capitulo(numero, version, 1)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto_capitulo(numero, version), encoding="utf-8", newline="\n")
    conexion.execute(
        "INSERT INTO capitulo_version (capitulo, version, intento, estado, ruta, creado) "
        "VALUES (?, ?, 1, 'aprobado', ?, ?)",
        (numero, version, disposicion.relativa(ruta), MOMENTO),
    )
    conexion.execute(
        "UPDATE capitulo SET estado = 'aprobado', version_vigente = ? WHERE numero = ?",
        (version, numero),
    )


def proyecto_listo(raiz: Path) -> tuple[sqlite3.Connection, DisposicionProyecto]:
    disposicion = DisposicionProyecto.de(IDENTIFICADOR, raiz)
    disposicion.crear_directorios()
    conexion = biblia_de_referencia(disposicion.base)
    conexion.execute(
        "INSERT INTO proyecto (id, identificador, estado, creado) VALUES (1, ?, 'publicacion', ?)",
        (IDENTIFICADOR, MOMENTO),
    )
    for numero in range(1, 11):
        escribir_version(conexion, disposicion, numero, 1)
    return conexion, disposicion


def impresora_falsa(html: Path, destino: Path) -> None:
    destino.write_bytes(b"%PDF-1.4 falso " + html.read_bytes()[:32])


# ─── El contrato del frontend, en Python ─────────────────────────────────────

ETIQUETAS_PERMITIDAS = {"p", "em", "strong", "blockquote", "hr", "br"}
ROLES = {
    "protagonista",
    "antagonista",
    "mentor",
    "aliado",
    "alivio_comico",
    "interes_romantico",
    "guardian_umbral",
    "traidor",
    "secundario",
}
_ETIQUETA = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9-]*)([^>]*)>")
_ATRIBUTO_P = re.compile(r"^\s+data-p=\"([1-9]\d*)\"\s*$")


def errores_html(html: str) -> list[str]:
    errores: list[str] = []
    etiquetas, esperado = 0, 1
    for m in _ETIQUETA.finditer(html):
        etiquetas += 1
        cierre, nombre, atributos = m.group(1), m.group(2).lower(), m.group(3)
        if nombre not in ETIQUETAS_PERMITIDAS:
            errores.append(f"<{nombre}> fuera de la lista blanca")
            continue
        if cierre:
            continue
        if nombre == "p":
            marca = _ATRIBUTO_P.match(atributos)
            if not marca or int(marca.group(1)) != esperado:
                errores.append(f"data-p del párrafo {esperado}")
            esperado += 1
        elif atributos.replace("/", "").strip():
            errores.append(f"<{nombre}> con atributos")
    if esperado == 1:
        errores.append("sin párrafos")
    if html.count("<") != etiquetas:
        errores.append("«<» suelto")
    return errores


def _numeros(lista: Any) -> bool:
    return (
        isinstance(lista, list)
        and all(isinstance(n, int) and 1 <= n <= 10 for n in lista)
        and all(a < b for a, b in zip(lista, lista[1:], strict=False))
    )


def contrato_lectura(dato: Any) -> list[str]:
    """Las reglas de `validarLectura` (plan-frontend §5.2)."""
    errores: list[str] = []
    if not isinstance(dato, dict):
        return ["no es un objeto"]
    version, anterior = dato.get("version"), dato.get("anterior")
    if not isinstance(version, int) or version < 1:
        errores.append("version")
    elif anterior != (None if version == 1 else version - 1):
        errores.append("anterior")
    if not _numeros(dato.get("cambiados")) or (anterior is None and dato["cambiados"]):
        errores.append("cambiados")
    portada = dato.get("portada")
    if not isinstance(portada, dict) or not str(portada.get("titulo", "")).strip():
        errores.append("portada.titulo")
    elif not (portada.get("dedicatoria") is None or isinstance(portada["dedicatoria"], str)):
        errores.append("portada.dedicatoria")
    capitulos = dato.get("capitulos")
    if not isinstance(capitulos, list) or len(capitulos) != 10:
        errores.append("capitulos")
    else:
        for i, c in enumerate(capitulos):
            if c.get("numero") != i + 1:
                errores.append(f"capitulos[{i}].numero")
            if c.get("titulo") is not None and not str(c["titulo"]).strip():
                errores.append(f"capitulos[{i}].titulo")
            errores.extend(f"capitulos[{i}].html: {e}" for e in errores_html(c.get("html", "")))
    for clave in ("personajes", "lugares"):
        ids: set[str] = set()
        for i, e in enumerate(dato.get(clave, [])):
            if not e.get("id") or e["id"] in ids:
                errores.append(f"{clave}[{i}].id")
            ids.add(e.get("id"))
            if not str(e.get("nombre", "")).strip():
                errores.append(f"{clave}[{i}].nombre")
            if not (e.get("descripcion") is None or isinstance(e["descripcion"], str)):
                errores.append(f"{clave}[{i}].descripcion")
            if not _numeros(e.get("capitulos")):
                errores.append(f"{clave}[{i}].capitulos")
            if clave == "personajes" and (
                not e.get("rol") or any(r not in ROLES for r in e["rol"])
            ):
                errores.append(f"personajes[{i}].rol")
        if clave == "lugares":
            padres = {e["id"]: e.get("padre") for e in dato.get("lugares", [])}
            for ident, padre in padres.items():
                if padre is not None and padre not in padres:
                    errores.append(f"lugares.{ident}.padre")
                vistos, actual = {ident}, padre
                while actual is not None and actual in padres:
                    if actual in vistos:
                        errores.append(f"lugares.{ident}: ciclo")
                        break
                    vistos.add(actual)
                    actual = padres[actual]
    return errores
