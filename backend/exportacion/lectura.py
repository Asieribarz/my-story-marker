"""TC-7: un único modelo de lectura escrito dos veces, y el manuscrito en Markdown.

- `markdown_a_html`: el conversor propio del subconjunto cerrado de decisiones-backend §4.3.
  Solo emite `p`, `em`, `strong`, `blockquote`, `hr` y `br`; todo lo demás llega escapado.
  Cada `<p>` lleva `data-p` desde 1: los párrafos son los de `capitulo/segmentacion.py`
  (B-14), así que `data-p` es el `p<n>` de los hallazgos y el `parrafo` del juez.
- `documento_html`: `lectura.html` autocontenido (CSS dentro, anclas `#cap-NN`), con la
  página de novedades delante si hay capítulos cambiados (RF-98). Es la fuente del PDF.
- `manuscrito_md`: RF-90 con la titulación del contexto; sin prólogo, epílogo ni
  interludios, fuera de la v1 (§3 punto 8).
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from html import escape

from backend.capitulo import segmentacion as seg
from backend.exportacion.modelos import Lectura

_BLOQUES = re.compile(r"\n[ \t]*\n")  # el mismo corte que segmentacion.parrafos (B-14)
_FUERTE = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
_ENFASIS_ASTERISCO = re.compile(r"(?<!\*)\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?!\*)")
_ENFASIS_GUION = re.compile(r"(?<![\w])_(?=\S)(.+?)(?<=\S)_(?![\w])")


class Titulacion(StrEnum):
    """§3 punto 8: los valores cerrados de `formato.titulacion` en la v1."""

    NUMERADO = "numerado"
    TITULADO = "titulado"
    NUMERADO_Y_TITULADO = "numerado_y_titulado"

    @classmethod
    def de(cls, valor: str) -> "Titulacion":
        """Un valor fuera de la lista (el modelo del contexto aún admite texto libre) se
        trata como `numerado_y_titulado`, que no pierde información."""
        try:
            return cls(valor)
        except ValueError:
            return cls.NUMERADO_Y_TITULADO


def titulo_en_lectura(titulo: str | None, titulacion: Titulacion) -> str | None:
    """plan-frontend §5.2: `titulo` es `null` si la titulación es `numerado`."""
    return None if titulacion is Titulacion.NUMERADO or not titulo else titulo


def encabezado(numero: int, titulo: str | None, titulacion: Titulacion) -> str:
    """RF-90: el encabezado de un capítulo según la titulación del contexto."""
    visible = titulo_en_lectura(titulo, titulacion)
    if visible is None:
        return f"Capítulo {numero}"
    if titulacion is Titulacion.TITULADO:
        return visible
    return f"Capítulo {numero}. {visible}"


def ancla_capitulo(numero: int) -> str:
    return f"cap-{numero:02d}"


# ─── Conversor Markdown → HTML ───────────────────────────────────────────────


def _en_linea(texto: str) -> str:
    """Escapa y después marca `**fuerte**`, `*énfasis*` y `_énfasis_`. Los asteriscos o
    guiones bajos sueltos se quedan como texto."""
    escapado = escape(texto, quote=True)
    escapado = _FUERTE.sub(r"<strong>\1</strong>", escapado)
    escapado = _ENFASIS_ASTERISCO.sub(r"<em>\1</em>", escapado)
    return _ENFASIS_GUION.sub(r"<em>\1</em>", escapado)


def _lineas_a_html(lineas: list[str]) -> str:
    """Un salto de línea dentro de un párrafo es un espacio; con dos espacios o una barra
    invertida al final, `<br>` (salto duro de Markdown)."""
    partes: list[str] = []
    for i, linea in enumerate(lineas):
        duro = linea.endswith(("  ", "\\")) and i < len(lineas) - 1
        limpia = linea.rstrip().removesuffix("\\").strip() if duro else linea.strip()
        partes.append(_en_linea(" ".join(limpia.split())))
        if i < len(lineas) - 1:
            partes.append("<br>" if duro else " ")
    return "".join(partes).strip()


def _es_cita(lineas: list[str]) -> bool:
    return all(linea.lstrip().startswith(">") for linea in lineas)


def markdown_a_html(cuerpo: str) -> str:
    """El cuerpo de un capítulo (sin su `# título`) como fragmento HTML de lista blanca.

    Un bloque es lo separado por una línea en blanco. El separador de escena es `<hr>`, un
    título que quede dentro se omite (no es párrafo en B-14), un bloque cuyas líneas empiezan
    todas por `>` es `<blockquote>` con su párrafo, y el resto, `<p>`. Si la numeración no
    coincide con la de `segmentacion.parrafos`, falla: `data-p` no puede mentir."""
    salida: list[str] = []
    numero = 0
    for bruto in _BLOQUES.split(cuerpo.replace("\r\n", "\n")):
        bloque = bruto.strip()
        if not bloque:
            continue
        if not seg.parrafos(bloque):
            # No es párrafo para B-14: separador de escena o título.
            if not bloque.startswith("#"):
                salida.append("<hr>")
            continue
        numero += 1
        lineas = bloque.split("\n")
        if _es_cita(lineas):
            dentro = [linea.lstrip()[1:].removeprefix(" ") for linea in lineas]
            salida.append(
                f'<blockquote><p data-p="{numero}">{_lineas_a_html(dentro)}</p></blockquote>'
            )
        else:
            salida.append(f'<p data-p="{numero}">{_lineas_a_html(lineas)}</p>')
    esperados = len(seg.parrafos(cuerpo))
    if numero != esperados:
        raise ValueError(f"el conversor numera {numero} párrafos y B-14 cuenta {esperados}")
    return "".join(salida)


# ─── Capítulo leído y manuscrito ─────────────────────────────────────────────


@dataclass(frozen=True)
class CapituloLeido:
    """El texto vigente de un capítulo publicado: su título (`# …`) y el cuerpo."""

    numero: int
    titulo: str | None
    cuerpo: str

    @classmethod
    def de_markdown(cls, numero: int, markdown: str) -> "CapituloLeido":
        titulo, cuerpo = seg.separar_titulo(markdown)
        return cls(numero, titulo, cuerpo)


def manuscrito_md(
    titulo: str,
    dedicatoria: str | None,
    capitulos: Iterable[CapituloLeido],
    titulacion: Titulacion,
) -> str:
    """RF-90: el manuscrito entero, con el título de la novela y la dedicatoria delante."""
    partes = [f"# {titulo}"]
    if dedicatoria:
        partes.append(f"*{dedicatoria.strip()}*")
    for capitulo in capitulos:
        partes.append(f"## {encabezado(capitulo.numero, capitulo.titulo, titulacion)}")
        partes.append(capitulo.cuerpo.strip())
    return "\n\n".join(partes) + "\n"


# ─── lectura.html ────────────────────────────────────────────────────────────

_CSS = """
:root { color-scheme: light; }
body { margin: 0; background: #fdfcf8; color: #222; font: 17px/1.6 Georgia, "Times New Roman",
  serif; }
