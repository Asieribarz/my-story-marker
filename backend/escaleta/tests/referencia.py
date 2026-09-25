"""Escaleta de referencia: diez fichas coherentes con el contexto y el plan de referencia.

Datos ficticios. Recorre la ruta del contexto (casa, bosque, faro, cueva) a un día por
etapa, planta un presagio en el capítulo 2 y lo cobra en el 9.
"""

from typing import Any

from backend.contexto.tests.referencia import referencia

_LUGAR_Y_DIA = (
    ("casa_abuela", 1),
    ("casa_abuela", 1),
    ("bosque", 2),
    ("bosque", 2),
    ("faro", 3),
    ("faro", 3),
    ("faro", 3),
    ("cueva_final", 4),
    ("cueva_final", 4),
    ("cueva_final", 4),
)
_HITOS = {1: ["detonante"], 2: ["primer_umbral"], 5: ["punto_medio"], 8: ["crisis"], 9: ["climax"]}
_HECHOS = {1: ["h1", "h3"], 2: ["h4"], 3: ["h2"], 10: ["h5"]}


def salida_escaletista() -> dict[str, Any]:
    """Una copia nueva cada vez, en JSON: lo que devolvería el escaletista."""
    formato = referencia()["novela"]["formato"]
    fichas = []
    for numero, (lugar, dia) in enumerate(_LUGAR_Y_DIA, start=1):
        fichas.append(
            {
                "numero": numero,
                "hitos": _HITOS.get(numero, []),
                "objetivo": f"Lo que cambia en el capítulo {numero}",
                "escenas": [{"tipo": "escena", "texto": f"La escena del capítulo {numero}"}],
                "pov": "prot",
                "localizacion": lugar,
                "presentes": ["prot", "nala", *(["antag"] if numero in (8, 9) else [])],
                "mencionados": [],
                "dia": dia,
                "tension": formato["curva_tension"][numero - 1],
                "palabras_objetivo": 1200,
                "cierre": formato["cierre_capitulo"][numero - 1],
                "plantar": (
                    [{"clave": "mapa_oculto", "descripcion": "La caja tiene doble fondo"}]
                    if numero == 2
                    else []
                ),
                "cobrar": ["mapa_oculto"] if numero == 9 else [],
                "hechos": _HECHOS.get(numero, []),
                "traspasos": [],
            }
        )
    return {"fichas": fichas}
