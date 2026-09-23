"""La biblia: lecturas «a fecha N−1», continuidad antes de escribir y escrituras del
Bibliotecario (RF-80 a RF-89, B-2, B-9, B-16, B-17, R-2).

Tres reglas:

- **A fecha N−1 (B-2).** Toda lectura recibe `antes_de`, el capítulo N que se va a escribir
  (de 1 a 11; 11 es la novela entera), y ve la última fila con capítulo menor que N. El
  capítulo 0 es el estado inicial de la planificación, y los eventos del contexto
  (`capitulo` NULL) cuentan como capítulo 0 (R-2).
- **Escribe el Bibliotecario, etiquetado (B-16).** Cada escritura recibe el `capitulo` de la
  orden vigente —quien llama lo saca del sello (AJ-4), nunca de un argumento de la
  herramienta— y solo se admite con ese capítulo `verificado` o `aprobado` (RF-106, V-19).
  `borrar_lo_escrito` deshace lo escrito para un capítulo; lo llama la emisión de cada orden
  de Bibliotecario, así que repetirla no duplica nada.
- **El vacío estructurado es error (RF-50c).** Un id que la biblia no conoce da
  `ReferenciaDesconocida`, en lecturas y en escrituras.

Todo el SQL de la biblia está aquí, salvo la siembra de planificación y escaleta
(`planificacion/materializar.py`, `planificacion/consultas.py`, `escaleta/consultas.py`).
"""

import json
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from backend.contexto.modelos import TipoExclusion, es_momento
from backend.contexto.persistencia import contexto_vigente
from backend.escaleta.consultas import leer_ficha
from backend.planificacion.consultas import leer_guia, leer_planificacion
from backend.shared.db import transaccion
from backend.shared.tipos import (
    CategoriaTermino,
    EstadoCapitulo,
    EstadoPresagio,
    Franja,
    Hallazgo,
    Severidad,
    TipoTermino,
)

VERIFICADOR = "continuidad"
TOPE_RESUMEN_CAPITULO = 240
TOPE_RESUMEN_ACTO = 360
_ESCRIBIBLE = frozenset({EstadoCapitulo.VERIFICADO.value, EstadoCapitulo.APROBADO.value})
_EXISTE = {
    "personaje": "SELECT 1 FROM personaje WHERE id = ?",
    "localizacion": "SELECT 1 FROM localizacion WHERE id = ?",
    "objeto": "SELECT 1 FROM objeto WHERE id = ?",
    "hecho": "SELECT 1 FROM hecho WHERE id = ?",
}
_REFERENCIA_DE = {
    CategoriaTermino.PERSONAJE: "personaje",
    CategoriaTermino.LOCALIZACION: "localizacion",
    CategoriaTermino.OBJETO: "objeto",
}


class ErrorBiblia(ValueError):
    pass


class CapituloNoVerificado(ErrorBiblia):
    """RF-106, V-19: nada entra en la biblia antes de verificar el capítulo."""

    def __init__(self, capitulo: int, estado: str | None) -> None:
        self.capitulo = capitulo
        self.estado = estado
        super().__init__(f"el capítulo {capitulo} está en {estado!r}, no verificado")


class ReferenciaDesconocida(ErrorBiblia):
    """Un id que la biblia no conoce. `tipo`: personaje, localizacion, objeto, hecho,
    presagio o ficha."""

    def __init__(self, tipo: str, ident: str) -> None:
        self.tipo = tipo
        self.ident = ident
        super().__init__(f"{tipo} desconocido: {ident!r}")


class EscrituraInvalida(ErrorBiblia):
    """Una escritura bien referida que la biblia no admite: un tope de resumen, un presagio
    en un estado que no toca, un evento sin su escala de tiempo."""


# ─── Lo que devuelven las lecturas ───────────────────────────────────────────


@dataclass(frozen=True)
class PersonajeAFecha:
    """`ficha` es la de la planificación (la salida del planificador, o la del contexto si
    aún no hay plan); `estado` y `sabe`, los de la fecha pedida."""

    id: str
    nombre: str | None
    alias: tuple[str, ...]
    descripcion: str | None
    ficha: dict[str, Any]
    estado: str | None
    sabe: tuple[str, ...]


@dataclass(frozen=True)
class Posesion:
    objeto: str
    nombre: str
    poseedor: str | None
    desde: int


@dataclass(frozen=True)
class PresagioPendiente:
    clave: str
    descripcion: str
    plantado_en: int
    cobrar_en: int | None


