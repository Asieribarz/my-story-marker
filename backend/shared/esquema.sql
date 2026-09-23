-- Esquema de la base de un proyecto: un fichero SQLite por proyecto (spec1.md §6, C-2).
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
--     (spec1.md §2.5).

BEGIN;

-- ─── Transversal · proyecto/ ────────────────────────────────────────────────

-- Una sola fila: la base es del proyecto. El directorio no se guarda: es el que contiene
-- este fichero y lo deriva shared/rutas.py del identificador (V-24).
CREATE TABLE proyecto (
  id                 INTEGER PRIMARY KEY CHECK (id = 1),
  identificador      TEXT    NOT NULL,
  version_ontologia  TEXT,
  estado             TEXT    NOT NULL DEFAULT 'intake' CHECK (estado IN (
                       'intake', 'contexto', 'planificacion', 'aprobacion_plan', 'escaleta',
                       'capitulos', 'verificacion_manuscrito', 'revision', 'aprobacion_final',
                       'publicacion', 'publicada', 'cambio_solicitado', 'regeneracion',
                       'detenida')),
  parada_plan        INTEGER NOT NULL DEFAULT 0 CHECK (parada_plan IN (0, 1)),
  parada_final       INTEGER NOT NULL DEFAULT 0 CHECK (parada_final IN (0, 1)),
  ciclos_revision    INTEGER NOT NULL DEFAULT 0 CHECK (ciclos_revision BETWEEN 0 AND 3),
  bloqueo_titular    TEXT,
  bloqueo_caduca     TEXT,
  creado             TEXT    NOT NULL,
  CHECK ((bloqueo_titular IS NULL) = (bloqueo_caduca IS NULL))
) STRICT;

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
  notas     TEXT
) STRICT;

-- Descartes de datos personales (tipo, nunca el valor), coincidencias del guardarraíl
-- y decisiones del hook de policy.
CREATE TABLE auditoria (
  id       INTEGER PRIMARY KEY,
  momento  TEXT NOT NULL,
  tipo     TEXT NOT NULL CHECK (tipo IN ('descarte_dato_personal', 'guardarrail', 'policy')),
  detalle  TEXT NOT NULL CHECK (json_valid(detalle))
) STRICT;

