"""Tipos comunes a varias rebanadas: estados, agentes, severidad, hallazgo e informe.

Los valores de los enumerados son los de architecture.md §3.1 y §6 y spec1.md §4.6.3.
`shared/esquema.sql` repite las mismas listas en sus CHECK; una prueba comprueba que
coinciden.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EstadoProyecto(StrEnum):
    INTAKE = "intake"
    CONTEXTO = "contexto"
    PLANIFICACION = "planificacion"
    APROBACION_PLAN = "aprobacion_plan"
    ESCALETA = "escaleta"
    CAPITULOS = "capitulos"
    VERIFICACION_MANUSCRITO = "verificacion_manuscrito"
    REVISION = "revision"
    APROBACION_FINAL = "aprobacion_final"
    PUBLICACION = "publicacion"
    PUBLICADA = "publicada"
    CAMBIO_SOLICITADO = "cambio_solicitado"
    REGENERACION = "regeneracion"
    DETENIDA = "detenida"


class EstadoCapitulo(StrEnum):
    # `pendiente` es el capítulo que aún no tiene borrador: su contador de intentos ya
    # existe, porque un resultado fuera de esquema consume intento (RF-77a).
    PENDIENTE = "pendiente"
    BORRADOR = "borrador"
    EDITADO = "editado"
    VERIFICADO = "verificado"
    APROBADO = "aprobado"
    REVISION_HUMANA = "revision_humana"


class Agente(StrEnum):
    """Los subagentes de architecture.md §3 y sus jueces, con el nombre de su fichero en
    `.claude/agents/` (specs/plan-entrega.md §4). La tabla `orden` repite la lista."""

    AGENTE_CONTEXTO = "agente-contexto"
    EXTRACTOR_HECHOS = "extractor-hechos"
    ARQUITECTO = "arquitecto"
    PERSONAJES = "personajes"
    MUNDO = "mundo"
    ESTILO = "estilo"
    ESCALETISTA = "escaletista"
    ESCRITOR = "escritor"
    EDITOR_ESTILO = "editor-estilo"
    JUEZ_CAPITULO = "juez-capitulo"
    BIBLIOTECARIO = "bibliotecario"
    JUEZ_MANUSCRITO = "juez-manuscrito"
    REVISOR = "revisor"
    EXPORTADOR = "exportador"
    INTERPRETE_CAMBIOS = "interprete-cambios"


class DesenlaceOrden(StrEnum):
    """Cómo se cerró una orden: con su resultado aceptado, rechazado o sin resultado porque
    una acción humana movió el proyecto mientras estaba vigente."""

    ACEPTADA = "aceptada"
    RECHAZADA = "rechazada"
    CADUCADA = "caducada"


class TipoEjecutor(StrEnum):
    """Quién tiene el bloqueo del proyecto (RF-09b): la sesión interactiva o el worker."""

    SESION = "sesion"
    WORKER = "worker"


class RecursoEntrada(StrEnum):
    """El texto no confiable al que da acceso un identificador de `/mcp/entrada`: el texto
    libre del comprador (RF-14) o la petición del lector (RF-120). La tabla
    `identificador_entrada` repite la lista."""

    TEXTO_LIBRE = "texto_libre"
    PETICION = "peticion"


class Severidad(StrEnum):
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
    BLOQUEANTE = "bloqueante"

    @property
    def corta_el_ciclo(self) -> bool:
        """RF-77: un hallazgo alto o bloqueante corta el ciclo antes de los jueces."""
        return self in (Severidad.ALTA, Severidad.BLOQUEANTE)


class Hallazgo(BaseModel):
    """RF-78: verificador, severidad, localización, evidencia citada y regla infringida."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    verificador: str
    severidad: Severidad
    regla: str
    localizacion: str
    evidencia: str
    esperado: str | None = None


class Informe(BaseModel):
    """Salida común de todo verificador: entra el objeto verificado, sale esto."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    verificador: str
    hallazgos: tuple[Hallazgo, ...] = Field(default=())

    @property
    def corta_el_ciclo(self) -> bool:
        return any(h.severidad.corta_el_ciclo for h in self.hallazgos)
