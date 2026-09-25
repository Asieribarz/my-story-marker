"""Guardar y leer la salida del planificador (RF-30 a RF-33, B-4).

`guardar_planificacion` escribe el plan, la guía y la siembra de la biblia en el capítulo 0
(B-2): personajes con su estado inicial y lo que saben, relaciones, localizaciones con su
nombre, objetos con su poseedor inicial y el glosario con nombres y alias (B-10). Sobre lo
que ya materializó el contexto (B-1) solo actualiza lo que añade el planificador; nunca
toca `origen`, `fuente`, `arco`, `nivel` ni `padre`. Volver a planificar —las notas de
`aprobacion_plan`— sustituye la siembra anterior entera.

La salida llega validada por el manejador del planificador. Si aun así choca con la base
(una clave ajena que no existe, un término repetido en el glosario) se lanza
`SalidaIncoherente` y no se escribe nada.
"""

import json
import sqlite3
from collections.abc import Iterator

from backend.contexto.persistencia import contexto_vigente
from backend.planificacion.modelos import GuiaEstilo, SalidaPlanificador
from backend.shared.db import transaccion
from backend.shared.tipos import CategoriaTermino, TipoTermino

_ORDEN_DE_NIVEL = {"macro": 0, "meso": 1, "micro": 2}


class SalidaIncoherente(ValueError):
    """Una salida validada que la base no admite: se devuelve como fallo de contenido."""


def _json(valor: object) -> str:
    return json.dumps(valor, ensure_ascii=False)


def _terminos(
    salida: SalidaPlanificador,
) -> Iterator[tuple[str, CategoriaTermino, str, TipoTermino]]:
    canonico, alias = TipoTermino.CANONICO, TipoTermino.ALIAS
    for p in salida.personajes:
        yield p.nombre, CategoriaTermino.PERSONAJE, p.id, canonico
        yield from ((a, CategoriaTermino.PERSONAJE, p.id, alias) for a in p.alias)
    for loc in salida.mundo.localizaciones:
        yield loc.nombre, CategoriaTermino.LOCALIZACION, loc.id, canonico
    for o in salida.mundo.objetos:
        yield o.nombre, CategoriaTermino.OBJETO, o.id, canonico
        yield from ((a, CategoriaTermino.OBJETO, o.id, alias) for a in o.alias)


def _glosario(salida: SalidaPlanificador) -> list[tuple[str, str, str, str]]:
    filas: dict[str, tuple[str, str, str, str]] = {}
    for termino, categoria, referencia, tipo in _terminos(salida):
        previa = filas.get(termino)
        if previa is not None and previa[2] != referencia:
            raise SalidaIncoherente(f"el término {termino!r} nombra a {previa[2]} y a {referencia}")
        if previa is None or tipo is TipoTermino.CANONICO:
            filas[termino] = (termino, categoria.value, referencia, tipo.value)
    return list(filas.values())


def _borrar_siembra(conexion: sqlite3.Connection, personajes: set[str], lugares: set[str]) -> None:
    """Lo que escribió una planificación anterior, sin tocar lo materializado del contexto."""
    conexion.execute("DELETE FROM glosario WHERE capitulo = 0")
    conexion.execute("DELETE FROM inventario WHERE capitulo = 0")
    conexion.execute("DELETE FROM personaje_estado WHERE capitulo = 0")
    conexion.execute("DELETE FROM personaje_sabe WHERE capitulo = 0")
    conexion.execute("DELETE FROM localizacion_estado WHERE capitulo = 0")
    conexion.execute("DELETE FROM relacion")
    conexion.execute("DELETE FROM objeto")
    for fila in conexion.execute("SELECT id FROM personaje").fetchall():
        if fila["id"] not in personajes:
            conexion.execute("DELETE FROM personaje WHERE id = ?", (fila["id"],))
    añadidas = conexion.execute("SELECT id, nivel FROM localizacion").fetchall()
    for fila in sorted(añadidas, key=lambda f: -_ORDEN_DE_NIVEL[f["nivel"]]):
        if fila["id"] not in lugares:
            conexion.execute("DELETE FROM localizacion WHERE id = ?", (fila["id"],))


def guardar_planificacion(conexion: sqlite3.Connection, salida: SalidaPlanificador) -> None:
    """RF-30 a RF-33. Exige el contexto validado y materializado; si no, `SalidaIncoherente`."""
    vigente = contexto_vigente(conexion)
    if vigente is None:
        raise SalidaIncoherente("no hay contexto validado que planificar")
    novela = vigente[1].novela
    try:
        with transaccion(conexion):
            _borrar_siembra(
                conexion,
                {p.id for p in novela.personajes},
                {loc.id for loc in novela.mundo.localizaciones},
            )
            _escribir(conexion, salida)
    except sqlite3.IntegrityError as error:
        raise SalidaIncoherente(str(error)) from error


