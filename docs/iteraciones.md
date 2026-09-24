# iteraciones.md — Registro de iteraciones

> Propósito: dejar escrito, **en el momento en que ocurre**, qué se intentó, qué falló o qué se descubrió y qué se cambió por ello. Al final no se puede reconstruir ([plan-entrega.md](../specs/plan-entrega.md) §3, «Cierre de cada hito»). Es la fuente del apartado de iteraciones de la documentación de entrega (H8).
>
> Los ataques deliberados no van aquí, sino en [red-team.md](red-team.md). Si un ataque obliga a cambiar algo, el cambio tiene entrada en los dos, y cada una cita a la otra.

---

## Formato

Una entrada por **episodio**: una ejecución, un grilling, una auditoría, una prueba en esta máquina. Si un episodio destapa varias cosas, van dentro con letras: (a), (b).

```markdown
### I-NN · AAAA-MM-DD · Hn · Lo descubierto en una línea, no la tarea

- **Qué se intentó:** lo que se estaba haciendo cuando apareció.
- **Qué falló o qué se descubrió:** el hecho, con la cifra o el síntoma que lo delató.
- **Qué se cambió y dónde:** la corrección, con los ficheros, las secciones y las decisiones (`B-n`, `TC-n`, `RF-n`, `V-n`) donde vive.
```

| Campo | Regla |
|---|---|
| `I-NN` | Correlativo y sin huecos. No se reutiliza |
| Fecha | La del día en que ocurrió, no la del commit que lo recoge |
| Hito | El de [plan-entrega.md](../specs/plan-entrega.md) §3 al que pertenece el trabajo afectado (`H0`…`H8`), o varios separados por comas. Si se descubrió trabajando en otro, lo cuenta «Qué se intentó» |
| Qué se cambió y dónde | Lo que aún no está aplicado en un sitio que se nombra lleva la marca **pendiente**. Quien lo aplica quita la marca |

- Se añade al final. Una entrada no se reescribe, salvo para quitar una marca **pendiente**: si algo posterior la deshace, entra una nueva que la cita (I-03 con I-01 e I-02).
- Si lo descubierto se acepta como riesgo y no se cambia nada, «Qué se cambió» lo dice y cita dónde queda aceptado. Un «nada» declarado vale; un campo vacío, no.
- Cada contraejemplo de TLC entra aquí junto con el cambio en el código (plan-entrega, H1).
- Ningún dato de una persona real. Si hace falta un ejemplo, sale de los briefs ficticios.
- Las entradas anteriores a este registro se reconstruyen desde git y lo dicen, con el commit.

---

## Entradas

### I-01 · 2026-09-23 · H0, H1 · Tres supuestos de la pila que no se cumplían en esta máquina

*Reconstruida desde el commit `8251788`.*

- **Qué se intentó:** comprobar en este Windows, antes de escribir el paso 0 de [plan-backend-v1.md](../specs/plan-backend-v1.md), que la pila decidida funciona.
- **Qué falló o qué se descubrió:**
  - (a) `mutmut` 3 no funciona en Windows sin WSL.
  - (b) Git tiene `core.autocrlf=true`, y convertir los saltos de línea del BPE de `o200k_base` rompe su SHA-256. `tiktoken` borra entonces la copia y la vuelve a descargar: se pierden a la vez el determinismo del estimador y el arranque sin red.
  - (c) El FastMCP del SDK oficial `mcp` ya no existe en su versión 2, y Starlette no arranca el `lifespan` de las subaplicaciones montadas.
- **Qué se cambió y dónde:**
  - (a) `cosmic-ray` sustituye a `mutmut` para V-15: [architecture.md](architecture.md) §7, plan-backend-v1.md paso 0 y AGENTS.md. La retira I-03.
  - (b) El BPE se versiona en `backend/capitulo/bpe/`, marcado como binario en `.gitattributes`, con una prueba de su SHA-256 (RF-52c): architecture.md §6.3 y plan-backend-v1.md paso 0.
  - (c) Se usa el paquete `fastmcp`, y el `lifespan` de cada superficie montada se combina con el de la aplicación: architecture.md §7 y plan-backend-v1.md paso 5.

### I-02 · 2026-09-23 · H1 · `cosmic-ray` daba por INCOMPETENT mutantes que estaban eliminados

