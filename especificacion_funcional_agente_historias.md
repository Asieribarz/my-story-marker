# Especificación funcional
## Agente generador de historias de aventura — solución de prompt único

| | |
|---|---|
| **Versión** | 1.0 |
| **Fecha** | 15 de septiembre de 2026 |
| **Tipo de solución** | Agente de prompt único (sin orquestador externo) |
| **Entregable del sistema** | Historia de aventura de 20 páginas |

---

## 1. Objetivo y alcance

El sistema genera una historia de aventura completa de 20 páginas a partir de una premisa breve, manteniendo coherencia de personajes, espacios y trama a lo largo de todo el texto, con estructura de introducción, nudo y desenlace.

La solución se implementa como **un único prompt ejecutado en una sola llamada al modelo**. No existe orquestador externo, código auxiliar, sistema de ficheros ni llamadas encadenadas. Todo comportamiento que en una arquitectura convencional correspondería a la capa de código —bucle, persistencia de estado, reintento, condición de parada— debe emerger de instrucciones dentro del propio prompt.

**Fuera de alcance:** ilustración, maquetación, traducción y cualquier interacción con el usuario posterior al lanzamiento.

---

## 2. Entradas y salidas

**Entrada**

| Dato | Obligatorio | Por defecto |
|---|---|---|
| Premisa (1-2 frases) | Sí | — |
| Tono | No | Aventura clásica |
| Público objetivo | No | Lector general |
| Número de páginas | No | 20 |

**Salida**

Un documento continuo con tres bloques visibles:

1. La biblia inicial (reglas del mundo, personajes, espacios, escaleta).
2. El cuerpo de 20 páginas numeradas, cada una precedida de su bloque de contexto.
3. El informe de cierre.

El estado intermedio también es visible en la salida (ver sección 3), por decisión de diseño, no por defecto de implementación.

---

## 3. Modelo de estado

En ausencia de almacenamiento externo, el estado se materializa como **bloques de texto que el modelo reemite en la propia salida antes de cada página**. La transcripción es la memoria: lo que no se reescribe, se pierde. Esto obliga a que cada bloque sea compacto, porque su coste se paga veinte veces.

### 3.1 Fichas de personaje

Se emiten una vez y se actualizan por delta.

| Campo | Tipo | Cuándo se escribe |
|---|---|---|
| id, nombre | texto | Fase A, inmutable |
| rol | protagonista / aliado / antagonista | Fase A, inmutable |
| deseo, miedo | texto breve | Fase A, inmutable |
| aspecto físico, vestuario | texto breve | Fase A, inmutable |
| voz | 2-3 rasgos de habla | Fase A, inmutable |
| arco | estado inicial → estado final | Fase A, inmutable |
| estado actual | texto de una línea | Tras cada página en que interviene |

### 3.2 Fichas de espacio

| Campo | Tipo | Cuándo se escribe |
|---|---|---|
| id, nombre | texto | Fase A, inmutable |
| aspecto, atmósfera | texto breve | Fase A, inmutable |
| función narrativa | texto breve | Fase A, inmutable |

### 3.3 Reglas del mundo

Lista cerrada de 4 a 8 afirmaciones sobre qué es posible y qué está prohibido. Inmutable tras la Fase A.

### 3.4 Escaleta

Veinte entradas con el formato `página → objetivo + gancho de cierre + personajes y espacios implicados`. Escrita en Fase A; solo se modifica mediante el procedimiento de RF-18.

### 3.5 Resumen acumulado

Una línea por página completada. Crece en Fase B.

### 3.6 Hilos abiertos

Lista de promesas narrativas con su página de apertura. Se añade y se tacha durante la Fase B; se audita en Fase C.

---

## 4. Flujo funcional

### Fase A — Preparación (una sola vez)

| Paso | Acción |
|---|---|
| A1 | Expandir la premisa: conflicto central, tema, tono, final tentativo. |
| A2 | Generar reglas del mundo. |
| A3 | Generar fichas de personaje, incluyendo arco. |
| A4 | Generar fichas de espacio. |
| A5 | Generar la escaleta con reparto 4 / 12 / 4 y páginas ancla en 5 (punto de no retorno), 10 (giro central) y 16 (crisis). |
| A6 | Autocomprobar coherencia: todos los personajes aparecen en la escaleta, todos los arcos abren y cierran, el reparto respeta las anclas. Si falla, rehacer A5 antes de continuar. |

