# contexto-tras-bloque1.md — Dónde está el proyecto y qué queda

> **Para:** una sesión nueva de Claude Code que retoma el proyecto, sobre todo si es en otra máquina.
> **Estado a:** 2026-09-23, 18:00. Rama `project-v2-avance`. El último commit es `e735f3b`, que tiene el bloque 1 completo. **Encima hay trabajo del bloque 2 sin commitear y a medias**: ver §3 y §5.1.
> **Entrega:** 2026-09-24, hacia las 13:00.

---

## 1. Reglas para trabajar aquí

- `AGENTS.md` y `CLAUDE.md` se cargan solos y mandan. No hagas commit ni push si la persona no lo pide.
- **[spec-backend-2.md](spec-backend-2.md) manda sobre `docs/`** hasta que el código aplique sus decisiones. Lo que hay en él:
  - §0: recortes;
  - §1: B-n;
  - §2: TC-n;
  - §2.1: ajustes al cerebro (AJ-n);
  - §3: contradicciones resueltas;
  - §4: contratos con las otras sesiones;
  - §4.4: documentos pendientes;
  - §4.5: avisos pendientes.
- **Decisiones del backend: sin ronda de preguntas.** La persona pidió que se tomen con tu recomendación. Di qué has decidido y apúntalo en `spec-backend-2.md`. Sí pregunta por lo que queda fuera del backend: commits, instalaciones y cambios que afecten a otras sesiones o a la ontología.
- **Presupuesto.** Todo el uso de modelo sale de la suscripción: nunca `ANTHROPIC_API_KEY`, ni un SDK de proveedor, ni `claude -p --bare`. La cuota por horas se agota: usa workflows con pocos agentes y un solo revisor, y no releas documentos largos si no hace falta.
- Mapa visual del proyecto, para la persona: https://claude.ai/artifact/P81cJNz85ToNgJHymsE9ed

## 2. Qué es

Un generador de novelas de aventura personalizadas para regalo. Parte de la entrevista a un comprador y produce 10 capítulos (de 1.000 a 1.500 palabras) que se leen en la web y en PDF, con versiones y cambios pedidos por el lector.

- **El backend (Python) decide:** el estado, la siguiente orden, lo que tiene que leer cada agente y las comprobaciones. Nunca llama a un modelo.
- **Claude Code ejecuta:** la skill `orquestar-novela` lanza los 12 subagentes de `.claude/agents/`. Se arranca con `/generar` o, sin nadie delante, con `claude -p` desde el worker.

## 3. Estado por pieza

| Pieza | Estado | Dónde |
|---|---|---|
| Backend · pasos 0 a 2 | Hecho (`d821a0d`) | `backend/shared`, `contexto`, `intake` |
| Backend · bloque 1: paso 3 y `/mcp/entrada` | Hecho y verificado (`e735f3b`): unas 510 pruebas, mypy, ruff y formato en verde | `backend/proyecto`, `backend/mcp`, `backend/app.py` |
| Backend · bloque 2 · **base** | **Hecha, sin commitear.** El esquema de la biblia con historia por capítulo, 12 agentes, `excluye` (B-18), rutas nuevas, `capitulo/biblia.py`, `planificacion/consultas.py`, `escaleta/consultas.py`, `planificacion/materializar.py` y el tipo `Manejador` | Anexo al final |
| Backend · bloque 2 · **cerebro** | **A medias, sin commitear.** Parado a las 17:50 con unas 40 acciones hechas | `backend/proyecto/` |
| Backend · bloque 2 · **planificación y escaleta** | **A medias, sin commitear.** Parado a las 17:50 con unas 35 acciones hechas | `backend/planificacion/`, `backend/escaleta/` |
| Backend · bloque 2 · Recuperador, verificadores y MCP | Sin empezar | §5.1 |
| Backend · bloque 3: pasos 8a a 10 | Decidido, sin empezar | §5.2 |
| Agentes: `.claude/` y `.mcp.json` | Los 12 agentes, el harness y 78 pruebas. Tiene una fuga de seguridad sin arreglar | [plan-multisesion.md](plan-multisesion.md), sección de agentes |
| Frontend: lectura | Hecha contra un fixture, con 43 pruebas | `frontend/`, [plan-frontend.md](plan-frontend.md) |
| Frontend: cambio | Diseñado; espera a las rutas del paso 9a | plan-frontend §7 |
| Briefs de evaluación | Los cinco hechos. E3 necesita `excluye`, que ya existe con la base: repásalo con `comprobar.py` | `evals/` |
| TLA+ y Lean | Escritos, con arreglos pendientes | `formal/`, [plan-formal.md](plan-formal.md) |
| Novela E1, PDF de ejemplo, evaluaciones y revisión humana | 0 % | — |

**Comprobaciones a las 18:00, con el trabajo a medias:**
- `pytest`: **3 pruebas fallan**, todas del cerebro:
  - `test_api.py::test_de_intake_a_planificacion_con_texto_libre_y_hechos`;
  - `test_api.py::test_la_aplicacion_publica_las_rutas_de_cada_rebanada`;
  - `test_persistencia.py::test_un_agente_sin_esquema_no_gasta_intento_ni_cierra_la_orden`.
- `mypy`: en verde, 80 ficheros.
- `ruff check`: **4 errores**.
- `ruff format --check`: **2 ficheros** sin formatear.

