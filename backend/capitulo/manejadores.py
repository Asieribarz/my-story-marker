"""Manejadores de `escritor`, `editor-estilo`, `juez-capitulo`, `bibliotecario` y `revisor`
(RF-60, RF-61, RF-77, RF-77a, B-15, B-16).

Los agrega `proyecto/manejadores.py`. Cada uno valida la salida contra su esquema
(`modelos_salida.py`): si no encaja devuelve `Desenlace.forma()` —el Escritor,
`Desenlace.contenido()`— con los errores en `detalle` y no persiste nada. El estado del
capítulo y los contadores los escribe el cerebro; aquí se escribe solo lo de la rebanada:
los ficheros de texto, `capitulo_version`, `informe` y la auditoría del guardarraíl.

- **Escritor:** guarda el borrador en su fichero y crea la `capitulo_version` (estado
  `borrador`), con `ruta` = `ruta_borrador` hasta que el Editor la reescriba.
- **Editor de estilo:** guarda el texto editado, ejecuta **todos** los deterministas y
  decide (RF-77): con un hallazgo alto o bloqueante, fallo de contenido, que es del
  guardarraíl si el intento tiene algún hallazgo suyo (B-12); si no, aceptado y la versión
  queda `editado` (§3 punto 2: `verificado` pide también el juez). Los hallazgos medios y
  bajos solo viajan en el informe (§3.4).
- **Juez de capítulo:** severidad por criterio (architecture §4, B-15); con alta, fallo de
  contenido; si no, la versión queda `verificado`. `aprobado` lo pone el cerebro al aceptar
  al Bibliotecario.
- **Bibliotecario:** el resultado se acepta solo si la biblia tiene lo que B-16 exige.
- **Revisor:** como el Editor, sobre una versión nueva del capítulo (§3, punto 7).
"""

import json
import sqlite3
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.capitulo import segmentacion as seg
from backend.capitulo.biblia import borrar_lo_escrito, pendiente_del_bibliotecario
from backend.capitulo.modelos_salida import (
    SEVERIDAD_DEL_CRITERIO,
    SalidaBibliotecario,
    SalidaCapitulo,
    SalidaJuez,
    capitulo_de_markdown,
    citas_ausentes,
)
from backend.capitulo.verificadores import ejecutar, lexico, vista_de
from backend.proyecto.manejadores import ContextoManejo, Manejador, Salida
from backend.proyecto.maquina import TOPE, Desenlace
from backend.shared.db import transaccion
from backend.shared.tipos import Agente, Hallazgo, Informe, Severidad

JUEZ = "juez-capitulo"
_RANGO = {s: i for i, s in enumerate(Severidad)}


def _errores(error: Exception) -> list[str]:
    """Ruta y mensaje de cada error, sin el valor recibido."""
    if isinstance(error, ValidationError):
        return [
            f"{'.'.join(str(p) for p in e['loc']) or '(raíz)'}: {e['msg']}"
            for e in error.errors(include_url=False)
        ]
    return [str(error)]


def _rechazo(desenlace: Desenlace, *errores: str) -> Salida:
    return Salida(desenlace, {"errores": list(errores)})


def _ultima_version(conexion: sqlite3.Connection, numero: int) -> sqlite3.Row | None:
    fila: sqlite3.Row | None = conexion.execute(
        "SELECT * FROM capitulo_version WHERE capitulo = ? ORDER BY id DESC LIMIT 1", (numero,)
    ).fetchone()
    return fila


def _version_de_la_orden(contexto: ContextoManejo, numero: int) -> sqlite3.Row | None:
    """La `capitulo_version` que leyó el agente: la (versión, intento del texto) de su entrada
    (`proyecto/manejadores._con_texto_a_leer`); sin ellos, la última del capítulo."""
    entrada = contexto.orden.entrada
    version, intento = entrada.get("version"), entrada.get("intento_texto")
    if not (isinstance(version, int) and isinstance(intento, int)):
        return _ultima_version(contexto.conexion, numero)
    fila: sqlite3.Row | None = contexto.conexion.execute(
        "SELECT * FROM capitulo_version WHERE capitulo = ? AND version = ? AND intento = ?",
        (numero, version, intento),
    ).fetchone()
    return fila


