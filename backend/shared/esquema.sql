-- Esquema de la base de un proyecto: un fichero SQLite por proyecto (spec-backend-1.md §6, C-2).
--
-- Convenciones:
--   · Todas las tablas son STRICT: SQLite sin STRICT acepta "hola" en una columna INTEGER.
--   · Enumerados como CHECK con lista cerrada; las listas de estado coinciden con
--     shared/tipos.py (lo comprueba una prueba).
--   · Fechas en texto ISO-8601 UTC. Booleanos como INTEGER 0/1.
--   · JSON como TEXT con CHECK (json_valid(...)).
--   · Rutas de fichero relativas al directorio del proyecto, con barras de POSIX (RNF-08).
--     Texto de capítulo, prompts y exportaciones son ficheros, no blobs (C-4).
--   · Cada paso del plan afina las columnas de sus tablas; no hay migraciones en la v1
--     (spec-backend-1.md §2.5).
--   · Biblia con historia por capítulo (B-2): la fila de estado vale desde su `capitulo`,
--     0 es el estado inicial de la planificación, y toda lectura es «a fecha N−1». El SQL
--     de estas tablas vive en capitulo/biblia.py y, para la siembra, en
--     planificacion/materializar.py, planificacion/consultas.py y escaleta/consultas.py.

BEGIN;

-- ─── Transversal · proyecto/ ────────────────────────────────────────────────

-- Una sola fila: la base es del proyecto. El directorio no se guarda: es el que contiene
-- este fichero y lo deriva shared/rutas.py del identificador (V-24).
CREATE TABLE proyecto (
  id                 INTEGER PRIMARY KEY CHECK (id = 1),
  identificador      TEXT    NOT NULL,
  -- Nombre legible que pone quien crea el proyecto; el identificador sigue siendo opaco.
  -- Puede llevar datos de persona: se muestra en el panel, nunca en rutas ni en logs.
  etiqueta           TEXT    CHECK (etiqueta IS NULL OR length(etiqueta) BETWEEN 1 AND 60),
  version_ontologia  TEXT,
  estado             TEXT    NOT NULL DEFAULT 'intake' CHECK (estado IN (
                       'intake', 'contexto', 'planificacion', 'aprobacion_plan', 'escaleta',
                       'capitulos', 'verificacion_manuscrito', 'revision', 'aprobacion_final',
                       'publicacion', 'publicada', 'cambio_solicitado', 'regeneracion',
                       'detenida')),
  -- De qué fase viene `detenida`: «reintentar» vuelve a ella. La lista son los orígenes
  -- de las aristas a `detenida` de proyecto/transiciones.py (lo comprueba una prueba).
  detenida_desde     TEXT    CHECK (detenida_desde IN (
                       'intake', 'contexto', 'planificacion', 'escaleta', 'capitulos',
                       'verificacion_manuscrito', 'revision', 'publicacion')),
  parada_plan        INTEGER NOT NULL DEFAULT 0 CHECK (parada_plan IN (0, 1)),
  parada_final       INTEGER NOT NULL DEFAULT 0 CHECK (parada_final IN (0, 1)),
  ciclos_revision    INTEGER NOT NULL DEFAULT 0 CHECK (ciclos_revision BETWEEN 0 AND 3),
  -- RF-07a: intentos de la orden en curso que no es ciclo de capítulo, y de los agentes
  -- posteriores al Escritor dentro del capítulo. Vuelve a cero en cada avance.
  intentos_paso      INTEGER NOT NULL DEFAULT 0 CHECK (intentos_paso BETWEEN 0 AND 3),
  -- AJ-3: suma 1 cada vez que se entra en verificacion_manuscrito; nunca vuelve a cero.
  pasadas            INTEGER NOT NULL DEFAULT 0 CHECK (pasadas >= 0),
  -- AJ-4: suma 1 cada vez que toma el bloqueo un titular distinto o uno que había caducado.
  generacion_bloqueo INTEGER NOT NULL DEFAULT 0 CHECK (generacion_bloqueo >= 0),
  -- RF-09b: el titular es un token opaco; el tipo dice si es la sesión o el worker.
  bloqueo_titular    TEXT,
  bloqueo_tipo       TEXT    CHECK (bloqueo_tipo IN ('sesion', 'worker')),
  bloqueo_caduca     TEXT,
  creado             TEXT    NOT NULL,
  CHECK ((bloqueo_titular IS NULL) = (bloqueo_caduca IS NULL)),
  CHECK ((bloqueo_titular IS NULL) = (bloqueo_tipo IS NULL)),
  CHECK ((estado = 'detenida') = (detenida_desde IS NOT NULL))
) STRICT;

