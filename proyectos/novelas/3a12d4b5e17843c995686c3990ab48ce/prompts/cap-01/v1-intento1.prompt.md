# Encargo del capítulo 1

Lee todas las secciones antes de escribir. La ficha del capítulo manda sobre todo lo demás.

## Ficha del capítulo

```json
{
  "cierre": "pausa",
  "cobrar": [],
  "dia": 1,
  "escenas": [
    {
      "texto": "Hugo prueba los prismáticos limpios en el porche de la cabaña, enfoca hacia el Pico Alto y distingue algo raro en la roca de la cima; al ajustar la lente comprueba que es una marca grabada, la misma silueta que recuerda haber visto de niño el día que subió y vio amanecer con Trasto.",
      "tipo": "escena"
    },
    {
      "texto": "Emocionado, baja corriendo a contárselo a su tío, pero este le resta importancia; Hugo duda entre insistir o guardárselo, y decide que mañana irá a preguntar a Tomás, el guardabosques, que algo sabrá del pico.",
      "tipo": "secuela"
    }
  ],
  "hechos": [
    "h1",
    "h2",
    "h3",
    "h4"
  ],
  "hitos": [
    "detonante"
  ],
  "localizacion": "cabana",
  "mencionados": [
    "guardabosques"
  ],
  "numero": 1,
  "objetivo": "Hugo descubre en los prismáticos de su abuela una marca grabada en la roca del pico que ya vio de niño.",
  "palabras_objetivo": 1200,
  "plantar": [
    {
      "clave": "marca_grabada",
      "descripcion": "Hugo ve una marca grabada en la roca del pico a través de los prismáticos de su abuela; no entiende su significado."
    }
  ],
  "pov": "prot",
  "presentes": [
    "prot",
    "trasto"
  ],
  "tension": 3,
  "traspasos": []
}
```

### Hechos del comprador en este capítulo

- [h1] ser_querido: Su perro, Trasto, un mestizo canela que le sigue a todas partes
- [h2] evento: Subió por primera vez con su perro al pico que hay sobre el valle y vio amanecer desde la cima
- [h3] lugar: La cabaña de su tío en el valle, donde pasa los veranos
- [h4] objeto: Los prismáticos de su abuela, que lleva siempre en la mochila

### Vetos: palabras

Ninguno.

### Vetos: temas

- araña

### Lista negra

- de repente
- la verdad es que
- sin embargo,
- en ese preciso instante
- no pudo evitar

## Informe del intento anterior

Ninguno.

## Guía de estilo

```json
{
  "dialogo": {
    "convencion": "raya",
    "proporcion": 40,
    "tratamiento": null
  },
  "ejemplos": [
    "Hugo apretó el paso por el sendero, con Trasto pisándole los talones. El aire olía a resina y a tierra mojada, y por encima de los árboles el Pico Alto asomaba, todavía dorado por el sol de la mañana. «Esto va a ser épico», pensó, y aceleró sin esperar a que su tío terminara de atarse las botas.",
    "—No es tu montaña, chaval —dijo Tomás, sin levantar la vista del cuaderno—. Y esa marca que dices haber visto no la enseño a cualquiera.\n—Pues enséñamela a mí —contestó Hugo—. Soy el único que sabe dónde está.",
    "El viento cortaba en el risco, y una piedra suelta rodó bajo su bota antes de que pudiera pensarlo dos veces. Trasto ladró una sola vez, grave, y Hugo entendió, por fin, que el perro llevaba razón desde el principio."
  ],
  "idioma": "es-ES",
  "lexico": [
    "montañismo",
    "cartografia"
  ],
  "metricas": {
    "descriptivo": 55,
    "frase_media_palabras": 12.0,
    "legibilidad_min": 55.0,
    "proporcion_dialogo": 40
  },
  "narrador": "tercera_limitada",
  "onomastica": "Los personajes reales (Hugo, Trasto) conservan su nombre y grafía exactos, tal como llegaron del comprador. Los ficticios reciben nombres castellanos sencillos y comunes en un entorno rural de montaña (Tomás, no inventos exóticos); los lugares ficticios se nombran por un rasgo físico o funcional en español llano (el risco del viento, la cascada del quebrado), nunca con nombres propios inventados que compitan con los reales del contexto.",
  "prohibidas": [],
  "registro": "estandar",
  "tiempo": "preterito",
  "voz": "cercana y aventurera, con detalle sensorial de montaña y ritmo ágil"
}
```

## Presagios pendientes e inventario vivo

### Presagios pendientes

Ninguno.

### Inventario

- diario_explorador (el cuaderno del explorador): guardabosques, desde el capítulo 0
- prismaticos (los prismáticos de la abuela): prot, desde el capítulo 0

### Estado de los presentes

- prot: Pasa el verano en la cabaña de su tío en el valle, impaciente por explorar antes de que acabe agosto.; sabe: Trasto es su perro y le sigue a todas partes; los prismáticos fueron de su abuela; subió una vez al pico y vio amanecer desde la cima; colecciona piedras con formas raras
- trasto: Vive junto a Hugo en la cabaña, siempre atento a cualquier rastro nuevo.; sabe: el camino de la cabaña al pico; el olor de Hugo entre mil

