"""El manejador del Intérprete de cambios (RF-121, RF-05a, V-29).

Valida la salida contra el esquema cerrado de `modelos.py` y deja el cambio en `propuesto`:
la siguiente orden es entonces `esperar_humano` con `confirmacion_cambio`. Lo que el
Intérprete escribe sale de una petición no confiable, así que:

- el informe de la orden (`detalle`, que ve el orquestador) no repite ningún valor suyo:
  solo el caso, el hecho y los errores de forma, sin el valor recibido;
- el hecho que cambia tiene que existir, y el valor nuevo tiene que encajar en su esquema
  de definitions §9; `valor_anterior` es el que tiene el hecho, no el que diga el agente;
- un valor con forma de dato excluido (email, teléfono, documento…, RF-13) se rechaza.

Un caso `ninguno`, o cualquier salida inválida, es un intento fallido: al tercero, el
proyecto vuelve a `publicada` con el cambio fallido (RF-05a, Q6).
"""

import json

from pydantic import ValidationError

from backend.cambio import hechos
from backend.cambio.consultas import cambio_en_curso
from backend.cambio.modelos import VALIDADOR_INTERPRETE, CambioDeHecho, HechoNuevo
from backend.contexto.modelos import Hecho
from backend.intake.datos_excluidos import descartes_de_texto
from backend.proyecto.manejadores import ContextoManejo, Manejador, Salida
from backend.proyecto.maquina import Desenlace
from backend.shared.tipos import Agente, EstadoCambio


def _errores(error: ValidationError) -> list[str]:
    """Ruta y mensaje de cada error, sin el valor recibido."""
    return [
        f"{'.'.join(str(parte) for parte in e['loc']) or '(raíz)'}: {e['msg']}"
        for e in error.errors(include_url=False)
    ]


def _con_datos_excluidos(*textos: str | None) -> list[dict[str, str]]:
    return [
        {"tipo": d.tipo, "campo": d.campo}
        for texto in textos
        if texto
        for d in descartes_de_texto(texto, "valor_nuevo")
    ]


def _interprete(contexto: ContextoManejo, resultado: object) -> Salida:
    fila = cambio_en_curso(contexto.conexion)
    if fila is None or fila["estado"] != EstadoCambio.INTERPRETANDO:
        return Salida(Desenlace.forma(), {"errores": ["(raíz): no hay cambio que interpretar"]})
    cambio = int(fila["id"])
    try:
        salida = VALIDADOR_INTERPRETE.validate_python(resultado)
    except ValidationError as error:
        return Salida(Desenlace.forma(), {"errores": _errores(error)})

    if isinstance(salida, CambioDeHecho):
        vigente = hechos.hecho_del_contexto(contexto.conexion, salida.hecho)
        if vigente is None:
            return Salida(Desenlace.forma(), {"errores": ["hecho: no es un hecho vigente"]})
        if salida.valor_nuevo == vigente.texto:
            return Salida(Desenlace.forma(), {"errores": ["valor_nuevo: igual al vigente"]})
        try:
            Hecho.model_validate({**vigente.model_dump(), "texto": salida.valor_nuevo})
        except ValidationError as error:
            return Salida(Desenlace.forma(), {"errores": _errores(error)})
        descartes = _con_datos_excluidos(salida.valor_nuevo)
        if descartes:
            return Salida(Desenlace.forma(), {"descartes": descartes})
        contexto.conexion.execute(
            "UPDATE cambio_lector SET hecho = ?, valor_anterior = ?, valor_nuevo = ?, "
            "estado = ? WHERE id = ?",
            (vigente.id, vigente.texto, salida.valor_nuevo, EstadoCambio.PROPUESTO.value, cambio),
        )
        coincide = salida.valor_anterior == vigente.texto
        return Salida(
            Desenlace.aceptado(),
            {"cambio": cambio, "tipo": "cambio", "hecho": vigente.id, "anterior_exacto": coincide},
        )

    if isinstance(salida, HechoNuevo):
        try:
            nuevo = hechos.hecho_nuevo(cambio, salida.hecho.model_dump(mode="json"))
        except ValidationError as error:
            return Salida(Desenlace.forma(), {"errores": _errores(error)})
        descartes = _con_datos_excluidos(nuevo.texto, nuevo.lugar)
        if descartes:
            return Salida(Desenlace.forma(), {"descartes": descartes})
        contexto.conexion.execute(
            "UPDATE cambio_lector SET hecho_nuevo = ?, valor_nuevo = ?, estado = ? WHERE id = ?",
            (
                json.dumps(nuevo.model_dump(mode="json"), ensure_ascii=False),
                nuevo.texto,
                EstadoCambio.PROPUESTO.value,
                cambio,
            ),
        )
        # El destino es siempre el capítulo del fragmento (RF-121), diga lo que diga.
        return Salida(Desenlace.aceptado(), {"cambio": cambio, "tipo": "nuevo", "hecho": nuevo.id})

    return Salida(Desenlace.forma(), {"errores": ["(raíz): la petición no es un cambio de hechos"]})


MANEJADORES: dict[Agente, Manejador] = {Agente.INTERPRETE_CAMBIOS: _interprete}
