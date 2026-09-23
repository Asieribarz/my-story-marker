# AGENTS.md — my-story-marker

Generador de novelas de aventura personalizadas para regalo, por agentes: convierte la entrevista a un comprador en un manuscrito verificado.

## Alcance de esta rama (importante)

Esta rama es `project-v2`, un **orphan branch**: contiene `docs/`, `specs/`, las skills de `.claude/` y el backend en construcción según [specs/plan-backend-v1.md](specs/plan-backend-v1.md).

- Considera como fuente de verdad **únicamente lo que existe en esta rama**. Ignora `main` y cualquier historial, convención o código anterior: no aplica aquí.
- Si algo no está en `docs/` ni en esta rama, no existe todavía. No lo asumas: pregúntalo o propónlo explícitamente.
- Al crear la estructura del proyecto, parte de cero siguiendo `docs/architecture.md`, no de un esqueleto heredado.

## Documentación de referencia

Léela antes de proponer diseño o escribir código. Los documentos son consistentes entre sí y deben seguir siéndolo:

| Documento | Qué contiene |
|---|---|
| [docs/domain-knowledge.md](docs/domain-knowledge.md) | Árbol de conocimiento del dominio (9 dimensiones, la novena de personalización, + pipeline de decisión), en Mermaid. Los nodos hoja son claves del objeto de contexto. |
| [docs/definitions.md](docs/definitions.md) | Diccionario de cada nodo: definición, valores permitidos, parámetros y ejemplo de instancia YAML. Es la base del esquema de validación. |
| [docs/architecture.md](docs/architecture.md) | Capas, agentes, verificadores, ciclo de capítulo, modelo de datos, tecnología y fases de construcción. |
| [docs/validators.md](docs/validators.md) | Qué método de verificación sostiene cada afirmación sobre el sistema, pieza por pieza. |

Si un cambio de código altera la ontología, los valores permitidos o el flujo, actualiza el documento correspondiente en el mismo cambio.

Todo diagrama o grafo, en `docs/` o en cualquier otro sitio del repositorio, se escribe en formato Mermaid: no se usan imágenes, ASCII art ni ningún otro formato.

Todo dato de persona que se commitea —briefs de ejemplo y de evaluación, novelas generadas, revisiones humanas— es **ficticio**, y cada brief lo declara en su cabecera. Ninguna novela generada con datos de una persona real entra en el repositorio.

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

Lo decidido: **backend en Python con FastAPI**, servido con **`uvicorn`**, **frontend en React con Vite**, **orquestación con Claude Code** — la sesión pide al backend la siguiente orden y lanza el subagente que indica; cada agente de la novela es un subagente suyo, y la decisión de qué toca es código del backend, no de la sesión — **acceso de los agentes a la biblia por MCP**, con el paquete `fastmcp` montado dentro del FastAPI, en tres superficies — herramientas tipadas, `/mcp/lectura` en `.mcp.json`, `/mcp/escritura` declarada solo en la definición del Bibliotecario y `/mcp/entrada` —el texto no confiable, con identificador de un solo uso— solo en la del Extractor y el Intérprete — y **SQLite local** como base de datos, un fichero por proyecto que cubre lo relacional, lo vectorial y la caché, con los capítulos y las exportaciones como ficheros en disco en vez de blobs. El entorno es **`uv`** con **Python 3.12**; la ontología se valida con **Pydantic v2** como fuente única, y se prueba con **`pytest`** + **`Hypothesis`**, **`httpx`** para el `TestClient` de FastAPI, **`mypy --strict`** y **`ruff`**. La cola de trabajos es una **tabla en SQLite** con un worker que lanza **`claude -p`**. La verificación formal usa **Lean 4** (`lake` vía `elan`, sin Mathlib) para la cronología de cada novela y **TLA+ con TLC** (`tla2tools.jar`, Java) para el grafo de estados, este último solo en desarrollo. El tope de entrada se vigila con **`tiktoken`** (`o200k_base`) × 1,35 como estimador conservador, no como contador exacto: no es el tokenizador de Claude, y el porqué del factor está en [docs/architecture.md](docs/architecture.md) §6.3.

Los agentes son configuración de Claude Code: un fichero por agente en `.claude/agents/` con su modelo (`opus`, `sonnet` o `haiku`, según [docs/architecture.md](docs/architecture.md) §3), la skill `orquestar-novela` con el bucle de ejecución (pedir la orden, ejecutar, registrar), y los hooks de validación de capítulo y de policy en `.claude/settings.json`. La inspección visual de la lectura web usa **Playwright MCP**. Ver [docs/architecture.md](docs/architecture.md) §8.

La organización del código también está decidida: **vertical slices en el backend**, una carpeta por fase de §2 con su router, sus modelos y su acceso a datos dentro —más `proyecto/` y `mcp/`, que no son fases y están excepcionadas por escrito—, y **package by feature en el frontend**, sin adoptar FSD. Ver [docs/architecture.md](docs/architecture.md) §8.

Todo lo demás (el mecanismo de búsqueda dentro de SQLite, la observabilidad, la exportación a PDF y el despliegue) está sin decidir — ver [docs/architecture.md](docs/architecture.md) §7. No introduzcas ninguna de esas dependencias por iniciativa propia: propón la decisión, y si se acepta, añádela a esa tabla en el mismo cambio.

## Comprobaciones del backend

Todas miran solo `backend/`; ninguna toca `.claude/` ni `formal/`. Un cambio de código no se da por terminado sin las cuatro en verde:

```
uv run pytest            # incluye V-10 (dependencias contra architecture.md §7) y V-24 (rutas y conexiones desde shared/)
uv run mypy              # V-6, modo strict
uv run ruff check        # incluye V-9: TID251 prohíbe clientes de proveedor de modelos
uv run ruff format --check
```

V-15 ya no usa mutación: cada regla del validador y de los verificadores tiene una prueba que la dispara y otra de control que no (decisiones-backend R-5). El backend se arranca con `uv run uvicorn backend.app:app`. Las pruebas de cada rebanada viven en su carpeta `tests/`; `backend/tests/` guarda solo las comprobaciones que miran el backend entero.
