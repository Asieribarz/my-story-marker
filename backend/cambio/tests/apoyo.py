"""Apoyo de las pruebas de `cambio/`: un proyecto ya publicado en su versión 1.

Todos los datos de persona son ficticios (`backend/contexto/tests/referencia.py`). La
versión 1 se coloca directamente en la base —diez capítulos aprobados, la versión de novela
con sus punteros y los usos de hechos—, sin recorrer el grafo: lo que se prueba aquí
empieza en `publicada`.

Usos de hechos en las versiones vigentes: `h1` (la perra) en los capítulos 2 y 5, y `h4` (la
brújula) en el 7. Además, una versión 2 del capítulo 5 que ya no es la vigente usa `h1` en
el 9, para comprobar que solo cuentan las versiones vigentes (V-31).
"""

import sqlite3
from pathlib import Path

from backend.contexto.modelos import VERSION_ONTOLOGIA
from backend.contexto.tests.referencia import referencia
from backend.contexto.validacion import validar
from backend.planificacion.materializar import materializar_contexto
from backend.proyecto.abierto import Proyecto, abrir_proyecto
from backend.proyecto.persistencia import crear_proyecto
from backend.proyecto.tests.apoyo import AHORA, MOMENTO
from backend.shared.db import transaccion

USOS_VIGENTES = {"h1": (2, 5), "h4": (7,)}


def _publicar_v1(conexion: sqlite3.Connection) -> None:
    informe = validar(referencia(), AHORA.date())
    assert informe.contexto is not None, informe.hallazgos
    contexto = informe.contexto
    conexion.execute(
        "INSERT INTO contexto (version_ontologia, contenido, validado) VALUES (?, ?, ?)",
        (VERSION_ONTOLOGIA, contexto.model_dump_json(), MOMENTO),
    )
    materializar_contexto(conexion, contexto, MOMENTO)
    conexion.execute("INSERT INTO version_novela (numero, publicada) VALUES (1, ?)", (MOMENTO,))
    for n in range(1, 11):
        fila = conexion.execute(
            "INSERT INTO capitulo_version (capitulo, version, intento, estado, ruta, creado) "
            "VALUES (?, 1, 1, 'aprobado', ?, ?) RETURNING id",
            (n, f"capitulos/cap-{n:02d}/v1-intento1.md", MOMENTO),
        ).fetchone()
        conexion.execute(
            "INSERT INTO version_novela_capitulo (version_novela, capitulo, capitulo_version) "
            "VALUES (1, ?, ?)",
            (n, fila["id"]),
        )
    conexion.execute("UPDATE capitulo SET estado = 'aprobado', intentos = 0, version_vigente = 1")
    for hecho, capitulos in USOS_VIGENTES.items():
        for n in capitulos:
            conexion.execute(
                "INSERT INTO hecho_uso (hecho, capitulo, version) VALUES (?, ?, 1)", (hecho, n)
            )
    # Una versión que no es la vigente: su uso no cuenta.
    conexion.execute(
        "INSERT INTO capitulo_version (capitulo, version, intento, estado, ruta, creado) "
        "VALUES (9, 2, 1, 'revision_humana', 'capitulos/cap-09/v2-intento1.md', ?)",
        (MOMENTO,),
    )
    conexion.execute("INSERT INTO hecho_uso (hecho, capitulo, version) VALUES ('h1', 9, 2)")
    conexion.execute("UPDATE proyecto SET estado = 'publicada'")


def proyecto_publicado(raiz: Path) -> str:
    """Crea un proyecto en `publicada` con la versión 1 y devuelve su identificador."""
    with crear_proyecto(AHORA, raiz_proyectos=raiz) as proyecto:
        with transaccion(proyecto.conexion) as conexion:
            _publicar_v1(conexion)
        return proyecto.identificador


def abrir(raiz: Path, identificador: str) -> Proyecto:
    return abrir_proyecto(identificador, raiz)


def salida_interprete(cuerpo: object) -> str:
    import json

    return f"```json\n{json.dumps(cuerpo, ensure_ascii=False)}\n```"
