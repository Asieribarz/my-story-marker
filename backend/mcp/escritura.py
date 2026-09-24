"""Superficie `/mcp/escritura` (RF-102, RF-104, RF-106, B-16, B-17, AJ-4): las escrituras del
Bibliotecario en la biblia.

Solo la declara la definición del Bibliotecario, en su propio `mcpServers`, y el hook de
policy la deniega a cualquier otro `agent_type` (architecture.md §7, §8). Aquí se hace
cumplir lo que no depende de quién llama:

- **Sello (AJ-4).** Cada herramienta recibe el sello de la orden y lo valida con
  `proyecto.sello.orden_de_sello`, dentro de la transacción que escribe: un sello viejo
  —un ejecutor caído, un subagente que acaba tarde— no escribe. La orden vigente tiene que
  ser de Bibliotecario sobre un capítulo.
- **Capítulo de la orden (B-16).** Ninguna herramienta recibe el capítulo: sale de la orden.
- **Verificado (RF-106, V-19).** La guarda vive en `capitulo/biblia.py`: el capítulo tiene
  que estar en `verificado` o posterior. Escribe biblia.py; aquí no hay SQL de la biblia.
- **Auditoría (RF-105).** Cada llamada queda en `llamada_mcp`, sin el texto libre.
"""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field
from starlette.applications import Starlette

from backend.capitulo import biblia
from backend.contexto.modelos import TipoExclusion
from backend.mcp.llamada import AuditarRechazos, ejecutar
from backend.proyecto import dependencias
from backend.proyecto.abierto import Proyecto, instante
from backend.proyecto.errores import SelloInvalido
from backend.shared.db import transaccion
from backend.shared.tipos import Agente, CategoriaTermino, Franja, TipoTermino

RUTA = "/mcp/escritura"
NOMBRE = "escritura"
SUPERFICIE = "escritura"

_INSTRUCCIONES = (
    "Escritura en la biblia de continuidad, solo para el Bibliotecario. Pasa en cada "
    "herramienta el argumento `sello`: todo lo que va detrás de `orden: ` en la primera línea "
    "de tu prompt, tal cual. El capítulo es el de tu orden. Si una herramienta responde con "
    "error, corrige los argumentos y repite: repetir no duplica nada."
)

Sello = Annotated[
    str, Field(description="El sello de tu orden: lo que va detrás de `orden: `, tal cual.")
]
Id = Annotated[str, Field(min_length=1)]


class Exclusion(BaseModel):
    """A quién excluye un evento: una muerte o una partida definitiva."""

    model_config = ConfigDict(extra="forbid")
    personaje: Id
    tipo: TipoExclusion


def _capitulo_de(p: Proyecto, sello: str) -> int:
    """AJ-4 y B-16: el capítulo de la orden vigente, si el sello es el suyo y es del
    Bibliotecario. `sello.py` es del cerebro y se importa al usarlo."""
    from backend.proyecto.sello import orden_de_sello

    try:
        orden = orden_de_sello(p.conexion, sello)
    except SelloInvalido as error:
        raise ToolError(f"{error}; no escribas más con este sello") from None
    if orden.agente is not Agente.BIBLIOTECARIO or orden.capitulo is None:
        raise ToolError("la orden vigente no es de Bibliotecario sobre un capítulo")
    return int(orden.capitulo)


