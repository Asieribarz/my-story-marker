---
name: regenerar
description: Entrada headless del worker de regeneración: /regenerar <proyecto> <trabajo>.
disable-model-invocation: true
argument-hint: <proyecto> <trabajo>
allowed-tools: Bash(uv run *), Agent, Skill
---

# /regenerar

Te lanza el worker del backend con `claude -p`, sin persona al otro lado. Los argumentos son `$0` (proyecto) y `$1` (trabajo). Llevas el proyecto hasta la próxima parada y terminas: toda decisión humana queda para la web.

## Pasos

1. Ejecuta la skill `orquestar-novela` con `$0 tipo=worker`.
2. Termina con una sola línea JSON: `{"trabajo": "$1", "proyecto": "$0", "decision": <la última decisión o el error, tal como llegó>}`.

Has terminado cuando imprimes esa línea. Sin preguntas: con `esperar_humano`, `publicada` o `detenida`, el trabajo ha llegado a su parada.
