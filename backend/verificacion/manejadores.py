"""Manejador de `juez-manuscrito` (RF-113, RF-77a, TC-4, TC-5).

Lo agrega `proyecto/manejadores.py`. El juez puntúa y el backend decide: con la salida
válida se persiste `informe_juez` y la fila `juez` de `gate_resultado` de la pasada en
curso, y el desenlace es `aceptado`. Con las tres filas de la pasada, el cerebro decide
(`persistencia._gates` → `maquina._gates`): verdes, publicación o parada final; alguna roja,
revisión con los capítulos de `detalle.capitulos` (M-6).
"""

from collections.abc import Mapping

from pydantic import ValidationError

from backend.proyecto.manejadores import ContextoManejo, Manejador, Salida
from backend.proyecto.maquina import Desenlace
from backend.shared.db import transaccion
from backend.shared.tipos import Agente, Gate
from backend.verificacion.consultas import guardar_evaluacion, guardar_gate, proyecto_en_curso
from backend.verificacion.modelos import SalidaJuezManuscrito


def _errores(error: ValidationError) -> list[str]:
    """Ruta y mensaje de cada error, sin el valor recibido."""
    return [
        f"{'.'.join(str(p) for p in e['loc']) or '(raíz)'}: {e['msg']}"
        for e in error.errors(include_url=False)
    ]


def _juez_de_manuscrito(contexto: ContextoManejo, resultado: object) -> Salida:
    try:
        salida = SalidaJuezManuscrito.model_validate(resultado)
    except ValidationError as error:
        return Salida(Desenlace.forma(), {"errores": _errores(error)})
    conexion = contexto.conexion
    pasada, ciclo, version = proyecto_en_curso(conexion)
    if pasada < 1:
        raise ValueError("juez-manuscrito fuera de una pasada de verificación (AJ-3)")
    evaluacion = f"juez-orden-{contexto.orden.id}"
    detalle = {
        "capitulos": sorted(set(salida.capitulos)),
        "puntuaciones": salida.puntuaciones,
        "suma": salida.suma,
        "evaluacion": evaluacion,
    }
    with transaccion(conexion):
        guardar_evaluacion(conexion, evaluacion, "juez", version, ciclo, salida, contexto.momento)
        guardar_gate(conexion, pasada, Gate.JUEZ, salida.aprueba, detalle, reemplazar=True)
    return Salida(Desenlace.aceptado(), {**detalle, "ok": salida.aprueba, "pasada": pasada})


MANEJADORES: Mapping[Agente, Manejador] = {Agente.JUEZ_MANUSCRITO: _juez_de_manuscrito}
