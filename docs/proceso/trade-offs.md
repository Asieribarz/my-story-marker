# trade-offs.md — Decisiones de diseño: opciones, criterios y elección

> Propósito: dejar cada decisión de diseño relevante escrita como decisión —**qué opciones había, con qué criterios se eligió, qué se eligió y qué cuesta**—, con el identificador original y el enlace al documento donde se tomó. Resume, no redefine: si este documento y la fuente discrepan, manda la fuente. El contexto general está en [spec-inicial.md](spec-inicial.md).
>
> Convención: cuando la fuente no enumera la alternativa descartada y solo se deduce del razonamiento, se marca como *(implícita)*. Lo que no está cerrado se dice.

Identificadores: `D-n` ([spec-backend-1.md](../../specs/spec-backend-1.md) §10), `E-n` ([plan-entrega.md](../../specs/plan-entrega.md) §2), `R-n`, `B-n`, `TC-n`, `AJ-n`, `M-n` ([spec-backend-2.md](../../specs/spec-backend-2.md)), `A-n`, `S-n` ([plan-agentes.md](../../specs/plan-agentes.md)), `F-n` ([plan-frontend.md](../../specs/plan-frontend.md)), `I-n` ([iteraciones.md](../iteraciones.md)).

---

## Índice

| # | Decisión | Estado |
|---|---|---|
| 1 | [Un agente o varios, y qué modelo para cada uno](#1-un-agente-o-varios-y-qué-modelo-para-cada-uno) | Cerrada (R-1) |
| 2 | [Quién orquesta](#2-quién-orquesta-el-backend-decide-o-la-sesión-decide) | Cerrada |
| 3 | [Formato de la story bible](#3-formato-de-la-story-bible) | Cerrada; búsqueda abierta (D-1) |
| 4 | [Acceso a la biblia por MCP en tres superficies](#4-acceso-a-la-biblia-por-mcp-en-tres-superficies) | Cerrada (D-11) |
| 5 | [Modelo de lectura: web y PDF desde la misma lectura HTML](#5-modelo-de-lectura-web-y-pdf-desde-la-misma-lectura-html) | Cerrada (E-2, D-8, TC-6, TC-7) |
| 6 | [Dónde se hace la entrevista](#6-dónde-se-hace-la-entrevista) | Cerrada (E-3), revisada en parte (F-10) |
| 7 | [TLA+ y su relación con el flujo real](#7-tla-y-su-relación-con-el-flujo-real) | Cerrada (V-25) |
| 8 | [Qué invariantes comprueba Lean](#8-qué-invariantes-comprueba-lean-y-por-qué-esas) | Cerrada (TC-1, TC-2) |
| 9 | [Tope de 100.000 tokens y cómo se cuentan](#9-tope-de-100000-tokens-y-cómo-se-cuentan) | Cerrada (D-5); D-9 abierta |
| 10 | [Guardarraíl de palabras prohibidas](#10-guardarraíl-de-palabras-prohibidas) | Cerrada (B-11, B-12) |
| 11 | [Suscripción y nunca API de pago](#11-suscripción-y-nunca-api-de-pago) | Cerrada |
| 12 | [Retirada de cosmic-ray](#12-retirada-de-cosmic-ray-v-15-por-regla) | Cerrada (R-5) |
| 13 | [Recortes R-1 a R-3](#13-recortes-r-1-a-r-3) | Cerrada |
| 14 | [Observabilidad con Langfuse](#14-observabilidad-con-langfuse-e-1--d-3) | **En curso** |
| 15 | [Otras decisiones con coste visible](#15-otras-decisiones-con-coste-visible) | Varias |

---

## 1. Un agente o varios, y qué modelo para cada uno

| Opción | A favor | En contra |
|---|---|---|
| Un solo agente que planifica, escribe, revisa y actualiza la memoria *(implícita)* | Menos piezas y menos invocaciones | Tendría que cargar la biblia entera (choca con el tope de §9), leería el texto no confiable del comprador y se juzgaría a sí mismo |
| Un agente por tarea de planificación: Arquitecto, Personajes, Mundo, Estilo y Escaletista (diseño previo a R-1) | Salidas pequeñas y especializadas | Cinco órdenes secuenciales y cinco esquemas antes del primer capítulo |
| **Un agente por papel, con la planificación en uno solo (R-1): 12 agentes** | Cada agente ve solo lo suyo; cada salida tiene su esquema; los jueces están separados del que escribe | Más definiciones que mantener; ~50 invocaciones por novela (E-7) |

**Criterios.**
- **Aislar el texto no confiable.** Solo el Extractor y el Intérprete lo leen, y su única herramienta es de solo lectura.
- **Separar quien escribe de quien juzga.** Los agentes proponen y los verificadores disponen.
- **Que cada agente reciba solo lo que necesita.** El Escritor trabaja con el prompt del Recuperador y no tiene MCP.
- **Elegir el modelo por adelantado**, porque el gasto no se puede degradar en caliente.

**Elección.**
- **12 subagentes de Claude Code** ([architecture.md](../architecture.md) §3).
- **Modelos:**
  - `opus` para la prosa, que es el producto: Escritor y Revisor.
  - `sonnet` para planificar, extraer hechos de cada capítulo (Bibliotecario), corregir estilo y juzgar: «un juez más débil que el escritor no detecta lo que tiene que detectar».
  - `haiku` solo donde la salida es corta y la valida un esquema cerrado: Extractor, Intérprete y Exportador.
- R-1 fundió Arquitecto, Personajes, Mundo y Estilo en un único `planificador` con una sola salida JSON.
- La verificación multiagente como método sobre el propio proceso (autoconsistencia, debate) se descartó: multiplica el coste sin un criterio de parada claro ([validators.md](../validators.md) §6).

**Coste.**
- El número de invocaciones se acerca a los límites de la suscripción. E-7 lo mitiga ejecutando solo tres novelas completas en las evaluaciones.
- Queda por confirmar que los subagentes con otro modelo descuentan de la suscripción ([architecture.md](../architecture.md) §10).

Fuentes: [architecture.md](../architecture.md) §3, [spec-backend-2.md](../../specs/spec-backend-2.md) R-1, [plan-agentes.md](../../specs/plan-agentes.md) §5.1.

## 2. Quién orquesta: el backend decide o la sesión decide

| Opción | A favor | En contra |
|---|---|---|
| La sesión de Claude Code decide el siguiente paso con reglas en su skill *(implícita)* | Nada que construir en el backend | Un modelo aplicando reglas es lo más frágil del sistema; los contadores vivirían en la ventana y se perderían al reiniciar |
| El backend llama él mismo a los modelos *(implícita)* | Control total | Exige un cliente de proveedor y gasto de API medido: descartado (RNF-10, §11) |
| **El backend decide, la sesión ejecuta** | La decisión es una función determinista del estado persistido, con pruebas (V-33) y modelada en TLA+ (V-25) | Que la sesión ejecute la orden tal como llega sigue sin poder verificarse (V-18, riesgo **U** declarado) |

**Criterios.**
- Reanudación tras una caída, un fin de ventana o días de espera.
- Topes de intentos que sobrevivan al reinicio.
- Un solo ejecutor por proyecto.
- Que la decisión sea verificable.

**Elección.**
- El backend expone la **siguiente orden** (RF-08, RF-08a). La persiste al emitirla, con un sello `<proyecto>:<orden>:<generación>` (AJ-4), y escribe él la transición al registrar el resultado.
- La skill `orquestar-novela` solo pide la orden, lanza el subagente y lee el acuse. El hook `SubagentStop` es la única vía de registro (A-5).
- Un bloqueo en la fila del proyecto impide que la sesión y el worker trabajen a la vez (RF-09b).

**Coste.**
- Hace falta más backend.
- «Una invocación es un intento» es protocolo y no se puede imponer: el backend no distingue dos intentos hechos en una sola invocación ([architecture.md](../architecture.md) §3.2).

Fuentes: [architecture.md](../architecture.md) §3.1-§3.3, [spec-backend-1.md](../../specs/spec-backend-1.md) §2.1 y V-18, [plan-agentes.md](../../specs/plan-agentes.md) §1 y A-5.

## 3. Formato de la story bible

| Opción | A favor | En contra |
|---|---|---|
| Servicios separados: base relacional, índice vectorial y almacén de objetos *(implícita)* | Cada necesidad con su herramienta | Cuatro servicios para una ejecución local de un comprador |
| **SQLite local, un fichero por proyecto (WAL), con capítulos, prompts y exportaciones como ficheros en disco** | Cuatro necesidades sin cuatro servicios; aislamiento por proyecto (RNF-09, V-24); borrar el proyecto es borrar un fichero y un directorio | Un solo escritor a la vez, así que la ejecución es secuencial; habrá que revisarlo con el multiusuario de la fase 3 |
| Texto de capítulo como blobs en la base | Todo en un sitio | Opaco justo para quien orquesta: no se lee con `grep` ni se compara con `diff` |

**Criterios.**
- Legibilidad para la sesión y para la auditoría (C-4).
- Cero servicios que operar.
- Reanudación e idempotencia: escrituras claveadas por `(capítulo, versión, intento)`.
- Historia consultable «a fecha de N−1» (B-2).

**Elección.**
- **SQLite** para lo relacional, lo vectorial y la caché. La biblia guarda historia por capítulo, y el capítulo 0 es el estado de la planificación (B-2).
- **Ficheros en disco** para capítulos, prompts y `export/vN/`. Una versión de novela publicada no se modifica nunca (RF-95).
- El resumen acumulado es **vista derivada**, nunca fuente de verdad: por eso compactarlo es seguro (RF-88).

**Coste.**
- **Cifrado en reposo fuera**, en tensión declarada con C-4 ([architecture.md](../architecture.md) §10).
- **D-1 sigue abierta:** búsqueda con embeddings locales o con FTS5. La v1 devuelve siempre el conjunto vacío detrás de una interfaz estrecha (RF-57).

Fuentes: [architecture.md](../architecture.md) §6, §6.1, §6.2 y §7, [spec-backend-1.md](../../specs/spec-backend-1.md) C-2, C-4 y §6.

## 4. Acceso a la biblia por MCP en tres superficies

| Opción | A favor | En contra |
|---|---|---|
| Endpoints de FastAPI llamados con Bash | Nada nuevo | «Solo el Bibliotecario escribe» dependería de que el agente se porte bien |
| Una superficie MCP con un campo `agente` en la llamada | Sencilla | MCP no transporta la identidad del llamante: sería una convención de prompt disfrazada de mecanismo |
| Superficies separadas, todas en `.mcp.json` | Separación visible | La sesión principal recibe las herramientas de todo `.mcp.json`: el orquestador tendría la escritura |
| **Tres superficies con FastMCP dentro del FastAPI: `/mcp/lectura` en `.mcp.json`; `/mcp/escritura` solo en la definición del Bibliotecario; `/mcp/entrada` solo en la del Extractor y la del Intérprete** | El permiso es configuración verificable (V-13) y hay una segunda barrera en el hook de policy; sin procesos nuevos | Depende de que la carpeta sea de confianza, porque Claude Code no conecta los servidores del frontmatter si no lo es (S-2) |

**Criterios.**
- Que el permiso sea mecanismo y no convención.
- Que el orquestador no vea ni la escritura ni el texto no confiable.
- Un solo proceso escribiendo en SQLite.

**Elección.**
- La tercera fila, con las reglas de la policy en el hook `PreToolUse`: la escritura solo para `agent_type == bibliotecario`, y la entrada solo para el Extractor y el Intérprete.
- Una regla `deny` de la configuración no sirve: se aplica también a los subagentes, y la lista `tools` no la anula.
- La comprobación de que el capítulo esté verificado vive en el backend (RF-106), porque no depende de quién llame.
- Se comprobó con una sonda antes de construir: la sesión principal no puede llamar a un servidor declarado en el frontmatter (S-1).

**Coste.** Un clon nuevo tiene que abrir Claude Code una vez y aceptar la confianza. Si no, el Extractor, el Intérprete y el Bibliotecario no arrancan, y el fallo es ruidoso.

Fuentes: [architecture.md](../architecture.md) §7 y §8, [spec-backend-1.md](../../specs/spec-backend-1.md) D-11 y §5.2, [plan-agentes.md](../../specs/plan-agentes.md) S-1 a S-5 y §5.3.

## 5. Modelo de lectura: web y PDF desde la misma lectura HTML

| Opción | A favor | En contra |
|---|---|---|
| WeasyPrint | PDF desde HTML | Necesita GTK en Windows |
| ReportLab | Control fino | Obliga a maquetar el PDF aparte de la web |
| **`playwright` para Python imprimiendo la misma `lectura.html` con su Chromium; plan B, `channel="msedge"`** | Un solo origen para la web y el PDF; Chromium conserva los enlaces internos del índice y de la página de novedades | Descarga de Chromium; sin navegador, la orden es `error` con causa `pdf_no_disponible` (TC-3) |
| EPUB o DOCX | Formatos editoriales | Fuera del alcance: el producto se lee en web y se descarga en PDF |

**Criterios.**
- Un único modelo de lectura.
- Enlaces internos que funcionen.
- Que funcione en Windows.
- Poder inspeccionar la lectura con Playwright MCP (E-4).

**Elección.**
- **Un modelo escrito dos veces** (TC-7): `lectura.html`, autocontenida, que es la fuente del PDF y de la inspección, y `lectura.json`, que la API sirve a React. El contrato lo propuso el frontend y el backend lo adoptó tal cual.
- **Conversor de Markdown a HTML propio**, para un subconjunto cerrado que escapa todo lo demás.
- **El navegador filtra el HTML otra vez con una lista blanca** y lo pinta como elementos de React, sin `dangerouslySetInnerHTML` (F-6). Es la segunda barrera, porque el texto sale de un modelo que recibió datos no confiables.
- `pypdf`, solo en desarrollo, comprueba los enlaces del PDF.

**Coste.** Dos dependencias nuevas (`playwright` y `pypdf`), añadidas a [architecture.md](../architecture.md) §7.

Fuentes: [plan-entrega.md](../../specs/plan-entrega.md) E-2, [spec-backend-1.md](../../specs/spec-backend-1.md) D-8, [spec-backend-2.md](../../specs/spec-backend-2.md) TC-6 y TC-7, [plan-frontend.md](../../specs/plan-frontend.md) F-3 y F-6.

## 6. Dónde se hace la entrevista

| Opción | A favor | En contra |
|---|---|---|
| Entrevista en la web | Es lo natural para un comprador | Una funcionalidad de frontend entera, y el enunciado no la pide |
| Entrevista hecha por un subagente | Aislado | Un subagente corre hasta terminar sin conversar con el comprador |
| **Skill `/entrevista` en la sesión principal, con el texto libre por fichero** | Es una conversación; el texto libre nunca entra en la ventana del orquestador | La sesión principal pregunta solo las respuestas estructuradas; los datos que faltan los señala el validador, y RF-12 (prioridad S) queda fuera |

**Criterios.**
- Que la entrevista pueda ser una conversación.
- Que el texto no confiable no pase por el orquestador. Si la anécdota se pegase en el chat, E2 dejaría de probar nada.
- Ahorrar trabajo de frontend.

**Elección.**
- **E-3.** La skill conversa las respuestas estructuradas. El comprador guarda el texto libre como `texto_libre*.txt` y `msm.py brief` lo envía sin imprimirlo; la policy deniega leerlo.
- **Revisada en parte el 2026-09-24 (F-10).** La web añade «Nueva novela», un formulario con los mismos bloques que envía el texto libre al backend sin pasar por ninguna sesión.
- La web **no lanza la generación**. `/entrevista` sigue siendo la vía de los briefs de evaluación, que llevan el oráculo y la web no debe leer.

Fuentes: [plan-entrega.md](../../specs/plan-entrega.md) E-3, [plan-agentes.md](../../specs/plan-agentes.md) E-3, [plan-frontend.md](../../specs/plan-frontend.md) F-10, [architecture.md](../architecture.md) §8.

## 7. TLA+ y su relación con el flujo real

| Opción | A favor | En contra |
|---|---|---|
| Solo pruebas de integración (V-14, V-19) | Verifican el código real | Bastaban con un grafo pequeño; con reintentos, reanudación, dos ejecutores y regeneración dejan de cubrir las combinaciones |
| **TLA+ de la función de siguiente orden y de la tabla de transiciones, comprobado con TLC en desarrollo** | Verifica el diseño sobre todas las trazas de un modelo pequeño, con caídas y bloqueo | Es un modelo, no el código: hay que mantener la correspondencia a mano |
| TLC en cada generación *(implícita)* | Comprobación continua | No aporta nada: la especificación no cambia entre novelas |

**Criterios.**
- Verificar la decisión del backend (reduce V-18 a «la sesión ejecuta la orden»).
- Seis invariantes de seguridad y la liveness de [architecture.md](../architecture.md) §3.4.
- Coste de ejecución acotado.

**Elección.**
- **Modelo.** `formal/tla/GrafoNovela.tla` con 5 capítulos, 2 intentos, 2 ciclos de revisión, 1 cambio del lector y dos ejecutores con caídas y caducidad del bloqueo.
- **Correspondencia con el código.** Una tabla une cada acción de la especificación a una rama de `backend/proyecto/` y marca su estado: *igual* o *pendiente* ([plan-formal.md](../../specs/plan-formal.md) §2.4).
- **Configuración de control.** `GrafoNovelaAnterior.cfg` reproduce el diseño anterior a AJ-3 y AJ-4 y **tiene que fallar**: comprueba que el modelo sigue viendo los fallos.
- **Hallazgos.** La revisión de diseño de la sesión formal destapó que los gates por ciclo reutilizaban resultados de una versión anterior y que un ejecutor caído podía duplicar la biblia. De ahí salieron AJ-2 a AJ-6 (I-07 d).

**Coste y límites.**
- Fuera del modelo: la cola y el worker, `error` con causa, el reloj del bloqueo y el contenido de cada capítulo ([plan-formal.md](../../specs/plan-formal.md) §1).
- El registro de contraejemplos de TLC de [plan-formal.md](../../specs/plan-formal.md) §5 aún está vacío.

Fuentes: [architecture.md](../architecture.md) §3.4 y §7, [spec-backend-1.md](../../specs/spec-backend-1.md) V-25, [plan-formal.md](../../specs/plan-formal.md), [validators.md](../validators.md) §6 (model checking).

## 8. Qué invariantes comprueba Lean y por qué esas

| Opción | A favor | En contra |
|---|---|---|
| Heurísticas de continuidad sobre la prosa (diseño de B-9 anterior a R-2) | Detección por capítulo | Frágiles (los pronombres se escapan) y caras de construir; retiradas por R-2 |
| **Tres invariantes sobre la cronología que se genera desde la biblia, con `decide`, como gate de manuscrito** | Decidibles sobre listas finitas, sin Mathlib; deterministas; el informe nombra los eventos implicados | Solo ven lo que el Bibliotecario registró como evento |
| Comparar también edades explícitas | Más cobertura | Aplazado: la v1 no compara edades (TC-2) |

**Criterios.**
- Atacar lo temporal, que ni los deterministas (tras R-2) ni un juez LLM garantizan.
- Que el fallo sea demostrable con un brief de evaluación (E3).
- Coste de comprobación acotado.

**Elección.**
- **Las tres invariantes** de [architecture.md](../architecture.md) §4.2:
  1. Lugar único por personaje y momento.
  2. Nadie aparece tras un evento que lo excluye.
  3. Nadie aparece en un evento fechado antes de nacer.
- **Por qué la exclusión.** Es la que prueba E3. Para que la muerte o la partida de un ser querido contada por el comprador llegue a Lean, hizo falta añadir `excluye` a los hechos de tipo evento (B-18).
- **Momentos en dos escalas** (B-6): los recuerdos como intervalo de días y la historia como `dia-N` más una franja. Solo se compara cuando el orden es seguro.
- **Por qué `decide +kernel`.** Con unos 100 eventos, `decide` agota `maxRecDepth` y `decide +kernel` no. `native_decide` se descartó porque metería el compilador en la base de confianza ([plan-formal.md](../../specs/plan-formal.md) §3.4).

**Coste.**
- Mientras el proyecto Lake no acepte la franja opcional, un evento sin franja se emite como `manana`, lo que puede dar falsos positivos dentro del mismo día (M-14).
- Sin Lean instalado, la orden es `error` con causa `lean_no_disponible`, no un gate rojo (TC-3). En la máquina del backend, las pruebas que ejecutan Lean llevan `skipif` (I-07 b).

Fuentes: [architecture.md](../architecture.md) §4.2, [spec-backend-2.md](../../specs/spec-backend-2.md) R-2, B-6, B-18, TC-1, TC-2 y §4.2, [plan-formal.md](../../specs/plan-formal.md) §3.

## 9. Tope de 100.000 tokens y cómo se cuentan

**El tope.**

| Opción | A favor | En contra |
|---|---|---|
| Usar la ventana entera del modelo | Nada que seleccionar | Un Escritor con la biblia volcada escribe peor y más caro, y el Recuperador sobraría |
| **100.000 tokens de entrada por agente, como disciplina** | Obliga a seleccionar por bloques con un orden de recorte fijo y declarado | Hay capítulos patológicos que no caben ni con la ficha sola (D-9, abierta) |

**Cómo se cuentan.**

| Opción | A favor | En contra |
|---|---|---|
| Endpoint `count_tokens` de la API de Anthropic | Exacto | No hay clave de API (suscripción); mete una llamada de red en el camino crítico y rompe el determinismo |
| Caracteres divididos por una constante | Sin dependencias | Más varianza entre bloques; obligaría a un margen mayor y recortaría capítulos que sí caben |
| `tiktoken` sin corrección | Local | Es el tokenizador de OpenAI e infracuenta a Claude entre un 15 y un 20 %, y más en español |
| **`tiktoken` `o200k_base` × 1,35, con el factor dentro del estimador** | El error pasa a ser siempre por exceso; el tope sigue siendo el único número normativo | Es un estimador, no un contador: RNF-05 promete el tope *estimado* |

**Criterios.**
- Contar antes de enviar.
- Determinismo byte a byte.
- Que el error vaya siempre por exceso.
- Que funcione sin red.

**Elección.**
- **D-5.** El factor es una constante de un módulo con interfaz estrecha: entra texto, sale un entero.
- **El BPE se versiona** en el repositorio y se marca como binario, porque `core.autocrlf` rompía su SHA-256 (I-01 b).
- **Respaldo en Python puro** sobre el mismo fichero cuando la DLL nativa no carga (M-10, I-07 a).
- **Prompt partido.** El prompt se guarda en partes de 20.000 tokens como mucho, porque `Read` corta hacia los 25.000.
- **Dónde se hace cumplir.** En el Escritor; en el resto de agentes queda acotado por construcción, como riesgo aceptado ([spec-backend-2.md](../../specs/spec-backend-2.md) §3.12).

**Coste.** Nulo en el caso normal: 100.000 ÷ 1,35 ≈ 74k tokens efectivos, frente a los ~43k que suman los tamaños esperados de los bloques.

Fuentes: [CLAUDE.md](../../CLAUDE.md), [architecture.md](../architecture.md) §6.3, [spec-backend-1.md](../../specs/spec-backend-1.md) RF-51 a RF-54, RF-52a a RF-52c, D-5 y D-9.

## 10. Guardarraíl de palabras prohibidas

| Opción | A favor | En contra |
|---|---|---|
| Confiar en el prompt del Escritor o en un juez *(implícita)* | Sin código | No es determinista ni verificable, y un veto del comprador no admite «casi siempre» |
| Clasificador de contenido | Detecta por sentido | Exigiría una dependencia fuera de la tabla de §7 (C-7): fase 2 |
| **Listas en ficheros versionados, copiadas a SQLite con su hash, y comparación con un normalizador propio** | Determinista, sin dependencias y auditable | Solo detecta términos listados y sus variantes sencillas |

**Criterios.**
- Obligatorio en la entrega.
- Determinista y sin modelo.
- Una auditoría que no guarde el término literal.
- Vetos del comprador por novela.

**Elección.**
- **Tres listas:**
  - Global.
  - Por público: la infantil lleva violencia explícita, sexo y drogas; la juvenil y la adulta van vacías en la v1.
  - Por novela: los vetos se materializan al salir de `contexto`.
- **Normalización (B-11):** minúsculas, sin tildes ni diéresis, conservando la ñ, con variantes de género y número en palabras de 4 letras o más y comparación por palabras enteras.
- **La auditoría** guarda el id de la palabra y el offset (B-12).
- **Por qué detiene la generación.** Es bloqueante y, a diferencia del resto, al agotar los intentos detiene la generación (RF-72a): «un capítulo con un veto del comprador no puede quedar en la novela ni siquiera marcado».

**Coste.** Las listas las redactó el backend y la persona las revisa cuando pueda (B-12): no bloquea.

Fuentes: [architecture.md](../architecture.md) §4.3, [spec-backend-1.md](../../specs/spec-backend-1.md) RF-72a y §1.2, [spec-backend-2.md](../../specs/spec-backend-2.md) B-11, B-12 y M-11.

## 11. Suscripción y nunca API de pago

| Opción | A favor | En contra |
|---|---|---|
| Cliente de API en el backend | Control de modelos y tokens exactos | Gasto medido aparte de la suscripción: descartado |
| `claude -p --bare` en el worker | Arranque mínimo | Lee una clave de API en vez de la suscripción, y además no carga hooks ni MCP |
| **Subagentes de Claude Code con la suscripción, y un worker que lanza `claude -p "/regenerar …" --permission-prompts none --output-format json`** | Sin cliente de modelo en `backend/` (RNF-10, verificado por análisis estático, V-9); el backend lanza un proceso | No hay control de coste por token: se controla eligiendo el modelo por adelantado; las métricas van en tokens y tiempo, nunca en dinero (F-11) |

**Criterios.** Restricción de presupuesto, determinismo del Recuperador (no hay red en el camino crítico) y ninguna dependencia de proveedor.

**Elección.**
- **Nunca `--bare`**, y el proceso hijo no hereda `ANTHROPIC_API_KEY` (M-19).
- **`ruff` prohíbe importar clientes de proveedor** con TID251 (V-9).
- **Embeddings.** Si D-1 elige embeddings, tendrán que correr en local por la misma razón ([architecture.md](../architecture.md) §6).

**Coste.**
- Los límites de la suscripción acotan cuántas novelas se pueden generar para las evaluaciones (E-7).
- La prueba real de `claude -p` es manual (TC-10).

Fuentes: [architecture.md](../architecture.md) §6.3, §7, §8 y §10, [spec-backend-1.md](../../specs/spec-backend-1.md) RNF-10, [spec-backend-2.md](../../specs/spec-backend-2.md) TC-10 y M-19, [plan-entrega.md](../../specs/plan-entrega.md) H6.

## 12. Retirada de cosmic-ray: V-15 por regla

| Opción | A favor | En contra |
|---|---|---|
| `mutmut` | Pruebas de mutación | La versión 3 no funciona en Windows sin WSL (I-01 a) |
| `cosmic-ray` | Funciona en Windows | En Windows, un fallo de decodificación entre cp1252 y UTF-8 daba 190 de 498 mutantes como INCOMPETENT cuando estaban eliminados (I-02 a); además, ejecuta la batería entera por cada mutante, y no compensaba el tiempo hasta la entrega |
| **Cobertura por regla** | Cada regla del validador y de cada verificador tiene una prueba que la dispara y otra de control que no; es barata | Mide menos que la mutación: no detecta aserciones débiles dentro de una prueba que sí dispara |

**Criterios.** Tiempo disponible hasta la entrega, y que funcione en la máquina de desarrollo.

**Elección.** R-5 (I-03). Se quitaron la dependencia y `cosmic-ray.toml`. Se conservan la guarda simplificada y las pruebas de límite que la mutación había destapado (I-02 b).

Fuentes: [spec-backend-2.md](../../specs/spec-backend-2.md) R-5, [iteraciones.md](../iteraciones.md) I-01 a I-03, [spec-backend-1.md](../../specs/spec-backend-1.md) V-15 y D-7.

## 13. Recortes R-1 a R-3

Los tres responden al mismo criterio: **llegar a la entrega con lo obligatorio verificado**, quitando piezas cuyo trabajo ya cubre otra.

| Recorte | Opciones | Elección y coste |
|---|---|---|
| **R-1 · Planificación en un agente** | Cuatro agentes (Arquitecto, Personajes, Mundo, Estilo) más el Escaletista, o un `planificador` más el Escaletista | Uno solo, con una salida JSON que se valida contra los modelos del contexto extendidos (B-4). Quedan 12 agentes y una sola orden en `planificacion`. Coste: una salida más grande y un solo punto de fallo en la planificación. Aprobado por la persona |
| **R-2 · Continuidad sin heurísticas sobre la prosa** | Reglas sobre el texto (nombres o alias de personajes excluidos, verbos de posesión, B-9) o solo comprobaciones antes de escribir | Solo antes de escribir: presentes excluidos a fecha N−1 y tiempos de viaje (RF-74 a RF-76). La prosa la miran el juez de capítulo y Lean. Coste declarado en V-17 (**U**): los deterministas no detectan toda incoherencia |
| **R-3 · Sin verificador de Repeticiones** | Verificador determinista (E-5, B-13) o dejarlo al Editor de estilo | Al Editor de estilo. E-5 queda rechazada y B-13 anulada. Coste: la prosa repetitiva no tiene regla determinista |

Fuentes: [spec-backend-2.md](../../specs/spec-backend-2.md) §0, [plan-entrega.md](../../specs/plan-entrega.md) E-5, [spec-backend-1.md](../../specs/spec-backend-1.md) V-17.

## 14. Observabilidad con Langfuse (E-1 / D-3)

**Estado: cerrada el 2026-09-24** con la recomendación de E-1, y dos precisiones que salieron al construirla ([iteraciones.md](../iteraciones.md) I-09).

| Opción | A favor | En contra |
|---|---|---|
| Langfuse alojado por uno mismo | Los datos no salen | Exige Postgres, ClickHouse, Redis y S3 en Docker |
| Plugin de usuario `langfuse-observability` | Ya estaba instalado | Envía hasta 20.000 caracteres de cada entrada y salida: capítulos y la anécdota del comprador (S-8) |
| **Recomendación de E-1: Langfuse Cloud, solo metadatos, y el backend como único emisor** | Sin texto no sale nada personal; el backend sabe qué orden, agente, capítulo y verificador hay detrás de cada dato | El formato del transcript del que salen los tokens no está documentado; con suscripción, el coste es una estimación |
| No integrar Langfuse | Sin trabajo ni dependencia | Sin trazas externas; la tabla de evaluaciones sale de los metadatos que ya guarda la base |
| Solo el MCP de Langfuse | Ninguna dependencia nueva | No tiene herramientas para crear trazas, spans ni uso de tokens: solo consulta, prompts y scores sobre trazas ya existentes |

**Cómo se envía.** Con el SDK `langfuse`, con la API de ingesta por lotes o con el endpoint OpenTelemetry. Se elige **OTLP en JSON con `httpx`**, que ya estaba en el lock: la ingesta por lotes está obsoleta y deja de aceptar trazas el 2026-11-16, y el SDK instrumenta con OpenTelemetry global, mientras que aquí se quieren identificadores deterministas. Reenviar con el mismo id **duplica** en Langfuse (se comprobó: I-09), así que cada proyecto guarda lo ya enviado y cada span sale una vez.

**Criterios.**
- Los datos de un tercero se quedan en local ([architecture.md](../architecture.md) §10).
- Coste de operación.
- Que la integración se pueda recortar sin perder datos.

**Lo que ya está hecho**, y no depende de la decisión:
- El plugin de usuario está **desactivado** en este proyecto (`enabledPlugins` en `.claude/settings.json`, E-1 d).
- El hook `SubagentStop` anota los tokens y la versión de prompt de cada subagente, y el backend los guarda en los `metadatos` de la orden (P-6).
- La ventana de métricas los agrega (`GET /proyectos/{id}/metricas`).

**Lo que se construyó:** `backend/observabilidad/`, que lee la base y envía trazas, scores y versiones de prompt tras cada `/resultado`. El coste es que la correspondencia con el formato de Langfuse la mantenemos nosotros, y que la prueba de centinela es lo que garantiza que no sale texto.

Fuentes: [plan-entrega.md](../../specs/plan-entrega.md) E-1, [plan-agentes.md](../../specs/plan-agentes.md) E-1 y S-8, [spec-backend-2.md](../../specs/spec-backend-2.md) §0, [spec-backend-1.md](../../specs/spec-backend-1.md) D-3.

## 15. Otras decisiones con coste visible

| Decisión | Opciones | Elección | Coste |
|---|---|---|---|
| **TC-5 · Umbral del juez de manuscrito** | «≥3 en todos y media ≥ 3,5», o «suma ≥ 18 y ninguno por debajo de 3» | La suma: con cinco notas enteras es equivalente, pero se puede probar en la frontera con sumas de 17 y 18 (I-06 a) | Ninguno; es la misma regla escrita de forma comprobable |
| **R-4 · Reintentos del worker** | Hasta 3 lanzamientos con espera (TC-9) o uno solo | Uno: si `claude -p` falla, el trabajo queda `fallido`, el proyecto vuelve a `publicada` con el cambio fallido y se vuelve a encolar a mano | Un fallo transitorio exige intervención humana |
| **Generar desde la web** | Copiar `/generar <proyecto>` a una sesión de Claude Code, o un botón que encola la generación en la cola del worker | El botón, reutilizando la cola, el worker y `/regenerar`: sin skill ni proceso nuevos. `/generar` sigue valiendo | Sin terminal no se ve el progreso fino, solo el seguimiento web; una novela entera ocupa el worker horas y las regeneraciones de otros proyectos esperan detrás |
| **Paradas humanas** | Activas por defecto o desactivadas | Desactivadas por defecto: para un regalo, el punto de control natural es leer y pedir cambios. Activas, no tienen salida automática (RF-05) | El comprador no revisa el plan salvo que lo pida |
| **Organización del código** | Capas horizontales (`routers/`, `models/`, `services/`), vertical slices o FSD en el frontend | Una carpeta por fase de §2 en el backend (con `proyecto/` y `mcp/` como excepciones escritas) y package by feature en el frontend, sin FSD | `shared/` hay que mantenerlo pequeño a la fuerza: se promueve algo cuando lo pide el tercer sitio |
| **D-9 · Prompt que no cabe ni con la ficha sola** | Truncar, subir el tope o fallar | **Abierta.** Mientras tanto, la orden es `error` con causa `no_cabe` y no se envía nada | Falla de forma ruidosa, a propósito |

Fuentes: [spec-backend-2.md](../../specs/spec-backend-2.md) TC-5, TC-9 y R-4, [architecture.md](../architecture.md) §3.3, §6.3 y §8, [spec-backend-1.md](../../specs/spec-backend-1.md) D-9.
