# iteraciones.md — Registro de iteraciones

> Propósito: dejar escrito, **en el momento en que ocurre**, qué se intentó, qué falló o qué se descubrió y qué se cambió por ello. Al final no se puede reconstruir ([plan-entrega.md](../specs/plan-entrega.md) §3, «Cierre de cada hito»). Es la fuente del apartado de iteraciones de la documentación de entrega (H8).
>
> Los ataques deliberados no van aquí, sino en [red-team.md](red-team.md). Si un ataque obliga a cambiar algo, el cambio tiene entrada en los dos, y cada una cita a la otra.

---

## Formato

Una entrada por **episodio**: una ejecución, un grilling, una auditoría, una prueba en esta máquina. Si un episodio destapa varias cosas, van dentro con letras: (a), (b).

```markdown
### I-NN · AAAA-MM-DD · Hn · Lo descubierto en una línea, no la tarea

- **Qué se intentó:** lo que se estaba haciendo cuando apareció.
- **Qué falló o qué se descubrió:** el hecho, con la cifra o el síntoma que lo delató.
- **Qué se cambió y dónde:** la corrección, con los ficheros, las secciones y las decisiones (`B-n`, `TC-n`, `RF-n`, `V-n`) donde vive.
```

| Campo | Regla |
|---|---|
| `I-NN` | Correlativo y sin huecos. No se reutiliza |
| Fecha | La del día en que ocurrió, no la del commit que lo recoge |
| Hito | El de [plan-entrega.md](../specs/plan-entrega.md) §3 al que pertenece el trabajo afectado (`H0`…`H8`), o varios separados por comas. Si se descubrió trabajando en otro, lo cuenta «Qué se intentó» |
| Qué se cambió y dónde | Lo que aún no está aplicado en un sitio que se nombra lleva la marca **pendiente**. Quien lo aplica quita la marca |

- Se añade al final. Una entrada no se reescribe, salvo para quitar una marca **pendiente**: si algo posterior la deshace, entra una nueva que la cita (I-03 con I-01 e I-02).
- Si lo descubierto se acepta como riesgo y no se cambia nada, «Qué se cambió» lo dice y cita dónde queda aceptado. Un «nada» declarado vale; un campo vacío, no.
- Cada contraejemplo de TLC entra aquí junto con el cambio en el código (plan-entrega, H1).
- Ningún dato de una persona real. Si hace falta un ejemplo, sale de los briefs ficticios.
- Las entradas anteriores a este registro se reconstruyen desde git y lo dicen, con el commit.

---

## Entradas

### I-01 · 2026-09-23 · H0, H1 · Tres supuestos de la pila que no se cumplían en esta máquina

*Reconstruida desde el commit `8251788`.*

- **Qué se intentó:** comprobar en este Windows, antes de escribir el paso 0 de [plan-backend-v1.md](../specs/plan-backend-v1.md), que la pila decidida funciona.
- **Qué falló o qué se descubrió:**
  - (a) `mutmut` 3 no funciona en Windows sin WSL.
  - (b) Git tiene `core.autocrlf=true`, y convertir los saltos de línea del BPE de `o200k_base` rompe su SHA-256. `tiktoken` borra entonces la copia y la vuelve a descargar: se pierden a la vez el determinismo del estimador y el arranque sin red.
  - (c) El FastMCP del SDK oficial `mcp` ya no existe en su versión 2, y Starlette no arranca el `lifespan` de las subaplicaciones montadas.
- **Qué se cambió y dónde:**
  - (a) `cosmic-ray` sustituye a `mutmut` para V-15: [architecture.md](architecture.md) §7, plan-backend-v1.md paso 0 y AGENTS.md. La retira I-03.
  - (b) El BPE se versiona en `backend/capitulo/bpe/`, marcado como binario en `.gitattributes`, con una prueba de su SHA-256 (RF-52c): architecture.md §6.3 y plan-backend-v1.md paso 0.
  - (c) Se usa el paquete `fastmcp`, y el `lifespan` de cada superficie montada se combina con el de la aplicación: architecture.md §7 y plan-backend-v1.md paso 5.

### I-02 · 2026-09-23 · H1 · `cosmic-ray` daba por INCOMPETENT mutantes que estaban eliminados

