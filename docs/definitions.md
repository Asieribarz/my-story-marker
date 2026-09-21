# definitions.md — Definiciones, valores permitidos y esquema del contexto

> Propósito: diccionario de cada nodo de los árboles de `domain-knowledge.md`, con su definición, valores permitidos y parámetros de serialización. Incluye las dependencias del pipeline de decisión, el diccionario de términos narrativos y un ejemplo de instancia en YAML que sirve de referencia para el esquema de validación descrito en `architecture.md`.

---

## 1. Estructura narrativa

| Nodo | Definición | Valores / parámetros |
|---|---|---|
| **Modelo estructural** | Plantilla macro que organiza los hitos de la trama. | `tres_actos`, `viaje_heroe`, `kishotenketsu`, `in_medias_res`, `coral`, `episodico` |
| **Planteamiento** | Presenta al protagonista, su mundo, su carencia y el problema que rompe el equilibrio. Termina cuando el protagonista se compromete con la aventura. | `porcentaje` (defecto 22%), `capitulos_asignados` |
| Mundo ordinario | Estado inicial del protagonista antes del cambio. Sirve para medir el arco. | Escena o capítulo inicial |
| Detonante | Suceso externo que lanza la aventura (mapa hallado, secuestro, naufragio, mensaje). Puede ir seguido de un rechazo inicial y de la aparición de un mentor. | `tipo_detonante`, `capitulo`, `mentor.tipo` |
| Primer umbral | Momento en que ya no se puede volver atrás. Cierra el Acto I. | `capitulo` |
| **Nudo** | Desarrollo del conflicto: obstáculos crecientes, alianzas, traiciones y aprendizaje. Debe contener al menos un giro. | `porcentaje` (defecto 55%), `numero_de_pruebas`, `giros` |
| Pruebas, aliados y enemigos | Secuencia de obstáculos que revelan habilidades y forjan el grupo. | Lista de `prueba{tipo, coste, aprendizaje}` |
| Punto medio | Revelación o inversión que cambia la comprensión del objetivo. | `tipo`: falsa victoria, falsa derrota, revelación |
| Escalada y crisis | Aumento de apuestas con una pérdida significativa, seguido del punto más bajo, en el que el protagonista debe cambiar internamente para continuar. | `perdida{que, quien}`, `crisis.capitulo` |
| **Desenlace** | Confrontación final y cierre. Todas las subtramas abiertas deben resolverse o dejarse abiertas de forma deliberada. | `porcentaje` (defecto 23%) |
| Clímax | Escena de máxima tensión donde se decide el conflicto principal. | `localizacion_climax`, `coste` |
| Resolución y retorno | Consecuencias inmediatas, cierre de hilos secundarios y nuevo equilibrio que muestra el cambio del protagonista. | Lista de subtramas cerradas, `elixir` |
| Tipo de final | Grado de cierre y tono emocional del final. | `cerrado`, `abierto`, `agridulce`, `gancho_saga`, `giro_final` |

---

## 2. Tipo de aventura

| Nodo | Definición | Notas de uso |
|---|---|---|
| **Subgénero** | Convención principal que fija escenarios, iconografía y expectativas del lector. Se admite uno primario y hasta dos secundarios. | `primario`, `secundarios[]` |
| **Tono** | Actitud emocional dominante de la narración. Condiciona el estilo y el nivel de contenido. | Un valor principal; puede modularse por acto |
| **Público objetivo** | Franja lectora. Determina complejidad léxica, longitud de capítulo y límites de contenido. | Fija valores por defecto en las dimensiones 3, 6 y 8 |
| **Tipo de misión** | Objetivo concreto que estructura la trama ("qué se persigue"). Suele materializarse en un *MacGuffin*. | `macguffin{nombre, descripcion, por_que_importa}` |
| **Conflicto** | Fuerza opositora fundamental: persona vs naturaleza, vs persona, vs sociedad, vs lo desconocido. Siempre se combina con un conflicto interno ligado al defecto del protagonista. | `externo`, `interno` |
| **Nivel de contenido** | Escala 0 (ninguno) a 3 (explícito) por categoría. Debe ser coherente con el público. | Infantil ≤1, YA ≤2, Adulto ≤3 |

---

## 3. Formato y longitud

