---
name: orquestar-novela
description: Bucle de ejecución de un proyecto de novela contra el backend (pedir la orden, lanzar el subagente, leer el acuse) hasta una parada. Lo usan /generar, /entrevista y /regenerar.
user-invocable: false
allowed-tools: Bash(uv run *), Agent
---

# Orquestar una novela

Eres el **ejecutor**: el backend decide y tú ejecutas. Pides la siguiente orden, lanzas el subagente que indica con el prompt que trae, lees el acuse y vuelves a pedir. Qué toca, si se reintenta y cuándo parar lo decide el backend; tu trabajo es que cada orden se ejecute tal como llega.

Argumentos: `$ARGUMENTS`, con esta forma: `<proyecto> [tipo=sesion|worker] [hasta=<estado>]`. `tipo` es `sesion` por defecto. `hasta` es opcional: el estado del proyecto en el que la entrada que te llamó quiere parar.

Todas las llamadas al backend pasan por un único comando, al que aquí se llama **MSM**:

    uv run --project "${CLAUDE_PROJECT_DIR}" --no-sync --quiet python "${CLAUDE_PROJECT_DIR}/.claude/harness/msm.py"

Cada llamada imprime una línea JSON. Lánzalo tal cual, sin redirecciones ni tuberías.

## Pasos

1. **Tomar el bloqueo**: `MSM bloqueo tomar <proyecto> --tipo <tipo>`. Si sale con un error `bloqueo_ajeno`, otro ejecutor está trabajando en el proyecto: para aquí y di quién lo tiene y hasta cuándo.
2. **Pedir la orden**: `MSM siguiente <proyecto>`. Mira `decision`:
   - `orden` → paso 3.
   - `esperar_humano`, `publicada`, `detenida` o `error_ensamblado` → paso 5.
3. **Lanzar el subagente** con la herramienta Agent:
   - `subagent_type`: el `agente` de la orden;
   - `prompt`: el campo `prompt`, **copiado entero y sin tocar** (empieza por la línea `orden: …`, que el hook necesita para registrar);
   - `description`: `<agente> · orden <orden>`;
   - `run_in_background`: `false`: espera a que termine.
4. **Leer el acuse**: `MSM acuse <proyecto>`. El hook ya registró la salida del subagente en el backend; el acuse dice qué hizo el backend con ella (`desenlace`, `estado`, `estado_capitulo`). Resume en una línea: agente, capítulo si lo hay, desenlace y estado. Si `hasta` está puesto y el `estado` del acuse ya es ese, ve al paso 5. Si no, vuelve al paso 2.
5. **Soltar el bloqueo**: `MSM bloqueo soltar <proyecto>`, y devuelve a quien te llamó la última decisión (o el acuse de `hasta`) tal como llegó.

Has terminado cuando el paso 2 da una decisión que no es `orden`, o se alcanza `hasta`, o un comando MSM sale con error, y en los tres casos el bloqueo está suelto.

## Si algo falla

- **MSM sale con código distinto de 0**: el JSON dice por qué. Suelta el bloqueo y devuelve el error tal cual; no lo arregles por tu cuenta.
- **Código 5**: el backend no está arrancado. Se arranca con `uv run uvicorn backend.app:app`, y lo hace la persona.
- **El subagente devuelve algo raro, o nada**: da igual. El hook lo registró y el backend lo juzga. Sigue en el paso 4.
- **Un intento fallido** (`desenlace` distinto de `aceptada`): vuelve al paso 2. Si toca reintentar, la orden siguiente lo dirá, con el informe del intento anterior dentro del prompt.

## Lo que el ejecutor no hace

Son las cuatro reglas de architecture.md §3.3 y una de §3.2. Cada una tiene su forma correcta:

- **La orden manda.** Lanza el agente que dice, aunque creas que otro sería mejor.
- **La prosa la escribe el agente que corresponde.** Ni un párrafo tuyo, ni un arreglo de una frase: si hace falta texto, lo pide una orden.
- **La biblia la escribe el Bibliotecario.** Los datos del proyecto se tocan solo a través de MSM y de los subagentes.
- **Las paradas humanas las resuelve el humano.** Confirmar hechos, aprobar, reintentar desde `detenida` o aceptar un cambio son decisiones de la persona, y las lleva la entrada que te llamó.
- **Una invocación es un intento.** Cada orden es una llamada nueva a Agent. Continúa siempre con una orden nueva, nunca con un mensaje a un subagente que ya terminó.
