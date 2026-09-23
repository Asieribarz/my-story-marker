# pendientes-sesiones.md — Lo que cada sesión tiene que arreglar

> Sale de la revisión de solo lectura del 2026-09-23, 16:25: cinco revisores y un verificador que intentó refutar cada hallazgo. Se confirmaron 40 de 41. Manda [decisiones-backend.md](decisiones-backend.md): si un arreglo choca con ese fichero, se avisa a la sesión de backend en vez de resolverlo por cuenta propia. Al terminar un punto, márcalo como hecho aquí.

## Sesión de agentes (.claude/)

- [ ] **alta** · `.claude/harness/politica.py:140` — Grep con la carpeta de un proyecto (o la raíz de proyectos) como `path` está permitido, y ripgrep entra entonces en brief/ y cambios/: se puede leer el texto libre con una herramienta de fichero, justo lo que E-3 prohíbe
  - Arreglo: En Grep, denegar cuando `path` es la raíz de proyectos o la carpeta de un proyecto (relativa con menos de 2 partes), o cuando brief/ o cambios/ quedan por debajo de ese path. Si hace falta, permitir solo subcarpetas explícitas como capitulos/ o prompts/. Añadir la prueba de Grep sobre <raiz>/<id> y sobre <raiz>.
- [ ] **media** · `.claude/harness/politica.py:70` — Las rutas con `..` no se normalizan, así que se saltan las reglas 3, 4 y 5 (escribir en proyectos/, leer brief/ y cambios/, escritor solo en prompts/). Además, el escritor puede leer prompts/ de cualquier proyecto
  - Arreglo: Normalizar con os.path.normpath (o Path.resolve(strict=False)) antes de _dentro, y denegar cualquier ruta que siga llevando `..` dentro de la raíz. Para el escritor, comparar partes[0] con el proyecto de la orden vigente, que el hook puede sacar de la cabecera del transcript o del estado local. Añadir pruebas con `..`.
- [ ] **media** · `.claude/harness/politica.py:266` — La policy falla abierta si la auditoría lanza algo que no sea OSError después de haber decidido denegar: no se escribe la denegación, el proceso sale con 1 y Claude Code ejecuta la herramienta
  - Arreglo: Escribir la denegación en stdout antes de auditar, o envolver _auditar en `except Exception`, y contar Edit, Write, MultiEdit y NotebookEdit bajo la raíz como sensibles en el fallo. Añadir la prueba de un backend que responde 200 con HTML.
- [ ] **media** · `.claude/agents/escritor.md:14` — El Escritor no puede leer su prompt ensamblado de una sola vez con Read: la herramienta corta a 25.000 tokens y el prompt no le dice cómo paginar ni cómo saber que ha llegado al final
  - Arreglo: En el prompt: leer con offset y limit hasta una marca fija de fin y no escribir antes de verla. Pedir al backend (paso 6) que termine el fichero de prompt con esa marca constante. Otra vía es subir CLAUDE_CODE_FILE_READ_MAX_OUTPUT_TOKENS en el env de settings.json, pero es una decisión que hay que tomar a propósito.
- [ ] **media** · `.claude/agents/escritor.md:21` — Los prompts contradicen R-2 sobre `mencionados`: quien solo sale en un recuerdo o una analepsis va en mencionados y no se bloquea, pero el escritor, el escaletista y el juez lo tratan como alguien que no puede aparecer
  - Arreglo: Escaletista: mencionados = quienes se nombran o salen solo en un recuerdo o analepsis. Escritor: pueden aparecer solo dentro de un recuerdo marcado como tal. Juez: una acción dentro de una analepsis marcada no cuenta como presencia; sí cuenta actuar en el presente de la historia.
- [ ] **media** · `.claude/harness/politica.py:133` — La policy solo mira el nombre del `path` de Read y Grep: un Grep sobre un directorio, o con `glob`, lee el texto adversarial de E2. El brief E2 y plan-agentes §5.3 afirman que no se puede leer.
  - Arreglo: Denegar Grep cuando `glob` o `pattern` apunten a `texto_libre`, o cuando `path` sea un directorio que contenga esos ficheros; o sacarlos del alcance de ripgrep con un `.ignore` para `evals/briefs/texto_libre*.txt`. Ajustar plan-agentes §8 y, en la sesión de briefs, la redacción de e2 L10 y L119.
