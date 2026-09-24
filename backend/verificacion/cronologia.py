"""El fichero Lean de la cronología y la lectura de su informe (RF-111, RF-112, TC-1, TC-2).

Contrato de decisiones-backend §4.2 y plan-formal §3: importa `Cronologia`, define
`novela : Novela` con ids numéricos y listas ordenadas por id, un teorema por invariante
con `by decide +kernel` y `#eval violaciones novela`. Sin texto libre: la correspondencia
de ids va en un JSON aparte. Todo es función pura de las filas leídas, así que la misma
biblia da el mismo fichero byte a byte (UTF-8 sin BOM, `\\n`).
"""

import calendar
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from backend.contexto.modelos import es_fecha

# plan-formal §3.1: un periodo sin fecha segura va con el intervalo más ancho que se puede
# afirmar. Sin ninguna cota, el de todo el calendario: nunca es «con seguridad» anterior ni
# posterior a otro recuerdo, así que no produce violaciones falsas.
INTERVALO_SIN_FECHA = (1, date.max.toordinal())

TEOREMAS = (
    ("lugar_unico", "lugarUnico"),
    ("sin_reaparicion", "sinReaparicion"),
    ("nacido_antes", "nacidoAntes"),
)
CLAVES_INFORME = ("lugar_unico", "exclusion", "nacimiento")


@dataclass(frozen=True)
class EventoBiblia:
    """Una fila de `evento` con sus presentes; `capitulo` None es del contexto (R-2)."""

    id: int
    capitulo: int | None
    momento: str | None
    dia: int | None
    franja: str | None
    lugar: str
    presentes: tuple[str, ...]
    excluye: str | None


@dataclass(frozen=True)
class Biblia:
    localizaciones: tuple[tuple[str, str | None], ...]  # (id, padre)
    personajes: tuple[tuple[str, str | None], ...]  # (id, fecha_nacimiento)
    eventos: tuple[EventoBiblia, ...]


@dataclass(frozen=True)
class Cronologia:
    lean: str
    correspondencia: dict[str, Any]

    @property
    def lean_bytes(self) -> bytes:
        return self.lean.encode("utf-8")

    @property
    def correspondencia_bytes(self) -> bytes:
        texto = json.dumps(self.correspondencia, ensure_ascii=False, indent=1)
        return (texto + "\n").encode("utf-8")


def intervalo(momento: str) -> tuple[int, int]:
    """plan-formal §3.1: `AAAA`, `AAAA-MM` o `AAAA-MM-DD` como intervalo cerrado de
    `date.toordinal()`; un periodo (`infancia`), `INTERVALO_SIN_FECHA`."""
    if not es_fecha(momento):
        return INTERVALO_SIN_FECHA
    partes = [int(p) for p in momento.split("-")]
    if len(partes) == 3:
        dia = date(*partes).toordinal()
        return dia, dia
    if len(partes) == 2:
        anio, mes = partes
        ultimo = calendar.monthrange(anio, mes)[1]
        return date(anio, mes, 1).toordinal(), date(anio, mes, ultimo).toordinal()
    return date(partes[0], 1, 1).toordinal(), date(partes[0], 12, 31).toordinal()


def _numerar(ids: Sequence[str]) -> dict[str, int]:
    return {ident: n for n, ident in enumerate(sorted(ids), start=1)}


def _opcion(valor: int | None) -> str:
    return "none" if valor is None else f"some {valor}"


def _lista(elementos: Sequence[str], sangria: str) -> str:
    if not elementos:
        return "[]"
    return "[ " + (",\n" + sangria + "  ").join(elementos) + " ]"