| Nodo | Definición | Valores / parámetros |
|---|---|---|
| **Extensión total** | Palabras objetivo del manuscrito completo. | `palabras_objetivo`, `tolerancia %` |
| **Número de capítulos** | Derivado: `palabras_objetivo / longitud_media_capitulo`. Se distribuye entre actos según los porcentajes de la dimensión 1. | Entero; recomendado 20-40 para novela estándar |
| Longitud media de capítulo | Palabras por capítulo. Juvenil: 1.500-2.500; adulto: 2.500-5.000. | `min`, `max`, `media` |
| Estructura interna | Patrón *escena* (objetivo → conflicto → desastre) + *secuela* (reacción → dilema → decisión). | `escenas_por_capitulo` |
| Cierre de capítulo | Recurso con el que termina cada capítulo para sostener la lectura. | `cliffhanger`, `pausa`, `giro`, `pregunta`, `imagen` |
| Titulación y macroestructura | Forma de encabezar los capítulos y elementos superiores: prólogo, epílogo, partes, interludios, mapa, glosario. | `titulacion`, booleanos y listas |
| **Curva de tensión** | Perfil objetivo de intensidad por capítulo (0-10), con picos en umbral, punto medio, crisis y clímax. | Array de enteros |
| Ratio acción / reflexión | Proporción de escenas de acción física frente a escenas de introspección o diálogo. | Ej. `70/30` |
| **Cronología** | Orden en que se presentan los hechos respecto a su orden real. | `lineal`, `analepsis`, `doble_linea`, `enmarcada` |

---

## 4. Personajes

| Nodo | Definición | Valores / parámetros |
|---|---|---|
| **Rol narrativo** | Función que cumple el personaje en la trama, independiente de su personalidad. Un personaje puede acumular roles. | Lista de roles por `personaje.id` |
| **Ficha de personaje** | Registro canónico que garantiza consistencia en toda la novela. Forma parte de la *biblia* (dimensión 8). | Objeto con los campos del diagrama |
| Deseo externo | Meta visible y concreta que persigue. Motor de la trama. | Texto breve |
| Necesidad interna | Carencia que debe resolver para completar su arco; a menudo opuesta al deseo. | Texto breve |
| Herida y miedo | Suceso pasado que explica el miedo y el defecto; el miedo se materializa en la crisis. | Texto breve |
| Defecto fatal | Rasgo que le pone en peligro y que la trama pondrá a prueba. | Texto breve |
| Voz | Forma de hablar: registro, ritmo, expresiones propias. Alimenta la dimensión 6. | `registro`, `muletillas[]`, `tratamiento` |
| **Arco** | Trayectoria de cambio del personaje entre mundo ordinario y retorno. | `positivo`, `negativo`, `plano`, `redencion`, `corrupcion` |
| **Relaciones** | Grafo dirigido entre personajes con tipo y evolución. | `origen`, `destino`, `tipo`, `estado_inicial`, `estado_final` |
| **Configuración del grupo** | Número y dinámica de personajes que viajan juntos. | Determina reparto de escenas y diálogos |

### Evolución del personaje

Concreta el **arco** en el tiempo de la novela. Obligatoria para el protagonista; recomendable para antagonista y aliado principal.

| Nodo | Definición | Valores / parámetros |
|---|---|---|
| **Punto de partida** | Cómo piensa y actúa el personaje en el mundo ordinario, gobernado por su defecto y por la creencia equivocada que sostiene. | `creencia_inicial`, `conducta_inicial` |
| **Punto de llegada** | Cómo piensa y actúa en el retorno. Debe diferir del punto de partida salvo en arcos planos. | `creencia_final`, `conducta_final` |
| **Momento de cambio** | Suceso o decisión que provoca la transformación. Suele coincidir con la crisis y siempre ocurre antes del clímax. | `capitulo`, `detonante` |
| **Qué cambia** | Aspectos en los que la evolución se hace visible al lector; al menos dos deben cambiar. | `creencias`, `habilidades`, `relaciones` (opcional: `estatus`, `moral`) |

---

## 5. Espacios y mundo

| Nodo | Definición | Valores / parámetros |
|---|---|---|
| **Tipo de mundo** | Relación del escenario con la realidad. Condiciona el nivel de documentación histórica y de invención. | Enum del diagrama |
| **Época** | Momento temporal; en mundos reales, año o siglo; en secundarios, era interna. | `fecha_inicio`, `duracion_historia` |
| **Niveles espaciales** | Jerarquía de contención: cada escena ocurre en un *micro* que pertenece a un *meso* dentro de un *macro*. | Árbol de `localizacion{id, nivel, padre}` |
| **Ruta del viaje** | Secuencia ordenada de localizaciones que recorre el grupo; base del mapa y de la cronología. | Lista ordenada de `localizacion.id` con `dias_viaje` |
| Peligros ambientales | Amenazas propias del entorno usadas como obstáculos (tormentas, fauna, hambre, frío). | Lista |
| **Sociedad y cultura** | Estructuras humanas que generan conflicto social y color local. | Objeto por región |
| **Reglas del mundo** | Sistema de lo posible (física, magia, tecnología). Debe declarar límites y costes para evitar soluciones arbitrarias. | `reglas[]`, `excepciones[]` |
| **Localizaciones clave** | Escenarios obligatorios vinculados a hitos de la dimensión 1. | Cada una enlaza a un hito estructural |

