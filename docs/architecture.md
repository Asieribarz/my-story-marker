# architecture.md — Arquitectura y flujo del generador

> Propósito: describe cómo el sistema convierte el contexto (`domain-knowledge.md` + `definitions.md`) en un manuscrito: capas, agentes, verificadores, flujo de trabajo, modelo de datos, organización del código y despliegue. El documento describe **qué** hace cada pieza, no con qué se implementa: la pila está sin decidir salvo lo recogido en §7.

---

## 1. Visión general por capas

```mermaid
flowchart TB
  subgraph UI["Capa de interfaz"]
    U1["Panel del editor · configuración, revisión, aprobación"]
    U2["API REST / SDK"]
  end
  subgraph ORQ["Capa de orquestación · Claude Code"]
    O1["Sesión de Claude Code · recorre el grafo de estados"]
    O2["Cola de trabajos · un job por capítulo · backend"]
  end
  subgraph AG["Capa de agentes · subagentes de Claude Code"]
    A1["Agentes de planificación"]
    A2["Agentes de escritura"]
    A3["Agentes de revisión"]
  end
  subgraph VER["Capa de verificación"]
    V1["Verificadores deterministas"]
    V2["Verificadores LLM-juez"]
  end
  subgraph MEM["Capa de memoria"]
    M1["Biblia estructurada"]
    M2["Índice semántico"]
    M3["Manuscrito versionado"]
  end
  subgraph LLM["Capa de modelos"]
    L1["Modelo grande · escritura y planificación"]
    L2["Modelo rápido · resúmenes, extracción, jueces"]
    L3["Embeddings"]
  end
  UI --> ORQ --> AG
  AG <--> VER
  AG <--> MEM
  VER <--> MEM
  AG --> LLM
  VER --> LLM
```

**Quién orquesta:** una sesión de Claude Code, no código propio. Recorre el grafo de estados como protocolo escrito, lanza cada agente como subagente y aplica la política de reintentos. El backend se queda con todo lo que no consume modelo: verificadores deterministas, persistencia, índice y exportación.

**Idea central:** los agentes proponen, los verificadores disponen y la biblia recuerda. Ningún agente escribe en la biblia directamente; solo el Bibliotecario, y solo después de que un capítulo pase la verificación.

---

## 2. Flujo de extremo a extremo

```mermaid
flowchart LR
  I["1 · Intake · brief del editor"] --> C["2 · Instanciar ontología · contexto validado"]
  C --> PL["3 · Planificación · estructura, personajes, mundo, tema, estilo"]
  PL --> HG1{"Aprobación humana del plan"}
  HG1 -->|"cambios"| PL
  HG1 -->|"ok"| ES["4 · Escaleta · una ficha por capítulo"]
  ES --> GEN["5 · Bucle por capítulo · escribir → verificar → biblia"]
  GEN --> FA{"¿Fin de acto?"}
  FA -->|"sí"| VA["Verificación de acto"] --> GEN
  FA -->|"no"| GEN
  GEN --> FM["6 · Verificación de manuscrito"]
  FM -->|"fallos"| REV["7 · Pasada de revisión dirigida"] --> FM
  FM -->|"ok"| HG2{"Aprobación humana final"}
  HG2 -->|"notas"| REV
  HG2 -->|"ok"| OUT["8 · Metadatos y exportación · EPUB, DOCX, PDF"]
```

| Fase | Entrada | Salida | Responsable |
|---|---|---|---|
| Intake | Brief libre del editor (público, género, extensión, ideas) | Brief normalizado | Panel + Agente de Contexto |
| Instanciar ontología | Brief normalizado | Objeto de contexto completo (YAML de `definitions.md`) con valores por defecto heredados | Agente de Contexto + Verificador de Esquema |
| Planificación | Objeto de contexto | Plan narrativo: hitos por capítulo, fichas, mundo y ruta, tema, guía de estilo | Agentes de planificación |
| Escaleta | Plan narrativo | N fichas de capítulo | Escaletista |
| Bucle por capítulo | Ficha + biblia | Capítulo aprobado + biblia actualizada | Escritor, Editor, verificadores, Bibliotecario |
| Verificación de manuscrito | Manuscrito completo + biblia | Informe de fallos globales | Verificadores de manuscrito |
| Revisión dirigida | Informe | Capítulos corregidos | Revisor |
| Exportación | Manuscrito aprobado | Archivos + metadatos | Exportador |

---

