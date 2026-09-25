# definitions.md — Definiciones, valores permitidos y esquema del contexto

> Propósito: diccionario de cada nodo de los árboles de `domain-knowledge.md`, con su definición, valores permitidos y parámetros de serialización. Incluye las dependencias del pipeline de decisión, el diccionario de términos narrativos y un ejemplo de instancia en YAML que sirve de referencia para el esquema de validación descrito en `architecture.md`.
>
> El producto es una **novela de aventura personalizada para regalo**, de 10 capítulos. Las dimensiones 1 a 8 describen la novela como historia; la 9 describe a quién se le regala y qué aporta el comprador.

---

## 1. Estructura narrativa

| Nodo | Definición | Valores / parámetros |
|---|---|---|
| **Modelo estructural** | Plantilla macro que organiza los hitos de la trama. | `tres_actos` (defecto), `viaje_heroe`, `episodico` |
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

Con 10 capítulos, los porcentajes por defecto dan un reparto de **2 / 6 / 2** capítulos por acto. `episodico` admite que cada capítulo cierre su propia peripecia —encaja con novelas hechas de recuerdos—, pero sigue exigiendo un hilo que atraviese los diez y un clímax en el acto III.

---

## 2. Tipo de aventura y tono

El género primario es **siempre aventura**. Los valores están filtrados para un regalo a una persona real: se han retirado los subgéneros, tonos y misiones que no encajan en ese uso.

| Nodo | Definición | Valores / parámetros |
|---|---|---|
| **Subgénero** | Convención de aventura que fija escenarios, iconografía y expectativas del lector. Se admite uno primario y hasta dos secundarios. | `primario`, `secundarios[]` de: `expedicion`, `nautica`, `capa_y_espada`, `tesoro`, `fantasia_epica`, `ciencia_ficcion`, `steampunk`, `urbana`, `road_novel` |
| **Tono** | Actitud emocional dominante de la narración. Condiciona el estilo y el nivel de contenido. Un valor principal; puede modularse por acto. | `epico`, `ligero`, `pulp`, `melancolico` |
| **Público objetivo** | Franja lectora. Determina complejidad léxica y límites de contenido. **Se deriva de la edad del lector** (§9) y el entrevistador puede cambiarlo. | `infantil` (<12), `juvenil` (12-17), `adulto` (≥18), `crossover` (solo por cambio explícito) |
| **Tipo de misión** | Objetivo concreto que estructura la trama ("qué se persigue"). Suele materializarse en un *MacGuffin*. **Obligatorio.** | `rescate`, `busqueda`, `descubrimiento`, `carrera`, `proteccion`; `macguffin{nombre, descripcion, por_que_importa}` |
| **Conflicto** | Fuerza opositora fundamental. Siempre se combina con un conflicto interno ligado al defecto del protagonista. | `externo[]` de: `persona_vs_naturaleza`, `persona_vs_persona`, `persona_vs_sociedad`, `persona_vs_desconocido`; `interno`: texto breve |
| **Nivel de contenido** | Escala 0 (ninguno) a 2 (moderado) por categoría. **Tope de 2 para cualquier público**: el nivel 3 (explícito) no existe en este producto. Debe ser coherente con el público. | Categorías `violencia`, `romance`, `lenguaje`, `sensibles`. Infantil ≤1, YA ≤2, Adulto ≤2 |

---

## 3. Formato y longitud

