---
name: sqlite
description: "Referencia de SQLite: pragmas obligatorios, tipado dinámico, transacciones, WAL y escritor único, FTS5 y el módulo sqlite3 de Python. Úsala al escribir esquema, migraciones o cualquier consulta contra la base del proyecto."
---

# SQLite — referencia

Lo que distingue a SQLite de un servidor de base de datos, y los errores que solo aparecen aquí. **No contiene el esquema de este proyecto**: las tablas de la biblia se definen a partir de `docs/definitions.md` y `docs/architecture.md` §6.

## Pragmas: lo que hay que poner en cada conexión

```sql
PRAGMA journal_mode = WAL;      -- una sola vez, persiste en el fichero
PRAGMA foreign_keys = ON;       -- POR CONEXIÓN, y está OFF por defecto
PRAGMA busy_timeout = 5000;     -- POR CONEXIÓN, milisegundos
PRAGMA synchronous = NORMAL;    -- seguro con WAL, bastante más rápido
```

**Las claves ajenas no se aplican por defecto.** Es la trampa más cara de SQLite: declaras `REFERENCES`, el esquema parece correcto, y la base acepta filas huérfanas en silencio porque nadie activó el pragma. Hay que ponerlo en *cada* conexión nueva, no una vez en la creación.

`busy_timeout` evita que un `SQLITE_BUSY` falle al instante cuando otro proceso está escribiendo; sin él, cualquier concurrencia da errores esporádicos.

## WAL y el escritor único

En modo WAL, los lectores no bloquean al escritor ni el escritor a los lectores. Pero **solo puede haber un escritor a la vez** en toda la base. Con varios procesos escribiendo, uno gana y el resto espera o recibe `SQLITE_BUSY`.

WAL crea dos ficheros junto a la base, `-wal` y `-shm`. Copiar solo el `.db` mientras hay escrituras en curso da una copia incompleta: para copias en caliente, usa la API de backup (`conn.backup(dest)` en Python), no `cp`.

WAL no funciona sobre sistemas de ficheros en red.

## Transacciones

`BEGIN` normal abre una transacción de lectura y la asciende a escritura en el primer `INSERT`. Si otro proceso ya escribió entre medias, el ascenso falla con `SQLITE_BUSY` y **no lo salva el `busy_timeout`**: hay que reintentar la transacción entera.

Si sabes que vas a escribir, empieza directamente en modo escritura:

```sql
BEGIN IMMEDIATE;
...
COMMIT;
```

Mete las escrituras en lote dentro de una transacción. Sin ella, cada `INSERT` es su propia transacción con su propio `fsync`: la diferencia entre insertar mil filas en un `BEGIN` y hacerlo suelto es de dos órdenes de magnitud.

## Tipado: no es lo que parece

SQLite tiene **afinidad de tipo**, no tipos. Una columna `INTEGER` acepta la cadena `"hola"` y la guarda tal cual. El esquema no te protege.

Desde 3.37 hay tablas estrictas, que sí lo hacen:

```sql
CREATE TABLE chapters (
  id      INTEGER PRIMARY KEY,
  number  INTEGER NOT NULL,
  state   TEXT NOT NULL CHECK (state IN ('borrador','editado','verificado','aprobado','revision_humana'))
) STRICT;
```

Usa `STRICT` siempre que puedas, y `CHECK` con lista cerrada para los enumerados: SQLite no tiene tipo enum.

**No hay tipo fecha.** Se guarda como texto ISO-8601 (`2026-09-21T14:30:00Z`), que ordena y compara correctamente como cadena, o como entero unix. Elige uno y no lo mezcles.

**No hay booleano**: es `INTEGER` 0 o 1.

## ALTER TABLE es limitado

Solo puedes renombrar la tabla, renombrar una columna, añadir una columna y borrar una columna (3.35+). **No** puedes cambiar un tipo, añadir una restricción ni reordenar. Para eso, el procedimiento es crear la tabla nueva, copiar con `INSERT INTO nueva SELECT ... FROM vieja`, borrar la vieja y renombrar; todo dentro de una transacción y con `PRAGMA foreign_keys = OFF` mientras dura.

Una columna nueva con `NOT NULL` necesita `DEFAULT`, y ese default no puede ser variable como `CURRENT_TIMESTAMP`.

## Sintaxis útil que no todo el mundo conoce

```sql
-- UPSERT
INSERT INTO facts (chapter, key, value) VALUES (?, ?, ?)
  ON CONFLICT(chapter, key) DO UPDATE SET value = excluded.value;

-- RETURNING (3.35+): evita el SELECT posterior
INSERT INTO chapters (number) VALUES (?) RETURNING id;
```

`AUTOINCREMENT` casi nunca hace falta: `INTEGER PRIMARY KEY` ya es autoincremental y más rápido. `AUTOINCREMENT` solo añade la garantía de no reutilizar ids borrados, a cambio de una tabla extra.

## FTS5

Búsqueda de texto completo sin embeddings, incluida en SQLite. Para un corpus de capítulos, la forma correcta es una tabla de contenido externo, que no duplica el texto:

```sql
CREATE VIRTUAL TABLE chunks_fts USING fts5(
  body,
  content='chunks',
  content_rowid='id',
  tokenize="unicode61 remove_diacritics 2"
);
```

Con contenido externo, el índice **no se actualiza solo**: hay que mantenerlo con disparadores en `INSERT`, `UPDATE` y `DELETE` de la tabla base. Olvidarlos es el fallo típico: las búsquedas devuelven resultados viejos.

`remove_diacritics 2` importa en castellano: sin ello, "camión" y "camion" no coinciden.

Consulta con `MATCH` y ordena por `rank` (menor es mejor). `bm25(chunks_fts)` permite ponderar columnas. `snippet()` y `highlight()` devuelven el fragmento con el término marcado.

Cuidado: la entrada de `MATCH` es una **sintaxis de consulta**, no texto literal. Un término del usuario con comillas, `*`, `NEAR` o `OR` se interpreta como operador y puede dar error. Para búsqueda literal, envuelve el término en comillas dobles y escapa las que contenga.

## Python: el módulo sqlite3

- Parametriza siempre con `?`. Nunca formatees SQL con f-strings.
- `conn.row_factory = sqlite3.Row` devuelve filas accesibles por nombre de columna.
- Una conexión no se comparte entre hilos por defecto. Abre una por hilo, o usa `check_same_thread=False` sabiendo que tú te encargas de serializar.
- El manejo de transacciones por defecto es heredado y confuso: `isolation_level=None` desactiva el implícito y te deja escribir `BEGIN`/`COMMIT` a mano, que es más predecible. En Python 3.12+ existe `autocommit`, que es la forma moderna.
- `conn.execute` no hace commit. Usar `with conn:` sí lo hace al salir, y hace rollback si hubo excepción — pero no cierra la conexión.

## Detalles que muerden

- `NULL` nunca es igual a nada, ni a `NULL`. Usa `IS NULL`. En `UNIQUE`, varios `NULL` conviven sin violar la restricción.
- `LIKE` no distingue mayúsculas solo en ASCII: con acentos y eñes no funciona como esperas. Para texto real, FTS5.
- `VACUUM` reescribe la base entera y necesita el doble de espacio; no se puede ejecutar dentro de una transacción.
- `PRAGMA optimize` antes de cerrar conexiones de larga vida mantiene las estadísticas al día.
- `EXPLAIN QUERY PLAN` delante de una consulta lenta dice si está usando índice o recorriendo la tabla.