- **Qué se intentó:** cerrar el paso 2 pasando la mutación (V-15) sobre `backend/contexto/validacion.py`, como pide H1.
- **Qué falló o qué se descubrió:**
  - (a) 190 de los 498 mutantes salían INCOMPETENT cuando en realidad estaban eliminados. En Windows, pytest escribe su salida en cp1252, y `cosmic-ray` la decodifica como UTF-8 en la rama de mutante eliminado: basta un «é» o un «→» en el informe de pytest para que la decodificación reviente.
  - (b) Ocho mutantes sobrevivían en la guarda que impide salir de `contexto` (`puede_salir_de_contexto`, RF-22, V-20), porque le sobraba una comprobación: además de `valido`, exigía que no hubiera hallazgos bloqueantes. `valido` ya exige cero hallazgos, y el validador solo emite hallazgos bloqueantes.
- **Qué se cambió y dónde:**
  - (a) El comando de pruebas de `cosmic-ray.toml` lanza pytest con `python -X utf8`. El porqué está en la cabecera del fichero.
  - (b) La guarda queda en `informe.valido` (`backend/contexto/validacion.py`), y `test_todo_hallazgo_del_validador_es_bloqueante` (`backend/contexto/tests/test_validacion.py`) fija la premisa de la que depende. Los casos de límite que matan al resto de supervivientes, y los supervivientes equivalentes con su razón, están en `backend/contexto/tests/test_validacion_limites.py`.

### I-03 · 2026-09-23 · H1, H3 · Se retira `cosmic-ray`: V-15 pasa a ser cobertura por regla

- **Qué se intentó:** mantener la mutación como V-15 sobre el validador de ontología (H1) y sobre los verificadores (H3).
- **Qué falló o qué se descubrió:** no compensa el tiempo que queda hasta la entrega. `cosmic-ray` ejecuta la batería entera por cada mutante (498 solo en el validador), y en H3 se sumarían los verificadores.
- **Qué se cambió y dónde:** V-15 pasa a ser una comprobación de **cobertura por regla**: cada regla tiene una prueba que la dispara y otra de control que no. Deshace la elección de I-01 (a) y deja sin uso el arreglo de I-02 (a). La guarda simplificada de I-02 (b) y las pruebas de límite se quedan. Se aplica en:
  - [validators.md](validators.md), las dos filas de V-15 · **hecho** (2026-09-24)
  - [spec-backend-1.md](../specs/spec-backend-1.md), V-15 en §9 y D-7 · **hecho** (2026-09-24)
  - architecture.md §7 y AGENTS.md, en la pila y en las comprobaciones del backend · **pendiente**
  - plan-backend-v1.md, pasos 2 y 7, y plan-entrega.md, H1 y H3 · **pendiente**
  - `pyproject.toml` y `cosmic-ray.toml` · **pendiente**. `pyproject.toml` y §7 cambian juntos, o falla V-10.

### I-04 · 2026-09-23 · H1 · Dos huecos del grafo que salieron en el grilling del paso 3

- **Qué se intentó:** cerrar con grilling el paso 3 de plan-backend-v1.md (grafo, siguiente orden y bloqueo) antes de escribirlo. El código cita esas preguntas como Q4 a Q8.
- **Qué falló o qué se descubrió:**
  - (a) «Reintentar» desde `detenida` volvía siempre a `capitulos` (architecture.md §3.1, RF-64b). Pero a `detenida` también se llega agotando el tope de intentos de una fase que no es el bucle (RF-07a): un proyecto detenido en `planificacion` habría saltado a `capitulos` sin escaleta.
  - (b) No estaba escrito qué gasta un intento de capítulo. Por ejemplo: ¿una salida mal formada del Editor o del Bibliotecario cuenta como intento del Escritor y manda reescribir el capítulo?
- **Qué se cambió y dónde:**
  - (a) Q6. El proyecto guarda de qué fase viene (`proyecto.detenida_desde`, en `backend/shared/esquema.sql`), y «reintentar» vuelve a ella (`DESTINO_DE_REINTENTAR`, en `backend/proyecto/transiciones.py`). Desde `verificacion_manuscrito` sigue volviendo a `capitulos`, porque se aplica RF-64b. Queda por recoger en architecture.md §3.1, en la fila de `detenida`, y en spec-backend-1.md RF-64b, que aún dicen «se vuelve a `capitulos`» · **hecho** (2026-09-24).
  - (b) Q4 y Q5. Dos tipos de fallo (`TipoDesenlace`, en `backend/proyecto/maquina.py`):
    - **de contenido** —deterministas altos o bloqueantes, guardarraíl, juez de capítulo que rechaza, o salida inválida del Escritor—: gasta `capitulo.intentos` y vuelve al Escritor;
    - **de formato** —salida inválida de un agente posterior al Escritor—: repite solo ese agente sobre el mismo borrador y gasta el contador nuevo `proyecto.intentos_paso`.

    Queda por recoger en architecture.md §3.2 · **hecho** (2026-09-24).

