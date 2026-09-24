"""RF-90 a RF-98: publicar la versión de novela N+1 y leer las publicadas.

Publicación atómica (spec-backend-2 §2.1, supuestos menores): todo se escribe en un
directorio temporal junto a `export/`, se renombra entero a `export/vN` y solo después se
escriben las filas y los punteros. Si algo falla antes del renombrado, el temporal se
borra; si fallan las filas, se borra `export/vN`. Una versión publicada es la que tiene
fila en `version_novela`: un `export/vN` sin fila (un registro deshecho después de
renombrar) no es una versión y la publicación siguiente lo sustituye. Las filas publicadas
no se tocan nunca: los disparadores del esquema lo impiden (RF-95).
"""

import json
import shutil
import sqlite3
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from backend.contexto.modelos import Rol
from backend.contexto.persistencia import contexto_vigente
from backend.exportacion.lectura import (
    CapituloLeido,
    Titulacion,
    documento_html,
    manuscrito_md,
    markdown_a_html,
    titulo_en_lectura,
)
from backend.exportacion.modelos import (
    NUMERO_CAPITULOS,
    CapituloLectura,
    Lectura,
    LugarLectura,
    PersonajeLectura,
    Portada,
    SalidaExportador,
    VersionPublicada,
)
from backend.exportacion.pdf import imprimir_pdf
from backend.proyecto.errores import CodigoError, ErrorProyecto
from backend.shared.db import transaccion
from backend.shared.rutas import (
    CRONOLOGIA,
    LECTURA_HTML,
    LECTURA_JSON,
    MANUSCRITO,
    METADATOS,
    PDF,
    DisposicionProyecto,
)
from backend.shared.tipos import EstadoCapitulo, EstadoProyecto

Impresora = Callable[[Path, Path], None]


class ErrorPublicacion(ErrorProyecto):
    """RF-93, RN-8: no se puede publicar. Fuera de `publicacion`, o con un capítulo sin
    versión aprobada. Es una transición que el grafo no permite: 409."""

    codigo = CodigoError.TRANSICION_INVALIDA
    requisito = "RF-93"


# ─── Lectura de la base ──────────────────────────────────────────────────────


def _punteros_vigentes(conexion: sqlite3.Connection) -> dict[int, sqlite3.Row]:
    """RF-94: por capítulo, la versión vigente aprobada (su último intento)."""
    filas = conexion.execute(
        "SELECT v.id, v.capitulo, v.ruta, v.estado FROM capitulo c "
        "JOIN capitulo_version v ON v.capitulo = c.numero AND v.version = c.version_vigente "
        "WHERE v.id = (SELECT max(id) FROM capitulo_version w "
        "  WHERE w.capitulo = c.numero AND w.version = c.version_vigente) "
        "ORDER BY c.numero"
    ).fetchall()
    return {int(f["capitulo"]): f for f in filas}


def punteros_de(conexion: sqlite3.Connection, version: int) -> dict[int, int]:
    """Capítulo → id de `capitulo_version` de una versión publicada."""
    return {
        int(f["capitulo"]): int(f["capitulo_version"])
        for f in conexion.execute(
            "SELECT capitulo, capitulo_version FROM version_novela_capitulo "
            "WHERE version_novela = ?",
            (version,),
        )
    }


def cambiados_entre(anteriores: Mapping[int, int], nuevos: Mapping[int, int]) -> list[int]:
    """RF-96: los capítulos cambiados son la diferencia de punteros con la anterior."""
    if not anteriores:
        return []
    return sorted(n for n, cv in nuevos.items() if anteriores.get(n) != cv)


def versiones_publicadas(conexion: sqlite3.Connection) -> list[VersionPublicada]:
    """RF-96: las versiones, ascendentes, con sus capítulos cambiados."""
    resultado: list[VersionPublicada] = []
    anteriores: dict[int, int] = {}
    for fila in conexion.execute("SELECT numero, publicada FROM version_novela ORDER BY numero"):
        punteros = punteros_de(conexion, int(fila["numero"]))
        resultado.append(
            VersionPublicada(
                version=int(fila["numero"]),
                publicada=fila["publicada"],
                cambiados=tuple(cambiados_entre(anteriores, punteros)),
            )
        )
        anteriores = punteros
    return resultado