-- RF-03, RF-08a: una fila por orden emitida, persistida antes de devolverse a la sesión.
-- La vigente es la que no está cerrada, y el índice único parcial impide que haya dos.
-- `detalle` guarda la huella del resultado registrado (RF-06) y su informe, que la orden
-- siguiente lleva como entrada cuando es un reintento.
CREATE TABLE orden (
  id               INTEGER PRIMARY KEY,
  estado_proyecto  TEXT    NOT NULL CHECK (estado_proyecto IN (
                     'intake', 'contexto', 'planificacion', 'aprobacion_plan', 'escaleta',
                     'capitulos', 'verificacion_manuscrito', 'revision', 'aprobacion_final',
                     'publicacion', 'publicada', 'cambio_solicitado', 'regeneracion',
                     'detenida')),
  agente           TEXT    NOT NULL CHECK (agente IN (
                     'agente-contexto', 'extractor-hechos', 'planificador', 'escaletista',
                     'escritor', 'editor-estilo', 'juez-capitulo', 'bibliotecario',
                     'juez-manuscrito', 'revisor', 'exportador', 'interprete-cambios')),
  capitulo         INTEGER REFERENCES capitulo (numero),
  intento          INTEGER NOT NULL CHECK (intento BETWEEN 1 AND 3),
  entrada          TEXT    NOT NULL CHECK (json_valid(entrada)),
  emitida          TEXT    NOT NULL,
  cerrada          TEXT,
  desenlace        TEXT    CHECK (desenlace IN ('aceptada', 'rechazada', 'caducada')),
  detalle          TEXT    CHECK (detalle IS NULL OR json_valid(detalle)),
  -- AJ-4, §4.1.2: `<proyecto>:<orden>:<generación>`; cambia al volver a sellar la orden.
  sello            TEXT    UNIQUE,
  -- §4.1.8: modelo, tokens y duración que envía el hook con el resultado; todo opcional.
  metadatos        TEXT    CHECK (metadatos IS NULL OR json_valid(metadatos)),
  CHECK ((cerrada IS NULL) = (desenlace IS NULL))
) STRICT;

CREATE UNIQUE INDEX orden_una_vigente ON orden ((cerrada IS NULL)) WHERE cerrada IS NULL;

-- RF-09: historial append-only.
CREATE TABLE transicion (
  id       INTEGER PRIMARY KEY,
  momento  TEXT NOT NULL,
  origen   TEXT NOT NULL,
  destino  TEXT NOT NULL,
  causa    TEXT NOT NULL
) STRICT;

CREATE TRIGGER transicion_sin_update BEFORE UPDATE ON transicion
BEGIN SELECT RAISE(ABORT, 'transicion es append-only (RF-09)'); END;
CREATE TRIGGER transicion_sin_delete BEFORE DELETE ON transicion
BEGIN SELECT RAISE(ABORT, 'transicion es append-only (RF-09)'); END;

-- Aprobaciones, confirmaciones y reintentos: la única salida de las paradas humanas.
CREATE TABLE decision_humana (
  id        INTEGER PRIMARY KEY,
  momento   TEXT NOT NULL,
  tipo      TEXT NOT NULL CHECK (tipo IN (
              'aprobacion_plan', 'aprobacion_final', 'confirmacion_hechos', 'reintentar',
              'confirmacion_cambio')),
  decision  TEXT NOT NULL CHECK (decision IN (
              'aprobado', 'cambios', 'confirmado', 'rechazado', 'reintentar')),
  notas     TEXT,
  -- M-6: los capítulos que revisar tras «cambios» en `aprobacion_final` (todos, si no dijo).
  capitulos TEXT CHECK (capitulos IS NULL OR (json_valid(capitulos)
                                              AND json_type(capitulos) = 'array'))
) STRICT;

-- Descartes de datos personales (tipo, nunca el valor), coincidencias del guardarraíl
-- y decisiones del hook de policy.
CREATE TABLE auditoria (
  id       INTEGER PRIMARY KEY,
  momento  TEXT NOT NULL,
  tipo     TEXT NOT NULL CHECK (tipo IN ('descarte_dato_personal', 'guardarrail', 'policy')),
  detalle  TEXT NOT NULL CHECK (json_valid(detalle))
) STRICT;

-- RF-14, RF-120: identificadores opacos de un solo uso para /mcp/entrada. Se guarda la
-- huella SHA-256 del secreto, no el secreto: el identificador entero solo viaja en la
-- entrada de la orden que lo lleva (intake/entrada.py).
CREATE TABLE identificador_entrada (
  huella      TEXT PRIMARY KEY CHECK (length(huella) = 64),
  recurso     TEXT NOT NULL CHECK (recurso IN ('texto_libre', 'peticion')),
  ruta        TEXT NOT NULL,
  emitido     TEXT NOT NULL,
  caduca      TEXT NOT NULL,
  consumido   TEXT,
  CHECK (caduca > emitido),
  CHECK (consumido IS NULL OR consumido >= emitido)
) STRICT;

