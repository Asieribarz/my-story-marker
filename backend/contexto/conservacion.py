"""B-20 · Conservación del brief: lo que fijó el comprador llega intacto al contexto.

El Agente de Contexto normaliza el brief (`intake`) e instancia la ontología (`contexto`). En
los dos pasos puede cambiar lo que dio el comprador —«corregir» una edad que no cuadra con la
fecha de nacimiento (E5) o tapar un nombre con `[NOMBRE_ANONIMIZADO]` (E4)— y su salida sigue
siendo válida para el validador. Esta comprobación la compara con las respuestas guardadas:

- Cada valor que el comprador dio en `personalizacion` sale igual: el destinatario y el
  segundo destinatario campo a campo, `edad_lector`, `vetos` y `dedicatoria`; `ocasion`,
  `relacion` y `papel` solo si ya eran un valor permitido, porque traducirlos es su trabajo.
- Cada hecho de la entrevista conserva, por su id, `tipo`, `texto`, `prioridad`, `momento` y
  `excluye`. El `lugar` puede pasar a ser el id de una localización (la regla de eventos).
- Cada hecho confirmado del texto libre sale con su `tipo` y su `texto`.
- Cada preferencia dada (`tono`, `subgenero`, `cronologia`, `final`, B-19) sale igual.
- Ninguna cadena de la salida lleva un marcador de anonimización que no viniera del brief.

Un conflicto entre lo que fijó el comprador y una regla de coherencia no lo resuelve el
agente: entre esta regla y la del validador no puede pasar ni cambiando el valor ni sin
cambiarlo, y el proyecto acaba en `detenida` con los dos informes, no en `planificacion`.

La evidencia nombra la clave, nunca el valor: puede ser un dato del comprador (RF-13). El
agente tiene el brief en su entrada para corregirlo.
"""

import json
import re
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from backend.contexto.modelos import Ocasion, Papel, Relacion
from backend.shared.tipos import Hallazgo, Severidad

MARCADOR = re.compile(r"\[[A-ZÁÉÍÓÚÑ_ ]*(?:ANONIMIZAD|OCULT|ELIMINAD)[A-ZÁÉÍÓÚÑ_ ]*\]")
"""Un marcador de anonimización: `[NOMBRE_ANONIMIZADO]`, `[FECHA_OCULTA]`, `[EMAIL_ELIMINADO]`…"""

REGLA = "B-20 · conservacion_del_brief"

_TRADUCIBLES = {
    "ocasion": frozenset(o.value for o in Ocasion),
    "relacion": frozenset(r.value for r in Relacion),
}
_PAPELES = frozenset(p.value for p in Papel)
_CLAVES_LITERALES = ("edad_lector", "vetos", "dedicatoria")
_CAMPOS_DEL_HECHO = ("tipo", "texto", "prioridad", "momento", "excluye")

# Dónde queda cada preferencia del brief (B-19) en la salida de cada paso.
_PREFERENCIAS_EN_EL_CONTEXTO = {
    "tono": ("novela", "tono"),
    "subgenero": ("novela", "tipo_aventura", "subgenero"),
    "cronologia": ("novela", "formato", "cronologia"),
    "final": ("novela", "estructura", "desenlace", "final"),
}
_PREFERENCIAS_EN_LA_NORMALIZACION = {
    clave: ("preferencias", clave) for clave in _PREFERENCIAS_EN_EL_CONTEXTO
}


def en_la_normalizacion(
    respuestas: Mapping[str, Any], confirmados: Sequence[Mapping[str, Any]], salida: object
) -> tuple[Hallazgo, ...]:
    """La salida del paso `intake`: `{personalizacion, preferencias, notas, faltan}`."""
    return _comprobar(
        respuestas, confirmados, salida, ("personalizacion",), _PREFERENCIAS_EN_LA_NORMALIZACION
    )


def en_el_contexto(
    respuestas: Mapping[str, Any], confirmados: Sequence[Mapping[str, Any]], salida: object
) -> tuple[Hallazgo, ...]:
    """La salida del paso `contexto`: el objeto de contexto, `{novela: {...}}`."""
    return _comprobar(
        respuestas,
        confirmados,
        salida,
        ("novela", "personalizacion"),
        _PREFERENCIAS_EN_EL_CONTEXTO,
    )