### I-05 · 2026-09-23 · H1 · `fastapi[standard]` habría escondido dependencias a V-10

- **Qué se intentó:** añadir FastAPI para el paso 3.
- **Qué falló o qué se descubrió:** el extra `[standard]` instala `uvicorn`, `httpx` y otros paquetes sin nombrarlos en `pyproject.toml`. V-10 compara las dependencias declaradas con architecture.md §7, así que no los habría visto, y la pila habría crecido sin pasar por la tabla.
- **Qué se cambió y dónde:** `fastapi` sin extras, con `uvicorn` como servidor y `httpx`, solo en desarrollo, para el `TestClient`, declarados en `pyproject.toml`. Los nombran architecture.md §7 (filas «Backend» y «Pruebas y análisis estático») y la pila de AGENTS.md, con el porqué.

### I-06 · 2026-09-23 · H4 · Dos contradicciones en los gates de manuscrito, al preparar los tramos B y C

- **Qué se intentó:** preparar los tramos B (pasos 4 a 8) y C (pasos 8a a 10) de plan-backend-v1.md antes de construirlos.
- **Qué falló o qué se descubrió:**
  - (a) El umbral del juez de manuscrito, «≥3 en todos y media ≥3,5» (architecture.md §4.1, RF-113), no se puede probar en su frontera. Con cinco notas enteras, la media no puede valer exactamente 3,5 (la suma tendría que ser 17,5), así que el caso «media a 3,5» de V-32 no se puede construir.
  - (b) El Revisor no puede arreglar un fallo de cobertura. La cobertura se mide sobre `hecho_uso`, y ese registro solo lo escribe el Bibliotecario: un capítulo corregido por el Revisor seguiría sin contar sus hechos.
- **Qué se cambió y dónde:** en [spec-backend-2.md](../specs/spec-backend-2.md). `docs/` lo recoge cuando el código lo aplique (AGENTS.md, regla 3).
  - (a) TC-5: **suma ≥ 18 y ningún criterio por debajo de 3**. En enteros equivale a «media ≥ 3,5», pero se puede probar en la frontera: V-32 se prueba con sumas 17 y 18.
  - (b) §3, punto 7. En `revision`, cada capítulo pasa por Revisor, deterministas y Bibliotecario sobre la versión nueva. Los capítulos que hay que corregir salen de `ficha_capitulo_hecho` (cobertura), de `evento.capitulo` (Lean) y de un campo `capitulos` en la salida del juez. Cambia la tabla del paso 3 y la spec TLA+.

### I-07 · 2026-09-24 · H2 a H6 · Bloques 2 y 3 del backend: lo que cambió al construirlos

- **Qué se intentó:** construir los pasos 4 a 10 de plan-backend-v1.md (planificación, Recuperador, verificadores, escritura MCP, gates, publicación, cambio del lector y worker) con las decisiones de [spec-backend-2.md](../specs/spec-backend-2.md).
- **Qué falló o qué se descubrió:**
  - (a) La extensión nativa de `tiktoken` no carga en esta máquina: la bloquea una directiva de control de aplicaciones de Windows (dif-local-vm L-2).
  - (b) No hay `elan`/`lake`, Java ni el CLI `claude` en el PATH (L-3), así que Lean, TLC y el `claude -p` real no se pueden ejecutar aquí.
  - (c) El contrato Lean exige una franja en cada evento de la historia, y la ficha y el Bibliotecario solo manejan días.
  - (d) La revisión de diseño de la sesión formal destapó que los gates por ciclo reutilizaban cobertura y Lean de una versión anterior, y que un ejecutor caído podía duplicar la biblia.
- **Qué se cambió y dónde:**
  - (a) M-10: respaldo del estimador en Python puro sobre el mismo `o200k_base` y con el mismo factor, en `backend/capitulo/estimador.py`; la decisión sigue siendo `tiktoken` ([architecture.md](architecture.md) §6.3 y §7).
  - (b) Las pruebas que ejecutan Lean o Chromium llevan `skipif`, y el worker se prueba con un `claude` falso (TC-10). Lean, TLC y la prueba manual de `claude -p` quedan pendientes.
  - (c) M-14: un evento sin franja se emite como `manana` hasta que `formal/lean` acepte la franja opcional; puede dar falsos positivos dentro del mismo día.
  - (d) AJ-3 (gates por pasada) y AJ-4 (sello con la generación del bloqueo), en `backend/proyecto/` ([architecture.md](architecture.md) §3.2).
  - `docs/` recoge lo construido en esta fecha: architecture §2, §3, §3.1, §3.2, §4, §6, §6.3, §7 y §8; definitions §3, §6 y §9; validators §2; spec-backend-1 y los planes.

