"""Longitud (RF-70, RF-79) y métricas de estilo con legibilidad INFLESZ (RF-71, D-6).

- **Longitud:** media si el capítulo sale de `[min, max]` del contexto, y media si se aleja
  del `palabras_objetivo` de la ficha más que la tolerancia. Las `metricas` llevan siempre la
  desviación en palabras y en porcentaje (RF-79).
- **Métricas (B-14):** la frase media se compara en desviación relativa y el diálogo en
  puntos porcentuales, contra la tolerancia del contexto (10 % si no la trae): baja hasta
  dos veces la tolerancia, media por encima. La legibilidad es el índice de Szigriszt-Pazos
  en la escala INFLESZ; bajo el mínimo, media. El mínimo es el mayor entre el de la guía y
  el del público (crossover usa el juvenil). `descriptivo` no se mide en la v1.
"""

import re
from typing import Literal

from backend.capitulo import segmentacion as seg
from backend.contexto.modelos import Publico
from backend.shared.tipos import Hallazgo, Informe, Severidad

TOLERANCIA_POR_DEFECTO = 10
UMBRAL_DE_LEGIBILIDAD = {
    Publico.INFANTIL: 65.0,
    Publico.JUVENIL: 55.0,
    Publico.ADULTO: 40.0,
    Publico.CROSSOVER: 55.0,
}
_FUERTES = frozenset("aeoáéó")
_DEBILES_TONICAS = frozenset("íú")
_VOCALES = re.compile(r"[aeiouáéíóúü]+")


def _hallazgo(
    verificador: str, severidad: Severidad, regla: str, evidencia: str, esperado: str
) -> Hallazgo:
    return Hallazgo(
        verificador=verificador,
        severidad=severidad,
        regla=regla,
        localizacion="capitulo",
        evidencia=evidencia,
        esperado=esperado,
    )


def longitud(cuerpo: str, minimo: int, maximo: int, objetivo: int, tolerancia: int) -> Informe:
    """RF-70 y RF-79 sobre las palabras del cuerpo, sin el título."""
    palabras = seg.contar_palabras(cuerpo)
    desviacion = palabras - objetivo
    porcentaje = round(100 * desviacion / objetivo, 2)
    hallazgos = []
    if not minimo <= palabras <= maximo:
        hallazgos.append(
            _hallazgo(
                "longitud",
                Severidad.MEDIA,
                "RF-70 · fuera_de_rango",
                f"{palabras} palabras",
                f"entre {minimo} y {maximo}",
            )
        )
    if abs(porcentaje) > tolerancia:
        hallazgos.append(
            _hallazgo(
                "longitud",
                Severidad.MEDIA,
                "RF-70 · lejos_del_objetivo",
                f"{palabras} palabras ({porcentaje:+} %)",
                f"{objetivo} ± {tolerancia} %",
            )
        )
    metricas = {
        "palabras": float(palabras),
        "objetivo": float(objetivo),
        "desviacion_palabras": float(desviacion),
        "desviacion_porcentaje": porcentaje,
    }
    return Informe(verificador="longitud", hallazgos=tuple(hallazgos), metricas=metricas)


def silabas(palabra: str) -> int:
    """Sílabas de una palabra española: un núcleo por grupo vocálico, partido en hiato entre
    dos vocales fuertes o junto a una débil tónica. La `y` final cuenta como vocal."""
    minusculas = palabra.lower()
    if minusculas.endswith("y") and len(minusculas) > 1 and minusculas[-2] in "aeiou":
        minusculas = minusculas[:-1] + "i"
    total = 0
    for grupo in _VOCALES.findall(minusculas):
        total += 1
        for a, b in zip(grupo, grupo[1:], strict=False):
            fuertes = a in _FUERTES and b in _FUERTES
            if fuertes or a in _DEBILES_TONICAS or b in _DEBILES_TONICAS:
                total += 1
    return max(total, 1) if any(c.isalpha() for c in palabra) else 0


def inflesz(cuerpo: str) -> float:
    """D-6: perspicuidad de Szigriszt-Pazos, 206,835 − 62,3·sílabas/palabras − palabras/frases."""
    parrafos = seg.parrafos(cuerpo)
    palabras = [p for par in parrafos for p in seg.tokens(par.texto) if not p[0].isdigit()]
    frases = sum(len(seg.frases(par)) for par in parrafos)
    if not palabras or not frases:
        return 0.0
    total = sum(silabas(p) for p in palabras)
    return round(206.835 - 62.3 * total / len(palabras) - len(palabras) / frases, 2)


def _por_tolerancia(desvio: float, tolerancia: int) -> Severidad | None:
    if desvio <= tolerancia:
        return None
    return Severidad.BAJA if desvio <= 2 * tolerancia else Severidad.MEDIA


def metricas(
    cuerpo: str,
    *,
    frase_media: float,
    proporcion_dialogo: int,
    legibilidad_min: float,
    convencion: str,
    tolerancia: int,
) -> Informe:
    """RF-71 contra la guía de estilo (B-14)."""
    parrafos = seg.parrafos(cuerpo)
    palabras = sum(seg.contar_palabras(p.texto) for p in parrafos)
    frases = sum(len(seg.frases(p)) for p in parrafos)
    conv: Literal["raya", "comillas"] = "comillas" if convencion == "comillas" else "raya"
    en_dialogo = sum(seg.contar_palabras(trozo) for p in parrafos for trozo in seg.dialogo(p, conv))
    media = round(palabras / frases, 2) if frases else 0.0
    dialogo = round(100 * en_dialogo / palabras, 2) if palabras else 0.0
    indice = inflesz(cuerpo)
    hallazgos = []
    desvio_frase = 100 * abs(media - frase_media) / frase_media
    severidad = _por_tolerancia(desvio_frase, tolerancia)
    if severidad is not None:
        hallazgos.append(
            _hallazgo(
                "metricas",
                severidad,
                "RF-71 · frase_media",
                f"{media} palabras por frase",
                f"{frase_media} ± {tolerancia} %",
            )
        )
    severidad = _por_tolerancia(abs(dialogo - proporcion_dialogo), tolerancia)
    if severidad is not None:
        hallazgos.append(
            _hallazgo(
                "metricas",
                severidad,
                "RF-71 · proporcion_dialogo",
                f"{dialogo} % de diálogo",
                f"{proporcion_dialogo} ± {tolerancia} puntos",
            )
        )
    if indice < legibilidad_min:
        hallazgos.append(
            _hallazgo(
                "metricas",
                Severidad.MEDIA,
                "RF-71 · legibilidad",
                f"INFLESZ {indice}",
                f"al menos {legibilidad_min}",
            )
        )
    medidas = {
        "frase_media_palabras": media,
        "proporcion_dialogo": dialogo,
        "inflesz": indice,
        "legibilidad_min": legibilidad_min,
    }
    return Informe(verificador="metricas", hallazgos=tuple(hallazgos), metricas=medidas)