## 3. Agentes

Cada agente de esta tabla es un **subagente de Claude Code**, con su propio contexto y su modelo fijado según la columna *Modelo*. Las definiciones concretas aún no existen.

```mermaid
flowchart LR
  ORQ["Claude Code · orquestador"]
  ORQ --> CTX["Agente de Contexto"]
  ORQ --> ARQ["Arquitecto narrativo"]
  ORQ --> PER["Diseñador de personajes"]
  ORQ --> MUN["Constructor de mundo"]
  ORQ --> EST["Director de estilo"]
  ORQ --> ESC["Escaletista"]
  ORQ --> WRI["Escritor de capítulo"]
  ORQ --> EDI["Editor de estilo"]
  ORQ --> BIB["Bibliotecario"]
  ORQ --> REV["Revisor dirigido"]
  ORQ --> EXP["Exportador"]
  CTX -.-> ARQ
  ARQ -.-> PER
  PER -.-> MUN
  MUN -.-> EST
  EST -.-> ESC
  ESC -.-> WRI
  WRI -.-> EDI
  EDI -.-> BIB
```

| Agente | Responsabilidad | Entrada | Salida | Modelo |
|---|---|---|---|---|
| **Claude Code · orquestador** | Recorre el grafo de estados como protocolo, lanza los subagentes, aplica la política de reintentos y para en los puntos de aprobación humana. No genera prosa de la novela. | Estado del proyecto | Transiciones e invocaciones de subagente | Sesión de Claude Code |
| **Agente de Contexto** | Convierte el brief en el objeto de contexto de la ontología, rellena valores por defecto según el pipeline de decisión y pregunta lo que falte. | Brief | Contexto YAML validado | Grande |
| **Arquitecto narrativo** | Elige modelo estructural, reparte hitos por capítulo, define curva de tensión, pregunta dramática y tipo de final. | Contexto | Plan estructural | Grande |
| **Diseñador de personajes** | Crea fichas, arcos, evolución y grafo de relaciones coherentes con los hitos. | Contexto + plan estructural | Fichas y grafo | Grande |
| **Constructor de mundo** | Define tipo de mundo, ruta ligada a los hitos, localizaciones clave, reglas del mundo con costes. | Contexto + plan + fichas | Biblia inicial de mundo | Grande |
| **Director de estilo** | Fija narrador, registro, métricas de prosa, léxico, lista negra y convención onomástica; produce una guía de estilo con ejemplos. | Contexto + fichas | Guía de estilo | Grande |
| **Escaletista** | Produce una ficha por capítulo: hito, escenas y secuelas, POV, localización, tensión objetivo, elementos a plantar y cobrar. | Plan completo | N fichas de capítulo | Grande |
| **Escritor de capítulo** | Redacta el borrador a partir de la ficha, el resumen acumulado y el estado de la biblia. | Ficha + contexto recuperado | Borrador | Grande |
| **Editor de estilo** | Pasada de corrección local: métricas de prosa, repeticiones, lista negra, ritmo. No cambia hechos. | Borrador + guía de estilo | Borrador editado | Rápido |
| **Bibliotecario** | Extrae del capítulo aprobado los hechos nuevos (estado de personajes, objetos, fechas, presagios) y actualiza la biblia y el resumen acumulado. | Capítulo aprobado | Biblia actualizada | Rápido |
| **Revisor dirigido** | Corrige capítulos concretos a partir de un informe de fallos, con cambios mínimos. | Capítulo + informe | Capítulo corregido | Grande |
| **Exportador** | Genera título, sinopsis, palabras clave y los archivos finales. | Manuscrito | EPUB, DOCX, PDF, metadatos | Rápido + código |

---

## 4. Verificadores

Se distinguen dos familias: los **deterministas** (código, baratos, siempre se ejecutan) y los **LLM-juez** (un modelo evalúa con rúbrica, se ejecutan después de los deterministas). Un verificador nunca corrige; devuelve un informe con severidad y localización del fallo.