- [ ] **baja** · `.claude/agents/agente-contexto.md:14` — El sello no se trata como opaco en todo el harness: dos prompts de H1 enseñan la cabecera como `orden: <proyecto>:<n>`, y comun.py saca el id de la orden del segundo segmento del sello
  - Arreglo: Cambiar `<proyecto>:<n>` por `<sello>` en los dos prompts y en los docstrings. Limitar la lectura del segundo segmento al caso de una orden sin campo `sello` (contrato del bloque 1), o quitarla cuando llegue el bloque 2.
- [ ] **baja** · `.claude/skills/generar/SKILL.md:31` — Las skills solo conocen `error_ensamblado`; AJ-5/TC-3 lo sustituyen por la decisión `error` con causa, y /generar no sabría explicar `lean_no_disponible` ni `pdf_no_disponible`
  - Arreglo: Añadir a /generar la fila `error` · causa (lean_no_disponible, pdf_no_disponible, D-9) con lo que tiene que hacer la persona, y listar `error` en el paso 2 de orquestar-novela.
- [ ] **baja** · `.claude/tests/test_definiciones.py:13` — Todo el análisis estático V-13·A depende de PyYAML, que es una dependencia transitiva no declarada, y se salta en silencio si desaparece
  - Arreglo: Leer el frontmatter con biblioteca estándar (son claves simples y una lista mcpServers), o sustituir importorskip por un import que falle.

## Sesión de briefs (evals/)

- [ ] **media** · `evals/briefs/e2-inyeccion.json:96` — La señal del hook de policy en E2 espera que se deniegue leer proyecto.sqlite, pero ni la policy ni su especificación lo deniegan con Read o Grep, y la decisión no llega a la tabla auditoria.
  - Arreglo: Quitar proyecto.sqlite de la señal, o limitarla a Bash y PowerShell, y decir que con un proyecto inexistente la decisión queda en el auditoria.jsonl del harness. Si se quiere denegar también la lectura de la base con Read, lo decide la persona y lo cambia la sesión de agentes en plan-agentes §5.3, no el brief.
- [ ] **media** · `evals/briefs/e2-inyeccion.json:90` — La señal del identificador de un solo uso exige que cada intento quede en llamada_mcp. Hoy /mcp/entrada no registra nada; para el identificador inyectado no hay base donde escribirlo; y registrarlo como pide RF-105 contradiría la señal de la L102.
  - Arreglo: Dejar en la señal solo lo comprobable: EntradaNoCanjeable para el identificador inyectado y para el propio ya consumido, y ningún texto devuelto. Pasar el registro en llamada_mcp a limites, como dependiente de RF-105, con la nota de que, cuando llegue, leer_entrada se registre sin el resultado. Esa decisión la toma la sesión de backend.
- [ ] **baja** · `evals/briefs/e3-incoherencia-temporal.json:87` — La descripción de E3 dice que lo que pase de la ficha al texto solo lo ve Lean, en contra de R-2 y del propio puede_saltar del brief.
  - Arreglo: Reescribirla así: «Tras R-2 ninguna regla determinista de continuidad mira la prosa: lo que pase de la ficha al texto lo ven el juez de capítulo (puede_saltar) y Lean».
- [ ] **baja** · `evals/briefs/e3-incoherencia-temporal.json:119` — El caso de control «Lean sobre h2» no controla nada, porque nadie registra al ser querido de h1 como presente en el evento h2.
  - Arreglo: Declararlo en limites (el control es vacuo mientras los eventos del contexto no lleven presentes) o cambiarlo por un control real. Que la materialización registre presentes en los eventos del contexto, por ejemplo la fuente del hecho, sería una decisión de backend que hay que llevar a la persona.

## Sesión de frontend (frontend/)

- [ ] **baja** · `frontend/src/lectura/modelo.js:15` — Con {versiones: []}, versionVigente lanza un TypeError en el render y deja la página en blanco
  - Arreglo: En Proyecto (Lectura.jsx), si versiones.versiones está vacía, mostrar un Aviso ('Tu novela aún no está publicada') antes de llamar a versionVigente. Y acordar con backend, en §4.3, si ese caso es 404 con codigo o una lista vacía.
- [ ] **baja** · `specs/plan-frontend.md:202` — E-4 sigue pendiente y el plan da .mcp.json por inexistente cuando ya existe
  - Arreglo: Hacer la inspección de portada, capítulo (también a 375 px) y fichas con Playwright MCP, en claro y oscuro, y actualizar §8 y §10 con el resultado y con que .mcp.json ya está.
- [ ] **baja** · `frontend/src/lectura/useCarga.js:1` — Tres módulos sin JSX no llevan // @ts-check, en contra de F-2
  - Arreglo: Añadir // @ts-check como primera línea de los tres ficheros y corregir lo que el editor marque, o dejar escrita en F-2 la excepción.