---

## 6. Lenguaje y estilo

| Nodo | Definición | Valores / parámetros |
|---|---|---|
| **Idioma y variante** | Lengua de salida y norma regional (léxico, tratamiento, ortotipografía). | `codigo_idioma`, `pais` |
| **Narrador** | Instancia que cuenta la historia y su grado de acceso a la mente de los personajes. | Enum del diagrama; si `multiple`, definir rotación por capítulo |
| **Tiempo verbal** | Tiempo base de la narración. | `preterito` (defecto), `presente` |
| **Registro** | Nivel de formalidad del lenguaje narrativo. | Enum |
| **Voz autoral** | Personalidad estilística global; puede referirse a un tono o tradición, nunca a la copia de un autor concreto. | Descripción + 2-3 rasgos |
| **Diálogo** | Reglas de construcción del habla de los personajes. | `proporcion %`, `tratamiento`, `raya|comillas` |
| **Prosa** | Métricas de la escritura. | `frase_media_palabras`, `descriptivo 1-5`, `legibilidad` |
| Léxico especializado | Vocabulario técnico del subgénero que aporta verosimilitud. | Lista de dominios |
| Convención onomástica | Reglas para crear nombres coherentes (fonética, sufijos, cultura). | Texto + ejemplos |
| Palabras prohibidas | Términos o muletillas que el generador debe evitar. | Lista |
| **Recursos narrativos** | Técnicas transversales que enriquecen la trama. | Lista activable |

---

## 7. Temas y motivos

| Nodo | Definición |
|---|---|
| **Tema central** | Idea abstracta que la trama explora; se demuestra mediante las decisiones del protagonista, no mediante discurso. |
| **Subtemas** | Ideas secundarias asociadas a personajes o subtramas. |
| **Pregunta dramática** | Pregunta que mantiene al lector hasta el final. Se formula al cerrar el planteamiento y se responde en el clímax. |
| **Motivos y símbolos** | Imágenes u objetos recurrentes que refuerzan el tema (una brújula, el mar, una cicatriz). |
| **Mensaje** | Conclusión implícita que se desprende del desenlace. Debe ser coherente con el tipo de final. |

---

## 8. Restricciones y control de generación

| Nodo | Definición |
|---|---|
| **Biblia de continuidad** | Fuente de verdad que el generador consulta y actualiza tras cada capítulo para evitar contradicciones. Incluye fichas, localizaciones, línea temporal, inventario de objetos y hechos establecidos. |
| **Líneas rojas** | Prohibiciones absolutas derivadas del público, la política editorial y la propiedad intelectual. |
| **Validaciones automáticas** | Comprobaciones posteriores a la generación; un fallo devuelve el capítulo a reescritura. |
| **Escaleta** | Plan de cada capítulo: objetivo, escenas, personajes presentes, localización, hito estructural, palabras objetivo y cierre. Es la unidad de trabajo del generador. |
| Resumen acumulado | Síntesis de lo narrado hasta el capítulo actual que se inyecta como contexto en cada nueva generación. |
| **Metadatos editoriales** | Título, sinopsis, palabras clave, serie y volumen. Se generan al final del proceso. |

---

## 9. Orden de decisión recomendado (pipeline)

Las decisiones deben tomarse de lo general a lo particular, porque cada nivel fija valores por defecto del siguiente.

**Dependencias principales**

- Público → límites de contenido, longitud de capítulo, legibilidad.
- Subgénero → léxico especializado, tipo de mundo, peligros ambientales.
- Extensión → número de capítulos → reparto de hitos por capítulo.
- Modelo estructural → localizaciones clave obligatorias → ruta del viaje.
- Personajes (voz) → reglas de diálogo.
- Tema → tipo de final y mensaje.

---

## 10. Diccionario consolidado de términos

