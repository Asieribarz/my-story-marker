@AGENTS.md

## Claude-specific notes

- Trabaja siempre sobre la rama `project-v2` y trátala como el único contexto válido: no consultes ni copies nada de `main`.
- Lee los tres documentos de `docs/` antes de planificar. Son largos pero autocontenidos; no infieras el dominio a partir del nombre del repo.
- Los diagramas de `docs/` son Mermaid. Al editarlos, mantén el estilo existente (`flowchart LR`, ids cortos tipo `E1`, `T2a`) y comprueba que el diagrama sigue siendo válido.
- No crees código de aplicación sin que exista una decisión explícita en `docs/architecture.md` que lo respalde; si falta, propón primero el cambio de documento.

## Stack

Lo único decidido: **backend en Python con FastAPI** y **frontend en React con Vite**.

Todo lo demás (orquestación de agentes, base de datos, índice vectorial, cola de trabajos, almacén de objetos, observabilidad, exportación, despliegue) está sin decidir — ver `docs/architecture.md` §7. No introduzcas ninguna de esas dependencias por iniciativa propia: propón la decisión, y si se acepta, añádela a esa tabla en el mismo cambio.

## Trabajo

- Respeta el presupuesto: se trabaja con suscripción, no con crédito de API medido. Evita lanzar subagentes o workflows en paralelo salvo petición explícita.
- Explica el razonamiento en prosa y da una recomendación concreta, en lugar de presentar un menú de opciones.
- Idioma de interacción: español.