| Nodo | Definición | Valores / parámetros |
|---|---|---|
| **Extensión total** | Palabras objetivo del manuscrito completo. Consecuencia de los dos nodos siguientes, no un dato de entrada. | 10.000-15.000; `tolerancia %` |
| **Número de capítulos** | Fijo en este producto. No se deriva de la extensión. | `10` |
| Longitud de capítulo | Palabras por capítulo, igual para todos los públicos. | `min: 1000`, `max: 1500` |
| Estructura interna | Patrón *escena* (objetivo → conflicto → desastre) + *secuela* (reacción → dilema → decisión). | `escenas_por_capitulo` |
| Cierre de capítulo | Recurso con el que termina cada capítulo para sostener la lectura. Un valor para todos, o una lista de 10, uno por capítulo. | `cliffhanger`, `pausa`, `giro`, `pregunta`, `imagen` |
| Titulación y macroestructura | Forma de encabezar los capítulos. En la v1 solo la titulación, con valores cerrados; prólogo, epílogo, partes e interludios quedan fuera del alcance. Un valor fuera de la lista se exporta como `numerado_y_titulado`. | `titulacion`: `numerado`, `titulado`, `numerado_y_titulado` |
| **Curva de tensión** | Perfil objetivo de intensidad por capítulo (0-10), con picos en umbral, punto medio, crisis y clímax. | Array de 10 enteros |
| Ratio acción / reflexión | Proporción de escenas de acción física frente a escenas de introspección o diálogo. | Ej. `70/30` |
| **Cronología** | Orden en que se presentan los hechos respecto a su orden real. `analepsis` es la vía natural para contar recuerdos aportados. | `lineal`, `analepsis` |

---

## 4. Personajes

| Nodo | Definición | Valores / parámetros |
|---|---|---|
| **Rol narrativo** | Función que cumple el personaje en la trama, independiente de su personalidad. Un personaje puede acumular roles. | Lista de roles por `personaje.id`, de: `protagonista`, `antagonista`, `mentor`, `aliado`, `alivio_comico`, `interes_romantico`, `guardian_umbral`, `traidor`, `secundario` |
| **Origen** | Si el personaje es una persona real aportada por el comprador (el destinatario o un hecho `ser_querido`, §9) o un personaje inventado. Un personaje real conserva **el nombre exacto** del brief, y su ficha no puede contradecir los hechos aportados sobre él. | `real` con `fuente` (id de hecho o `destinatario`), `ficticio` |
| **Ficha de personaje** | Registro canónico que garantiza consistencia en toda la novela. Forma parte de la *biblia* (dimensión 8). | Objeto con los campos del diagrama |
| Deseo externo | Meta visible y concreta que persigue. Motor de la trama. | Texto breve |
| Necesidad interna | Carencia que debe resolver para completar su arco; a menudo opuesta al deseo. | Texto breve |
| Herida y miedo | Suceso pasado que explica el miedo y el defecto; el miedo se materializa en la crisis. | Texto breve |
| Defecto fatal | Rasgo que le pone en peligro y que la trama pondrá a prueba. | Texto breve |
| Voz | Forma de hablar: registro, ritmo, expresiones propias. Alimenta la dimensión 6. | `registro` (§6), `muletillas[]`, `tratamiento`: `tu`, `usted`, `vos` |
| **Arco** | Trayectoria de cambio del personaje entre mundo ordinario y retorno. | `positivo`, `negativo`, `plano`, `redencion`, `corrupcion` |
| **Relaciones** | Grafo dirigido entre personajes con tipo y evolución. | `origen`, `destino`, `tipo` (`alianza`, `rivalidad`, `mentoria`, `familiar`, `romance`, `deuda`), `estado_inicial`, `estado_final` |
| **Configuración del grupo** | Número y dinámica de personajes que viajan juntos. | Determina reparto de escenas y diálogos |

### Evolución del personaje

Concreta el **arco** en el tiempo de la novela. Obligatoria para el protagonista; recomendable para antagonista y aliado principal.

| Nodo | Definición | Valores / parámetros |
|---|---|---|
| **Punto de partida** | Cómo piensa y actúa el personaje en el mundo ordinario, gobernado por su defecto y por la creencia equivocada que sostiene. | `creencia_inicial`, `conducta_inicial` |
| **Punto de llegada** | Cómo piensa y actúa en el retorno. Debe diferir del punto de partida salvo en arcos planos. | `creencia_final`, `conducta_final` |
| **Momento de cambio** | Suceso o decisión que provoca la transformación. Suele coincidir con la crisis y siempre ocurre antes del clímax. | `capitulo`, `detonante` |
| **Qué cambia** | Aspectos en los que la evolución se hace visible al lector; al menos dos deben cambiar. | `creencias`, `habilidades`, `relaciones` (opcional: `estatus`, `moral`) |