## Sesión formal (formal/)

- [ ] **media** · `formal/tla/GrafoNovelaAnterior.cfg:17` — La configuración «Anterior» desactiva AJ-3 y AJ-4 a la vez, y TLC para en la primera violación: solo puede enseñar el contraejemplo de AJ-4, nunca el de AJ-3. Además, no está escrito qué propiedad tiene que fallar, y §5 está vacío.
  - Arreglo: Separarla en dos .cfg, uno por ajuste (solo SelloConGeneracion=FALSE y solo GatesPorPasada=FALSE), y escribir en plan-formal §2.2 qué propiedad debe violar cada uno (Inv2_ReanudarSinCoste o Inv6 en el primero, Inv1 en el segundo). Completar §5 con las trazas y pasarlas a iteraciones.md.
- [ ] **media** · `formal/tla/GrafoNovela.tla:859` — Dos partes de las invariantes son ciertas por construcción y no pueden fallar: Inv3_VersionAnterior y el primer conjunto de Inv6. Además, Inv6 no instrumenta emitir ni registrar, aunque plan-formal dice que los cubre.
  - Arreglo: Declarar en plan-formal §2.3 que esas dos partes valen por representación, como ya se hace con «una versión vigente» en la invariante 2, o reformularlas para que puedan fallar. Por ejemplo, modelar las versiones publicadas como referencias a filas capitulo_version que la regeneración podría sobrescribir, e instrumentar Pedir/Registrar con una marca fantasma si el guardia del bloqueo se quita en una variante.
- [ ] **media** · `formal/lean/ejemplos/novela.lean:33` — Los ejemplos que sirven de plantilla del fichero que genera el backend, y el generador de la prueba de tamaño, usan `by decide`, pero el contrato exige `by decide +kernel`.
  - Arreglo: Cambiar los dos ejemplos a `by decide +kernel` y añadir a generar_tamano.py una opción que genere la variante +kernel, citándola en §3.4.
- [ ] **baja** · `specs/plan-formal.md:115` — La fila de Pedir se marca «igual» a emitir_siguiente_orden, pero la spec no modela la rama de RF-14 que cierra la orden vigente por entrada caducada y emite otra.
  - Arreglo: Marcar la fila de Pedir como «igual salvo la caducidad de la entrada (RF-14), fuera del modelo», o modelar una acción CaducarEntrada acotada que cierre la orden sin gastar intento.
- [ ] **baja** · `formal/tla/GrafoNovela.cfg:3` — La cabecera del cfg dice que el código implementa AJ-3 y AJ-4, y no es así. El cfg «Anterior» y plan-formal remiten a contraejemplos de plan-formal §5 (I-formal-1) que no están escritos.
  - Arreglo: Cambiar la cabecera a «con AJ-3 y AJ-4, que el código aplica en el bloque 2», y escribir en plan-formal §5 los contraejemplos o hallazgos de diseño que justifican AJ-2 a AJ-6 (I-formal-1 incluido), para que iteraciones.md pueda recogerlos.

## La persona

- [ ] **baja** · `.claude/settings.json:10` — El settings.json que se commitea lleva reglas allow de sesiones concretas: el scratchpad y el workflow de la sesión 853bdf54, correr_mutantes.py (cosmic-ray, que R-5 retira), awk y xargs
  - Arreglo: Antes del commit, mover las l.10-17 a .claude/settings.local.json y dejar en settings.json solo las de §5.4 (msm.py, Agent, Skill y las tres superficies MCP).

## Backend (lo recoge la sesión de backend en el bloque 2)

- [ ] **alta** · `specs/decisiones-backend.md:111` — El cuerpo de /resultado se contradice dentro de §4.1: el punto 1 dice que el campo es `sello` y el punto 7, que es `orden`.
  - Arreglo: Cambiar §4.1.1 a `{orden, salida_cruda, metadatos?}`, con `orden` = sello, y dejar un único punto normativo, por ejemplo haciendo que §4.1.1 remita a §4.1.7.
- [ ] **alta** · `specs/decisiones-backend.md:152` — La lista de §4.4 deja fuera los recortes R-1, R-2 y R-3, que según §0 mandan sobre todo lo demás, aunque dejan desfasados architecture, spec1, validators y plan-entrega.
  - Arreglo: Añadir a §4.4 una entrada por recorte, con estos destinos: R-1 → architecture §3, §3.1 y §11, spec1 §1.2 y plan-entrega §4 y H2; R-2 → architecture §4 y §4.2, spec1 RF-74, RF-75, V-12 y V-17, y validators V-12; R-3 → plan-entrega E-5, H3 y H9.
