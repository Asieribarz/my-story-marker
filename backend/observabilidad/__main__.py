"""`uv run python -m backend.observabilidad <proyecto>… | --todos | --prompts`.

Envía a Langfuse los proyectos indicados (o todos los de la raíz) y, antes, las versiones
de prompt de `.claude/agents/`. Con `--prompts`, solo las versiones de prompt.
"""

import sys

from backend.observabilidad.cliente import ClienteLangfuse
from backend.observabilidad.configuracion import de_entorno
from backend.observabilidad.exportar import exportar_proyecto, sincronizar_prompts
from backend.shared.rutas import DisposicionProyecto, identificadores_en


def main(argumentos: list[str]) -> int:
    configuracion = de_entorno()
    if configuracion is None:
        print(
            "Sin LANGFUSE_PUBLIC_KEY y LANGFUSE_SECRET_KEY (entorno o .env), o con "
            "MSM_LANGFUSE=0: no se envía nada.",
            file=sys.stderr,
        )
        return 1
    if not argumentos:
        print(__doc__, file=sys.stderr)
        return 2
    cliente = ClienteLangfuse(configuracion)
    try:
        versiones = sincronizar_prompts(cliente)
        print(f"prompts: {len(versiones)} agentes sincronizados")
        if argumentos == ["--prompts"]:
            return 0
        proyectos = identificadores_en() if argumentos == ["--todos"] else argumentos
        for identificador in proyectos:
            disposicion = DisposicionProyecto.de(identificador)
            resumen = exportar_proyecto(disposicion, cliente, versiones)
            print(f"{resumen.proyecto}: {resumen.spans} observaciones, {resumen.scores} scores")
    finally:
        cliente.cerrar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
