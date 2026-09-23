"""El catálogo de errores de `proyecto/`: un código por clase y un requisito en cada una.

Los errores de entrada —validación y ruta inexistente— no infringen ningún requisito: son
los únicos con `requisito` a `None`.
"""

from backend.proyecto import errores
from backend.proyecto.errores import CodigoError, ErrorProyecto


def test_cada_error_tiene_su_codigo_y_su_requisito() -> None:
    clases = [
        valor
        for valor in vars(errores).values()
        if isinstance(valor, type)
        and issubclass(valor, ErrorProyecto)
        and valor is not ErrorProyecto
    ]
    assert {c.codigo for c in clases} == set(CodigoError)
    assert len(clases) == len(CodigoError)
    assert all(c.requisito is None or c.requisito.startswith("RF-") for c in clases)
    assert {c.codigo for c in clases if c.requisito is None} == {
        CodigoError.VALIDACION,
        CodigoError.NO_ENCONTRADO,
    }
