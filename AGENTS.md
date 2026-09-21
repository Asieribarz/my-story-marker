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

Todo diagrama o grafo, en `docs/` o en cualquier otro sitio del repositorio, se escribe en formato Mermaid: no se usan imágenes, ASCII art ni ningún otro formato.

## Cómo se trabaja

Tres reglas que no se saltan:

1. **Interroga antes de escribir.** Antes de modificar `docs/` o código, invoca el skill `grilling` (plugin `mattpocock-skills`) y sigue su protocolo: árbol de decisión, rondas de preguntas numeradas con tu recomendación en cada una, y espera a las respuestas antes de la siguiente ronda. Los hechos los averiguas tú leyendo el repositorio; a la persona solo le llevas decisiones. No rellenes los huecos por tu cuenta. Al cerrar, di por escrito qué has entendido, qué decisiones se han tomado y qué supuestos aplicas, antes de tocar nada. Excepciones: erratas, formato y lo que la persona ya haya dejado inequívoco — o cuando te diga explícitamente que te lo saltes.
2. **No implementes sin acuerdo explícito.** El código no es el sitio donde se decide qué hay que hacer. Si al implementar aparece algo que el acuerdo no previó, vuelve a preguntar; no lo resuelvas sobre la marcha.
3. **Actualiza el contexto al terminar.** Todo cambio de código termina revisando qué documentos de `docs/` han quedado desfasados y actualizándolos en el mismo cambio, según esta tabla. Di explícitamente cuáles tocaste y cuáles no aplicaban: un "no aplicaba" declarado vale, un silencio no. No hagas commit ni push: los pide la persona a mano, y pedir un commit no autoriza el push.

| Si el cambio afecta a… | Actualizar |
|---|---|
| Las claves, valores permitidos o estructura del objeto de contexto | [docs/definitions.md](docs/definitions.md) |
| Las dimensiones del dominio o el pipeline de decisión | [docs/domain-knowledge.md](docs/domain-knowledge.md) |
| Capas, agentes, verificadores, flujo, modelo de datos o despliegue | [docs/architecture.md](docs/architecture.md) |
| La pila tecnológica: cualquier dependencia nueva | [docs/architecture.md](docs/architecture.md) §7 **y** este fichero |
| Los métodos de verificación en uso | [docs/validators.md](docs/validators.md) |
| Convenciones de trabajo o de nombres | Este fichero |
| Nada de lo anterior | Nada, y se dice |

La dirección importa: los `docs/` **siguen** al código, no lo preceden. Registran lo que quedó hecho.

El skill `grilling` viene del plugin `mattpocock-skills`, del marketplace oficial. Si no lo tienes: `claude plugin install mattpocock-skills`.

## Stack

Lo decidido: **backend en Python con FastAPI**, **frontend en React con Vite**, **orquestación con Claude Code** — la sesión recorre el grafo de estados y cada agente de la novela es un subagente suyo; no se escribe un orquestador en código — **acceso de los agentes a la biblia por un servidor MCP** sobre esa base — herramientas tipadas, escritura reservada al Bibliotecario — y **SQLite local** como base de datos, un fichero por proyecto que cubre lo relacional, lo vectorial y la caché, con los capítulos y las exportaciones como ficheros en disco en vez de blobs.

La organización del código también está decidida: **vertical slices en el backend**, una carpeta por fase de §2 con su router, sus modelos y su acceso a datos dentro, y **package by feature en el frontend**, sin adoptar FSD. Ver [docs/architecture.md](docs/architecture.md) §8.

Todo lo demás (el mecanismo de búsqueda dentro de SQLite, la cola de trabajos, la observabilidad, la exportación y el despliegue) está sin decidir — ver [docs/architecture.md](docs/architecture.md) §7. No introduzcas ninguna de esas dependencias por iniciativa propia: propón la decisión, y si se acepta, añádela a esa tabla en el mismo cambio.
