# plan-formal.md — Verificación formal: TLA+ del grafo y Lean de la cronología

> **Estado: en curso (2026-09-23).** Lo escribe la sesión formal, que es dueña de `formal/` y de este fichero. Cubre V-25 (TLA+ del grafo de estados, [architecture.md](../docs/architecture.md) §3.4) y el proyecto Lake de la cronología (§4.2, RF-111, RF-112, TC-1, TC-2).
>
> El modelo sigue las **decisiones** de [spec-backend-2.md](spec-backend-2.md), no solo el código escrito hoy: R-1 y AJ-1 a AJ-6. Lo que el modelo supone y el código aún no hace está en §4, y se alinea rama a rama cuando termine el bloque 2 del backend.

---

## 1. Qué se especifica y qué no

| Pieza | Dónde | Qué comprueba |
|---|---|---|
| Grafo de estados | [`formal/tla/GrafoNovela.tla`](../formal/tla/GrafoNovela.tla) | La función de siguiente orden, la tabla de transiciones, el bloqueo con dos ejecutores, las caídas con reanudación y los dos efectos de un subagente que no pasan por `/resultado`: el canje del identificador de un solo uso (`/mcp/entrada`) y las escrituras del Bibliotecario (`/mcp/escritura`). Seis invariantes y la liveness de §3.4 |
| Cronología | [`formal/lean/`](../formal/lean/) | Las tres invariantes de §4.2 sobre el fichero que genera el backend por novela, con `decide` |

Fuera del modelo TLA+, y dicho para que no se lea como verificado:

- **La cola y el worker** (TC-8, R-4). Los dos ejecutores del modelo son simétricos: los dos corren la skill `orquestar-novela`. Que el worker lance una sola vez y marque el trabajo `fallido` no está modelado.
- **`error` con causa** (AJ-5, TC-3) y **`AgenteSinEsquema`** (Q8): no cambian el estado, así que son pasos de tartamudeo (*stuttering*) y no hay nada que comprobar.
- **La renovación del bloqueo.** El reloj no se modela: renovar a tiempo es lo normal, y no renovar es la acción `CaducarEnVida`, acotada.
- **El contenido.** Qué dice un capítulo, qué hallazgos tiene y qué escribe el Bibliotecario se abstrae en el desenlace de cada orden, que se elige de forma no determinista entre los posibles.

---

## 2. TLA+

### 2.1 Qué es cada variable

| Variable | Qué representa | En el código |
|---|---|---|
| `bd.estado`, `detenidaDesde`, `paradaPlan`, `paradaFinal`, `ciclos`, `intentosPaso`, `cap`, `av`, `orden` | La `Instantanea` de `maquina.py`: fila `proyecto`, filas `capitulo`, banderas de avance y orden vigente | `persistencia._instantanea` |
| `bd.orden.canjeado` | Si el identificador de un solo uso de la orden vigente ya se canjeó | `/mcp/entrada` (paso 5, E-6) |
| `bd.vig` | La versión vigente de cada capítulo en la versión de novela en curso, con lo que ya pasó sobre ella (deterministas, juez, Bibliotecario, origen, publicada) | `capitulo_version`, `capitulo.version_vigente` |
| `bd.gates` | Cobertura y Lean guardados por ciclo (TC-4); con AJ-3, cada pasada empieza vacía | paso 8a |
| `bd.rev` | Capítulos que quedan por revisar y en qué fase (Revisor o Bibliotecario) | AJ-2 |
| `bd.lotes` | Lotes de escritura del Bibliotecario en la biblia para cada capítulo desde la última emisión | B-16 |
| `bd.cambio` | Estado del cambio del lector | `cambio_lector.estado` |
| `bd.pubs` | Las versiones publicadas, en orden, cada una con la versión de cada capítulo | `version_novela`, `version_novela_capitulo` |
| `bloqueo` | Titular y vigencia del bloqueo | `proyecto.bloqueo_*` |
| `ej` | Lo que cada ejecutor tiene en su ventana: token, copia de la orden, qué ha hecho su subagente. Se pierde al caer | la sesión de Claude Code |
| `cota`, `fantasma` | Contadores de las cotas del modelo y marcas para las invariantes 2 y 6 | no existen |