## 4. Lo que ya hay en el backend (hasta el bloque 1)

**Cómo se usa:**
- Arrancar: `uv run uvicorn backend.app:app` (http://127.0.0.1:8000).
- Comprobaciones: `uv run pytest` (unos 95 s), `uv run mypy`, `uv run ruff check` y `uv run ruff format --check`.
- Otras baterías: `uv run pytest .claude/tests`, `uv run python -m evals.comprobar`, y `npm test` dentro de `frontend/`.

**Rutas:**
- Proyecto: `POST /proyectos` · `GET /proyectos/{id}/estado` · `POST /proyectos/{id}/siguiente` · `POST /proyectos/{id}/resultado` · `POST` y `DELETE /proyectos/{id}/bloqueo` · `POST /proyectos/{id}/reintentar` · `DELETE /proyectos/{id}`.
- Entrevista y contexto: `POST /proyectos/{id}/brief` · `GET /proyectos/{id}/hechos` · `POST /proyectos/{id}/hechos/confirmacion` · `POST /proyectos/{id}/contexto/validar`.
- MCP: `/mcp/entrada/` con una herramienta, `leer_entrada(identificador)`.

**Contratos vigentes:**
- El bloqueo lleva la cabecera `X-Bloqueo` y caduca a los 30 minutos.
- Solo puede haber una orden vigente en la tabla `orden`.
- Errores: `{codigo, requisito, detalle}`.
- El identificador de entrada tiene la forma `<proyecto>.<secreto>`, se guarda como SHA-256 y sirve una sola vez.
- `/resultado` acepta todavía `{orden, resultado}`. El cambio a `{orden: sello, salida_cruda, metadatos}` es de la pieza del cerebro.

## 5. Lo que queda del backend

### 5.1 Bloque 2 · pasos 4 a 8

**Los prompts y los contratos entre piezas están en [workflow-bloque-2.js](workflow-bloque-2.js).** Es el guion del workflow que se paró:
- la constante `CONTRATOS` fija las firmas que comparten las piezas;
- la constante `REGLAS`, las condiciones de trabajo;
- `piezas()`, el encargo de cada pieza;
- las tres fases finales son la revisión, la corrección y los documentos.

Para reutilizarlo:
1. Cambia la constante `REPO` a la ruta de la máquina nueva.
2. Quita la fase «Base», que ya está hecha, y pasa a cada pieza el anexo de este fichero en lugar del informe de la base.
3. En las piezas del cerebro y de la planificación, añade: «continúa lo que hay a medias en tus carpetas».

| Pieza | Estado | Requisitos | Decisiones |
|---|---|---|---|
| Base | ✅ | Esquema, acceso y contratos | Anexo |
| **Cerebro** | 🟡 A medias | AJ-1 a AJ-5, el `/resultado` final (§4.1, puntos 1, 2, 3, 7 y 8), `sello` en `/siguiente`, `/auditoria` (§4.1.9), `llamada_mcp` de entrada (§4.1.10), `proyecto/sello.py`, agregar los MANEJADORES, llamar a `materializar_contexto`, `rutas_prompt` con `preparar_prompt`, `/plan/aprobacion` y `/aprobacion-final`, y la revisión capítulo a capítulo (AJ-2) | §2.1, §4.1 |
| **Planificación y escaleta** | 🟡 A medias | RF-30 a 36 y RF-40 a 43: modelos de salida, MANEJADORES, `GET /plan` y `GET /escaleta`; V-21 | B-1, B-3 a B-5, B-9, B-16 |
| Recuperador | ⬜ | RF-50 a 59b: estimador, estructurada, similitud vacía, `ensamblado.preparar_prompt` en partes de 20.000 tokens como mucho; V-3a, V-4, V-5 y V-23 | B-8, §4.1.4, D-9 |
| Verificadores | ⬜ | RF-60 a 62, 70 a 73a, 76 a 79, 72a y 77a: segmentación, longitud, INFLESZ, lista negra, guardarraíl con sus listas, grafía, frases literales, modelos de salida y MANEJADORES de `capitulo/`; V-7, V-15 por regla, V-26, V-28 y V-35 | B-11, B-12, B-14, B-15, R-2, R-3 |
| MCP | ⬜ | RF-100 a 106: `/mcp/lectura` y `/mcp/escritura` con el sello, RF-106 y `llamada_mcp`, montadas en `app.py`; V-19 y V-13 (lado del backend) | §4.1.6, AJ-4, B-16, B-17 |
| Revisión, corrección y documentos | ⬜ | La batería completa, integración y la pasada de §4.4 de spec-backend-2 | — |

**Orden recomendado:**
1. Terminar el cerebro y la planificación, y dejar la batería en verde.
2. Lanzar el Recuperador, los verificadores y el MCP en paralelo: las tres usan `biblia.py` y no se pisan.
3. Un revisor, un corrector y una pasada breve de documentos.

El workflow admite a la vez tantos agentes como núcleos menos 2: en una máquina de 4 núcleos, solo 2.

### 5.2 Bloque 3 · pasos 8a a 10

| Paso | Requisitos | Decisiones |
|---|---|---|
| 8a · gates | RF-110 a 115 | TC-1 a TC-5; §4.2 (Lean: `decide +kernel`, UTF-8 sin BOM, `\n`); AJ-3 (`verificacion/pasada-k/`) |
| 9 · publicación | RF-90 a 98 | TC-6: `playwright` y `pypdf` son dependencias nuevas; se anotan en architecture §7 y AGENTS.md, y hay que descargar Chromium. TC-7 y §4.3: `lectura.json` según plan-frontend §5 |
| 9a · cambios y worker | RF-120 a 125 | TC-8; R-4 (una sola ejecución y la arista `regeneracion → publicada`); TC-10 (un `claude` falso en las pruebas); AJ-6 |
| 10 · API | Rutas y errores | TC-11 y TC-12 |

**Verificación del bloque 3:** V-27, V-28 (cobertura), V-29, V-30, V-31 y V-32 (suma ≥ 18).

**Fuera de la v1 o recortado:** RF-12 (lo cubre `/entrevista`), V-3b, E-5 y Langfuse. Langfuse está pendiente de la persona: se recorta si el enunciado no lo exige.

### 5.3 Documentos y avisos

- Pasada breve con **todo lo de §4.4 de spec-backend-2**, mejor al cerrar el bloque 2.
- Los **avisos de §4.5**, a medida que llegue cada cosa.

## 6. Cómo construir rápido

Lecciones medidas en los bloques 1 y 2:

- **El tiempo es volumen.** El 70 al 90 % se va en que el modelo escribe código y pruebas. Escribe pruebas solo para los V-n, más un caso de control por regla.
- **Primero el esquema y los contratos, después piezas en paralelo** en carpetas que no se pisan. Eso es lo que se hizo en el bloque 2.
- **Un solo revisor más el corrector.** Salta el agente de documentos y haz la pasada tú, al final.
- **Mientras se trabaja, solo las pruebas de la rebanada.** La batería completa tarda unos 95 s; va al final.
- **Windows:** escribe con `newline="\n"`, ejecuta Python con `-X utf8` si una salida lleva acentos, y usa `Path`.

## 7. Puesta en marcha en otra máquina

1. Clona o copia el repositorio con el trabajo sin commitear (hay que commitear antes de llevarlo, ver §8). Después, `uv sync` en la raíz y `npm install` en `frontend/`.
2. **Abre Claude Code una vez en el repositorio y acepta el diálogo de confianza.** Sin eso, los servidores MCP del frontmatter de los agentes no se conectan (plan-agentes, S-2).
3. Herramientas que hay que volver a instalar en la máquina nueva:
   - Lean 4 con `elan`: el `formal/lean/lean-toolchain` fija la versión;
   - Java 21, JRE a nivel de usuario vale;
   - `tla2tools.jar`, fuera del repositorio;
   - más adelante, Chromium para Playwright (TC-6).

   En la máquina de hoy estaban en `~/.elan`, `C:\Users\student\herramientas\jre\…\java.exe` y `C:\Users\student\tools\tla\tla2tools.jar`.
4. Comprueba el punto de partida con las cuatro comprobaciones (§4) y compáralo con el estado de §3.

## 8. Lo que decide o hace la persona

- **Commitear** el trabajo del bloque 2 a medias antes de llevar el repositorio a la otra máquina, y el push si hace falta.
- Si el enunciado exige Langfuse.
- Limpiar las reglas `allow` de `.claude/settings.json` que dejaron otras sesiones con sus rutas.
- Reabrir la sesión de agentes para la fuga de la policy ([plan-multisesion.md](plan-multisesion.md)).
- Mañana: la revisión humana de E1 con la rúbrica, y la presentación con su vídeo.

## 9. Otras sesiones

Cada una tiene su lista en [plan-multisesion.md](plan-multisesion.md). Al reabrir una, dile: «lee specs/plan-multisesion.md, tu sección, y specs/spec-backend-2.md».

- **Agentes (`.claude/`), lo urgente:**
  - la policy deja que Grep lea `brief/` y `cambios/` si se le da como ruta la carpeta del proyecto;
  - las rutas con `..` no se normalizan;
  - la policy falla abierta si la auditoría lanza una excepción;
  - los prompts contradicen R-2 sobre `mencionados`.
  - Además: el Escritor tiene que leer su prompt en partes (§4.1.4), el Agente de contexto tiene que conocer `excluye` (B-18) y el contrato final se activa con `MSM_CONTRATO_RESULTADO=salida_cruda` cuando el cerebro lo tenga.
- **Formal:** dos invariantes que nunca pueden fallar, y los ejemplos de Lean usan `by decide` en lugar de `+kernel`.
- **Briefs:** cuatro ajustes en las señales de E2 y E3.
- **Frontend:** tres detalles menores, y está esperando las rutas.

## 10. Plan hasta la entrega

1. **Terminar el bloque 2** (§5.1): el cerebro y la planificación primero; después, el Recuperador, los verificadores y el MCP en paralelo; al final, la revisión, la corrección y los documentos.
2. **Bloque 3, en versión ligera** (§5.2).
3. **Paso S:** dos capítulos con agentes reales (plan-backend-v1, paso S). Arreglar lo que salga.
4. **Novela E1 completa** y el PDF de ejemplo.
5. **Evaluaciones:** E1 entera; E2 y E5 hasta su validador; E3 y E4 hasta sus comprobaciones. Tabla en `docs/evals.md`, un ajuste de prompts (v1 → v2) y la revisión humana de E1.
6. **Documentación final y README;** la presentación, que es de la persona.

---

## Anexo · lo que dejó la base del bloque 2

Informe literal del agente de la base (2026-09-23, 17:42). Las piezas que faltan se construyen sobre esto.

**Resumen.** La base del bloque 2 está construida y todas las comprobaciones que me tocaban están en verde. El esquema está cambiado: la biblia guarda historia por capítulo, con el capítulo 0 como estado inicial (B-2), y ganan columnas o tablas B-3, B-4, B-5, B-6, B-10, B-16 y B-17, AJ-3, AJ-4, §4.1.5 y §4.1.8, el informe único por versión y verificador, el índice con coalesce y gate_resultado. El enum Agente tiene 12 agentes. Hecho también: B-18 en la ontología con dos reglas nuevas, las rutas nuevas y el tipo Manejador con la agregación por rebanadas. Nuevos: capitulo/biblia.py (lecturas «a fecha N−1», las dos comprobaciones de B-9, las escrituras del Bibliotecario con la guarda de V-19 y el borrado de B-16, y las lecturas para MCP), planificacion/{modelos,consultas,materializar}.py, escaleta/{modelos,consultas}.py, los MANEJADORES vacíos de planificacion, escaleta y capitulo, y datos de referencia ficticios para las pruebas (biblia, plan y escaleta). Para que proyecto/ siguiera importando tras cambiar el enum, apliqué en maquina.py y persistencia.py solo el cambio de nombre de AJ-1; AJ-2 a AJ-5 quedan para el cerebro. Pruebas que pasan: shared, contexto, planificacion, escaleta y capitulo; proyecto, intake y mcp tras el cambio del enum; .claude/tests/test_definiciones.py; y mypy, ruff check y ruff format --check. `evals.comprobar` ya da ok para E3. No he ejecutado la batería completa: queda para el revisor.

**Ficheros.** `C:\Users\student\Documents\GitHub\my-story-marker\backend\shared\esquema.sql`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\shared\tipos.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\shared\rutas.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\shared\tests\test_db.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\shared\tests\test_rutas.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\contexto\modelos.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\contexto\validacion.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\contexto\tests\test_validacion.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\proyecto\manejadores.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\proyecto\maquina.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\proyecto\persistencia.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\proyecto\tests\generadores.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\proyecto\tests\test_api.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\proyecto\tests\test_maquina.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\proyecto\tests\test_persistencia.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\capitulo\biblia.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\capitulo\manejadores.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\capitulo\tests\referencia.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\capitulo\tests\test_biblia.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\planificacion\__init__.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\planificacion\modelos.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\planificacion\consultas.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\planificacion\materializar.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\planificacion\manejadores.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\planificacion\tests\referencia.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\planificacion\tests\test_materializar.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\escaleta\__init__.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\escaleta\modelos.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\escaleta\consultas.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\escaleta\manejadores.py`, `C:\Users\student\Documents\GitHub\my-story-marker\backend\escaleta\tests\referencia.py`

### Interfaz

== ESQUEMA (shared/esquema.sql; todas STRICT; listas CHECK = enums de shared/tipos.py, comprobado en shared/tests/test_db.py) ==
- proyecto: + pasadas INTEGER NOT NULL DEFAULT 0 CHECK ≥0 (AJ-3). + generacion_bloqueo INTEGER NOT NULL DEFAULT 0 CHECK ≥0 (AJ-4).
- orden: el CHECK de agente tiene los 12. + sello TEXT UNIQUE (admite NULL; lo rellena y lo vuelve a sellar el cerebro). + metadatos TEXT (json_valid o NULL, §4.1.8).
- personaje(id TEXT PK, nombre TEXT NULL hasta planificar salvo los destinatarios, alias TEXT array JSON DEFAULT '[]', descripcion TEXT NULL, origen, fuente, ficha TEXT JSON, arco, evolucion JSON NULL, fecha_nacimiento TEXT NULL). Se quitan estado_actual y sabe.
- personaje_estado(personaje FK, capitulo INTEGER 0..10, estado TEXT; PK (personaje, capitulo)).
- personaje_sabe(personaje FK, capitulo 0..10, dato TEXT; PK (personaje, capitulo, dato)). Acumulativo.
- localizacion(id, nivel, padre, nombre TEXT NULL, descripcion TEXT NULL, hito TEXT NULL CHECK Hito). Se quita estado.
- localizacion_estado(localizacion FK, capitulo 0..10, estado; PK (localizacion, capitulo)).
- objeto(id TEXT PK, nombre TEXT NOT NULL, alias TEXT array JSON).
- inventario(objeto FK objeto, poseedor FK personaje NULL, capitulo 0..10; PK (objeto, capitulo)).
- ficha_capitulo(numero PK 1..10, objetivo TEXT, escenas JSON, pov NOT NULL FK, localizacion NOT NULL FK, dia INTEGER ≥1, tension, palabras_objetivo, cierre, plantar JSON [{clave, descripcion}], cobrar JSON [clave], traspasos JSON [{objeto, a}]). Se quita hito.
- ficha_capitulo_hito(capitulo FK, hito CHECK Hito; PK (capitulo, hito); UNIQUE (hito)).
- ficha_capitulo_personaje: + papel TEXT NOT NULL CHECK PapelEnFicha ('presente', 'mencionado').
- capitulo_version: + ruta_borrador TEXT NULL (salida del Escritor), + dia_fin INTEGER NULL ≥1, + localizacion_fin TEXT NULL FK. ruta sigue siendo el texto vigente, el que reescribe el Editor.
- informe, rehecha: (id, capitulo_version NOT NULL FK, verificador TEXT, severidad NULL = la mayor, hallazgos TEXT con array JSON de Hallazgo, metricas JSON NULL, momento; UNIQUE (capitulo_version, verificador)). Sin ambito: los resultados de manuscrito van a gate_resultado.
- evento: momento TEXT NULL (recuerdo), dia INTEGER NULL ≥1 (historia), franja TEXT NULL CHECK Franja. CHECK: va exactamente uno de momento o dia, y franja solo con dia. capitulo NULL es un evento del contexto y cuenta como capítulo 0.
- presagio(id, clave TEXT UNIQUE, descripcion, plantar_en 1..10 NULL, cobrar_en 1..10 NULL, abierto_en 1..10 NULL; CHECK: va exactamente uno de plantar_en o abierto_en).
- presagio_estado(presagio FK, capitulo 0..10, estado CHECK EstadoPresagio; PK (presagio, capitulo)).
- glosario(id, termino, categoria CHECK CategoriaTermino, referencia TEXT NULL si y solo si la categoría es 'otro', tipo CHECK TipoTermino, capitulo 0..10, nota; UNIQUE (termino, capitulo)).
- resumen(id, ambito 'capitulo'|'acto', numero = capítulo, o acto 1..3, capitulo 1..10 y version ≥1 = la versión cuyo Bibliotecario lo escribió, texto, creado; UNIQUE (ambito, numero, capitulo, version)).
- palabra_prohibida: sin UNIQUE en la tabla; índice único palabra_prohibida_unica ON (termino, nivel, coalesce(publico, '')).
- gate_resultado(pasada INTEGER ≥1, gate CHECK Gate, ok 0/1, detalle JSON; PK (pasada, gate)).

== TIPOS ==
- shared/tipos.py: Agente con 12 (AGENTE_CONTEXTO, EXTRACTOR_HECHOS, PLANIFICADOR, ESCALETISTA, ESCRITOR, EDITOR_ESTILO, JUEZ_CAPITULO, BIBLIOTECARIO, JUEZ_MANUSCRITO, REVISOR, EXPORTADOR, INTERPRETE_CAMBIOS).
- Enums nuevos: Hito(detonante, primer_umbral, punto_medio, crisis, climax), PapelEnFicha(presente, mencionado), EstadoPresagio(previsto, plantado, cobrado), CategoriaTermino(personaje, localizacion, objeto, otro), TipoTermino(canonico, alias), Franja(manana, tarde, noche), Gate(cobertura, lean, juez).
- Informe.metricas: dict[str, float] | None = None.
- contexto/modelos.py: TipoExclusion(muerte, partida); Exclusion{fuente: str, tipo}; Hecho.excluye: Exclusion | None = None; es_momento(str) -> bool (fecha parcial o periodo).
- contexto/validacion.py, reglas nuevas: exclusion_en_evento (solo un evento excluye) y exclusion_con_fuente (la fuente es la de un personaje real de la novela).

== RUTAS (DisposicionProyecto) ==
- borrador(n, v, i) → capitulos/cap-NN/vV-intentoI.borrador.md
- prompt_parte(n, v, i, parte≥1) → prompts/cap-NN/vV-intentoI.prompt.parte-P.md
- verificacion (propiedad) → verificacion/
- pasada(k≥1) → verificacion/pasada-k
- crear_directorios() crea también verificacion/. Fuera de rango: ValueError.

== proyecto/manejadores.py ==
- Manejador = Callable[[ContextoManejo, object], Salida].
  - ContextoManejo(proyecto, orden: OrdenEmitida, ahora), con .conexion y .momento.
  - Salida(desenlace: maquina.Desenlace, detalle: dict = {}).
  - El 2.º argumento es la salida ya extraída por el cerebro: el Markdown en str, sin la línea del sello, para escritor, editor-estilo y revisor; el valor del bloque JSON para el resto.
  - Si la salida no encaja, el manejador devuelve Desenlace.forma() (Desenlace.contenido() si es el escritor) con los errores en detalle. No lanza y no persiste.
- Cada rebanada expone <rebanada>/manejadores.py con MANEJADORES: Mapping[Agente, Manejador]. Ya existen vacíos en planificacion, escaleta y capitulo.
- manejador_de(agente) busca primero en proyecto.manejadores.MANEJADORES (extractor, agente-contexto y los parches de las pruebas) y después en _de_las_rebanadas().
  - _de_las_rebanadas() importa de forma diferida planificacion, escaleta y capitulo.
  - Un agente en dos rebanadas: RuntimeError.
  - Sin manejador: AgenteSinEsquema.
  - Las rebanadas del bloque 3 se añaden en _de_las_rebanadas().
- PASO_QUE_LO_TRAE ya tiene los 12.

== planificacion/modelos.py ==
- SalidaPlanificador{plan: Plan, personajes: tuple[PersonajePlan, ...] ≥1, mundo: MundoPlan, estilo: GuiaEstilo}.
- Plan{modelo, reparto: Reparto, curva_tension: 10 enteros 0..10, pregunta_dramatica, tipo_final}.
  - Reparto{detonante, primer_umbral, punto_medio, crisis, climax: 1..10}, con .capitulo(Hito) -> int.
- PersonajePlan: extiende contexto.Personaje con nombre, alias, descripcion (≤600 caracteres), estado_inicial, sabe y relaciones: RelacionPersonaje{destino, tipo: TipoRelacion, estado_inicial?, estado_final?}.
- LocalizacionPlan: extiende Localizacion con nombre, descripcion (1..600), hito: Hito | None y estado_inicial: str | None.
- MundoPlan{localizaciones ≥1 (todas, las del contexto incluidas), objetos: Objeto{id, nombre, alias, poseedor | None}}. Sin ruta ni reglas: salen del contexto.
- GuiaEstilo: extiende Lenguaje con:
  - metricas: Metricas{frase_media_palabras (0, 60], proporcion_dialogo, descriptivo, legibilidad_min};
  - lista_negra;
  - onomastica | None;
  - ejemplos: como mucho 3, de ≤600 caracteres.
- Constantes TOPE_DESCRIPCION, TOPE_EJEMPLO y MAX_EJEMPLOS; tipo Id.

== planificacion/consultas.py ==
- class SalidaIncoherente(ValueError).
- guardar_planificacion(conexion, salida: SalidaPlanificador) -> None, en una transacción:
  - Sustituye la siembra anterior: capítulo 0 de glosario, inventario, estados y saber; relaciones; objetos; personajes y localizaciones que no son del contexto.
  - Personajes y localizaciones del contexto: upsert sin tocar origen, fuente, arco, nivel ni padre.
  - Siembra en el capítulo 0 estados, saber, inventario y glosario, con nombres y alias.
  - Escribe plan (contenido = la salida entera) y guia_estilo.
  - SalidaIncoherente: sin contexto validado, con un término que nombra dos entidades o con cualquier sqlite3.IntegrityError.
- leer_planificacion(conexion) -> SalidaPlanificador | None.
- leer_guia(conexion) -> GuiaEstilo | None.

== planificacion/materializar.py ==
- materializar_contexto(conexion, contexto: Contexto, momento: str) -> None.
  - En una transacción e idempotente.
  - Orden de escritura: personalizacion y hecho; después todos los personajes del contexto (nombre y fecha de nacimiento de los destinatarios) y las localizaciones, de padre a hijo; ruta y regla_mundo; evento de los hechos evento (capitulo NULL, sin presentes; excluye traducido al id del personaje de esa fuente); palabra_prohibida de nivel novela con vetos.palabras y vetos.temas.
  - ValueError si un excluye no tiene personaje.

== escaleta/modelos.py ==
- SalidaEscaletista{fichas ≥1}.
- FichaCapitulo{numero, hitos: tuple[Hito], objetivo, escenas ≥1 Escena{tipo 'escena'|'secuela', texto}, pov, localizacion, presentes ≥1, mencionados, dia ≥1, tension 0..10, palabras_objetivo 1000..1500, cierre, plantar: PresagioPrevisto{clave, descripcion}, cobrar: tuple[clave], hechos: tuple[id], traspasos: Traspaso{objeto, a | None}}.

== escaleta/consultas.py ==
- guardar_escaleta(conexion, salida) -> None:
  - Sustituye la escaleta anterior entera.
  - Crea un presagio por cada plantar (plantar_en = su ficha; cobrar_en = la ficha que lo cobra), con estado previsto en el capítulo 0.
  - SalidaIncoherente: clave ajena inexistente, hito en dos fichas, alguien presente y mencionado a la vez, clave de presagio repetida.
- leer_ficha(conexion, numero) -> FichaCapitulo | None, y leer_escaleta(conexion) -> tuple[FichaCapitulo, ...]. Devuelven la ficha tal como entró.

== capitulo/biblia.py ==
Excepciones:
- ErrorBiblia(ValueError), la base.
- CapituloNoVerificado(capitulo, estado), con .capitulo y .estado.
- ReferenciaDesconocida(tipo, ident), con .tipo ∈ personaje|localizacion|objeto|hecho|presagio|ficha|contexto y .ident.
- EscrituraInvalida.
- ValueError si antes_de no va de 1 a 11 o si el capítulo está fuera de rango.

Constantes: VERIFICADOR = "continuidad", TOPE_RESUMEN_CAPITULO = 240, TOPE_RESUMEN_ACTO = 360.

Dataclasses congeladas:
- PersonajeAFecha(id, nombre, alias, descripcion, ficha: dict, estado, sabe)
- Posesion(objeto, nombre, poseedor, desde)
- PresagioPendiente(clave, descripcion, plantado_en, cobrar_en)
- Lugar(id, nivel, padre, nombre, descripcion, hito, estado)
- Regla(regla, limites, costes, excepciones)
- Termino(termino, categoria, referencia, tipo)
- Resumen(ambito, numero, texto)
- Acto(numero, primero, ultimo)
- FinDeCapitulo(dia, localizacion)

Lecturas; antes_de = N y cada una ve las filas con capítulo < N:
- personajes_a_fecha(c, antes_de, ids) -> tuple[PersonajeAFecha, ...]
- inventario_a_fecha(c, antes_de) -> tuple[Posesion, ...]
- presagios_pendientes(c, antes_de) -> tuple[PresagioPendiente, ...]
- localizacion_con_ascendientes(c, localizacion, antes_de) -> tuple[Lugar, ...], de la localización a la macro.
- reglas_del_mundo(c) -> tuple[Regla, ...]
- glosario_a_fecha(c, antes_de) -> tuple[Termino, ...]
- resumen_acumulado(c, antes_de) -> tuple[Resumen, ...], compactado según §6.2.
- actos(c) -> tuple[Acto, ...] y acto_de(c, capitulo) -> Acto.

B-9:
- presentes_excluidos(c, antes_de, presentes) -> tuple[Hallazgo, ...]. Regla 'RF-74 · presente_excluido', severidad ALTA, localización 'ficha N'.
- dias_minimos(ruta: Sequence[(loc, dias)], padres: Mapping, origen, destino) -> int | None. Pura.
- salto_imposible(c, numero, dia, localizacion, anterior: FinDeCapitulo | None) -> tuple[Hallazgo, ...]. Reglas 'RF-76 · dia_retrocede' y 'RF-76 · viaje_imposible'.
- fin_de_capitulo(c, numero) -> FinDeCapitulo | None: lo registrado por el Bibliotecario o, si no hay, lo previsto en la ficha.
- continuidad_antes_de_escribir(c, numero) -> tuple[Hallazgo, ...], sobre la ficha guardada. ReferenciaDesconocida('ficha') si no existe.

Escrituras del Bibliotecario:
- Todas reciben capitulo = el de la orden vigente y van en una transacción.
- Todas lanzan CapituloNoVerificado si capitulo.estado no está en {verificado, aprobado} o si el capítulo no tiene capitulo_version; y ReferenciaDesconocida ante un id desconocido.
- La versión en curso es la última capitulo_version del capítulo.
- Funciones:
  - actualizar_estado_personaje(c, capitulo, personaje, estado)
  - registrar_saber(c, capitulo, personaje, datos)
  - actualizar_estado_localizacion(c, capitulo, localizacion, estado)
  - registrar_traspaso(c, capitulo, objeto, poseedor | None)
  - registrar_evento(c, capitulo, descripcion, lugar, presentes, *, dia=None, franja=None, momento=None, excluye: (personaje, TipoExclusion) | None) -> int. EscrituraInvalida si falta o sobra la escala de tiempo.
  - plantar_presagio(c, capitulo, clave) y cobrar_presagio(c, capitulo, clave). EscrituraInvalida si el estado a fecha no es previsto o plantado, respectivamente.
  - abrir_presagio(c, capitulo, clave, descripcion). EscrituraInvalida si la clave ya existe.
  - registrar_termino(c, capitulo, termino, categoria, referencia | None, tipo). EscrituraInvalida si referencia y categoría no casan.
  - escribir_resumen(c, capitulo, ambito 'capitulo'|'acto', texto, momento). EscrituraInvalida por encima del tope de palabras.
  - registrar_uso_de_hecho(c, capitulo, hecho)
  - registrar_fin(c, capitulo, dia, localizacion)
- borrar_lo_escrito(c, capitulo) -> None (B-16): sin guarda; no toca los resúmenes de otras versiones.
- pendiente_del_bibliotecario(c, capitulo) -> tuple[str, ...], con valores entre 'resumen', 'dia_fin', 'localizacion_fin' y 'resumen_acto'.

Lecturas para MCP (§4.1.6), todas -> dict | None:
- contexto_para_mcp(c), sin texto_libre
- plan_para_mcp(c)
- ficha_para_mcp(c, numero)
- guia_para_mcp(c)

== DATOS DE PRUEBA ==
- capitulo/tests/referencia.py: biblia_de_referencia(ruta, contexto=None) -> Connection, verificar(conexion, *capitulos) y MOMENTO.
- planificacion/tests/referencia.py: salida_planificador() -> dict.
- escaleta/tests/referencia.py: salida_escaletista() -> dict.

### Decisiones que tomó sobre la marcha

- AJ-1 mínimo en proyecto/: cambiar el enum rompía la importación de maquina.py. En planificacion queda una sola orden, la del planificador (con las notas de plan si las hay), y persistencia.py cuenta sus órdenes aceptadas. Ajusté las pruebas de proyecto/ que nombraban arquitecto, personajes, mundo o estilo. No hay cambios de lógica más allá de esto: AJ-2 a AJ-5 quedan para el cerebro.
- Lo que sabe un personaje (personaje_sabe) va un dato por fila y se acumula: a fecha N−1 sabe todo lo aprendido antes de N. El estado de personaje y el de localización, en cambio, son la última fila anterior a N.
- El estado del presagio (previsto, plantado, cobrado) va en una tabla de historia, presagio_estado(presagio, capitulo, estado), y no en una columna. Así el borrado de B-16 por capítulo es exacto. En presagio quedan clave, plantar_en y cobrar_en (previstos por la escaleta) y abierto_en (si lo abrió el Bibliotecario).
- evento separa las dos escalas de B-6: momento para los recuerdos, y dia más franja opcional para la historia. Un CHECK exige exactamente uno de los dos.
- informe se rehízo como uno por (capitulo_version, verificador), con hallazgos en JSON, métricas y la severidad máxima. Se quitó ambito: lo de manuscrito va a gate_resultado.
- resumen guarda qué versión de capítulo lo escribió (capitulo y version). El vigente de cada ámbito es el de mayor versión y, a igual versión, el último escrito. Un acto cerrado que no tiene resumen de acto viaja con los resúmenes de sus capítulos.
- personaje.nombre es NULL hasta la planificación, salvo el de los destinatarios, que sale del contexto. Añadí también personaje.descripcion, porque lectura.json la espera.
- glosario: la categoría es una lista cerrada, referencia es NULL solo en la categoría 'otro' y hay UNIQUE(termino, capitulo). Un mismo término que nombra dos entidades en la planificación da SalidaIncoherente.
- B-18: la fuente del excluye es válida si es la de un personaje real de la novela, lo que admite también segundo_destinatario. Son dos reglas nuevas del validador, exclusion_en_evento y exclusion_con_fuente, con un caso inválido cada una y otro de control.
- La materialización lleva todos los personajes y localizaciones del contexto, más la ruta y las reglas del mundo. Los eventos del contexto no tienen presentes: el hecho no dice quién estaba.
- Salida del planificador: tiene las claves plan, personajes, mundo y estilo. El mundo no trae ruta ni reglas, que salen del contexto. GuiaEstilo extiende Lenguaje, y plan.contenido guarda la salida entera para leer_planificacion.
- En ficha_capitulo, pov y localizacion son NOT NULL. ficha_capitulo_hito lleva UNIQUE(hito) como red de seguridad de RF-42: la regla sigue siendo del escaletista.
- capitulo_version: ruta_borrador es la salida del Escritor y ruta, el texto vigente, que reescribe el Editor.
- La guarda de V-19 (RF-106) vive en las escrituras de biblia.py: el capítulo tiene que estar en verificado o aprobado y tener al menos una versión. La versión en curso es la última capitulo_version del capítulo.
- Las lecturas reciben antes_de = N, de 1 a 11; 11 es la novela entera.
- El Bibliotecario no crea objetos nuevos: solo registra traspasos de objetos que ya existen desde la planificación.
- Los MANEJADORES de las rebanadas se importan de forma diferida para evitar el import circular. Los de proyecto/ mandan sobre los de las rebanadas, porque es donde las pruebas sustituyen uno.
- Las pruebas de transacción de shared/tests/test_db.py pasan de la tabla glosario a cache, porque glosario tiene ahora columnas obligatorias.
- pendiente_del_bibliotecario pide el resumen de acto si el capítulo es el último de su acto o si el acto ya tiene resumen (una regeneración, B-17).
- La biblia expone es_momento (fecha parcial o periodo) desde contexto/modelos.py, y el validador de Hecho la usa también.

### Pendientes que dejó

- AJ-6 y cambio fallido. La historia de la biblia va por capítulo y no por versión, y B-16 borra lo escrito para el capítulo cuando empieza el Bibliotecario de la versión nueva. Si el cambio falla, la biblia no vuelve a la versión anterior. resumen, hecho_uso y dia_fin sí van por versión. Hay que decidir en el bloque 3 si se etiqueta por versión o si se restaura.
- Para el cerebro: en persistencia._AVANCE, las banderas personajes (EXISTS personaje) y mundo (EXISTS localizacion y ruta) quedan en verdadero en cuanto se materializa el contexto. Con AJ-1, plan_completo debería pasar a ser plan + guia_estilo. Además, test_api y test_persistencia esperan hoy que el planificador responda 501 sin esquema (paso 4): cambiarán cuando llegue su manejador.
- orden.sello admite NULL: el cerebro tiene que rellenarlo al emitir la orden y volver a sellarla al tomar el bloqueo (AJ-4).
- informe_juez sigue con la columna ciclo. AJ-3 guarda los gates por pasada; queda para el bloque 3.
- B-12 pide guardar el hash de las listas del guardarraíl, y el esquema aún no tiene dónde. Lo decide el agente de verificadores.
- capitulo/manejadores.py lo tocarán dos agentes: el de verificadores (escritor, editor-estilo, juez-capitulo) y el que escriba el manejador del Bibliotecario. Hay que coordinarlos para que no se pisen.
- Para el bloque 3: el resumen vigente se elige por la mayor versión. Con regeneraciones debería salir de la versión vigente de cada capítulo.
- Volver a materializar el contexto cuando ya hay fichas o usos de hechos fallaría por claves ajenas. No ocurre en el grafo actual.

### Cambios de documento que pide

- docs/definitions.md §9: B-18, el campo excluye {fuente, tipo: muerte|partida} de los hechos evento, con las reglas exclusion_en_evento y exclusion_con_fuente.
- docs/architecture.md §6 (modelo de datos): la historia por capítulo con el capítulo 0 (B-2); las tablas nuevas personaje_estado, personaje_sabe, localizacion_estado, objeto, presagio_estado, ficha_capitulo_hito y gate_resultado; informe único por versión y verificador; evento con dos escalas de tiempo; resumen por versión.
- docs/architecture.md §3 y §3.1: los 12 agentes y una sola orden en planificacion (R-1, AJ-1). §8: cada rebanada expone MANEJADORES en <rebanada>/manejadores.py y proyecto/manejadores.py los agrega.
- specs/spec-backend-1.md §6: la tabla del modelo de datos con las tablas nuevas. §5.3: los ficheros borrador, prompt.parte-N y verificacion/pasada-k.
- docs/validators.md: V-22 (la propiedad «a fecha N−1» de capitulo/tests/test_biblia.py como base) y V-11 con las dos reglas nuevas de B-18.
- specs/spec-backend-2.md: apuntar las decisiones_sobre_la_marcha, según R-6.
- docs/domain-knowledge.md: revisar si el árbol de la dimensión 9 debe mostrar la hoja excluye del hecho evento.
- AGENTS.md: no aplica, no hay dependencias nuevas.