- **Qué se intentó:** cerrar el paso 2 pasando la mutación (V-15) sobre `backend/contexto/validacion.py`, como pide H1.
- **Qué falló o qué se descubrió:**
  - (a) 190 de los 498 mutantes salían INCOMPETENT cuando en realidad estaban eliminados. En Windows, pytest escribe su salida en cp1252, y `cosmic-ray` la decodifica como UTF-8 en la rama de mutante eliminado: basta un «é» o un «→» en el informe de pytest para que la decodificación reviente.
  - (b) Ocho mutantes sobrevivían en la guarda que impide salir de `contexto` (`puede_salir_de_contexto`, RF-22, V-20), porque le sobraba una comprobación: además de `valido`, exigía que no hubiera hallazgos bloqueantes. `valido` ya exige cero hallazgos, y el validador solo emite hallazgos bloqueantes.
- **Qué se cambió y dónde:**
  - (a) El comando de pruebas de `cosmic-ray.toml` lanza pytest con `python -X utf8`. El porqué está en la cabecera del fichero.
  - (b) La guarda queda en `informe.valido` (`backend/contexto/validacion.py`), y `test_todo_hallazgo_del_validador_es_bloqueante` (`backend/contexto/tests/test_validacion.py`) fija la premisa de la que depende. Los casos de límite que matan al resto de supervivientes, y los supervivientes equivalentes con su razón, están en `backend/contexto/tests/test_validacion_limites.py`.

### I-03 · 2026-09-23 · H1, H3 · Se retira `cosmic-ray`: V-15 pasa a ser cobertura por regla

- **Qué se intentó:** mantener la mutación como V-15 sobre el validador de ontología (H1) y sobre los verificadores (H3).
- **Qué falló o qué se descubrió:** no compensa el tiempo que queda hasta la entrega. `cosmic-ray` ejecuta la batería entera por cada mutante (498 solo en el validador), y en H3 se sumarían los verificadores.
- **Qué se cambió y dónde:** V-15 pasa a ser una comprobación de **cobertura por regla**: cada regla tiene una prueba que la dispara y otra de control que no. Deshace la elección de I-01 (a) y deja sin uso el arreglo de I-02 (a). La guarda simplificada de I-02 (b) y las pruebas de límite se quedan. Se aplica en:
  - [validators.md](validators.md), las dos filas de V-15 · **hecho** (2026-09-24)
  - [spec1.md](../specs/spec1.md), V-15 en §9 y D-7 · **hecho** (2026-09-24)
  - architecture.md §7 y AGENTS.md, en la pila y en las comprobaciones del backend · **pendiente**
  - plan-backend-v1.md, pasos 2 y 7, y plan-entrega.md, H1 y H3 · **pendiente**
  - `pyproject.toml` y `cosmic-ray.toml` · **pendiente**. `pyproject.toml` y §7 cambian juntos, o falla V-10.

### I-04 · 2026-09-23 · H1 · Dos huecos del grafo que salieron en el grilling del paso 3

- **Qué se intentó:** cerrar con grilling el paso 3 de plan-backend-v1.md (grafo, siguiente orden y bloqueo) antes de escribirlo. El código cita esas preguntas como Q4 a Q8.
- **Qué falló o qué se descubrió:**
  - (a) «Reintentar» desde `detenida` volvía siempre a `capitulos` (architecture.md §3.1, RF-64b). Pero a `detenida` también se llega agotando el tope de intentos de una fase que no es el bucle (RF-07a): un proyecto detenido en `planificacion` habría saltado a `capitulos` sin escaleta.
  - (b) No estaba escrito qué gasta un intento de capítulo. Por ejemplo: ¿una salida mal formada del Editor o del Bibliotecario cuenta como intento del Escritor y manda reescribir el capítulo?
- **Qué se cambió y dónde:**
  - (a) Q6. El proyecto guarda de qué fase viene (`proyecto.detenida_desde`, en `backend/shared/esquema.sql`), y «reintentar» vuelve a ella (`DESTINO_DE_REINTENTAR`, en `backend/proyecto/transiciones.py`). Desde `verificacion_manuscrito` sigue volviendo a `capitulos`, porque se aplica RF-64b. Queda por recoger en architecture.md §3.1, en la fila de `detenida`, y en spec1.md RF-64b, que aún dicen «se vuelve a `capitulos`» · **hecho** (2026-09-24).
  - (b) Q4 y Q5. Dos tipos de fallo (`TipoDesenlace`, en `backend/proyecto/maquina.py`):
    - **de contenido** —deterministas altos o bloqueantes, guardarraíl, juez de capítulo que rechaza, o salida inválida del Escritor—: gasta `capitulo.intentos` y vuelve al Escritor;
    - **de formato** —salida inválida de un agente posterior al Escritor—: repite solo ese agente sobre el mismo borrador y gasta el contador nuevo `proyecto.intentos_paso`.

    Queda por recoger en architecture.md §3.2 · **hecho** (2026-09-24).

### I-05 · 2026-09-23 · H1 · `fastapi[standard]` habría escondido dependencias a V-10

