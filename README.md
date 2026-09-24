# my-story-marker

Generador de novelas de aventura personalizadas para regalo, escrito por agentes. Una entrevista al comprador se convierte en un contexto validado contra una ontología; a partir de él, doce subagentes de Claude Code planifican, escriben, verifican y publican una novela de diez capítulos que se lee en la web o en PDF. El backend (FastAPI + SQLite) decide cada paso; la sesión de Claude Code solo ejecuta la orden que recibe. La cronología de cada novela se comprueba con Lean 4 y el grafo de estados está especificado en TLA+.

## Documentación

Todo en [`docs/`](docs). Algunos documentos se están escribiendo en paralelo y puede que aún no existan.

| Documento | Qué contiene |
|---|---|
| [spec-inicial.md](docs/proceso/spec-inicial.md) | La especificación de partida |
| [trade-offs.md](docs/proceso/trade-offs.md) | Opciones, criterios y elección de cada decisión |
| [explainers.md](docs/proceso/explainers.md) | Un explainer por concepto |
| [diagramas.md](docs/proceso/diagramas.md) | Los diagramas del sistema, incluido el esquema SQLite |
| [claude-code.md](docs/proceso/claude-code.md) | Cómo usa el repositorio Claude Code: subagentes, skills, hooks, MCP, pruebas y memoria |
| [browser-mcp.md](docs/proceso/browser-mcp.md) | Uso de Playwright MCP para inspeccionar la lectura |
| [architecture.md](docs/architecture.md) | Capas, agentes, verificadores, ciclo de capítulo, modelo de datos, tecnología |
| [definitions.md](docs/definitions.md) | Diccionario de la ontología: claves, valores permitidos, ejemplos |
| [domain-knowledge.md](docs/domain-knowledge.md) | Árbol de conocimiento del dominio y pipeline de decisión |
| [validators.md](docs/validators.md) | Qué método de verificación sostiene cada afirmación |
| [evals.md](docs/evals.md) | Resultados de los briefs de evaluación |
| [iteraciones.md](docs/iteraciones.md) | Registro de iteraciones: qué falló y qué se cambió |
| [red-team.md](docs/red-team.md) | Ataques deliberados y su resultado |

Los planes de construcción están en [`specs/`](specs) (en particular [plan-agentes.md](specs/plan-agentes.md) y [plan-formal.md](specs/plan-formal.md)). Las instrucciones para agentes, en [AGENTS.md](AGENTS.md) y [CLAUDE.md](CLAUDE.md).

## Requisitos e instalación

