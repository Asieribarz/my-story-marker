# AGENTS.md — my-story-marker

Generador de novelas de aventura por agentes: convierte un brief de editor en un manuscrito verificado.

## Alcance de esta rama (importante)

Esta rama es `project-v2`, un **orphan branch vacío**: solo contiene `docs/`. No hay código todavía.

- Considera como fuente de verdad **únicamente lo que existe en esta rama**. Ignora `main` y cualquier historial, convención o código anterior: no aplica aquí.
- Si algo no está en `docs/` ni en esta rama, no existe todavía. No lo asumas: pregúntalo o propónlo explícitamente.
- Al crear la estructura del proyecto, parte de cero siguiendo `docs/architecture.md`, no de un esqueleto heredado.

## Documentación de referencia

Léela antes de proponer diseño o escribir código. Los tres documentos son consistentes entre sí y deben seguir siéndolo:

| Documento | Qué contiene |
|---|---|
| [docs/domain-knowledge.md](docs/domain-knowledge.md) | Árbol de conocimiento del dominio (8 dimensiones + pipeline de decisión), en Mermaid. Los nodos hoja son claves del objeto de contexto. |
| [docs/definitions.md](docs/definitions.md) | Diccionario de cada nodo: definición, valores permitidos, parámetros y ejemplo de instancia YAML. Es la base del esquema de validación. |
| [docs/architecture.md](docs/architecture.md) | Capas, agentes, verificadores, ciclo de capítulo, modelo de datos, tecnología y fases de construcción. |

Si un cambio de código altera la ontología, los valores permitidos o el flujo, actualiza el documento correspondiente en el mismo cambio.