def crear_servidor(
    reloj: Callable[[], datetime] = dependencias.reloj,
    raiz: Callable[[], Path] = dependencias.raiz_proyectos,
) -> FastMCP[Any]:
    """El servidor con sus herramientas; reloj y raíz inyectados, como en `/mcp/entrada`."""
    servidor: FastMCP[Any] = FastMCP(NOMBRE, instructions=_INSTRUCCIONES, mask_error_details=True)
    servidor.add_middleware(AuditarRechazos(SUPERFICIE, raiz, reloj))

    def herramienta(nombre: str, titulo: str) -> Callable[[Callable[..., Any]], Any]:
        return servidor.tool(
            name=nombre,
            annotations=ToolAnnotations(
                title=titulo,
                read_only_hint=False,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=False,
            ),
            output_schema=None,
        )

    def escribir(
        sello: str,
        nombre: str,
        argumentos: dict[str, Any],
        operacion: Callable[[Proyecto, int, str], object],
    ) -> dict[str, Any]:
        """Valida el sello, toma el capítulo de la orden y escribe; devuelve el capítulo."""
        ahora = reloj()

        def con_capitulo(p: Proyecto) -> dict[str, Any]:
            # AJ-4: el sello se valida en la misma transacción inmediata que escribe; así
            # nadie puede tomar el bloqueo (y volver a sellar) entre la comprobación y la
            # escritura. Las de biblia.py anidan en ella como SAVEPOINT.
            with transaccion(p.conexion):
                capitulo = _capitulo_de(p, sello)
                operacion(p, capitulo, instante(ahora))
            return {"ok": True, "capitulo": capitulo}

        herr = f"{SUPERFICIE}.{nombre}"
        return ejecutar(raiz(), ahora, sello, herr, argumentos, con_capitulo)

    @herramienta("actualizar_estado_personaje", "Estado de un personaje")
    def actualizar_estado_personaje(
        sello: Sello, personaje: Id, estado: Annotated[str, Field(min_length=1)]
    ) -> dict[str, Any]:
        """El estado del personaje al terminar el capítulo."""
        return escribir(
            sello,
            "actualizar_estado_personaje",
            {"personaje": personaje, "estado": estado},
            lambda p, n, _: biblia.actualizar_estado_personaje(p.conexion, n, personaje, estado),
        )

    @herramienta("registrar_saber", "Lo que aprende un personaje")
    def registrar_saber(
        sello: Sello,
        personaje: Id,
        datos: Annotated[list[Annotated[str, Field(min_length=1)]], Field(min_length=1)],
    ) -> dict[str, Any]:
        """Lo que el personaje llega a saber en el capítulo; se suma a lo que ya sabía."""
        return escribir(
            sello,
            "registrar_saber",
            {"personaje": personaje, "datos": datos},
            lambda p, n, _: biblia.registrar_saber(p.conexion, n, personaje, datos),
        )

    @herramienta("actualizar_estado_localizacion", "Estado de una localización")
    def actualizar_estado_localizacion(
        sello: Sello, localizacion: Id, estado: Annotated[str, Field(min_length=1)]
    ) -> dict[str, Any]:
        """El estado de la localización al terminar el capítulo."""
        return escribir(
            sello,
            "actualizar_estado_localizacion",
            {"localizacion": localizacion, "estado": estado},
            lambda p, n, _: biblia.actualizar_estado_localizacion(
                p.conexion, n, localizacion, estado
            ),
        )

    @herramienta("registrar_traspaso", "Un objeto cambia de manos")
    def registrar_traspaso(
        sello: Sello,
        objeto: Id,
        poseedor: Annotated[str | None, Field(description="Id de personaje; null: nadie.")],
    ) -> dict[str, Any]:
        """Desde este capítulo, `objeto` lo tiene `poseedor`."""
        return escribir(
            sello,
            "registrar_traspaso",
            {"objeto": objeto, "poseedor": poseedor},
            lambda p, n, _: biblia.registrar_traspaso(p.conexion, n, objeto, poseedor),
        )

    @herramienta("registrar_evento", "Un suceso en la cronología")
    def registrar_evento(
        sello: Sello,
        descripcion: Annotated[str, Field(min_length=1)],
        lugar: Annotated[str, Field(min_length=1, description="Id de localización.")],
        presentes: list[Id],
        dia: Annotated[int | None, Field(ge=1, description="Día de la historia, D1…Dn.")] = None,
        franja: Franja | None = None,
        momento: Annotated[
            str | None, Field(description="Solo un recuerdo: AAAA, AAAA-MM, AAAA-MM-DD o periodo.")
        ] = None,
        excluye: Exclusion | None = None,
    ) -> dict[str, Any]:
        """Un suceso de la historia (`dia` y, si se sabe, `franja`) o un recuerdo contado en
        analepsis (`momento`, sin `dia`). Uno de los dos, nunca ambos."""
        return escribir(
            sello,
            "registrar_evento",
            {
                "descripcion": descripcion,
                "lugar": lugar,
                "presentes": presentes,
                "dia": dia,
                "franja": franja,
                "momento": momento,
                "excluye": excluye.model_dump(mode="json") if excluye else None,
            },
            lambda p, n, _: biblia.registrar_evento(
                p.conexion,
                n,
                descripcion,
                lugar,
                presentes,
                dia=dia,
                franja=franja,
                momento=momento,
                excluye=(excluye.personaje, excluye.tipo) if excluye else None,
            ),
        )

    @herramienta("plantar_presagio", "Confirmar un presagio previsto")
    def plantar_presagio(sello: Sello, clave: Id) -> dict[str, Any]:
        """Confirma que el capítulo planta el presagio previsto con esta clave."""
        return escribir(
            sello,
            "plantar_presagio",
            {"clave": clave},
            lambda p, n, _: biblia.plantar_presagio(p.conexion, n, clave),
        )

    @herramienta("cobrar_presagio", "Cerrar un presagio")
    def cobrar_presagio(sello: Sello, clave: Id) -> dict[str, Any]:
        """Cierra un presagio plantado en un capítulo anterior."""
        return escribir(
            sello,
            "cobrar_presagio",
            {"clave": clave},
            lambda p, n, _: biblia.cobrar_presagio(p.conexion, n, clave),
        )

    @herramienta("abrir_presagio", "Abrir un presagio no previsto")
    def abrir_presagio(
        sello: Sello, clave: Id, descripcion: Annotated[str, Field(min_length=1)]
    ) -> dict[str, Any]:
        """Un presagio que la escaleta no preveía; nace plantado en este capítulo."""
        return escribir(
            sello,
            "abrir_presagio",
            {"clave": clave, "descripcion": descripcion},
            lambda p, n, _: biblia.abrir_presagio(p.conexion, n, clave, descripcion),
        )

    @herramienta("registrar_termino", "Nombre propio en el glosario")
    def registrar_termino(
        sello: Sello,
        termino: Id,
        categoria: CategoriaTermino,
        tipo: TipoTermino,
        referencia: Annotated[
            str | None, Field(description="Id al que se refiere; null solo en `otro`.")
        ] = None,
    ) -> dict[str, Any]:
        """Un nombre propio nuevo, o una grafía nueva, con su grafía exacta."""
        return escribir(
            sello,
            "registrar_termino",
            {"termino": termino, "categoria": categoria, "tipo": tipo, "referencia": referencia},
            lambda p, n, _: biblia.registrar_termino(
                p.conexion, n, termino, categoria, referencia, tipo
            ),
        )

    @herramienta("registrar_uso_de_hecho", "Uso de un hecho aportado")
    def registrar_uso_de_hecho(sello: Sello, hecho: Id) -> dict[str, Any]:
        """El capítulo usa de verdad este hecho aportado por el comprador (`hecho_uso`)."""
        return escribir(
            sello,
            "registrar_uso_de_hecho",
            {"hecho": hecho},
            lambda p, n, _: biblia.registrar_uso_de_hecho(p.conexion, n, hecho),
        )

    @herramienta("escribir_resumen_capitulo", "Resumen del capítulo y dónde termina")
    def escribir_resumen_capitulo(
        sello: Sello,
        texto: Annotated[str, Field(min_length=1, description="Hasta 240 palabras.")],
        dia_fin: Annotated[int, Field(ge=1, description="Día en que termina el capítulo.")],
        localizacion_fin: Annotated[str, Field(min_length=1, description="Id de localización.")],
    ) -> dict[str, Any]:
        """El resumen del capítulo (240 palabras como mucho), con el día y la localización en
        que termina."""

        def operacion(p: Proyecto, n: int, momento: str) -> None:
            with transaccion(p.conexion):
                biblia.escribir_resumen(p.conexion, n, "capitulo", texto, momento)
                biblia.registrar_fin(p.conexion, n, dia_fin, localizacion_fin)

        return escribir(
            sello,
            "escribir_resumen_capitulo",
            {"texto": texto, "dia_fin": dia_fin, "localizacion_fin": localizacion_fin},
            operacion,
        )

    @herramienta("escribir_resumen_acto", "Resumen del acto")
    def escribir_resumen_acto(
        sello: Sello,
        texto: Annotated[str, Field(min_length=1, description="Hasta 360 palabras.")],
    ) -> dict[str, Any]:
        """Solo si el capítulo cierra un acto: el acto entero en 360 palabras como mucho."""
        ambito: Literal["acto"] = "acto"
        return escribir(
            sello,
            "escribir_resumen_acto",
            {"texto": texto},
            lambda p, n, momento: biblia.escribir_resumen(p.conexion, n, ambito, texto, momento),
        )

    return servidor


def superficie(
    reloj: Callable[[], datetime] = dependencias.reloj,
    raiz: Callable[[], Path] = dependencias.raiz_proyectos,
) -> Starlette:
    """La aplicación HTTP que se monta en `RUTA`; su URL es `/mcp/escritura/`."""
    return crear_servidor(reloj, raiz).http_app(
        path="/",
        stateless_http=True,
        json_response=True,
        host_origin_protection="auto",
    )