Cuando el protagonista es el destinatario real, el **defecto fatal** y los arcos `negativo` y `corrupcion` se eligen con cuidado: el defecto es un rasgo amable y reconocible (testarudez, impaciencia), nunca uno que el destinatario pueda leer como un reproche, y el arco del destinatario es `positivo` o `plano`.

---

## 5. Espacios y mundo

| Nodo | Definición | Valores / parámetros |
|---|---|---|
| **Tipo de mundo** | Relación del escenario con la realidad. Condiciona el nivel de documentación histórica y de invención. | `real_historico`, `contemporaneo`, `alternativo`, `secundario`, `futuro` |
| **Época** | Momento temporal; en mundos reales, año o siglo; en secundarios, era interna. | `fecha_inicio`, `duracion_historia` |
| **Niveles espaciales** | Jerarquía de contención: cada escena ocurre en un *micro* que pertenece a un *meso* dentro de un *macro*. **Obligatorio**: todo evento de la cronología necesita un lugar. | Árbol de `localizacion{id, nivel, padre}` |
| **Ruta del viaje** | Secuencia ordenada de localizaciones que recorre el grupo; base del mapa y de la cronología. **Obligatoria, con 2 localizaciones como mínimo**, aunque sean cercanas. Los hechos `lugar` del comprador (§9) entran en la ruta con prioridad. | Lista ordenada de `localizacion.id` con `dias_viaje` |
| Peligros ambientales | Amenazas propias del entorno usadas como obstáculos (tormentas, fauna, hambre, frío). Opcional. | Lista |
| **Sociedad y cultura** | Estructuras humanas que generan conflicto social y color local. | Objeto por región |
| **Reglas del mundo** | Sistema de lo posible (física, magia, tecnología). Debe declarar límites y costes para evitar soluciones arbitrarias. **Solo cuando el tipo de mundo no es `real_historico` ni `contemporaneo`.** | `reglas[]`, `excepciones[]` |
| **Localizaciones clave** | Escenarios obligatorios vinculados a hitos de la dimensión 1. | Cada una enlaza a un hito estructural |

---

## 6. Lenguaje y estilo

| Nodo | Definición | Valores / parámetros |
|---|---|---|
| **Idioma y variante** | Lengua de salida y norma regional (léxico, tratamiento, ortotipografía). Único valor en este producto. | `es-ES` |
| **Narrador** | Instancia que cuenta la historia y su grado de acceso a la mente de los personajes. | `primera`, `tercera_limitada`, `tercera_omnisciente`, `multiple`; si `multiple`, definir rotación por capítulo |
| **Tiempo verbal** | Tiempo base de la narración. | `preterito` (defecto), `presente` |
| **Registro** | Nivel de formalidad del lenguaje narrativo. | `culto`, `estandar`, `coloquial`, `arcaizante` |
| **Voz autoral** | Personalidad estilística global; puede referirse a un tono o tradición, nunca a la copia de un autor concreto. | Descripción + 2-3 rasgos |
| **Diálogo** | Reglas de construcción del habla de los personajes. | `proporcion %`, `tratamiento`, `raya` o `comillas` |
| **Prosa** | Métricas de la escritura. | `frase_media_palabras`, `descriptivo 1-5`, `legibilidad` |
| Léxico especializado | Vocabulario técnico del subgénero que aporta verosimilitud. | Lista de dominios |
| Convención onomástica | Reglas para crear nombres coherentes (fonética, sufijos, cultura). No se aplica a los personajes reales, que conservan su nombre. | Texto + ejemplos |
| Palabras prohibidas | Términos o muletillas de estilo que el generador debe evitar. Van a la **lista negra** de la guía de estilo (severidad baja). No son los vetos del comprador (§9), que van al guardarraíl de palabras prohibidas y bloquean. | Lista |
| **Recursos narrativos** | Técnicas transversales que enriquecen la trama. | Lista activable |

---

## 7. Temas y motivos

| Nodo | Definición |
|---|---|
| **Tema central** | Idea abstracta que la trama explora; se demuestra mediante las decisiones del protagonista, no mediante discurso. |
| **Subtemas** | Ideas secundarias asociadas a personajes o subtramas. |
| **Pregunta dramática** | Pregunta que mantiene al lector hasta el final. Se formula al cerrar el planteamiento y se responde en el clímax. |
| **Motivos y símbolos** | Imágenes u objetos recurrentes que refuerzan el tema (una brújula, el mar, una cicatriz). Un hecho `objeto` del comprador es el mejor candidato a motivo. |
| **Mensaje** | Conclusión implícita que se desprende del desenlace. Debe ser coherente con el tipo de final. |

