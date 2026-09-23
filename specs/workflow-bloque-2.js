export const meta = {
  name: 'backend-bloque-2',
  description: 'Bloque 2 del backend (pasos 4-8): base de datos y contratos, cinco piezas en paralelo, revisión, corrección y documentos',
  phases: [
    { title: 'Base', detail: 'esquema, acceso a la biblia y contratos entre piezas' },
    { title: 'Piezas', detail: 'cerebro, planificación, Recuperador, verificadores y MCP en paralelo' },
    { title: 'Revisión', detail: 'un revisor: integración, conformidad y robustez' },
    { title: 'Corrección', detail: 'integrar y arreglar lo confirmado' },
    { title: 'Documentos', detail: 'pasada única de docs/ (bloques 1 y 2)' },
  ],
}

const REPO = 'C:\\Users\\student\\Documents\\GitHub\\my-story-marker'

const REPORT = {
  type: 'object',
  properties: {
    resumen: { type: 'string' },
    ficheros: { type: 'array', items: { type: 'string' } },
    interfaz: { type: 'string' },
    decisiones_sobre_la_marcha: { type: 'array', items: { type: 'string' } },
    pendientes: { type: 'array', items: { type: 'string' } },
    cambios_de_documento_necesarios: { type: 'array', items: { type: 'string' } },
    comprobaciones_en_verde: { type: 'boolean' },
  },
  required: ['resumen', 'ficheros', 'interfaz', 'decisiones_sobre_la_marcha', 'pendientes', 'comprobaciones_en_verde'],
}
const FINDINGS = {
  type: 'object',
  properties: {
    hallazgos: { type: 'array', items: { type: 'object', properties: {
      fichero: { type: 'string' }, linea: { type: 'integer' }, severidad: { type: 'string', enum: ['alta', 'media', 'baja'] },
      resumen: { type: 'string' }, evidencia: { type: 'string' }, arreglo_sugerido: { type: 'string' } },
      required: ['fichero', 'severidad', 'resumen', 'evidencia'] } },
    suite_completa: { type: 'string', description: 'resultado de uv run --frozen pytest completo, mypy y ruff' },
  },
  required: ['hallazgos', 'suite_completa'],
}
const FIXES = {
  type: 'object',
  properties: {
    resultados: { type: 'array', items: { type: 'object', properties: {
      resumen: { type: 'string' }, desenlace: { type: 'string', enum: ['arreglado', 'descartado', 'pendiente'] }, motivo: { type: 'string' } },
      required: ['resumen', 'desenlace', 'motivo'] } },
    decisiones_sobre_la_marcha: { type: 'array', items: { type: 'string' } },
    cambios_de_documento_necesarios: { type: 'array', items: { type: 'string' } },
    comprobaciones_en_verde: { type: 'boolean' },
  },
  required: ['resultados', 'comprobaciones_en_verde'],
}
const DOCS = {
  type: 'object',
  properties: {
    tocados: { type: 'array', items: { type: 'object', properties: { documento: { type: 'string' }, que: { type: 'string' } }, required: ['documento', 'que'] } },
    no_aplicaba: { type: 'array', items: { type: 'object', properties: { documento: { type: 'string' }, por_que: { type: 'string' } }, required: ['documento', 'por_que'] } },
    comprobaciones_en_verde: { type: 'boolean' },
  },
  required: ['tocados', 'no_aplicaba', 'comprobaciones_en_verde'],
}

