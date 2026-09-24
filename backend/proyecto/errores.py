"""Errores de `proyecto/`: uno por caso, cada uno con su código y el requisito que hace cumplir.

La API los traduce a su modelo de error (spec-backend-1.md §5.1): código, requisito infringido y
detalle accionable (el mensaje). Una transición inválida no es un error de validación de
entrada, y por eso tiene su propia clase en vez de un `ValueError` genérico.

`CodigoError` es el catálogo de códigos; las rebanadas que añadan errores propios lo
amplían aquí, para que siga estando en un solo sitio. Los dos errores de entrada
—`EntradaInvalida` y `NoEncontrado`— no infringen ningún requisito: su `requisito` es `None`.
"""

from datetime import datetime
from enum import StrEnum
from typing import ClassVar

from backend.shared.tipos import Agente, EstadoProyecto, TipoEjecutor


class CodigoError(StrEnum):
    PROYECTO_INEXISTENTE = "proyecto_inexistente"
    TRANSICION_INVALIDA = "transicion_invalida"
    BLOQUEO_AJENO = "bloqueo_ajeno"
    BLOQUEO_REQUERIDO = "bloqueo_requerido"
    ORDEN_AJENA = "orden_ajena"
    SELLO_INVALIDO = "sello_invalido"
    AGENTE_SIN_ESQUEMA = "agente_sin_esquema"
    DECISION_HUMANA_INVALIDA = "decision_humana_invalida"
    ENTRADA_NO_CANJEABLE = "entrada_no_canjeable"
    PROYECTO_EN_USO = "proyecto_en_uso"
    VALIDACION = "validacion"
    NO_ENCONTRADO = "no_encontrado"
    HERRAMIENTA_NO_DISPONIBLE = "herramienta_no_disponible"
    CAMBIO_INEXISTENTE = "cambio_inexistente"


class ErrorProyecto(Exception):
    codigo: ClassVar[CodigoError]
    requisito: ClassVar[str | None]


class ProyectoInexistente(ErrorProyecto, LookupError):
    codigo = CodigoError.PROYECTO_INEXISTENTE
    requisito = "RF-02"

    def __init__(self, identificador: str) -> None:
        super().__init__(f"no existe el proyecto {identificador}")
        self.identificador = identificador


class TransicionInvalida(ErrorProyecto):
    """RF-04: la tabla de transiciones no tiene esa arista. La fila no se modifica."""

    codigo = CodigoError.TRANSICION_INVALIDA
    requisito = "RF-04"

    def __init__(
        self,
        origen: EstadoProyecto,
        destino: EstadoProyecto | None,
        causa: str,
        motivo: str | None = None,
    ) -> None:
        hacia = destino.value if destino is not None else "ningún estado"
        mensaje = f"no hay transición de {origen.value} a {hacia} por «{causa}»"
        super().__init__(mensaje if motivo is None else f"{mensaje}: {motivo}")
        self.origen = origen
        self.destino = destino
        self.causa = causa


class BloqueoAjeno(ErrorProyecto):
    """RF-09b: otro ejecutor tiene el bloqueo vigente. Dice quién y hasta cuándo."""

    codigo = CodigoError.BLOQUEO_AJENO
    requisito = "RF-09b"

    def __init__(self, tipo: TipoEjecutor, caduca: datetime) -> None:
        super().__init__(
            f"el proyecto lo está ejecutando otro ejecutor ({tipo.value}); "
            f"su bloqueo caduca a las {caduca.isoformat()} si no lo renueva"
        )
        self.tipo = tipo
        self.caduca = caduca


class BloqueoRequerido(ErrorProyecto):
    """RF-09b: pedir orden o registrar resultado exige el token del bloqueo vigente."""

    codigo = CodigoError.BLOQUEO_REQUERIDO
    requisito = "RF-09b"

    def __init__(self, motivo: str) -> None:
        super().__init__(f"hace falta el bloqueo del proyecto: {motivo}")


class OrdenAjena(ErrorProyecto):
    """RF-08a: el resultado no es de la orden vigente, o repite otra con un resultado distinto."""

    codigo = CodigoError.ORDEN_AJENA
    requisito = "RF-08a"

    def __init__(self, orden: int, vigente: int | None, motivo: str) -> None:
        cual = f"la vigente es la {vigente}" if vigente is not None else "no hay orden vigente"
        super().__init__(f"el resultado para la orden {orden} se rechaza: {motivo}; {cual}")
        self.orden = orden
        self.vigente = vigente