def _escribir(conexion: sqlite3.Connection, salida: SalidaPlanificador) -> None:
    for p in salida.personajes:
        conexion.execute(
            "INSERT INTO personaje (id, nombre, alias, descripcion, origen, fuente, ficha, arco, "
            "evolucion) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (id) DO UPDATE SET "
            "nombre = excluded.nombre, alias = excluded.alias, "
            "descripcion = excluded.descripcion, ficha = excluded.ficha, "
            "evolucion = excluded.evolucion",
            (
                p.id,
                p.nombre,
                _json(list(p.alias)),
                p.descripcion,
                p.origen.tipo,
                p.origen.fuente,
                p.model_dump_json(),
                p.arco.value,
                p.evolucion.model_dump_json() if p.evolucion is not None else None,
            ),
        )
    for p in salida.personajes:
        conexion.execute(
            "INSERT INTO personaje_estado (personaje, capitulo, estado) VALUES (?, 0, ?)",
            (p.id, p.estado_inicial),
        )
        conexion.executemany(
            "INSERT OR IGNORE INTO personaje_sabe (personaje, capitulo, dato) VALUES (?, 0, ?)",
            [(p.id, dato) for dato in p.sabe],
        )
        conexion.executemany(
            "INSERT INTO relacion (origen, destino, tipo, estado_inicial, estado_final) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (p.id, r.destino, r.tipo.value, r.estado_inicial, r.estado_final)
                for r in p.relaciones
            ],
        )
    mundo = salida.mundo
    for loc in sorted(mundo.localizaciones, key=lambda x: _ORDEN_DE_NIVEL[x.nivel.value]):
        conexion.execute(
            "INSERT INTO localizacion (id, nivel, padre, nombre, descripcion, hito) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (id) DO UPDATE SET nombre = excluded.nombre, "
            "descripcion = excluded.descripcion, hito = excluded.hito",
            (
                loc.id,
                loc.nivel.value,
                loc.padre,
                loc.nombre,
                loc.descripcion,
                loc.hito.value if loc.hito else None,
            ),
        )
        if loc.estado_inicial is not None:
            conexion.execute(
                "INSERT INTO localizacion_estado (localizacion, capitulo, estado) VALUES (?, 0, ?)",
                (loc.id, loc.estado_inicial),
            )
    for o in mundo.objetos:
        conexion.execute(
            "INSERT INTO objeto (id, nombre, alias) VALUES (?, ?, ?)",
            (o.id, o.nombre, _json(list(o.alias))),
        )
        conexion.execute(
            "INSERT INTO inventario (objeto, poseedor, capitulo) VALUES (?, ?, 0)",
            (o.id, o.poseedor),
        )
    conexion.executemany(
        "INSERT INTO glosario (termino, categoria, referencia, tipo, capitulo) "
        "VALUES (?, ?, ?, ?, 0)",
        _glosario(salida),
    )
    plan = salida.plan
    conexion.execute(
        "INSERT OR REPLACE INTO plan (id, modelo, reparto, curva_tension, pregunta_dramatica, "
        "tipo_final, contenido) VALUES (1, ?, ?, ?, ?, ?, ?)",
        (
            plan.modelo.value,
            plan.reparto.model_dump_json(),
            _json(list(plan.curva_tension)),
            plan.pregunta_dramatica,
            plan.tipo_final.value,
            salida.model_dump_json(),
        ),
    )
    guia = salida.estilo
    conexion.execute(
        "INSERT OR REPLACE INTO guia_estilo (id, narrador, registro, metricas, lexico, "
        "lista_negra, onomastica, contenido) VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
        (
            guia.narrador.value,
            guia.registro.value,
            guia.metricas.model_dump_json(),
            _json(list(guia.lexico)),
            _json(list(guia.lista_negra)),
            guia.onomastica,
            guia.model_dump_json(),
        ),
    )


def leer_planificacion(conexion: sqlite3.Connection) -> SalidaPlanificador | None:
    """RF-35: el plan completo tal como se guardó —plan, personajes, mundo y guía—, en una
    sola lectura. `None` si aún no hay planificación."""
    fila = conexion.execute("SELECT contenido FROM plan WHERE id = 1").fetchone()
    return None if fila is None else SalidaPlanificador.model_validate_json(fila["contenido"])


def leer_guia(conexion: sqlite3.Connection) -> GuiaEstilo | None:
    fila = conexion.execute("SELECT contenido FROM guia_estilo WHERE id = 1").fetchone()
    return None if fila is None else GuiaEstilo.model_validate_json(fila["contenido"])