const REGLAS = `
Reglas de este trabajo (además de AGENTS.md y CLAUDE.md, que ya tienes):
- Repositorio: ${REPO}, rama project-v2-avance. No hagas commit ni push. No toques .claude/, formal/, frontend/ ni evals/: puedes leerlos. evals/comprobar.py importa backend.contexto.modelos.Personalizacion, backend.contexto.validacion.validar, backend.intake.datos_excluidos.depurar y backend.intake.router.Brief: no los renombres.
- Mandan specs/decisiones-backend.md (§0 recortes, §1 B-n, §2 TC-n, §2.1 AJ-n, §3 contradicciones resueltas, §4.1 a §4.3 contratos) y specs/contexto-tras-bloque1.md (§4 lo construido, §5.1 lo que toca, §6 lecciones). Las decisiones están cerradas. Si falta algo menor, decide lo más coherente y apúntalo en decisiones_sobre_la_marcha. Si algo contradice esos ficheros o docs/, no lo implementes: apúntalo en pendientes.
- VOLUMEN CONTENIDO: el tiempo del bloque 1 se fue en escribir de más. Código compacto, sin abstracciones especulativas. Pruebas solo para los criterios V-n de tu encargo, más un caso de control por regla. Sin baterías extra.
- Mientras trabajas, ejecuta solo las pruebas de tu carpeta: uv run --frozen pytest -q -p no:cacheprovider backend/<tu carpeta>. Al final, uv run --frozen mypy, uv run --frozen ruff check y uv run --frozen ruff format --check. La batería completa (unos 95 s) la ejecuta el revisor.
- Estilo del código existente: identificadores y docstrings en español que citan RF/V; conexiones solo con backend/shared/db.py y rutas solo con backend/shared/rutas.py (V-24); escrituras dentro de transaccion(); el tiempo entra como parámetro; tablas STRICT con CHECK de lista cerrada iguales a los enums de shared/tipos.py. Ficheros con saltos LF: si los escribes con un script, usa newline="\\n". Sin dependencias nuevas (uv add prohibido) y sin cosmic-ray.
- Hay otros agentes editando a la vez en otras carpetas: toca solo lo tuyo. Si falla un módulo ajeno, repite una vez y no lo arregles tú; apúntalo.
- Lee antes .claude/skills/sqlite/SKILL.md, y .claude/skills/fastapi/SKILL.md si tocas FastAPI.`

const CONTRATOS = `
Contratos entre las piezas de este bloque. Úsalos EXACTAMENTE así: los implementan agentes distintos a la vez.
- Manejadores: cada rebanada con agentes expone en <rebanada>/manejadores.py un MANEJADORES: Mapping[Agente, Manejador], con el tipo Manejador que define la base en backend/proyecto/manejadores.py (ver su interfaz). backend/proyecto/ los agrega.
- backend/planificacion/materializar.py: materializar_contexto(conexion, contexto, momento) -> None. Lo escribe la base; el cerebro lo llama al pasar de contexto a planificacion.
- backend/capitulo/ensamblado.py: preparar_prompt(conexion: sqlite3.Connection, disposicion: DisposicionProyecto, numero: int, version: int, intento: int, informe_anterior: str | None, momento: str) -> PromptPreparado, con PromptPreparado (dataclass congelada del mismo módulo) = {rutas_partes: tuple[Path, ...], ruta_completa: Path, ruta_desglose: Path, tokens_estimados: int}. Si no cabe (D-9) o hay una inconsistencia de B-9, lanza ErrorEnsamblado(causa: str, detalle: dict). Lo escribe el agente del Recuperador; el cerebro lo llama para construir entrada.rutas_prompt (rutas absolutas) de la orden del escritor.
- backend/proyecto/sello.py: orden_de_sello(conexion, sello: str) -> la orden vigente, o lanza SelloInvalido si el sello no es el vigente (AJ-4). Lo escribe el agente del cerebro; lo usan las herramientas de /mcp/escritura.
- Las lecturas y escrituras de la biblia son las funciones de backend/capitulo/biblia.py que deja la base; nadie más escribe SQL de la biblia.`

