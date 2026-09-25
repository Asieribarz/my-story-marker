"""La instancia de referencia: transcripción del YAML de definitions.md §12.

Todos los datos son ficticios, como en el documento. Si §12 cambia, esta transcripción
cambia con él. `validar` recibe JSON, así que las fechas van como texto ISO.
"""

import copy
from typing import Any

HOY = "2026-09-23"

_REFERENCIA: dict[str, Any] = {
    "novela": {
        "personalizacion": {
            "destinatario": {
                "nombre": "Aitana",
                "fecha_nacimiento": "2017-04-12",
                "edad": 9,
                "rasgos": ["curiosa", "testaruda", "le_encantan_los_mapas"],
                "papel": "protagonista",
            },
            "segundo_destinatario": None,
            "ocasion": "cumpleanos",
            "relacion": "hijo",
            "edad_lector": 9,
            "hechos": [
                {
                    "id": "h1",
                    "tipo": "ser_querido",
                    "texto": "Su perra se llama Nala, una galga blanca",
                    "prioridad": "obligatorio",
                    "origen": "entrevista",
                },
                {
                    "id": "h2",
                    "tipo": "evento",
                    "texto": "Aprendió a nadar en la playa el verano de 2023",
                    "momento": "2023-07",
                    "lugar": "playa",
                    "prioridad": "obligatorio",
                    "origen": "entrevista",
                },
                {
                    "id": "h3",
                    "tipo": "lugar",
                    "texto": "La casa de la abuela en el pueblo",
                    "prioridad": "obligatorio",
                    "origen": "entrevista",
                },
                {
                    "id": "h4",
                    "tipo": "objeto",
                    "texto": "Una brújula que le regaló su abuelo",
                    "prioridad": "obligatorio",
                    "origen": "entrevista",
                },
                {
                    "id": "h5",
                    "tipo": "frase",
                    "texto": "¡A la aventura, Nala!",
                    "prioridad": "deseable",
                    "origen": "entrevista",
                },
            ],
            "texto_libre": {"ref": "brief/texto_libre.txt", "confiable": False},
            "vetos": {"palabras": [], "temas": ["hospitales"]},
            "dedicatoria": "Para Aitana, que ya sabe leer mapas. Feliz noveno cumpleaños.",
        },
        "publico": "infantil",
        "tono": "ligero",
        "tipo_aventura": {
            "subgenero": {"primario": "tesoro", "secundarios": ["expedicion"]},
            "mision": "busqueda",
            "macguffin": {
                "nombre": "El mapa de la brújula",
                "descripcion": "Un mapa escondido en la caja de la brújula del abuelo",
                "por_que_importa": "Lleva al tesoro que el abuelo nunca llegó a buscar",
            },
            "conflicto": {
                "externo": ["persona_vs_naturaleza", "persona_vs_persona"],
                "interno": "no sabe pedir ayuda",
            },
            "contenido": {"violencia": 1, "romance": 0, "lenguaje": 0, "sensibles": 0},
        },
        "formato": {
            "palabras_objetivo": 12000,
            "capitulos": 10,
            "longitud_capitulo": {"min": 1000, "max": 1500},
            "cierre_capitulo": [
                "pausa",
                "cliffhanger",
                "giro",
                "cliffhanger",
                "pregunta",
                "giro",
                "cliffhanger",
                "cliffhanger",
                "giro",
                "imagen",
            ],
            "titulacion": "titulado",
            "cronologia": "analepsis",
            "curva_tension": [3, 4, 5, 5, 6, 7, 6, 8, 9, 5],
        },
        "estructura": {
            "modelo": "tres_actos",
            "planteamiento": {
                "capitulos": [1, 2],
                "detonante": "Nala desentierra la caja de la brújula del abuelo",
            },
            "nudo": {"capitulos": [3, 8], "punto_medio": 5, "crisis": 8},
            "desenlace": {"capitulos": [9, 10], "climax": 9, "final": "cerrado"},
        },
        "personajes": [
            {
                "id": "prot",
                "origen": {"tipo": "real", "fuente": "destinatario"},
                "rol": ["protagonista"],
                "deseo": "encontrar el tesoro del mapa",
                "necesidad": "aprender a pedir ayuda",
                "defecto": "testarudez",
                "arco": "positivo",
                "voz": {"registro": "coloquial", "tratamiento": "tu"},
            },
            {
                "id": "nala",
                "origen": {"tipo": "real", "fuente": "h1"},
                "rol": ["aliado"],
                "arco": "plano",
            },
            {
                "id": "antag",
                "origen": {"tipo": "ficticio"},
                "rol": ["antagonista"],
                "deseo": "quedarse con el tesoro antes que nadie",
                "arco": "redencion",
            },
        ],
        "mundo": {
            "tipo": "contemporaneo",
            "epoca": {"fecha_inicio": 2026, "duracion_historia": "tres días"},
            "localizaciones": [
                {"id": "comarca", "nivel": "macro", "padre": None},
                {"id": "pueblo", "nivel": "meso", "padre": "comarca"},
                {"id": "bosque", "nivel": "meso", "padre": "comarca"},
                {"id": "costa", "nivel": "meso", "padre": "comarca"},
                {"id": "casa_abuela", "nivel": "micro", "padre": "pueblo"},
                {"id": "cueva_final", "nivel": "micro", "padre": "bosque"},
                {"id": "faro", "nivel": "micro", "padre": "costa"},
                {"id": "playa", "nivel": "micro", "padre": "costa"},
            ],
            "ruta": [
                {"id": "casa_abuela", "dias_viaje": 0},
                {"id": "bosque", "dias_viaje": 1},
                {"id": "faro", "dias_viaje": 1},
                {"id": "cueva_final", "dias_viaje": 1},
            ],
            "reglas": [],
        },
        "lenguaje": {
            "idioma": "es-ES",
            "narrador": "tercera_limitada",
            "tiempo": "preterito",
            "registro": "estandar",
            "voz": "aventurera_con_humor",
            "dialogo": {"proporcion": 40, "convencion": "raya"},
            "lexico": ["cartografia"],
            "prohibidas": ["de repente", "sin embargo"],
        },
        "tema": {
            "central": "valor_y_amistad",
            "pregunta_dramatica": "¿Encontrará Aitana el tesoro antes de que se lo lleve otro?",
        },
        "control": {
            "validaciones": [
                "cierre_subtramas",
                "chejov",
                "coherencia_temporal",
                "longitud",
                "cobertura_hechos",
            ],
            "lineas_rojas": ["sin_contenido_explicito", "vetos_del_comprador"],
        },
    }
}


def referencia() -> dict[str, Any]:
    """Una copia nueva cada vez: las pruebas la mutan."""
    return copy.deepcopy(_REFERENCIA)