def _escribir(ruta: Path, salida: SalidaCapitulo) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(salida.markdown, encoding="utf-8", newline="\n")


def _guardar_informe(
    conexion: sqlite3.Connection, version: int, informe: Informe, momento: str
) -> None:
    """Uno por versión y verificador (RF-78); repetirlo lo sustituye."""
    mayor = max((h.severidad for h in informe.hallazgos), key=_RANGO.__getitem__, default=None)
    conexion.execute(
        "INSERT INTO informe (capitulo_version, verificador, severidad, hallazgos, metricas, "
        "momento) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (capitulo_version, verificador) DO "
        "UPDATE SET severidad = excluded.severidad, hallazgos = excluded.hallazgos, "
        "metricas = excluded.metricas, momento = excluded.momento",
        (
            version,
            informe.verificador,
            mayor.value if mayor is not None else None,
            json.dumps([h.model_dump(mode="json") for h in informe.hallazgos], ensure_ascii=False),
            json.dumps(informe.metricas) if informe.metricas is not None else None,
            momento,
        ),
    )


def _detalle(informes: tuple[Informe, ...]) -> dict[str, Any]:
    """El informe que va a `orden.detalle` y al intento siguiente (B-8)."""
    return {
        "hallazgos": [h.model_dump(mode="json") for i in informes for h in i.hallazgos],
        "metricas": {i.verificador: i.metricas for i in informes if i.metricas is not None},
    }


def _verificar(contexto: ContextoManejo, fila: sqlite3.Row, ruta: str, cuerpo: str) -> Salida:
    """RF-77: los deterministas sobre el texto vigente de la versión `fila`."""
    conexion, momento = contexto.conexion, contexto.momento
    numero = int(fila["capitulo"])
    with transaccion(conexion):
        informes = ejecutar(cuerpo, vista_de(conexion, numero, momento))
        for informe in informes:
            _guardar_informe(conexion, fila["id"], informe, momento)
        del_guardarrail = [
            h for i in informes if i.verificador == "guardarrail" for h in i.hallazgos
        ]
        conexion.executemany(
            "INSERT INTO auditoria (momento, tipo, detalle) VALUES (?, 'guardarrail', ?)",
            [
                (
                    momento,
                    json.dumps(
                        {
                            "capitulo": numero,
                            "version": fila["version"],
                            "intento": fila["intento"],
                            "nivel": h.regla.rsplit(" ", 1)[-1],
                            "palabra": lexico.id_de(h),
                            "offset": h.localizacion,
                        }
                    ),
                )
                for h in del_guardarrail
            ],
        )
        corta = any(i.corta_el_ciclo for i in informes)
        # §3 punto 2: `editado` pide los deterministas en verde; si cortan, sigue `borrador`.
        conexion.execute(
            "UPDATE capitulo_version SET ruta = ?, estado = ? WHERE id = ?",
            (ruta, "borrador" if corta else "editado", fila["id"]),
        )
    desenlace = Desenlace.contenido(bool(del_guardarrail)) if corta else Desenlace.aceptado()
    return Salida(desenlace, _detalle(informes))


# ─── escritor ────────────────────────────────────────────────────────────────


def _version_a_escribir(contexto: ContextoManejo, numero: int) -> int:
    """La de la orden si la trae; si no, la siguiente a la vigente (1 en la generación)."""
    propia = contexto.orden.entrada.get("version")
    if isinstance(propia, int) and propia >= 1:
        return propia
    fila = contexto.conexion.execute(
        "SELECT version_vigente FROM capitulo WHERE numero = ?", (numero,)
    ).fetchone()
    return int(fila["version_vigente"] or 0) + 1 if fila is not None else 1