CREATE TABLE cache (
  clave   TEXT PRIMARY KEY,
  valor   TEXT NOT NULL,
  creado  TEXT NOT NULL
) STRICT;

CREATE TABLE llamada_mcp (
  id          INTEGER PRIMARY KEY,
  momento     TEXT NOT NULL,
  agente      TEXT,
  herramienta TEXT NOT NULL,
  argumentos  TEXT NOT NULL CHECK (json_valid(argumentos)),
  resultado   TEXT NOT NULL CHECK (json_valid(resultado))
) STRICT;

-- ─── intake/ y contexto/ ────────────────────────────────────────────────────

-- `extraccion`: la orden del Extractor que extrajo el texto libre vigente (RF-14, RF-15). Es
-- NULL si aún no se ha extraído, y vuelve a NULL si el comprador cambia el texto.
CREATE TABLE brief (
  id                INTEGER PRIMARY KEY CHECK (id = 1),
  respuestas        TEXT NOT NULL CHECK (json_valid(respuestas)),
  ruta_texto_libre  TEXT,
  normalizado       TEXT CHECK (normalizado IS NULL OR json_valid(normalizado)),
  extraccion        INTEGER REFERENCES orden (id),
  creado            TEXT NOT NULL,
  CHECK (extraccion IS NULL OR ruta_texto_libre IS NOT NULL)
) STRICT;

CREATE TABLE hecho_propuesto (
  id         INTEGER PRIMARY KEY,
  tipo       TEXT NOT NULL CHECK (tipo IN (
               'evento', 'rasgo', 'ser_querido', 'lugar', 'objeto', 'frase')),
  texto      TEXT NOT NULL,
  prioridad  TEXT NOT NULL CHECK (prioridad IN ('obligatorio', 'deseable')),
  momento    TEXT,
  lugar      TEXT,
  estado     TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN (
               'pendiente', 'confirmado', 'rechazado')),
  creado     TEXT NOT NULL
) STRICT;

CREATE TABLE contexto (
  id                 INTEGER PRIMARY KEY,
  version_ontologia  TEXT NOT NULL,
  contenido          TEXT NOT NULL CHECK (json_valid(contenido)),
  validado           TEXT NOT NULL
) STRICT;

-- ─── Personalización (RF-89) ────────────────────────────────────────────────

CREATE TABLE personalizacion (
  id                    INTEGER PRIMARY KEY CHECK (id = 1),
  destinatario          TEXT NOT NULL CHECK (json_valid(destinatario)),
  segundo_destinatario  TEXT CHECK (segundo_destinatario IS NULL
                                    OR json_valid(segundo_destinatario)),
  ocasion               TEXT NOT NULL CHECK (ocasion IN (
                          'cumpleanos', 'boda', 'aniversario', 'jubilacion', 'nacimiento',
                          'graduacion', 'sin_ocasion')),
  relacion              TEXT NOT NULL CHECK (relacion IN (
                          'hijo', 'pareja', 'padre_madre', 'abuelo', 'amigo', 'companero',
                          'otra')),
  edad_lector           INTEGER NOT NULL CHECK (edad_lector >= 0),
  vetos                 TEXT NOT NULL CHECK (json_valid(vetos)),
  dedicatoria           TEXT
) STRICT;

CREATE TABLE hecho (
  id         TEXT PRIMARY KEY,
  tipo       TEXT NOT NULL CHECK (tipo IN (
               'evento', 'rasgo', 'ser_querido', 'lugar', 'objeto', 'frase')),
  texto      TEXT NOT NULL,
  prioridad  TEXT NOT NULL CHECK (prioridad IN ('obligatorio', 'deseable')),
  origen     TEXT NOT NULL CHECK (origen IN ('entrevista', 'texto_libre', 'lector')),
  momento    TEXT,
  lugar      TEXT
) STRICT;

-- ─── planificacion/ ─────────────────────────────────────────────────────────

CREATE TABLE plan (
  id                  INTEGER PRIMARY KEY CHECK (id = 1),
  modelo              TEXT NOT NULL CHECK (modelo IN ('tres_actos', 'viaje_heroe', 'episodico')),
  reparto             TEXT NOT NULL CHECK (json_valid(reparto)),
  curva_tension       TEXT NOT NULL CHECK (json_valid(curva_tension)
                                           AND json_array_length(curva_tension) = 10),
  pregunta_dramatica  TEXT NOT NULL,
  tipo_final          TEXT NOT NULL CHECK (tipo_final IN (
                        'cerrado', 'abierto', 'agridulce', 'gancho_saga', 'giro_final')),
  contenido           TEXT NOT NULL CHECK (json_valid(contenido))
) STRICT;

