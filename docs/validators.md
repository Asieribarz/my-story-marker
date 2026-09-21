# validators.md — Verificación del código y del comportamiento de los agentes

> Propósito: catálogo de los métodos de verificación que queremos considerar para comprobar que **nuestro código es correcto y que la salida de los agentes es fiable**. No confundir con los verificadores de `architecture.md` §4, que comprueban el **manuscrito** (continuidad, estilo, hitos). Aquellos son parte del producto; estos son parte de cómo lo construimos y lo operamos.
>
> Este documento es un menú, no un compromiso: enumera métodos con su definición y su clasificación. Qué se adopta y en qué fase es una decisión posterior.

---

## 1. Marco de clasificación (Trust Spec)

Cada método se etiqueta según **cómo** obtiene su garantía. La etiqueta aparece en la columna `Tipo` de las tablas siguientes.

| Código | Nombre | Definición |
|---|---|---|
| **T** | Test · prueba | Se verifica ejecutando el sistema contra entradas concretas. |
| **A** | Análisis | Se verifica por razonamiento estático: tipos, SAST, ejecución simbólica o demostración formal. |
| **I** | Inspección | Se verifica porque una persona —o un modelo crítico— lo lee y lo juzga. |
| **D** | Demostración | Se verifica observando el funcionamiento correcto en un escenario realista (staging, sandbox). |
| **U** | No verificable / riesgo aceptado | Ningún método aplica, o no compensa su coste. Se nombra explícitamente en lugar de quedar como supuesto silencioso. |

**`U` no etiqueta métodos, etiqueta criterios.** Ningún método es "no verificable": lo que puede serlo es una afirmación concreta para la que no exista método que la sostenga, o para la que no compense su coste. Por eso `U` no aparece en las tablas de §2 y §3, y sí debe aparecer allí donde se escriban criterios de aceptación.

La categoría **U** es tan importante como las demás: un riesgo declarado es gestionable; un riesgo no declarado, no.

---

## 2. Verificación a nivel de código

¿Es correcto lo que hemos escrito?

