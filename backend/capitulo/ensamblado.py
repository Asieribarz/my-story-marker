"""Ensamblado del prompt del Escritor (RF-51 a RF-54, RF-58, RF-59a, RF-59b, D-9, B-8, B-9,
decisiones-backend §4.1.4).

`preparar_prompt` comprueba la continuidad antes de escribir (B-9), pide los bloques a la
recuperación estructurada y a la de similitud, recorta por unidades completas en orden de
prioridad inverso hasta que el total estimado cabe en `TOPE` (RF-53, RF-53a), declara cada
recorte en el desglose y en el propio prompt (RF-54), y escribe en `prompts/` el prompt
entero, sus partes de `LIMITE_PARTE` tokens estimados como mucho y el desglose. Todo lo
cuenta `estimador.estimar_tokens`.
"""

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from backend.capitulo import biblia, estimador, similitud
from backend.capitulo.recuperacion_estructurada import (
    Bloque,
    BloqueVacio,
    bloques_estructurados,
    normalizar,
)
from backend.escaleta.consultas import leer_ficha
from backend.shared.rutas import DisposicionProyecto

TOPE = 100_000
LIMITE_PARTE = 20_000
# Orden de recorte (RF-53): prioridad inversa; a igual prioridad (2) cae antes el informe
# del intento anterior que la guía. La ficha no está: nunca se recorta.
ORDEN_RECORTE = (
    "pasajes",
    "capitulo_anterior",
    "resumen",
    "localizacion",
    "presentes",
    "presagios_inventario",
    "informe_anterior",
    "guia",
)
# RF-59a: constante del código, no se redacta al vuelo.
ENCABEZADO_PASAJES = (
    "Pasajes de capítulos anteriores, incluidos como muestra de voz, ritmo y tratamiento de "
    "estas escenas. **No son estado vigente**: describen la situación tal como era en su "
    "capítulo. El estado actual de personajes, objetos y localizaciones es el de los bloques "
    "anteriores. Ante cualquier discrepancia, manda la ficha."
)
CABECERA = (
    "# Encargo del capítulo {numero}\n\n"
    "Lee todas las secciones antes de escribir. La ficha del capítulo manda sobre todo lo "
    "demás."
)
AVISO_RECORTE = (
    "## Omitido por espacio\n\n"
    "Para no pasar del tope de entrada se ha omitido, entero, lo siguiente: {lista}. Lo que "
    "sí aparece en este encargo está completo."
)


class ErrorEnsamblado(Exception):
    """`causa`: `inconsistencia` (B-9 o un vacío estructurado, RF-50c) o `no_cabe` (D-9)."""

    def __init__(self, causa: str, detalle: dict[str, Any]) -> None:
        self.causa = causa
        self.detalle = detalle
        super().__init__(f"{causa}: {detalle}")


@dataclass(frozen=True)
class PromptPreparado:
    rutas_partes: tuple[Path, ...]
    ruta_completa: Path
    ruta_desglose: Path
    tokens_estimados: int


@dataclass
class _Estado:
    bloques: list[Bloque]
    recortes: list[dict[str, Any]] = field(default_factory=list)
    fuera: dict[str, int] = field(default_factory=dict)


