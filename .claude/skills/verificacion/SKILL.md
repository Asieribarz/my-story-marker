---
name: verificacion
description: Cómo elegir un método de verificación para una afirmación concreta, con el marco T/A/I/D/U y enlaces a la referencia canónica de cada método. Úsala al definir criterios de aceptación, al decidir qué pruebas escribir, o cuando haya que justificar por qué algo no se verifica.
---

# Verificación — cómo elegir el método

El **catálogo** de métodos, con la definición de cada uno, está en `docs/validators.md`. Esta skill no lo repite: es el procedimiento para elegir, más los enlaces de referencia que el catálogo no lleva.

## Primero: qué estás verificando

Son tres cosas distintas y se confunden constantemente.

| Qué | Dónde se define | Ejemplo |
|---|---|---|
| **El código que escribimos** | `docs/validators.md` §2 | ¿El endpoint de intake rechaza un brief sin género? |
| **El comportamiento del agente** | `docs/validators.md` §3 | ¿El Escritor respeta la ficha de capítulo de forma consistente? |
| **El manuscrito** | `docs/architecture.md` §4 | ¿El capítulo 12 contradice la biblia? |

Lo tercero es **parte del producto** y tiene sus propios verificadores con su política de reintentos. Lo primero y lo segundo son parte de cómo construimos. Un criterio de aceptación que mezcla los tres no se puede comprobar.

## El marco T/A/I/D/U

Cada método obtiene su garantía de una forma distinta. La etiqueta dice **cuál**:

- **T · Test** — ejecutando el sistema contra entradas concretas.
- **A · Análisis** — razonando sin ejecutar: tipos, SAST, ejecución simbólica, demostración formal.
- **I · Inspección** — alguien lo lee y lo juzga: una persona o un modelo crítico.
- **D · Demostración** — observando funcionamiento correcto en un escenario realista.
- **U · No verificable** — ningún método aplica o no compensa. **Se declara.**

`U` no es una derrota: es la diferencia entre un riesgo gestionado y un supuesto silencioso. Un criterio marcado `U` y escrito es información; el mismo riesgo sin marcar es una sorpresa futura.

## El procedimiento

1. **Escribe la afirmación en forma comprobable.** "El intake funciona" no lo es. "Un brief sin género recibe 422 con el campo que falta" sí.
2. **Decide de cuál de las tres columnas de arriba habla.**
3. **Elige la garantía más barata que la sostenga.** El orden habitual de coste creciente es A → T → D → I. Si los tipos ya lo garantizan, no escribas una prueba; si una prueba lo cubre, no montes un entorno de demostración; y no gastes revisión humana en lo que una prueba decide sola.
4. **Si nada la sostiene, márcala `U` y di por qué.** Eso cierra el asunto de forma explícita.

Dos criterios que se resisten a esto merecen atención especial. La **salida de un modelo** rara vez admite `T` con salida esperada exacta: lo que aplica son evals con dataset y método de puntuación, o un juez, que es `I`. Y lo que depende de **coste o latencia** suele ser `D`, no `T`: se observa en ejecución, no se afirma en una prueba.

Cuidado también con dar por verificado lo que solo está **prevenido** o solo está **ejecutado en CI**. Ver `docs/validators.md` §3.1.

## Referencias canónicas

Enlaces a la explicación del método, no a producto:

| Método | Referencia |
|---|---|
| Comprobación de tipos | [Type system — Wikipedia](https://en.wikipedia.org/wiki/Type_system) |
| Análisis estático / SAST | [Static program analysis — Wikipedia](https://en.wikipedia.org/wiki/Static_program_analysis) |
| Ejecución simbólica | [Symbolic execution — Wikipedia](https://en.wikipedia.org/wiki/Symbolic_execution) |
| Verificación formal | [Formal verification — Wikipedia](https://en.wikipedia.org/wiki/Formal_verification) |
| Pruebas unitarias / integración | [Unit testing — Wikipedia](https://en.wikipedia.org/wiki/Unit_testing) |
| Pruebas basadas en propiedades | [QuickCheck — Claessen & Hughes, 2000](https://dl.acm.org/doi/10.1145/351240.351266) |
| Pruebas de mutación | [Mutation testing — Wikipedia](https://en.wikipedia.org/wiki/Mutation_testing) |
| Pruebas de contrato | [Contract Test — Martin Fowler](https://martinfowler.com/bliki/ContractTest.html) |
| Observabilidad / trazas | [Observability primer — OpenTelemetry](https://opentelemetry.io/docs/concepts/observability-primer/) |
| Evals (ambas variantes) | [HELM — Liang et al., 2022](https://arxiv.org/abs/2211.09110) |
| Ejecución en sandbox | [Sandbox — Wikipedia](https://en.wikipedia.org/wiki/Sandbox_(computer_security)) |
| Revisión humana en el bucle | [Human-in-the-loop — Wikipedia](https://en.wikipedia.org/wiki/Human-in-the-loop) |
| Verificación multiagente | [AI Safety via Debate — Irving et al., 2018](https://arxiv.org/abs/1805.00899) |
| Despliegue progresivo | [Feature toggle — Wikipedia](https://en.wikipedia.org/wiki/Feature_toggle) |
| Red teaming | [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/) |
| Model checking | [Model checking — Wikipedia](https://en.wikipedia.org/wiki/Model_checking) |
| Marco T/A/I/D/U | [Verification and validation — Wikipedia](https://en.wikipedia.org/wiki/Verification_and_validation) |

Los **guardarraíles** ([NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework)) y la **integración en CI/CD** ([Continuous integration](https://en.wikipedia.org/wiki/Continuous_integration)) no están en esta tabla a propósito: no son métodos de verificación. Un guardarraíl previene en vez de comprobar, y CI/CD ejecuta métodos sin ser uno. Ver `docs/validators.md` §3.1.

Las pruebas basadas en propiedades y las evals no tienen una referencia fundacional única como sí la tiene la verificación formal; QuickCheck y HELM son el trabajo que formalizó cada una, no la única elección posible.

## Lo que esta skill no decide

`docs/validators.md` es un **menú, no un compromiso**: qué métodos se adoptan y en qué fase sigue sin decidirse. Esta skill ayuda a elegir para un criterio concreto; no autoriza a introducir una herramienta de verificación en el proyecto. Eso es una dependencia, y va por `docs/architecture.md` §7 como cualquier otra.