- **Qué se intentó:** añadir FastAPI para el paso 3.
- **Qué falló o qué se descubrió:** el extra `[standard]` instala `uvicorn`, `httpx` y otros paquetes sin nombrarlos en `pyproject.toml`. V-10 compara las dependencias declaradas con architecture.md §7, así que no los habría visto, y la pila habría crecido sin pasar por la tabla.
- **Qué se cambió y dónde:** `fastapi` sin extras, con `uvicorn` como servidor y `httpx`, solo en desarrollo, para el `TestClient`, declarados en `pyproject.toml`. Los nombran architecture.md §7 (filas «Backend» y «Pruebas y análisis estático») y la pila de AGENTS.md, con el porqué.

### I-06 · 2026-09-23 · H4 · Dos contradicciones en los gates de manuscrito, al preparar los tramos B y C

- **Qué se intentó:** preparar los tramos B (pasos 4 a 8) y C (pasos 8a a 10) de plan-backend-v1.md antes de construirlos.
- **Qué falló o qué se descubrió:**
  - (a) El umbral del juez de manuscrito, «≥3 en todos y media ≥3,5» (architecture.md §4.1, RF-113), no se puede probar en su frontera. Con cinco notas enteras, la media no puede valer exactamente 3,5 (la suma tendría que ser 17,5), así que el caso «media a 3,5» de V-32 no se puede construir.
  - (b) El Revisor no puede arreglar un fallo de cobertura. La cobertura se mide sobre `hecho_uso`, y ese registro solo lo escribe el Bibliotecario: un capítulo corregido por el Revisor seguiría sin contar sus hechos.
- **Qué se cambió y dónde:** en [decisiones-backend.md](../specs/decisiones-backend.md). `docs/` lo recoge cuando el código lo aplique (AGENTS.md, regla 3).
  - (a) TC-5: **suma ≥ 18 y ningún criterio por debajo de 3**. En enteros equivale a «media ≥ 3,5», pero se puede probar en la frontera: V-32 se prueba con sumas 17 y 18.
  - (b) §3, punto 7. En `revision`, cada capítulo pasa por Revisor, deterministas y Bibliotecario sobre la versión nueva. Los capítulos que hay que corregir salen de `ficha_capitulo_hecho` (cobertura), de `evento.capitulo` (Lean) y de un campo `capitulos` en la salida del juez. Cambia la tabla del paso 3 y la spec TLA+.

### I-07 · 2026-09-24 · H2 a H6 · Bloques 2 y 3 del backend: lo que cambió al construirlos

- **Qué se intentó:** construir los pasos 4 a 10 de plan-backend-v1.md (planificación, Recuperador, verificadores, escritura MCP, gates, publicación, cambio del lector y worker) con las decisiones de [decisiones-backend.md](../specs/decisiones-backend.md).
- **Qué falló o qué se descubrió:**
  - (a) La extensión nativa de `tiktoken` no carga en esta máquina: la bloquea una directiva de control de aplicaciones de Windows (dif-local-vm L-2).
  - (b) No hay `elan`/`lake`, Java ni el CLI `claude` en el PATH (L-3), así que Lean, TLC y el `claude -p` real no se pueden ejecutar aquí.
  - (c) El contrato Lean exige una franja en cada evento de la historia, y la ficha y el Bibliotecario solo manejan días.
  - (d) La revisión de diseño de la sesión formal destapó que los gates por ciclo reutilizaban cobertura y Lean de una versión anterior, y que un ejecutor caído podía duplicar la biblia.
- **Qué se cambió y dónde:**
  - (a) M-10: respaldo del estimador en Python puro sobre el mismo `o200k_base` y con el mismo factor, en `backend/capitulo/estimador.py`; la decisión sigue siendo `tiktoken` ([architecture.md](architecture.md) §6.3 y §7).
  - (b) Las pruebas que ejecutan Lean o Chromium llevan `skipif`, y el worker se prueba con un `claude` falso (TC-10). Lean, TLC y la prueba manual de `claude -p` quedan pendientes.
  - (c) M-14: un evento sin franja se emite como `manana` hasta que `formal/lean` acepte la franja opcional; puede dar falsos positivos dentro del mismo día.
  - (d) AJ-3 (gates por pasada) y AJ-4 (sello con la generación del bloqueo), en `backend/proyecto/` ([architecture.md](architecture.md) §3.2).
  - `docs/` recoge lo construido en esta fecha: architecture §2, §3, §3.1, §3.2, §4, §6, §6.3, §7 y §8; definitions §3, §6 y §9; validators §2; spec1 y los planes.
