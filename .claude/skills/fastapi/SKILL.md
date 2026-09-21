---
name: fastapi
description: Capa sobre el plugin fastapi@han: corrige su error sobre async frente a sync, y cubre lo que no trae (lifespan, migración a Pydantic v2, y por qué sus ejemplos de base de datos no valen aquí). Léela junto a las skills del plugin, no en su lugar.
---

# FastAPI — correcciones y huecos

El plugin `fastapi@han` aporta tres skills largas y detalladas: patrones async, inyección de dependencias y validación. Sirven como referencia amplia. Esta skill **no las repite**: recoge lo que dicen mal y lo que no dicen.

## Corrección: un endpoint `def` NO bloquea el bucle de eventos

`fastapi-async-patterns` abre con este ejemplo, y está mal:

```python
# Sync endpoint (blocks the event loop)   <- FALSO
@app.get('/sync')
def sync_endpoint():
    time.sleep(1)  # Blocks the entire server   <- FALSO
```

FastAPI ejecuta los endpoints declarados con `def` normal en un **threadpool**, precisamente para que puedan bloquear sin parar el servidor. Ese ejemplo es seguro.

El peligro real es el contrario, y el plugin no lo ilustra:

```python
@app.get('/async')
async def bad():
    time.sleep(1)      # esto SÍ para el proceso entero
    conn.execute(...)  # una consulta SQLite síncrona, también
```

Un `async def` corre en el bucle de eventos. Cualquier llamada bloqueante dentro detiene todas las peticiones en vuelo, y **no produce ningún error**: solo lentitud bajo carga, que es lo que lo hace difícil de encontrar.

La regla: si todo lo que haces dentro es `await`, usa `async def`. Si llamas a algo síncrono, usa `def` normal y deja que FastAPI lo aparte. Si no hay más remedio que bloquear dentro de un `async def`, `await anyio.to_thread.run_sync(fn, arg)`.

Esto importa aquí más que en un proyecto normal: el acceso a SQLite desde `sqlite3` es síncrono.

## Hueco: ciclo de vida

Ninguna de las tres skills cubre el arranque y parada de la aplicación. `@app.on_event("startup")` está **deprecado**; lo correcto es el gestor de contexto `lifespan`:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = open_db()
    yield
    app.state.db.close()

app = FastAPI(lifespan=lifespan)
```

Es el único sitio correcto para abrir y cerrar recursos de proceso.

## Hueco: migrar de Pydantic v1 a v2

La skill de validación usa v2, pero no avisa de los cambios que rompen. Copiando ejemplos antiguos de internet te encontrarás con:

| v1 | v2 |
|---|---|
| `.dict()` | `.model_dump()` |
| `.json()` | `.model_dump_json()` |
| `parse_obj()` | `model_validate()` |
| `class Config: orm_mode = True` | `model_config = ConfigDict(from_attributes=True)` |
| `@validator` | `@field_validator` |
| `@root_validator` | `@model_validator` |

## Aviso: sus ejemplos de base de datos no valen aquí

`fastapi-async-patterns` y `fastapi-dependency-injection` ilustran el acceso a datos con SQLAlchemy async, asyncpg, Motor y Tortoise, sobre PostgreSQL y MongoDB. Nada de eso es el stack de este proyecto: la base es **SQLite local** (`docs/architecture.md` §6) y **no hay decisión tomada sobre ORM**. Toma de ahí el patrón de dependencia con `yield`, no la elección de biblioteca.

Para SQLite, ver la skill `sqlite`.

## Lo que sí conviene tomar del plugin

- Dependencias con `yield` para cerrar conexiones y transacciones.
- `app.dependency_overrides` para sustituir dependencias en las pruebas.
- `StreamingResponse` para respuestas largas.
- El aviso de que `BackgroundTasks` es fuego y olvido en el mismo proceso: si el proceso se reinicia, la tarea se pierde sin rastro ni reintento. No sustituye a una cola.
