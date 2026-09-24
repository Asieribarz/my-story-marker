"""Lista negra (RF-72) y guardarraíl de palabras prohibidas (RF-72a), con el normalizador de
B-11 que comparten.

- **Normalizar (B-11):** minúsculas, sin tildes ni diéresis y **conservando la ñ**. Cada
  palabra de un término se expande a sus variantes de género y número (-s, -es, z→ces,
  -o/-a/-os/-as), y se compara por palabras enteras, así que «hospital» no dispara dentro de
  «hospitalario».
- **Listas del guardarraíl (B-12):** la global y la de cada público son ficheros versionados
  en `capitulo/listas/`; se copian a `palabra_prohibida` la primera vez que se verifica un
  capítulo del proyecto, y `lista_guardarrail` guarda el hash del fichero copiado. Una vez
  copiada, el proyecto conserva su copia aunque el fichero cambie. La lista de novela
  (vetos) la escribe la materialización del contexto (B-1).
"""

import hashlib
import itertools
import sqlite3
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from backend.capitulo import segmentacion as seg
from backend.contexto.modelos import Publico
from backend.shared.db import transaccion
from backend.shared.tipos import Hallazgo, Informe, Severidad

LISTAS = Path(__file__).resolve().parents[1] / "listas"
# B-12: juvenil y adulto van vacías en la v1; crossover usa la juvenil, como su umbral (B-14).
LISTA_DEL_PUBLICO = {
    Publico.INFANTIL: "infantil",
    Publico.JUVENIL: "juvenil",
    Publico.ADULTO: "adulto",
    Publico.CROSSOVER: "juvenil",
}
_MINIMO_PARA_VARIAR = 4


@dataclass(frozen=True)
class Prohibida:
    id: int
    termino: str
    nivel: str


def normalizar(texto: str) -> str:
    """B-11: minúsculas, sin tildes ni diéresis, con la ñ."""
    marcado = unicodedata.normalize("NFC", texto).lower().replace("ñ", "\0")
    sin_marcas = "".join(
        c for c in unicodedata.normalize("NFD", marcado) if not unicodedata.combining(c)
    )
    return sin_marcas.replace("\0", "ñ")


def variantes(palabra: str) -> frozenset[str]:
    """B-11: las variantes de género y número de una palabra ya normalizada."""
    if len(palabra) < _MINIMO_PARA_VARIAR:
        return frozenset({palabra})
    bases = {palabra}
    if palabra.endswith("ces"):
        bases.add(palabra[:-3] + "z")
    if palabra.endswith("es"):
        bases.add(palabra[:-2])
    if palabra.endswith("s"):
        bases.add(palabra[:-1])
    todas: set[str] = set()
    for base in bases:
        todas |= {base, base + "s", base + "es"}
        if base.endswith("z"):
            todas.add(base[:-1] + "ces")
        if base[-1:] in ("o", "a") and len(base) >= _MINIMO_PARA_VARIAR:
            raiz = base[:-1]
            todas |= {raiz + "o", raiz + "a", raiz + "os", raiz + "as"}
    return frozenset(todas)


def _formas(termino: str) -> set[tuple[str, ...]]:
    palabras = [normalizar(p) for p in seg.tokens(termino)]
    return set(itertools.product(*(sorted(variantes(p)) for p in palabras))) if palabras else set()


@dataclass(frozen=True)
class Coincidencia:
    indice: int
    parrafo: int
    offset: int
    literal: str


def buscar(cuerpo: str, terminos: Iterable[str]) -> Iterator[Coincidencia]:
    """Cada aparición de cada término (por su índice en `terminos`) en el cuerpo, por
    palabras enteras tras normalizar y expandir las variantes."""
    indice: dict[tuple[str, ...], int] = {}
    for i, termino in enumerate(terminos):
        for forma in _formas(termino):
            indice.setdefault(forma, i)
    longitudes = sorted({len(f) for f in indice}, reverse=True)
    for parrafo in seg.parrafos(cuerpo):
        palabras = seg.palabras(parrafo)
        normales = [normalizar(p.texto) for p in palabras]
        for inicio in range(len(palabras)):
            for largo in longitudes:
                encontrado = indice.get(tuple(normales[inicio : inicio + largo]))
                if encontrado is not None and inicio + largo <= len(palabras):
                    ultima = palabras[inicio + largo - 1]
                    literal = parrafo.texto[
                        palabras[inicio].inicio : ultima.inicio + len(ultima.texto)
                    ]
                    yield Coincidencia(encontrado, parrafo.numero, palabras[inicio].inicio, literal)
                    break


