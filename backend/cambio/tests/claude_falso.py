"""Un `claude` falso para probar el worker (TC-10). Lo lanza el worker con `sys.executable`.

El comportamiento lo elige `MSM_CLAUDE_FALSO`: `exito` deja el cambio propuesto, como haría
`/regenerar` al llegar a la parada; `sin_parada` sale bien sin tocar nada; `error` sale con
1; `bloqueo` sale con 1 como `claude` cuando no puede tomar el bloqueo; `cuelgue` no acaba;
`caida` muere con 137; `propone_y_falla` deja el cambio propuesto y sale con 1;
`nieto_colgado` lanza un nieto que escribe `MSM_CLAUDE_FALSO_MARCA` a los 4 s y se cuelga.
Cada lanzamiento añade su línea de argumentos, y si ve la clave de API, a
`MSM_CLAUDE_FALSO_REGISTRO`.
"""

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

argumentos = sys.argv[1:]
registro = Path(os.environ["MSM_CLAUDE_FALSO_REGISTRO"])
with registro.open("a", encoding="utf-8") as fichero:
    datos = {"argumentos": argumentos, "clave": "ANTHROPIC_API_KEY" in os.environ}
    fichero.write(json.dumps(datos) + "\n")

modo = os.environ["MSM_CLAUDE_FALSO"]
if modo == "nieto_colgado":
    import subprocess

    nieto = "import pathlib, sys, time; time.sleep(4); pathlib.Path(sys.argv[1]).write_text('vivo')"
    subprocess.Popen([sys.executable, "-c", nieto, os.environ["MSM_CLAUDE_FALSO_MARCA"]])
    time.sleep(120)
    sys.exit(0)
if modo in ("exito", "propone_y_falla"):
    proyecto = argumentos[argumentos.index("-p") + 1].split()[1]
    base = Path(os.environ["MSM_PROYECTOS"]) / proyecto / "proyecto.sqlite"
    conexion = sqlite3.connect(base)
    with conexion:
        conexion.execute(
            "UPDATE cambio_lector SET estado = 'propuesto' WHERE estado = 'interpretando'"
        )
    conexion.close()
    sys.exit(0 if modo == "exito" else 1)
if modo == "sin_parada":
    sys.exit(0)
if modo in ("error", "bloqueo"):
    sys.exit(1)
if modo == "cuelgue":
    time.sleep(120)
    sys.exit(0)
if modo == "caida":
    os._exit(137)
sys.exit(2)