| Método | Definición | Tipo | Referencia |
|---|---|---|---|
| **Comprobación de tipos** | Comprobación automatizada de que los valores se usan de forma coherente con lo que las operaciones esperan de ellos (p. ej. que nunca se pase una cadena donde se requiere un número). | A | [Type system](https://en.wikipedia.org/wiki/Type_system) |
| **Análisis estático / SAST** | Escaneo del código fuente sin ejecutarlo, buscando coincidencias con patrones conocidos como problemáticos: vulnerabilidades de seguridad, *code smells*, antipatrones. | A | [Static program analysis](https://en.wikipedia.org/wiki/Static_program_analysis) |
| **Ejecución simbólica** | Ejecución del código con entradas marcador («simbólicas») para derivar, mediante un resolutor SMT, las condiciones exactas que lo romperían y contraejemplos concretos. | A | [Symbolic execution](https://en.wikipedia.org/wiki/Symbolic_execution) |
| **Verificación formal / demostración de teoremas** | Demostración matemática de que el código satisface una especificación para **todas** las entradas posibles, no solo para las probadas o exploradas. | A | [Formal verification](https://en.wikipedia.org/wiki/Formal_verification) |
| **Pruebas unitarias / de integración** | Comprobación del comportamiento contra entradas de ejemplo concretas y elegidas, con sus salidas esperadas. | T | [Unit testing](https://en.wikipedia.org/wiki/Unit_testing) |
| **Pruebas basadas en propiedades** | Especificación de una propiedad general que debe cumplirse para cualquier entrada, y generación automática de muchas entradas para buscar una violación. | T | [QuickCheck, 2000](https://dl.acm.org/doi/10.1145/351240.351266) |
| **Pruebas de mutación** | Introducción deliberada de pequeños fallos en el código para comprobar si la batería de pruebas existente los detecta realmente. | T | [Mutation testing](https://en.wikipedia.org/wiki/Mutation_testing) |
| **Pruebas de contrato** | Verificación de que la interfaz (forma de la petición y de la respuesta) entre dos servicios se mantiene coherente, con independencia de los detalles internos de cada lado. | T | [Contract Test · Fowler](https://martinfowler.com/bliki/ContractTest.html) |

---

## 3. Verificación a nivel de proceso

¿Se está comportando el agente de forma fiable?

| Método | Definición | Tipo | Referencia |
|---|---|---|---|
| **Observabilidad / trazas en ejecución** | Instrumentación del agente para que su trayectoria real (llamadas a herramientas, tokens, latencia, errores) sea visible y consultable a posteriori. | D | [Observability primer](https://opentelemetry.io/docs/concepts/observability-primer/) |
| **Evals con puntuación automática** | Pruebas estructuradas contra un conjunto de datos con respuesta conocida (*golden dataset*), cumplimiento de tarea, adversariales o en vivo, puntuadas por código. | T | [HELM, 2022](https://arxiv.org/abs/2211.09110) |
| **Evals con modelo juez** | La misma mecánica, pero quien puntúa es otro modelo aplicando una rúbrica. La garantía ya no es ejecución contra salida esperada, sino juicio. | I | [HELM, 2022](https://arxiv.org/abs/2211.09110) |
| **Ejecución en sandbox** | Ejecución del código del agente en un entorno aislado (contenedor, microVM) para que una acción dañina falle de forma segura en lugar de alcanzar producción. | D | [Sandbox](https://en.wikipedia.org/wiki/Sandbox_(computer_security)) |
| **Revisión humana en el bucle** | Una persona aprueba, rechaza o edita las acciones de alta consecuencia del agente, y la decisión se reinyecta como señal de entrenamiento. | I | [Human-in-the-loop](https://en.wikipedia.org/wiki/Human-in-the-loop) |
| **Verificación multiagente** | Crítico/verificador (un segundo modelo revisa al primero), autoconsistencia (voto mayoritario entre ejecuciones repetidas), debate (dos modelos discuten y un juez decide), reflexión (autocrítica y revisión), ensembles (combinación de modelos distintos). | I | [AI Safety via Debate, 2018](https://arxiv.org/abs/1805.00899) |
| **Despliegue progresivo** | Publicar un cambio tras un *feature flag* a un porcentaje pequeño del tráfico, monitorizado antes de la liberación completa. | D | [Feature toggle](https://en.wikipedia.org/wiki/Feature_toggle) |
| **Red teaming / pruebas adversariales** | Sondeo deliberado en busca de fallos bajo un modelo de amenaza adversarial (inyección de prompts, cadenas de mal uso de herramientas, deriva de objetivos, exfiltración de datos), no solo del error ordinario. | T | [OWASP Top 10 LLM](https://owasp.org/www-project-top-10-for-large-language-model-applications/) |
| **Model checking** | Exploración exhaustiva de los estados y transiciones alcanzables por un agente para verificar invariantes (p. ej. «nunca borrar antes de hacer copia de seguridad»). Es el análogo de la ejecución simbólica para flujos multiagente. | A | [Model checking](https://en.wikipedia.org/wiki/Model_checking) |

### 3.1 Controles y vehículos — no son métodos de verificación

Dos piezas que suelen aparecer en estas listas y que conviene mantener fuera, porque no verifican nada y confundirlas rompe el marco.

| Pieza | Qué es | Por qué no es un método | Referencia |
|---|---|---|---|
| **Guardarraíles** | Políticas o filtros que restringen qué acciones o salidas puede producir un agente, **antes** de que actúe. | Un guardarraíl **previene**; no determina si una afirmación es cierta. Hace que algo no pueda pasar, que no es lo mismo que haber comprobado que no pasa. | [AI RMF · NIST](https://www.nist.gov/itl/ai-risk-management-framework) |
| **Integración en CI/CD** | Hacer pasar los cambios generados por agentes por la misma tubería, pruebas y revisión que el código escrito por personas, más etiquetado de procedencia. | CI/CD **ejecuta** métodos, no es uno. Un criterio no se verifica «con CI/CD»: se verifica con una prueba que además corre ahí. | [Continuous integration](https://en.wikipedia.org/wiki/Continuous_integration) |

Ambas siguen siendo deseables. Simplemente no cuentan como la garantía de un criterio.

---

## 4. Resumen

```mermaid
flowchart LR
  V["Verificación"] --> C["Código · ¿es correcto lo escrito?"]
  V --> P["Proceso · ¿es fiable el agente?"]

  C --> CA["Análisis (A) · tipos, SAST, simbólica, formal"]
  C --> CT["Prueba (T) · unitarias, propiedades, mutación, contrato"]

  P --> PA["Análisis (A) · model checking"]
  P --> PT["Prueba (T) · evals con puntuación automática, red teaming"]
  P --> PI["Inspección (I) · humano en el bucle, multiagente, evals con juez"]
  P --> PD["Demostración (D) · trazas, sandbox, despliegue progresivo"]

  V --> U["Riesgo aceptado (U) · etiqueta criterios, no métodos"]
  V -.-> CTL["Controles · guardarraíles, CI/CD · no verifican"]
```