-- RF-14, RF-120: identificadores opacos de un solo uso para /mcp/entrada.
CREATE TABLE identificador_entrada (
  token       TEXT PRIMARY KEY,
  recurso     TEXT NOT NULL CHECK (recurso IN ('texto_libre', 'peticion')),
  ruta        TEXT NOT NULL,
  emitido     TEXT NOT NULL,
  caduca      TEXT NOT NULL,
  consumido   TEXT
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

CREATE TABLE brief (
  id                INTEGER PRIMARY KEY CHECK (id = 1),
  respuestas        TEXT NOT NULL CHECK (json_valid(respuestas)),
  ruta_texto_libre  TEXT,
  normalizado       TEXT CHECK (normalizado IS NULL OR json_valid(normalizado)),
  creado            TEXT NOT NULL
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

CREATE TABLE personaje (
  id                TEXT PRIMARY KEY,
  nombre            TEXT NOT NULL,
  origen            TEXT NOT NULL CHECK (origen IN ('real', 'ficticio')),
  fuente            TEXT,
  ficha             TEXT NOT NULL CHECK (json_valid(ficha)),
  arco              TEXT NOT NULL CHECK (arco IN (
                      'positivo', 'negativo', 'plano', 'redencion', 'corrupcion')),
  evolucion         TEXT CHECK (evolucion IS NULL OR json_valid(evolucion)),
  estado_actual     TEXT CHECK (estado_actual IS NULL OR json_valid(estado_actual)),
  sabe              TEXT CHECK (sabe IS NULL OR json_valid(sabe)),
  fecha_nacimiento  TEXT,
  CHECK ((origen = 'real') = (fuente IS NOT NULL))
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
  id      TEXT PRIMARY KEY,
  nivel   TEXT NOT NULL CHECK (nivel IN ('macro', 'meso', 'micro')),
  padre   TEXT REFERENCES localizacion (id),
  hito    TEXT,
  estado  TEXT,
  CHECK ((nivel = 'macro') = (padre IS NULL))
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

-- Personajes presentes y hechos que usa van en tablas propias, no en JSON: el
-- Recuperador arma sus bloques con consultas parametrizadas por la ficha (plan, paso 4).
CREATE TABLE ficha_capitulo (
  numero             INTEGER PRIMARY KEY CHECK (numero BETWEEN 1 AND 10),
  hito               TEXT,
  escenas            TEXT    NOT NULL CHECK (json_valid(escenas)),
  pov                TEXT    REFERENCES personaje (id),
  localizacion       TEXT    REFERENCES localizacion (id),
  tension            INTEGER NOT NULL CHECK (tension BETWEEN 0 AND 10),
  palabras_objetivo  INTEGER NOT NULL CHECK (palabras_objetivo BETWEEN 1000 AND 1500),
  cierre             TEXT    NOT NULL CHECK (cierre IN (
                       'cliffhanger', 'pausa', 'giro', 'pregunta', 'imagen')),
  plantar            TEXT    NOT NULL DEFAULT '[]' CHECK (json_valid(plantar)),
  cobrar             TEXT    NOT NULL DEFAULT '[]' CHECK (json_valid(cobrar))
) STRICT;

CREATE TABLE ficha_capitulo_personaje (
  capitulo   INTEGER NOT NULL REFERENCES ficha_capitulo (numero),
  personaje  TEXT    NOT NULL REFERENCES personaje (id),
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
CREATE TABLE capitulo_version (
  id              INTEGER PRIMARY KEY,
  capitulo        INTEGER NOT NULL REFERENCES capitulo (numero),
  version         INTEGER NOT NULL CHECK (version >= 1),
  intento         INTEGER NOT NULL CHECK (intento BETWEEN 1 AND 3),
  estado          TEXT    NOT NULL CHECK (estado IN (
                    'borrador', 'editado', 'verificado', 'aprobado', 'revision_humana')),
  ruta            TEXT    NOT NULL,
  ruta_prompt     TEXT,
  semilla         TEXT,
  version_prompt  TEXT,
  version_modelo  TEXT,
  creado          TEXT    NOT NULL,
  UNIQUE (capitulo, version, intento)
) STRICT;

CREATE TABLE informe (
  id                INTEGER PRIMARY KEY,
  capitulo_version  INTEGER REFERENCES capitulo_version (id),
  ambito            TEXT NOT NULL CHECK (ambito IN ('capitulo', 'manuscrito')),
  verificador       TEXT NOT NULL,
  severidad         TEXT NOT NULL CHECK (severidad IN ('baja', 'media', 'alta', 'bloqueante')),
  regla             TEXT NOT NULL,
  localizacion      TEXT NOT NULL,
  evidencia         TEXT NOT NULL,
  esperado          TEXT,
  momento           TEXT NOT NULL,
  CHECK ((ambito = 'capitulo') = (capitulo_version IS NOT NULL))
) STRICT;

-- ─── capitulo/ · biblia ─────────────────────────────────────────────────────

CREATE TABLE evento (
  id              INTEGER PRIMARY KEY,
  descripcion     TEXT NOT NULL,
  momento         TEXT NOT NULL,
  lugar           TEXT NOT NULL REFERENCES localizacion (id),
  capitulo        INTEGER CHECK (capitulo IS NULL OR capitulo BETWEEN 1 AND 10),
  excluye         TEXT REFERENCES personaje (id),
  tipo_exclusion  TEXT CHECK (tipo_exclusion IN ('muerte', 'partida')),
  hecho           TEXT REFERENCES hecho (id),
  CHECK ((excluye IS NULL) = (tipo_exclusion IS NULL))
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

-- Una fila por traspaso: desde este capítulo, el objeto lo tiene este poseedor.
CREATE TABLE inventario (
  id        INTEGER PRIMARY KEY,
  objeto    TEXT    NOT NULL,
  poseedor  TEXT    REFERENCES personaje (id),
  capitulo  INTEGER NOT NULL CHECK (capitulo BETWEEN 1 AND 10),
  UNIQUE (objeto, capitulo)
) STRICT;

CREATE TABLE presagio (
  id           INTEGER PRIMARY KEY,
  descripcion  TEXT    NOT NULL,
  plantado_en  INTEGER NOT NULL CHECK (plantado_en BETWEEN 1 AND 10),
  cobrado_en   INTEGER CHECK (cobrado_en IS NULL OR cobrado_en > plantado_en)
) STRICT;

CREATE TABLE glosario (
  termino    TEXT PRIMARY KEY,
  categoria  TEXT NOT NULL,
  nota       TEXT
) STRICT;

CREATE TABLE resumen (
  id      INTEGER PRIMARY KEY,
  ambito  TEXT    NOT NULL CHECK (ambito IN ('capitulo', 'acto')),
  numero  INTEGER NOT NULL CHECK (numero >= 1),
  texto   TEXT    NOT NULL,
  creado  TEXT    NOT NULL,
  UNIQUE (ambito, numero)
) STRICT;

-- ─── Guardarraíl y jueces ───────────────────────────────────────────────────

CREATE TABLE palabra_prohibida (
  id       INTEGER PRIMARY KEY,
  termino  TEXT NOT NULL,
  nivel    TEXT NOT NULL CHECK (nivel IN ('global', 'publico', 'novela')),
  publico  TEXT CHECK (publico IN ('infantil', 'juvenil', 'adulto', 'crossover')),
  UNIQUE (termino, nivel, publico),
  CHECK ((nivel = 'publico') = (publico IS NOT NULL))
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
  criterio       TEXT    NOT NULL,
  puntuacion     INTEGER NOT NULL CHECK (puntuacion BETWEEN 1 AND 5),
  justificacion  TEXT    NOT NULL,
  momento        TEXT    NOT NULL,
  UNIQUE (evaluacion, criterio)
) STRICT;

-- ─── exportacion/ y cambio/ ─────────────────────────────────────────────────

CREATE TABLE cambio_lector (
  id              INTEGER PRIMARY KEY,
  version_novela  INTEGER NOT NULL,
  capitulo        INTEGER NOT NULL CHECK (capitulo BETWEEN 1 AND 10),
  fragmento       TEXT    NOT NULL,
  ruta_peticion   TEXT    NOT NULL,
  hecho           TEXT    REFERENCES hecho (id),
  valor_anterior  TEXT,
  valor_nuevo     TEXT,
  hecho_nuevo     TEXT    CHECK (hecho_nuevo IS NULL OR json_valid(hecho_nuevo)),
  estado          TEXT    NOT NULL DEFAULT 'recibido' CHECK (estado IN (
                    'recibido', 'propuesto', 'confirmado', 'rechazado', 'aplicado', 'fallido')),
  creado          TEXT    NOT NULL
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

CREATE TABLE trabajo (
  id         INTEGER PRIMARY KEY,
  cambio     INTEGER REFERENCES cambio_lector (id),
  estado     TEXT NOT NULL DEFAULT 'en_cola' CHECK (estado IN (
               'en_cola', 'en_curso', 'hecho', 'fallido')),
  creado     TEXT NOT NULL,
  empezado   TEXT,
  terminado  TEXT,
  detalle    TEXT
) STRICT;

COMMIT;