## Fichas de los personajes presentes

```json
[
  {
    "alias": [],
    "descripcion": "Catorce años, curioso hasta la exasperación, siempre con los prismáticos de su abuela en la mochila y una piedra rara en el bolsillo. Se orienta por las estrellas y por Trasto, aunque tarda en admitir que necesita a los dos.",
    "ficha": {
      "alias": [],
      "arco": "positivo",
      "defecto": "impaciencia",
      "descripcion": "Catorce años, curioso hasta la exasperación, siempre con los prismáticos de su abuela en la mochila y una piedra rara en el bolsillo. Se orienta por las estrellas y por Trasto, aunque tarda en admitir que necesita a los dos.",
      "deseo": "encontrar el tesoro escondido en el valle antes de que acabe el verano",
      "estado_inicial": "Pasa el verano en la cabaña de su tío en el valle, impaciente por explorar antes de que acabe agosto.",
      "evolucion": null,
      "herida": null,
      "id": "prot",
      "necesidad": "aprender a tener paciencia y a confiar en los demás en vez de adelantarse solo",
      "nombre": "Hugo",
      "origen": {
        "fuente": "destinatario",
        "tipo": "real"
      },
      "relaciones": [
        {
          "destino": "trasto",
          "estado_final": "aprende a seguir el olfato de Trasto antes que su propia prisa",
          "estado_inicial": "confía en Trasto pero se adelanta sin esperarlo",
          "tipo": "alianza"
        },
        {
          "destino": "guardabosques",
          "estado_final": "gana su confianza y hereda parte de lo que sabe del pico",
          "estado_inicial": "lo ve como un desconocido reservado y algo hosco",
          "tipo": "mentoria"
        }
      ],
      "rol": [
        "protagonista"
      ],
      "sabe": [
        "Trasto es su perro y le sigue a todas partes",
        "los prismáticos fueron de su abuela",
        "subió una vez al pico y vio amanecer desde la cima",
        "colecciona piedras con formas raras"
      ],
      "voz": {
        "muletillas": [],
        "registro": "coloquial",
        "tratamiento": "tu"
      }
    },
    "id": "prot",
    "nombre": "Hugo"
  },
  {
    "alias": [],
    "descripcion": "Mestizo canela, orejas de pillo, nariz que no descansa. Sigue a Hugo a todas partes desde cachorro y detecta antes que nadie cuándo algo va mal en el camino.",
    "ficha": {
      "alias": [],
      "arco": "plano",
      "defecto": "se distrae con cualquier rastro nuevo",
      "descripcion": "Mestizo canela, orejas de pillo, nariz que no descansa. Sigue a Hugo a todas partes desde cachorro y detecta antes que nadie cuándo algo va mal en el camino.",
      "deseo": "estar siempre junto a Hugo",
      "estado_inicial": "Vive junto a Hugo en la cabaña, siempre atento a cualquier rastro nuevo.",
      "evolucion": null,
      "herida": null,
      "id": "trasto",
      "necesidad": "que Hugo confíe en su olfato cuando se pierde el camino",
      "nombre": "Trasto",
      "origen": {
        "fuente": "h1",
        "tipo": "real"
      },
      "relaciones": [
        {
          "destino": "prot",
          "estado_final": "Hugo aprende a leer sus señales y a fiarse de ellas",
          "estado_inicial": "sigue a Hugo sin que este le haga caso del todo",
          "tipo": "alianza"
        }
      ],
      "rol": [
        "aliado"
      ],
      "sabe": [
        "el camino de la cabaña al pico",
        "el olor de Hugo entre mil"
      ],
      "voz": {
        "muletillas": [],
        "registro": "coloquial",
        "tratamiento": "tu"
      }
    },
    "id": "trasto",
    "nombre": "Trasto"
  }
]
```

## Localización y reglas del mundo aplicables

```json
[
  {
    "descripcion": "Una cabaña de madera junto al río donde Hugo pasa los veranos, con una estantería llena de fotos viejas y trastos de montaña.",
    "estado": null,
    "hito": "detonante",
    "id": "cabana",
    "nivel": "micro",
    "nombre": "La cabaña del tío",
    "padre": "valle"
  },
  {
    "descripcion": "Un valle verde entre laderas empinadas, atravesado por un río y cerrado al fondo por el Pico Alto.",
    "estado": null,
    "hito": null,
    "id": "valle",
    "nivel": "meso",
    "nombre": "El valle",
    "padre": "comarca"
  },
  {
    "descripcion": "Tierras de montaña salpicadas de pueblos pequeños, con un único valle profundo coronado por un pico que domina el horizonte.",
    "estado": null,
    "hito": null,
    "id": "comarca",
    "nivel": "macro",
    "nombre": "La comarca del valle alto",
    "padre": null
  }
]
```

### Reglas del mundo

Ninguno.

## Resumen acumulado

Ninguno.

## Capítulo anterior íntegro

Ninguno.
