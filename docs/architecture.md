# architecture.md — Arquitectura y flujo del generador

> Propósito: describe cómo el sistema convierte el contexto (`domain-knowledge.md` + `definitions.md`) en un manuscrito: capas, agentes, verificadores, flujo de trabajo, modelo de datos, tecnología y despliegue. Las decisiones tecnológicas son una propuesta de referencia; en cada caso se indica la alternativa razonable.

---

## 1. Visión general por capas

```mermaid
flowchart TB
  subgraph UI["Capa de interfaz"]
    U1["Panel del editor · configuración, revisión, aprobación"]
    U2["API REST / SDK"]
  end
  subgraph ORQ["Capa de orquestación"]
    O1["Orquestador de flujo · grafo de estados"]
    O2["Cola de trabajos · un job por capítulo"]
  end
  subgraph AG["Capa de agentes"]
    A1["Agentes de planificación"]
    A2["Agentes de escritura"]
    A3["Agentes de revisión"]
  end
  subgraph VER["Capa de verificación"]
    V1["Verificadores deterministas"]
    V2["Verificadores LLM-juez"]
  end
  subgraph MEM["Capa de memoria"]
    M1["Biblia estructurada · Postgres"]
    M2["Índice semántico · pgvector"]
    M3["Manuscrito versionado · objetos"]
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

```mermaid
flowchart LR
  ORQ["Orquestador"]
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
| **Orquestador** | Ejecuta el grafo de estados, reintentos, límites de coste y puntos de aprobación humana. No genera texto. | Estado del proyecto | Transiciones | Código, sin LLM |
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
  participant O as Orquestador
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

| Almacén | Contenido | Tecnología propuesta | Alternativa |
|---|---|---|---|
| Relacional | Proyecto, contexto, plan, fichas, biblia, informes de verificación, costes | PostgreSQL (JSONB para el contexto) | MySQL, SQLite en local |
| Vectorial | Fragmentos de capítulos con metadatos (capítulo, POV, personajes, localización) | pgvector en la misma base | Qdrant, Weaviate |
| Objetos | Versiones de capítulos, exportaciones, prompts y respuestas para auditoría | S3 o compatible (MinIO en local) | Sistema de archivos |
| Caché | Prompts repetidos, embeddings | Redis | Sin caché en fase inicial |

Cada capítulo se guarda con versión, estado (`borrador`, `editado`, `verificado`, `aprobado`, `revision_humana`) y los informes que lo produjeron, de modo que cualquier fallo es trazable hasta el prompt exacto.

---

## 7. Tecnología de referencia

| Componente | Propuesta | Por qué | Alternativa |
|---|---|---|---|
| Lenguaje | Python 3.12 | Ecosistema de IA y validación de esquemas | TypeScript (Node) |
| Orquestación de agentes | LangGraph (grafo de estados con persistencia) | Bucles, reintentos y puntos de pausa humana nativos | Temporal + código propio, CrewAI |
| Modelos | Claude Opus/Sonnet para escritura y planificación; Haiku para resúmenes, extracción y jueces | Calidad de prosa larga y coste escalonado | GPT, Gemini, modelos abiertos vía vLLM |
| Validación de esquema | Pydantic + JSON Schema derivado de la ontología | Contexto y fichas siempre tipados | Zod en TypeScript |
| Métricas de estilo | spaCy (es) + textstat | Frase media, legibilidad, léxico | Código propio |
| Cola de trabajos | Celery + Redis o RQ | Un job por capítulo, paralelismo controlado | Temporal, AWS SQS |
| API | FastAPI | Tipado, documentación automática | Flask, NestJS |
| Panel de editor | Next.js o Streamlit (MVP) | Revisión de plan, diff de capítulos, aprobación | Retool |
| Observabilidad | Langfuse (trazas de prompts, coste, latencia) + OpenTelemetry | Auditar cada decisión de los agentes | LangSmith, Arize |
| Exportación | Pandoc (EPUB, DOCX), WeasyPrint (PDF) | Formatos editoriales estándar | python-docx, ebooklib |
| Despliegue | Docker Compose en desarrollo; Kubernetes o ECS en producción | Aislar workers de agentes por coste | Serverless para API + workers en cola |

---

## 8. Despliegue

```mermaid
flowchart LR
  subgraph EDGE["Acceso"]
    U["Editor"] --> W["Panel web"]
    U --> API["API FastAPI"]
  end
  subgraph CORE["Núcleo"]
    API --> Q["Cola de trabajos"]
    Q --> WK1["Worker de planificación"]
    Q --> WK2["Workers de capítulo · escalables"]
    Q --> WK3["Worker de verificación"]
  end
  subgraph DATA["Datos"]
    PG["PostgreSQL + pgvector"]
    S3["Almacén de objetos"]
    RD["Redis"]
  end
  subgraph EXT["Servicios externos"]
    LLMs["API de modelos"]
    OBS["Langfuse"]
  end
  WK1 & WK2 & WK3 --> PG & S3 & RD
  WK1 & WK2 & WK3 --> LLMs
  WK1 & WK2 & WK3 --> OBS
```

---

## 9. Transversales

| Aspecto | Decisión |
|---|---|
| **Human-in-the-loop** | Dos puntos obligatorios (plan y manuscrito final) y uno condicional (capítulo que agota reintentos). El panel muestra diff y el informe que motivó la pausa. |
| **Control de coste** | Presupuesto por proyecto en tokens; el orquestador degrada a modelo rápido en editores y jueces si se supera el 80 %; alerta al 100 %. Estimación previa: novela estándar ≈ 30 capítulos × (1 escritura + 1,5 regeneraciones medias + edición + jueces). |
| **Paralelismo** | Planificación secuencial; capítulos secuenciales por defecto (dependen de la biblia). Paralelizable solo en estructuras corales con líneas independientes hasta su convergencia. |
| **Determinismo y reproducibilidad** | Semilla, versión de prompt, versión de modelo y contexto exacto guardados por capítulo. |
| **Seguridad y privacidad** | Sin datos personales en el brief; secretos en gestor de credenciales; prompts y salidas cifrados en reposo; retención configurable. |
| **Evaluación continua** | Conjunto de briefs de prueba; se mide tasa de aprobación al primer intento, fallos por tipo de verificador, coste por capítulo y valoración humana ciega de calidad. |
| **Versionado de la ontología** | La ontología tiene versión semántica; cada proyecto fija la suya y las migraciones se validan con el verificador de esquema. |

---

## 10. Plan de construcción por fases

```mermaid
flowchart LR
  F1["Fase 1 · MVP · 4-6 semanas"] --> F2["Fase 2 · Calidad · 4-6 semanas"] --> F3["Fase 3 · Producto · 6-8 semanas"]
  F1 --> F1a["Ontología como esquema · Contexto, Arquitecto, Escaletista, Escritor · verificadores deterministas · biblia mínima · salida Markdown"]
  F2 --> F2a["Resto de agentes de planificación · LLM-juez · Bibliotecario con extracción · índice semántico · panel de revisión"]
  F3 --> F3a["Verificación de manuscrito · originalidad · exportación editorial · control de coste · evaluación continua · multiusuario"]
```
