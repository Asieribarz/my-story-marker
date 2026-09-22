@AGENTS.md

## Claude-specific notes

- Trabaja siempre sobre la rama `project-v2` y trátala como el único contexto válido: no consultes ni copies nada de `main`.
- Lee los tres documentos de `docs/` antes de planificar. Son largos pero autocontenidos; no infieras el dominio a partir del nombre del repo.
- Los diagramas de `docs/` son Mermaid. Al editarlos, mantén el estilo existente (`flowchart LR`, ids cortos tipo `E1`, `T2a`) y comprueba que el diagrama sigue siendo válido.
- No crees código de aplicación sin que exista una decisión explícita en `docs/architecture.md` que lo respalde; si falta, propón primero el cambio de documento.
- **Tope de 100.000 tokens de entrada por agente.** Vale para cada subagente de la novela: lo que le pases —ficha, contexto recuperado, guía de estilo, capítulos anteriores— tiene que caber ahí. Acota la entrada, no la salida: no hay presupuesto de salida. Los bloques y el orden de recorte están en `docs/architecture.md` §6.3.
- **Ese tope no es el límite del modelo, es la decisión de no usarlo entero.** Los modelos actuales tienen ventanas de un orden de magnitud mayor. Los 100.000 son una disciplina deliberada: un Escritor con la biblia entera volcada no escribe mejor, escribe peor y más caro, y el Recuperador de contexto existe precisamente porque seleccionar vence a volcar. Si el tope fuese la ventana del modelo, el Recuperador sobraría y el orden de recorte de §6.3 no se ejecutaría nunca. Subirlo es una decisión que se mide contra la calidad del capítulo, no un hueco que se rellena.