---

## 8. Restricciones y control de generación

| Nodo | Definición |
|---|---|
| **Biblia de continuidad** | Fuente de verdad que el generador consulta y actualiza tras cada capítulo para evitar contradicciones. Incluye fichas, localizaciones, línea temporal, inventario de objetos y hechos establecidos. Cada hecho registra **en qué capítulos se usa**, y la línea temporal se guarda como **eventos datados** (§9). |
| **Líneas rojas** | Prohibiciones absolutas derivadas del público, la política editorial, la propiedad intelectual y los **vetos del comprador** (§9). |
| **Validaciones automáticas** | Comprobaciones posteriores a la generación; un fallo devuelve el capítulo a reescritura. Incluyen la **cobertura**: todo hecho obligatorio aparece en al menos un capítulo. |
| **Escaleta** | Plan de cada capítulo: objetivo, escenas, personajes presentes, localización, hito estructural, palabras objetivo, cierre y **hechos aportados que usa**. Es la unidad de trabajo del generador. |
| Resumen acumulado | Síntesis de lo narrado hasta el capítulo actual que se inyecta como contexto en cada nueva generación. |
| **Metadatos editoriales** | Título, sinopsis, palabras clave, serie y volumen. Se generan al final del proceso. |

---

## 9. Personalización

Lo que el comprador aporta sobre la persona a la que regala la novela. La entrevista lo rellena primero, y fija valores por defecto de las dimensiones 2, 4, 5 y 8.

| Nodo | Definición | Valores / parámetros |
|---|---|---|
| **Destinatario** | Persona a la que se regala la novela. Aparece en ella con su nombre exacto. | `nombre`, `fecha_nacimiento`, `edad`, `rasgos[]` |
| Papel del destinatario | Lugar que ocupa en la historia. Por defecto, protagonista. | `protagonista` (defecto), `coprotagonista`, `secundario_clave` |
| Segundo destinatario | Para regalos a una pareja (boda, aniversario). Mismos campos que el destinatario; su papel es `coprotagonista`. | Opcional |
| **Ocasión** | Motivo del regalo. Fija valores por defecto de tono, tipo de final y líneas rojas. | `cumpleanos`, `boda`, `aniversario`, `jubilacion`, `nacimiento`, `graduacion`, `sin_ocasion` |
| **Relación** | Qué es el destinatario para el comprador. Condiciona tono y tratamiento. | `hijo`, `pareja`, `padre_madre`, `abuelo`, `amigo`, `companero`, `otra` |
| Edad del lector | Quién va a leer la novela. Por defecto, la edad del destinatario; en `nacimiento`, la leen los padres y el defecto es adulto. Determina el público (§2). | Entero |
| **Hecho aportado** | Dato concreto sobre el destinatario o su mundo que debe o puede aparecer en la novela. | `hecho{id, tipo, texto, prioridad, origen}`; `origen`: `entrevista`, `texto_libre`, `lector` |
| Tipo de hecho | Qué es el hecho y adónde va dentro del contexto. | `evento` → cronología, con `momento` y `lugar`; `rasgo` → ficha del destinatario; `ser_querido` → personaje con origen `real`; `lugar` → localización y ruta; `objeto` → inventario y candidato a motivo; `frase` → debe aparecer literalmente |
| Prioridad del hecho | Si su ausencia bloquea la novela. Por defecto son obligatorios el nombre del destinatario y hasta 5 hechos que elige el comprador; el resto es `deseable`. Todo obligatorio obligaría a meter los recuerdos con calzador. | `obligatorio`, `deseable` |
| Exclusión de un evento | Solo en hechos `evento`, opcional: a quién deja fuera de la historia desde ese momento (una muerte o una partida). `fuente` es la del personaje excluido —`destinatario`, `segundo_destinatario` o el id de un hecho `ser_querido` que exista—. Al salir de `contexto` se lleva a la cronología, y es lo que permite a Lean detectar que alguien reaparece. | `excluye{fuente, tipo}`; `tipo`: `muerte`, `partida` |
| Momento de un evento | Cuándo ocurrió. Puede ser una fecha o un periodo aproximado; solo los eventos con fecha entran en la comprobación de edad frente a fecha de nacimiento. El **lugar** de un evento es el id de una localización del mundo (§5): todo evento de la cronología necesita un lugar. | Fecha (`AAAA`, `AAAA-MM`, `AAAA-MM-DD`) o periodo en minúsculas (`infancia`, `adolescencia`…) |
| **Texto libre** | Anécdota o carta que pega el comprador. Es **contenido no confiable**: se guarda aparte, solo se extraen de él hechos con esta misma estructura, y nunca llega en crudo a quien escribe. | `ref` al fichero, `confiable: false` |
| **Vetos** | Palabras y temas que el comprador no quiere que aparezcan (por ejemplo, el nombre de una expareja). | `palabras[]`, `temas[]` |
| **Dedicatoria** | Texto de la portada. | Texto |
| Preferencias del comprador | Lo que el comprador pide en la entrevista sobre la novela. Viajan en `respuestas.preferencias` del brief y las traduce el Agente de Contexto a las claves de §1-§3; `publico` solo puede bajar el que da la edad (§10). | `tono`, `subgenero`, `cronologia`, `final`, `publico` |
| Datos excluidos | Datos personales que la novela no necesita y que se descartan siempre, aunque el comprador los aporte en la entrevista o en el texto libre. No son claves del contexto: se listan para que el esquema los rechace. | documento de identidad, teléfono, email, dirección exacta, datos bancarios, datos de salud |