Dos abstracciones que conviene tener presentes al leer la especificación:

- **Los tokens son relativos.** Un ejecutor tiene el token `actual`, uno `viejo` o ninguno. Como cada toma genera un token nuevo, uno viejo no vuelve a valer nunca: basta con saber si es el de la fila.
- **La copia de la orden** lleva `vigente` y `sello`, que equivalen a comparar su id y su sello con los de la fila. Cuando la orden se cierra o se vuelve a sellar, el backend no toca las copias; el modelo las marca para no tener que llevar ids que crecen.

### 2.2 Configuración

| Constante | Entrega | Rápido | Anterior | Qué es |
|---|---|---|---|---|
| `NCap` | 5 | 2 | 2 | Capítulos (el código: 10) |
| `TopeIntentos` | 2 | 2 | 2 | Intentos por orden y por capítulo (el código: 3) |
| `TopeCiclos` | 2 | 2 | 2 | Ciclos de revisión (el código: 3) |
| `MaxCambios` | 1 | 1 | 1 | Cambios del lector |
| `Ejecutores` | `{sesion, worker}` | ídem | ídem | Dos ejecutores que compiten por el bloqueo |
| `MaxCaidas` | 2 | 2 | 2 | Caídas de un ejecutor, en cualquier punto entre dos acciones |
| `MaxCaducidades` | 1 | 1 | 1 | Caducidades del bloqueo con su titular vivo |
| `MaxReintentos` | 1 | 1 | 1 | «Reintentar» desde `detenida` |
| `MaxCambiosPlan`, `MaxNotasFinal` | 1 | 1 | 1 | Vueltas humanas en las dos paradas |
| `MaxAfectados` | 2 | 2 | 2 | Capítulos que toca una revisión o un cambio del lector |
| `SelloConGeneracion` | `TRUE` | `TRUE` | `FALSE` | AJ-4 |
| `GatesPorPasada` | `TRUE` | `TRUE` | `FALSE` | AJ-3 |

Las paradas `aprobacion_plan` y `aprobacion_final` se exploran activas e inactivas: las cuatro combinaciones salen del estado inicial. Los tres ficheros están en `formal/tla/`: `GrafoNovela.cfg` (entrega), `GrafoNovelaRapido.cfg` y `GrafoNovelaAnterior.cfg`. El de entrega y el rápido deben pasar. El anterior reproduce el diseño previo a AJ-3 y AJ-4 y **tiene que fallar**: si pasa, el modelo ha dejado de ver los fallos de §5.

### 2.3 Las invariantes y la liveness

| §3.4 | En la especificación | Cómo se formaliza |
|---|---|---|
| 1. Nunca se publica una versión con un capítulo que no ha pasado todos los validadores | `Inv1_PublicaVerificado` (propiedad de acción) | En el paso que publica, todo capítulo está `aprobado` y terminado; su versión vigente pasó los deterministas y el Bibliotecario, y también el juez de capítulo si viene del bucle; cobertura y Lean de la pasada están en verde **y se evaluaron sobre esas mismas versiones**; y el juez de manuscrito aprobó sin que cambiara nada después. Un capítulo revisado no vuelve a pasar el juez de capítulo (AJ-2): lo cubre el juez de manuscrito, y está decidido así |
| 2. La reanudación no duplica ni pierde capítulos | `Inv2_SinDuplicados`, `Inv2_ReanudarSinCoste`, `Inv2_NoPierde` | La biblia no recibe dos lotes de escritura para un capítulo; una reanudación no gasta un intento porque el identificador de un solo uso ya estuviera canjeado; y un capítulo terminado conserva lo que lo terminó (salvo mientras lo revisa el Revisor). Que cada capítulo tenga exactamente una versión vigente lo da la representación (`vig` es una función) |
| 3. Publicar la N+1 no modifica la N | `Inv3_VersionAnterior` (propiedad de acción), `Inv3_PublicadaCoherente` | Las versiones publicadas solo se añaden, nunca cambian; y en `publicada` lo vigente es exactamente la última versión publicada, también después de un cambio fallido (AJ-6) |
| 4. Los reintentos nunca superan el límite | `Inv4_Topes` | `intentosPaso`, `ciclos`, los intentos de cada capítulo y el intento de la orden vigente, dentro de sus topes, con los mismos márgenes que `maquina.incoherencias()` |
| 5. Una parada humana activa no se sale sin acción humana | `Inv5_ParadaHumana` (propiedad de acción) | Si el proyecto está en `aprobacion_plan`, `aprobacion_final`, `publicada`, `detenida` o en `cambio_solicitado` con el cambio propuesto, y el estado cambia, el paso es una acción humana |
| 6. Dos ejecutores nunca trabajan a la vez | `Inv6_UnSoloEjecutor` | Solo un token vale en cada momento, y nadie escribe en el proyecto (emitir, registrar, canjear o escribir en la biblia) mientras **otro** tiene el bloqueo vigente. Lo que escribe un ejecutor solo, con el bloqueo ya caducado, no cuenta aquí: que no sobreviva al relevo lo vigila la invariante 2 (I-formal-1, §5) |
| Liveness | `Termina`, `CambioTermina` | Desde cualquier estado que no sea `publicada` ni `detenida` se llega a uno de los dos; y un cambio confirmado acaba `aplicado` o `fallido` |

