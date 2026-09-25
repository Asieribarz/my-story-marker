"""El cambio del lector en la base (RF-120 a RF-123, TC-8, AJ-6, V-31).

- `pedir_cambio` (RF-120, RF-123): la petición va a `cambios/` como no confiable, el
  proyecto pasa de `publicada` a `cambio_solicitado` y se encola un trabajo. Sobre una
  versión que ya no es la vigente, el cambio queda `obsoleto` y no se guarda nada más.
- `decidir_cambio` (RF-122): confirmar aplica el valor nuevo, calcula los capítulos
  afectados desde el `hecho_uso` de las versiones vigentes (`cambio_capitulo`), los reabre
  (AJ-6: versión nueva, `pendiente`, contadores a cero), pasa a `regeneracion` y encola otro
  trabajo; rechazar vuelve a `publicada` sin tocar nada.
- `leer_cambio`: lo que enseña `GET /cambios/{c}`, nunca la petición.

El resto del ciclo —publicado, rechazado, fallido y su vuelta atrás— lo escribe
`efectos.py` al volver el proyecto a `publicada`. Las decisiones pasan por
`proyecto.persistencia.decidir`, dentro de la transacción de aquí: la acción humana, su
transición y los efectos de esta rebanada van juntos o no van.
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from backend.cambio import hechos
from backend.cambio.entrada import guardar_peticion
from backend.contexto.modelos import Hecho
from backend.proyecto.abierto import Proyecto, instante
from backend.proyecto.errores import CambioInexistente, DecisionHumanaInvalida
from backend.proyecto.maquina import AccionHumana
from backend.proyecto.persistencia import decidir, exigir_fase
from backend.shared.db import transaccion
from backend.shared.tipos import EstadoCambio, EstadoProyecto, EstadoTrabajo

# Por qué un cambio queda `obsoleto` (RF-123). Los de `fallido` son la causa de la
# transición que lo hizo volver a `publicada` (`proyecto.transiciones.Causa`).
MOTIVO_VERSION_OBSOLETA = "version_obsoleta"


@dataclass(frozen=True)
class Peticion:
    version: int
    capitulo: int
    parrafos: tuple[int, int] | None
    fragmento: str
    peticion: str


@dataclass(frozen=True)
class Propuesta:
    """RF-121: lo que propone el Intérprete. `hecho` es el id del hecho que cambia o, en uno
    nuevo, el que tendrá; `valor_anterior` es `None` en un hecho nuevo."""

    tipo: str
    hecho: str
    valor_anterior: str | None
    valor_nuevo: str


@dataclass(frozen=True)
class CambioLeido:
    id: int
    estado: EstadoCambio
    version: int
    capitulo: int
    parrafos: tuple[int, int] | None
    propuesta: Propuesta | None
    capitulos: tuple[int, ...]
    version_nueva: int | None
    motivo: str | None


def version_vigente(conexion: sqlite3.Connection) -> int | None:
    fila = conexion.execute("SELECT max(numero) AS n FROM version_novela").fetchone()
    return None if fila["n"] is None else int(fila["n"])


def cambio_en_curso(conexion: sqlite3.Connection) -> sqlite3.Row | None:
    """El cambio que ocupa el proyecto: interpretándose, propuesto o regenerando. Hay como
    mucho uno, porque solo se pide desde `publicada`."""
    fila: sqlite3.Row | None = conexion.execute(
        "SELECT * FROM cambio_lector WHERE estado IN (?, ?, ?) ORDER BY id DESC LIMIT 1",
        (
            EstadoCambio.INTERPRETANDO.value,
            EstadoCambio.PROPUESTO.value,
            EstadoCambio.REGENERANDO.value,
        ),
    ).fetchone()
    return fila


def encolar_trabajo(conexion: sqlite3.Connection, cambio: int | None, momento: str) -> int:
    """TC-8: un trabajo es «orquestar este proyecto hasta la próxima parada»."""
    fila = conexion.execute(
        "INSERT INTO trabajo (cambio, estado, creado) VALUES (?, ?, ?) RETURNING id",
        (cambio, EstadoTrabajo.EN_COLA.value, momento),
    ).fetchone()
    return int(fila["id"])


def pedir_cambio(proyecto: Proyecto, peticion: Peticion, ahora: datetime) -> int:
    """RF-120, RF-123: registra la petición y devuelve el número del cambio."""
    momento = instante(ahora)
    with transaccion(proyecto.conexion) as conexion:
        exigir_fase(conexion, EstadoProyecto.PUBLICADA, "pedir un cambio")
        desde, hasta = peticion.parrafos if peticion.parrafos is not None else (None, None)
        if peticion.version != version_vigente(conexion):
            fila = conexion.execute(
                "INSERT INTO cambio_lector (version_novela, capitulo, parrafo_desde, "
                "parrafo_hasta, estado, motivo, creado) VALUES (?, ?, ?, ?, ?, ?, ?) "
                "RETURNING id",
                (
                    peticion.version,
                    peticion.capitulo,
                    desde,
                    hasta,
                    EstadoCambio.OBSOLETO.value,
                    MOTIVO_VERSION_OBSOLETA,
                    momento,
                ),
            ).fetchone()
            return int(fila["id"])
        numero = int(
            conexion.execute("SELECT coalesce(max(id), 0) + 1 AS n FROM cambio_lector").fetchone()[
                "n"
            ]
        )
        ruta = guardar_peticion(
            conexion,
            proyecto.disposicion,
            numero,
            peticion.capitulo,
            peticion.parrafos,
            peticion.fragmento,
            peticion.peticion,
        )
        conexion.execute(
            "INSERT INTO cambio_lector (id, version_novela, capitulo, parrafo_desde, "
            "parrafo_hasta, ruta_peticion, estado, creado) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                numero,
                peticion.version,
                peticion.capitulo,
                desde,
                hasta,
                ruta,
                EstadoCambio.INTERPRETANDO.value,
                momento,
            ),
        )
        decidir(proyecto, AccionHumana.PEDIR_CAMBIO, ahora)
        encolar_trabajo(conexion, numero, momento)
    return numero


def _fila(conexion: sqlite3.Connection, cambio: int) -> sqlite3.Row:
    fila: sqlite3.Row | None = conexion.execute(
        "SELECT * FROM cambio_lector WHERE id = ?", (cambio,)
    ).fetchone()
    if fila is None:
        raise CambioInexistente(cambio)
    return fila


def _propuesta(fila: sqlite3.Row) -> Propuesta | None:
    if fila["hecho"] is not None:
        return Propuesta("cambio", fila["hecho"], fila["valor_anterior"], fila["valor_nuevo"])
    if fila["hecho_nuevo"] is not None:
        nuevo: dict[str, Any] = json.loads(fila["hecho_nuevo"])
        return Propuesta("nuevo", str(nuevo["id"]), None, str(nuevo["texto"]))
    return None


def leer_cambio(conexion: sqlite3.Connection, cambio: int) -> CambioLeido:
    """§4.3: el estado del cambio con la propuesta, los capítulos que reabrió y la versión
    que lo publicó. Nunca la petición ni el fragmento: son del lector (V-29)."""
    fila = _fila(conexion, cambio)
    capitulos = tuple(
        int(c["capitulo"])
        for c in conexion.execute(
            "SELECT capitulo FROM cambio_capitulo WHERE cambio = ? ORDER BY capitulo", (cambio,)
        )
    )
    desde, hasta = fila["parrafo_desde"], fila["parrafo_hasta"]
    return CambioLeido(
        id=int(fila["id"]),
        estado=EstadoCambio(fila["estado"]),
        version=int(fila["version_novela"]),
        capitulo=int(fila["capitulo"]),
        parrafos=(int(desde), int(hasta)) if desde is not None and hasta is not None else None,
        propuesta=_propuesta(fila),
        capitulos=capitulos,
        version_nueva=fila["version_publicada"],
        motivo=fila["motivo"],
    )


def capitulos_afectados(conexion: sqlite3.Connection, fila: sqlite3.Row) -> tuple[int, ...]:
    """V-31, RF-122: los capítulos cuya versión vigente —la de la versión de novela
    publicada— usa el hecho, según `hecho_uso`. Un hecho nuevo va al capítulo del fragmento.
    Un hecho que ninguna versión vigente usa cae en los capítulos cuya ficha lo pide y, si
    tampoco hay, en el del fragmento: el cambio siempre regenera algo."""
    if fila["hecho"] is None:
        return (int(fila["capitulo"]),)
    usados = tuple(
        int(f["capitulo"])
        for f in conexion.execute(
            "SELECT DISTINCT hu.capitulo FROM version_novela_capitulo vnc "
            "JOIN capitulo_version cv ON cv.id = vnc.capitulo_version "
            "JOIN hecho_uso hu ON hu.capitulo = cv.capitulo AND hu.version = cv.version "
            "WHERE vnc.version_novela = (SELECT max(numero) FROM version_novela) "
            "AND hu.hecho = ? ORDER BY hu.capitulo",
            (fila["hecho"],),
        )
    )
    if usados:
        return usados
    en_fichas = tuple(
        int(f["capitulo"])
        for f in conexion.execute(
            "SELECT capitulo FROM ficha_capitulo_hecho WHERE hecho = ? ORDER BY capitulo",
            (fila["hecho"],),
        )
    )
    return en_fichas or (int(fila["capitulo"]),)


def _reabrir(conexion: sqlite3.Connection, cambio: int, capitulos: tuple[int, ...]) -> None:
    """AJ-6: cada capítulo afectado vuelve a `pendiente` con sus contadores a cero, y su
    versión nueva es la siguiente a la mayor que tenga —también a la de un cambio fallido—."""
    for numero in capitulos:
        fila = conexion.execute(
            "SELECT max(coalesce((SELECT max(version) FROM capitulo_version WHERE capitulo = "
            ":n), 0), coalesce(version_vigente, 0)) + 1 AS v FROM capitulo WHERE numero = :n",
            {"n": numero},
        ).fetchone()
        conexion.execute(
            "INSERT INTO cambio_capitulo (cambio, capitulo, version) VALUES (?, ?, ?)",
            (cambio, numero, int(fila["v"])),
        )
    conexion.executemany(
        "UPDATE capitulo SET estado = 'pendiente', intentos = 0 WHERE numero = ?",
        [(n,) for n in capitulos],
    )


def decidir_cambio(proyecto: Proyecto, cambio: int, confirmado: bool, ahora: datetime) -> None:
    """RF-122: confirmar o rechazar el cambio propuesto. Solo se decide uno `propuesto`: si
    no, `DecisionHumanaInvalida` y nada cambia."""
    momento = instante(ahora)
    with transaccion(proyecto.conexion) as conexion:
        fila = _fila(conexion, cambio)
        if fila["estado"] != EstadoCambio.PROPUESTO:
            raise DecisionHumanaInvalida(
                f"el cambio {cambio} está {fila['estado']}: solo se decide uno propuesto"
            )
        if not confirmado:
            decidir(proyecto, AccionHumana.RECHAZAR_CAMBIO, ahora)
            return
        if fila["hecho"] is not None:
            hechos.cambiar_texto(conexion, fila["hecho"], fila["valor_nuevo"], momento)
        else:
            nuevo = Hecho.model_validate_json(fila["hecho_nuevo"])
            hechos.anadir(conexion, nuevo, int(fila["capitulo"]), momento)
        _reabrir(conexion, cambio, capitulos_afectados(conexion, fila))
        # La máquina lee los capítulos ya reabiertos: `regeneracion` tiene uno en curso.
        decidir(proyecto, AccionHumana.CONFIRMAR_CAMBIO, ahora)
        conexion.execute(
            "UPDATE cambio_lector SET estado = ? WHERE id = ?",
            (EstadoCambio.REGENERANDO.value, cambio),
        )
        encolar_trabajo(conexion, cambio, momento)


def encolar_si_regenera(conexion: sqlite3.Connection, momento: str) -> int | None:
    """TC-8: tras aprobar en `aprobacion_final` una regeneración, nadie lanzaría al
    Exportador: se encola otro trabajo para llegar a `publicada`."""
    fila = cambio_en_curso(conexion)
    if fila is None or fila["estado"] != EstadoCambio.REGENERANDO:
        return None
    return encolar_trabajo(conexion, int(fila["id"]), momento)
