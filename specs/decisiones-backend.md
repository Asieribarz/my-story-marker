# decisiones-backend.md — Decisiones de los tramos B y C del backend

> **Estado: decidido (2026-09-23).** La persona pidió que las decisiones del backend se tomen con la recomendación de la sesión de backend, sin ronda de preguntas (AGENTS.md, regla 1, excepción explícita). Salen de la preparación de los tramos B (pasos 4 a 8) y C (pasos 8a a 10) de [plan-backend-v1.md](plan-backend-v1.md).
>
> Son **premisas de construcción**, no documentación de lo hecho: `docs/` se actualiza cuando el código las aplica (regla 3). Si una de estas decisiones contradice `docs/`, manda esta hasta que el código la aplique y `docs/` la recoja. Las sesiones de agentes, formal y frontend leen aquí sus contratos (§4).

---

## 0. Recortes (2026-09-23, por la entrega)

Mandan sobre lo que digan las secciones siguientes.

| # | Recorte | Qué cambia |
|---|---|---|
| **R-1** | **La planificación usa dos agentes:** `planificador` (sonnet, `/mcp/lectura`), que en una sola salida JSON produce el plan estructural, los personajes, el mundo y la guía de estilo, y `escaletista`, que no cambia. Aprobado por la persona. | Desaparecen `arquitecto`, `personajes`, `mundo` y `estilo`: quedan 12 agentes. B-3 y B-4 describen las partes de la salida del planificador. En `planificacion` hay una sola orden. |
| **R-2** | **Continuidad sin heurísticas sobre la prosa.** | B-9 se queda solo con las comprobaciones previas a la escritura (ficha y biblia a fecha N−1, y RF-76 con los días); las reglas de RF-74 y RF-75 sobre el texto no se construyen. B-10 se queda solo con la regla de grafía de los términos conocidos. La continuidad del texto la cubren el juez de capítulo y Lean; se declara en V-17. Los eventos que vienen del contexto (`capitulo` NULL, B-18) cuentan como capítulo 0. Quien solo sale en un recuerdo o una analepsis va en `mencionados`, no en `presentes`, y no se bloquea. Si el Escritor lo hace actuar en el presente de todos modos, el Bibliotecario lo registra en un evento de `dia-N` y lo detecta Lean. |
| **R-3** | **Sin verificador de Repeticiones.** | B-13 queda anulada: E-5 se rechaza, y las repeticiones las vigila el Editor de estilo. |
| **R-4** | **El worker lanza una sola vez.** | TC-9 se simplifica: si `claude -p` falla, se cuelga o muere, el trabajo queda `fallido` y el proyecto vuelve a `publicada` con el cambio fallido; se vuelve a encolar a mano. Se mantienen el tiempo máximo y la reanudación de un trabajo `en_curso` al arrancar. La arista `regeneracion → publicada` con causa `worker_fallido` entra en la tabla de transiciones y en TLA+. |
| **R-5** | **Sin cosmic-ray.** | V-15 pasa a ser una comprobación de cobertura por regla: cada regla del validador, y después cada verificador, tiene al menos una prueba que la dispara y otra de control que no. Se quitan la dependencia, `cosmic-ray.toml` y sus menciones en los documentos. |
| **R-6** | **No se crean más ficheros de spec** para el backend. | Las decisiones nuevas van aquí; las actualizaciones de `docs/` al cerrar cada bloque son breves. |

Pendiente de la persona: Langfuse (E-1), que se recorta si el enunciado no lo exige expresamente.

---

## 1. Tramo B · pasos 4 a 8