| Pieza | Para qué | Cómo |
|---|---|---|
| [`uv`](https://docs.astral.sh/uv/) + Python 3.12 | Backend y harness de `.claude/` | `uv sync` en la raíz (instala también el grupo `dev`) |
| Node.js + npm | Frontend (React + Vite) | `npm install` en `frontend/` |
| Claude Code, con **suscripción** | Orquestación y subagentes | Sesión iniciada con la suscripción. **Nunca** `ANTHROPIC_API_KEY` en el entorno ni `--bare`: el worker quita esa variable y no usa `--bare` (`backend/cambio/worker.py`), porque `--bare` ignora los hooks y los agentes del repositorio |
| `elan` / Lean 4 | Gate de cronología de cada novela | Instalar `elan`; `formal/lean/lean-toolchain` fija `leanprover/lean4:v4.34.0`. El backend busca `lake` en el PATH o en `~/.elan/bin`. Primera compilación: `lake build` en `formal/lean/`. Sin Lean, la generación para con `error` · `lean_no_disponible` |
| Chromium de Playwright | PDF de la novela | `uv run playwright install chromium`. Sin él, `error` · `pdf_no_disponible` |
| Java 11+ y `tla2tools.jar` | TLC, **solo en desarrollo** | Ver [Correspondencia TLA+ ↔ código](#correspondencia-tla--código) |

Plugins de Claude Code usados en desarrollo: `mattpocock-skills` (skill `grilling`, obligatoria según AGENTS.md): `claude plugin install mattpocock-skills`.

**Carpeta de confianza.** En un clon nuevo, abre Claude Code una vez en el repo y acepta el diálogo de confianza. Sin eso, Claude Code no conecta los servidores MCP del frontmatter y el Extractor, el Intérprete y el Bibliotecario no arrancan (vale también para el `claude -p` del worker).

### `.env.example`

Cópialo a `.env` (que git ignora) y ajústalo si hace falta. Hoy solo trae `MSM_PROYECTOS`, la raíz de los proyectos generados (por defecto `proyectos/`, también ignorada). El repositorio no contiene ninguna clave ni la necesita: el modelo sale de la suscripción de Claude Code.

Otras variables que leen el harness y el backend, todas opcionales: `MSM_BACKEND` (URL del backend, por defecto `http://127.0.0.1:8000`; también la usa el proxy de Vite) y `MSM_WORKER` (`0` desactiva el worker de regeneración).

## Brief de ejemplo

[`evals/e1-reference/input/brief.json`](evals/e1-reference/input/brief.json) es el brief de referencia E1. Sus datos son **ficticios** y lo declara su `cabecera` (`"ficticio": true`). Tiene tres bloques:

- `entrada.respuestas`: lo único que va al backend. En `personalizacion`, un destinatario (nombre, nacimiento, rasgos), sin segundo destinatario; ocasión **cumpleaños**; relación **hijo**; público de **14 años**; seis hechos de tipos distintos (un ser querido, un recuerdo, un lugar, un objeto, una frase literal y un rasgo); vetos y dedicatoria. En `preferencias`, tono épico y subgénero de expedición con tesoro.
- `entrada.texto_libre_fichero`: la anécdota del comprador, en un `texto_libre*.txt` aparte que ninguna herramienta de fichero puede leer (hook de policy).
- `evaluacion`: el oráculo de la prueba; no se entrega a ningún agente.

Toda novela tiene **10 capítulos** (`NUMERO_DE_CAPITULOS` en `backend/proyecto/maquina.py`). Hay cinco briefs de evaluación (E1 a E5) en [`evals/`](evals); sus resultados, en [docs/evals.md](docs/evals.md).

## Cómo generar una novela

1. **Arranca el backend** en una terminal: `uv run uvicorn backend.app:app` (queda en `http://127.0.0.1:8000`). Sirve la API, las tres superficies MCP (`/mcp/lectura`, `/mcp/escritura`, `/mcp/entrada`) y el worker.
2. **Abre Claude Code en la raíz del repo** (carpeta de confianza aceptada).
3. **Entrevista**: `/entrevista` crea el proyecto, te pregunta las respuestas estructuradas y el texto libre por fichero, lanza al Extractor, te enseña los hechos para confirmarlos y para con el contexto validado (estado `planificacion`). Con un brief de evaluación: `/entrevista evals/e1-reference/input/brief.json`. Apunta el identificador del proyecto.
4. **Generación**: `/generar <proyecto>` sigue o reanuda. La sesión pide al backend la siguiente orden, lanza el subagente que indica y lee el acuse, hasta una parada: `esperar_humano`, `publicada`, `detenida` o `error` con causa. Reanudar es lo mismo que empezar, porque el estado vive en el backend. La skill explica cada parada y qué puede hacer la persona.
5. **Cambio del lector**: desde la web, el lector pide un cambio sobre una versión publicada (`POST /proyectos/{id}/cambios`). El backend encola un trabajo y su worker lanza `claude -p "/regenerar <proyecto> <trabajo>" --permission-prompts none --output-format json`. El Intérprete traduce la petición a un cambio sobre un hecho; el lector lo confirma, y se regeneran solo los capítulos afectados hasta publicar la versión siguiente. La versión anterior no se modifica.

El bucle es la skill `orquestar-novela`, y todo pasa por `.claude/harness/msm.py`. El detalle está en [docs/claude-code.md](docs/proceso/claude-code.md) y en [specs/plan-agentes.md](specs/plan-agentes.md).

## Cómo leer la novela

- **Web**: con el backend arrancado, en `frontend/`: `npm install` y `npm run dev`. Vite sirve en su puerto por defecto (5173) y hace de proxy de `/api` al backend (`MSM_BACKEND`, por defecto `http://127.0.0.1:8000`), así que no hace falta CORS. La lectura de un proyecto está en `#/<proyecto>`, con portada, capítulos, fichas y el botón de descarga del PDF.
- **PDF**: `GET /proyectos/{id}/versiones/{v}/pdf`. Lo imprime Playwright sobre la misma lectura HTML.
- **Ejemplo**: [`ejemplos/novela-ejemplo.pdf`](ejemplos/novela-ejemplo.pdf), la versión 1 de E1 (datos ficticios, 10 capítulos aprobados, 37 páginas con enlaces internos).

## Pruebas

Backend (miran solo `backend/`; un cambio no se da por terminado sin las cuatro en verde):

```
uv run pytest
uv run mypy
uv run ruff check
uv run ruff format --check
```

Harness de Claude Code (fuera de las cuatro anteriores):

```
uv run pytest .claude/tests
uv run ruff check --no-force-exclude .claude/harness/*.py .claude/tests/*.py
```

Frontend, en `frontend/`: `npm test` (`node --test`), `npm run build` y `npm run validar-lectura` sobre un `lectura.json`.

Lean, en `formal/lean/`:

```
lake build                              # la librería Cronologia
lake build Pruebas                      # casos que infringen cada invariante y casos de control
lake env lean ejemplos/novela.lean      # ejemplo que pasa; ejemplos/novela_falla.lean infringe una
```

Para la prueba de tamaño: `python scripts/generar_tamano.py <n>` (ver [plan-formal §3.4](specs/plan-formal.md#34-pruebas-y-prueba-de-tamaño)).

TLC: ver la sección siguiente.

## Correspondencia TLA+ ↔ código

[`formal/tla/GrafoNovela.tla`](formal/tla/GrafoNovela.tla) especifica el grafo de estados de un proyecto: la función de siguiente orden, la tabla de transiciones, el bloqueo con dos ejecutores (sesión y worker), las caídas con reanudación, el canje del identificador de un solo uso y las escrituras del Bibliotecario. Comprueba seis invariantes y la liveness de [architecture.md](docs/architecture.md) §3.4 (tabla en [plan-formal §2.3](specs/plan-formal.md#23-las-invariantes-y-la-liveness)).

La tabla adapta [plan-formal §2.4](specs/plan-formal.md#24-correspondencia-con-el-código). Rutas relativas a `backend/proyecto/` salvo que se diga otra cosa. Cada función citada se ha comprobado en el código. Varias filas que plan-formal §2.4 aún marca **pendiente** ya tienen código (AJ-1 a AJ-6, cerrados en los bloques 2 y 3 del backend); la alineación rama a rama con la especificación la tiene pendiente la sesión formal ([plan-multisesion.md](specs/plan-multisesion.md), «Sesión formal»).

| Acción o definición de la especificación | Estado o transición del código |
|---|---|
| `Aristas` | `transiciones.TRANSICIONES`: la tabla de aristas (origen, destino, causa) |
| `DetenPorTope`, `FallidasPorTope` | `transiciones._DETENIBLES_POR_TOPE`, `_FALLIDAS_POR_TOPE` |
| `DestinoDeReintentar` | `transiciones.DESTINO_DE_REINTENTAR` |
| `ParadasHumanas`, `OrigenesDeDetenida` | `transiciones.PARADAS_HUMANAS`, `ORIGENES_DE_DETENIDA` |
| `Transitar` | `maquina._transitar`, que pasa siempre por `transiciones.arista()`; al entrar en `verificacion_manuscrito` suma una pasada y deja los gates sin evaluar (AJ-3) |
| `Deshacer` | `cambio/efectos.deshacer` y `restaurar_punteros`: un cambio fallido restaura la versión N (AJ-6) |
| `FueraDelBucle`, `EnCurso` | `maquina.CapituloInstantanea.fuera_del_bucle`, `maquina._capitulo_en_curso` |
| `DestinoDeFracaso` | `maquina._destino_de_fracaso` |
| `Derivar`, `Derivaciones` | `maquina._derivar`, `_derivaciones`, `resolver` |
| `Decision` | `maquina.siguiente_orden` |
| `EnBucle` | `maquina._en_bucle` |
| `EnRevision` | `maquina._en_revision`: por capítulo, Revisor y luego Bibliotecario (AJ-2); sin capítulos, `error` · `revision_sin_capitulos` |
| `Emitir` | `persistencia._emitir`; al emitir la orden del Bibliotecario se borra lo escrito para su capítulo (`capitulo/biblia.borrar_lo_escrito`, desde `manejadores._entrada_del_bibliotecario`, B-16) |
| `GatesPorEvaluar`, `EvaluarGates` | `verificacion/gates.gates_pendientes`, `preparar_gates`, `ejecutar_gates` (cobertura y Lean por pasada, TC-4), llamados al preparar la orden del juez de manuscrito (`manejadores._entrada_del_juez_de_manuscrito`); `persistencia._gates` los lee |
| `Resellar` | `sello.volver_a_sellar`, llamado por `bloqueo.tomar_bloqueo` (AJ-4) |
| `FalloDePaso` | `maquina._desenlace_de_paso`, rama de fallo |
| `Gates` | `maquina._gates` |
| `Publicar` | `maquina._desenlace_de_paso` con el Exportador; `exportacion/publicar.publicar` escribe la versión |
| `DesenlacePaso` | `maquina._desenlace_de_paso` |
| `DesenlaceCapitulo` | `maquina._desenlace_de_capitulo` (un fallo de contenido gasta intento del capítulo; uno de forma repite el agente) |
| `DesenlaceRevision` | `maquina._desenlace_de_paso` con `_marcar_revision` |
| `Manejar` | manejador del Bibliotecario, `capitulo/manejadores._bibliotecario` |
| `AplicarDesenlace` | `maquina.aplicar_desenlace` |
| `Reabrir` | `maquina._reabrir` |
| `Humana` | `maquina.aplicar_accion_humana`; confirmar un cambio reabre los capítulos afectados en `cambio/consultas.decidir_cambio` y `_reabrir` |
| `Tomar` | `bloqueo.tomar_bloqueo` |
| `Pedir` | `persistencia.emitir_siguiente_orden` y el lanzamiento del subagente por la skill `orquestar-novela` |
| `Canjear` | `intake/entrada.canjear`, detrás de la herramienta `leer_entrada` de `mcp/entrada.py` |
| `EscribirBiblia` | herramientas de `mcp/escritura.py`, que comprueban el sello con `sello.orden_de_sello` dentro de la transacción |
| `Terminar` | el subagente devuelve su salida (fuera del backend) |
| `Registrar` | `persistencia.registrar_resultado`, que localiza la orden con `sello.fila_de_sello` y rechaza un sello viejo |
| `Soltar` | `bloqueo.soltar_bloqueo` |
| `Caer` | la sesión muere; se prueba en `tests/test_reanudacion.py` |
| `CaducarTrasCaida`, `CaducarEnVida` | `bloqueo.DURACION` (30 min) y `bloqueo.exigir_bloqueo` |
| `Decidir` | `persistencia.decidir` y `_caducar` |
| `SubirBrief`, `ConfirmarHechos` | `intake/persistencia.guardar_brief`, `confirmar_hechos` |
| `AprobarPlan` … `Reintentar` | rutas de `router.py` (`/plan/aprobacion`, `/aprobacion-final`, `/reintentar`), `persistencia.decidir_parada` y `persistencia.reintentar` |
| `TypeOK`, `Coherencia`, `Inv4_Topes` | `maquina.incoherencias()` y los `CHECK` de `shared/esquema.sql` |

Lo que queda fuera del modelo (la cola y el worker, `error` con causa, la renovación del bloqueo y el contenido) está en [plan-formal §1](specs/plan-formal.md#1-qué-se-especifica-y-qué-no).

### Configuraciones y cómo ejecutar TLC

Hay tres en `formal/tla/`:

| Fichero | Qué es | Resultado esperado |
|---|---|---|
| `GrafoNovela.cfg` | Modelo de entrega: 5 capítulos, 2 intentos, 2 ciclos, 1 cambio del lector, dos ejecutores, caídas | Pasa |
| `GrafoNovelaRapido.cfg` | El de entrega con 2 capítulos, para iterar | Pasa |
| `GrafoNovelaAnterior.cfg` | El diseño previo a AJ-3 y AJ-4 (`SelloConGeneracion = FALSE`, `GatesPorPasada = FALSE`) | **Tiene que fallar**: si pasa, el modelo ha dejado de ver el fallo |

Con Java 11+ y `tla2tools.jar` (plan-formal §2.5), desde `formal/tla/`:

```
java -cp <ruta>/tla2tools.jar tla2sany.SANY GrafoNovela.tla
java -XX:+UseParallelGC -Xmx8g -cp <ruta>/tla2tools.jar tlc2.TLC -config GrafoNovelaRapido.cfg -workers auto -deadlock -metadir <carpeta temporal> GrafoNovela.tla
```

`-deadlock` desactiva la comprobación de bloqueo mutuo, porque `publicada` y `detenida` son estados finales legítimos; la liveness detecta un estado que se queda parado sin serlo. `-metadir` saca del repositorio el directorio de estados. Los contraejemplos y hallazgos se recogen en [plan-formal §5](specs/plan-formal.md#5-contraejemplos-y-hallazgos).

## Observabilidad (Langfuse)

El backend envía cada proyecto a Langfuse Cloud, **solo metadatos**: agentes, modelos, tokens, tiempos, desenlaces, severidades y puntuaciones, nunca texto de la novela ni del comprador. La sesión es el proyecto; hay una traza por generación y otra por cada cambio del lector, un span por capítulo, una observación por agente con el nombre de su rol (`entrevistador:`, `planner:`, `writer:`, `editor:`…) y una `tool:` por llamada MCP. Los validadores van como scores (`esquema_salida`, `validador:*`, `gate:cobertura`, `gate:lean`, `juez:*`, `humano:*`) y las definiciones de `.claude/agents/` como versiones de prompt. Detalle en [architecture.md §7](docs/architecture.md).

1. Copia `.env.example` a `.env` y rellena `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` y, si no es la región por defecto, `LANGFUSE_BASE_URL`. `.env` no se commitea.
2. Con el backend arrancado, cada resultado de un agente se envía solo, en segundo plano.
3. Para enviar lo que ya existía, o tras la revisión humana:

   ```
   uv run python -m backend.observabilidad --todos      # o <proyecto>, o --prompts
   ```

Sin claves no se envía nada, y las pruebas lo apagan siempre (`MSM_LANGFUSE=0`). El coste lo calcula Langfuse a partir del modelo y los tokens: con suscripción es una estimación, no un cargo.

**MCP de Langfuse** (opcional, sesión de desarrollo): `.mcp.json` lo declara para versionar prompts y consultar métricas y scores. Necesita en el entorno de Claude Code `LANGFUSE_MCP_AUTH`, el base64 de `clave_publica:clave_secreta`. Ese MCP no escribe trazas.

## Estructura del repositorio

| Carpeta | Qué contiene |
|---|---|
| `.claude/` | Configuración de Claude Code: los 12 agentes de la novela, las skills, los hooks (`settings.json`), el harness en Python (`harness/`) y sus pruebas (`tests/`) |
| `backend/` | FastAPI en vertical slices, una carpeta por fase del pipeline más `proyecto/`, `mcp/`, `observabilidad/` (envío a Langfuse) y `shared/` |
| `docs/` | Documentación del sistema (ver arriba) |
| `ejemplos/` | La novela de ejemplo en PDF |
| `evals/` | Los cinco briefs de evaluación, uno por carpeta con `input/` y `results/`, y `comprobar.py` |
| `formal/` | Verificación formal: `tla/` (grafo de estados) y `lean/` (proyecto Lake de la cronología) |
| `frontend/` | React + Vite: lectura de la novela, cambio del lector y demás vistas web |
| `images/` | Recursos gráficos |
| `specs/` | Planes y decisiones de construcción (backend, agentes, formal, frontend, entrega) |
| `proyectos/` | Proyectos generados, uno por carpeta con su SQLite, en `novelas/` o en `evals/` (las ejecuciones de los briefs de evaluación). Git la ignora: ninguna novela generada se commitea |

`.mcp.json` declara los servidores MCP de la sesión (lectura de la biblia y Playwright), y `dif-local-vm.md` registra las diferencias de la máquina de desarrollo.