### I-08 · 2026-09-24 · H1, H7 · El Agente de Contexto resuelve solo las contradicciones del comprador, y E5 falla

- **Qué se intentó:** ejecutar E5 según E-7, hasta la entrevista: `/entrevista evals/briefs/e5-contradiccion.json` sobre el proyecto `317444e9136c4088979143515d55ee8c`.
- **Qué falló o qué se descubrió:**
  - (a) El proyecto llegó a `planificacion` con 0 de los 2 hallazgos esperados de RF-24 y 0 preguntas a la compradora. En el Trabajo 2, el Agente de Contexto cambió la edad (de 6 a 8, la que da la fecha de nacimiento) y el tono (de `melancolico` a `ligero`), y el validador recibió un contexto ya limpio. Según el oráculo del brief, cualquiera de los dos cambios es un fallo del eval.
  - (b) Causa: `.claude/agents/agente-contexto.md` pide a la vez «lo que el comprador fijó, se respeta tal cual» y terminar cuando «ninguna regla de coherencia falla». Con un valor del comprador que incumple una regla, las dos órdenes chocan y gana la segunda.
  - (c) Ninguna comprobación del backend verifica que el contexto conserve el destinatario, `edad_lector` y los hechos del brief. Además, en `contexto` no hay parada humana: un rechazo del validador vuelve al agente, y `/entrevista` solo vuelve a preguntar desde `intake`.
- **Qué se cambió y dónde:** el resultado está en [evals.md](evals.md) y en `evals/e5-contradiction/results/2026-09-24.md`. Los tres arreglos quedan **pendientes**, recogidos en [plan-multisesion.md](../specs/plan-multisesion.md): (a/b) en el prompt, dejar sin tocar el valor del comprador que incumple una regla y nombrarlo, que es el ajuste v1 → v2; (c) una regla determinista de conservación del brief en el validador, y los hallazgos sobre valores del comprador llevan a `esperar_humano` con la pregunta en `/entrevista`. Después se repite E5.

### I-09 · 2026-09-24 · H7 · La API de ingesta de Langfuse que planeábamos usar está obsoleta, y su MCP no escribe trazas