### Fase B — Ciclo de escritura (N = 1 … 20)

| Paso | Acción |
|---|---|
| B1 | Emitir el bloque de contexto de la página N: reglas del mundo, fichas solo de los personajes y espacios que la escaleta asigna a N, objetivo de N, resumen acumulado y último párrafo literal de la página N-1. |
| B2 | Escribir la página N. |
| B3 | Autoverificación mecánica. |
| B4 | Autoverificación de consistencia. |
| B5 | Si alguna verificación falla, reescribir la página. Máximo dos reintentos. |
| B6 | Emitir el delta de estado: nueva línea de resumen, cambios en "estado actual" de los personajes implicados, hilos abiertos o cerrados. |
| B7 | Si N < 20, incrementar y volver a B1. Si N = 20, pasar a Fase C. |

### Fase C — Cierre

| Paso | Acción |
|---|---|
| C1 | Auditar hilos abiertos. |
| C2 | Auditar arcos de personaje contra el estado final declarado en Fase A. |
| C3 | Emitir informe de cierre con incidencias y páginas marcadas para revisión. |

---

## 5. Requisitos funcionales

| ID | Requisito |
|---|---|
| RF-01 | El sistema generará las reglas del mundo antes que personajes y espacios. |
| RF-02 | Cada personaje tendrá arco declarado con estado inicial y estado final. |
| RF-03 | Cada espacio tendrá descripción de aspecto y atmósfera antes de su primera aparición en el texto. |
| RF-04 | La escaleta asignará a cada página un objetivo único de una línea y un gancho de cierre. |
| RF-05 | La escaleta declarará, por página, qué personajes y espacios intervienen. |
| RF-06 | El sistema no iniciará la Fase B si A6 detecta incoherencias. |
| RF-07 | Antes de cada página, el sistema emitirá su bloque de contexto de forma visible. |
| RF-08 | El bloque de contexto incluirá únicamente las fichas de los elementos declarados en RF-05. |
| RF-09 | El bloque de contexto no reproducirá el texto íntegro de páginas anteriores. |
| RF-10 | Cada página respetará la extensión declarada con una tolerancia del 20%. |
| RF-11 | Ninguna página introducirá personajes ausentes de las fichas. |
| RF-12 | Ninguna página contradirá aspecto físico, voz ni arco declarados. |
| RF-13 | Ninguna página violará las reglas del mundo. |
| RF-14 | Cada página cumplirá el objetivo asignado y terminará con su gancho. |
| RF-15 | Tras cada página, el sistema emitirá el delta de estado antes de comenzar la siguiente. |
| RF-16 | El sistema mantendrá el registro de hilos abiertos con su página de apertura. |
| RF-17 | El sistema se detendrá al completar la página 20 y no antes. |
| RF-18 | Si durante la Fase B surge una desviación de la escaleta, el sistema actualizará explícitamente las entradas restantes antes de continuar. |
| RF-19 | El informe de cierre listará hilos sin cerrar, arcos incompletos y páginas marcadas. |

---

## 6. Reglas de validación y gestión de errores

**Nivel mecánico (RF-10, RF-11).** Comprobaciones objetivas de extensión y de nómina de personajes. No requieren juicio.

**Nivel de consistencia (RF-12 a RF-14).** Contraste de la página recién escrita contra fichas, reglas y objetivo. La verificación se formula como lista de comprobación explícita sobre la página, no como impresión global; un juicio difuso sobre texto propio tiende al autoaprobado.

**Rama de fallo.** Reescritura de la misma página con el mismo bloque de contexto, no del contexto completo. Tras dos reintentos fallidos, la página se acepta, se marca con `[REVISIÓN: motivo]` y el ciclo continúa. Detener la generación por un fallo local produce un entregable inservible; marcarlo produce uno corregible.

---

## 7. Estrategia de gestión de contexto