| # | Decisión | Paso |
|---|---|---|
| **B-1** | **Manda el contexto validado.** Los planificadores añaden, no cambian: pueden crear personajes ficticios o localizaciones `micro`, pero no quitar ni cambiar `id`, `origen`, `rol` ni `arco` de lo que ya fija el contexto; si lo contradicen, su salida es inválida (RF-77a). Al salir de `contexto`, el backend materializa `personalizacion`, `hecho`, los `evento` que vienen de hechos de tipo evento (con `capitulo` NULL) y los vetos en `palabra_prohibida` con nivel `novela`. Para que las claves ajenas de `evento.lugar` y `evento.excluye` existan, materializa **antes** los `personaje` (el destinatario y los hechos `ser_querido`) y las `localizacion` que ya fija el contexto; `excluye.fuente` se traduce al id de ese personaje. | 4 |
| **B-2** | **La biblia guarda historia por capítulo.** Cada fila que cambia lleva el `capitulo` desde el que vale (estado de personaje, lo que sabe, estado de localización, glosario), como ya hace `inventario`. Toda consulta es «a fecha de N−1»: la última fila con capítulo menor que N. El estado inicial de la planificación es el capítulo 0. Así una regeneración del capítulo 5 ve el mundo del capítulo 4, y un cambio fallido se deshace. | 4, 6, 8 |
| **B-3** | **Catálogo único de hitos** para los tres modelos: `detonante`, `primer_umbral`, `punto_medio`, `crisis`, `climax`. Los tres últimos se copian del contexto; el Arquitecto sitúa los dos primeros dentro del planteamiento. `ficha_capitulo.hito` pasa a una tabla `ficha_capitulo_hito`: un capítulo puede tener varios hitos. | 4 |
| **B-4** | **Las salidas de Personajes, Mundo y Estilo extienden los modelos del contexto** (una sola fuente de tipos, D-4). Personajes añade `nombre`, `alias[]`, `estado_inicial`, `sabe[]`, `relaciones[]`; el nombre de un personaje real tiene que coincidir con el del destinatario o aparecer literal en su hecho. Mundo añade `nombre`, `descripcion` (con tope) e `hito` por localización, y `objetos[]` con su poseedor inicial (inventario en el capítulo 0). Estilo añade `metricas {frase_media_palabras, proporcion_dialogo, descriptivo, legibilidad_min}`, léxico, lista negra (que incluye siempre `lenguaje.prohibidas`), onomástica y ejemplos con tope. Nombres y alias siembran el glosario. | 4 |
| **B-5** | **Ficha de capítulo ampliada:** `numero, hitos[], objetivo, escenas[{tipo, texto}], pov, localizacion, presentes[], mencionados[], dia, tension, palabras_objetivo, cierre, plantar[{clave, descripcion}], cobrar[clave], hechos[], traspasos[{objeto, a}]`. `tension` y `cierre` deben coincidir con el contexto. RF-41: los capítulos de cada acto difieren de 10·p/100 en menos de 1 (con 22/55/23, 2/6/2); la comprobación también corre al validar el contexto. Aviso si un hecho obligatorio no está en ninguna ficha. | 4 |
| **B-6** | **Dos escalas de tiempo.** La acción de la novela va en días enteros `D1…Dn`: la ficha trae el día previsto y el Bibliotecario registra `dia_fin` y `localizacion_fin` de cada capítulo. Los recuerdos del comprador van en fecha parcial o periodo, y todos son anteriores a `D1`. | 4, 7, 8, 8a |
| **B-7** | **Contrato con la sesión de agentes:** ver §4.1. | 5, 6, 7 |
| **B-8** | **Bloques del Recuperador.** Vacío en un bloque obligatorio (ficha, guía, fichas de presentes, localización) es error; en uno opcional (presagios e inventario, resumen, capítulo anterior, reglas) se emite el encabezado con la línea fija «Ninguno.», que no cuenta como recorte. Si N−1 no está aprobado, se usa el último aprobado y una frase fija lo avisa. Bloque nuevo **«Informe del intento anterior»**, prioridad 2, ~1k, se recorta entero. Vetos, frases literales y lista negra van dentro del bloque de la ficha, que nunca se recorta; el estado de los presentes va en el bloque de presagios e inventario. Los tamaños esperados son constantes informativas en unidades del estimador. | 6 |
| **B-9** | **Continuidad dura en dos niveles.** Antes de escribir (Recuperador y registro de la escaleta; aborta sin gastar intento): presentes excluidos a fecha N−1, y todo RF-76 con los días de la ficha y los `dias_viaje` de la ruta. Sobre el texto, severidad alta: RF-74 (un nombre o alias ligado a un personaje que no está en `presentes ∪ mencionados` y que a N−1 está excluido o en otro sitio) y RF-75 (objeto, no poseedor y verbo de posesión de lista cerrada en la misma frase, sin traspaso previo ni en la ficha). Los pronombres escapan: riesgo aceptado en V-17. | 6, 7 |
| **B-10** | **Nombres propios por heurística** (mayúscula fuera de inicio de frase, unidas por `de`, `del`, `la`, `los`, `y`), con dos reglas en severidad media: grafía distinta de un término conocido, y término desconocido. El glosario gana `referencia` (id de personaje, lugar u objeto) y `tipo` (canónico o alias). | 4, 7 |
| **B-11** | **Normalización:** minúsculas, sin tildes ni diéresis, **conservando la ñ**; cada término se expande a sus variantes de género y número (-s, -es, z→ces, -o/-a/-os/-as); se compara por palabras enteras. La lista negra usa el mismo normalizador. Las frases literales (RF-73a) no: solo se unifican Unicode, espacios y comillas o apóstrofos tipográficos. | 7 |
| **B-12** | **Listas del guardarraíl** como ficheros versionados en `backend/capitulo/`, copiados a la base al crear el proyecto, con su hash. Global de 100 a 200 términos en español de España; infantil con violencia explícita, sexo y drogas; juvenil y adulto vacías en la v1; la de novela, con `vetos.palabras` y `vetos.temas`. Las redacta el backend y **la persona las revisa cuando pueda** (no bloquea). La auditoría guarda capítulo, versión, intento, nivel, id de la palabra y offset, **sin el término literal**. Agotar intentos cuenta como «agotado por el guardarraíl» solo si el intento que agota tiene algún hallazgo del guardarraíl. | 7 |
| **B-13** | **E-5 aceptada:** verificador de Repeticiones en severidad **baja** (la misma palabra de contenido de 4+ letras 3 veces en un párrafo o en 50 palabras; tres frases seguidas con la misma primera palabra). Umbrales como constantes. RF y V nuevos en spec1. | 7 |
| **B-14** | **Un solo módulo de segmentación** (párrafo, frase con lista de abreviaturas, palabra, diálogo según la convención del contexto); localización de hallazgos `p<n>:<offset>`. Métricas: baja hasta dos veces la tolerancia, media por encima; legibilidad bajo el mínimo, media. `crossover` usa el umbral juvenil (55); sin tolerancia, 10 %, declarado. `Informe` gana un campo opcional `metricas` para la desviación de RF-79. **Párrafo** = bloque de texto del Markdown del capítulo separado por una línea en blanco, sin contar el título ni el separador de escena. `p<n>` del backend, `data-p` del frontend y `parrafo` del juez numeran esos mismos bloques, desde 1. | 7 |
| **B-15** | **Juez de capítulo por criterio:** `{criterio, cumple, hallazgos[{parrafo, cita, motivo}]}`; la severidad la pone el backend según architecture §4. Salida inválida si una cita no aparece en el texto o si `cumple` no cuadra con los hallazgos. Se añade el criterio **`contenido`** (alta), que corrige spec1 §1.2: nada más mira el texto contra el público. | 7 |
| **B-16** | **Bibliotecario idempotente:** cada escritura se etiqueta con el capítulo de la **orden vigente**, no con un argumento; al emitir una orden de Bibliotecario se borra lo escrito antes para ese capítulo. Los presagios nacen de `ficha.plantar` al registrar la escaleta; el Bibliotecario los confirma o los cierra por clave, y puede abrir uno no previsto. Al registrar su resultado, el backend comprueba que están el resumen, `dia_fin`, `localizacion_fin` y, si cierra acto, el resumen de acto; si falta algo, intento fallido. | 8 |
| **B-18** | **Un hecho `evento` puede declarar a quién excluye:** campo opcional `excluye {fuente, tipo: muerte\|partida}`, donde `fuente` es el id del hecho `ser_querido` o `destinatario`. Al salir de `contexto`, la materialización de B-1 lo lleva a `evento.excluye` y a `tipo_exclusion`. Sin esto, la muerte de un ser querido contada por el comprador nunca llega a Lean, y E3 no demuestra nada. Es un cambio aditivo de la ontología: definitions §9, `contexto/modelos.py` y su validación (el `excluye` apunta a una fuente que existe). | 4 |
| **B-19** | **Preferencias del comprador en la entrevista:** `tono`, `subgenero`, `cronologia` y `final`, más `publico` solo para bajarlo (definitions §10). Van en `respuestas.preferencias` del brief y las traduce el Agente de Contexto. Se añaden a definitions §9. Los briefs de evaluación son JSON, no YAML (se corrige plan-entrega H0). | docs |
| **B-17** | **El Bibliotecario del último capítulo de un acto escribe el resumen del acto**, sin estado nuevo. Topes en la herramienta: 240 palabras por capítulo y 360 por acto. Regenerar un capítulo de un acto cerrado reescribe también su resumen de acto. | 4, 8 |