const PROMPT_BASE = `Construye la BASE del bloque 2 del backend: el modelo de datos, su acceso y los contratos. Cuando termines, cinco agentes trabajarán a la vez sobre lo que dejes (cerebro, planificación y escaleta, Recuperador, verificadores y MCP), así que tu interfaz tiene que ser precisa.
${REGLAS}
${CONTRATOS}
Lee specs/decisiones-backend.md y specs/contexto-tras-bloque1.md; docs/architecture.md §6 y §6.1 a §6.3; specs/spec1.md §4.4 a §4.6 y §6; y el código de backend/shared, backend/contexto y backend/proyecto.
1. Esquema (backend/shared/esquema.sql y tipos.py):
   - B-2: historia por capítulo para el estado de personaje, lo que sabe y el estado de localización (columna capitulo desde la que vale; 0 = estado inicial). El glosario gana capitulo, referencia y tipo (B-10). Tabla objeto (id, nombre, alias). inventario admite el capítulo 0.
   - personaje y localizacion ganan nombre, alias y descripcion donde B-4 lo pide. ficha_capitulo se amplía según B-5, con ficha_capitulo_hito (B-3). presagio gana clave y estado (previsto, plantado o cobrado; B-16).
   - dia_fin y localizacion_fin por versión de capítulo (B-6, B-16). resumen con versión.
   - proyecto.pasadas (AJ-3) y proyecto.generacion_bloqueo (AJ-4). orden gana sello y metadatos (§4.1.8). capitulo_version gana ruta_borrador (§4.1.5).
   - Un informe único por (capitulo_version, verificador). Índice único de palabra_prohibida con coalesce(publico, ''). Tabla gate_resultado(pasada, gate, ok, detalle), para el paso 8a.
   - El enum Agente pasa a los 12 agentes (R-1, AJ-1).
2. Ontología: B-18, excluye {fuente, tipo: muerte|partida} en los hechos de tipo evento (contexto/modelos.py), con la regla de validación de que la fuente existe, y su prueba. No rompas el contexto válido de referencia.
3. Rutas (shared/rutas.py): borrador(n, v, i); las partes del prompt, …prompt.parte-N.md; y verificacion/pasada-k/.
4. Acceso a datos:
   - backend/capitulo/biblia.py:
     - lecturas «a fecha N−1» (B-2): estado y saber de los presentes, inventario vivo, presagios pendientes, la localización con sus ascendientes, las reglas, el glosario y el resumen acumulado compactado (§6.2);
     - las dos comprobaciones de B-9 y R-2, que devuelven hallazgos: presentes excluidos a fecha N−1, contando los eventos del contexto como capítulo 0 y sin bloquear a los mencionados; y el salto de días imposible según la ruta;
     - las escrituras del Bibliotecario, etiquetadas con capítulo, y el borrado de B-16 de lo escrito para un capítulo;
     - lecturas para MCP: el contexto sin el texto libre, el plan, una ficha y la guía (§4.1.6).
   - backend/planificacion/consultas.py y backend/escaleta/consultas.py: guardar y leer el plan, los personajes, el mundo, la guía y las fichas.
   - backend/planificacion/materializar.py, según el contrato: B-1 con personajes y localizaciones antes que los eventos, y B-18.
5. Solo el tipo Manejador y la forma en que el cerebro agrega los MANEJADORES de cada rebanada, en backend/proyecto/manejadores.py. Los manejadores de los agentes nuevos los escriben los demás; los que ya existen siguen funcionando.
Pruebas mínimas: la del esquema frente a los tipos (ya existe), una propiedad de «a fecha N−1» (base de V-22), la materialización, y B-9 con un caso que dispara y uno de control.
En interfaz: las tablas y columnas nuevas con sus tipos, y las firmas públicas de biblia.py, consultas.py, materializar.py y Manejador, con cada excepción.`