main { max-width: 38em; margin: 0 auto; padding: 2em 1em 4em; }
section { margin: 0 0 3em; }
h1, h2, h3 { font-weight: normal; line-height: 1.25; }
.portada { text-align: center; padding: 6em 0 4em; }
.portada h1 { font-size: 2.2em; margin: 0 0 1.5em; }
.dedicatoria { font-style: italic; }
.capitulo p { margin: 0; text-indent: 1.5em; }
.capitulo p[data-p="1"], .capitulo hr + p { text-indent: 0; }
blockquote { margin: 1em 2em; font-style: italic; }
blockquote p { text-indent: 0; }
hr { border: 0; text-align: center; margin: 1.5em 0; }
hr::after { content: "* * *"; letter-spacing: .5em; }
nav ol, nav ul, .fichas ul { padding-left: 1.2em; }
.fichas dt { font-weight: bold; margin-top: 1em; }
.fichas dd { margin: .2em 0 0 1.2em; }
a { color: #1f4e79; }
@media print {
  body { background: #fff; font-size: 12pt; }
  main { max-width: none; padding: 0; }
  section { break-after: page; }
}
"""


def _enlaces_a_capitulos(numeros: Iterable[int]) -> str:
    enlaces = [f'<a href="#{ancla_capitulo(n)}">{n}</a>' for n in numeros]
    return ", ".join(enlaces) if enlaces else "—"


def _novedades(lectura: Lectura, titulacion: Titulacion) -> str:
    """RF-98: la página de novedades, con un enlace interno a cada capítulo cambiado."""
    titulos = {c.numero: c.titulo for c in lectura.capitulos}
    elementos = "".join(
        f'<li><a href="#{ancla_capitulo(n)}">'
        f"{escape(encabezado(n, titulos.get(n), titulacion))}</a></li>"
        for n in lectura.cambiados
    )
    return (
        '<section id="novedades" class="novedades">'
        f"<h2>Novedades de la versión {lectura.version}</h2>"
        f"<p>Capítulos que cambian respecto a la versión {lectura.anterior}:</p>"
        f"<ul>{elementos}</ul></section>"
    )


def _fichas(lectura: Lectura) -> str:
    nombres = {lugar.id: lugar.nombre for lugar in lectura.lugares}
    personajes = "".join(
        f'<dt id="personaje-{escape(p.id)}">{escape(p.nombre)}</dt>'
        + (f"<dd>{escape(p.descripcion)}</dd>" if p.descripcion else "")
        + f"<dd>Aparece en los capítulos {_enlaces_a_capitulos(p.capitulos)}</dd>"
        for p in lectura.personajes
    )
    lugares = "".join(
        f'<dt id="lugar-{escape(lugar.id)}">{escape(lugar.nombre)}</dt>'
        + (f"<dd>{escape(lugar.descripcion)}</dd>" if lugar.descripcion else "")
        + (
            f'<dd>Dentro de <a href="#lugar-{escape(lugar.padre)}">'
            f"{escape(nombres.get(lugar.padre, lugar.padre))}</a></dd>"
            if lugar.padre
            else ""
        )
        + f"<dd>Capítulos: {_enlaces_a_capitulos(lugar.capitulos)}</dd>"
        for lugar in lectura.lugares
    )
    return (
        '<section id="fichas" class="fichas"><h2>Personajes y lugares</h2>'
        f"<h3>Personajes</h3><dl>{personajes}</dl>"
        f"<h3>Lugares</h3><dl>{lugares}</dl></section>"
    )


def documento_html(lectura: Lectura, titulacion: Titulacion) -> str:
    """RF-97, TC-7: `lectura.html` autocontenido, del mismo modelo que `lectura.json`.

    Orden: novedades (solo si hay cambiados), portada con dedicatoria, índice, los diez
    capítulos (`#cap-NN`) y la ficha de personajes y lugares con enlaces a los capítulos."""
    portada = lectura.portada
    dedicatoria = (
        f'<p class="dedicatoria">{escape(portada.dedicatoria)}</p>' if portada.dedicatoria else ""
    )
    indice = "".join(
        f'<li><a href="#{ancla_capitulo(c.numero)}">'
        f"{escape(encabezado(c.numero, c.titulo, titulacion))}</a></li>"
        for c in lectura.capitulos
    )
    capitulos = "".join(
        f'<section id="{ancla_capitulo(c.numero)}" class="capitulo">'
        f"<h2>{escape(encabezado(c.numero, c.titulo, titulacion))}</h2>{c.html}</section>"
        for c in lectura.capitulos
    )
    partes = [
        _novedades(lectura, titulacion) if lectura.cambiados else "",
        f'<section id="portada" class="portada"><h1>{escape(portada.titulo)}</h1>'
        f"{dedicatoria}</section>",
        '<section id="indice"><nav><h2>Índice</h2>'
        f'<ol>{indice}<li><a href="#fichas">Personajes y lugares</a></li></ol></nav></section>',
        capitulos,
        _fichas(lectura),
    ]
    return (
        '<!DOCTYPE html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(portada.titulo)}</title>\n<style>{_CSS}</style>\n</head>\n"
        f"<body>\n<main>{''.join(partes)}</main>\n</body>\n</html>\n"
    )