Además, `TypeOK` y `Coherencia` comprueban los tipos y lo que `maquina.incoherencias()` supone de una instantánea, y `Transitar` aborta con `Assert` ante cualquier arista que no esté en la tabla (RF-04).

**Supuestos de la liveness.** Hay equidad débil en los pasos de cada ejecutor, en la caducidad del bloqueo de un titular caído y en las respuestas del humano en las esperas (subir el brief, confirmar hechos, las dos paradas y confirmar o rechazar un cambio). Pedir un cambio y reintentar no son equitativos: son decisiones humanas, acotadas por constantes. Las caídas y las caducidades con el titular vivo están acotadas, así que lo que se demuestra es «con un número finito de caídas». Nadie lanza `/generar` ni `/regenerar` sobre un proyecto que espera a un humano (`HayTrabajo`).

### 2.4 Correspondencia con el código

Estado de cada fila: **igual**, si la especificación sigue el código de hoy; **pendiente**, si sigue una decisión que el código aún no aplica (§4). Las rutas son de `backend/proyecto/` salvo que se diga otra cosa.

| Especificación | Código | Estado |
|---|---|---|
| `Aristas` | `transiciones.TRANSICIONES` | igual |
| `DetenPorTope`, `FallidasPorTope` | `transiciones._DETENIBLES_POR_TOPE`, `_FALLIDAS_POR_TOPE` | igual |
| `DestinoDeReintentar` | `transiciones.DESTINO_DE_REINTENTAR` | igual |
| `ParadasHumanas`, `OrigenesDeDetenida` | `transiciones.PARADAS_HUMANAS`, `ORIGENES_DE_DETENIDA` | igual |
| `Transitar` | `maquina._transitar` | igual; el vaciado de gates al entrar en `verificacion_manuscrito` es AJ-3, **pendiente** |
| `Deshacer` | — | **pendiente**: AJ-6, paso 9a |
| `FueraDelBucle`, `EnCurso` | `maquina.CapituloInstantanea.fuera_del_bucle`, `_capitulo_en_curso` | igual |
| `DestinoDeFracaso` | `maquina._destino_de_fracaso` | igual |
| `Derivar`, `Derivaciones` | `maquina._derivar`, `_derivaciones`, `resolver` | igual, salvo `planificacion`: una sola salida (R-1, AJ-1), **pendiente** |
| `Decision` | `maquina.siguiente_orden`, sin orden vigente | igual, salvo `planificacion` (AJ-1) y `revision` (AJ-2), **pendientes** |
| `EnBucle` | `maquina._en_bucle` | igual |
| `EnRevision` | — | **pendiente**: AJ-2. Hoy `revision` lanza al Revisor sin capítulo |
| `Emitir` | `persistencia._emitir` | igual; el borrado de lo escrito por el Bibliotecario es B-16, **pendiente** (paso 8) |
| `GatesPorEvaluar`, `EvaluarGates` | — | **pendiente**: TC-4 y AJ-3, paso 8a. Hoy `persistencia._gates` devuelve `SIN_EVALUAR` |
| `Resellar` | — | **pendiente**: AJ-4 |
| `FalloDePaso` | `maquina._desenlace_de_paso`, rama de fallo | igual |
| `Gates` | `maquina._gates` | igual; la composición con cobertura y Lean es TC-4, **pendiente** |
| `Publicar` | `maquina._desenlace_de_paso` · Exportador | transición igual; las versiones publicadas son del paso 9, **pendientes** |
| `DesenlacePaso` | `maquina._desenlace_de_paso` | igual, salvo el planificador (AJ-1) |
| `DesenlaceCapitulo` | `maquina._desenlace_de_capitulo` | igual (Q5: contenido gasta intento del capítulo, forma repite el agente) |
| `DesenlaceRevision` | — | **pendiente**: AJ-2 |
| `Manejar` | manejador del Bibliotecario (B-16) | **pendiente**: paso 8 |
| `AplicarDesenlace` | `maquina.aplicar_desenlace` | igual, salvo `revision` (AJ-2) |
| `Reabrir` | `maquina._reabrir` | igual |
| `Humana` | `maquina.aplicar_accion_humana` | igual, salvo que confirmar reabre los capítulos afectados (AJ-6), **pendiente** |
| `Tomar` | `bloqueo.tomar_bloqueo` | igual; volver a sellar es AJ-4, **pendiente** |
| `Pedir` | `persistencia.emitir_siguiente_orden`, y el lanzamiento del subagente | igual |
| `Canjear` | `/mcp/entrada` | **pendiente**: paso 5 (E-6) y AJ-4 |
| `EscribirBiblia` | `/mcp/escritura` | **pendiente**: paso 8 y AJ-4 |
| `Terminar` | el subagente devuelve su salida | fuera del backend |
| `Registrar` | `persistencia.registrar_resultado` | igual; rechazar el sello viejo es AJ-4, **pendiente** |
| `Soltar` | `bloqueo.soltar_bloqueo` | igual |
| `Caer` | la sesión muere (V-1, `tests/test_reanudacion.py`) | — |
| `CaducarTrasCaida`, `CaducarEnVida` | `bloqueo.DURACION`, `bloqueo.exigir_bloqueo` | igual |
| `Decidir` | `persistencia.decidir` y `_caducar` | igual |
| `SubirBrief`, `ConfirmarHechos` | `intake/persistencia.guardar_brief`, `confirmar_hechos` | igual |
| `AprobarPlan` … `Reintentar` | las rutas de decisión de `router.py` y `persistencia.reintentar` | igual |
| `TypeOK`, `Coherencia`, `Inv4_Topes` | `maquina.incoherencias()` y los `CHECK` de `shared/esquema.sql` | igual |