@dataclass(frozen=True)
class Lugar:
    id: str
    nivel: str
    padre: str | None
    nombre: str | None
    descripcion: str | None
    hito: str | None
    estado: str | None


@dataclass(frozen=True)
class Regla:
    regla: str
    limites: str
    costes: str
    excepciones: tuple[str, ...]


@dataclass(frozen=True)
class Termino:
    termino: str
    categoria: CategoriaTermino
    referencia: str | None
    tipo: TipoTermino


@dataclass(frozen=True)
class Resumen:
    ambito: Literal["capitulo", "acto"]
    numero: int
    texto: str


@dataclass(frozen=True)
class Acto:
    numero: int
    primero: int
    ultimo: int


@dataclass(frozen=True)
class FinDeCapitulo:
    dia: int
    localizacion: str


# ─── Lecturas a fecha N−1 ────────────────────────────────────────────────────


def _fecha(antes_de: int) -> int:
    if not 1 <= antes_de <= 11:
        raise ValueError(f"`antes_de` va de 1 a 11: {antes_de}")
    return antes_de


def _exigir(conexion: sqlite3.Connection, tipo: str, ident: str) -> None:
    if conexion.execute(_EXISTE[tipo], (ident,)).fetchone() is None:
        raise ReferenciaDesconocida(tipo, ident)


def personajes_a_fecha(
    conexion: sqlite3.Connection, antes_de: int, ids: Sequence[str]
) -> tuple[PersonajeAFecha, ...]:
    """RF-56, RF-80: ficha, estado y saber de cada personaje pedido, en el orden pedido."""
    n = _fecha(antes_de)
    resultado = []
    for ident in ids:
        fila = conexion.execute("SELECT * FROM personaje WHERE id = ?", (ident,)).fetchone()
        if fila is None:
            raise ReferenciaDesconocida("personaje", ident)
        estado = conexion.execute(
            "SELECT estado FROM personaje_estado WHERE personaje = ? AND capitulo < ? "
            "ORDER BY capitulo DESC LIMIT 1",
            (ident, n),
        ).fetchone()
        sabe = conexion.execute(
            "SELECT dato FROM personaje_sabe WHERE personaje = ? AND capitulo < ? "
            "GROUP BY dato ORDER BY min(capitulo), min(rowid)",
            (ident, n),
        ).fetchall()
        resultado.append(
            PersonajeAFecha(
                id=ident,
                nombre=fila["nombre"],
                alias=tuple(json.loads(fila["alias"])),
                descripcion=fila["descripcion"],
                ficha=json.loads(fila["ficha"]),
                estado=estado["estado"] if estado is not None else None,
                sabe=tuple(s["dato"] for s in sabe),
            )
        )
    return tuple(resultado)


def inventario_a_fecha(conexion: sqlite3.Connection, antes_de: int) -> tuple[Posesion, ...]:
    """RF-56, RF-83: quién tiene cada objeto, por id de objeto."""
    filas = conexion.execute(
        "SELECT i.objeto, o.nombre, i.poseedor, i.capitulo FROM inventario i "
        "JOIN objeto o ON o.id = i.objeto WHERE i.capitulo = ("
        "  SELECT max(capitulo) FROM inventario WHERE objeto = i.objeto AND capitulo < ?"
        ") ORDER BY i.objeto",
        (_fecha(antes_de),),
    ).fetchall()
    return tuple(Posesion(f["objeto"], f["nombre"], f["poseedor"], f["capitulo"]) for f in filas)


def presagios_pendientes(
    conexion: sqlite3.Connection, antes_de: int
) -> tuple[PresagioPendiente, ...]:
    """RF-84, RF-56: los plantados y aún no cobrados, por capítulo en que se plantaron."""
    filas = conexion.execute(
        "SELECT p.clave, p.descripcion, p.cobrar_en, e.capitulo FROM presagio p "
        "JOIN presagio_estado e ON e.presagio = p.id WHERE e.estado = ? AND e.capitulo = ("
        "  SELECT max(capitulo) FROM presagio_estado WHERE presagio = p.id AND capitulo < ?"
        ") ORDER BY e.capitulo, p.clave",
        (EstadoPresagio.PLANTADO.value, _fecha(antes_de)),
    ).fetchall()
    return tuple(
        PresagioPendiente(f["clave"], f["descripcion"], f["capitulo"], f["cobrar_en"])
        for f in filas
    )