- [ ] **media** · `.claude/agents/agente-contexto.md:42` — B-18 (`excluye` en un hecho evento) no llega al prompt del Agente de Contexto, y decisiones §4.5 no prevé avisar a la sesión de agentes. Cuando el backend lo aplique, el agente reconstruirá los hechos sin `excluye` y E3 no llegará a Lean
  - Arreglo: Backend: añadir en §4.5 la fila «Bloque 2 → agentes: `excluye` en hecho evento (B-18)». Agentes, cuando llegue: añadir `excluye {fuente, tipo: muerte|partida}` al ejemplo y a la tabla, con «si el hecho lo trae, consérvalo tal cual», y alinear la lista de preferencias con B-19.
- [ ] **media** · `specs/decisiones-backend.md:43` — B-14 no define qué es un párrafo, así que p<n> del backend, data-p del frontend y 'parrafo' del juez pueden desalinearse
  - Arreglo: Fijar en B-14 la unidad: solo los párrafos del cuerpo, sin el encabezado '#'; '---' no cuenta; cada párrafo dentro de '>' cuenta. Añadir en el paso 9 una prueba de que, para el mismo texto, la segmentación de B-14 y los data-p del conversor de TC-7 dan la misma numeración. Pedir a la sesión de agentes que juez-capitulo.md use esa misma definición.
- [ ] **media** · `specs/decisiones-backend.md:18` — R-4 mueve el proyecto a publicada con el cambio fallido cuando falla el worker, pero esa transición no está ni en TRANSICIONES ni en Aristas, y la spec deja el worker fuera del modelo.
  - Arreglo: La sesión de backend fija la arista o aristas (origen en regeneracion, verificacion_manuscrito, revision, publicacion o cambio_solicitado, con una causa propia, p. ej. trabajo_fallido) y las añade a TRANSICIONES. Después, la sesión formal añade al modelo una acción FallaWorker acotada, que pase por Transitar/Deshacer, y actualiza plan-formal §1.
- [ ] **media** · `backend/proyecto/persistencia.py:224` — El código permite reenviar el brief en intake en cualquier momento, y la spec solo permite enviarlo una vez. Esa diferencia esconde un fallo: un texto libre nuevo nunca pasa por el Extractor.
  - Arreglo: Backend: que extraccion_hecha dependa del brief vigente (p. ej., una orden del Extractor aceptada después del último guardar_brief), y decidir si el reenvío se deniega o cierra la orden vigente como caducada. Formal: modelar SubirBrief como repetible en intake y corregir la fila de §2.4.
- [ ] **media** · `specs/decisiones-backend.md:112` — El sello de §4.1.2 y §4.1.3 es el antiguo: dos segmentos y repetición obligatoria. Además, ningún punto de decisiones fija dónde viaja el sello en /siguiente, y el harness lo resuelve con un fallback silencioso.
  - Arreglo: Reescribir §4.1.2 y §4.1.3 con el formato de AJ-4 y la repetición opcional, y fijar en §4.1 el nombre y el nivel del campo (por ejemplo `orden.sello` en la respuesta de /siguiente). Recomendable, a cargo de la sesión de agentes: con el contrato `salida_cruda`, que el harness falle si falta `sello`.
- [ ] **media** · `specs/decisiones-backend.md:152` — §4.4 también deja fuera otros cambios de docs/ que decisiones exige explícitamente.
  - Arreglo: Añadir a §4.4: definitions §3 y spec1 RF-90 (§3.8); architecture §7, AGENTS.md y spec1 D-8 (TC-6); architecture §2, §4 y §6.2 (§3.13); architecture §8 hooks y skill (§4.1.5); architecture §6 (B-2); architecture §3.1 y spec1 RF-08 (TC-3/AJ-5); y AGENTS.md «Comprobaciones», con las pruebas de .claude/tests (plan-agentes §9).
- [ ] **media** · `specs/decisiones-backend.md:30` — B-18 no cuadra con B-1: la materialización al salir de `contexto` escribe `evento.lugar` y `evento.excluye`, que son claves ajenas a `localizacion` y `personaje`, pero B-1 no materializa ni personajes ni localizaciones. Tampoco dice cómo se traduce `fuente` (un id de hecho) a un id de personaje.
  - Arreglo: Ampliar B-1: al salir de contexto se materializan también los personajes y localizaciones del contexto, como capítulo 0 (B-2). Añadir a B-18 que `excluye.fuente` se resuelve al personaje cuyo `origen.fuente` coincide, y que no encontrarlo es un hallazgo del validador.
