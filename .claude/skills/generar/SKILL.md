---
name: generar
description: Generar o reanudar la novela de un proyecto: /generar <proyecto>.
disable-model-invocation: true
argument-hint: <proyecto>
allowed-tools: Bash(uv run *), Agent, Skill
---

# /generar

Lleva el proyecto `$ARGUMENTS` tan lejos como deje el backend, y deja a la persona lo que solo puede decidir ella. Reanudar es lo mismo que empezar: el estado vive en el backend.

**MSM** es el comando de la skill `orquestar-novela`:

    uv run --project "${CLAUDE_PROJECT_DIR:-.}" --no-sync --quiet python "${CLAUDE_PROJECT_DIR:-.}/.claude/harness/msm.py"

## Pasos

1. Sin proyecto en los argumentos, enseña `MSM proyectos`, con la etiqueta o el título, el estado y los 6 primeros caracteres de cada uno, y pregunta cuál. Para uno nuevo, la entrada es `/entrevista`. `<proyecto>` puede ser el identificador entero o un prefijo único de al menos 4 caracteres: MSM lo resuelve. Si el prefijo es ambiguo, enseña los `candidatos` del error y pregunta. Desde aquí usa el `proyecto` entero que devuelve `MSM estado`.
2. `MSM estado <proyecto>`. Con código 5, pide a la persona que arranque el backend (`uv run uvicorn backend.app:app`) y para. Enseña el estado en una línea.
3. Ejecuta la skill `orquestar-novela` con `<proyecto> tipo=sesion`.
4. Cuando termine, explica la parada y lo que puede hacer la persona:

| Parada | Qué se le dice | Qué haces si responde |
|---|---|---|
| `esperar_humano` · `brief` | Falta el brief: `/entrevista` | — |
| `esperar_humano` · `confirmacion_hechos` | Enseña `MSM hechos <proyecto>`: cada hecho con su id, tipo y texto, y pregunta cuáles confirma | `MSM confirmar <proyecto> --si <ids> --no <ids>` con **su** respuesta, y vuelve al paso 3 |
| `esperar_humano` · `aprobacion_plan` o `aprobacion_final` | La parada está activa y espera su decisión; esta skill aún no tiene la ruta de aprobación | — |
| `detenida` | Enseña `MSM estado` y de qué fase viene: algún capítulo o la revisión agotó sus intentos | Si pide reintentar: `MSM reintentar <proyecto> --notas "<sus notas>"` y vuelve al paso 3 |
| `publicada` | La novela está publicada; se lee en la web | — |
| `error` · `no_cabe` | El prompt de un capítulo no cabe ni con la ficha sola (D-9): hay un dato mal formado | — |
| `error` · `inconsistencia` o `cronologia_invalida` | La ficha del capítulo choca con la biblia (B-9) o la cronología no se puede generar: enseña el `detalle` | — |
| `error` · `contexto_incoherente` | El contexto guardado no pasa el validador: enseña el `detalle` | — |
| `error` · `lean_no_disponible` | Falta Lean (`elan`/`lake`) en la máquina del backend: hay que instalarlo y volver a `/generar` | — |
| `error` · `pdf_no_disponible` | Falta el Chromium de Playwright: `uv run playwright install chromium` y volver a `/generar` | — |
| `error` · `revision_sin_capitulos` | El juez suspendió sin señalar capítulos: enseña el `detalle` | — |
| `error` · `peticion_no_disponible` | No hay petición de cambio que interpretar | — |
| Error de MSM | El JSON del error, tal cual | — |

Las decisiones de la tabla son de la persona: confirma, aprueba o reintenta solo con lo que ella diga, nunca por defecto.
