"""Salida del planificador de referencia, coherente con la instancia de definitions.md §12.

Datos ficticios, como los de `backend/contexto/tests/referencia.py`, de la que parte: repite
cada personaje y cada localización del contexto y añade lo que pone el planificador (B-4).
"""

from typing import Any

from backend.contexto.tests.referencia import referencia

_PERSONAJES: dict[str, dict[str, Any]] = {
    "prot": {
        "nombre": "Aitana",
        "alias": ["Aiti"],
        "estado_inicial": "En casa de la abuela, con la brújula",
        "sabe": ["La brújula era del abuelo"],
        "relaciones": [{"destino": "nala", "tipo": "alianza"}],
    },
    "nala": {"nombre": "Nala", "estado_inicial": "Junto a Aitana"},
    "antag": {
        "nombre": "Bruno",
        "alias": ["el Buscador"],
        "estado_inicial": "Rondando el pueblo",
        "relaciones": [{"destino": "prot", "tipo": "rivalidad"}],
    },
}
_LUGARES = {
    "comarca": "Valdeluna",
    "pueblo": "Robledo",
    "bosque": "Bosque de las Hayas",
    "costa": "Costa de Sal",
    "casa_abuela": "Casa de la Abuela",
    "cueva_final": "Cueva del Eco",
    "faro": "Faro de Punta Gris",
    "playa": "Playa de las Conchas",
}
_HITOS = {"casa_abuela": "detonante", "cueva_final": "climax"}


def salida_planificador() -> dict[str, Any]:
    """Una copia nueva cada vez, en JSON: lo que devolvería el planificador."""
    novela = referencia()["novela"]
    lenguaje = novela["lenguaje"]
    return {
        "plan": {
            "modelo": "tres_actos",
            "reparto": {
                "detonante": 1,
                "primer_umbral": 2,
                "punto_medio": 5,
                "crisis": 8,
                "climax": 9,
            },
            "curva_tension": novela["formato"]["curva_tension"],
            "pregunta_dramatica": novela["tema"]["pregunta_dramatica"],
            "tipo_final": "cerrado",
        },
        "personajes": [{**p, **_PERSONAJES[p["id"]]} for p in novela["personajes"]],
        "mundo": {
            "localizaciones": [
                {
                    **loc,
                    "nombre": _LUGARES[loc["id"]],
                    "descripcion": f"Así es {_LUGARES[loc['id']]}.",
                    "hito": _HITOS.get(loc["id"]),
                }
                for loc in novela["mundo"]["localizaciones"]
            ],
            "objetos": [
                {
                    "id": "brujula",
                    "nombre": "Brújula del Abuelo",
                    "alias": ["la brújula"],
                    "poseedor": "prot",
                }
            ],
        },
        "estilo": {
            **lenguaje,
            "metricas": {
                "frase_media_palabras": 14,
                "proporcion_dialogo": 40,
                "descriptivo": 30,
                "legibilidad_min": 70,
            },
            "lista_negra": list(lenguaje["prohibidas"]),
            "onomastica": "Nombres cortos y castellanos",
        },
    }