def localizacion_con_ascendientes(
    conexion: sqlite3.Connection, localizacion: str, antes_de: int
) -> tuple[Lugar, ...]:
    """RF-81: la localización y sus ascendientes hasta la `macro`, con su estado."""
    n = _fecha(antes_de)
    lugares: list[Lugar] = []
    actual: str | None = localizacion
    while actual is not None and all(lugar.id != actual for lugar in lugares):
        fila = conexion.execute("SELECT * FROM localizacion WHERE id = ?", (actual,)).fetchone()
        if fila is None:
            raise ReferenciaDesconocida("localizacion", actual)
        estado = conexion.execute(
            "SELECT estado FROM localizacion_estado WHERE localizacion = ? AND capitulo < ? "
            "ORDER BY capitulo DESC LIMIT 1",
            (actual, n),
        ).fetchone()
        lugares.append(
            Lugar(
                id=fila["id"],
                nivel=fila["nivel"],
                padre=fila["padre"],
                nombre=fila["nombre"],
                descripcion=fila["descripcion"],
                hito=fila["hito"],
                estado=estado["estado"] if estado is not None else None,
            )
        )
        actual = fila["padre"]
    return tuple(lugares)


def reglas_del_mundo(conexion: sqlite3.Connection) -> tuple[Regla, ...]:
    filas = conexion.execute("SELECT * FROM regla_mundo ORDER BY id").fetchall()
    return tuple(
        Regla(f["regla"], f["limites"], f["costes"], tuple(json.loads(f["excepciones"])))
        for f in filas
    )


def glosario_a_fecha(conexion: sqlite3.Connection, antes_de: int) -> tuple[Termino, ...]:
    """RF-85, B-10: los términos conocidos, por orden alfabético."""
    filas = conexion.execute(
        "SELECT * FROM glosario g WHERE g.capitulo = ("
        "  SELECT max(capitulo) FROM glosario WHERE termino = g.termino AND capitulo < ?"
        ") ORDER BY g.termino",
        (_fecha(antes_de),),
    ).fetchall()
    return tuple(
        Termino(
            f["termino"], CategoriaTermino(f["categoria"]), f["referencia"], TipoTermino(f["tipo"])
        )
        for f in filas
    )


def actos(conexion: sqlite3.Connection) -> tuple[Acto, ...]:
    """Los tres actos del contexto validado, con su primer y último capítulo."""
    vigente = contexto_vigente(conexion)
    if vigente is None:
        raise ReferenciaDesconocida("contexto", "vigente")
    e = vigente[1].novela.estructura
    tramos = (e.planteamiento.capitulos, e.nudo.capitulos, e.desenlace.capitulos)
    return tuple(Acto(i, a, b) for i, (a, b) in enumerate(tramos, start=1))


def acto_de(conexion: sqlite3.Connection, capitulo: int) -> Acto:
    """El acto que contiene el capítulo; cierra el acto si `capitulo == acto.ultimo` (B-17)."""
    for acto in actos(conexion):
        if acto.primero <= capitulo <= acto.ultimo:
            return acto
    raise ValueError(f"el capítulo {capitulo} no está en ningún acto")


def _resumen_vigente(conexion: sqlite3.Connection, ambito: str, numero: int) -> str | None:
    fila = conexion.execute(
        "SELECT texto FROM resumen WHERE ambito = ? AND numero = ? "
        "ORDER BY version DESC, id DESC LIMIT 1",
        (ambito, numero),
    ).fetchone()
    return None if fila is None else str(fila["texto"])


def resumen_acumulado(conexion: sqlite3.Connection, antes_de: int) -> tuple[Resumen, ...]:
    """RF-55, §6.2: un resumen por acto cerrado antes de N y los de los capítulos del acto
    en curso. Un acto cerrado sin resumen de acto viaja con los de sus capítulos. De cada
    ámbito vale el de mayor versión (y, a igual versión, el último escrito)."""
    n = _fecha(antes_de)
    resumenes: list[Resumen] = []
    for acto in actos(conexion):
        if acto.primero >= n:
            break
        if acto.ultimo < n:
            texto = _resumen_vigente(conexion, "acto", acto.numero)
            if texto is not None:
                resumenes.append(Resumen("acto", acto.numero, texto))
                continue
        for capitulo in range(acto.primero, min(acto.ultimo, n - 1) + 1):
            texto = _resumen_vigente(conexion, "capitulo", capitulo)
            if texto is not None:
                resumenes.append(Resumen("capitulo", capitulo, texto))
    return tuple(resumenes)


