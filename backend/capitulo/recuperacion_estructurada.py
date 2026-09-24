"""Recuperación estructurada del Recuperador (RF-50a, RF-50c, RF-55, RF-56, B-8).

Todos los bloques del prompt del Escritor menos el de pasajes, en el orden y con las
prioridades de architecture §6.3 más el bloque «Informe del intento anterior» (B-8). Los
datos salen de `biblia.py`, del contexto vigente y de las consultas de planificación y
escaleta; aquí no hay SQL de la biblia.

- **Determinismo byte a byte (RF-50a):** listas en el orden de sus consultas (con
  `ORDER BY`), JSON con claves ordenadas, texto en NFC y saltos `\\n`.
- **Vacíos (RF-50c, B-8):** un bloque obligatorio vacío (ficha, guía, presentes,
  localización) lanza `BloqueVacio`; uno opcional (informe anterior, presagios e
  inventario, resumen, capítulo anterior, reglas) lleva la línea fija «Ninguno.», que no es
  un recorte.
- Vetos, frases literales y lista negra van dentro de la ficha, que nunca se recorta; el
  estado de los presentes va en el bloque de presagios e inventario (B-8).
"""

import json
import sqlite3
import unicodedata
from dataclasses import dataclass
from typing import Any

from backend.capitulo import biblia
from backend.contexto.modelos import TipoHecho
from backend.contexto.persistencia import contexto_vigente
from backend.escaleta.consultas import leer_ficha
from backend.planificacion.consultas import leer_guia
from backend.shared.rutas import DisposicionProyecto

NINGUNO = "Ninguno."
AVISO_ULTIMO_APROBADO = (
    "El capítulo {anterior} aún no está aprobado: este es el último capítulo aprobado, el {k}."
)


class BloqueVacio(ValueError):
    """RF-50c: la recuperación estructurada no encontró lo que un bloque obligatorio exige."""

    def __init__(self, bloque: str, motivo: str) -> None:
        self.bloque = bloque
        self.motivo = motivo
        super().__init__(f"bloque {bloque}: {motivo}")


@dataclass(frozen=True)
class Bloque:
    """Un bloque del prompt. `unidades` son lo que se recorta: una sola, el bloque entero,
    salvo en los pasajes (`divisible`), donde cada fragmento es una (RF-53a). `esperado` es
    el tamaño esperado de §6.3 en unidades del estimador: informativo, no una asignación."""

    id: str
    titulo: str
    prioridad: int
    esperado: int
    unidades: tuple[str, ...]
    divisible: bool = False
    preambulo: str = ""

    def texto(self, unidades: tuple[str, ...] | None = None) -> str:
        partes = [f"## {self.titulo}", *([self.preambulo] if self.preambulo else [])]
        return "\n\n".join([*partes, *(self.unidades if unidades is None else unidades)])


def normalizar(texto: str) -> str:
    return unicodedata.normalize("NFC", texto.replace("\r\n", "\n").replace("\r", "\n"))


def _json(valor: Any) -> str:
    return "```json\n" + json.dumps(valor, ensure_ascii=False, sort_keys=True, indent=2) + "\n```"


def _lista(lineas: list[str]) -> str:
    return "\n".join(f"- {linea}" for linea in lineas) if lineas else NINGUNO


def _bloque(ident: str, titulo: str, prioridad: int, esperado: int, cuerpo: str) -> Bloque:
    return Bloque(ident, titulo, prioridad, esperado, (normalizar(cuerpo.strip() or NINGUNO),))