```mermaid
flowchart LR
  V["Verificadores"] --> D["Deterministas · código"]
  V --> J["LLM-juez · rúbrica"]
  D --> D1["Esquema · el contexto cumple la ontología"]
  D --> D2["Longitud · capítulo y manuscrito dentro de tolerancia"]
  D --> D3["Métricas de estilo · frase media, % diálogo, legibilidad, lista negra"]
  D --> D4["Consistencia de nombres y grafías"]
  D --> D5["Continuidad dura · personaje ausente, objeto duplicado, tiempo de viaje imposible"]
  J --> J1["Hito estructural cumplido"]
  J --> J2["Coherencia blanda · motivaciones, reglas del mundo, conocimiento de cada personaje"]
  J --> J3["Voz y POV constantes"]
  J --> J4["Contenido dentro de topes y líneas rojas"]
  J --> J5["Manuscrito · Chéjov, subtramas, pregunta dramática, arco y evolución del protagonista"]
```

| Verificador | Momento | Tipo | Severidad si falla | Acción |
|---|---|---|---|---|
| Esquema del contexto | Tras instanciar la ontología | Determinista (JSON Schema) | Bloqueante | Agente de Contexto corrige |
| Longitud | Cada capítulo y al final | Determinista | Media | Editor amplía o recorta |
| Métricas de estilo | Cada capítulo | Determinista | Baja / Media | Editor de estilo |
| Nombres y grafías | Cada capítulo | Determinista contra glosario | Media | Editor de estilo |
| Continuidad dura | Cada capítulo | Determinista contra biblia | Alta | Escritor regenera el pasaje |
| Hito estructural | Cada capítulo | LLM-juez | Alta | Escritor regenera el capítulo |
| Coherencia blanda | Cada capítulo | LLM-juez con biblia como evidencia | Alta | Escritor regenera el pasaje |
| Voz y POV | Cada capítulo | LLM-juez | Media | Editor de estilo |
| Contenido y líneas rojas | Cada capítulo | Clasificador + LLM-juez | Bloqueante | Regeneración obligatoria |
| Verificación de acto | Fin de acto | LLM-juez | Alta | Revisor dirigido |
| Verificación de manuscrito | Final | LLM-juez + deterministas | Alta | Revisor dirigido |
| Originalidad | Final | Búsqueda de similitud contra corpus | Bloqueante | Revisor dirigido |

**Política de reintentos:** máximo 3 ciclos por capítulo; si persiste el fallo, el capítulo pasa a cola de revisión humana con el informe adjunto.

---

## 5. Ciclo de un capítulo

```mermaid
sequenceDiagram
  participant O as Claude Code
  participant R as Recuperador de contexto
  participant B as Biblia
  participant W as Escritor
  participant E as Editor de estilo
  participant VD as Verificadores deterministas
  participant VJ as Verificadores LLM-juez
  participant L as Bibliotecario

  O->>R: ficha del capítulo n
  R->>B: estado actual, resumen acumulado, fichas de personajes presentes, localización, presagios pendientes
  B-->>R: paquete de contexto
  R-->>W: prompt ensamblado (ficha + contexto + guía de estilo)
  W-->>E: borrador
  E-->>VD: borrador editado
  VD-->>O: informe determinista
  alt fallo bloqueante o alto
    O->>W: regenerar con informe
  else ok
    VD-->>VJ: borrador
    VJ-->>O: informe de jueces
    alt fallo
      O->>W: regenerar pasaje con informe
    else ok
      O->>L: capítulo aprobado
      L->>B: hechos nuevos, resumen, estado de objetos y personajes
      O->>O: siguiente capítulo
    end
  end
```

El **Recuperador de contexto** no es un agente creativo: ensambla el prompt a partir de consultas estructuradas a la biblia y de una búsqueda semántica de pasajes anteriores relevantes (por ejemplo, la última vez que apareció un secundario), para que el Escritor no reciba toda la novela sino solo lo pertinente.

---

## 6. Modelo de datos y memoria

```mermaid
flowchart LR
  PRJ["Proyecto"] --> CTX["Contexto · ontología instanciada"]
  PRJ --> PLAN["Plan narrativo · hitos, curva de tensión"]
  PRJ --> FIC["Fichas de capítulo · escaleta"]
  PRJ --> CAP["Capítulos · versiones, estado, informes"]
  PRJ --> BIB["Biblia"]
  BIB --> B1["Personajes · ficha, estado, evolución, qué saben"]
  BIB --> B2["Localizaciones · jerarquía, estado"]
  BIB --> B3["Línea temporal · día de la historia por capítulo"]
  BIB --> B4["Inventario · objeto → poseedor → capítulo"]
  BIB --> B5["Presagios · plantado en / cobrado en"]
  BIB --> B6["Glosario y nombres"]
  BIB --> B7["Resúmenes · por capítulo y global"]
  CAP --> IDX["Índice semántico · fragmentos con metadatos"]
```