const piezas = (base) => [
  { key: 'cerebro', prompt: `Pieza CEREBRO del bloque 2. Tus carpetas son backend/proyecto/, y además backend/mcp/entrada.py e backend/intake/entrada.py solo para el registro de canjes.
Informe de la base: ${JSON.stringify(base)}
${REGLAS}
${CONTRATOS}
Hazlo:
1. Aplica AJ-1 a AJ-5 de decisiones §2.1.
2. Aplica el contrato final de /resultado (§4.1, puntos 1, 2, 3, 7 y 8): el cuerpo es {orden: sello, salida_cruda, metadatos?}. Extraes el sello (opcional), el Markdown del escritor, el editor y el revisor ({titulo, texto}) y el único bloque JSON del resto. Una salida mal formada es un fallo de forma y gasta intento. Guarda metadatos con la orden y retira el campo resultado.
3. La respuesta de /siguiente lleva sello.
4. POST /proyectos/{id}/auditoria (§4.1.9).
5. Registra en llamada_mcp cada canje de /mcp/entrada (§4.1.10).
6. backend/proyecto/sello.py, según el contrato.
7. Agrega los MANEJADORES de planificacion, escaleta y capitulo: los escriben otros agentes ahora mismo.
8. Llama a materializar_contexto al pasar de contexto a planificacion.
9. entrada.rutas_prompt de la orden del escritor, con preparar_prompt; ErrorEnsamblado se convierte en la decisión error con causa (AJ-5).
10. Las acciones humanas de las paradas: POST /proyectos/{id}/plan/aprobacion (RF-36) y POST /proyectos/{id}/aprobacion-final (RF-05).
11. Revisión capítulo a capítulo con el Bibliotecario (AJ-2).
Pruebas: el sello viejo se rechaza al cambiar el titular del bloqueo (V-34 con la generación); salida_cruda en Markdown, en JSON y mal formada; las pasadas; la auditoría; las paradas por API (V-14). Amplía V-33 y V-2 solo a lo nuevo.` },
  { key: 'planificacion', prompt: `Pieza PLANIFICACIÓN Y ESCALETA (paso 4). Tus carpetas son backend/planificacion/ y backend/escaleta/, salvo consultas.py y materializar.py, que ya dejó la base y solo tocas si les falta algo mínimo.
Informe de la base: ${JSON.stringify(base)}
${REGLAS}
${CONTRATOS}
Hazlo:
1. Modelos de salida (RF-77a):
   - del planificador: las cuatro partes de B-3 y B-4, que extienden los modelos del contexto; según B-1 no puede contradecirlo;
   - del escaletista: B-5.
2. MANEJADORES de las dos rebanadas:
   - el del planificador valida contra el contexto (B-1), persiste con consultas.py y siembra el glosario;
   - el del escaletista valida RF-41 (diferencia menor que 1 con 10·p/100), RF-42 (cada hito en exactamente una ficha) y RF-43 (todo lo que se planta se cobra más tarde); pasa las comprobaciones de B-9 de biblia.py; crea los presagios previstos desde plantar (B-16); y avisa de los hechos obligatorios que no usa ninguna ficha.
3. Rutas GET /proyectos/{id}/plan (RF-35) y GET /proyectos/{id}/escaleta. No hagas PUT: la salida del agente entra por /resultado.
Pruebas: V-21, con hito ausente y hito duplicado, más un caso de control. Y una salida del planificador que contradice el contexto.` },
  { key: 'recuperador', prompt: `Pieza RECUPERADOR (paso 6). Tus ficheros son backend/capitulo/estimador.py, recuperacion_estructurada.py, similitud.py y ensamblado.py, y sus pruebas en backend/capitulo/tests/.
Informe de la base: ${JSON.stringify(base)}
${REGLAS}
${CONTRATOS}
Lee docs/architecture.md §6.3 entero y specs/spec1.md RF-50 a RF-59b.
Hazlo:
1. estimador: tiktoken o200k_base × 1,35, con TIKTOKEN_CACHE_DIR apuntando a backend/capitulo/bpe y sin red (RF-52a a 52c).
2. recuperacion_estructurada: los bloques salen de biblia.py y de consultas. Determinismo byte a byte: ORDER BY, JSON con claves ordenadas, NFC y saltos \\n.
3. similitud: siempre la lista vacía (RF-57).
4. ensamblado.preparar_prompt, según el contrato:
   - los bloques y prioridades de §6.3 más B-8: los vacíos opcionales llevan «Ninguno.»; el bloque «Informe del intento anterior»; los vetos, las frases literales y la lista negra van dentro de la ficha;
   - recorte por unidades completas, siempre declarado (RF-53, 53a y 54);
   - desglose (RF-59b);
   - partes de 20.000 tokens estimados como mucho, más el fichero completo y el desglose, en las rutas de shared/rutas.py (§4.1.4, RF-58);
   - las comprobaciones de B-9 de biblia.py antes de ensamblar: una inconsistencia lanza ErrorEnsamblado(causa='inconsistencia');
   - si no cabe ni con la ficha sola: ErrorEnsamblado(causa='no_cabe') con el desglose (D-9).
Pruebas: V-3a (una propiedad, misma entrada → mismos bytes), V-5 (propiedad con una biblia sintética grande: nunca se pasa del tope, todo recorte queda en el informe, ninguna unidad sale cortada), V-23 (similitud vacía sin encabezado; estructurada vacía, error) y V-4 (del desglose al fichero de prompt).` },
  { key: 'verificadores', prompt: `Pieza VERIFICADORES (paso 7). Tus ficheros son backend/capitulo/segmentacion.py, backend/capitulo/verificadores/ (un módulo por verificador o pocos), backend/capitulo/listas/ (las listas del guardarraíl, versionadas), backend/capitulo/modelos_salida.py, backend/capitulo/manejadores.py y sus pruebas.
Informe de la base: ${JSON.stringify(base)}
${REGLAS}
${CONTRATOS}
Lee specs/spec1.md §4.6.3 y docs/architecture.md §4 y §4.3.
Hazlo:
1. segmentacion (B-14), con la definición de párrafo de decisiones.
2. Los verificadores, todos con la misma firma, que devuelven un Informe y nunca corrigen (RN-6):
   - longitud (RF-70 y RF-79, con la desviación en metricas);
   - métricas e INFLESZ (RF-71, D-6);
   - lista negra (RF-72);
   - guardarraíl de tres niveles (RF-72a, B-11 y B-12): listas global e infantil en ficheros con su hash, copiadas a palabra_prohibida al crear el proyecto (o de forma perezosa al primer uso), más los vetos de la novela; la auditoría sin el término literal; la regla de agotamiento de B-12;
   - nombres, solo la regla de grafía (RF-73, R-2 y B-10);
   - frases literales (RF-73a).
   No hagas Repeticiones (R-3) ni continuidad sobre el texto (R-2).
3. Modelos de salida (RF-77a):
   - escritor, editor y revisor: {titulo, texto};
   - juez de capítulo: B-15, con el criterio contenido; la severidad la pone el backend; la salida es inválida si una cita no aparece en el texto;
   - bibliotecario: B-16, casi vacío, con la comprobación de que está todo lo que se exige.
4. MANEJADORES de capitulo/:
   - escritor: guarda el borrador en su fichero y capitulo_version;
   - editor: guarda el editado, ejecuta los verificadores y devuelve el desenlace (RF-77);
   - juez de capítulo: aplica las severidades de architecture §4;
   - bibliotecario: la comprobación de B-16;
   - revisor: como el editor, sobre la versión corregida.
Pruebas: V-15 por regla (R-5): cada regla con un caso que la dispara y otro de control. V-26: un caso por nivel del guardarraíl y otro de variante con acento o plural. V-28: frases literales. V-35: una salida válida y otra mal formada por agente. V-7: capítulo de tamaño máximo por debajo de un umbral de tiempo.` },
  { key: 'mcp', prompt: `Pieza MCP (pasos 5 y 8). Tus ficheros son backend/mcp/lectura.py, backend/mcp/escritura.py, sus pruebas y el montaje en backend/app.py.
Informe de la base: ${JSON.stringify(base)}
${REGLAS}
${CONTRATOS}
Lee docs/architecture.md §7 y §8 y specs/spec1.md RF-100 a RF-106. Mira cómo se hizo backend/mcp/entrada.py con FastMCP 4.0.5 y cómo se monta en backend/app.py, con los lifespans combinados, y haz lo mismo.
Hazlo:
1. /mcp/lectura/: las herramientas tipadas de RF-103 más las de §4.1.6, que delegan en biblia.py y en consultas. Nunca SQL libre (RF-100).
2. /mcp/escritura/: las herramientas de RF-104 (hechos nuevos; estado de personajes y objetos; cerrar presagios; resumen de capítulo y de acto con los topes de B-17; hecho_uso; dia_fin y localizacion_fin):
   - cada una recibe el sello y lo valida con orden_de_sello (AJ-4);
   - toman el capítulo de la orden y no de un argumento (B-16);
   - rechazan la escritura si el capítulo no está en verificado o posterior (RF-106);
   - escriben con biblia.py.
3. Registra cada llamada en llamada_mcp (RF-105), sin texto libre.
4. Monta las dos superficies en app.py.
Pruebas: V-19 (rechazada antes de verificado, aceptada después); el sello viejo, rechazado; que la escritura solo existe en /mcp/escritura (el lado de V-13 que toca al backend); y el contrato de forma de cada herramienta.` },
]