def _comprobar(
    respuestas: Mapping[str, Any],
    confirmados: Sequence[Mapping[str, Any]],
    salida: object,
    raiz: tuple[str, ...],
    preferencias_en: Mapping[str, tuple[str, ...]],
) -> tuple[Hallazgo, ...]:
    dada = _objeto(respuestas.get("personalizacion"))
    sale = _objeto(_en(salida, raiz))
    prefijo = ".".join(raiz)
    rutas = [
        *_personalizacion(dada, sale, prefijo),
        *_hechos(dada, sale, confirmados, prefijo),
        *_preferencias(_objeto(respuestas.get("preferencias")), salida, preferencias_en),
    ]
    hallazgos = [_hallazgo(ruta, "cambia respecto al brief") for ruta in rutas]
    en_el_brief = set(
        MARCADOR.findall(json.dumps([respuestas, list(confirmados)], ensure_ascii=False))
    )
    hallazgos += [
        _hallazgo(ruta, "marcador de anonimización en lugar de un dato del comprador")
        for ruta, marcador in _marcadores(salida, "")
        if marcador not in en_el_brief
    ]
    return tuple(hallazgos)


def _personalizacion(dada: dict[str, Any], sale: dict[str, Any], prefijo: str) -> Iterator[str]:
    for clave in ("destinatario", "segundo_destinatario"):
        persona = dada.get(clave)
        if not isinstance(persona, dict):
            continue
        suya = _objeto(sale.get(clave))
        for campo, valor in persona.items():
            if campo == "papel" and valor not in _PAPELES:
                continue
            if valor is not None and suya.get(campo) != valor:
                yield f"{prefijo}.{clave}.{campo}"
    for clave in _CLAVES_LITERALES:
        valor = dada.get(clave)
        if valor is not None and sale.get(clave) != valor:
            yield f"{prefijo}.{clave}"
    for clave, permitidos in _TRADUCIBLES.items():
        valor = dada.get(clave)
        if valor in permitidos and sale.get(clave) != valor:
            yield f"{prefijo}.{clave}"


def _hechos(
    dada: dict[str, Any],
    sale: dict[str, Any],
    confirmados: Sequence[Mapping[str, Any]],
    prefijo: str,
) -> Iterator[str]:
    salen = [h for h in sale.get("hechos") or [] if isinstance(h, dict)]
    por_id = {h.get("id"): h for h in salen}
    for hecho in dada.get("hechos") or []:
        if not isinstance(hecho, dict):
            continue
        suyo = por_id.get(hecho.get("id"))
        if suyo is None:
            yield f"{prefijo}.hechos[{hecho.get('id')}]"
            continue
        for campo in _CAMPOS_DEL_HECHO:
            valor = hecho.get(campo)
            if valor is not None and suyo.get(campo) != valor:
                yield f"{prefijo}.hechos[{hecho.get('id')}].{campo}"
    presentes = {(h.get("tipo"), h.get("texto")) for h in salen}
    for indice, hecho in enumerate(confirmados, start=1):
        if (hecho.get("tipo"), hecho.get("texto")) not in presentes:
            yield f"{prefijo}.hechos[confirmado {indice}]"


def _preferencias(
    dadas: dict[str, Any], salida: object, destinos: Mapping[str, tuple[str, ...]]
) -> Iterator[str]:
    for clave, ruta in destinos.items():
        valor = dadas.get(clave)
        if valor is not None and _en(salida, ruta) != valor:
            yield ".".join(ruta)


def _marcadores(valor: object, ruta: str) -> Iterator[tuple[str, str]]:
    if isinstance(valor, str):
        for marcador in MARCADOR.findall(valor):
            yield ruta or "(raíz)", marcador
    elif isinstance(valor, dict):
        for clave, hijo in valor.items():
            yield from _marcadores(hijo, f"{ruta}.{clave}" if ruta else str(clave))
    elif isinstance(valor, list):
        for indice, hijo in enumerate(valor):
            yield from _marcadores(hijo, f"{ruta}[{indice}]")


def _en(datos: object, ruta: tuple[str, ...]) -> object:
    for clave in ruta:
        if not isinstance(datos, dict):
            return None
        datos = datos.get(clave)
    return datos


def _objeto(valor: object) -> dict[str, Any]:
    return valor if isinstance(valor, dict) else {}


def _hallazgo(localizacion: str, evidencia: str) -> Hallazgo:
    return Hallazgo(
        verificador="conservacion",
        severidad=Severidad.BLOQUEANTE,
        regla=REGLA,
        localizacion=localizacion,
        evidencia=evidencia,
        esperado="el valor del brief, tal cual",
    )
