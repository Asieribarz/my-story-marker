"""El manejador del Exportador (TC-4): validar sus metadatos y publicar.

En `publicacion`, se publica al registrar el resultado del Exportador. Una salida que no
encaja en `SalidaExportador` es un fallo de forma y no publica nada (RF-77a); aceptada, la
versión N+1 queda en disco y en la base, y el desenlace aceptado lleva el proyecto de
`publicacion` a `publicada` (`maquina._desenlace_de_paso`, causa `version_publicada`).
"""

from pydantic import ValidationError

from backend.exportacion.modelos import SalidaExportador
from backend.exportacion.publicar import publicar
from backend.proyecto.manejadores import ContextoManejo, Manejador, Salida
from backend.proyecto.maquina import Desenlace
from backend.shared.tipos import Agente


def _errores(error: ValidationError) -> list[str]:
    """Ruta y mensaje de cada error, sin el valor recibido."""
    return [
        f"{'.'.join(str(parte) for parte in e['loc']) or '(raíz)'}: {e['msg']}"
        for e in error.errors(include_url=False)
    ]


def _exportador(contexto: ContextoManejo, resultado: object) -> Salida:
    """RF-91, TC-4. `ErrorPublicacion` (RF-93) y `OrdenNoEmitible` (`pdf_no_disponible`,
    TC-3) se propagan: no son un intento fallido del agente."""
    try:
        metadatos = SalidaExportador.model_validate(resultado)
    except ValidationError as error:
        return Salida(Desenlace.forma(), {"errores": _errores(error)})
    numero = publicar(contexto.conexion, contexto.proyecto.disposicion, metadatos, contexto.momento)
    return Salida(Desenlace.aceptado(), {"version": numero})


MANEJADORES: dict[Agente, Manejador] = {Agente.EXPORTADOR: _exportador}