### 2.5 Cómo se ejecuta

TLC necesita Java 11 o superior. En esta máquina hay un JRE Temurin 21 a nivel de usuario, sin añadir al PATH, y `tla2tools.jar` v1.7.4:

```powershell
$java = "$env:USERPROFILE\herramientas\jre\jdk-21.0.12.1+1-jre\bin\java.exe"
$tla  = "C:\Users\student\tools\tla\tla2tools.jar"
cd formal\tla
& $java -cp $tla tla2sany.SANY GrafoNovela.tla                      # solo sintaxis
& $java -XX:+UseParallelGC -Xmx8g -cp $tla tlc2.TLC -config GrafoNovelaRapido.cfg `
    -workers auto -deadlock -metadir $env:TEMP\tlc GrafoNovela.tla
```

`-deadlock` desactiva la comprobación de bloqueo mutuo: `publicada` y `detenida` sin nada más que hacer son estados finales legítimos. Un estado que se queda parado sin serlo lo detecta la liveness. `-metadir` saca del repositorio el directorio de estados de TLC.

---

## 3. Lean

### 3.1 El fichero que genera el backend

Es el contrato de [spec-backend-2.md](spec-backend-2.md) §4.2, con estos detalles fijados aquí:

- **Codificación:** UTF-8 **sin BOM**, con saltos `\n`. Con BOM, Lean no lee el fichero (`expected token` en 1:0).
- **Cabecera:** `import Cronologia` y `open Cronologia`.
- **Días:** `date.toordinal()` de Python, donde el 1 es el 0001-01-01. Una fecha parcial es el intervalo cerrado entero: `2023-07` es `.recuerdo 738702 738732`. Un periodo sin fecha segura va con el intervalo más ancho que se pueda afirmar. La historia es `.historia <dia> .manana | .tarde | .noche`.
- **Nacimiento:** intervalo cerrado de días, `some (desde, hasta)`, o `none` si no se sabe.
- **Listas ordenadas por id**, y ids numéricos con su correspondencia en un JSON aparte, sin texto libre.

```lean
import Cronologia
open Cronologia