# ─── Continuidad antes de escribir (B-9, R-2) ────────────────────────────────


def _hallazgo(regla: str, numero: int, evidencia: str, esperado: str) -> Hallazgo:
    return Hallazgo(
        verificador=VERIFICADOR,
        severidad=Severidad.ALTA,
        regla=regla,
        localizacion=f"ficha {numero}",
        evidencia=evidencia,
        esperado=esperado,
    )


def presentes_excluidos(
    conexion: sqlite3.Connection, antes_de: int, presentes: Iterable[str]
) -> tuple[Hallazgo, ...]:
    """RF-74 antes de escribir: un presente que un evento anterior a N excluye (muerte o
    partida). Los eventos del contexto cuentan como capítulo 0. Recibe solo `presentes`:
    los `mencionados` no se bloquean (R-2)."""
    n = _fecha(antes_de)
    hallazgos = []
    for ident in presentes:
        fila = conexion.execute(
            "SELECT id, tipo_exclusion, coalesce(capitulo, 0) AS capitulo FROM evento "
            "WHERE excluye = ? AND coalesce(capitulo, 0) < ? "
            "ORDER BY coalesce(capitulo, 0), id LIMIT 1",
            (ident, n),
        ).fetchone()
        if fila is not None:
            hallazgos.append(
                _hallazgo(
                    "RF-74 · presente_excluido",
                    n,
                    f"{ident}: {fila['tipo_exclusion']} en el evento {fila['id']} "
                    f"(capítulo {fila['capitulo']})",
                    "fuera de `presentes`; en `mencionados` si solo sale en un recuerdo",
                )
            )
    return tuple(hallazgos)


def dias_minimos(
    ruta: Sequence[tuple[str, int]],
    padres: Mapping[str, str | None],
    origen: str,
    destino: str,
) -> int | None:
    """RF-76: días de viaje entre dos localizaciones por la ruta —la suma de `dias_viaje`
    entre sus etapas—. La etapa de una localización es la suya o la de su ascendiente más
    cercano en la ruta; si alguna de las dos no tiene, `None`: no se puede juzgar."""
    posiciones: dict[str, int] = {}
    for i, (lugar, _) in enumerate(ruta):
        posiciones.setdefault(lugar, i)

    def etapa(lugar: str | None) -> int | None:
        vistos: set[str] = set()
        while lugar is not None and lugar not in vistos:
            if lugar in posiciones:
                return posiciones[lugar]
            vistos.add(lugar)
            lugar = padres.get(lugar)
        return None

    a, b = etapa(origen), etapa(destino)
    if a is None or b is None:
        return None
    desde, hasta = sorted((a, b))
    return sum(dias for _, dias in ruta[desde + 1 : hasta + 1])


def salto_imposible(
    conexion: sqlite3.Connection,
    numero: int,
    dia: int,
    localizacion: str,
    anterior: FinDeCapitulo | None,
) -> tuple[Hallazgo, ...]:
    """RF-76 antes de escribir: el capítulo `numero` empieza el día `dia` en `localizacion`,
    y el anterior terminó en `anterior`. Un día que retrocede, o menos días de los que pide la
    ruta, es un hallazgo. Sin capítulo anterior no hay nada que comparar."""
    _exigir(conexion, "localizacion", localizacion)
    if anterior is None:
        return ()
    _exigir(conexion, "localizacion", anterior.localizacion)
    salto = dia - anterior.dia
    if salto < 0:
        return (
            _hallazgo(
                "RF-76 · dia_retrocede",
                numero,
                f"D{dia} tras terminar el capítulo anterior en D{anterior.dia}",
                f"D{anterior.dia} o posterior",
            ),
        )
    ruta = [
        (f["localizacion"], f["dias_viaje"])
        for f in conexion.execute("SELECT localizacion, dias_viaje FROM ruta ORDER BY posicion")
    ]
    padres = {f["id"]: f["padre"] for f in conexion.execute("SELECT id, padre FROM localizacion")}
    minimos = dias_minimos(ruta, padres, anterior.localizacion, localizacion)
    if minimos is not None and salto < minimos:
        return (
            _hallazgo(
                "RF-76 · viaje_imposible",
                numero,
                f"de {anterior.localizacion} (D{anterior.dia}) a {localizacion} (D{dia})",
                f"al menos {minimos} días de viaje según la ruta",
            ),
        )
    return ()