| Término | Definición breve |
|---|---|
| Acto | División macro de la trama (I planteamiento, II nudo, III desenlace). |
| Analepsis | Salto al pasado dentro de la narración (flashback). |
| Arco | Evolución interna de un personaje a lo largo de la historia. |
| Biblia | Documento de continuidad con todos los hechos canónicos de la obra. |
| Cliffhanger | Cierre de capítulo en un momento de máxima incertidumbre. |
| Clímax | Escena decisiva donde se resuelve el conflicto principal. |
| Detonante | Suceso que rompe el equilibrio inicial e inicia la aventura. |
| Escaleta | Plan detallado de escenas de un capítulo previo a su redacción. |
| Escena / secuela | Unidad de acción (objetivo-conflicto-desastre) y unidad de reacción (emoción-dilema-decisión). |
| Focalización | Personaje a través de cuya percepción se narra un pasaje. |
| Guardián del umbral | Obstáculo o personaje que pone a prueba al héroe antes de un cambio de estado. |
| Hito estructural | Punto obligatorio del modelo elegido (umbral, punto medio, crisis, clímax). |
| In medias res | Comienzo en plena acción, con el planteamiento diferido. |
| Kishōtenketsu | Estructura de cuatro partes (introducción, desarrollo, giro, conclusión) sin conflicto central obligatorio. |
| MacGuffin | Objeto o meta que impulsa la trama, cuya naturaleza importa menos que su persecución. |
| Mundo ordinario | Situación de partida del protagonista. |
| Mundo secundario | Escenario ficticio con reglas propias, independiente de la realidad. |
| Narrador omnisciente | Voz que conoce pensamientos y hechos de todos los personajes. |
| Narrador limitado | Voz en tercera persona restringida a la percepción de un personaje. |
| Presagio | Anticipación sutil de un hecho futuro. |
| Pregunta dramática | Interrogante central que sostiene el interés hasta el final. |
| Punto de no retorno | Momento en que el protagonista ya no puede abandonar la aventura. |
| Punto medio | Giro central del nudo que redefine el objetivo o su comprensión. |
| Regla de Chéjov | Todo elemento destacado debe tener función posterior. |
| Subtrama | Línea argumental secundaria que apoya o contrasta con la principal. |
| Tono | Actitud emocional global de la narración. |
| Voz | Personalidad estilística reconocible del narrador o de un personaje. |

---

## 11. Ejemplo de instancia de contexto (YAML)

```yaml
novela:
  publico: juvenil
  tono: epico_ligero
  tipo_aventura:
    subgenero_primario: nautica_piratas
    subgenero_secundario: [busqueda_tesoro]
    mision: busqueda_de_objeto
    macguffin: "El astrolabio de Ámbar"
    conflicto: [persona_vs_persona, persona_vs_naturaleza]
    contenido: {violencia: 2, romance: 1, lenguaje: 1, sensibles: 1}
  formato:
    palabras_objetivo: 75000
    capitulos: 30
    longitud_capitulo: {min: 2000, max: 3000}
    cierre_capitulo: cliffhanger_alternado
    titulacion: titulado
    cronologia: lineal
    curva_tension: [3,4,5,6,5,6,7,6,7,8,6,7,8,9,7,6,7,8,8,9,7,8,9,9,8,9,10,8,6,4]
  estructura:
    modelo: viaje_heroe
    planteamiento: {capitulos: [1,7], detonante: "carta del padre desaparecido"}
    nudo: {capitulos: [8,23], punto_medio: 15, crisis: 23}
    desenlace: {capitulos: [24,30], climax: 27, final: agridulce}
  personajes:
    - id: prot
      rol: [protagonista]
      deseo: "encontrar a su padre"
      necesidad: "aceptar que puede liderar"
      defecto: impulsividad
      arco: positivo
      voz: {registro: coloquial, tratamiento: tu}
    - id: antag
      rol: [antagonista]
      deseo: "controlar la ruta comercial"
      arco: plano
  mundo:
    tipo: historia_alternativa
    epoca: "siglo XVII"
    ruta: [puerto_origen, isla_niebla, arrecife_roto, fortaleza_final]
    reglas: ["sin magia; tecnología de época verosímil"]
  lenguaje:
    idioma: es-ES
    narrador: tercera_limitada
    tiempo: preterito
    registro: estandar
    voz: cinematografica_con_humor
    dialogo: {proporcion: 40, convencion: raya}
    lexico: [nautico]
    prohibidas: ["de repente", "sin embargo"]
  tema:
    central: identidad_y_madurez
    pregunta_dramatica: "¿Encontrará a su padre antes de que la flota del antagonista llegue al arrecife?"
  control:
    validaciones: [cierre_subtramas, chejov, coherencia_temporal, longitud]
    lineas_rojas: [sin_personajes_protegidos, sin_contenido_explicito]
```
