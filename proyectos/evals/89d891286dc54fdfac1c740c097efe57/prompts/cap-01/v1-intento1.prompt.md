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
      "texto": "Repasan los últimos detalles de la boda y juegan una partida rápida al juego de exploradores en la biblioteca; Nerea quiere ceñirse a su itinerario cerrado y Daniel prefiere improvisar un rato, hasta que el tablero se calienta y las páginas se despliegan solas: el juego se ha convertido en un atlas de verdad, con una voz que susurra entre sus páginas.",
      "tipo": "escena"
    },
    {
      "texto": "Del asombro pasan al miedo; dudan entre guardar el atlas y seguir con los preparativos o averiguar qué es. Lo abren juntos y una imagen del mirador de la sierra se dibuja sola sobre el papel.",
      "tipo": "secuela"
    }
  ],
  "hechos": [
    "h1",
    "h2",
    "h4",
    "h5"
  ],
  "hitos": [
    "detonante"
  ],
  "localizacion": "biblioteca_municipal",
  "mencionados": [
    "mostaza"
  ],
  "numero": 1,
  "objetivo": "Nerea y Daniel, en la biblioteca donde se conocieron, ven cómo su juego de mesa de exploradores se transforma en un atlas vivo que los llama a una aventura de verdad.",
  "palabras_objetivo": 1100,
  "plantar": [
    {
      "clave": "regla_atlas_dos_manos",
      "descripcion": "Una voz entre las páginas susurra que el atlas solo dibuja el camino cuando lo sostienen dos manos a la vez; ellos no le hacen caso al principio."
    }
  ],
  "pov": "nerea",
  "presentes": [
    "nerea",
    "daniel"
  ],
  "tension": 3,
  "traspasos": []
}
```

### Hechos del comprador en este capítulo

- [h1] evento: Se conocieron al quedarse encerrados en el ascensor de la biblioteca municipal durante una tormenta
- [h2] ser_querido: Su gata, Mostaza, que se tumba encima de cualquier mapa que abran
- [h4] objeto: Un juego de mesa de exploradores al que juegan desde su primera cita
- [h5] frase literal, tal cual: «Contigo, hasta el ascensor es una aventura»

### Vetos: palabras

- Rubén

### Vetos: temas

- traición

### Lista negra

- de repente
- sin duda
- no pudo evitar
- un escalofrío recorrió su espalda
- en ese instante

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
    "Nerea desplegó el itinerario sobre la mesa de la biblioteca, con sus casillas numeradas y sus horarios a prueba de despistes. —Aquí no hay margen para perderse —dijo, y justo entonces el mapa dejó de ser de papel.",
    "—Voy bien, voy bien —insistió Daniel, mirando el GPS al revés por tercera vez—. Es solo que la sierra ha cambiado de sitio.",
    "Brumal habló con voz de página vieja: «Según reza el atlas, dos manos que no se sueltan encuentran siempre el camino, aunque discutan por el camino que es»."
  ],
  "idioma": "es-ES",
  "lexico": [
    "cartografia",
    "exploracion"
  ],
  "metricas": {
    "descriptivo": 40,
    "frase_media_palabras": 13.0,
    "legibilidad_min": 40.0,
    "proporcion_dialogo": 40
  },
  "narrador": "multiple",
  "onomastica": "Los nombres reales (Nerea, Daniel, Mostaza) se mantienen exactos. Los personajes ficticios reciben nombres cortos y evocadores del mundo de la cartografía o la mitología ligera de exploradores, fáciles de pronunciar en voz alta, coherentes con el tono ligero y sin usar en ningún caso la palabra vetada 'Rubén'.",
  "prohibidas": [],
  "registro": "coloquial",
  "tiempo": "preterito",
  "voz": "cálida y cómplice, con el humor de una pareja que se conoce de memoria"
}
```

## Presagios pendientes e inventario vivo

### Presagios pendientes

Ninguno.

### Inventario

- atlas_viviente (El atlas viviente de los exploradores): nerea, desde el capítulo 0
- juego_mesa_exploradores (El juego de mesa de los exploradores): daniel, desde el capítulo 0

### Estado de los presentes

- nerea: A punto de casarse con Daniel, lleva encima el juego de exploradores que comparten desde la primera cita y un itinerario cerrado para el fin de semana.; sabe: Se conoció con Daniel en el ascensor de la biblioteca municipal durante una tormenta; El mirador de la sierra es donde Daniel le pidió matrimonio
- daniel: Lleva semanas preparando en secreto una sorpresa para el fin de semana de boda, sin sospechar que el juego de mesa va a cobrar vida antes de tiempo.; sabe: Se conoció con Nerea en el ascensor de la biblioteca municipal durante una tormenta; Le pidió matrimonio a Nerea en el mirador de la sierra

## Fichas de los personajes presentes