def fin_de_capitulo(conexion: sqlite3.Connection, numero: int) -> FinDeCapitulo | None:
    """B-6: día y localización en que termina un capítulo: lo último que registró su
    Bibliotecario o, si aún no hay, lo previsto en su ficha. `None` sin ficha."""
    fila = conexion.execute(
        "SELECT dia_fin, localizacion_fin FROM capitulo_version "
        "WHERE capitulo = ? AND dia_fin IS NOT NULL ORDER BY id DESC LIMIT 1",
        (numero,),
    ).fetchone()
    if fila is not None:
        return FinDeCapitulo(fila["dia_fin"], fila["localizacion_fin"])
    ficha = conexion.execute(
        "SELECT dia, localizacion FROM ficha_capitulo WHERE numero = ?", (numero,)
    ).fetchone()
    return None if ficha is None else FinDeCapitulo(ficha["dia"], ficha["localizacion"])


def continuidad_antes_de_escribir(
    conexion: sqlite3.Connection, numero: int
) -> tuple[Hallazgo, ...]:
    """B-9 sobre la ficha guardada del capítulo `numero`, para el Recuperador: presentes
    excluidos y salto de días. Sin ficha, `ReferenciaDesconocida`."""
    ficha = leer_ficha(conexion, numero)
    if ficha is None:
        raise ReferenciaDesconocida("ficha", str(numero))
    anterior = fin_de_capitulo(conexion, numero - 1) if numero > 1 else None
    return presentes_excluidos(conexion, numero, ficha.presentes) + salto_imposible(
        conexion, numero, ficha.dia, ficha.localizacion, anterior
    )


# ─── Escrituras del Bibliotecario (B-16) ─────────────────────────────────────


def _version_en_curso(conexion: sqlite3.Connection, capitulo: int) -> sqlite3.Row | None:
    """La última versión de capítulo registrada: sobre la que trabaja el Bibliotecario."""
    fila: sqlite3.Row | None = conexion.execute(
        "SELECT id, version FROM capitulo_version WHERE capitulo = ? ORDER BY id DESC LIMIT 1",
        (capitulo,),
    ).fetchone()
    return fila


def _exigir_verificado(conexion: sqlite3.Connection, capitulo: int) -> sqlite3.Row:
    fila = conexion.execute("SELECT estado FROM capitulo WHERE numero = ?", (capitulo,)).fetchone()
    estado = fila["estado"] if fila is not None else None
    version = _version_en_curso(conexion, capitulo)
    if estado not in _ESCRIBIBLE or version is None:
        raise CapituloNoVerificado(capitulo, estado)
    return version


def actualizar_estado_personaje(
    conexion: sqlite3.Connection, capitulo: int, personaje: str, estado: str
) -> None:
    with transaccion(conexion):
        _exigir_verificado(conexion, capitulo)
        _exigir(conexion, "personaje", personaje)
        conexion.execute(
            "INSERT INTO personaje_estado (personaje, capitulo, estado) VALUES (?, ?, ?) "
            "ON CONFLICT (personaje, capitulo) DO UPDATE SET estado = excluded.estado",
            (personaje, capitulo, estado),
        )


def registrar_saber(
    conexion: sqlite3.Connection, capitulo: int, personaje: str, datos: Sequence[str]
) -> None:
    """Lo que el personaje aprende en el capítulo; se suma a lo que ya sabía."""
    with transaccion(conexion):
        _exigir_verificado(conexion, capitulo)
        _exigir(conexion, "personaje", personaje)
        conexion.executemany(
            "INSERT OR IGNORE INTO personaje_sabe (personaje, capitulo, dato) VALUES (?, ?, ?)",
            [(personaje, capitulo, dato) for dato in datos],
        )


def actualizar_estado_localizacion(
    conexion: sqlite3.Connection, capitulo: int, localizacion: str, estado: str
) -> None:
    with transaccion(conexion):
        _exigir_verificado(conexion, capitulo)
        _exigir(conexion, "localizacion", localizacion)
        conexion.execute(
            "INSERT INTO localizacion_estado (localizacion, capitulo, estado) VALUES (?, ?, ?) "
            "ON CONFLICT (localizacion, capitulo) DO UPDATE SET estado = excluded.estado",
            (localizacion, capitulo, estado),
        )