Lo que el diseño acota no es la ocupación de la ventana, sino **la cantidad de información que el modelo debe consultar para escribir cada página**. Ese conjunto es de tamaño aproximadamente constante: reglas del mundo, dos o tres fichas, un objetivo, un resumen que crece una línea por página y un párrafo literal de enlace. Escribir la página 19 exige mirar lo mismo que escribir la página 3.

El mecanismo que lo consigue es doble:

- **Carga selectiva (RF-08):** impide que el coste crezca con el número de personajes del reparto.
- **Compresión (RF-15):** sustituye el texto ya escrito por su resumen de una línea.

La reemisión visible del bloque de contexto (RF-07) actúa además como ancla de atención: el material relevante está siempre en la posición más reciente, no sepultado veinte páginas atrás.

Bajo prompt único, la ventana **sí** crece de forma lineal en tokens, porque toda la historia generada permanece en el contexto. Esa es una limitación estructural, no un fallo del diseño, y se recoge en la sección 9.

---

## 8. Criterios de aceptación

Una ejecución se acepta si cumple todo lo siguiente:

- Produce 20 páginas numeradas con la estructura 4 / 12 / 4.
- Ningún personaje cambia de nombre, aspecto o voz sin justificación narrativa.
- Cada espacio se describe en su primera aparición.
- El informe de cierre no reporta hilos abiertos ni arcos incompletos.
- Las páginas marcadas para revisión no superan el 10% del total.
- La lectura continuada de las páginas 1 a 20 no presenta saltos causales.

---

## 9. Limitaciones y riesgos

**Crecimiento real de la ventana.** El contexto acumula toda la salida. A partir de cierta extensión, la calidad decae aunque el diseño sea correcto. Mitigación dentro de la restricción: mantener los deltas de estado tan breves como sea posible. Fuera de ella: partir en varias llamadas.

**Autoevaluación complaciente.** El mismo modelo que escribe la página la valida, y tiende a aprobarla. Mitigación: formular la validación como comprobaciones enumeradas con respuesta sí/no, nunca como valoración abierta.

**Ausencia de bucle real.** El ciclo es una repetición instruida, no controlada. El riesgo característico es la deriva: páginas que se acortan o que dejan de emitir el bloque de estado. Mitigación: la emisión visible del contexto en cada iteración hace la deriva detectable a simple vista.

**Coste del reintento.** Reescribir dentro de la misma ejecución consume contexto sin eliminar el intento fallido, que sigue presente e influye en lo que viene después. Es la razón del límite de dos reintentos.

---

## Anexo — Diagrama de flujo

```
                           INICIO
                             │
                             ▼
              ┌──────────────────────────────┐
              │ GENERACIÓN DE CARACTERÍSTICAS│
              │ reglas → personajes (+ arco) │
              │ → espacios                   │
              └──────────────┬───────────────┘
                             ▼
              ┌──────────────────────────────┐
              │ SEPARACIÓN DE PARTES         │
              │ introducción / nudo /        │
              │ desenlace · escaleta 20 pág. │
              └──────────────┬───────────────┘
                             ▼
   ┌────────────────────────────────────────────┐
   │  PREPARACIÓN DE CONTEXTO MÍNIMO            │◀───┐
   │  características relevantes + resumen      │    │
   │  1→N-1 + objetivo de la página N           │    │
   └──────────────────┬─────────────────────────┘    │
                      ▼                              │
        ┌──────────────────────────┐                 │
        │   ESCRIBIR PÁGINA N      │◀────┐           │
        └──────────────┬───────────┘     │ ERROR     │
                       ▼                 │           │
        ┌──────────────────────────┐     │           │
        │  VALIDACIÓN DE LA PÁGINA │─────┘           │
        └──────────────┬───────────┘                 │
                       │ OK                          │
                       ▼                             │
        ┌──────────────────────────┐                 │
        │ GUARDAR PÁGINA +         │                 │
        │ ACTUALIZAR ESTADO        │                 │
        └──────────────┬───────────┘                 │
                       ▼                             │
                  ◇ ¿N = 20? ───── NO ───────────────┘
                       │                        (N = N+1)
                       │ SÍ
                       ▼
              ┌──────────────────────────────┐
              │ VALIDACIÓN FINAL             │
              │ hilos · arcos · informe      │
              └──────────────┬───────────────┘
                             ▼
                            FIN
```