```json
[
  {
    "alias": [],
    "descripcion": "Organizada hasta la obsesión, lleva la logística de cualquier plan en una libreta que no suelta ni de broma; competitiva en los juegos de mesa, mide cada paso de la aventura como si fuera una partida que piensa ganar.",
    "ficha": {
      "alias": [],
      "arco": "positivo",
      "defecto": "le cuesta improvisar cuando el plan se tuerce",
      "descripcion": "Organizada hasta la obsesión, lleva la logística de cualquier plan en una libreta que no suelta ni de broma; competitiva en los juegos de mesa, mide cada paso de la aventura como si fuera una partida que piensa ganar.",
      "deseo": "demostrar que puede planificar la aventura perfecta hasta el último detalle",
      "estado_inicial": "A punto de casarse con Daniel, lleva encima el juego de exploradores que comparten desde la primera cita y un itinerario cerrado para el fin de semana.",
      "evolucion": null,
      "herida": null,
      "id": "nerea",
      "necesidad": "aprender a disfrutar de lo imprevisto sin soltar la mano de Daniel",
      "nombre": "Nerea",
      "origen": {
        "fuente": "destinatario",
        "tipo": "real"
      },
      "relaciones": [
        {
          "destino": "daniel",
          "estado_final": "casados en lo esencial, aprendiendo a compartir el mando de la aventura",
          "estado_inicial": "comprometidos y a un paso de la boda",
          "tipo": "romance"
        },
        {
          "destino": "mostaza",
          "estado_final": "agradece que Mostaza se siente justo donde hace falta mirar",
          "estado_inicial": "su dueña, algo resignada a que la gata arruine sus mapas",
          "tipo": "familiar"
        }
      ],
      "rol": [
        "protagonista"
      ],
      "sabe": [
        "Se conoció con Daniel en el ascensor de la biblioteca municipal durante una tormenta",
        "El mirador de la sierra es donde Daniel le pidió matrimonio"
      ],
      "voz": {
        "muletillas": [],
        "registro": "coloquial",
        "tratamiento": "tu"
      }
    },
    "id": "nerea",
    "nombre": "Nerea"
  },
  {
    "alias": [],
    "descripcion": "Cocina de maravilla y se pierde hasta con el GPS puesto; despistado y cariñoso, guarda desde niño la manía de mirar el paisaje en vez del mapa, lo que lo mete en líos y, a veces, lo saca de ellos.",
    "ficha": {
      "alias": [],
      "arco": "positivo",
      "defecto": "se despista con facilidad y pierde el rumbo",
      "descripcion": "Cocina de maravilla y se pierde hasta con el GPS puesto; despistado y cariñoso, guarda desde niño la manía de mirar el paisaje en vez del mapa, lo que lo mete en líos y, a veces, lo saca de ellos.",
      "deseo": "sorprender a Nerea con una aventura a la altura de la que le propuso en el mirador",
      "estado_inicial": "Lleva semanas preparando en secreto una sorpresa para el fin de semana de boda, sin sospechar que el juego de mesa va a cobrar vida antes de tiempo.",
      "evolucion": null,
      "herida": null,
      "id": "daniel",
      "necesidad": "confiar en su instinto en vez de perderse siempre en el camino",
      "nombre": "Daniel",
      "origen": {
        "fuente": "segundo_destinatario",
        "tipo": "real"
      },
      "relaciones": [
        {
          "destino": "nerea",
          "estado_final": "casados en lo esencial, aprendiendo a compartir el mando de la aventura",
          "estado_inicial": "comprometidos y a un paso de la boda",
          "tipo": "romance"
        },
        {
          "destino": "mostaza",
          "estado_final": "acepta que Mostaza tenga siempre razón sobre dónde mirar",
          "estado_inicial": "el que siempre le deja la manta más calentita a la gata",
          "tipo": "familiar"
        }
      ],
      "rol": [
        "protagonista"
      ],
      "sabe": [
        "Se conoció con Nerea en el ascensor de la biblioteca municipal durante una tormenta",
        "Le pidió matrimonio a Nerea en el mirador de la sierra"
      ],
      "voz": {
        "muletillas": [],
        "registro": "coloquial",
        "tratamiento": "tu"
      }
    },
    "id": "daniel",
    "nombre": "Daniel"
  }
]
```

## Localización y reglas del mundo aplicables

```json
[
  {
    "descripcion": "La biblioteca donde se conocieron atrapados en un ascensor durante una tormenta; ahora guarda, sin que nadie lo sepa, la sección de mapas donde el juego se convierte en atlas.",
    "estado": null,
    "hito": "detonante",
    "id": "biblioteca_municipal",
    "nivel": "micro",
    "nombre": "La biblioteca municipal",
    "padre": "pueblo"
  },
  {
    "descripcion": "El pueblo donde Nerea y Daniel se preparan para la boda, con su plaza, su biblioteca y sus vecinos curiosos.",
    "estado": null,
    "hito": null,
    "id": "pueblo",
    "nivel": "meso",
    "nombre": "El pueblo",
    "padre": "comarca"
  },
  {
    "descripcion": "Una comarca de pueblos de piedra y sierras cercanas, donde lo cotidiano y lo legendario conviven sin que nadie se sorprenda demasiado.",
    "estado": null,
    "hito": null,
    "id": "comarca",
    "nivel": "macro",
    "nombre": "La comarca",
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
