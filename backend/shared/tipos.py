"""Tipos comunes a varias rebanadas: estados, severidad, hallazgo e informe.

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