-- B-4: `nombre` es NULL hasta la planificación, salvo el de los destinatarios, que lo fija
-- el contexto (B-1). Estado y saber no van aquí: tienen historia por capítulo (B-2).
CREATE TABLE personaje (
  id                TEXT PRIMARY KEY,
  nombre            TEXT,
  alias             TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(alias)
                                                      AND json_type(alias) = 'array'),
  descripcion       TEXT,
  origen            TEXT NOT NULL CHECK (origen IN ('real', 'ficticio')),
  fuente            TEXT,
  ficha             TEXT NOT NULL CHECK (json_valid(ficha)),
  arco              TEXT NOT NULL CHECK (arco IN (
                      'positivo', 'negativo', 'plano', 'redencion', 'corrupcion')),
  evolucion         TEXT CHECK (evolucion IS NULL OR json_valid(evolucion)),
  fecha_nacimiento  TEXT,
  CHECK ((origen = 'real') = (fuente IS NOT NULL))
) STRICT;

CREATE TABLE personaje_estado (
  personaje  TEXT    NOT NULL REFERENCES personaje (id),
  capitulo   INTEGER NOT NULL CHECK (capitulo BETWEEN 0 AND 10),
  estado     TEXT    NOT NULL,
  PRIMARY KEY (personaje, capitulo)
) STRICT;

-- Lo que sabe, un dato por fila y acumulativo: a fecha N−1 sabe lo aprendido antes de N.
CREATE TABLE personaje_sabe (
  personaje  TEXT    NOT NULL REFERENCES personaje (id),
  capitulo   INTEGER NOT NULL CHECK (capitulo BETWEEN 0 AND 10),
  dato       TEXT    NOT NULL,
  PRIMARY KEY (personaje, capitulo, dato)
) STRICT;

CREATE TABLE relacion (
  id              INTEGER PRIMARY KEY,
  origen          TEXT NOT NULL REFERENCES personaje (id),
  destino         TEXT NOT NULL REFERENCES personaje (id),
  tipo            TEXT NOT NULL CHECK (tipo IN (
                    'alianza', 'rivalidad', 'mentoria', 'familiar', 'romance', 'deuda')),
  estado_inicial  TEXT,
  estado_final    TEXT,
  UNIQUE (origen, destino, tipo),
  CHECK (origen <> destino)
) STRICT;

CREATE TABLE localizacion (
  id           TEXT PRIMARY KEY,
  nivel        TEXT NOT NULL CHECK (nivel IN ('macro', 'meso', 'micro')),
  padre        TEXT REFERENCES localizacion (id),
  nombre       TEXT,
  descripcion  TEXT,
  hito         TEXT CHECK (hito IN (
                 'detonante', 'primer_umbral', 'punto_medio', 'crisis', 'climax')),
  CHECK ((nivel = 'macro') = (padre IS NULL))
) STRICT;

CREATE TABLE localizacion_estado (
  localizacion  TEXT    NOT NULL REFERENCES localizacion (id),
  capitulo      INTEGER NOT NULL CHECK (capitulo BETWEEN 0 AND 10),
  estado        TEXT    NOT NULL,
  PRIMARY KEY (localizacion, capitulo)
) STRICT;

CREATE TABLE ruta (
  posicion      INTEGER PRIMARY KEY CHECK (posicion >= 1),
  localizacion  TEXT    NOT NULL REFERENCES localizacion (id),
  dias_viaje    INTEGER NOT NULL CHECK (dias_viaje >= 0)
) STRICT;

CREATE TABLE regla_mundo (
  id           INTEGER PRIMARY KEY,
  regla        TEXT NOT NULL,
  limites      TEXT NOT NULL,
  costes       TEXT NOT NULL,
  excepciones  TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(excepciones))
) STRICT;

-- B-4: los objetos del mundo; quién tiene cada uno lo dice `inventario`.
CREATE TABLE objeto (
  id      TEXT PRIMARY KEY,
  nombre  TEXT NOT NULL,
  alias   TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(alias) AND json_type(alias) = 'array')
) STRICT;

CREATE TABLE guia_estilo (
  id          INTEGER PRIMARY KEY CHECK (id = 1),
  narrador    TEXT NOT NULL CHECK (narrador IN (
                'primera', 'tercera_limitada', 'tercera_omnisciente', 'multiple')),
  registro    TEXT NOT NULL CHECK (registro IN ('culto', 'estandar', 'coloquial', 'arcaizante')),
  metricas    TEXT NOT NULL CHECK (json_valid(metricas)),
  lexico      TEXT NOT NULL CHECK (json_valid(lexico)),
  lista_negra TEXT NOT NULL CHECK (json_valid(lista_negra)),
  onomastica  TEXT,
  contenido   TEXT NOT NULL CHECK (json_valid(contenido))
) STRICT;