def _escritor(contexto: ContextoManejo, resultado: object) -> Salida:
    numero = contexto.orden.capitulo
    if numero is None:
        return _rechazo(Desenlace.contenido(), "(orden): sin capítulo")
    try:
        salida = capitulo_de_markdown(resultado)
    except ValueError as error:
        return _rechazo(Desenlace.contenido(), *_errores(error))
    version, intento = _version_a_escribir(contexto, numero), contexto.orden.intento
    disposicion = contexto.proyecto.disposicion
    ruta = disposicion.borrador(numero, version, intento)
    _escribir(ruta, salida)
    relativa = disposicion.relativa(ruta)
    with transaccion(contexto.conexion) as conexion:
        conexion.execute(
            "INSERT INTO capitulo_version (capitulo, version, intento, estado, ruta, "
            "ruta_borrador, ruta_prompt, creado) VALUES (?, ?, ?, 'borrador', ?, ?, ?, ?) "
            "ON CONFLICT (capitulo, version, intento) DO UPDATE SET estado = 'borrador', "
            "ruta = excluded.ruta, ruta_borrador = excluded.ruta_borrador",
            (
                numero,
                version,
                intento,
                relativa,
                relativa,
                disposicion.relativa(disposicion.prompt(numero, version, intento)),
                contexto.momento,
            ),
        )
    palabras = seg.contar_palabras(salida.texto)
    return Salida(
        Desenlace.aceptado(), {"version": version, "intento": intento, "palabras": palabras}
    )


# ─── editor-estilo y revisor ─────────────────────────────────────────────────


def _editor(contexto: ContextoManejo, resultado: object) -> Salida:
    numero = contexto.orden.capitulo
    if numero is None:
        return _rechazo(Desenlace.forma(), "(orden): sin capítulo")
    try:
        salida = capitulo_de_markdown(resultado)
    except ValueError as error:
        return _rechazo(Desenlace.forma(), *_errores(error))
    fila = _version_de_la_orden(contexto, numero)
    if fila is None:
        return _rechazo(Desenlace.forma(), f"(capítulo {numero}): no tiene borrador")
    disposicion = contexto.proyecto.disposicion
    ruta = disposicion.capitulo(numero, fila["version"], fila["intento"])
    _escribir(ruta, salida)
    return _verificar(contexto, fila, disposicion.relativa(ruta), salida.texto)


def _revisor(contexto: ContextoManejo, resultado: object) -> Salida:
    """§3, punto 7: la corrección es una versión nueva del capítulo, la siguiente a la
    última, sin borrador; los deterministas corren sobre ella como con el Editor. Si la
    última es un intento del Revisor que los deterministas rechazaron (sigue `borrador` y sin
    `ruta_borrador`), el nuevo intento va en esa misma versión: no deja huecos."""
    numero = contexto.orden.capitulo
    if numero is None:
        return _rechazo(Desenlace.forma(), "(orden): sin capítulo")
    try:
        salida = capitulo_de_markdown(resultado)
    except ValueError as error:
        return _rechazo(Desenlace.forma(), *_errores(error))
    anterior = _ultima_version(contexto.conexion, numero)
    rechazada = (
        anterior is not None and anterior["estado"] == "borrador" and not anterior["ruta_borrador"]
    )
    version = (int(anterior["version"]) if anterior is not None else 0) + (0 if rechazada else 1)
    intento = contexto.orden.intento
    disposicion = contexto.proyecto.disposicion
    ruta = disposicion.capitulo(numero, version, intento)
    _escribir(ruta, salida)
    relativa = disposicion.relativa(ruta)
    with transaccion(contexto.conexion) as conexion:
        (fila,) = conexion.execute(
            "INSERT INTO capitulo_version (capitulo, version, intento, estado, ruta, creado) "
            "VALUES (?, ?, ?, 'borrador', ?, ?) ON CONFLICT (capitulo, version, intento) DO "
            "UPDATE SET estado = 'borrador', ruta = excluded.ruta, creado = excluded.creado "
            "RETURNING *",
            (numero, version, intento, relativa, contexto.momento),
        ).fetchall()
        return _verificar(contexto, fila, relativa, salida.texto)


# ─── juez-capitulo ───────────────────────────────────────────────────────────