| Almacén | Contenido | Tecnología |
|---|---|---|
| Relacional | Proyecto, contexto, plan, fichas, biblia, informes de verificación, costes | **SQLite local**, un fichero por proyecto |
| Vectorial | Fragmentos de capítulos con metadatos (capítulo, POV, personajes, localización) | **SQLite local**, misma base; extensión vectorial o FTS5, sin decidir |
| Objetos | Versiones de capítulos, exportaciones, prompts y respuestas para auditoría | Ficheros en disco, dentro del proyecto |
| Caché | Prompts repetidos, embeddings | **SQLite local**, misma base |

Son cuatro necesidades, no cuatro servicios.

Las versiones de capítulo, las exportaciones y los prompts de auditoría son ficheros en disco y no blobs en la base, precisamente porque quien orquesta es Claude Code: un fichero se lee con grep y se compara con diff; un blob es opaco justo para quien más lo necesita.

Un único fichero SQLite cubre las tres necesidades que no son ficheros: relacional, vectorial y caché. No hay servicio de base de datos aparte ni índice vectorial separado.

SQLite funciona en modo **WAL** y admite un solo escritor a la vez, de modo que la escritura queda serializada. Ver la restricción que eso impone al paralelismo en §10.

Queda por decidir **cómo** se hace la búsqueda dentro de esa base: una extensión vectorial sobre embeddings, o FTS5, que es búsqueda de texto completo y no necesita embeddings. Lo segundo evita depender de un proveedor de embeddings externo, que es gasto medido aparte de la suscripción.

Cada capítulo se guarda con versión, estado (`borrador`, `editado`, `verificado`, `aprobado`, `revision_humana`) y los informes que lo produjeron, de modo que cualquier fallo es trazable hasta el prompt exacto.

---

## 7. Tecnología

Lo decidido hasta ahora es solo esto:

| Componente | Decisión |
|---|---|
| Backend | Python + FastAPI |
| Frontend | React con Vite |
| Orquestación de agentes | Claude Code: la sesión recorre el grafo y los agentes son subagentes suyos |
| Base de datos | SQLite local, un fichero por proyecto, en modo WAL: relacional, vectorial y caché en la misma base |
| Almacén de objetos | Ficheros en disco, sin servicio aparte |

SQLite es una decisión de las **fases 1 y 2**. El multiusuario de la fase 3 (§11) obligará a revisarla; queda dicho aquí para que ese día se lea como un cambio previsto y no como una sorpresa.

Todo lo demás está **sin decidir**: el mecanismo de búsqueda dentro de SQLite (extensión vectorial con embeddings o FTS5), la cola de trabajos, la observabilidad, los formatos de exportación, el despliegue y **por qué vía accede Claude Code a la biblia y al índice** (endpoint de FastAPI, servidor MCP u otra). El resto del documento describe esas piezas por su función, no por su implementación; cada decisión se tomará cuando la fase correspondiente la exija y se añadirá a esta tabla.

---

## 8. Organización del código

Dos criterios distintos, uno por lado, y ambos con la misma intención: que lo que cambia junto viva junto.

### Backend — vertical slices, una carpeta por tarea

Las tareas son las **fases de §2**, no los agentes de §3 ni los recursos REST. Una fase es la unidad de trabajo real y es lo que se toca entero cuando cambia algo; varios agentes comparten fase, así que una carpeta por agente dispersaría lo que se modifica a la vez.

Cada rebanada contiene **todo lo suyo**: su router de FastAPI, sus modelos Pydantic, su lógica y su acceso a SQLite. No hay `routers/`, `models/` ni `services/` transversales: esa organización obliga a abrir cuatro carpetas para entender una sola tarea.

```
backend/
  intake/            · brief → brief normalizado
  contexto/          · brief → objeto de contexto validado
  planificacion/     · contexto → plan narrativo
  escaleta/          · plan → fichas de capítulo
  capitulo/          · el bucle de §5
  verificacion/      · verificación de manuscrito
  revision/          · revisión dirigida
  exportacion/       · manuscrito → archivos y metadatos
  shared/            · deliberadamente pequeño
```