---

## 2. Tramo C · pasos 8a a 10

| # | Decisión | Paso |
|---|---|---|
| **TC-1** | **Contrato del fichero Lean** (§4.2). Lo implementa la sesión formal; el backend lo genera. | 8a |
| **TC-2** | Igual que B-6. La invariante 3 queda como «nadie aparece en un evento fechado antes de nacer»; la v1 no compara edades explícitas, y se dice en spec1. | 8, 8a |
| **TC-3** | **Si falta una herramienta** (Lean, Chromium), la siguiente orden es `error` con causa (`lean_no_disponible`, `pdf_no_disponible`), que generaliza `error_ensamblado`: el estado no cambia, no gasta ciclo de revisión y no va al Revisor. Las pruebas que ejecutan la herramienta real llevan `skipif`. | 8a, 9 |
| **TC-4** | **Los gates los ejecuta el backend** al calcular la siguiente orden en `verificacion_manuscrito`: cobertura y Lean, y después la orden del juez de manuscrito; se guardan por versión en curso y ciclo, así que repetir no hace daño. **Los tres gates corren en cada ciclo** y el Revisor recibe un informe conjunto. En `publicacion`, se publica al registrar el resultado del Exportador. | 8a, 9 |
| **TC-5** | Umbral del juez de manuscrito en enteros: **suma ≥ 18 y ningún criterio por debajo de 3** (la media 3,5 no es alcanzable con cinco enteros). V-32 se prueba con sumas 17 y 18. Los cinco criterios son un enum cerrado. | 8a |
| **TC-6** | **E-2 / D-8: PDF con Playwright para Python** imprimiendo la misma lectura HTML, con el Chromium de Playwright (`uv run playwright install --only-shell chromium`); plan B escrito: `channel="msedge"`. `pypdf` en desarrollo para comprobar los enlaces internos. Dependencias nuevas: `playwright` y `pypdf`, a architecture §7, AGENTS.md y spec1 §10. | 9 |
| **TC-7** | **Lectura en disco:** un único modelo escrito dos veces, `lectura.html` autocontenido (anclas `#cap-NN`, CSS dentro; fuente del PDF e inspección con Playwright MCP) y `lectura.json` (estructura y un fragmento HTML por capítulo; lo sirve la API a React). Conversor Markdown → HTML propio de un subconjunto cerrado que escapa todo lo demás. `export/vN/` guarda `manuscrito.md`, `metadatos.json`, `lectura.html`, `lectura.json`, `novela.pdf` y `cronologia.lean`, con los nombres en `shared/rutas.py`. | 9 |
| **TC-8** | **Un trabajo es «orquestar este proyecto hasta la próxima parada».** Se encola al pedir un cambio (termina en `esperar_humano`) y al confirmarlo (termina en `publicada`). El worker procesa un trabajo cada vez, el más antiguo de todos los proyectos, y lanza `/regenerar <proyecto> <trabajo>`. Tabla nueva `cambio_capitulo` con los capítulos afectados calculados al confirmar (V-31). | 9a |
| **TC-9** | **Si `claude -p` falla, se cuelga o muere:** hasta 3 lanzamientos con tiempo máximo y espera; agotados, trabajo `fallido` y proyecto a `publicada` con el cambio fallido; con el bloqueo tomado no se lanza; un trabajo `en_curso` al arrancar se reanuda. El worker es un hilo del `lifespan` con `subprocess` síncrono, desactivable en las pruebas. | 9a |
| **TC-10** | **El worker se prueba con un `claude` falso** (un script de Python lanzado con `sys.executable`) que simula éxito, error, cuelgue, caída y bloqueo ocupado. El comando es configurable y por defecto `shutil.which("claude")`. Lanzamiento con `--permission-prompts none` y `--output-format json`, nunca `--bare`; como argumentos solo el id hexadecimal y un entero. **La prueba real de `claude -p` es manual** y la hace la persona. | 9a |
| **TC-11** | **Modelo de error:** se mantiene el del paso 3, `{codigo, requisito, detalle}`, con el catálogo de códigos como `StrEnum` en un solo sitio. Una salida de subagente fuera de esquema no es error HTTP: responde 200 y cuenta como intento fallido (RF-77a). Un contexto con hallazgos tampoco: se devuelve el informe. | 3, 10 |
| **TC-12** | **El paso 10** aplica el modelo de error a todo, añade las rutas que faltan (paradas, `GET /cambios/{c}`, manuscrito vigente y sus informes antes de publicar) y retira las duplicadas (§3, puntos 5 y 6). | 10 |

