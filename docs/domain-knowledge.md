# domain-knowledge.md — Conocimiento de dominio: novelas de aventura personalizadas

> Propósito: árbol de conocimiento que el sistema usa como contexto para generar novelas de aventura **personalizadas para regalo**: el destinatario, sus seres queridos, sus lugares y sus recuerdos entran en la historia como personajes, localizaciones y hechos. Cada dimensión se representa como un árbol de decisión en Mermaid. Los nodos hoja se corresponden con claves del objeto de contexto descrito en `definitions.md`; la forma en que el sistema lo consume está en `architecture.md`.

**Cómo leer los árboles:** de izquierda a derecha, de lo general a lo particular. Los nodos intermedios agrupan; los nodos hoja deciden y deben poder expresarse como `clave: valor`.

**Dos objetivos del mismo peso.** La novela tiene que llevar los datos del destinatario de forma que se reconozca en ella, y tiene que funcionar como historia. Las dimensiones 1 a 8 sostienen lo segundo y la 9 lo primero; ninguna de las dos justifica sacrificar la otra.

---

## 0. Visión general

```mermaid
flowchart LR
  N["NOVELA DE AVENTURA PERSONALIZADA"]
  N --> E["1. Estructura narrativa"]
  N --> T["2. Tipo de aventura y tono"]
  N --> F["3. Formato y longitud"]
  N --> P["4. Personajes"]
  N --> M["5. Espacios y mundo"]
  N --> L["6. Lenguaje y estilo"]
  N --> TM["7. Temas y motivos"]
  N --> C["8. Restricciones y control"]
  N --> PZ["9. Personalización"]
```

---

## 1. Estructura narrativa

```mermaid
flowchart LR
  E["Estructura narrativa"] --> E0["Modelo estructural"]
  E --> E1["PLANTEAMIENTO · Acto I · ~22%"]
  E --> E2["NUDO · Acto II · ~55%"]
  E --> E3["DESENLACE · Acto III · ~23%"]

  E0 --> E01["Tres actos · Viaje del héroe · Episódico"]

  E1 --> E11["Mundo ordinario"]
  E1 --> E12["Detonante"]
  E1 --> E13["Primer umbral"]

  E2 --> E21["Pruebas, aliados y enemigos"]
  E2 --> E22["Punto medio · giro"]
  E2 --> E23["Escalada y crisis"]

  E3 --> E31["Clímax"]
  E3 --> E32["Resolución y retorno"]
  E3 --> E33["Tipo de final"]
```

---

## 2. Tipo de aventura y tono

El género primario es **siempre aventura**. Lo que se elige es el subgénero de aventura, y los valores están filtrados para un regalo: fuera lo que no encaja en un libro que se regala a una persona real.

```mermaid
flowchart LR
  T["Tipo de aventura y tono"] --> T1["Subgénero"]
  T --> T2["Tono"]
  T --> T3["Público objetivo"]
  T --> T4["Tipo de misión"]
  T --> T5["Conflicto y contenido"]

  T1 --> T1a["Realista e histórica: expedición, náutica, capa y espada, tesoro"]
  T1 --> T1b["Especulativa: fantasía épica, ciencia ficción, steampunk"]
  T1 --> T1c["Contemporánea: urbana, road novel"]

  T2 --> T2a["Épico · Ligero · Pulp · Melancólico"]
  T3 --> T3a["Infantil · Juvenil/YA · Adulto · Crossover · derivado de la edad del lector"]
  T4 --> T4a["Rescate · Búsqueda · Descubrimiento · Carrera · Protección"]
  T5 --> T5a["Conflicto externo + conflicto interno"]
  T5 --> T5b["Escalas 0-2: violencia, romance, lenguaje, temas sensibles"]
```

---

## 3. Formato y longitud

