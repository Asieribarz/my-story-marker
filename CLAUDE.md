@AGENTS.md

## Claude-specific notes

- Trabaja siempre sobre la rama `project-v2` y trátala como el único contexto válido: no consultes ni copies nada de `main`.
- Lee los documentos de `docs/` antes de planificar. Son largos pero autocontenidos; no infieras el dominio a partir del nombre del repo.
- Los diagramas de `docs/` son Mermaid. Al editarlos, mantén el estilo existente (`flowchart LR`, ids cortos tipo `E1`, `T2a`) y comprueba que el diagrama sigue siendo válido.
- No crees código de aplicación sin que exista una decisión explícita en `docs/architecture.md` que lo respalde; si falta, propón primero el cambio de documento.
- **Tope de 100.000 tokens de entrada por agente.** Vale para cada subagente de la novela: lo que le pases —ficha, contexto recuperado, guía de estilo, capítulos anteriores— tiene que caber ahí. Acota la entrada, no la salida: no hay presupuesto de salida. Los bloques y el orden de recorte están en `docs/architecture.md` §6.3.
- **Ese tope no es el límite del modelo, es la decisión de no usarlo entero.** Los modelos actuales tienen ventanas de un orden de magnitud mayor. Los 100.000 son una disciplina deliberada: un Escritor con la biblia entera volcada no escribe mejor, escribe peor y más caro, y el Recuperador de contexto existe precisamente porque seleccionar vence a volcar. Si el tope fuese la ventana del modelo, el Recuperador sobraría y el orden de recorte de §6.3 no se ejecutaría nunca. Subirlo es una decisión que se mide contra la calidad del capítulo, no un hueco que se rellena.

## Harness de la novela

Configuración de Claude Code que convierte el backend en una novela. Detalle y contratos en `specs/plan-agentes.md`.

- **Lanzar una novela:** con el backend arrancado (`uv run uvicorn backend.app:app`, en `http://127.0.0.1:8000`), `/entrevista` crea el proyecto y deja el contexto validado; `/entrevista evals/briefs/eN-….json` hace lo mismo con un brief de evaluación. `/generar <proyecto>` sigue o reanuda. El worker del backend lanza `/regenerar <proyecto> <trabajo>` con `claude -p`, nunca con `--bare`.
- **La sesión ejecuta y el backend decide.** El bucle es la skill `orquestar-novela`: pedir la orden, lanzar el subagente con el prompt que trae, leer el acuse. Todo pasa por `.claude/harness/msm.py`. Lo que el orquestador no hace está en esa skill y en `docs/architecture.md` §3.3.
- **La carpeta tiene que ser de confianza.** Sin el diálogo de confianza aceptado, Claude Code no conecta los servidores MCP del frontmatter, y el Extractor, el Intérprete y el Bibliotecario no arrancan. En un clon nuevo, abre Claude Code una vez en el repo antes de generar.
- **Hooks** (`.claude/settings.json`):
  - La **policy** deniega leer el texto no confiable (`brief/`, `cambios/`, `texto_libre*.txt`) y escribir en `proyectos/` con las herramientas de fichero; la escritura en la biblia solo se le permite al Bibliotecario. Una denegación es intencionada: a esos datos se llega por `msm.py`, la API o el MCP.
  - El hook de **`SubagentStop`** registra en el backend la salida de cada subagente de la novela.
  - El estado local va a `.claude/estado/`, que git ignora.
- **Pruebas del harness:** `uv run pytest .claude/tests`. No entran en las cuatro del backend. `ruff` mira solo `backend/` (`include` en `pyproject.toml`): para `.claude/` pásale los ficheros, no la carpeta, con `--no-force-exclude` (`uv run ruff check --no-force-exclude .claude/harness/*.py .claude/tests/*.py`).
- **Las definiciones de agentes se cargan al abrir la sesión** (S-12): tras editar `.claude/agents/`, genera en una sesión nueva.