def bloques_estructurados(
    conexion: sqlite3.Connection,
    disposicion: DisposicionProyecto,
    numero: int,
    informe_anterior: str | None,
) -> tuple[Bloque, ...]:
    """Los bloques del capítulo `numero`, a fecha N−1, en orden de emisión. Lanza
    `BloqueVacio` o, ante un id que la biblia no conoce, `biblia.ReferenciaDesconocida`."""
    ficha = leer_ficha(conexion, numero)
    if ficha is None:
        raise BloqueVacio("ficha", f"no hay ficha del capítulo {numero}: registra la escaleta")
    vigente = contexto_vigente(conexion)
    if vigente is None:
        raise BloqueVacio("ficha", "no hay contexto validado")
    guia = leer_guia(conexion)
    if guia is None:
        raise BloqueVacio("guia", "no hay guía de estilo: registra la planificación")
    novela = vigente[1].novela

    # 1 · Ficha, con hechos (las frases, literales), vetos y lista negra.
    hechos = {h.id: h for h in novela.personalizacion.hechos}
    lineas_hechos = []
    for ident in ficha.hechos:
        if ident not in hechos:
            raise biblia.ReferenciaDesconocida("hecho", ident)
        hecho = hechos[ident]
        if hecho.tipo == TipoHecho.FRASE:
            lineas_hechos.append(f"[{ident}] frase literal, tal cual: «{hecho.texto}»")
        else:
            lineas_hechos.append(f"[{ident}] {hecho.tipo.value}: {hecho.texto}")
    vetos = novela.personalizacion.vetos
    ficha_texto = "\n\n".join(
        [
            _json(ficha.model_dump(mode="json")),
            "### Hechos del comprador en este capítulo\n\n" + _lista(lineas_hechos),
            "### Vetos: palabras\n\n" + _lista(list(vetos.palabras)),
            "### Vetos: temas\n\n" + _lista(list(vetos.temas)),
            "### Lista negra\n\n" + _lista(list(guia.lista_negra)),
        ]
    )

    # 2 · Guía de estilo (la lista negra ya va en la ficha).
    guia_texto = _json(guia.model_dump(mode="json", exclude={"lista_negra"}))

    # 3 · Presagios pendientes, inventario vivo y estado de los presentes (RF-56).
    presentes = biblia.personajes_a_fecha(conexion, numero, ficha.presentes)
    if not presentes:
        raise BloqueVacio("presentes", f"la ficha {numero} no tiene presentes")
    presagios = [
        f"{p.clave} (plantado en el capítulo {p.plantado_en}"
        + (f", se cobra en el {p.cobrar_en}" if p.cobrar_en is not None else "")
        + f"): {p.descripcion}"
        for p in biblia.presagios_pendientes(conexion, numero)
    ]
    inventario = [
        f"{p.objeto} ({p.nombre}): {p.poseedor or 'sin poseedor'}, desde el capítulo {p.desde}"
        for p in biblia.inventario_a_fecha(conexion, numero)
    ]
    estados = [
        f"{p.id}: {p.estado or 'sin estado registrado'}"
        + (f"; sabe: {'; '.join(p.sabe)}" if p.sabe else "")
        for p in presentes
    ]
    vivo_texto = "\n\n".join(
        [
            "### Presagios pendientes\n\n" + _lista(presagios),
            "### Inventario\n\n" + _lista(inventario),
            "### Estado de los presentes\n\n" + _lista(estados),
        ]
    )

    # 4 · Fichas de los presentes.
    presentes_texto = _json(
        [
            {
                "id": p.id,
                "nombre": p.nombre,
                "alias": list(p.alias),
                "descripcion": p.descripcion,
                "ficha": p.ficha,
            }
            for p in presentes
        ]
    )

    # 5 · Localización con sus ascendientes y reglas del mundo.
    lugares = biblia.localizacion_con_ascendientes(conexion, ficha.localizacion, numero)
    if not lugares:
        raise BloqueVacio("localizacion", f"sin localización para la ficha {numero}")
    reglas = biblia.reglas_del_mundo(conexion)
    lugar_texto = "\n\n".join(
        [
            _json([vars(lugar) for lugar in lugares]),
            "### Reglas del mundo\n\n"
            + (
                _json([{**vars(r), "excepciones": list(r.excepciones)} for r in reglas])
                if reglas
                else NINGUNO
            ),
        ]
    )

    # 6 · Resumen acumulado, compactado (RF-55).
    resumen_texto = "\n\n".join(
        f"### {'Acto' if r.ambito == 'acto' else 'Capítulo'} {r.numero}\n\n{r.texto}"
        for r in biblia.resumen_acumulado(conexion, numero)
    )

    return (
        _bloque("ficha", "Ficha del capítulo", 1, 2000, ficha_texto),
        _bloque(
            "informe_anterior", "Informe del intento anterior", 2, 1000, informe_anterior or ""
        ),
        _bloque("guia", "Guía de estilo", 2, 5000, guia_texto),
        _bloque(
            "presagios_inventario", "Presagios pendientes e inventario vivo", 3, 2000, vivo_texto
        ),
        _bloque("presentes", "Fichas de los personajes presentes", 4, 8000, presentes_texto),
        _bloque("localizacion", "Localización y reglas del mundo aplicables", 5, 5000, lugar_texto),
        _bloque("resumen", "Resumen acumulado", 6, 3000, resumen_texto),
        _bloque(
            "capitulo_anterior",
            "Capítulo anterior íntegro",
            7,
            3000,
            _capitulo_anterior(conexion, disposicion, numero),
        ),
    )


def _capitulo_anterior(
    conexion: sqlite3.Connection, disposicion: DisposicionProyecto, numero: int
) -> str:
    """B-8: el texto vigente del último capítulo aprobado antes de N, con aviso si no es N−1.

    Lectura directa de `capitulo` y `capitulo_version` (no son biblia y `biblia.py` no la
    ofrece): la versión vigente del capítulo, o la última registrada si no hay vigente."""
    fila = conexion.execute(
        "SELECT c.numero, v.ruta FROM capitulo c JOIN capitulo_version v ON v.capitulo = c.numero "
        "WHERE c.numero < ? AND c.estado = 'aprobado' "
        "ORDER BY c.numero DESC, (v.version = c.version_vigente) DESC, v.id DESC LIMIT 1",
        (numero,),
    ).fetchone()
    if fila is None:
        return ""
    ruta = disposicion.absoluta(fila["ruta"])
    if not ruta.is_file():
        raise BloqueVacio(
            "capitulo_anterior", f"el capítulo {fila['numero']} está aprobado y falta {ruta}"
        )
    texto = ruta.read_bytes().decode("utf-8").strip()
    if fila["numero"] != numero - 1:
        texto = AVISO_ULTIMO_APROBADO.format(anterior=numero - 1, k=fila["numero"]) + "\n\n" + texto
    return texto