### 2.1 Ajustes al cerebro de fases (`proyecto/`), del bloque 1

El bloque 1 se lanzó antes de estas decisiones. Se aplican al empezar el bloque 2; AJ-6, en el bloque 3. AJ-2 a AJ-6 salen de la revisión de diseño de la sesión formal, y TLC los comprobará.

| # | Ajuste |
|---|---|
| **AJ-1** | R-1: en `planificacion` hay una sola orden, la del `planificador`, y la lista de agentes pasa a 12. |
| **AJ-2** | §3, punto 7: en `revision`, por cada capítulo, Revisor → deterministas → Bibliotecario. El Bibliotecario entra en los agentes de `revision`, con su propio desenlace; no usa el del bucle de capítulos. |
| **AJ-3** | **Pasadas de verificación.** `proyecto.pasadas` suma 1 cada vez que se entra en `verificacion_manuscrito` y nunca se pone a cero. Los gates de TC-4 se guardan por pasada, no por ciclo: las notas de `aprobacion_final` y el «reintentar» ponen a cero o repiten el ciclo, y reutilizarían cobertura y Lean de una versión anterior. |
| **AJ-4** | **El sello lleva la generación del bloqueo.** `proyecto.generacion_bloqueo` suma 1 cada vez que toma el bloqueo un titular distinto o uno que ya había caducado. El sello de la orden es `<proyecto>:<orden>:<generación>`, opaco salvo el primer segmento, que es el proyecto. Cuando se toma el bloqueo con una orden vigente, la orden se vuelve a sellar: si es del Bibliotecario, se borra lo escrito para su capítulo (B-16); si es del Extractor o del Intérprete, se emite un identificador nuevo y el anterior queda invalidado. Se rechazan los resultados y las escrituras MCP con un sello viejo; las herramientas de `/mcp/escritura` reciben el sello como argumento. Así, un ejecutor caído no duplica la biblia ni gasta un intento con un identificador ya canjeado. |
| **AJ-5** | TC-3: la decisión `error` con causa sustituye a `error_ensamblado`, y D-9 pasa a ser una causa más. |
| **AJ-6** | **Paso 9a.** Confirmar un cambio reabre los capítulos afectados (`cambio_capitulo`): versión nueva, estado `pendiente` y contadores a cero. Si el cambio falla, se restauran los punteros de la versión N, se deshace el hecho (`valor_anterior`) y sus capítulos salen de `revision_humana`, para que el cambio siguiente pueda empezar. |

### 2.2 Decisiones sobre la marcha del bloque 2 (2026-09-23, R-6)

Las tomaron las piezas al construir los pasos 4 a 8. Van resumidas; el detalle está en el código.