# ─── RF-72 · lista negra ─────────────────────────────────────────────────────


def lista_negra(cuerpo: str, lista: tuple[str, ...]) -> Informe:
    """RF-72: muletillas y palabras de estilo prohibidas de la guía (`lenguaje.prohibidas`
    incluidas, resolución 3 de §3), en severidad baja."""
    hallazgos = tuple(
        Hallazgo(
            verificador="lista_negra",
            severidad=Severidad.BAJA,
            regla="RF-72 · lista_negra",
            localizacion=seg.localizacion(c.parrafo, c.offset),
            evidencia=c.literal,
            esperado=f"evitar «{lista[c.indice]}»",
        )
        for c in buscar(cuerpo, lista)
    )
    return Informe(verificador="lista_negra", hallazgos=hallazgos)


# ─── RF-72a · guardarraíl ────────────────────────────────────────────────────


def huella(lista: str) -> str:
    return hashlib.sha256((LISTAS / f"{lista}.txt").read_bytes()).hexdigest()


def terminos_de(lista: str) -> tuple[str, ...]:
    """Una entrada por línea; `#` empieza un comentario."""
    lineas = (LISTAS / f"{lista}.txt").read_text(encoding="utf-8").splitlines()
    limpias = (linea.split("#", 1)[0].strip() for linea in lineas)
    return tuple(dict.fromkeys(t for t in limpias if t))


def asegurar_listas(conexion: sqlite3.Connection, publico: Publico, momento: str) -> None:
    """B-12: copia a la base la lista global y la del público si el proyecto aún no las tiene,
    con el hash del fichero copiado. Idempotente."""
    with transaccion(conexion):
        for lista in ("global", LISTA_DEL_PUBLICO[publico]):
            ya = conexion.execute("SELECT 1 FROM lista_guardarrail WHERE lista = ?", (lista,))
            if ya.fetchone() is not None:
                continue
            nivel, de_publico = ("global", None) if lista == "global" else ("publico", lista)
            conexion.executemany(
                "INSERT OR IGNORE INTO palabra_prohibida (termino, nivel, publico) "
                "VALUES (?, ?, ?)",
                [(t, nivel, de_publico) for t in terminos_de(lista)],
            )
            conexion.execute(
                "INSERT INTO lista_guardarrail (lista, hash, copiada) VALUES (?, ?, ?)",
                (lista, huella(lista), momento),
            )


def prohibidas(conexion: sqlite3.Connection, publico: Publico) -> tuple[Prohibida, ...]:
    """Las tres listas que valen para este proyecto: global, la de su público y la de novela."""
    filas = conexion.execute(
        "SELECT id, termino, nivel FROM palabra_prohibida WHERE nivel IN ('global', 'novela') "
        "OR (nivel = 'publico' AND publico = ?) ORDER BY id",
        (LISTA_DEL_PUBLICO[publico],),
    ).fetchall()
    return tuple(Prohibida(f["id"], f["termino"], f["nivel"]) for f in filas)


def id_de(hallazgo: Hallazgo) -> int:
    """El id de `palabra_prohibida` de un hallazgo del guardarraíl, para la auditoría."""
    return int((hallazgo.esperado or "").rsplit(" ", 1)[-1])


def guardarrail(cuerpo: str, lista: tuple[Prohibida, ...]) -> Informe:
    """RF-72a: toda aparición de una palabra de las tres listas es bloqueante. La evidencia
    es lo que dice el capítulo; `esperado` lleva el id de la palabra, no el término."""
    hallazgos = tuple(
        Hallazgo(
            verificador="guardarrail",
            severidad=Severidad.BLOQUEANTE,
            regla=f"RF-72a · {lista[c.indice].nivel}",
            localizacion=seg.localizacion(c.parrafo, c.offset),
            evidencia=c.literal,
            esperado=f"palabra_prohibida {lista[c.indice].id}",
        )
        for c in buscar(cuerpo, (p.termino for p in lista))
    )
    return Informe(verificador="guardarrail", hallazgos=hallazgos)