-- ─── escaleta/ ──────────────────────────────────────────────────────────────

-- B-5. Hitos, personajes y hechos van en tablas propias, no en JSON: el Recuperador arma
-- sus bloques con consultas parametrizadas por la ficha. `plantar` es [{clave,
-- descripcion}], `cobrar` [clave] y `traspasos` [{objeto, a}], tal como los da la escaleta.
CREATE TABLE ficha_capitulo (
  numero             INTEGER PRIMARY KEY CHECK (numero BETWEEN 1 AND 10),
  objetivo           TEXT    NOT NULL,
  escenas            TEXT    NOT NULL CHECK (json_valid(escenas)),
  pov                TEXT    NOT NULL REFERENCES personaje (id),
  localizacion       TEXT    NOT NULL REFERENCES localizacion (id),
  -- B-6: día previsto de la historia, D1…Dn.
  dia                INTEGER NOT NULL CHECK (dia >= 1),
  tension            INTEGER NOT NULL CHECK (tension BETWEEN 0 AND 10),
  palabras_objetivo  INTEGER NOT NULL CHECK (palabras_objetivo BETWEEN 1000 AND 1500),
  cierre             TEXT    NOT NULL CHECK (cierre IN (
                       'cliffhanger', 'pausa', 'giro', 'pregunta', 'imagen')),
  plantar            TEXT    NOT NULL DEFAULT '[]' CHECK (json_valid(plantar)),
  cobrar             TEXT    NOT NULL DEFAULT '[]' CHECK (json_valid(cobrar)),
  traspasos          TEXT    NOT NULL DEFAULT '[]' CHECK (json_valid(traspasos))
) STRICT;

-- B-3: un capítulo puede tener varios hitos, y cada hito está en una sola ficha (RF-42).
CREATE TABLE ficha_capitulo_hito (
  capitulo  INTEGER NOT NULL REFERENCES ficha_capitulo (numero),
  hito      TEXT    NOT NULL CHECK (hito IN (
              'detonante', 'primer_umbral', 'punto_medio', 'crisis', 'climax')),
  PRIMARY KEY (capitulo, hito),
  UNIQUE (hito)
) STRICT;

-- R-2: `mencionado` es quien solo sale en un recuerdo; no cuenta como presente.
CREATE TABLE ficha_capitulo_personaje (
  capitulo   INTEGER NOT NULL REFERENCES ficha_capitulo (numero),
  personaje  TEXT    NOT NULL REFERENCES personaje (id),
  papel      TEXT    NOT NULL CHECK (papel IN ('presente', 'mencionado')),
  PRIMARY KEY (capitulo, personaje)
) STRICT;

CREATE TABLE ficha_capitulo_hecho (
  capitulo  INTEGER NOT NULL REFERENCES ficha_capitulo (numero),
  hecho     TEXT    NOT NULL REFERENCES hecho (id),
  PRIMARY KEY (capitulo, hecho)
) STRICT;

-- ─── capitulo/ · versiones, estado e informes ───────────────────────────────

CREATE TABLE capitulo (
  numero           INTEGER PRIMARY KEY CHECK (numero BETWEEN 1 AND 10),
  estado           TEXT    NOT NULL DEFAULT 'pendiente' CHECK (estado IN (
                     'pendiente', 'borrador', 'editado', 'verificado', 'aprobado',
                     'revision_humana')),
  intentos         INTEGER NOT NULL DEFAULT 0 CHECK (intentos BETWEEN 0 AND 3),
  version_vigente  INTEGER
) STRICT;

-- RF-06: la idempotencia la garantiza la clave única, no una comprobación previa.
-- `ruta_borrador` es la salida del Escritor tal cual (§4.1.5); `ruta`, el texto vigente de
-- la versión, que reescribe el Editor. `dia_fin` y `localizacion_fin` los registra el
-- Bibliotecario (B-6, B-16).
CREATE TABLE capitulo_version (
  id                INTEGER PRIMARY KEY,
  capitulo          INTEGER NOT NULL REFERENCES capitulo (numero),
  version           INTEGER NOT NULL CHECK (version >= 1),
  intento           INTEGER NOT NULL CHECK (intento BETWEEN 1 AND 3),
  estado            TEXT    NOT NULL CHECK (estado IN (
                      'borrador', 'editado', 'verificado', 'aprobado', 'revision_humana')),
  ruta              TEXT    NOT NULL,
  ruta_borrador     TEXT,
  ruta_prompt       TEXT,
  semilla           TEXT,
  version_prompt    TEXT,
  version_modelo    TEXT,
  dia_fin           INTEGER CHECK (dia_fin IS NULL OR dia_fin >= 1),
  localizacion_fin  TEXT    REFERENCES localizacion (id),
  creado            TEXT    NOT NULL,
  UNIQUE (capitulo, version, intento)
) STRICT;