def registrar_traspaso(
    conexion: sqlite3.Connection, capitulo: int, objeto: str, poseedor: str | None
) -> None:
    """RF-83: desde este capítulo, `objeto` lo tiene `poseedor` (`None`: nadie)."""
    with transaccion(conexion):
        _exigir_verificado(conexion, capitulo)
        _exigir(conexion, "objeto", objeto)
        if poseedor is not None:
            _exigir(conexion, "personaje", poseedor)
        conexion.execute(
            "INSERT INTO inventario (objeto, poseedor, capitulo) VALUES (?, ?, ?) "
            "ON CONFLICT (objeto, capitulo) DO UPDATE SET poseedor = excluded.poseedor",
            (objeto, poseedor, capitulo),
        )


def registrar_evento(
    conexion: sqlite3.Connection,
    capitulo: int,
    descripcion: str,
    lugar: str,
    presentes: Sequence[str],
    *,
    dia: int | None = None,
    franja: Franja | None = None,
    momento: str | None = None,
    excluye: tuple[str, TipoExclusion] | None = None,
) -> int:
    """RF-82, B-6: un evento de la historia (`dia`, y `franja` si se sabe) o un recuerdo que
    el capítulo cuenta en analepsis (`momento`). Devuelve su id."""
    if (dia is None) == (momento is None):
        raise EscrituraInvalida("un evento lleva `dia` (historia) o `momento` (recuerdo)")
    if momento is not None and not es_momento(momento):
        raise EscrituraInvalida("`momento`: AAAA, AAAA-MM, AAAA-MM-DD o un periodo")
    if dia is not None and dia < 1:
        raise EscrituraInvalida("`dia` empieza en D1")
    if franja is not None and dia is None:
        raise EscrituraInvalida("la franja es solo de los eventos de la historia")
    if not descripcion.strip():
        raise EscrituraInvalida("un evento lleva descripción")
    with transaccion(conexion):
        _exigir_verificado(conexion, capitulo)
        _exigir(conexion, "localizacion", lugar)
        for ident in (*presentes, *([excluye[0]] if excluye else [])):
            _exigir(conexion, "personaje", ident)
        fila = conexion.execute(
            "INSERT INTO evento (descripcion, momento, dia, franja, lugar, capitulo, excluye, "
            "tipo_exclusion) VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (
                descripcion,
                momento,
                dia,
                franja.value if franja is not None else None,
                lugar,
                capitulo,
                excluye[0] if excluye else None,
                excluye[1].value if excluye else None,
            ),
        ).fetchone()
        conexion.executemany(
            "INSERT INTO evento_personaje (evento, personaje) VALUES (?, ?)",
            [(fila["id"], ident) for ident in dict.fromkeys(presentes)],
        )
    return int(fila["id"])


def _presagio(conexion: sqlite3.Connection, clave: str, antes_de: int) -> tuple[int, str | None]:
    fila = conexion.execute("SELECT id FROM presagio WHERE clave = ?", (clave,)).fetchone()
    if fila is None:
        raise ReferenciaDesconocida("presagio", clave)
    estado = conexion.execute(
        "SELECT estado FROM presagio_estado WHERE presagio = ? AND capitulo < ? "
        "ORDER BY capitulo DESC LIMIT 1",
        (fila["id"], antes_de),
    ).fetchone()
    return int(fila["id"]), estado["estado"] if estado is not None else None


def _marcar_presagio(
    conexion: sqlite3.Connection,
    capitulo: int,
    clave: str,
    desde: EstadoPresagio,
    hasta: EstadoPresagio,
) -> None:
    with transaccion(conexion):
        _exigir_verificado(conexion, capitulo)
        ident, estado = _presagio(conexion, clave, capitulo)
        if estado != desde.value:
            raise EscrituraInvalida(f"el presagio {clave!r} está {estado}, no {desde.value}")
        conexion.execute(
            "INSERT INTO presagio_estado (presagio, capitulo, estado) VALUES (?, ?, ?) "
            "ON CONFLICT (presagio, capitulo) DO UPDATE SET estado = excluded.estado",
            (ident, capitulo, hasta.value),
        )


def plantar_presagio(conexion: sqlite3.Connection, capitulo: int, clave: str) -> None:
    """B-16: confirma un presagio previsto por la escaleta."""
    _marcar_presagio(conexion, capitulo, clave, EstadoPresagio.PREVISTO, EstadoPresagio.PLANTADO)


def cobrar_presagio(conexion: sqlite3.Connection, capitulo: int, clave: str) -> None:
    """B-16: cierra un presagio plantado en un capítulo anterior."""
    _marcar_presagio(conexion, capitulo, clave, EstadoPresagio.PLANTADO, EstadoPresagio.COBRADO)