```mermaid
flowchart LR
  F["Formato y longitud"] --> F1["Extensión total"]
  F --> F2["Capítulos"]
  F --> F3["Ritmo"]
  F --> F4["Cronología"]

  F1 --> F1a["Fija: 10.000-15.000 palabras"]

  F2 --> F2a["Fijo: 10 capítulos de 1.000-1.500 palabras"]
  F2 --> F2b["Estructura interna: escena + secuela"]
  F2 --> F2c["Cierre: cliffhanger, giro, pausa"]

  F3 --> F3a["Curva de tensión por capítulo"]
  F3 --> F3b["Ratio acción / reflexión"]

  F4 --> F4a["Lineal · Con flashbacks"]
```

---

## 4. Personajes

```mermaid
flowchart LR
  P["Personajes"] --> P1["Roles narrativos"]
  P --> P2["Ficha de personaje"]
  P --> P3["Arco"]
  P --> P4["Relaciones y grupo"]
  P --> P5["Evolución del personaje"]
  P --> P6["Origen del personaje"]

  P1 --> P1a["Protagonista · Antagonista · Mentor"]
  P1 --> P1b["Aliados · Alivio cómico · Interés romántico"]
  P1 --> P1c["Guardián del umbral · Traidor · Secundarios"]

  P2 --> P2a["Identidad y físico"]
  P2 --> P2b["Deseo externo · Necesidad interna · Herida · Miedo"]
  P2 --> P2c["Habilidad distintiva · Defecto fatal · Voz"]

  P3 --> P3a["Positivo · Negativo · Plano · Redención · Corrupción"]

  P4 --> P4a["Alianza · Rivalidad · Mentoría · Familiar · Romance · Deuda"]
  P4 --> P4b["Solitario · Dúo · Compañía · Coral"]

  P5 --> P5a["Punto de partida"]
  P5 --> P5b["Punto de llegada"]
  P5 --> P5c["Momento de cambio"]
  P5 --> P5d["Qué cambia · Creencias · Habilidades · Relaciones"]

  P6 --> P6a["Real · destinatario o ser querido aportado por el comprador"]
  P6 --> P6b["Ficticio · inventado por el sistema"]
```

---

## 5. Espacios y mundo

```mermaid
flowchart LR
  M["Espacios y mundo"] --> M1["Tipo de mundo y época"]
  M --> M2["Niveles espaciales"]
  M --> M3["Geografía y viaje"]
  M --> M4["Sociedad y reglas"]
  M --> M5["Localizaciones clave"]

  M1 --> M1a["Real histórico · Contemporáneo · Alternativo · Secundario · Futuro"]
  M2 --> M2a["Macro (mundo) → Meso (región/ruta) → Micro (escena)"]
  M3 --> M3a["Ruta obligatoria · 2 localizaciones como mínimo"]
  M3 --> M3b["Lugares reales del comprador con prioridad"]
  M3 --> M3c["Biomas, clima, distancias, transporte, peligros"]
  M4 --> M4a["Poder, economía, religión, tecnología, costumbres"]
  M4 --> M4b["Reglas del mundo con límites y costes · solo en mundos no realistas"]
  M5 --> M5a["Hogar → Umbral → Pruebas → Refugio → Guarida → Clímax"]
```

---

## 6. Lenguaje y estilo

```mermaid
flowchart LR
  L["Lenguaje y estilo"] --> L1["Idioma y narrador"]
  L --> L2["Registro y voz"]
  L --> L3["Diálogo y prosa"]
  L --> L4["Léxico y recursos"]

  L1 --> L1a["es-ES"]
  L1 --> L1b["1ª persona · 3ª limitada · 3ª omnisciente · múltiple"]
  L1 --> L1c["Pretérito · Presente"]

  L2 --> L2a["Culto · Estándar · Coloquial · Arcaizante"]
  L2 --> L2b["Sobria · Lírica · Humorística · Pulp · Clásica"]

  L3 --> L3a["Proporción de diálogo · Tratamiento tú/usted/vos"]
  L3 --> L3b["Longitud de frase · Densidad descriptiva · Legibilidad"]

  L4 --> L4a["Léxico especializado · Glosario · Nombres · Palabras prohibidas"]
  L4 --> L4b["Presagios · Motivos · Documentos insertados"]
```

