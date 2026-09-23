"""Manejadores de `escritor`, `editor-estilo`, `juez-capitulo` y `bibliotecario` (RF-77a).

Los agrega `proyecto/manejadores.py`. Contrato: `Manejador`, `ContextoManejo` y
`Salida`, de `backend.proyecto.manejadores`.
"""

from collections.abc import Mapping

from backend.proyecto.manejadores import Manejador
from backend.shared.tipos import Agente

MANEJADORES: Mapping[Agente, Manejador] = {}