**Uso de un hecho.** Cada hecho aportado registra los capítulos en que aparece. Es lo que permite comprobar la cobertura de los obligatorios y, cuando el lector corrige un hecho, saber qué capítulos hay que regenerar.

---

## 10. Orden de decisión recomendado (pipeline)

Las decisiones deben tomarse de lo general a lo particular, porque cada nivel fija valores por defecto del siguiente.

**Dependencias principales**

- Edad del lector → público → límites de contenido, legibilidad.
- Ocasión → tono, tipo de final, líneas rojas.
- Subgénero → léxico especializado, tipo de mundo, peligros ambientales.
- Número de capítulos (fijo, 10) → reparto de hitos por capítulo.
- Modelo estructural → localizaciones clave obligatorias → ruta del viaje.
- Hechos `lugar` → ruta del viaje; hechos `ser_querido` → personajes; hechos `evento` → cronología.
- Personajes (voz) → reglas de diálogo.
- Tema → tipo de final y mensaje.

**Coherencias que la entrevista comprueba** antes de dar el contexto por válido:

- Edad del lector frente a tono y nivel de contenido (un lector de 6 años con tono `melancolico` o contenido 2 es una contradicción).
- Edad declarada frente a fecha de nacimiento.
- Momento de cada evento frente a fecha de nacimiento del destinatario (no hay recuerdos anteriores a nacer).
- Ocasión frente a tipo de final (una `jubilacion` o una `boda` no admiten un final `agridulce` por defecto).

Cómo se concretan al validar, porque el enunciado de arriba admite más de una lectura:

- **Público frente a edad del lector**: el entrevistador puede **bajar** el público (un adulto puede leer una novela `infantil`), nunca subirlo por encima del que da la edad. `crossover` solo para lectores de 12 años o más.
- **Tono frente a edad**: un lector menor de 12 años no admite tono `melancolico`. El nivel de contenido lo acota ya la regla de §2.
- **Edad declarada frente a fecha de nacimiento**: se admite la edad cumplida a la fecha de validación y la que está a punto de cumplir, porque el regalo suele ser de cumpleaños.
- **Ocasión frente a final**: `boda` y `jubilacion` con final `agridulce` no se admiten.
- **Tema frente a final**: sin regla automática; no hay una correspondencia cerrada que comprobar.