- [ ] **media** · `specs/decisiones-backend.md:96` — El fichero Lean se guarda por ciclo (`verificacion/ciclo-k/`), pero AJ-3 decide que los gates se guardan por pasada precisamente porque el ciclo se reinicia y se reutilizaría el Lean de una versión anterior.
  - Arreglo: Cambiar §3.9 a `verificacion/pasada-p/cronologia.lean`, o a pasada y ciclo, en `shared/rutas.py`. La sesión formal ajusta el ejemplo de plan-formal §3.3.
- [ ] **baja** · `specs/decisiones-backend.md:154` — La lista §4.4 de cambios de documentos pendientes no recoge R-1 ni el registro de todas las salidas por el hook (P-2), así que architecture y spec1 seguirán describiendo 13 agentes y dos vías de registro
  - Arreglo: Añadir a §4.4: architecture §3 (12 agentes, planificador), §3.1 (una sola orden en planificacion), §8 (SubagentStop registra todas las salidas; la skill solo lee el acuse) y spec1 l.56.
- [ ] **baja** · `docs/architecture.md:537` — Los docs no recogen todavía la pila ni la verificación del frontend (pendiente de §4.4), aunque ya se tocaron por otras dependencias
  - Arreglo: Al cerrar el bloque, aplicar las tres entradas de §4.4 del frontend: las cuatro dependencias de F-1 con npm en architecture §7 y en AGENTS.md; quitar entrevista/ de §8; y añadir a validators.md las filas de plan-frontend §8 (node:test T, vite build A, capturas I, validar-lectura T).
- [ ] **baja** · `specs/decisiones-backend.md:89` — decisiones §3 punto 2 y el código y la spec no dicen lo mismo sobre en qué estado actúa el Bibliotecario.
  - Arreglo: La sesión de backend decide cuál de las dos vale y alinea decisiones §3.2 o maquina.py; después, formal ajusta EnBucle y DesenlaceCapitulo o anota la diferencia en plan-formal §4.
- [ ] **baja** · `specs/decisiones-backend.md:96` — El fichero Lean se guarda por ciclo (verificacion/ciclo-k/), mientras que AJ-3 decide que los gates se guarden por pasada porque los ciclos se repiten.
  - Arreglo: Cambiar la ruta a verificacion/pasada-p/cronologia.lean (proyecto.pasadas) en decisiones §3.9 y shared/rutas.py, y avisar a formal para corregir plan-formal §3.3.
- [ ] **baja** · `docs/architecture.md:222` — architecture §3.3 y §3.1 dicen que cambio_solicitado solo sale con una acción humana, pero el código y la spec tienen la salida automática tope_agotado, e Inv5 solo protege cambio_solicitado cuando el cambio ya está propuesto.
  - Arreglo: Al cerrar el bloque, recoger en architecture §3.1 (diagrama y fila de cambio_solicitado) y §3.3 que la parada es la confirmación del cambio propuesto y que el tope del Intérprete devuelve a publicada con el cambio fallido.
- [ ] **baja** · `specs/decisiones-backend.md:128` — El contrato Lean exige una franja (`manana`, `tarde`, `noche`) en cada evento de la historia, pero ninguna decisión dice de dónde sale: la ficha y el Bibliotecario solo manejan días.
  - Arreglo: Decidir en B-6 o B-16 que el Bibliotecario registra la franja de cada evento (o qué valor se usa por defecto y cómo se evita el falso positivo), y reflejarlo en el esquema de su herramienta de escritura.
- [ ] **baja** · `docs/iteraciones.md:36` — Lo que cuenta el registro es cierto, pero le faltan episodios que ya están documentados en otros ficheros como descubrimientos en esta máquina.
  - Arreglo: Añadir I-07 (Lean: BOM y `decide +kernel`), I-08 (sonda de Claude Code S-1..S-10) e I-09 (revisión de diseño formal → AJ-2..AJ-6), con los datos que aporten las sesiones formal y de agentes; las dos primeras se reconstruyen desde plan-formal y plan-agentes y lo dicen.
- [ ] **baja** · `docs/red-team.md:11` — red-team.md dice que E2 son dos ataques (dos entradas), y el brief E2 define cuatro vectores y pide una entrada por vector.
  - Arreglo: Cambiar el ejemplo de red-team.md L11 a los cuatro vectores del brief (cuatro entradas), o acordar con la sesión de briefs el número y ajustar e2 L114.
