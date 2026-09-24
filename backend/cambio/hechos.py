"""Aplicar y deshacer el cambio de un hecho (RF-122, AJ-6).

Un hecho vive en dos sitios: la fila de `hecho`, que es la biblia (B-1), y el contexto
validado, del que lee el Recuperador (`personalizacion.hechos`). Los dos cambian juntos, en
la transacción de quien llama. El contexto no se reescribe: se añade una fila nueva de
`contexto`, que pasa a ser la vigente, así que la historia de lo validado se conserva.

- Un cambio sobre un hecho existente cambia su `texto` al valor nuevo; deshacerlo vuelve
  al valor anterior, que el cambio conserva.
- Un hecho nuevo (`origen` = `lector`) entra en `hecho`, en el contexto y en la ficha del
  capítulo del fragmento (`ficha_capitulo_hecho`), para que el Escritor lo reciba y la
  cobertura lo exija; deshacerlo lo quita de los tres y borra sus usos.
- Un hecho nuevo de tipo `evento` con `momento` y un `lugar` del mundo es un recuerdo:
  entra también en `evento` con `capitulo` NULL, como los de B-1, para que llegue a la
  cronología de Lean (RF-91). Sin `momento` o con un lugar que el mundo no tiene, no.
"""

import sqlite3
from collections.abc import Callable
from typing import Any

from backend.contexto.modelos import Contexto, Hecho, OrigenHecho, TipoHecho
from backend.contexto.persistencia import contexto_vigente

HechosDelContexto = tuple[Hecho, ...]


def id_de_hecho_nuevo(cambio: int) -> str:
    """El id del hecho que añade el cambio `cambio`: cabe en el patrón de definitions §9."""
    return f"lector_{cambio}"


def hecho_del_contexto(conexion: sqlite3.Connection, ident: str) -> Hecho | None:
    vigente = contexto_vigente(conexion)
    if vigente is None:
        return None
    return next((h for h in vigente[1].novela.personalizacion.hechos if h.id == ident), None)


def hecho_nuevo(cambio: int, datos: dict[str, Any]) -> Hecho:
    """RF-121: el hecho nuevo que propone el Intérprete, validado contra definitions §9.
    Lanza `pydantic.ValidationError` si no encaja."""
    return Hecho.model_validate({**datos, "id": id_de_hecho_nuevo(cambio), "origen": "lector"})


def _reescribir_contexto(
    conexion: sqlite3.Connection,
    momento: str,
    transformar: Callable[[HechosDelContexto], HechosDelContexto],
) -> None:
    vigente = contexto_vigente(conexion)
    if vigente is None:
        raise LookupError("no hay contexto validado al que aplicar el cambio")
    version, contexto = vigente
    datos = contexto.model_dump(mode="json")
    hechos = transformar(contexto.novela.personalizacion.hechos)
    datos["novela"]["personalizacion"]["hechos"] = [h.model_dump(mode="json") for h in hechos]
    nuevo = Contexto.model_validate(datos)
    conexion.execute(
        "INSERT INTO contexto (version_ontologia, contenido, validado) VALUES (?, ?, ?)",
        (version, nuevo.model_dump_json(), momento),
    )


def cambiar_texto(conexion: sqlite3.Connection, ident: str, texto: str, momento: str) -> None:
    """El hecho `ident` pasa a decir `texto`, en la biblia y en el contexto."""
    conexion.execute("UPDATE hecho SET texto = ? WHERE id = ?", (texto, ident))
    conexion.execute(
        "UPDATE evento SET descripcion = ? WHERE hecho = ? AND capitulo IS NULL", (texto, ident)
    )
    _reescribir_contexto(
        conexion,
        momento,
        lambda hechos: tuple(
            h.model_copy(update={"texto": texto}) if h.id == ident else h for h in hechos
        ),
    )


def anadir(conexion: sqlite3.Connection, hecho: Hecho, capitulo: int, momento: str) -> None:
    """El hecho nuevo del lector entra en la biblia, en el contexto y en la ficha."""
    if hecho.origen is not OrigenHecho.LECTOR:
        raise ValueError("solo un hecho del lector entra por un cambio")
    conexion.execute(
        "INSERT INTO hecho (id, tipo, texto, prioridad, origen, momento, lugar) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            hecho.id,
            hecho.tipo.value,
            hecho.texto,
            hecho.prioridad.value,
            hecho.origen.value,
            hecho.momento,
            hecho.lugar,
        ),
    )
    # En la ficha, si el capítulo la tiene (siempre, tras la escaleta).
    conexion.execute(
        "INSERT OR IGNORE INTO ficha_capitulo_hecho (capitulo, hecho) SELECT :c, :h "
        "WHERE EXISTS (SELECT 1 FROM ficha_capitulo WHERE numero = :c)",
        {"c": capitulo, "h": hecho.id},
    )
    _evento_del_recuerdo(conexion, hecho)
    _reescribir_contexto(conexion, momento, lambda hechos: (*hechos, hecho))


def _evento_del_recuerdo(conexion: sqlite3.Connection, hecho: Hecho) -> None:
    """B-1, B-18 para un hecho del lector: el `evento` de un recuerdo, como en
    `planificacion/materializar.py`, con la exclusión resuelta a su personaje."""
    if hecho.tipo is not TipoHecho.EVENTO or hecho.momento is None or hecho.lugar is None:
        return
    if (
        conexion.execute("SELECT 1 FROM localizacion WHERE id = ?", (hecho.lugar,)).fetchone()
        is None
    ):
        return
    excluye = None
    if hecho.excluye is not None:
        fila = conexion.execute(
            "SELECT id FROM personaje WHERE fuente = ?", (hecho.excluye.fuente,)
        ).fetchone()
        if fila is None:
            return
        excluye = (fila["id"], hecho.excluye.tipo.value)
    conexion.execute(
        "INSERT INTO evento (descripcion, momento, lugar, capitulo, excluye, tipo_exclusion, "
        "hecho) VALUES (?, ?, ?, NULL, ?, ?, ?)",
        (hecho.texto, hecho.momento, hecho.lugar, *(excluye or (None, None)), hecho.id),
    )


def quitar(conexion: sqlite3.Connection, ident: str, momento: str) -> None:
    """AJ-6: deshace `anadir`, con los usos que registró el Bibliotecario de la versión
    fallida."""
    for sql in (
        "DELETE FROM evento_personaje WHERE evento IN (SELECT id FROM evento WHERE hecho = ?)",
        "DELETE FROM evento WHERE hecho = ?",
        "DELETE FROM ficha_capitulo_hecho WHERE hecho = ?",
        "DELETE FROM hecho_uso WHERE hecho = ?",
        "DELETE FROM hecho WHERE id = ?",
    ):
        conexion.execute(sql, (ident,))
    _reescribir_contexto(
        conexion, momento, lambda hechos: tuple(h for h in hechos if h.id != ident)
    )