Y la integridad que el contexto necesita para poder planificarse: a lo sumo 5 hechos `obligatorio`; los tres tramos de la estructura cubren los capítulos 1 a 10 sin huecos, con el punto medio y la crisis dentro del nudo y el clímax dentro del desenlace, y porcentajes que suman 100; exactamente un personaje con fuente `destinatario` (y otro con `segundo_destinatario` si lo hay), con arco `positivo` o `plano` y con el rol `protagonista` si ese es su papel; todo personaje `real` con una fuente válida y ningún `ficticio` con fuente; el árbol de localizaciones encadena `macro` → `meso` → `micro`, la ruta pasa solo por localizaciones del mundo y las reglas del mundo solo aparecen fuera de `real_historico` y `contemporaneo`.

---

## 11. Diccionario consolidado de términos

| Término | Definición breve |
|---|---|
| Acto | División macro de la trama (I planteamiento, II nudo, III desenlace). |
| Analepsis | Salto al pasado dentro de la narración (flashback). |
| Arco | Evolución interna de un personaje a lo largo de la historia. |
| Biblia | Documento de continuidad con todos los hechos canónicos de la obra. |
| Cliffhanger | Cierre de capítulo en un momento de máxima incertidumbre. |
| Clímax | Escena decisiva donde se resuelve el conflicto principal. |
| Comprador | Quien encarga la novela y aporta los datos del destinatario. |
| Dedicatoria | Texto de la portada, escrito por el comprador. |
| Destinatario | Persona real a la que se regala la novela y que aparece en ella. |
| Detonante | Suceso que rompe el equilibrio inicial e inicia la aventura. |
| Escaleta | Plan detallado de escenas de un capítulo previo a su redacción. |
| Escena / secuela | Unidad de acción (objetivo-conflicto-desastre) y unidad de reacción (emoción-dilema-decisión). |
| Focalización | Personaje a través de cuya percepción se narra un pasaje. |
| Guardián del umbral | Obstáculo o personaje que pone a prueba al héroe antes de un cambio de estado. |
| Hecho aportado | Dato del destinatario o de su mundo que el comprador pide incluir; tiene tipo y prioridad. |
| Hito estructural | Punto obligatorio del modelo elegido (umbral, punto medio, crisis, clímax). |
| MacGuffin | Objeto o meta que impulsa la trama, cuya naturaleza importa menos que su persecución. |
| Mundo ordinario | Situación de partida del protagonista. |
| Mundo secundario | Escenario ficticio con reglas propias, independiente de la realidad. |
| Narrador omnisciente | Voz que conoce pensamientos y hechos de todos los personajes. |
| Narrador limitado | Voz en tercera persona restringida a la percepción de un personaje. |
| Ocasión | Motivo del regalo (cumpleaños, boda, jubilación…). |
| Presagio | Anticipación sutil de un hecho futuro. |
| Pregunta dramática | Interrogante central que sostiene el interés hasta el final. |
| Punto de no retorno | Momento en que el protagonista ya no puede abandonar la aventura. |
| Punto medio | Giro central del nudo que redefine el objetivo o su comprensión. |
| Regla de Chéjov | Todo elemento destacado debe tener función posterior. |
| Subtrama | Línea argumental secundaria que apoya o contrasta con la principal. |
| Texto libre | Anécdota o carta pegada por el comprador; no confiable, solo fuente de hechos. |
| Tono | Actitud emocional global de la narración. |
| Veto | Palabra o tema que el comprador prohíbe en la novela. |
| Voz | Personalidad estilística reconocible del narrador o de un personaje. |

---

## 12. Ejemplo de instancia de contexto (YAML)

Todos los datos del ejemplo son ficticios.