phase('Base')
const base = await agent(PROMPT_BASE, { label: 'b2:base', phase: 'Base', schema: REPORT })
if (!base) return { error: 'la base no terminó' }
log('Base lista; arrancan las cinco piezas en paralelo')

phase('Piezas')
const informes = await parallel(piezas(base).map(p => () =>
  agent(`${p.prompt}`, { label: `b2:${p.key}`, phase: 'Piezas', schema: REPORT })
))
const todos = { base, piezas: informes }

phase('Revisión')
const revision = await agent(`Revisa el bloque 2 del backend recién construido en ${REPO}; el cambio va desde el commit e735f3b (git diff e735f3b). Informes de los agentes: ${JSON.stringify(todos)}
${REGLAS}
NO edites ficheros. PRIMERO ejecuta la batería completa (uv run --frozen pytest -q -p no:cacheprovider), mypy y ruff, y apunta el resultado en suite_completa: son piezas de cinco agentes y puede haber roturas de integración entre ellas. Después revisa tres cosas:
- la integración: que se cumplen los contratos entre piezas y que el cerebro agrega los manejadores y llama a preparar_prompt y a materializar_contexto;
- la conformidad con specs/decisiones-backend.md y con los RF de los pasos 4 a 8 (RF-30 a 43, 50 a 59b, 60 a 62, 65, 70 a 79, 80 a 89 y 100 a 106);
- la robustez: idempotencia, sellos, RF-106, determinismo byte a byte y el tope de tokens.
Solo problemas comprobados, con fichero, línea y evidencia. Como mucho 15, los más graves primero.`, { label: 'b2:revision', phase: 'Revisión', schema: FINDINGS })

