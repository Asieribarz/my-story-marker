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
      "texto": "Nerea repasa su libreta de tareas para la boda mientras Daniel cocina y Mostaza dormita sobre la caja del tablero de los Exploradores; al querer sacar las piezas para la partida de cada noche, la gata vuelca la caja y de su fondo falso cae un mapa amarillento que ninguno de los dos recuerda haber guardado, con una ruta trazada a mano que termina en la biblioteca municipal. Al mirarlo con más calma descubren que también falta una pieza del tablero, la del explorador con la brújula.",
      "tipo": "escena"
    },
    {
      "texto": "Sorprendidos, discuten qué hacer: Nerea quiere archivar el hallazgo hasta después de la boda para no descuadrar los preparativos, Daniel insiste en que un mapa así no puede esperar. Entre bromas y un vistazo al reloj, acuerdan acercarse a la biblioteca esa misma tarde, solo para salir de dudas.",
      "tipo": "secuela"
    }
  ],
  "hechos": [
    "h2",
    "h4"
  ],
  "hitos": [
    "detonante"
  ],
  "localizacion": "piso",
  "mencionados": [],
  "numero": 1,
  "objetivo": "Nerea descubre, junto con Daniel y Mostaza, un mapa oculto que cae de la caja del tablero de los Exploradores y decide que deben seguirlo antes de la boda.",
  "palabras_objetivo": 1200,
  "plantar": [
    {
      "clave": "pieza_perdida",
      "descripcion": "Falta la pieza del explorador con la brújula en el tablero de los Exploradores; nadie sabe dónde ha ido a parar."
    }
  ],
  "pov": "prot_nerea",
  "presentes": [
    "prot_nerea",
    "prot_daniel",
    "mostaza"
  ],
  "tension": 3,
  "traspasos": []
}
```

### Hechos del comprador en este capítulo

- [h2] ser_querido: Su gata, Mostaza, que se tumba encima de cualquier mapa que abran
- [h4] objeto: Un juego de mesa de exploradores al que juegan desde su primera cita

### Vetos: palabras

- Rubén

### Vetos: temas

- traición

### Lista negra

- Rubén
- de repente
- sin previo aviso
- un escalofrío recorrió su espalda
- en ese preciso instante

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
    "Nerea contó las piezas del tablero por tercera vez esa tarde, como si fueran a multiplicarse solas. —Falta una —dijo, y Daniel, sin levantar la vista de la sartén, respondió—: Seguro que se ha ido a buscar aventuras sin nosotros.",
    "Daniel se detuvo en la bifurcación del sendero y giró el mapa dos veces, tres, buscando un norte que no terminaba de encontrar. —Confía en mí —dijo, sin estar del todo seguro de a quién se lo pedía.",
    "Mostaza se sentó justo en el centro del mapa desplegado, como llevaba haciendo toda la vida. —Contigo, hasta el ascensor es una aventura —murmuró Nerea, y por primera vez en días dejó de mirar el reloj."
  ],
  "idioma": "es-ES",
  "lexico": [
    "cartografia",
    "exploracion",
    "reliquia"
  ],
  "metricas": {
    "descriptivo": 45,
    "frase_media_palabras": 14.0,
    "legibilidad_min": 40.0,
    "proporcion_dialogo": 40
  },
  "narrador": "multiple",
  "onomastica": "Los personajes reales (Nerea, Daniel, Mostaza) conservan su nombre y grafía tal cual, sin variaciones ni diminutivos nuevos. Cualquier personaje secundario ficticio que se necesite recibe un nombre castellano sencillo, coherente con el entorno de ciudad o sierra, y nunca 'Rubén' ni derivados.",
  "prohibidas": [],
  "registro": "estandar",
  "tiempo": "preterito",
  "voz": "cálida y cómplice, con humor ligero, alternando la mirada de Nerea y de Daniel"
}
```

## Presagios pendientes e inventario vivo

### Presagios pendientes

Ninguno.

### Inventario

- mapa_oculto (El mapa que ninguno recordaba haber guardado): prot_daniel, desde el capítulo 0
- tablero_exploradores (El tablero de los Exploradores): prot_nerea, desde el capítulo 0

### Estado de los presentes

- prot_nerea: A tres días de la boda, repasando la lista de tareas pendientes mientras Daniel busca las piezas del juego.; sabe: Que conoció a Daniel atrapados en el ascensor de la biblioteca municipal durante una tormenta.; Que Daniel se pierde incluso con el GPS puesto.; Que Mostaza se tumba siempre encima de cualquier mapa que abren.
- prot_daniel: Preparando algo rico para cenar mientras finge que ha memorizado el orden de la ceremonia.; sabe: Que conoció a Nerea en aquel ascensor durante la tormenta.; Que juegan a los Exploradores desde su primera cita.; Que le pidió matrimonio en el mirador de la sierra.
- mostaza: Dormitando encima de la caja del juego de mesa, como cada tarde.

## Fichas de los personajes presentes