class SelloInvalido(ErrorProyecto):
    """AJ-4, RF-08a: el sello no es el de la orden vigente. Es de una orden que no existe o de
    una generación anterior del bloqueo: un ejecutor caído, o un subagente suyo que acaba
    tarde. Su resultado o su escritura no se registran."""

    codigo = CodigoError.SELLO_INVALIDO
    requisito = "RF-08a"

    def __init__(self, motivo: str) -> None:
        super().__init__(f"el sello no es el de la orden vigente: {motivo}")


class AgenteSinEsquema(ErrorProyecto):
    """RF-77a: el agente todavía no tiene esquema de salida. No gasta intento ni cierra la orden."""

    codigo = CodigoError.AGENTE_SIN_ESQUEMA
    requisito = "RF-77a"

    def __init__(self, agente: Agente, paso: str) -> None:
        super().__init__(
            f"el resultado de «{agente.value}» aún no se puede registrar: su esquema de "
            f"salida llega en el {paso} del plan (specs/plan-backend-v1.md); la orden sigue "
            "vigente y no ha gastado intento"
        )
        self.agente = agente
        self.paso = paso


class DecisionHumanaInvalida(ErrorProyecto, ValueError):
    """RF-05, RF-36: la decisión no existe o no se puede tomar todavía en esta parada."""

    codigo = CodigoError.DECISION_HUMANA_INVALIDA
    requisito = "RF-05"


class EntradaNoCanjeable(ErrorProyecto, LookupError):
    """RF-14, RF-120: el identificador de `/mcp/entrada` no da acceso a ningún texto.

    Desconocido, ya usado, caducado, mal formado o de un proyecto que no existe: los cinco
    dan esta misma excepción con el mismo mensaje. Distinguirlos sería un oráculo para una
    instrucción inyectada que pruebe identificadores (V-29).
    """

    codigo = CodigoError.ENTRADA_NO_CANJEABLE
    requisito = "RF-14"

    def __init__(self) -> None:
        super().__init__(
            "el identificador de entrada no da acceso a ningún texto: es desconocido, ya se "
            "usó, ha caducado o está mal formado"
        )


class ProyectoEnUso(ErrorProyecto):
    """RF-09a: el proyecto no se puede borrar mientras otra petición lo tiene abierto. No se
    ha borrado nada: el borrado es entero o no es."""

    codigo = CodigoError.PROYECTO_EN_USO
    requisito = "RF-09a"

    def __init__(self, identificador: str) -> None:
        super().__init__(
            f"el proyecto {identificador} está abierto por otra petición en curso y no se ha "
            "borrado nada; vuelve a intentarlo cuando acabe"
        )
        self.identificador = identificador


class HerramientaNoDisponible(ErrorProyecto):
    """TC-3: falta una herramienta del backend (Lean, Chromium) al registrar un resultado que
    la necesita —publicar exige imprimir el PDF—. Nada se registra: la orden sigue vigente y
    no gasta intento. `causa` es la de la decisión `error` (`pdf_no_disponible`…)."""

    codigo = CodigoError.HERRAMIENTA_NO_DISPONIBLE
    requisito = "RF-98"

    def __init__(self, causa: str) -> None:
        super().__init__(
            f"falta una herramienta del backend ({causa}): el resultado no se ha registrado y "
            "la orden sigue vigente sin gastar intento; vuelve a enviarlo cuando esté instalada"
        )
        self.causa = causa


class CambioInexistente(ErrorProyecto, LookupError):
    """RF-122: el proyecto no tiene un cambio del lector con ese número."""

    codigo = CodigoError.CAMBIO_INEXISTENTE
    requisito = "RF-122"

    def __init__(self, cambio: int) -> None:
        super().__init__(f"el proyecto no tiene el cambio {cambio}")
        self.cambio = cambio


class EntradaInvalida(ErrorProyecto, ValueError):
    """La petición no cumple el esquema de su ruta. Es un error de entrada, no del grafo:
    se distingue de `TransicionInvalida` (spec-backend-1.md §5.1). La API da el mismo código a los
    errores de validación de FastAPI."""

    codigo = CodigoError.VALIDACION
    requisito = None


class NoEncontrado(ErrorProyecto, LookupError):
    """La ruta pedida no existe. Un proyecto que no existe es `ProyectoInexistente`."""

    codigo = CodigoError.NO_ENCONTRADO
    requisito = None