---

## 7. Temas y motivos

```mermaid
flowchart LR
  TM["Temas y motivos"] --> TM1["Tema central"]
  TM --> TM2["Pregunta dramática"]
  TM --> TM3["Símbolos y mensaje"]

  TM1 --> TM1a["Valor · Amistad · Libertad · Codicia"]
  TM1 --> TM1b["Identidad · Civilización vs naturaleza · Hogar"]
  TM2 --> TM2a["¿Conseguirá X antes de que Y?"]
  TM3 --> TM3a["Motivos recurrentes coherentes con el final"]
```

---

## 8. Restricciones y control de generación

```mermaid
flowchart LR
  C["Restricciones y control"] --> C1["Biblia de continuidad"]
  C --> C2["Líneas rojas"]
  C --> C3["Validaciones"]
  C --> C4["Parámetros de generación"]

  C1 --> C1a["Fichas · Localizaciones · Línea temporal · Inventario · Hechos"]
  C1 --> C1b["Uso de cada hecho por capítulo · Eventos datados"]
  C2 --> C2a["Contenido · Originalidad · Sensibilidad cultural"]
  C2 --> C2b["Vetos del comprador"]
  C3 --> C3a["Cierre de subtramas · Chéjov · Coherencia · Longitud · Estilo"]
  C3 --> C3b["Cobertura de hechos obligatorios"]
  C4 --> C4a["Escaleta por capítulo · Resumen acumulado · Metadatos"]
```

---

## 9. Personalización

Lo que el comprador aporta sobre la persona a la que regala la novela. Es la dimensión que la entrevista rellena primero y la que fija valores por defecto de casi todas las demás.

```mermaid
flowchart LR
  PZ["Personalización"] --> PZ1["Destinatario"]
  PZ --> PZ2["Comprador y ocasión"]
  PZ --> PZ3["Hechos aportados"]
  PZ --> PZ4["Texto libre"]
  PZ --> PZ5["Vetos"]
  PZ --> PZ6["Dedicatoria"]

  PZ1 --> PZ1a["Nombre · Fecha de nacimiento · Edad · Rasgos"]
  PZ1 --> PZ1b["Papel: protagonista · coprotagonista · secundario clave"]
  PZ1 --> PZ1c["Segundo destinatario opcional · parejas"]

  PZ2 --> PZ2a["Ocasión: cumpleaños · boda · aniversario · jubilación · nacimiento · graduación · sin ocasión"]
  PZ2 --> PZ2b["Relación: hijo · pareja · padre o madre · abuelo · amigo · compañero · otra"]
  PZ2 --> PZ2c["Edad del lector"]

  PZ3 --> PZ3a["Tipo: evento · rasgo · ser querido · lugar · objeto · frase"]
  PZ3 --> PZ3b["Prioridad: obligatorio · deseable"]

  PZ4 --> PZ4a["Anécdota o carta · no confiable · solo se extraen hechos"]
  PZ5 --> PZ5a["Palabras y temas que no deben aparecer"]
  PZ6 --> PZ6a["Texto de la portada"]
```

---

## 10. Orden de decisión recomendado (pipeline)

```mermaid
flowchart LR
  D0["0. Personalización · entrevista"] --> D1["1. Público y tono"]
  D1 --> D2["2. Subgénero y misión"]
  D2 --> D3["3. Capítulos · fijo en 10"]
  D3 --> D4["4. Estructura e hitos"]
  D4 --> D5["5. Personajes"]
  D5 --> D6["6. Mundo y ruta"]
  D6 --> D7["7. Tema"]
  D7 --> D8["8. Lenguaje y estilo"]
  D8 --> D9["9. Escaleta"]
  D9 --> D10["10. Generación"]
  D10 --> D11["11. Validación"]
  D11 -->|"fallo"| D9
  D11 -->|"ok"| D12["12. Entrega"]
  D0 -.->|"seres queridos"| D5
  D0 -.->|"lugares"| D6
  D0 -.->|"hechos obligatorios"| D9
```
