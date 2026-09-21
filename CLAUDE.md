@AGENTS.md

## Claude-specific notes

- Trabaja siempre sobre la rama `project-v2` y trátala como el único contexto válido: no consultes ni copies nada de `main`.
- Lee los tres documentos de `docs/` antes de planificar. Son largos pero autocontenidos; no infieras el dominio a partir del nombre del repo.
- Los diagramas de `docs/` son Mermaid. Al editarlos, mantén el estilo existente (`flowchart LR`, ids cortos tipo `E1`, `T2a`) y comprueba que el diagrama sigue siendo válido.
- No crees código de aplicación sin que exista una decisión explícita en `docs/architecture.md` que lo respalde; si falta, propón primero el cambio de documento.
- **Tope de 100.000 tokens de ventana de contexto por agente.** Vale para cada subagente de la novela: lo que le pases —ficha, contexto recuperado, guía de estilo, capítulos anteriores— tiene que caber ahí. Es el límite que obliga a que el Recuperador de contexto seleccione en vez de volcar (`docs/architecture.md` §5).