def preparar_prompt(
    conexion: sqlite3.Connection,
    disposicion: DisposicionProyecto,
    numero: int,
    version: int,
    intento: int,
    informe_anterior: str | None,
    momento: str,
) -> PromptPreparado:
    """Ensambla y guarda el prompt de `(numero, version, intento)`. Lanza `ErrorEnsamblado`."""
    try:
        hallazgos = biblia.continuidad_antes_de_escribir(conexion, numero)
        if hallazgos:
            raise ErrorEnsamblado(
                "inconsistencia", {"hallazgos": [h.model_dump(mode="json") for h in hallazgos]}
            )
        originales = bloques_estructurados(conexion, disposicion, numero, informe_anterior)
        ficha = leer_ficha(conexion, numero)
    except BloqueVacio as error:
        raise ErrorEnsamblado(
            "inconsistencia", {"bloque": error.bloque, "motivo": error.motivo}
        ) from error
    except biblia.ErrorBiblia as error:
        raise ErrorEnsamblado("inconsistencia", {"motivo": str(error)}) from error
    assert ficha is not None
    fragmentos = similitud.ordenar(similitud.buscar(conexion, similitud.consulta_de_ficha(ficha)))
    todos = list(originales)
    if fragmentos:  # RF-50c: vacío, sin encabezado ni recorte.
        todos.append(
            Bloque(
                "pasajes",
                "Pasajes recuperados",
                8,
                15000,
                tuple(
                    normalizar(
                        f"Procedencia: capítulo {f.capitulo}, fragmento {f.posicion}.\n\n"
                        + f.texto.strip()
                    )
                    for f in fragmentos
                ),
                divisible=True,
                preambulo=ENCABEZADO_PASAJES,
            )
        )

    estado = _Estado(bloques=list(todos))
    texto = _componer(numero, estado)
    total = estimador.estimar_tokens(texto)
    while total > TOPE:
        if not _recortar(estado):
            detalle = _desglose(
                todos,
                estado,
                fragmentos,
                numero,
                version,
                intento,
                momento,
                total,
                texto,
                disposicion,
                (),
            )
            raise ErrorEnsamblado("no_cabe", detalle)
        texto = _componer(numero, estado)
        total = estimador.estimar_tokens(texto)

    partes = _partir(texto, LIMITE_PARTE)
    rutas = tuple(
        disposicion.prompt_parte(numero, version, intento, i) for i in range(1, len(partes) + 1)
    )
    completa = disposicion.prompt(numero, version, intento)
    ruta_desglose = disposicion.desglose(numero, version, intento)
    completa.parent.mkdir(parents=True, exist_ok=True)
    completa.write_bytes(texto.encode("utf-8"))
    for ruta, parte in zip(rutas, partes, strict=True):
        ruta.write_bytes(parte.encode("utf-8"))
    sobrante = len(partes) + 1  # partes de un ensamblado anterior del mismo intento
    while (vieja := disposicion.prompt_parte(numero, version, intento, sobrante)).exists():
        vieja.unlink()
        sobrante += 1
    detalle = _desglose(
        todos,
        estado,
        fragmentos,
        numero,
        version,
        intento,
        momento,
        total,
        texto,
        disposicion,
        rutas,
    )
    ruta_desglose.write_bytes(
        (json.dumps(detalle, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    )
    return PromptPreparado(rutas, completa, ruta_desglose, total)


def _componer(numero: int, estado: _Estado) -> str:
    secciones = [CABECERA.format(numero=numero), *(b.texto() for b in estado.bloques)]
    if estado.recortes:
        omitidos = sorted({r["titulo"] for r in estado.recortes})
        secciones.append(AVISO_RECORTE.format(lista="; ".join(omitidos)))
    return "\n\n".join(secciones) + "\n"


def _recortar(estado: _Estado) -> bool:
    """Quita una unidad completa: un fragmento de la cola en los pasajes, el bloque entero en
    los demás (RF-53a). `False` si solo queda la ficha."""
    for ident in ORDEN_RECORTE:
        indice = next((i for i, b in enumerate(estado.bloques) if b.id == ident), None)
        if indice is None:
            continue
        bloque = estado.bloques[indice]
        if bloque.divisible and len(bloque.unidades) > 1:
            unidad = bloque.unidades[-1]
            estado.bloques[indice] = replace(bloque, unidades=bloque.unidades[:-1])
            tokens, unidades = estimador.estimar_tokens(unidad), 1
        else:
            del estado.bloques[indice]
            tokens, unidades = estimador.estimar_tokens(bloque.texto()), len(bloque.unidades)
        estado.fuera[ident] = estado.fuera.get(ident, 0) + tokens
        estado.recortes.append(
            {"bloque": ident, "titulo": bloque.titulo, "unidades": unidades, "tokens": tokens}
        )
        return True
    return False


def _desglose(
    todos: list[Bloque],
    estado: _Estado,
    fragmentos: tuple[similitud.Fragmento, ...],
    numero: int,
    version: int,
    intento: int,
    momento: str,
    total: int,
    texto: str,
    disposicion: DisposicionProyecto,
    partes: tuple[Path, ...],
) -> dict[str, Any]:
    """RF-59b: por bloque, id, tokens finales, esperado y lo que quedó fuera; el total, los
    recortes en orden y los fragmentos de similitud con su capítulo y posición."""
    emitidos = {b.id: b for b in estado.bloques}
    pasajes = emitidos.get("pasajes")
    return {
        "capitulo": numero,
        "version": version,
        "intento": intento,
        "momento": momento,
        "estimador": {"motor": estimador.motor(), "factor": estimador.FACTOR},
        "tope": TOPE,
        "total": total,
        "sha256": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
        "prompt": disposicion.relativa(disposicion.prompt(numero, version, intento)),
        "partes": [
            {
                "ruta": disposicion.relativa(r),
                "tokens": estimador.estimar_tokens(r.read_bytes().decode("utf-8")),
            }
            for r in partes
        ],
        "bloques": [
            {
                "id": b.id,
                "titulo": b.titulo,
                "prioridad": b.prioridad,
                "esperado": b.esperado,
                "tokens": estimador.estimar_tokens(emitidos[b.id].texto())
                if b.id in emitidos
                else 0,
                "recortado": b.id in estado.fuera,
                "fuera": estado.fuera.get(b.id, 0),
            }
            for b in todos
        ],
        "recortes": [{k: v for k, v in r.items() if k != "titulo"} for r in estado.recortes],
        "similitud": [
            {
                "capitulo": f.capitulo,
                "posicion": f.posicion,
                "emitido": pasajes is not None and i < len(pasajes.unidades),
            }
            for i, f in enumerate(fragmentos)
        ],
    }


def _partir(texto: str, limite: int) -> list[str]:
    """§4.1.4: trozos consecutivos cuya concatenación es `texto`, cada uno de `limite`
    tokens estimados como mucho, cortados por párrafo (o por línea, o por caracteres, solo si
    un párrafo no cabe)."""
    partes: list[str] = []
    actual: list[str] = []
    suma = 0
    for segmento in _segmentos(texto, limite):
        tokens = estimador.estimar_tokens(segmento)
        if actual and suma + tokens > limite:
            partes.append("".join(actual))
            actual, suma = [], 0
        actual.append(segmento)
        suma += tokens
    if actual:
        partes.append("".join(actual))
    # La suma por segmento aproxima; se comprueba cada parte entera y se corrige.
    corregidas: list[str] = []
    for parte in partes:
        trozos = _segmentos(parte, limite)
        while trozos:
            n = len(trozos)
            while n > 1 and estimador.estimar_tokens("".join(trozos[:n])) > limite:
                n -= 1
            corregidas.append("".join(trozos[:n]))
            trozos = trozos[n:]
    return corregidas


def _segmentos(texto: str, limite: int) -> list[str]:
    salida: list[str] = []
    for parrafo in re.split(r"(?<=\n\n)", texto):
        if not parrafo:
            continue
        if estimador.estimar_tokens(parrafo) <= limite:
            salida.append(parrafo)
            continue
        for linea in parrafo.splitlines(keepends=True):
            if estimador.estimar_tokens(linea) <= limite:
                salida.append(linea)
            else:
                # Peor caso de o200k con respaldo de bytes: 4 tokens por carácter × 1,35.
                paso = max(1, limite // 6)
                salida.extend(linea[i : i + paso] for i in range(0, len(linea), paso))
    return salida