def novela : Novela :=
  { localizaciones := [ { id := 1, padre := none }, { id := 2, padre := some 1 } ],
    personajes := [ { id := 1, nacimiento := some (736431, 736431) } ],
    eventos :=
      [ { id := 1, momento := .recuerdo 738702 738732, lugar := 2, presentes := [1],
          excluye := none },
        { id := 2, momento := .historia 1 .manana, lugar := 1, presentes := [1],
          excluye := none } ] }

theorem lugar_unico : lugarUnico novela = true := by decide +kernel
theorem sin_reaparicion : sinReaparicion novela = true := by decide +kernel
theorem nacido_antes : nacidoAntes novela = true := by decide +kernel

#eval violaciones novela
```

Hay dos ejemplos completos en `formal/lean/ejemplos/`: `novela.lean`, que pasa, y `novela_falla.lean`, en el que un personaje reaparece tras su partida.

### 3.2 Las invariantes

| §4.2 | Función | Violación |
|---|---|---|
| 1. Un personaje no está en dos lugares en el mismo momento | `lugarUnico` / `choquesLugar` | El mismo personaje en dos eventos que son **con seguridad** el mismo momento, en lugares que no se contienen el uno al otro. Solo la historia da simultaneidad segura: mismo día y misma franja. Dos recuerdos del mismo día pueden ser uno de mañana y otro de noche |
| 2. Nadie aparece después de un evento que lo excluye | `sinReaparicion` / `reapariciones` | Un personaje presente en un evento que es **con seguridad** posterior al que lo excluye: un recuerdo es anterior a otro si termina antes de que el otro empiece, toda la historia es posterior a todos los recuerdos, y en la historia manda el día y después la franja. En el propio evento que lo excluye, y en la misma franja, no hay violación |
| 3. La edad cuadra con la fecha de nacimiento (TC-2: nadie aparece en un evento fechado antes de nacer) | `nacidoAntes` / `antesDeNacer` | Un personaje presente en un recuerdo que termina antes del primer día en que pudo nacer. La historia no tiene fecha de calendario y no se compara |

«Estar dentro» sube por `padre` con un combustible igual al número de localizaciones, así que una lista con un ciclo no cuelga la comprobación. Todo es recursión estructural sobre listas, para que el núcleo pueda reducirlo.

### 3.3 Cómo lo ejecuta el backend y qué devuelve

```powershell
cd formal\lean
lake build                                   # una vez, o tras cambiar Cronologia/
lake env lean <proyecto>\verificacion\ciclo-k\cronologia.lean
```

| Resultado | Código de salida | Salida |
|---|---|---|
| Las tres invariantes se cumplen | 0 | Una línea `{"lugar_unico":[],"exclusion":[],"nacimiento":[]}` |
| Alguna se infringe | 1 | Un error por teorema fallido (`Tactic 'decide' proved that the proposition … is false`) y la línea JSON con las violaciones |
| Error de herramienta | ≠ 0 | Errores de Lean sin violaciones en el JSON, o sin línea JSON: es la causa `lean_no_disponible` o un error de generación, no un gate en rojo |

La línea JSON es la única que empieza por `{`. Su forma es fija:

```json
{"lugar_unico":[{"personaje":1,"eventos":[3,7]}],
 "exclusion":[{"personaje":2,"excluye":4,"evento":9}],
 "nacimiento":[{"personaje":1,"evento":2}]}
```

(en una sola línea). Las listas salen en el orden de `novela.eventos`, así que la misma novela da la misma línea. Con los ids de eventos, el backend saca los capítulos que van al Revisor (`evento.capitulo`, spec-backend-2 §3.7).

### 3.4 Pruebas y prueba de tamaño

- **`lake build Pruebas`** compila [`Pruebas/Casos.lean`](../formal/lean/Pruebas/Casos.lean). Tiene un caso por invariante que la infringe (con la violación exacta), casos de control que rozan cada regla sin infringirla, la comprobación de que cada caso negativo infringe solo su invariante, y la forma del JSON con `#guard_msgs`. Si una regla deja de detectar su caso o dispara en uno de control, no compila. Es la parte de V-27 que no necesita novela.
- **La prueba de tamaño** genera con `python scripts/generar_tamano.py <n>` una novela coherente con `n` eventos de historia, 20 recuerdos, 12 personajes y 50 localizaciones, en `tamano/`, que no se versiona. Es el caso más caro para `decide`, porque no hay nada que encontrar.

| Eventos (historia + recuerdos) | `by decide` | `by decide +kernel` |
|---|---|---|
| 80 + 20 | **agota `maxRecDepth`** | pasa |
| 320 + 20 | agota `maxRecDepth` | pasa |

Por eso el contrato dice `decide +kernel` (Q4). Da la misma garantía, porque la prueba la sigue comprobando el núcleo, y se salta la evaluación en el elaborador, que es la que agota la recursión. `native_decide` no se usa: metería el compilador en la base de confianza.

---

## 4. Lo que el modelo supone y el código aún no hace

Se alinea con el código cuando termine el bloque 2 del backend (AJ-1 a AJ-5) y el bloque 3 (AJ-6). Hasta entonces, las filas **pendientes** de §2.4 son especificación de lo que el código tiene que hacer, no descripción de lo que hace.

| # | Decisión | Qué supone el modelo |
|---|---|---|
| 1 | R-1, AJ-1 | En `planificacion`, una sola orden, la del `planificador`; el plan está completo cuando su salida se acepta y no hay notas pendientes |
| 2 | AJ-2, §3.7 | En `revision`, por cada capítulo del informe y en orden: Revisor (con los deterministas al registrarlo), que crea una versión nueva, y Bibliotecario sobre ella. Un fallo de cualquiera gasta `intentos_paso` y, agotado, va a `detenida` o a `publicada` con el cambio fallido. Los capítulos a revisar son un subconjunto no vacío no determinista |
| 3 | AJ-3, TC-4 | Cobertura y Lean se evalúan al calcular la orden del juez de manuscrito y se reutilizan dentro de la misma pasada; cada entrada a `verificacion_manuscrito` empieza sin ellos. Los gates están en verde si lo están los tres |
| 4 | AJ-4 | Tomar el bloqueo con una orden vigente la vuelve a sellar: identificador nuevo para el Extractor y el Intérprete, lo escrito por el Bibliotecario borrado. Se rechazan los resultados, los canjes y las escrituras con sello viejo |
| 5 | B-16 | Emitir una orden de Bibliotecario borra lo escrito para su capítulo; registrarla sin nada escrito es un fallo de forma |
| 6 | AJ-6 | Confirmar un cambio reabre los capítulos afectados (subconjunto no vacío no determinista); si el cambio falla, se restaura la versión N, los capítulos vuelven a `aprobado` y el cambio queda `fallido` |

---

## 5. Contraejemplos y hallazgos

Listos para copiar a [docs/iteraciones.md](../docs/iteraciones.md), que es de otra sesión. Cada uno dice si lo encontró TLC o la lectura, y qué cambio provoca. Los que cambian el código se han pasado a la sesión de backend, que los ha recogido como AJ-2 a AJ-6.

*(Se completa con las ejecuciones.)*