phase('Corrección')
const correccion = await agent(`Integra y corrige el bloque 2 en ${REPO}. Eres el único agente editando.
Resultado de la revisión (suite y hallazgos): ${JSON.stringify(revision)}
Informes de los agentes: ${JSON.stringify(todos)}
${REGLAS}
Primero deja en verde la batería completa y las cuatro comprobaciones: arregla las roturas de integración. Después, cada hallazgo: intenta refutarlo; si es real, arréglalo con una prueba que falle sin el arreglo; si exige reabrir una decisión, déjalo pendiente. Termina con uv run --frozen pytest, mypy, ruff check y ruff format --check en verde.`, { label: 'b2:correccion', phase: 'Corrección', schema: FIXES })

phase('Documentos')
const documentos = await agent(`Pasada ÚNICA y BREVE de documentación (AGENTS.md, regla 3) por los bloques 1 y 2 del backend en ${REPO}. Eres el único agente editando.
Aplica la lista de specs/decisiones-backend.md §4.4 y lo que pidan los cambios_de_documento_necesarios de estos informes: ${JSON.stringify({ todos, correccion })}
Documentos que tocar: docs/architecture.md (§2, §3, §3.1 con las aristas de Q6, §3.2, §6, §7 con la pila del frontend y sin cosmic-ray, y §8), specs/spec1.md (RF-05a, RF-14, RF-07a y RF-63 según Q5, RF-64b, RF-74 y 75 según R-2, V-15, V-17, D-7, §1.2, §5.1 y §6), docs/validators.md (V-15 y las filas del frontend de plan-frontend §8), docs/definitions.md (§6 y §9: B-18 y B-19), specs/plan-backend-v1.md (pasos 2 a 8 hechos, E-6) y specs/plan-entrega.md (§1, E-5 rechazada, E-6 decidida y briefs en JSON).
Cambia solo lo que el código ya hace: los docs siguen al código. Mermaid válido, con el estilo existente. Sé breve: nada de reescribir secciones enteras. Añade una entrada al día en docs/iteraciones.md. Al final, uv run --frozen pytest backend/tests (V-10 lee architecture §7). No hagas commit.`, { label: 'b2:documentos', phase: 'Documentos', schema: DOCS })

return { base, piezas: informes, revision, correccion, documentos }