| # | Pieza | Decisión |
|---|---|---|
| **M-1** | Base | La historia de la biblia va por capítulo, no por versión. `personaje_sabe` es un dato por fila y se acumula; los estados de personaje y de localización son la última fila anterior a N. El estado del presagio va en la tabla de historia `presagio_estado`. `evento` separa `momento` (recuerdo) de `dia` + `franja` (historia) con un CHECK de exactamente uno. Hay un `informe` por (versión, verificador). `resumen` guarda qué versión lo escribió. |
| **M-2** | Base | La guarda de V-19 vive en las escrituras de `capitulo/biblia.py`. El Bibliotecario no crea objetos, solo registra traspasos. `antes_de` va de 1 a 11, y 11 es la novela entera. |
| **M-3** | Cerebro | Estados de §3.2 en el código: Editor en verde → `editado`; juez en verde → `verificado`; Bibliotecario aceptado → `aprobado`, que actualiza `capitulo.version_vigente`. |
| **M-4** | Cerebro | El sello no sale en `GET /estado`. La generación sube en cada toma del bloqueo y la renovación no la cambia. La huella de reenvío es el SHA-256 de `salida_cruda`. Los metadatos desconocidos se ignoran. |
| **M-5** | Cerebro | Extracción: un solo bloque JSON (con ```` ```json ```` o sin lenguaje, o el texto entero si es JSON); dos bloques son un fallo de forma. El Markdown exige `# título` en la primera línea. El sello repetido por el modelo se quita sin compararlo. |
| **M-6** | Cerebro | Los capítulos que van a revisión salen de `gate_resultado.detalle.capitulos` con `ok = 0` en la pasada en curso: es el contrato con el bloque 3. Nunca hay Revisor sin capítulo (M-25). |
| **M-7** | Cerebro | La orden del Escritor lleva `entrada.version` (`version_vigente + 1`), `entrada.intento`, `rutas_prompt` absolutas y `tokens_estimados`. `/auditoria` no exige el token del bloqueo, porque el hook no lo lleva. «cambios» sin notas en una parada es 422. Un canje de `/mcp/entrada` con identificador mal formado o de un proyecto inexistente no se registra, porque no hay base donde escribirlo. |
| **M-8** | Planificación | Los avisos del escaletista (hecho obligatorio sin ficha) van en `Salida.detalle["avisos"]`, con severidad media; no rechazan. |
| **M-9** | Recuperador | Orden de bloques: ficha → informe anterior → guía → presagios e inventario → presentes → localización y reglas → resumen → capítulo anterior → pasajes; a igual prioridad se recorta antes el informe. La lista negra va en la ficha y se quita de la guía. Si hay recortes, el prompt termina con «## Omitido por espacio». Las partes se cortan por párrafo, luego por línea, y su concatenación es el fichero completo. El desglose lleva el sha256 y el motor del estimador. |
| **M-10** | Recuperador | Respaldo del estimador: si la DLL de `tiktoken` no carga (política de la máquina), un BPE en Python puro sobre el mismo `o200k_base` versionado, con pre-tokenización hecha con `re`. Reproduce los ids de o200k; un pre-token de más de 256 bytes cuenta un token por byte, que es una cota superior. |
| **M-11** | Verificadores | Hash de las listas del guardarraíl en la tabla `lista_guardarrail`, con copia perezosa en la primera verificación. El crossover usa la lista juvenil. Longitud: dos reglas medias, `fuera_de_rango` y `lejos_del_objetivo`. Métricas: el diálogo se mide en puntos, y la legibilidad mínima es el máximo entre la de la guía y el umbral del público. Las variantes de B-11 se aplican solo a palabras de 4 letras o más. El hallazgo de una frase literal nombra el hecho, sin copiar la frase. |
| **M-12** | MCP | La lectura recibe `proyecto` como argumento (vale también el sello entero); la escritura lo saca del sello y exige que la orden vigente sea del Bibliotecario y tenga capítulo. En `llamada_mcp` se guarda `<superficie>.<herramienta>`; de los campos de texto, solo el tamaño; nunca el sello. `escribir_resumen_capitulo` registra a la vez el resumen, `dia_fin` y `localizacion_fin`. |

### 2.3 Decisiones sobre la marcha del bloque 3 (2026-09-24, R-6)

| # | Pieza | Decisión |
|---|---|---|
| **M-13** | Gates | Detalle de `gate_resultado`: siempre `capitulos`. Cobertura añade `sin_uso` y `por_hecho`; Lean añade `eventos`, `violaciones` y `fichero`; el juez añade `puntuaciones`, `suma` y `evaluacion`. Cobertura y Lean se evalúan una sola vez por pasada; un segundo juez aceptado en la misma pasada sustituye al anterior. Una salida de Lean ilegible cuenta como `lean_no_disponible`, no como gate rojo. |
| **M-14** | Gates | Numeración para Lean: localizaciones y personajes por su id textual ordenado; eventos por (capítulo, con el contexto como 0; id de fila). Un periodo sin fecha abarca todo el calendario. Un evento sin franja va como `manana` hasta que `formal/lean` acepte la franja opcional (§4.2): puede dar falsos positivos dentro del mismo día. |
| **M-15** | Gates | Criterios del juez de manuscrito, en enum cerrado: `continuidad`, `personajes`, `arco_ritmo`, `tono` y `personalizacion`, con puntuación entera de 1 a 5 y `justificacion`. La revisión humana va en `POST/GET /proyectos/{id}/manuscrito/juez` (rebanada `revision/`) y no cambia estado ni gates. |
| **M-16** | Exportación | `SalidaExportador` acepta `serie` y `volumen` como opcionales, porque el agente los produce. La página de novedades va dentro de `lectura.html` y el PDF se imprime de ese mismo fichero. Una titulación que no sea uno de los tres valores cerrados se trata como `numerado_y_titulado`. Un `export/vN` sin fila en la base no cuenta como versión. Ruta extra: `GET /versiones/{v}/capitulos/{n}`, que usa el frontend. |
| **M-17** | Cambio | La petición y el fragmento del lector solo se escriben en `cambios/peticion-N.txt` y llegan al Intérprete por `/mcp/entrada`. Al volver a sellar, el identificador del Intérprete se renueva (AJ-4). Una respuesta `ninguno` gasta intento; agotado el tope, el proyecto vuelve a `publicada` con el cambio fallido. Una petición sobre una versión antigua se registra como `obsoleto`, sin transición y sin guardar el texto (RF-123). |
| **M-18** | Cambio | El valor anterior sale de la base, no del agente. Un hecho nuevo del lector tiene id `lector_<c>` y origen `lector`. Los capítulos afectados salen de `hecho_uso` de la última versión publicada; si ninguno usa el hecho, de las fichas que lo piden y, en último lugar, del capítulo del fragmento. La versión nueva de cada capítulo reabierto es su versión más alta + 1 y queda en `cambio_capitulo`. |
| **M-19** | Worker | El éxito es salir con código 0 y el proyecto en una parada. Salir con 0 sin parada es `sin_parada`. Un código negativo o ≥ 128 es una caída. No se guarda la salida del proceso y el hijo no hereda `ANTHROPIC_API_KEY`. La arista `worker_fallido → publicada` sale de los cinco estados de una regeneración. Decidir en `aprobacion_final` durante una regeneración encola otro trabajo. `MSM_WORKER=0` lo desactiva. |
| **M-20** | API | Códigos nuevos en el catálogo: `herramienta_no_disponible` (503) y `cambio_inexistente` (404). Si una herramienta falta dentro del manejador del Exportador, `/resultado` responde 503 sin registrar nada ni gastar intento. |

### 2.4 Correcciones tras las revisiones (2026-09-24, R-6)

| # | Decisión |
|---|---|
| **M-21** | Las órdenes de Editor, juez de capítulo, Bibliotecario y Revisor llevan en la entrada `version`, `intento_texto` y `etapa`: `borrador` para el Editor y `editado` para juez y Bibliotecario; el Revisor lee la versión vigente aprobada. La del planificador lleva `notas_plan`, que `/estado` no enseña. Las de juez de manuscrito, Revisor y Exportador llevan `manuscrito` (los punteros vigentes de los 10 capítulos); la del Revisor, además, `informe_gates` y las notas de `aprobacion_final`. |
| **M-22** | `/mcp/escritura` valida el sello y escribe dentro de la misma transacción: cierra el hueco entre la comprobación de AJ-4 y la escritura. Las llamadas que rechaza la validación de argumentos también quedan en `llamada_mcp` (RF-105). |
| **M-23** | Si un Bibliotecario rechazado agota el tope, se borra lo que escribió para su capítulo (B-16). `registrar_evento` es idempotente por (capítulo, descripción, lugar, día, franja, momento). El resumen vigente es el de la versión vigente del capítulo, y el de acto el último escrito por una versión vigente. |
| **M-24** | Tras «reintentar», el Escritor pasa a la versión siguiente cuando su (versión, intento) ya existe, en vez de numerar el intento sin tope: el intento sigue en 1..3 (CHECK, rutas y MCP). Una versión que los deterministas cortan queda en `borrador`, no en `editado`. Un intento rechazado del Revisor se reutiliza, sin dejar huecos. |
| **M-25** | **Nunca se lanza un Revisor sin capítulo.** Un juez de manuscrito que suspende tiene que señalar al menos un capítulo. La cobertura roja de un hecho sin ficha señala el capítulo con menos hechos en su ficha. Un Lean rojo solo con eventos del contexto es `error` con causa `contexto_incoherente`. En «cambios» de `aprobacion_final` el cuerpo admite `capitulos` opcional; sin él, pasan todos. Sustituye la última frase de M-6. |
| **M-26** | Las fechas parciales se validan como fechas reales. Un fallo al generar la cronología es `error` con causa `cronologia_invalida`. El worker mata el árbol de procesos al agotar el tiempo (`taskkill /T` en Windows, grupo de procesos en POSIX), y no abandona un proyecto que ha llegado a una parada, salga como salga. Las rutas de versión acotan sus enteros. |
| **M-27** | Lean no corre dentro del `BEGIN IMMEDIATE` de la emisión: si la orden que toca es la del juez de manuscrito y a la pasada le faltan gates, `emitir_siguiente_orden` confirma lo derivado, ejecuta los gates sin transacción abierta (`FASES_PREVIAS`, `preparar_gates`: leer y generar, ejecutar Lean, guardar la fila en una transacción corta que vuelve a mirar `hay_gate`) y vuelve a emitir una vez. Un fallo de esa fase es `error` con su causa; la fila de cobertura ya queda. |
| **M-28** | (2026-09-24, auditoría de cohesión) La orden del Agente de Contexto lleva sus datos en la entrada, como `notas_plan`: en `intake`, `brief` (las respuestas) y `hechos_confirmados`; en `contexto`, `brief_normalizado` y `hechos_confirmados`. `/mcp/lectura` no los exponía y el agente no tenía de dónde leerlos. El texto libre sigue sin ir en ninguna orden salvo como identificador del Extractor (RF-14). |

Pendientes aceptados del bloque 3: un cambio fallido no restaura la biblia, porque su historia va por capítulo (B-2) y el siguiente cambio la reescribe; y la prueba real de `claude -p` es manual (TC-10).

Supuestos menores: publicación atómica (directorio temporal, renombrado a `export/vN` y después las filas); la cobertura se mide contra el `hecho_uso` de la versión vigente de cada capítulo; `formal/lean` se localiza desde `Path(__file__)`.

---

## 3. Contradicciones entre documentos y cómo se resuelven

1. **Quién escribe la biblia.** RF-65 rige desde `capitulos`; lo que siembra la planificación entra por `/resultado`, solo en `planificacion` y `escaleta`.
2. **Estado del capítulo cuando actúa el Bibliotecario.** `verificado` = deterministas y juez en verde. El Bibliotecario trabaja sobre `verificado`, y al registrar su resultado el capítulo pasa a `aprobado`.
3. **Palabras prohibidas de estilo y vetos.** `lenguaje.prohibidas` va a la lista negra (baja) y los vetos al guardarraíl (bloqueante); se corrige definitions §6.
4. **Acciones de la tabla de verificadores.** Los hallazgos medios y bajos solo se registran y viajan en el informe del intento anterior; no hay regeneración de pasaje.
5. **Dos vías para registrar.** `/resultado` es la única vía para las salidas de subagente; `POST /capitulos/{n}/versiones` se retira; `/manuscrito/juez` queda solo para la revisión humana.
6. **`POST /exportar` frente a la inmutabilidad.** El Markdown se escribe al publicar y lo sirve `GET /versiones/{v}/manuscrito`.
7. **El Revisor no puede arreglar la cobertura** (`hecho_uso` solo lo escribe el Bibliotecario). En `revision`, por cada capítulo: Revisor → deterministas → Bibliotecario sobre la versión nueva. Los capítulos a corregir salen de `ficha_capitulo_hecho` (cobertura), de `evento.capitulo` (Lean) y de un campo `capitulos` en la salida del juez. Cambia la tabla del paso 3 y TLA+.
8. **Macroestructura.** En la v1, solo la titulación con valores cerrados (`numerado`, `titulado`, `numerado_y_titulado`); prólogo, epílogo e interludios quedan fuera del alcance, y se dice en definitions y spec1.
9. **Metadatos** en `export/vN/metadatos.json`. **Fichero Lean** en `verificacion/pasada-k/cronologia.lean`, por pasada y no por ciclo (AJ-3),, copiado a `export/vN/` al publicar.
10. **Agente en la auditoría MCP.** Se infiere de la superficie y de la orden vigente, y se marca como inferido.
11. **Semilla:** NULL, declarado; `version_prompt` es el hash del fichero del agente, que envía el hook.
12. **Tope de 100.000 tokens:** se hace cumplir en el Escritor; en el resto queda acotado por construcción, como riesgo aceptado.
13. **Verificación de acto:** fuera de la v1; la compactación la dispara el último capítulo del acto (B-17).
14. **YAML:** todas las salidas de agente son JSON; el YAML de definitions §12 queda como documentación.
15. **Firma de los verificadores:** `(texto, vista)`, donde la vista reúne contexto, ficha, biblia a fecha N−1 y listas.
16. **E3 y Lean:** RF-74 compara por orden de capítulo y Lean por momento de la historia; E3 se monta con la partida contada en una analepsis posterior a la reaparición.

---

## 4. Contratos con las otras sesiones

### 4.1 Sesión de agentes (B-7)

1. **Una sola ruta para registrar cualquier salida:** `POST /proyectos/{id}/resultado`, con `{orden, salida_cruda, metadatos?}`, donde `orden` es el sello (punto 7). El backend extrae y valida.
2. **Sello de orden.** La respuesta de `/siguiente` lleva un campo `sello` con la forma `<proyecto>:<orden>:<generación>` (AJ-4). Es opaco salvo el primer segmento. El harness lo pone en la primera línea del prompt como `orden: <sello>` y lo devuelve en `/resultado`. Que el subagente lo repita es opcional (punto 7).
3. **Formato de salida.** Escritor, Editor y Revisor devuelven Markdown: `# título` y el texto; la línea del sello, si viene, se quita. Todos los demás devuelven un único bloque JSON delimitado.
4. **El Escritor lee su prompt de un fichero.** `Read` exige rutas absolutas y corta hacia los 25.000 tokens, y el prompt puede llegar a 100.000. Por eso el backend lo guarda en **partes de, como mucho, 20.000 tokens estimados** (`…prompt.parte-N.md`, más el fichero entero para auditoría), y la orden lleva en `entrada.rutas_prompt` la lista de **rutas absolutas**, en orden, dentro de `prompts/` del proyecto. El Escritor las lee todas antes de escribir. El Escritor solo tiene `Read`, y el hook de policy se lo limita a `prompts/`.
5. **Un solo hook registra todas las salidas** (`SubagentStop`), no solo los borradores. Así el orquestador no reteclea salidas largas.
6. **`/mcp/lectura`** trae, además de lo de RF-103: el contexto (sin el texto libre), el plan, una ficha, la guía de estilo, el texto de un capítulo por número, versión, intento y etapa, y el informe de un intento.
7. **Cuerpo de `/resultado`** (cierra P-1 y P-4 de plan-agentes): `{orden, salida_cruda, metadatos?}`. `orden` es el **sello** completo, en texto, que el harness saca del prompt que envió, no de lo que devuelve el modelo. El backend lo compara con el sello de la orden vigente (AJ-4). Que el subagente repita el sello en la primera línea es opcional: si lo hace, el backend quita esa línea antes de validar, y si no lo hace, no cuenta como fallo de formato. El hook envía la salida sin tocarla (`last_assistant_message` si empieza por la cabecera `orden:`; si no, lo último que el subagente escribió en el transcript (texto o entrega de `SubagentHandback`) que empiece por ella; si nada, `last_assistant_message`), y **el backend** extrae el sello, el Markdown o el bloque JSON (en el Markdown, lo que venga tras la línea `<!-- fin del capítulo -->` se descarta: son notas del modelo, no prosa) y valida: la extracción vive en un solo sitio, con pruebas. El bloque 1 acepta `{orden, resultado}`; el bloque 2 lo sustituye por `salida_cruda` y retira `resultado`. Hasta entonces, el harness puede seguir extrayendo el JSON por su cuenta.
8. **`metadatos`** (cierra P-6): `{modelo, tokens_entrada, tokens_salida, tokens_cache_creacion, tokens_cache_lectura, duracion_ms, version_prompt}`. Todos son opcionales. El backend los guarda con la orden, que es de donde saldrán el coste y la tabla de evaluaciones.
9. **Auditoría de la policy** (cierra P-5): `POST /proyectos/{id}/auditoria` con `{decision, herramienta, agente, motivo}`, sin valores de texto libre. El backend lo escribe en `auditoria` con tipo `policy`. Las decisiones que no tocan un proyecto se quedan en el registro local del harness.
10. **Registro de `/mcp/entrada`:** cada canje, válido o no, se escribe en `llamada_mcp` sin el texto ni el secreto (RF-105). Así el red team de E2 tiene la prueba de cada intento con un identificador ajeno, usado o caducado. Llega con el bloque 2.
11. **URLs de MCP** (P-7): `http://127.0.0.1:8000/mcp/lectura/`, `…/mcp/escritura/` y `…/mcp/entrada/`. La ruta exacta de `entrada`, con el nombre de su herramienta, se confirma al cerrar el bloque 1.

### 4.2 Sesión formal (TC-1, TC-2)

El backend genera, por novela, un `.lean` que importa el módulo Lake de `formal/lean` y define `novela : Novela`:

- ids numéricos (`Nat`) con su correspondencia en un JSON aparte, y sin ningún texto libre;
- listas ordenadas por id, incluido el árbol de localizaciones (`padre`), porque estar en una casa y en el pueblo que la contiene no es estar en dos sitios;
- momentos en dos escalas: los recuerdos como intervalo de días de calendario; la historia como `dia-N` más una franja (`manana`, `tarde`, `noche`); toda la historia es posterior a todos los recuerdos, y solo se compara cuando el orden es seguro;
- un `theorem … := by decide +kernel` por invariante; la franja del día es opcional y, si falta, dos eventos del mismo día solo se comparan por día;
- `#eval violaciones novela`, que imprime una línea JSON con los ids de los eventos implicados.

Comprobado por la sesión formal: con unos 100 eventos, `decide` agota `maxRecDepth` y `decide +kernel` no. Los teoremas usan `by decide +kernel`. El fichero se escribe en **UTF-8 sin BOM** (con BOM, Lean no lo lee) y con saltos `\n`; el formato completo está en plan-formal §3.

### 4.3 Sesión de frontend (TC-7)

La API sirve `lectura.json` por versión. **La forma exacta es la de [plan-frontend.md](plan-frontend.md) §5, adoptada tal cual:**

- `version`, `anterior` y `cambiados[]`;
- `portada {titulo, dedicatoria|null}`;
- `capitulos[10] {numero, titulo|null, html}`;
- `personajes[] {id, nombre, rol[], descripcion?, capitulos[]}`;
- `lugares[] {id, nombre, descripcion?, padre|null, capitulos[]}`.

El HTML solo admite `p`, `em`, `strong`, `blockquote`, `hr` y `br`, y cada `<p>` lleva un `data-p` numerado desde 1: es el `p<n>` de B-14. `GET /versiones` devuelve `{versiones: [{version, publicada, cambiados[]}]}`. El paso 9 comprueba cada `lectura.json` generado con el validador del frontend (`npm run validar-lectura`).

`GET /cambios/{c}` distingue estos estados: `interpretando`, `propuesto` (con el hecho y los valores anterior y nuevo), `obsoleto` (RF-123), `regenerando`, `fallido` y `publicado` (con el número de la versión nueva).

Dependencias del frontend (F-1): `react`, `react-dom`, `vite` y `@vitejs/plugin-react`, con npm. Entran en architecture §7 y en AGENTS.md al cerrar el bloque 1.

---

## 4.4 Cambios de documentos pendientes

Se aplican en la actualización de `docs/` al cerrar el bloque 1, o en el bloque en que llegue el código que les corresponde:

- **architecture §2 y §8**: E-3. La entrevista es la skill `/entrevista` y el frontend se queda sin `entrevista/`. El árbol de `.claude/` gana `harness/`, `tests/`, `estado/` y las skills `entrevista` e `inspeccionar-lectura` (plan-agentes §9).
- **architecture §7 y AGENTS.md**: las dependencias del frontend (F-1): `react`, `react-dom`, `vite` y `@vitejs/plugin-react`. Y R-5: fuera `cosmic-ray`.
- **validators.md**: las filas de verificación del frontend de plan-frontend §8 (node:test sobre el contrato, las rutas y el filtro HTML, T; `vite build`, A; capturas del navegador, I; `validar-lectura` sobre `export/vN/lectura.json`, T). Y V-15 según R-5.
- **definitions §9**: B-18 (`excluye` en un hecho `evento`) y B-19 (preferencias del comprador).
- **definitions §6**: la resolución 3 de §3 (`lenguaje.prohibidas` va a la lista negra y los vetos, al guardarraíl).
- **spec1**: V-15 (R-5), D-7 sin cosmic-ray, §1.2 (criterio `contenido` del juez, B-15), la invariante 3 de Lean (TC-2), V-32 con suma ≥ 18 (TC-5) y §5.1 (TC-12, más las rutas de auditoría y de cambios).
- **plan-entrega H0**: los briefs son JSON.
- **spec1 RF-05a**: `cambio_solicitado` solo sale por acción humana, **salvo** cuando el Intérprete agota su tope: entonces vuelve a `publicada` con el cambio fallido (Q6). Lo detectó la revisión del bloque 1.
- **spec1 RF-14**: el identificador es `<proyecto>.<secreto>`. Lo que «no se deriva del proyecto» es el **secreto**; el prefijo solo sirve para que la petición identifique su proyecto sin recorrer los demás (V-24). Lo detectó la revisión del bloque 1.
- **architecture §3.1**: las aristas de Q6 (13 pares) entran en el diagrama y en la tabla.
- **R-1** (12 agentes, una sola orden en `planificacion`): architecture §2 y §3 (tabla y diagrama de agentes, y la fila de `planificacion` de §3.1), spec1 §1.2 y §4.4, y plan-entrega §4.
- **R-2** (sin heurísticas sobre la prosa): spec1 RF-74 y RF-75 (solo antes de escribir), V-12 y V-17 en spec1 §9 y validators.md.
- **R-3** (sin Repeticiones): plan-entrega E-5, marcada como rechazada.
- **P-2** (el hook registra todas las salidas): architecture §8, en la descripción de los dos hooks.
- **B-8** (bloque «Informe del intento anterior» y vacíos opcionales): architecture §6.3, en la tabla de bloques, y spec1 RF-50c.
- **§4.1** (cuerpo de `/resultado`, sello y `/auditoria`): spec1 §5.1.

## 4.5 Avisos pendientes a otras sesiones

Hay que avisar a cada sesión cuando llegue lo que espera:

| Cuándo | A quién | Qué |
|---|---|---|
| Al cerrar el bloque 1 | agentes (c9) | La URL exacta de `/mcp/entrada` y el nombre de su herramienta (P-7) |
| Bloque 2 | agentes (c9) | Que `/resultado` ya acepta `{orden: sello, salida_cruda, metadatos}`, para activar `MSM_CONTRATO_RESULTADO=salida_cruda`; que ya existe `/auditoria`; y las URLs de `/mcp/lectura` y `/mcp/escritura` |
| Bloque 2 | briefs (ec) | Que ya existe `excluye` (B-18), para repasar E3 con `comprobar.py` |
| Bloque 2 | formal (a1) | Que AJ-1 a AJ-5 ya están en `backend/proyecto/`, para alinear TLA+ rama a rama |
| Bloque 3, paso 9 | frontend (76) | Que la ruta de lectura ya se sirve, para pasar `lectura/` a `FUENTE = 'api'` |
| Bloque 3, paso 9a | frontend (76) | Que existen `POST /cambios`, `GET /cambios/{c}` y `POST /cambios/{c}/confirmacion`, para construir `cambio/` |

## 5. Lo que sigue necesitando a la persona

- Instalar `elan` y Java; permitir la descarga de Chromium (TC-6).
- La prueba real de `claude -p` con un `/regenerar` mínimo (TC-10).
- Revisar las listas del guardarraíl cuando pueda (B-12).
- Los commits.