def generar(biblia: Biblia) -> Cronologia:
    """RF-111: el `.lean` de la novela y su correspondencia de ids.

    Localizaciones y personajes se numeran por su id textual ordenado; los eventos, por
    capítulo (el contexto es el 0) y por id de fila. Un evento de la historia sin franja va
    con `.manana`: el tipo `Momento` de `formal/lean` no admite franja opcional (pendiente
    con la sesión formal).
    """
    locs = _numerar([ident for ident, _ in biblia.localizaciones])
    pjs = _numerar([ident for ident, _ in biblia.personajes])
    padres = dict(biblia.localizaciones)
    nacimientos = dict(biblia.personajes)
    eventos = sorted(biblia.eventos, key=lambda e: (e.capitulo or 0, e.id))

    lineas_locs = []
    for ident in sorted(locs, key=locs.__getitem__):
        padre = padres[ident]
        numero_padre = locs[padre] if padre is not None else None
        lineas_locs.append(f"{{ id := {locs[ident]}, padre := {_opcion(numero_padre)} }}")
    lineas_pjs = []
    for ident in sorted(pjs, key=pjs.__getitem__):
        fecha = nacimientos[ident]
        nacimiento = "none" if fecha is None else "some ({}, {})".format(*intervalo(fecha))
        lineas_pjs.append(f"{{ id := {pjs[ident]}, nacimiento := {nacimiento} }}")
    lineas_evs = []
    for n, e in enumerate(eventos, start=1):
        if e.dia is not None:
            momento = f".historia {e.dia} .{e.franja or 'manana'}"
        else:
            momento = ".recuerdo {} {}".format(*intervalo(e.momento or ""))
        presentes = ", ".join(str(p) for p in sorted(pjs[p] for p in set(e.presentes)))
        excluye = _opcion(pjs[e.excluye] if e.excluye else None)
        lineas_evs.append(
            f"{{ id := {n}, momento := {momento}, lugar := {locs[e.lugar]}, "
            f"presentes := [{presentes}],\n          excluye := {excluye} }}"
        )

    texto = [
        "import Cronologia",
        "open Cronologia",
        "",
        "def novela : Novela :=",
        "  { localizaciones :=",
        "      " + _lista(lineas_locs, "      ") + ",",
        "    personajes :=",
        "      " + _lista(lineas_pjs, "      ") + ",",
        "    eventos :=",
        "      " + _lista(lineas_evs, "      ") + " }",
        "",
        *(f"theorem {t} : {f} novela = true := by decide +kernel" for t, f in TEOREMAS),
        "",
        "#eval violaciones novela",
        "",
    ]
    correspondencia = {
        "localizaciones": [{"id": locs[i], "localizacion": i} for i in sorted(locs)],
        "personajes": [{"id": pjs[i], "personaje": i} for i in sorted(pjs)],
        "eventos": [
            {"id": n, "evento": e.id, "capitulo": e.capitulo}
            for n, e in enumerate(eventos, start=1)
        ],
    }
    return Cronologia("\n".join(texto), correspondencia)


class SalidaLeanIlegible(ValueError):
    """La salida de Lean no trae la línea JSON del informe con su forma fija: es un error
    de herramienta o de generación, no un gate en rojo (plan-formal §3.3)."""


def leer_informe(codigo: int, salida: str) -> dict[str, list[dict[str, Any]]]:
    """RF-112, plan-formal §3.3: la línea que empieza por `{` es el informe. Código 0 y
    listas vacías: verde; código ≠ 0 con alguna violación: rojo; lo demás, ilegible."""
    lineas = [linea.strip() for linea in salida.splitlines() if linea.strip().startswith("{")]
    if len(lineas) != 1:
        raise SalidaLeanIlegible(f"{len(lineas)} líneas JSON en la salida de Lean")
    try:
        informe = json.loads(lineas[0])
    except json.JSONDecodeError as error:
        raise SalidaLeanIlegible(f"la línea JSON no se lee: {error}") from error
    if not isinstance(informe, dict) or sorted(informe) != sorted(CLAVES_INFORME):
        raise SalidaLeanIlegible("el informe no tiene las claves fijas")
    if not all(isinstance(v, list) for v in informe.values()):
        raise SalidaLeanIlegible("el informe no trae listas")
    hay_violaciones = any(informe.values())
    if (codigo == 0) == hay_violaciones:
        raise SalidaLeanIlegible(f"código {codigo} con violaciones={hay_violaciones}")
    return informe


def eventos_implicados(informe: Mapping[str, list[dict[str, Any]]]) -> list[int]:
    """Los ids Lean de los eventos que nombra el informe, ordenados."""
    ids: set[int] = set()
    for choque in informe["lugar_unico"]:
        ids.update(choque["eventos"])
    for reaparicion in informe["exclusion"]:
        ids.update((reaparicion["excluye"], reaparicion["evento"]))
    for nacimiento in informe["nacimiento"]:
        ids.add(nacimiento["evento"])
    return sorted(ids)
