"""B-1: al salir de `contexto`, el contexto validado se materializa en sus tablas.

Personalización y hechos (RF-89); los personajes que fija el contexto y sus localizaciones,
con la ruta y las reglas del mundo; los `evento` que vienen de hechos de tipo evento, con
`capitulo` NULL, que cuenta como capítulo 0 (R-2), y su exclusión (B-18); y los vetos en
`palabra_prohibida` con nivel `novela` (B-12). Personajes y localizaciones van **antes** que
los eventos, para que existan las claves ajenas de `evento.lugar` y `evento.excluye`.

La llama el cerebro dentro de la transacción que registra el contexto. Repetirla da las
mismas filas: lo propio del contexto se sustituye y lo que ya añadió la planificación a un
personaje o una localización (nombre, descripción) se conserva.
"""

import json
import sqlite3

from backend.contexto.modelos import Contexto, NivelEspacial, TipoHecho
from backend.shared.db import transaccion

_ORDEN_DE_NIVEL = {NivelEspacial.MACRO: 0, NivelEspacial.MESO: 1, NivelEspacial.MICRO: 2}


def materializar_contexto(conexion: sqlite3.Connection, contexto: Contexto, momento: str) -> None:
    """B-1. `momento` es el instante del registro; hoy ninguna fila materializada lo guarda.

    Lanza `ValueError` si un `excluye` no apunta a la fuente de un personaje: la validación
    del contexto (regla `exclusion_con_fuente`) lo impide antes.
    """
    novela = contexto.novela
    p = novela.personalizacion
    nombres = {"destinatario": p.destinatario}
    if p.segundo_destinatario is not None:
        nombres["segundo_destinatario"] = p.segundo_destinatario
    por_fuente = {
        pj.origen.fuente: pj.id for pj in novela.personajes if pj.origen.fuente is not None
    }
    with transaccion(conexion):
        conexion.execute(
            "DELETE FROM evento_personaje WHERE evento IN "
            "(SELECT id FROM evento WHERE capitulo IS NULL)"
        )
        conexion.execute("DELETE FROM evento WHERE capitulo IS NULL")
        conexion.execute("DELETE FROM palabra_prohibida WHERE nivel = 'novela'")
        conexion.execute("DELETE FROM ruta")
        conexion.execute("DELETE FROM regla_mundo")
        conexion.execute(
            "INSERT OR REPLACE INTO personalizacion (id, destinatario, segundo_destinatario, "
            "ocasion, relacion, edad_lector, vetos, dedicatoria) VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
            (
                p.destinatario.model_dump_json(),
                p.segundo_destinatario.model_dump_json() if p.segundo_destinatario else None,
                p.ocasion.value,
                p.relacion.value,
                p.edad_lector,
                p.vetos.model_dump_json(),
                p.dedicatoria,
            ),
        )
        for h in p.hechos:
            conexion.execute(
                "INSERT INTO hecho (id, tipo, texto, prioridad, origen, momento, lugar) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (id) DO UPDATE SET tipo = excluded.tipo, "
                "texto = excluded.texto, prioridad = excluded.prioridad, "
                "origen = excluded.origen, momento = excluded.momento, lugar = excluded.lugar",
                (
                    h.id,
                    h.tipo.value,
                    h.texto,
                    h.prioridad.value,
                    h.origen.value,
                    h.momento,
                    h.lugar,
                ),
            )
        for pj in novela.personajes:
            persona = nombres.get(pj.origen.fuente or "")
            nacimiento = persona.fecha_nacimiento if persona is not None else None
            conexion.execute(
                "INSERT INTO personaje (id, nombre, origen, fuente, ficha, arco, evolucion, "
                "fecha_nacimiento) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (id) DO UPDATE "
                "SET nombre = coalesce(personaje.nombre, excluded.nombre), "
                "origen = excluded.origen, fuente = excluded.fuente, arco = excluded.arco, "
                "fecha_nacimiento = excluded.fecha_nacimiento",
                (
                    pj.id,
                    persona.nombre if persona is not None else None,
                    pj.origen.tipo,
                    pj.origen.fuente,
                    pj.model_dump_json(),
                    pj.arco.value,
                    pj.evolucion.model_dump_json() if pj.evolucion is not None else None,
                    nacimiento.isoformat() if nacimiento is not None else None,
                ),
            )
        for loc in sorted(novela.mundo.localizaciones, key=lambda x: _ORDEN_DE_NIVEL[x.nivel]):
            conexion.execute(
                "INSERT INTO localizacion (id, nivel, padre) VALUES (?, ?, ?) "
                "ON CONFLICT (id) DO UPDATE SET nivel = excluded.nivel, padre = excluded.padre",
                (loc.id, loc.nivel.value, loc.padre),
            )
        conexion.executemany(
            "INSERT INTO ruta (posicion, localizacion, dias_viaje) VALUES (?, ?, ?)",
            [(i, e.id, e.dias_viaje) for i, e in enumerate(novela.mundo.ruta, start=1)],
        )
        conexion.executemany(
            "INSERT INTO regla_mundo (regla, limites, costes, excepciones) VALUES (?, ?, ?, ?)",
            [
                (r.regla, r.limites, r.costes, json.dumps(list(r.excepciones), ensure_ascii=False))
                for r in novela.mundo.reglas
            ],
        )
        for h in p.hechos:
            if h.tipo is not TipoHecho.EVENTO:
                continue
            excluye = None
            if h.excluye is not None:
                excluye = por_fuente.get(h.excluye.fuente)
                if excluye is None:
                    raise ValueError(f"el hecho {h.id} excluye una fuente sin personaje")
            conexion.execute(
                "INSERT INTO evento (descripcion, momento, lugar, capitulo, excluye, "
                "tipo_exclusion, hecho) VALUES (?, ?, ?, NULL, ?, ?, ?)",
                (
                    h.texto,
                    h.momento,
                    h.lugar,
                    excluye,
                    h.excluye.tipo.value if h.excluye is not None else None,
                    h.id,
                ),
            )
        vetos = dict.fromkeys((*p.vetos.palabras, *p.vetos.temas))
        conexion.executemany(
            "INSERT INTO palabra_prohibida (termino, nivel) VALUES (?, 'novela')",
            [(termino,) for termino in vetos],
        )