`shared/` es solo para lo que es transversal de verdad: la conexión a SQLite con sus pragmas, el esquema de la ontología y los tipos comunes. La tensión es real en las dos direcciones. Sin `shared/`, los pragmas acaban duplicados en ocho sitios y un día divergen —y un `PRAGMA foreign_keys` olvidado en una sola rebanada no da error, solo filas huérfanas—. Con un `shared/` que crece sin control, vuelves a tener capas horizontales con otro nombre. Ante la duda, duplicar dentro de la rebanada; se promueve a `shared/` cuando el tercer sitio lo necesite.

### Frontend — package by feature, sin FSD

Una carpeta por funcionalidad, con sus componentes, sus hooks, su estado y sus llamadas a la API dentro. No hay `components/`, `hooks/` ni `services/` en la raíz recogiendo piezas de pantallas que no tienen nada que ver entre sí.

**Sin FSD**: no se adopta Feature-Sliced Design. Sus capas obligatorias (`shared`, `entities`, `features`, `widgets`, `pages`, `app`) y sus reglas de importación entre capas son más metodología de la que este frontend necesita, y el coste de aprenderla y respetarla no se paga con un panel de editor.

Lo compartido entre funcionalidades vive en un `shared/` con el mismo criterio de arriba: pequeño, y se promueve cuando el tercer sitio lo pide.

---

## 9. Despliegue

```mermaid
flowchart LR
  subgraph EDGE["Acceso"]
    U["Editor"] --> W["Panel web · React + Vite"]
    W --> API["API · FastAPI"]
    U --> API
  end
  subgraph CORE["Núcleo"]
    API --> Q["Cola de trabajos"]
    Q --> WK1["Worker de planificación"]
    Q --> WK2["Workers de capítulo · escalables"]
    Q --> WK3["Worker de verificación"]
  end
  subgraph DATA["Datos"]
    ST["SQLite local · fichero por proyecto"]
    FS["Ficheros en disco · capítulos, exportaciones, auditoría"]
  end
  subgraph EXT["Servicios externos"]
    LLMs["API de modelos"]
    OBS["Trazas y coste"]
  end
  WK1 & WK2 & WK3 --> ST
  WK1 & WK2 & WK3 --> FS
  WK1 & WK2 & WK3 --> LLMs
  WK1 & WK2 & WK3 --> OBS
```

---

## 10. Transversales

| Aspecto | Decisión |
|---|---|
| **Human-in-the-loop** | Dos puntos obligatorios (plan y manuscrito final) y uno condicional (capítulo que agota reintentos). El panel muestra diff y el informe que motivó la pausa. |
| **Control de coste** | El gasto es de suscripción, no de API medida: no hay presupuesto por token que degradar en caliente. El control se ejerce eligiendo el modelo de cada subagente por adelantado (rápido en editores y jueces, grande en escritura y planificación). Estimación previa: novela estándar ≈ 30 capítulos × (1 escritura + 1,5 regeneraciones medias + edición + jueces). |
| **Paralelismo** | Planificación secuencial; capítulos secuenciales por defecto (dependen de la biblia). Paralelizable solo en estructuras corales con líneas independientes hasta su convergencia, y **condicionado a que el almacén lo soporte**: con SQLite la escritura es serializada, así que el paralelismo coral se limita a la generación, no a la escritura en la biblia. |
| **Determinismo y reproducibilidad** | Semilla, versión de prompt, versión de modelo y contexto exacto guardados por capítulo. |
| **Seguridad y privacidad** | Sin datos personales en el brief; secretos en gestor de credenciales; prompts y salidas cifrados en reposo; retención configurable. |
| **Evaluación continua** | Conjunto de briefs de prueba; se mide tasa de aprobación al primer intento, fallos por tipo de verificador, coste por capítulo y valoración humana ciega de calidad. |
| **Versionado de la ontología** | La ontología tiene versión semántica; cada proyecto fija la suya y las migraciones se validan con el verificador de esquema. |

---

## 11. Plan de construcción por fases

```mermaid
flowchart LR
  F1["Fase 1 · MVP · 4-6 semanas"] --> F2["Fase 2 · Calidad · 4-6 semanas"] --> F3["Fase 3 · Producto · 6-8 semanas"]
  F1 --> F1a["Ontología como esquema · Contexto, Arquitecto, Escaletista, Escritor · verificadores deterministas · biblia mínima · salida Markdown"]
  F2 --> F2a["Resto de agentes de planificación · LLM-juez · Bibliotecario con extracción · índice semántico · panel de revisión"]
  F3 --> F3a["Verificación de manuscrito · originalidad · exportación editorial · control de coste · evaluación continua · multiusuario"]
```