-- RF-78: un informe por verificador y versión de capítulo, con sus hallazgos como lista
-- JSON de `Hallazgo` (shared/tipos.py). `severidad` es la mayor, NULL si no hay hallazgos.
CREATE TABLE informe (
  id                INTEGER PRIMARY KEY,
  capitulo_version  INTEGER NOT NULL REFERENCES capitulo_version (id),
  verificador       TEXT    NOT NULL,
  severidad         TEXT    CHECK (severidad IN ('baja', 'media', 'alta', 'bloqueante')),
  hallazgos         TEXT    NOT NULL CHECK (json_valid(hallazgos)
                                            AND json_type(hallazgos) = 'array'),
  metricas          TEXT    CHECK (metricas IS NULL OR json_valid(metricas)),
  momento           TEXT    NOT NULL,
  UNIQUE (capitulo_version, verificador)
) STRICT;

-- ─── capitulo/ · biblia ─────────────────────────────────────────────────────

-- B-6: dos escalas. Un recuerdo lleva `momento` (fecha parcial o periodo, anterior a D1);
-- la historia lleva `dia` (D1…Dn) y, si se sabe, la franja. `capitulo` NULL: viene del
-- contexto (B-1) y cuenta como capítulo 0 (R-2).
CREATE TABLE evento (
  id              INTEGER PRIMARY KEY,
  descripcion     TEXT    NOT NULL,
  momento         TEXT,
  dia             INTEGER CHECK (dia IS NULL OR dia >= 1),
  franja          TEXT    CHECK (franja IN ('manana', 'tarde', 'noche')),
  lugar           TEXT    NOT NULL REFERENCES localizacion (id),
  capitulo        INTEGER CHECK (capitulo IS NULL OR capitulo BETWEEN 1 AND 10),
  excluye         TEXT    REFERENCES personaje (id),
  tipo_exclusion  TEXT    CHECK (tipo_exclusion IN ('muerte', 'partida')),
  hecho           TEXT    REFERENCES hecho (id),
  CHECK ((excluye IS NULL) = (tipo_exclusion IS NULL)),
  CHECK ((momento IS NULL) <> (dia IS NULL)),
  CHECK (franja IS NULL OR dia IS NOT NULL)
) STRICT;

CREATE TABLE evento_personaje (
  evento     INTEGER NOT NULL REFERENCES evento (id),
  personaje  TEXT    NOT NULL REFERENCES personaje (id),
  PRIMARY KEY (evento, personaje)
) STRICT;

CREATE TABLE hecho_uso (
  hecho     TEXT    NOT NULL REFERENCES hecho (id),
  capitulo  INTEGER NOT NULL CHECK (capitulo BETWEEN 1 AND 10),
  version   INTEGER NOT NULL CHECK (version >= 1),
  PRIMARY KEY (hecho, capitulo, version)
) STRICT;

-- Una fila por traspaso: desde este capítulo, el objeto lo tiene este poseedor (NULL:
-- nadie). El capítulo 0 es el poseedor inicial que da el mundo (B-4).
CREATE TABLE inventario (
  objeto    TEXT    NOT NULL REFERENCES objeto (id),
  poseedor  TEXT    REFERENCES personaje (id),
  capitulo  INTEGER NOT NULL CHECK (capitulo BETWEEN 0 AND 10),
  PRIMARY KEY (objeto, capitulo)
) STRICT;

-- B-16: nacen de `ficha.plantar` al registrar la escaleta (`plantar_en`, y `cobrar_en` si
-- alguna ficha lo cobra), o los abre el Bibliotecario de un capítulo (`abierto_en`). El
-- estado lleva historia por capítulo en `presagio_estado`, como el resto de la biblia.
CREATE TABLE presagio (
  id           INTEGER PRIMARY KEY,
  clave        TEXT    NOT NULL UNIQUE,
  descripcion  TEXT    NOT NULL,
  plantar_en   INTEGER CHECK (plantar_en BETWEEN 1 AND 10),
  cobrar_en    INTEGER CHECK (cobrar_en BETWEEN 1 AND 10),
  abierto_en   INTEGER CHECK (abierto_en BETWEEN 1 AND 10),
  CHECK ((plantar_en IS NULL) <> (abierto_en IS NULL))
) STRICT;

CREATE TABLE presagio_estado (
  presagio  INTEGER NOT NULL REFERENCES presagio (id),
  capitulo  INTEGER NOT NULL CHECK (capitulo BETWEEN 0 AND 10),
  estado    TEXT    NOT NULL CHECK (estado IN ('previsto', 'plantado', 'cobrado')),
  PRIMARY KEY (presagio, capitulo)
) STRICT;

