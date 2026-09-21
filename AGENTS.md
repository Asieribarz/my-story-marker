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

## Cómo se trabaja

Desarrollo dirigido por especificaciones. El ciclo completo está en [specs/spec-driven-development.md](specs/spec-driven-development.md); estas son las tres reglas que no se saltan:

1. **Interroga antes de escribir.** Antes de modificar `docs/`, `specs/` o código, invoca el skill `grilling` (plugin `mattpocock-skills`) y sigue su protocolo: árbol de decisión, rondas de preguntas numeradas con tu recomendación en cada una, y espera a las respuestas antes de la siguiente ronda. Los hechos los averiguas tú leyendo el repositorio; a la persona solo le llevas decisiones. No rellenes los huecos por tu cuenta. Al cerrar, el acuerdo se escribe en la spec correspondiente antes de tocar nada. Excepciones: erratas, formato y lo que la persona ya haya dejado inequívoco — o cuando te diga explícitamente que te lo saltes.
2. **No implementes sin spec acordada.** El código no es el sitio donde se decide qué hay que hacer. Si al implementar aparece algo que la spec no previó, vuelve a preguntar.
3. **Actualiza el contexto al terminar.** Todo cambio de código termina revisando qué documentos de `docs/` han quedado desfasados y actualizándolos en el mismo commit. Di explícitamente cuáles tocaste y cuáles no aplicaban.

El índice de especificaciones está en [specs/README.md](specs/README.md), y las specs nuevas parten de [specs/_template.md](specs/_template.md).

El skill `grilling` viene del plugin `mattpocock-skills`, del marketplace oficial. Si no lo tienes: `claude plugin install mattpocock-skills`.

## Stack

Lo único decidido: **backend en Python con FastAPI** y **frontend en React con Vite**.

Todo lo demás (orquestación de agentes, base de datos, índice vectorial, cola de trabajos, almacén de objetos, observabilidad, exportación, despliegue) está sin decidir — ver [docs/architecture.md](docs/architecture.md) §7. No introduzcas ninguna de esas dependencias por iniciativa propia: propón la decisión, y si se acepta, añádela a esa tabla en el mismo cambio.