```yaml
novela:
  personalizacion:
    destinatario:
      nombre: "Aitana"
      fecha_nacimiento: 2017-04-12
      edad: 9
      rasgos: [curiosa, testaruda, le_encantan_los_mapas]
      papel: protagonista
    segundo_destinatario: null
    ocasion: cumpleanos
    relacion: hijo
    edad_lector: 9
    hechos:
      - {id: h1, tipo: ser_querido, texto: "Su perra se llama Nala, una galga blanca", prioridad: obligatorio, origen: entrevista}
      - {id: h2, tipo: evento, texto: "Aprendió a nadar en la playa el verano de 2023", momento: 2023-07, lugar: playa, prioridad: obligatorio, origen: entrevista}
      - {id: h3, tipo: lugar, texto: "La casa de la abuela en el pueblo", prioridad: obligatorio, origen: entrevista}
      - {id: h4, tipo: objeto, texto: "Una brújula que le regaló su abuelo", prioridad: obligatorio, origen: entrevista}
      - {id: h5, tipo: frase, texto: "¡A la aventura, Nala!", prioridad: deseable, origen: entrevista}
    texto_libre: {ref: brief/texto_libre.txt, confiable: false}
    vetos: {palabras: [], temas: [hospitales]}
    dedicatoria: "Para Aitana, que ya sabe leer mapas. Feliz noveno cumpleaños."
  publico: infantil
  tono: ligero
  tipo_aventura:
    subgenero: {primario: tesoro, secundarios: [expedicion]}
    mision: busqueda
    macguffin: {nombre: "El mapa de la brújula", descripcion: "Un mapa escondido en la caja de la brújula del abuelo", por_que_importa: "Lleva al tesoro que el abuelo nunca llegó a buscar"}
    conflicto: {externo: [persona_vs_naturaleza, persona_vs_persona], interno: "no sabe pedir ayuda"}
    contenido: {violencia: 1, romance: 0, lenguaje: 0, sensibles: 0}
  formato:
    palabras_objetivo: 12000
    capitulos: 10
    longitud_capitulo: {min: 1000, max: 1500}
    cierre_capitulo: [pausa, cliffhanger, giro, cliffhanger, pregunta, giro, cliffhanger, cliffhanger, giro, imagen]
    titulacion: titulado
    cronologia: analepsis
    curva_tension: [3,4,5,5,6,7,6,8,9,5]
  estructura:
    modelo: tres_actos
    planteamiento: {capitulos: [1,2], detonante: "Nala desentierra la caja de la brújula del abuelo"}
    nudo: {capitulos: [3,8], punto_medio: 5, crisis: 8}
    desenlace: {capitulos: [9,10], climax: 9, final: cerrado}
  personajes:
    - id: prot
      origen: {tipo: real, fuente: destinatario}
      rol: [protagonista]
      deseo: "encontrar el tesoro del mapa"
      necesidad: "aprender a pedir ayuda"
      defecto: testarudez
      arco: positivo
      voz: {registro: coloquial, tratamiento: tu}
    - id: nala
      origen: {tipo: real, fuente: h1}
      rol: [aliado]
      arco: plano
    - id: antag
      origen: {tipo: ficticio}
      rol: [antagonista]
      deseo: "quedarse con el tesoro antes que nadie"
      arco: redencion
  mundo:
    tipo: contemporaneo
    epoca: {fecha_inicio: 2026, duracion_historia: "tres días"}
    localizaciones:
      - {id: comarca, nivel: macro, padre: null}
      - {id: pueblo, nivel: meso, padre: comarca}
      - {id: bosque, nivel: meso, padre: comarca}
      - {id: costa, nivel: meso, padre: comarca}
      - {id: casa_abuela, nivel: micro, padre: pueblo}
      - {id: cueva_final, nivel: micro, padre: bosque}
      - {id: faro, nivel: micro, padre: costa}
      - {id: playa, nivel: micro, padre: costa}
    ruta:
      - {id: casa_abuela, dias_viaje: 0}
      - {id: bosque, dias_viaje: 1}
      - {id: faro, dias_viaje: 1}
      - {id: cueva_final, dias_viaje: 1}
    reglas: []
  lenguaje:
    idioma: es-ES
    narrador: tercera_limitada
    tiempo: preterito
    registro: estandar
    voz: aventurera_con_humor
    dialogo: {proporcion: 40, convencion: raya}
    lexico: [cartografia]
    prohibidas: ["de repente", "sin embargo"]
  tema:
    central: valor_y_amistad
    pregunta_dramatica: "¿Encontrará Aitana el tesoro antes de que se lo lleve otro?"
  control:
    validaciones: [cierre_subtramas, chejov, coherencia_temporal, longitud, cobertura_hechos]
    lineas_rojas: [sin_contenido_explicito, vetos_del_comprador]
```