-- B-10: `referencia` es el id del personaje, la localización o el objeto; NULL si `otro`.
CREATE TABLE glosario (
  id          INTEGER PRIMARY KEY,
  termino     TEXT    NOT NULL,
  categoria   TEXT    NOT NULL CHECK (categoria IN (
                'personaje', 'localizacion', 'objeto', 'otro')),
  referencia  TEXT,
  tipo        TEXT    NOT NULL CHECK (tipo IN ('canonico', 'alias')),
  capitulo    INTEGER NOT NULL CHECK (capitulo BETWEEN 0 AND 10),
  nota        TEXT,
  UNIQUE (termino, capitulo),
  CHECK ((categoria = 'otro') = (referencia IS NULL))
) STRICT;

-- RF-86, RF-87, B-17: `numero` es el capítulo o el acto (1 a 3); `capitulo` y `version`,
-- la versión de capítulo cuyo Bibliotecario lo escribió. No se borra al compactar.
CREATE TABLE resumen (
  id        INTEGER PRIMARY KEY,
  ambito    TEXT    NOT NULL CHECK (ambito IN ('capitulo', 'acto')),
  numero    INTEGER NOT NULL CHECK (numero >= 1),
  capitulo  INTEGER NOT NULL CHECK (capitulo BETWEEN 1 AND 10),
  version   INTEGER NOT NULL CHECK (version >= 1),
  texto     TEXT    NOT NULL,
  creado    TEXT    NOT NULL,
  UNIQUE (ambito, numero, capitulo, version),
  CHECK (ambito = 'acto' OR numero = capitulo),
  CHECK (ambito = 'capitulo' OR numero BETWEEN 1 AND 3)
) STRICT;

-- ─── Guardarraíl y jueces ───────────────────────────────────────────────────

CREATE TABLE palabra_prohibida (
  id       INTEGER PRIMARY KEY,
  termino  TEXT NOT NULL,
  nivel    TEXT NOT NULL CHECK (nivel IN ('global', 'publico', 'novela')),
  publico  TEXT CHECK (publico IN ('infantil', 'juvenil', 'adulto', 'crossover')),
  CHECK ((nivel = 'publico') = (publico IS NOT NULL))
) STRICT;

-- Un UNIQUE con `publico` NULL admitiría duplicados de las listas global y de novela.
CREATE UNIQUE INDEX palabra_prohibida_unica
  ON palabra_prohibida (termino, nivel, coalesce(publico, ''));

-- B-12: qué fichero de `capitulo/listas/` se copió a `palabra_prohibida`, con su SHA-256.
-- Se copia la primera vez que se verifica un capítulo; después el proyecto conserva su copia.
CREATE TABLE lista_guardarrail (
  lista    TEXT PRIMARY KEY CHECK (lista IN ('global', 'infantil', 'juvenil', 'adulto')),
  hash     TEXT NOT NULL CHECK (length(hash) = 64),
  copiada  TEXT NOT NULL
) STRICT;

-- TC-4, AJ-3: un resultado por gate y pasada de verificación de manuscrito.
CREATE TABLE gate_resultado (
  pasada   INTEGER NOT NULL CHECK (pasada >= 1),
  gate     TEXT    NOT NULL CHECK (gate IN ('cobertura', 'lean', 'juez')),
  ok       INTEGER NOT NULL CHECK (ok IN (0, 1)),
  detalle  TEXT    NOT NULL CHECK (json_valid(detalle)),
  PRIMARY KEY (pasada, gate)
) STRICT;

-- RF-113, RF-114: una fila por criterio; `evaluacion` agrupa las cinco de una pasada.
CREATE TABLE informe_juez (
  id             INTEGER PRIMARY KEY,
  evaluacion     TEXT    NOT NULL,
  -- La versión de novela en curso (la N+1 que se está verificando): juez y revisión
  -- humana de la misma versión se comparan por aquí (RF-114).
  version_novela INTEGER NOT NULL CHECK (version_novela >= 1),
  revisor        TEXT    NOT NULL CHECK (revisor IN ('juez', 'humano')),
  ciclo          INTEGER NOT NULL CHECK (ciclo >= 0),
  criterio       TEXT    NOT NULL CHECK (criterio IN (
                   'continuidad', 'personajes', 'arco_ritmo', 'tono', 'personalizacion')),
  puntuacion     INTEGER NOT NULL CHECK (puntuacion BETWEEN 1 AND 5),
  justificacion  TEXT    NOT NULL,
  momento        TEXT    NOT NULL,
  UNIQUE (evaluacion, criterio)
) STRICT;

-- ─── exportacion/ y cambio/ ─────────────────────────────────────────────────