def version_existe(conexion: sqlite3.Connection, version: int) -> bool:
    fila = conexion.execute("SELECT 1 FROM version_novela WHERE numero = ?", (version,))
    return fila.fetchone() is not None


def _personajes(conexion: sqlite3.Connection) -> list[PersonajeLectura]:
    """RF-97: capítulos sacados de `presentes` de cada ficha. Sin deseo, necesidad, herida
    ni defecto (plan-frontend §5.2). Sin nombre todavía, el id."""
    roles_validos = {r.value for r in Rol}
    resultado = []
    for fila in conexion.execute(
        "SELECT id, nombre, descripcion, ficha FROM personaje ORDER BY id"
    ):
        ficha = json.loads(fila["ficha"])
        roles = [r for r in ficha.get("rol", []) if r in roles_validos] or [Rol.SECUNDARIO.value]
        capitulos = [
            int(c["capitulo"])
            for c in conexion.execute(
                "SELECT capitulo FROM ficha_capitulo_personaje "
                "WHERE personaje = ? AND papel = 'presente' ORDER BY capitulo",
                (fila["id"],),
            )
        ]
        resultado.append(
            PersonajeLectura(
                id=fila["id"],
                nombre=fila["nombre"] or fila["id"],
                rol=tuple(Rol(r) for r in roles),
                descripcion=fila["descripcion"],
                capitulos=tuple(capitulos),
            )
        )
    return resultado


def _lugares(conexion: sqlite3.Connection) -> list[LugarLectura]:
    """RF-97: capítulos de la `localizacion` de cada ficha; un `macro` o `meso` puede
    quedarse sin capítulos si solo se pisan sus hijos."""
    resultado = []
    for fila in conexion.execute(
        "SELECT id, nombre, descripcion, padre FROM localizacion ORDER BY id"
    ):
        capitulos = [
            int(c["numero"])
            for c in conexion.execute(
                "SELECT numero FROM ficha_capitulo WHERE localizacion = ? ORDER BY numero",
                (fila["id"],),
            )
        ]
        resultado.append(
            LugarLectura(
                id=fila["id"],
                nombre=fila["nombre"] or fila["id"],
                descripcion=fila["descripcion"],
                padre=fila["padre"],
                capitulos=tuple(capitulos),
            )
        )
    return resultado


def _titulacion_y_dedicatoria(conexion: sqlite3.Connection) -> tuple[Titulacion, str | None]:
    vigente = contexto_vigente(conexion)
    if vigente is None:
        fila = conexion.execute("SELECT dedicatoria FROM personalizacion WHERE id = 1").fetchone()
        return Titulacion.NUMERADO_Y_TITULADO, fila["dedicatoria"] if fila else None
    novela = vigente[1].novela
    return Titulacion.de(novela.formato.titulacion), novela.personalizacion.dedicatoria


