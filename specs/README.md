# specs/ — Especificaciones

Una **spec** describe qué debe hacer una parte del sistema y por qué, antes de que exista el código. Es el artefacto que se discute, se aprueba y se versiona; el código es su consecuencia.

## Qué va aquí y qué va en docs/

| | `docs/` | `specs/` |
|---|---|---|
| Responde a | Qué es el sistema y cómo está pensado | Qué vamos a construir a continuación |
| Horizonte | Permanente | Una unidad de trabajo |
| Cambia cuando | Cambia el dominio, la ontología o la arquitectura | Se aborda un trabajo nuevo |
| Ejemplos | `domain-knowledge.md`, `definitions.md`, `architecture.md`, `validators.md` | El esquema del contexto, el endpoint de intake, el Escaletista |

Los `docs/` son el **contexto**: lo que hay que saber para entender cualquier spec. Las specs son **encargos**: acotados, con criterios de aceptación, y terminan.

## Índice

| Spec | Contenido |
|---|---|
| [spec-driven-development.md](spec-driven-development.md) | El ciclo de trabajo completo: de la intención al código y de vuelta a los docs. Es la spec que gobierna a las demás. |
| [_template.md](_template.md) | Plantilla para una spec nueva. |

## Convenciones

- Un fichero por spec, en kebab-case, con nombre que describa el resultado y no la tarea: `chapter-loop.md`, no `implementar-bucle.md`.
- Cada spec declara su **estado**: `borrador`, `acordada`, `implementada`, `obsoleta`.
- Una spec obsoleta no se borra: se marca y se dice qué la sustituye. El historial de por qué algo es como es vale tanto como el estado actual.