-- RF-120 a RF-123: la petición del lector. Su texto y el fragmento citado son no confiables:
-- van solo al fichero de `ruta_peticion` (cambios/), que se entrega por /mcp/entrada, y no
-- a la base. `ruta_peticion` es NULL en un cambio `obsoleto` (RF-123): no se guarda nada.
-- Los estados son los de `GET /cambios/{c}` (EstadoCambio de shared/tipos.py).
CREATE TABLE cambio_lector (
  id                 INTEGER PRIMARY KEY,
  version_novela     INTEGER NOT NULL CHECK (version_novela >= 1),
  capitulo           INTEGER NOT NULL CHECK (capitulo BETWEEN 1 AND 10),
  parrafo_desde      INTEGER CHECK (parrafo_desde IS NULL OR parrafo_desde >= 1),
  parrafo_hasta      INTEGER CHECK (parrafo_hasta IS NULL OR parrafo_hasta >= parrafo_desde),
  ruta_peticion      TEXT,
  hecho              TEXT    REFERENCES hecho (id),
  valor_anterior     TEXT,
  valor_nuevo        TEXT,
  hecho_nuevo        TEXT    CHECK (hecho_nuevo IS NULL OR json_valid(hecho_nuevo)),
  estado             TEXT    NOT NULL DEFAULT 'interpretando' CHECK (estado IN (
                       'interpretando', 'propuesto', 'obsoleto', 'rechazado', 'regenerando',
                       'fallido', 'publicado')),
  -- Por qué quedó `obsoleto` o `fallido`: una causa de la lista cerrada de cambio/, sin texto.
  motivo             TEXT,
  version_publicada  INTEGER CHECK (version_publicada IS NULL OR version_publicada >= 1),
  creado             TEXT    NOT NULL,
  CHECK ((estado = 'obsoleto') = (ruta_peticion IS NULL))
) STRICT;

-- TC-8, V-31: los capítulos que reabre la confirmación del cambio, calculados desde el
-- `hecho_uso` de las versiones vigentes, con la versión nueva que escribirá el Escritor.
CREATE TABLE cambio_capitulo (
  cambio    INTEGER NOT NULL REFERENCES cambio_lector (id),
  capitulo  INTEGER NOT NULL CHECK (capitulo BETWEEN 1 AND 10),
  version   INTEGER NOT NULL CHECK (version >= 1),
  PRIMARY KEY (cambio, capitulo)
) STRICT;

-- RF-94, RF-95: una versión publicada no se modifica nunca, ni sus punteros.
CREATE TABLE version_novela (
  numero     INTEGER PRIMARY KEY CHECK (numero >= 1),
  cambio     INTEGER REFERENCES cambio_lector (id),
  publicada  TEXT    NOT NULL
) STRICT;

CREATE TABLE version_novela_capitulo (
  version_novela    INTEGER NOT NULL REFERENCES version_novela (numero),
  capitulo          INTEGER NOT NULL CHECK (capitulo BETWEEN 1 AND 10),
  capitulo_version  INTEGER NOT NULL REFERENCES capitulo_version (id),
  PRIMARY KEY (version_novela, capitulo)
) STRICT;

CREATE TRIGGER version_novela_inmutable_u BEFORE UPDATE ON version_novela
BEGIN SELECT RAISE(ABORT, 'una versión publicada no se modifica (RF-95)'); END;
CREATE TRIGGER version_novela_inmutable_d BEFORE DELETE ON version_novela
BEGIN SELECT RAISE(ABORT, 'una versión publicada no se modifica (RF-95)'); END;
CREATE TRIGGER version_novela_capitulo_inmutable_u BEFORE UPDATE ON version_novela_capitulo
BEGIN SELECT RAISE(ABORT, 'una versión publicada no se modifica (RF-95)'); END;
CREATE TRIGGER version_novela_capitulo_inmutable_d BEFORE DELETE ON version_novela_capitulo
BEGIN SELECT RAISE(ABORT, 'una versión publicada no se modifica (RF-95)'); END;

-- RF-124, TC-8: «orquestar este proyecto hasta la próxima parada». El worker procesa el más
-- antiguo en cola de todos los proyectos; `detalle` lleva la causa de un fallo, sin salida
-- del proceso (EstadoTrabajo de shared/tipos.py).
CREATE TABLE trabajo (
  id         INTEGER PRIMARY KEY,
  cambio     INTEGER REFERENCES cambio_lector (id),
  estado     TEXT NOT NULL DEFAULT 'en_cola' CHECK (estado IN (
               'en_cola', 'en_curso', 'hecho', 'fallido')),
  creado     TEXT NOT NULL,
  empezado   TEXT,
  terminado  TEXT,
  detalle    TEXT CHECK (detalle IS NULL OR json_valid(detalle))
) STRICT;

COMMIT;