def _juez(contexto: ContextoManejo, resultado: object) -> Salida:
    numero = contexto.orden.capitulo
    if numero is None:
        return _rechazo(Desenlace.forma(), "(orden): sin capítulo")
    try:
        salida = SalidaJuez.model_validate(resultado)
    except ValidationError as error:
        return _rechazo(Desenlace.forma(), *_errores(error))
    fila = _version_de_la_orden(contexto, numero)
    if fila is None:
        return _rechazo(Desenlace.forma(), f"(capítulo {numero}): no tiene texto")
    texto = contexto.proyecto.disposicion.absoluta(fila["ruta"]).read_text(encoding="utf-8")
    cuerpo = seg.separar_titulo(texto)[1]
    ausentes = citas_ausentes(salida, cuerpo)
    if ausentes:
        return _rechazo(Desenlace.forma(), *ausentes)
    hallazgos = tuple(
        Hallazgo(
            verificador=JUEZ,
            severidad=SEVERIDAD_DEL_CRITERIO[juicio.criterio],
            regla=f"juez · {juicio.criterio.value}",
            localizacion=f"p{h.parrafo}",
            evidencia=h.cita,
            esperado=h.motivo,
        )
        for juicio in salida.criterios
        for h in juicio.hallazgos
    )
    informe = Informe(verificador=JUEZ, hallazgos=hallazgos)
    with transaccion(contexto.conexion) as conexion:
        _guardar_informe(conexion, fila["id"], informe, contexto.momento)
        if not informe.corta_el_ciclo:
            conexion.execute(
                "UPDATE capitulo_version SET estado = 'verificado' WHERE id = ?", (fila["id"],)
            )
    desenlace = Desenlace.contenido() if informe.corta_el_ciclo else Desenlace.aceptado()
    return Salida(desenlace, _detalle((informe,)))


# ─── bibliotecario ───────────────────────────────────────────────────────────


def _bibliotecario(contexto: ContextoManejo, resultado: object) -> Salida:
    """B-16: el recuento no se cree; se mira la biblia."""
    numero = contexto.orden.capitulo
    if numero is None:
        return _rechazo(Desenlace.forma(), "(orden): sin capítulo")
    try:
        salida = SalidaBibliotecario.model_validate(resultado)
    except ValidationError as error:
        return _bibliotecario_rechazado(contexto, numero, {"errores": _errores(error)})
    faltan = pendiente_del_bibliotecario(contexto.conexion, numero)
    if faltan:
        return _bibliotecario_rechazado(
            contexto,
            numero,
            {"errores": [_falta(f) for f in faltan], "faltan": list(faltan)},
        )
    return Salida(Desenlace.aceptado(), {"registrado": salida.registrado})


def _falta(pieza: str) -> str:
    """El error que lee el reintento. El de `resumen_acto` explica B-17, que sin el porqué el
    Bibliotecario descarta cuando el capítulo no cierra su acto."""
    if pieza == "resumen_acto":
        return (
            "biblia: falta resumen_acto: el acto de este capítulo ya tenía resumen y, al "
            "reescribir cualquiera de sus capítulos, hay que reescribir el resumen del acto "
            "entero con escribir_resumen_acto (B-17), aunque este capítulo no lo cierre"
        )
    return f"biblia: falta {pieza}"


def _bibliotecario_rechazado(
    contexto: ContextoManejo, numero: int, detalle: dict[str, Any]
) -> Salida:
    """B-16, RF-07a: con el último intento del tope (el suyo es `intentos_paso` + 1, en el
    bucle y en `revision`), lo que escribió no se queda en la biblia: el capítulo siguiente
    la leería como si fuese de un capítulo aprobado."""
    if contexto.orden.intento >= TOPE:
        borrar_lo_escrito(contexto.conexion, numero)
    return Salida(Desenlace.forma(), detalle)


MANEJADORES: dict[Agente, Manejador] = {
    Agente.ESCRITOR: _escritor,
    Agente.EDITOR_ESTILO: _editor,
    Agente.JUEZ_CAPITULO: _juez,
    Agente.BIBLIOTECARIO: _bibliotecario,
    Agente.REVISOR: _revisor,
}