def _cambio_en_curso(conexion: sqlite3.Connection, anterior: int) -> int | None:
    """RF-94: el cambio del lector que origina la versión; ninguno en la versión 1."""
    if anterior == 0:
        return None
    fila = conexion.execute(
        "SELECT id FROM cambio_lector WHERE estado = 'regenerando' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return int(fila["id"]) if fila is not None else None


# ─── Publicar ────────────────────────────────────────────────────────────────


def _escribir(ruta: Path, texto: str) -> None:
    ruta.write_text(texto, encoding="utf-8", newline="\n")


def _json(dato: Any) -> str:
    return json.dumps(dato, ensure_ascii=False, indent=2) + "\n"


def publicar(
    conexion: sqlite3.Connection,
    disposicion: DisposicionProyecto,
    metadatos: SalidaExportador,
    momento: str,
) -> int:
    """TC-4, RF-90 a RF-98: publica la versión N+1 y devuelve su número.

    `ErrorPublicacion` fuera de `publicacion` (RF-93) o con un capítulo sin versión
    aprobada (RN-8). Si el PDF no se puede generar, `OrdenNoEmitible("pdf_no_disponible")`
    sin dejar nada a medias."""
    return publicar_con(conexion, disposicion, metadatos, momento, imprimir_pdf)


def publicar_con(
    conexion: sqlite3.Connection,
    disposicion: DisposicionProyecto,
    metadatos: SalidaExportador,
    momento: str,
    imprimir: Impresora,
) -> int:
    """`publicar` con la impresora de PDF inyectada: las pruebas de propiedades (V-30) no
    arrancan un navegador por publicación."""
    fila = conexion.execute("SELECT estado, pasadas FROM proyecto WHERE id = 1").fetchone()
    if fila is None or fila["estado"] != EstadoProyecto.PUBLICACION.value:
        estado = fila["estado"] if fila is not None else "sin proyecto"
        raise ErrorPublicacion(f"solo se publica desde «publicacion»; el proyecto está en {estado}")
    punteros_filas = _punteros_vigentes(conexion)
    sin_aprobar = [
        n
        for n in range(1, NUMERO_CAPITULOS + 1)
        if n not in punteros_filas or punteros_filas[n]["estado"] != EstadoCapitulo.APROBADO.value
    ]
    if sin_aprobar:
        raise ErrorPublicacion(f"capítulos sin versión aprobada (RN-8): {sin_aprobar}")

    anterior = int(
        conexion.execute("SELECT coalesce(max(numero), 0) FROM version_novela").fetchone()[0]
    )
    numero = anterior + 1
    punteros = {n: int(f["id"]) for n, f in punteros_filas.items()}
    cambiados = cambiados_entre(punteros_de(conexion, anterior), punteros)
    titulacion, dedicatoria = _titulacion_y_dedicatoria(conexion)

    leidos = []
    for n in range(1, NUMERO_CAPITULOS + 1):
        ruta = disposicion.absoluta(punteros_filas[n]["ruta"])
        if not ruta.is_file():
            raise ErrorPublicacion(f"falta el texto del capítulo {n}: {punteros_filas[n]['ruta']}")
        leidos.append(CapituloLeido.de_markdown(n, ruta.read_text(encoding="utf-8")))

    lectura = Lectura(
        version=numero,
        anterior=anterior or None,
        cambiados=tuple(cambiados),
        portada=Portada(titulo=metadatos.titulo, dedicatoria=dedicatoria),
        capitulos=tuple(
            CapituloLectura(
                numero=c.numero,
                titulo=titulo_en_lectura(c.titulo, titulacion),
                html=markdown_a_html(c.cuerpo),
            )
            for c in leidos
        ),
        personajes=tuple(_personajes(conexion)),
        lugares=tuple(_lugares(conexion)),
    )

    disposicion.export.mkdir(parents=True, exist_ok=True)
    temporal = disposicion.version_novela_temporal(numero)
    temporal.mkdir()
    try:
        _escribir(
            temporal / MANUSCRITO, manuscrito_md(metadatos.titulo, dedicatoria, leidos, titulacion)
        )
        _escribir(
            temporal / METADATOS,
            _json({**metadatos.model_dump(mode="json"), "version": numero, "publicada": momento}),
        )
        _escribir(temporal / LECTURA_JSON, _json(lectura.model_dump(mode="json")))
        _escribir(temporal / LECTURA_HTML, documento_html(lectura, titulacion))
        pasadas = int(fila["pasadas"])
        if pasadas >= 1:
            lean = disposicion.cronologia_de_pasada(pasadas)
            if lean.is_file():
                shutil.copyfile(lean, temporal / CRONOLOGIA)
        imprimir(temporal / LECTURA_HTML, temporal / PDF)
        destino = disposicion.version_novela(numero)
        if destino.exists():
            shutil.rmtree(destino)  # sin fila en version_novela: no es una versión publicada
        temporal.rename(destino)
    except BaseException:
        shutil.rmtree(temporal, ignore_errors=True)
        raise

    try:
        with transaccion(conexion) as escritura:
            escritura.execute(
                "INSERT INTO version_novela (numero, cambio, publicada) VALUES (?, ?, ?)",
                (numero, _cambio_en_curso(escritura, anterior), momento),
            )
            escritura.executemany(
                "INSERT INTO version_novela_capitulo (version_novela, capitulo, capitulo_version) "
                "VALUES (?, ?, ?)",
                [(numero, n, cv) for n, cv in sorted(punteros.items())],
            )
    except BaseException:
        shutil.rmtree(destino, ignore_errors=True)
        raise
    return numero


def leer_fichero(disposicion: DisposicionProyecto, version: int, nombre: str) -> Path | None:
    ruta = disposicion.fichero_de_version(version, nombre)
    return ruta if ruta.is_file() else None