def abrir_presagio(
    conexion: sqlite3.Connection, capitulo: int, clave: str, descripcion: str
) -> None:
    """B-16: un presagio que la escaleta no preveía; nace plantado en este capítulo."""
    with transaccion(conexion):
        _exigir_verificado(conexion, capitulo)
        if conexion.execute("SELECT 1 FROM presagio WHERE clave = ?", (clave,)).fetchone():
            raise EscrituraInvalida(f"ya existe un presagio con la clave {clave!r}")
        fila = conexion.execute(
            "INSERT INTO presagio (clave, descripcion, abierto_en) VALUES (?, ?, ?) RETURNING id",
            (clave, descripcion, capitulo),
        ).fetchone()
        conexion.execute(
            "INSERT INTO presagio_estado (presagio, capitulo, estado) VALUES (?, ?, ?)",
            (fila["id"], capitulo, EstadoPresagio.PLANTADO.value),
        )


def registrar_termino(
    conexion: sqlite3.Connection,
    capitulo: int,
    termino: str,
    categoria: CategoriaTermino,
    referencia: str | None,
    tipo: TipoTermino,
) -> None:
    """RF-85, B-10: un nombre propio nuevo o una grafía nueva, desde este capítulo."""
    if (categoria is CategoriaTermino.OTRO) != (referencia is None):
        raise EscrituraInvalida("`referencia` va con personaje, localización u objeto")
    with transaccion(conexion):
        _exigir_verificado(conexion, capitulo)
        if referencia is not None:
            _exigir(conexion, _REFERENCIA_DE[categoria], referencia)
        conexion.execute(
            "INSERT INTO glosario (termino, categoria, referencia, tipo, capitulo) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT (termino, capitulo) DO UPDATE SET "
            "categoria = excluded.categoria, referencia = excluded.referencia, "
            "tipo = excluded.tipo",
            (termino, categoria.value, referencia, tipo.value, capitulo),
        )


def escribir_resumen(
    conexion: sqlite3.Connection,
    capitulo: int,
    ambito: Literal["capitulo", "acto"],
    texto: str,
    momento: str,
) -> None:
    """RF-86, B-17: el resumen del capítulo (240 palabras como mucho) o el del acto que lo
    contiene (360), etiquetado con la versión en curso del capítulo."""
    tope = TOPE_RESUMEN_CAPITULO if ambito == "capitulo" else TOPE_RESUMEN_ACTO
    palabras = len(texto.split())
    if not 0 < palabras <= tope:
        raise EscrituraInvalida(f"un resumen de {ambito} lleva de 1 a {tope} palabras: {palabras}")
    with transaccion(conexion):
        version = _exigir_verificado(conexion, capitulo)
        numero = capitulo if ambito == "capitulo" else acto_de(conexion, capitulo).numero
        conexion.execute(
            "INSERT INTO resumen (ambito, numero, capitulo, version, texto, creado) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (ambito, numero, capitulo, version) "
            "DO UPDATE SET texto = excluded.texto, creado = excluded.creado",
            (ambito, numero, capitulo, version["version"], texto, momento),
        )


def registrar_uso_de_hecho(conexion: sqlite3.Connection, capitulo: int, hecho: str) -> None:
    """RF-89, RF-104: el capítulo, en su versión en curso, usa este hecho aportado."""
    with transaccion(conexion):
        version = _exigir_verificado(conexion, capitulo)
        _exigir(conexion, "hecho", hecho)
        conexion.execute(
            "INSERT OR IGNORE INTO hecho_uso (hecho, capitulo, version) VALUES (?, ?, ?)",
            (hecho, capitulo, version["version"]),
        )


def registrar_fin(conexion: sqlite3.Connection, capitulo: int, dia: int, localizacion: str) -> None:
    """B-6: día y localización en que termina la versión en curso del capítulo."""
    if dia < 1:
        raise EscrituraInvalida("`dia` empieza en D1")
    with transaccion(conexion):
        version = _exigir_verificado(conexion, capitulo)
        _exigir(conexion, "localizacion", localizacion)
        conexion.execute(
            "UPDATE capitulo_version SET dia_fin = ?, localizacion_fin = ? WHERE id = ?",
            (dia, localizacion, version["id"]),
        )