```json
[
  {
    "alias": [],
    "descripcion": "Organizada hasta la médula: lleva el itinerario de la boda en una libreta con pestañas de colores y no soporta los imprevistos, salvo cuando el imprevisto es una partida.",
    "ficha": {
      "alias": [],
      "arco": "positivo",
      "defecto": "se aferra a la planificación y le cuesta improvisar",
      "descripcion": "Organizada hasta la médula: lleva el itinerario de la boda en una libreta con pestañas de colores y no soporta los imprevistos, salvo cuando el imprevisto es una partida.",
      "deseo": "completar la ruta del mapa antes de la boda, con todo bajo control",
      "estado_inicial": "A tres días de la boda, repasando la lista de tareas pendientes mientras Daniel busca las piezas del juego.",
      "evolucion": null,
      "herida": null,
      "id": "prot_nerea",
      "necesidad": "aprender a soltar el plan y dejar que la aventura la sorprenda",
      "nombre": "Nerea",
      "origen": {
        "fuente": "destinatario",
        "tipo": "real"
      },
      "relaciones": [
        {
          "destino": "prot_daniel",
          "estado_final": "a punto de casarse, habiendo aprendido a improvisar juntos",
          "estado_inicial": "prometidos, a tres días de la boda",
          "tipo": "romance"
        },
        {
          "destino": "mostaza",
          "estado_final": "la cuida igual, con una manía nueva: dejarla decidir cuándo se abre un mapa",
          "estado_inicial": "la cuida como a una hija con bigotes",
          "tipo": "alianza"
        }
      ],
      "rol": [
        "protagonista"
      ],
      "sabe": [
        "Que conoció a Daniel atrapados en el ascensor de la biblioteca municipal durante una tormenta.",
        "Que Daniel se pierde incluso con el GPS puesto.",
        "Que Mostaza se tumba siempre encima de cualquier mapa que abren."
      ],
      "voz": {
        "muletillas": [],
        "registro": "coloquial",
        "tratamiento": "tu"
      }
    },
    "id": "prot_nerea",
    "nombre": "Nerea"
  },
  {
    "alias": [],
    "descripcion": "Cocina de maravilla y se pierde hasta en su propio barrio; guarda la calma con una broma incluso cuando el plan de Nerea se desmorona.",
    "ficha": {
      "alias": [],
      "arco": "positivo",
      "defecto": "se despista con facilidad y pierde el rumbo",
      "descripcion": "Cocina de maravilla y se pierde hasta en su propio barrio; guarda la calma con una broma incluso cuando el plan de Nerea se desmorona.",
      "deseo": "demostrar que también puede llevar las riendas de una aventura",
      "estado_inicial": "Preparando algo rico para cenar mientras finge que ha memorizado el orden de la ceremonia.",
      "evolucion": null,
      "herida": null,
      "id": "prot_daniel",
      "necesidad": "confiar en su propio instinto aunque se pierda por el camino",
      "nombre": "Daniel",
      "origen": {
        "fuente": "segundo_destinatario",
        "tipo": "real"
      },
      "relaciones": [
        {
          "destino": "prot_nerea",
          "estado_final": "a punto de casarse, confiando por fin en su propio instinto",
          "estado_inicial": "prometido, a tres días de la boda",
          "tipo": "romance"
        },
        {
          "destino": "mostaza",
          "estado_final": "cómplice declarado, le deja elegir el camino alguna vez",
          "estado_inicial": "cómplice de sus despistes",
          "tipo": "alianza"
        }
      ],
      "rol": [
        "protagonista"
      ],
      "sabe": [
        "Que conoció a Nerea en aquel ascensor durante la tormenta.",
        "Que juegan a los Exploradores desde su primera cita.",
        "Que le pidió matrimonio en el mirador de la sierra."
      ],
      "voz": {
        "muletillas": [],
        "registro": "coloquial",
        "tratamiento": "tu"
      }
    },
    "id": "prot_daniel",
    "nombre": "Daniel"
  },
  {
    "alias": [
      "la gata",
      "la exploradora peluda"
    ],
    "descripcion": "Gata naranja de opiniones firmes: si hay un mapa desplegado sobre la mesa, ella es la dueña legítima de ese mapa.",
    "ficha": {
      "alias": [
        "la gata",
        "la exploradora peluda"
      ],
      "arco": "plano",
      "defecto": "se sienta siempre en el peor momento",
      "descripcion": "Gata naranja de opiniones firmes: si hay un mapa desplegado sobre la mesa, ella es la dueña legítima de ese mapa.",
      "deseo": "tumbarse sobre cualquier mapa que se despliegue",
      "estado_inicial": "Dormitando encima de la caja del juego de mesa, como cada tarde.",
      "evolucion": null,
      "herida": null,
      "id": "mostaza",
      "necesidad": "no aplica: acompaña, no cambia",
      "nombre": "Mostaza",
      "origen": {
        "fuente": "h2",
        "tipo": "real"
      },
      "relaciones": [
        {
          "destino": "prot_nerea",
          "estado_final": "sigue siéndolo, con un puesto de honor en la foto de boda",
          "estado_inicial": "su humana favorita para amasar croquetas",
          "tipo": "alianza"
        },
        {
          "destino": "prot_daniel",
          "estado_final": "sigue siéndolo, ahora también de aventuras",
          "estado_inicial": "su cómplice de siestas",
          "tipo": "alianza"
        }
      ],
      "rol": [
        "alivio_comico"
      ],
      "sabe": [],
      "voz": {
        "muletillas": [],
        "registro": "coloquial",
        "tratamiento": "tu"
      }
    },
    "id": "mostaza",
    "nombre": "Mostaza"
  }
]
```

## Localización y reglas del mundo aplicables

```json
[
  {
    "descripcion": "Salón pequeño con una mesa baja donde cada noche despliegan el juego de mesa; sofá con marcas de zarpazos de Mostaza.",
    "estado": null,
    "hito": "detonante",
    "id": "piso",
    "nivel": "micro",
    "nombre": "El piso de Nerea y Daniel",
    "padre": "ciudad"
  },
  {
    "descripcion": "Su ciudad de siempre: calles conocidas, la biblioteca municipal y el piso donde guardan el tablero de los Exploradores.",
    "estado": null,
    "hito": null,
    "id": "ciudad",
    "nivel": "meso",
    "nombre": "La ciudad",
    "padre": "comarca"
  },
  {
    "descripcion": "El territorio que enmarca la ciudad y la sierra donde Nerea y Daniel han construido su vida juntos.",
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
