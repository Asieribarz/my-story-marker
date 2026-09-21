@AGENTS.md

## Claude-specific notes

- Trabaja siempre sobre la rama `project-v2` y trátala como el único contexto válido: no consultes ni copies nada de `main`.
- Lee los tres documentos de `docs/` antes de planificar. Son largos pero autocontenidos; no infieras el dominio a partir del nombre del repo.
- Los diagramas de `docs/` son Mermaid. Al editarlos, mantén el estilo existente (`flowchart LR`, ids cortos tipo `E1`, `T2a`) y comprueba que el diagrama sigue siendo válido.
- No crees código de aplicación sin que exista una decisión explícita en `docs/architecture.md` que lo respalde; si falta, propón primero el cambio de documento.