def borrar_lo_escrito(conexion: sqlite3.Connection, capitulo: int) -> None:
    """B-16: deshace lo escrito para el capítulo —estado, saber, inventario, glosario,
    eventos, presagios, y el resumen, el uso de hechos y el fin de su versión en curso—.
    No exige estado: la llama la emisión de la orden del Bibliotecario, y AJ-4 al volver a
    sellarla. Los resúmenes de otras versiones se conservan (RF-87)."""
    if not 1 <= capitulo <= 10:
        raise ValueError(f"capítulo fuera de rango: {capitulo}")
    with transaccion(conexion):
        for sql in (
            "DELETE FROM personaje_estado WHERE capitulo = ?",
            "DELETE FROM personaje_sabe WHERE capitulo = ?",
            "DELETE FROM localizacion_estado WHERE capitulo = ?",
            "DELETE FROM inventario WHERE capitulo = ?",
            "DELETE FROM glosario WHERE capitulo = ?",
            "DELETE FROM evento_personaje WHERE evento IN "
            "(SELECT id FROM evento WHERE capitulo = ?)",
            "DELETE FROM evento WHERE capitulo = ?",
            "DELETE FROM presagio_estado WHERE capitulo = ?",
            "DELETE FROM presagio_estado WHERE presagio IN "
            "(SELECT id FROM presagio WHERE abierto_en = ?)",
            "DELETE FROM presagio WHERE abierto_en = ?",
        ):
            conexion.execute(sql, (capitulo,))
        version = _version_en_curso(conexion, capitulo)
        if version is not None:
            conexion.execute(
                "DELETE FROM resumen WHERE capitulo = ? AND version = ?",
                (capitulo, version["version"]),
            )
            conexion.execute(
                "DELETE FROM hecho_uso WHERE capitulo = ? AND version = ?",
                (capitulo, version["version"]),
            )
            conexion.execute(
                "UPDATE capitulo_version SET dia_fin = NULL, localizacion_fin = NULL WHERE id = ?",
                (version["id"],),
            )


def pendiente_del_bibliotecario(conexion: sqlite3.Connection, capitulo: int) -> tuple[str, ...]:
    """B-16: lo que falta para aceptar el resultado del Bibliotecario de este capítulo, en su
    versión en curso: `resumen`, `dia_fin`, `localizacion_fin` y, si cierra su acto o el
    acto ya tiene resumen (una regeneración, B-17), `resumen_acto`. Vacío si está todo."""
    version = _version_en_curso(conexion, capitulo)
    if version is None:
        return ("resumen", "dia_fin", "localizacion_fin")
    fila = conexion.execute(
        "SELECT dia_fin, localizacion_fin FROM capitulo_version WHERE id = ?", (version["id"],)
    ).fetchone()
    faltan = []

    def escrito(ambito: str) -> bool:
        sql = "SELECT 1 FROM resumen WHERE ambito = ? AND capitulo = ? AND version = ?"
        return conexion.execute(sql, (ambito, capitulo, version["version"])).fetchone() is not None

    if not escrito("capitulo"):
        faltan.append("resumen")
    if fila["dia_fin"] is None:
        faltan.append("dia_fin")
    if fila["localizacion_fin"] is None:
        faltan.append("localizacion_fin")
    acto = acto_de(conexion, capitulo)
    con_resumen = conexion.execute(
        "SELECT 1 FROM resumen WHERE ambito = 'acto' AND numero = ?", (acto.numero,)
    ).fetchone()
    if (capitulo == acto.ultimo or con_resumen is not None) and not escrito("acto"):
        faltan.append("resumen_acto")
    return tuple(faltan)


# ─── Lecturas para /mcp/lectura (§4.1.6) ─────────────────────────────────────


def contexto_para_mcp(conexion: sqlite3.Connection) -> dict[str, Any] | None:
    """El contexto validado sin la referencia al texto libre, que no es confiable (RF-14)."""
    vigente = contexto_vigente(conexion)
    if vigente is None:
        return None
    datos: dict[str, Any] = vigente[1].model_dump(mode="json")
    datos["novela"]["personalizacion"].pop("texto_libre", None)
    return datos


def plan_para_mcp(conexion: sqlite3.Connection) -> dict[str, Any] | None:
    salida = leer_planificacion(conexion)
    return None if salida is None else salida.model_dump(mode="json")


def ficha_para_mcp(conexion: sqlite3.Connection, numero: int) -> dict[str, Any] | None:
    ficha = leer_ficha(conexion, numero)
    return None if ficha is None else ficha.model_dump(mode="json")


def guia_para_mcp(conexion: sqlite3.Connection) -> dict[str, Any] | None:
    guia = leer_guia(conexion)
    return None if guia is None else guia.model_dump(mode="json")
