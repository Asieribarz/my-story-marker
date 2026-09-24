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
      "texto": "Objetivo: Maribel quiere ordenar la casa del puerto ahora que tiene todo el tiempo del mundo. Conflicto: al llegar a la vitrina del salón se topa con el sextante de su padre y no puede evitar sostenerlo contra la luz de la ventana. Desastre: descubre una línea grabada en la alidada que nunca había notado, una marca que no sabe leer y que la deja más inquieta que curiosa.",
      "tipo": "escena"
    },
    {
      "texto": "Reacción: se sienta con el sextante en el regazo y deja que vuelvan los recuerdos de Julián enseñándole a leer el cielo. Dilema: guardarlo de nuevo en la vitrina y seguir con su jubilación tranquila, o averiguar qué escondió su padre. Decisión: se calza las botas y baja hacia el muelle, a ver el barco con sus propios ojos por primera vez en años.",
      "tipo": "secuela"
    }
  ],
  "hechos": [
    "h1",
    "h3",
    "h4"
  ],
  "hitos": [
    "detonante"
  ],
  "localizacion": "casa_puerto",
  "mencionados": [
    "julian"
  ],
  "numero": 1,
  "objetivo": "Maribel, recién jubilada, abre la vitrina del salón y el hallazgo del sextante de Julián la empuja a bajar al muelle para mirar de frente el Estrella del Alba, amarrado desde hace seis años.",
  "palabras_objetivo": 1150,
  "plantar": [
    {
      "clave": "sextante_marca",
      "descripcion": "La línea grabada en la alidada del sextante, que Maribel no sabe interpretar y que su padre nunca explicó."
    }
  ],
  "pov": "maribel",
  "presentes": [
    "maribel"
  ],
  "tension": 2,
  "traspasos": []
}
```

### Hechos del comprador en este capítulo

- [h1] ser_querido: Su padre, Julián, patrón del pesquero Estrella del Alba, que le enseñó todo lo que sabe del mar
- [h3] evento: Julián murió en su casa del puerto; desde entonces el Estrella del Alba sigue amarrado
- [h4] objeto: El sextante de su padre, que ella guarda en la vitrina del salón

### Vetos: palabras

Ninguno.

### Vetos: temas

Ninguno.

### Lista negra

- de repente
- sin embargo
- no pudo evitar
- un escalofrío recorrió

## Informe del intento anterior

Ninguno.

## Guía de estilo

```json
{
  "dialogo": {
    "convencion": "raya",
    "proporcion": 35,
    "tratamiento": null
  },
  "ejemplos": [
    "El sextante pesaba más de lo que recordaba. Maribel lo sostuvo contra la luz de la ventana y buscó, otra vez, esa línea que su padre había grabado sin decirle nunca por qué.",
    "—El mar no se pelea, se lee —dijo Tomás, repitiendo la frase como quien repite un rezo que no es suyo pero que ha aprendido a querer.",
    "El Estrella del Alba crujió al soltar la última amarra, un sonido viejo que Maribel sintió en el pecho antes que en las manos."
  ],
  "idioma": "es-ES",
  "lexico": [
    "nautica",
    "navegacion",
    "meteorologia"
  ],
  "metricas": {
    "descriptivo": 60,
    "frase_media_palabras": 14.0,
    "legibilidad_min": 40.0,
    "proporcion_dialogo": 35
  },
  "narrador": "tercera_limitada",
  "onomastica": "Nombres y motes de pueblo pesquero español, sencillos y de una o dos sílabas de uso común (Tomás, Julián, Estrella del Alba), sin inventar términos exóticos ni fantasiosos.",
  "prohibidas": [],
  "registro": "estandar",
  "tiempo": "preterito",
  "voz": "cercana, sensorial y pausada, con la calma de quien ha aprendido a mirar el mar despacio"
}
```

## Presagios pendientes e inventario vivo

### Presagios pendientes

Ninguno.

### Inventario

- estrella_alba (El Estrella del Alba): maribel, desde el capítulo 0
- sextante (El sextante de Julián): maribel, desde el capítulo 0

### Estado de los presentes

- maribel: Recién jubilada, vive sola en la casa del puerto donde murió su padre; el Estrella del Alba lleva seis años amarrado y el sextante de Julián duerme en la vitrina del salón.; sabe: Que su padre, Julián, patrón del Estrella del Alba, le enseñó todo lo que sabe del mar; Que Julián murió en la casa del puerto en 2020 y desde entonces el barco no ha vuelto a salir; Que el mar no se pelea, se lee

## Fichas de los personajes presentes

```json
[
  {
    "alias": [],
    "descripcion": "Pescadora jubilada de sesenta y cinco años, madrugadora de toda la vida, capaz de leer el cielo antes de que rompa el día. Ha pasado seis años sin soltar amarras del barco de su padre.",
    "ficha": {
      "alias": [],
      "arco": "positivo",
      "defecto": "tozuda",
      "descripcion": "Pescadora jubilada de sesenta y cinco años, madrugadora de toda la vida, capaz de leer el cielo antes de que rompa el día. Ha pasado seis años sin soltar amarras del barco de su padre.",
      "deseo": "volver a sacar el Estrella del Alba a navegar",
      "estado_inicial": "Recién jubilada, vive sola en la casa del puerto donde murió su padre; el Estrella del Alba lleva seis años amarrado y el sextante de Julián duerme en la vitrina del salón.",
      "evolucion": null,
      "herida": null,
      "id": "maribel",
      "necesidad": "aceptar la pérdida de su padre y confiar en lo que él le enseñó",
      "nombre": "Maribel",
      "origen": {
        "fuente": "destinatario",
        "tipo": "real"
      },
      "relaciones": [
        {
          "destino": "julian",
          "estado_final": "hace las paces con su enseñanza y confía en lo aprendido",
          "estado_inicial": "lo recuerda como maestro ausente, una herida que evita mirar",
          "tipo": "mentoria"
        },
        {
          "destino": "companero_puerto",
          "estado_final": "aliado que la ayuda a preparar y acompañar la travesía",
          "estado_inicial": "vecino de muelle con el que apenas cruza palabra desde el entierro",
          "tipo": "alianza"
        }
      ],
      "rol": [
        "protagonista"
      ],
      "sabe": [
        "Que su padre, Julián, patrón del Estrella del Alba, le enseñó todo lo que sabe del mar",
        "Que Julián murió en la casa del puerto en 2020 y desde entonces el barco no ha vuelto a salir",
        "Que el mar no se pelea, se lee"
      ],
      "voz": {
        "muletillas": [],
        "registro": "estandar",
        "tratamiento": "tu"
      }
    },
    "id": "maribel",
    "nombre": "Maribel"
  }
]
```

## Localización y reglas del mundo aplicables

```json
[
  {
    "descripcion": "La casa familiar frente al agua donde murió Julián y donde su sextante espera en la vitrina del salón.",
    "estado": null,
    "hito": "detonante",
    "id": "casa_puerto",
    "nivel": "micro",
    "nombre": "La casa del puerto",
    "padre": "puerto"
  },
  {
    "descripcion": "Pueblo de pescadores donde Maribel creció, con lonja, casas bajas y el olor constante a sal y a diésel.",
    "estado": null,
    "hito": null,
    "id": "puerto",
    "nivel": "meso",
    "nombre": "El puerto pesquero",
    "padre": "costa"
  },
  {
    "descripcion": "Franja costera de pueblos pesqueros, acantilados y cielos cambiantes donde Maribel ha vivido toda su vida.",
    "estado": null,
    "hito": null,
    "id": "costa",
    "nivel": "macro",
    "nombre": "La costa",
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