- **Qué se intentó:** conectar el backend con Langfuse según E-1, y valorar si bastaba el servidor MCP de Langfuse.
- **Qué falló o qué se descubrió:**
  - (a) La [referencia del MCP de Langfuse](https://mcp.reference.langfuse.com) solo tiene herramientas de consulta, prompts, scores sobre trazas existentes, datasets y evaluadores: **ninguna crea trazas, spans ni uso de tokens**. No cubre la sección de observabilidad del enunciado.
  - (b) La especificación OpenAPI de Langfuse Cloud marca `POST /api/public/ingestion` como obsoleta: **desde el 2026-11-16 solo acepta scores**. El camino vigente es el endpoint OpenTelemetry (`/api/public/otel/v1/traces`, con la cabecera `x-langfuse-ingestion-version: 4`) y `POST /api/public/scores`.
  - (c) Las claves de la persona estaban en la configuración del plugin `langfuse-observability` de Claude Code, y la secreta en su almacén seguro: el backend no puede leerlas de ahí, y copiar secretos entre ficheros no se hace.
  - (d) Al enviar los proyectos existentes, `/api/public/scores` respondió **429**: el plan gratuito no admite un score por petición a ese ritmo.
  - (e) Al leer lo enviado, E1 tenía 1398 observaciones en vez de 699: **Langfuse no reemplaza un span reenviado con el mismo id, lo duplica.** El supuesto de que reenviar actualizaba era falso, y reenviar tras cada `/resultado` habría multiplicado los datos.
- **Qué se cambió y dónde:** `backend/observabilidad/` envía por OTLP en JSON con `httpx` (que pasa de dependencia de desarrollo a dependencia de ejecución), con los scores en lotes de `score-create` por la ingesta y reintento ante 429 y 503, y cada span y cada score enviados una sola vez (lo enviado queda en `cache` de cada proyecto; los padres salen cuando ya no cambian). Se borraron las trazas duplicadas y se reenvió todo: E1 queda con 699 observaciones y 224 scores, sin repetidos; y solo metadatos, con una prueba de centinela ([validators.md](validators.md) §2.9). El MCP de Langfuse queda en `.mcp.json` para la sesión de desarrollo: versiones de prompt y consultas para la tabla de evals. Las claves van a un `.env` que escribe la persona. [architecture.md](architecture.md) §7 y §8, AGENTS.md, `.env.example`.


### I-10 · 2026-09-24 · H7 · El Agente de Contexto cambia o anonimiza lo que dio el comprador, y el backend lo acepta

- **Qué se intentó:** ejecutar E4 (vetos) con `claude -p "/generar …"` sin supervisión, después de que E5 hubiera mostrado que el agente corrige valores del comprador (I-08).
- **Qué falló o qué se descubrió:**
  - (a) En la normalización de E4, el Agente de Contexto aplicó la política de privacidad de la organización (la instrucción RGPD que llevan todas las sesiones y subagentes) y sustituyó los nombres de los protagonistas, la fecha de nacimiento **y el término vetado** por `[NOMBRE_ANONIMIZADO]` y `[FECHA_OCULTA]`. El guardarraíl habría vigilado la etiqueta y no la palabra real. El orquestador detuvo la generación por su cuenta.
  - (b) Es el mismo hueco que E5 visto desde otro lado: el backend no compara la salida del agente con el brief, así que un cambio silencioso —una «corrección» o una anonimización— es indistinguible de un dato bueno.
  - (c) Es aleatorio: E1 y E5 conservaron los nombres con la misma política.
- **Qué se cambió y dónde:** regla **B-20, conservación del brief** ([spec-backend-2.md](../specs/spec-backend-2.md)): `backend/contexto/conservacion.py`, aplicada en el manejador del Agente de Contexto (`backend/proyecto/manejadores.py`) al registrar la normalización y el contexto; el patrón de marcador pasa a ser uno solo, compartido con el verificador de prosa. Pruebas en `contexto/tests/test_conservacion.py` y `proyecto/tests/test_contexto_en_grafo.py`. Prompt del agente alineado: lo que fijó el comprador sale tal cual y nunca se sustituye por una etiqueta. [architecture.md](architecture.md) §4 y [validators.md](validators.md) §2.2. E4 se repitió con un proyecto nuevo y conservó el veto; E3 pasó la normalización y el contexto con la regla activa. E5 no se ha repetido.

### I-11 · 2026-09-24 · H7 · Tres fallos del sistema que salieron en las novelas de E3 y E4

- **Qué se intentó:** llevar E3 y E4 hasta publicar con la regla B-20 activa.
- **Qué falló o qué se descubrió:**
  - (a) **Falso positivo de Lean en «lugar único».** El momento de la historia es día más franja, sin orden dentro de la franja, y un evento sin franja cuenta como `manana` (M-14). Un desplazamiento entre dos lugares hermanos en la misma tarde se lee como estar en dos sitios a la vez: 8 violaciones en E3 y 36 en E4. El Revisor no puede corregirlo porque el texto es correcto, y las dos novelas quedaron en `revision` sin poder publicarse.
  - (b) **El juez de capítulo puede leer una versión rechazada de un capítulo anterior.** `leer_capitulo` exige versión e intento, y la orden del juez solo trae los de su propio capítulo. En E3 citó el intento 1, rechazado, del capítulo 9, y tumbó un capítulo 10 correcto; con los otros dos rechazos, el proyecto pasó a `detenida`.
  - (c) **El Bibliotecario omite el resumen de acto** al reescribir un capítulo de un acto que ya lo tiene (B-17): siete fallos de forma en E4 y uno en E3, un reintento cada uno.
  - (d) **`claude -p` sin supervisión y los permisos.** La skill escribe MSM con `${CLAUDE_PROJECT_DIR:-.}`, y en modo sin preguntas esa expansión se deniega aunque `Bash(uv run *)` esté permitido; en Windows el orquestador además elegía PowerShell, que la skill no autoriza. Afecta igual al worker de `/regenerar`.
- **Qué se cambió y dónde:** nada todavía; los cuatro quedan en [plan-multisesion.md](../specs/plan-multisesion.md). Para las ejecuciones se usó `--disallowedTools PowerShell --allowedTools "Bash(uv run *)" Agent Skill` y una instrucción de ruta absoluta. Informes: [evals/report.md](../evals/report.md).
