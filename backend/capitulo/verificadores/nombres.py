"""Nombres y grafías (RF-73, solo la regla de grafía por R-2 y B-10) y frases literales
(RF-73a).

- **Grafía (B-10):** un nombre propio es una secuencia de palabras con mayúscula inicial,
  unidas por espacios o por `de`, `del`, `la`, `las`, `los`, `el` e `y`. Si normalizado (B-11,
  sin variantes) coincide con un término del glosario y no está escrito igual, es un hallazgo
  medio. Un término desconocido no se señala (R-2). De cada término del glosario se compara
  su parte con mayúscula: «el Buscador» se busca como «Buscador».
- **Frases literales:** cada hecho `frase` de la ficha tiene que estar en el capítulo tal
  cual. Solo se unifican Unicode, espacios y comillas o apóstrofos tipográficos (B-11).
"""

import re
import unicodedata

from backend.capitulo import segmentacion as seg
from backend.capitulo.biblia import Termino
from backend.capitulo.verificadores.lexico import normalizar
from backend.shared.tipos import Hallazgo, Informe, Severidad

CONECTORES = frozenset({"de", "del", "la", "las", "los", "el", "y"})
_COMILLAS = str.maketrans({"“": '"', "”": '"', "„": '"', "«": '"', "»": '"', "‘": "'", "’": "'"})


def _mayuscula(palabra: str) -> bool:
    return palabra[:1].isupper()


def _nucleo(termino: str) -> str:
    """El término desde su primera palabra con mayúscula."""
    partes = termino.split()
    while partes and not _mayuscula(partes[0]):
        partes.pop(0)
    return " ".join(partes)


def grafia(cuerpo: str, glosario: tuple[Termino, ...]) -> Informe:
    conocidos: dict[str, set[str]] = {}
    for termino in glosario:
        nucleo = _nucleo(termino.termino)
        if nucleo:
            clave = " ".join(normalizar(p) for p in seg.tokens(nucleo))
            conocidos.setdefault(clave, set()).add(" ".join(seg.tokens(nucleo)))
    hallazgos = []
    for parrafo in seg.parrafos(cuerpo):
        palabras = seg.palabras(parrafo)
        i = 0
        while i < len(palabras):
            if not _mayuscula(palabras[i].texto):
                i += 1
                continue
            tramo = [palabras[i]]
            while len(tramo) + i < len(palabras):
                siguiente = palabras[i + len(tramo)]
                previa = tramo[-1]
                hueco = parrafo.texto[previa.inicio + len(previa.texto) : siguiente.inicio]
                une = _mayuscula(siguiente.texto) or siguiente.texto in CONECTORES
                if hueco.strip() or not une:
                    break
                tramo.append(siguiente)
            avance = 1
            for largo in range(len(tramo), 0, -1):
                trozo = tramo[:largo]
                if not _mayuscula(trozo[-1].texto):
                    continue
                escrito = " ".join(p.texto for p in trozo)
                grafias = conocidos.get(" ".join(normalizar(p.texto) for p in trozo))
                if grafias is None:
                    continue
                avance = largo
                if escrito not in grafias:
                    hallazgos.append(
                        Hallazgo(
                            verificador="nombres",
                            severidad=Severidad.MEDIA,
                            regla="RF-73 · grafia",
                            localizacion=seg.localizacion(parrafo.numero, trozo[0].inicio),
                            evidencia=escrito,
                            esperado=" | ".join(sorted(grafias)),
                        )
                    )
                break
            i += avance
    return Informe(verificador="nombres", hallazgos=tuple(hallazgos))


_MARCADOR = re.compile(r"\[[A-ZÁÉÍÓÚÑ_ ]*(?:ANONIMIZAD|OCULT|ELIMINAD)[A-ZÁÉÍÓÚÑ_ ]*\]")


def marcadores(cuerpo: str) -> Informe:
    """Un marcador de anonimización (`[NOMBRE_ANONIMIZADO]`, `[EMAIL_ELIMINADO]`…) en la
    prosa es bloqueante: el modelo tapó un nombre que la novela necesita, y se publicaría."""
    hallazgos = tuple(
        Hallazgo(
            verificador="marcadores",
            severidad=Severidad.BLOQUEANTE,
            regla="marcador_de_anonimizacion",
            localizacion=seg.localizacion(parrafo.numero, m.start()),
            evidencia=m.group(),
            esperado="el nombre de la ficha o del glosario, escrito tal cual",
        )
        for parrafo in seg.parrafos(cuerpo)
        for m in _MARCADOR.finditer(parrafo.texto)
    )
    return Informe(verificador="marcadores", hallazgos=hallazgos)


def literal(texto: str) -> str:
    """B-11 para frases literales: Unicode, espacios y comillas o apóstrofos tipográficos."""
    return " ".join(unicodedata.normalize("NFC", texto).translate(_COMILLAS).split())


def frases_literales(cuerpo: str, frases: tuple[tuple[str, str], ...]) -> Informe:
    """RF-73a: `frases` son (id del hecho, texto) de los hechos `frase` de la ficha. La
    evidencia nombra el hecho, no copia la frase del comprador."""
    texto = literal(" ".join(p.texto for p in seg.parrafos(cuerpo)))
    hallazgos = tuple(
        Hallazgo(
            verificador="frases_literales",
            severidad=Severidad.ALTA,
            regla="RF-73a · frase_ausente",
            localizacion="capitulo",
            evidencia=f"falta la frase del hecho {hecho}",
            esperado="la frase tal cual, con su puntuación",
        )
        for hecho, frase in frases
        if literal(frase) not in texto
    )
    return Informe(verificador="frases_literales", hallazgos=hallazgos)
