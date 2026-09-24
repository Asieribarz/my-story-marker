------------------------------ MODULE GrafoNovela ------------------------------
(******************************************************************************)
(* El grafo de estados de my-story-marker: architecture.md §3.1-§3.4, V-25.   *)
(*                                                                            *)
(* Modela la función de siguiente orden y la tabla de transiciones de         *)
(* backend/proyecto/ (maquina.py, transiciones.py, persistencia.py,           *)
(* bloqueo.py), con dos ejecutores que compiten por el bloqueo, caídas en     *)
(* cualquier punto seguidas de reanudación, y los dos efectos de un           *)
(* subagente que no pasan por /resultado: el canje del identificador de un    *)
(* solo uso (/mcp/entrada) y las escrituras del Bibliotecario                 *)
(* (/mcp/escritura).                                                          *)
(*                                                                            *)
(* Cada operación del backend es una transacción de SQLite y aquí es una      *)
(* acción atómica; las caídas ocurren entre acciones. La correspondencia de   *)
(* cada acción y cada operador con su rama del código está en                 *)
(* specs/plan-formal.md §2.4.                                                 *)
(******************************************************************************)
EXTENDS Naturals, FiniteSets, Sequences, TLC

CONSTANTS
    NCap,               \* capítulos del modelo; el código tiene 10
    TopeIntentos,       \* tope de intentos de una orden y de un capítulo (código: TOPE = 3)
    TopeCiclos,         \* tope de ciclos de revisión (código: TOPE = 3)
    MaxCambios,         \* cambios del lector
    Ejecutores,         \* la sesión interactiva y el worker
    MaxCaidas,          \* caídas de un ejecutor, en cualquier punto
    MaxCaducidades,     \* veces que el bloqueo caduca con su titular vivo
    MaxReintentos,      \* «reintentar» desde detenida
    MaxCambiosPlan,     \* «cambios» en aprobacion_plan
    MaxNotasFinal,      \* «notas» en aprobacion_final
    MaxAfectados,       \* capítulos que toca una revisión o un cambio del lector
    SelloConGeneracion, \* AJ-4: el sello lleva la generación del bloqueo
    GatesPorPasada      \* AJ-3: los gates se guardan por pasada, no por ciclo

ASSUME /\ NCap \in Nat \ {0}
       /\ TopeIntentos \in Nat \ {0}
       /\ TopeCiclos \in Nat
       /\ SelloConGeneracion \in BOOLEAN
       /\ GatesPorPasada \in BOOLEAN

Caps == 1..NCap
Nadie == "nadie"
Ninguno == "ninguno"

Min(S) == CHOOSE x \in S : \A y \in S : x <= y

Afectables == {S \in SUBSET Caps : S # {} /\ Cardinality(S) <= MaxAfectados}

-------------------------------------------------------------------------------
(* Vocabulario: shared/tipos.py y R-1 de specs/spec-backend-2.md.        *)

Estados == {"intake", "contexto", "planificacion", "aprobacion_plan", "escaleta",
            "capitulos", "verificacion_manuscrito", "revision", "aprobacion_final",
            "publicacion", "publicada", "cambio_solicitado", "regeneracion",
            "detenida"}

EstadosCap == {"pendiente", "borrador", "editado", "verificado", "aprobado",
               "revision_humana"}

\* R-1: `planificador` sustituye a arquitecto, personajes, mundo y estilo.
Agentes == {"agente-contexto", "extractor-hechos", "planificador", "escaletista",
            "escritor", "editor-estilo", "juez-capitulo", "bibliotecario",
            "juez-manuscrito", "revisor", "exportador", "interprete-cambios"}

\* Los que canjean un identificador de un solo uso por /mcp/entrada.
AgentesDeEntrada == {"extractor-hechos", "interprete-cambios"}

-------------------------------------------------------------------------------
(* La tabla de transiciones: transiciones.py, TRANSICIONES.                  *)

DetenPorTope == {"intake", "contexto", "planificacion", "escaleta",
                 "verificacion_manuscrito", "revision", "publicacion"}

FallidasPorTope == {"verificacion_manuscrito", "revision", "publicacion",
                    "cambio_solicitado"}

DestinoDeReintentar ==
    [s \in DetenPorTope \cup {"capitulos"} |->
        IF s = "verificacion_manuscrito" THEN "capitulos" ELSE s]

Aristas ==
    { <<"intake", "contexto", "brief_normalizado">>,
      <<"contexto", "planificacion", "contexto_validado">>,
      <<"planificacion", "aprobacion_plan", "plan_completo">>,
      <<"planificacion", "escaleta", "plan_completo">>,
      <<"aprobacion_plan", "escaleta", "plan_aprobado">>,
      <<"aprobacion_plan", "planificacion", "plan_con_cambios">>,
      <<"escaleta", "capitulos", "escaleta_completa">>,
      <<"capitulos", "verificacion_manuscrito", "capitulos_aprobados">>,
      <<"capitulos", "detenida", "capitulo_agotado">>,
      <<"capitulos", "detenida", "veto_agotado">>,
      <<"verificacion_manuscrito", "revision", "gates_con_fallos">>,
      <<"revision", "verificacion_manuscrito", "revision_hecha">>,
      <<"verificacion_manuscrito", "detenida", "revisiones_agotadas">>,
      <<"verificacion_manuscrito", "publicada", "revisiones_agotadas">>,
      <<"verificacion_manuscrito", "aprobacion_final", "gates_verdes">>,
      <<"verificacion_manuscrito", "publicacion", "gates_verdes">>,
      <<"aprobacion_final", "revision", "final_con_notas">>,
      <<"aprobacion_final", "publicacion", "final_aprobado">>,
      <<"publicacion", "publicada", "version_publicada">>,
      <<"publicada", "cambio_solicitado", "peticion_lector">>,
      <<"cambio_solicitado", "publicada", "cambio_rechazado">>,
      <<"cambio_solicitado", "regeneracion", "cambio_confirmado">>,
      <<"regeneracion", "verificacion_manuscrito", "capitulos_aprobados">>,
      <<"regeneracion", "publicada", "capitulo_agotado">>,
      <<"regeneracion", "publicada", "veto_agotado">> }
    \cup {<<o, "detenida", "tope_agotado">> : o \in DetenPorTope}
    \cup {<<o, "publicada", "tope_agotado">> : o \in FallidasPorTope}
    \cup {<<"detenida", DestinoDeReintentar[s], "reintentar">> :
              s \in DOMAIN DestinoDeReintentar}

OrigenesDeDetenida == {a[1] : a \in {x \in Aristas : x[2] = "detenida"}}

\* transiciones.PARADAS_HUMANAS: de aquí no sale ninguna arista automática.
ParadasHumanas == {"aprobacion_plan", "aprobacion_final", "publicada", "detenida"}

\* Las causas que devuelven una regeneración a `publicada` con el cambio fallido.
CausasDeFracaso == {"capitulo_agotado", "veto_agotado", "revisiones_agotadas",
                    "tope_agotado"}

-------------------------------------------------------------------------------
(* El estado persistido. `bd` es la base del proyecto: los campos estado,     *)
(* detenidaDesde, paradaPlan, paradaFinal, ciclos, intentosPaso, cap, av y    *)
(* orden son la `Instantanea` de maquina.py; los demás son tablas de pasos    *)
(* posteriores (plan-formal.md §2.1).                                         *)

SinOrden == [hay |-> FALSE, agente |-> Ninguno, capitulo |-> 0, intento |-> 0,
             estado |-> Ninguno, canjeado |-> FALSE]

CapInicial == [estado |-> "pendiente", intentos |-> 0, terminado |-> FALSE]

\* La versión vigente de un capítulo y qué ha pasado ya sobre ella.
Version(origen, det) ==
    [det |-> det, juez |-> FALSE, bib |-> FALSE, origen |-> origen, enPub |-> FALSE]

SinVersion == Version("bucle", FALSE)

\* TC-4: cobertura y Lean, guardados por ciclo de la versión en curso. Con AJ-3,
\* cada entrada a verificacion_manuscrito es una pasada nueva y empieza sin ellos.
\* `alDia` no existe en el código: dice si se evaluaron sobre las versiones vigentes.
SinGate == [hay |-> FALSE, cob |-> FALSE, lean |-> FALSE, alDia |-> FALSE]
GatesSinEvaluar == [k \in 0..TopeCiclos |-> SinGate]

RevVacia == [pend |-> {}, fase |-> "revisor"]

AvanceInicial ==
    [brief |-> FALSE, textoLibre |-> FALSE, extraccionHecha |-> FALSE,
     hechosPendientes |-> FALSE, briefNormalizado |-> FALSE,
     contextoValidado |-> FALSE, plan |-> FALSE, notasPlan |-> FALSE,
     fichas |-> FALSE, cambioPropuesto |-> FALSE, esRegeneracion |-> FALSE]

BdInicial(pp, pf) ==
    [estado |-> "intake", detenidaDesde |-> Ninguno,
     paradaPlan |-> pp, paradaFinal |-> pf,
     ciclos |-> 0, intentosPaso |-> 0,
     cap |-> [c \in Caps |-> CapInicial],
     av |-> AvanceInicial,
     orden |-> SinOrden,
     vig |-> [c \in Caps |-> SinVersion],
     gates |-> GatesSinEvaluar,
     juezAlDia |-> FALSE,
     rev |-> RevVacia,
     lotes |-> [c \in Caps |-> 0],
     cambio |-> Ninguno,
     pubs |-> << >>]

\* La copia de la orden que tiene un ejecutor. `vigente` y `sello` dicen si su
\* id y su sello siguen siendo los de la fila: equivalen a comparar con ella.
OrdNula == [agente |-> Ninguno, capitulo |-> 0, intento |-> 0, estado |-> Ninguno,
            vigente |-> FALSE, sello |-> FALSE]

CopiaDe(o) == [agente |-> o.agente, capitulo |-> o.capitulo, intento |-> o.intento,
               estado |-> o.estado, vigente |-> TRUE, sello |-> TRUE]

EjInactivo == [pc |-> "inactivo", tok |-> Ninguno, ord |-> OrdNula,
               texto |-> "no", escribio |-> FALSE]

-------------------------------------------------------------------------------
(* La máquina: funciones puras sobre `bd`, como maquina.py.                  *)

FueraDelBucle(k) == k.terminado \/ k.estado = "revision_humana"

\* maquina._capitulo_en_curso: el de menor número que no está fuera del bucle.
EnCurso(b) ==
    LET abiertos == {c \in Caps : ~FueraDelBucle(b.cap[c])}
    IN IF abiertos = {} THEN 0 ELSE Min(abiertos)

PlanCompleto(a) == a.plan /\ ~a.notasPlan

\* maquina._destino_de_fracaso.
DestinoDeFracaso(b) ==
    IF b.estado \in {"cambio_solicitado", "regeneracion"} THEN "publicada"
    ELSE IF b.estado \in {"verificacion_manuscrito", "revision", "publicacion"}
            /\ b.av.esRegeneracion
         THEN "publicada"
         ELSE "detenida"

\* Paso 9a (no está en el código): un cambio fallido deja vigente la versión N.
Deshacer(b) ==
    [b EXCEPT !.cap = [c \in Caps |->
                         [estado |-> "aprobado", intentos |-> 0, terminado |-> TRUE]],
              !.vig = b.pubs[Len(b.pubs)],
              !.gates = GatesSinEvaluar,
              !.juezAlDia = FALSE,
              !.rev = RevVacia,
              !.cambio = "fallido",
              !.av.cambioPropuesto = FALSE]

\* Solo para TLC: al dejar una fase a la que no se vuelve, los campos que ya no
\* lee ninguna rama vuelven a su valor inicial. No cambia ningún comportamiento;
\* evita distinguir estados que solo se diferencian en datos muertos. De `intake`
\* no se vuelve una vez fuera, ni de `planificacion` tras `escaleta`.
Olvidar(b, destino) ==
    CASE destino = "contexto" ->
            [b EXCEPT !.av.brief = FALSE, !.av.textoLibre = FALSE,
                      !.av.extraccionHecha = FALSE, !.av.briefNormalizado = FALSE]
      [] destino = "capitulos" /\ b.estado = "escaleta" ->
            [b EXCEPT !.paradaPlan = FALSE]
      [] OTHER -> b

\* maquina._transitar: un paso por la tabla; una arista que no está es un error.
Transitar(b, destino, causa) ==
    IF <<b.estado, destino, causa>> \notin Aristas
    THEN Assert(FALSE, <<"arista fuera de la tabla", b.estado, destino, causa>>)
    ELSE LET t == [Olvidar(b, destino) EXCEPT
                     !.estado = destino,
                     !.detenidaDesde = IF destino = "detenida" THEN b.estado ELSE Ninguno,
                     !.intentosPaso = 0,
                     !.gates = IF GatesPorPasada /\ destino = "verificacion_manuscrito"
                               THEN GatesSinEvaluar
                               ELSE b.gates]
         IN IF destino = "publicada" /\ causa \in CausasDeFracaso
            THEN Deshacer(t)
            ELSE t

\* maquina._derivar: una fase ha dejado hecho lo que la cierra.
Derivar(b) ==
    LET a == b.av IN
    CASE b.estado = "intake" ->
            (IF a.brief /\ a.briefNormalizado /\ (a.extraccionHecha \/ ~a.textoLibre)
                /\ ~a.hechosPendientes
             THEN <<"contexto", "brief_normalizado">>
             ELSE << >>)
      [] b.estado = "contexto" ->
            (IF a.contextoValidado THEN <<"planificacion", "contexto_validado">>
             ELSE << >>)
      [] b.estado = "planificacion" ->
            (IF PlanCompleto(a)
             THEN <<(IF b.paradaPlan THEN "aprobacion_plan" ELSE "escaleta"),
                    "plan_completo">>
             ELSE << >>)
      [] b.estado = "escaleta" ->
            (IF a.fichas THEN <<"capitulos", "escaleta_completa">> ELSE << >>)
      [] b.estado \in {"capitulos", "regeneracion"} ->
            (IF EnCurso(b) # 0 THEN << >>
             ELSE IF \E c \in Caps : b.cap[c].estado = "revision_humana"
                  THEN <<DestinoDeFracaso(b), "capitulo_agotado">>
                  ELSE <<"verificacion_manuscrito", "capitulos_aprobados">>)
      [] OTHER -> << >>

\* maquina._derivaciones: encadena las derivaciones hasta una decisión.
RECURSIVE Derivaciones(_)
Derivaciones(b) ==
    IF b.orden.hay THEN b
    ELSE LET d == Derivar(b)
         IN IF d = << >> THEN b ELSE Derivaciones(Transitar(b, d[1], d[2]))

Lanza(agente, capitulo, intento) ==
    [tipo |-> "lanzar", agente |-> agente, capitulo |-> capitulo, intento |-> intento]
Espera == [tipo |-> "esperar", agente |-> Ninguno, capitulo |-> 0, intento |-> 0]
Parada == [tipo |-> "parada", agente |-> Ninguno, capitulo |-> 0, intento |-> 0]

\* maquina._en_bucle: §5, Escritor → Editor → juez → Bibliotecario.
EnBucle(b) ==
    LET c == EnCurso(b)
        k == b.cap[c]
        sig == b.intentosPaso + 1
    IN CASE k.estado = "pendiente" -> Lanza("escritor", c, k.intentos + 1)
         [] k.estado \in {"borrador", "editado"} -> Lanza("editor-estilo", c, sig)
         [] k.estado = "verificado" -> Lanza("juez-capitulo", c, sig)
         [] k.estado = "aprobado" -> Lanza("bibliotecario", c, sig)

\* spec-backend-2 §3.7 (no está en el código): por capítulo, Revisor y después
\* Bibliotecario; los deterministas van con el registro del Revisor.
EnRevision(b) ==
    LET c == Min(b.rev.pend) IN
    IF b.rev.fase = "revisor"
    THEN Lanza("revisor", c, b.intentosPaso + 1)
    ELSE Lanza("bibliotecario", c, b.intentosPaso + 1)

\* maquina.siguiente_orden, sin orden vigente y tras las derivaciones.
Decision(b) ==
    LET a == b.av
        sig == b.intentosPaso + 1
    IN CASE b.estado = "intake" ->
              (IF ~a.brief THEN Espera
               ELSE IF a.textoLibre /\ ~a.extraccionHecha
                    THEN Lanza("extractor-hechos", 0, sig)
                    ELSE IF a.hechosPendientes THEN Espera
                         ELSE Lanza("agente-contexto", 0, sig))
         [] b.estado = "contexto" -> Lanza("agente-contexto", 0, sig)
         [] b.estado = "planificacion" -> Lanza("planificador", 0, sig)
         [] b.estado \in {"aprobacion_plan", "aprobacion_final"} -> Espera
         [] b.estado = "escaleta" -> Lanza("escaletista", 0, sig)
         [] b.estado \in {"capitulos", "regeneracion"} -> EnBucle(b)
         [] b.estado = "verificacion_manuscrito" -> Lanza("juez-manuscrito", 0, sig)
         [] b.estado = "revision" -> EnRevision(b)
         [] b.estado = "publicacion" -> Lanza("exportador", 0, sig)
         [] b.estado = "cambio_solicitado" ->
              (IF a.cambioPropuesto THEN Espera ELSE Lanza("interprete-cambios", 0, sig))
         [] b.estado \in {"publicada", "detenida"} -> Parada

\* persistencia._emitir: la orden se persiste al emitirla. B-16: la orden del
\* Bibliotecario borra lo escrito antes para su capítulo.
Emitir(b, d) ==
    [b EXCEPT !.orden = [hay |-> TRUE, agente |-> d.agente, capitulo |-> d.capitulo,
                         intento |-> d.intento, estado |-> b.estado,
                         canjeado |-> FALSE],
              !.lotes = IF d.agente = "bibliotecario"
                        THEN [b.lotes EXCEPT ![d.capitulo] = 0]
                        ELSE b.lotes]

\* TC-4: cobertura y Lean se evalúan al calcular la orden del juez de manuscrito,
\* y se reutilizan si ya están guardados (por ciclo; con AJ-3, por pasada).
GatesPorEvaluar(b) == ~b.gates[b.ciclos].hay

EvaluarGates(b, cob, lean) ==
    [b EXCEPT !.gates[b.ciclos] = [hay |-> TRUE, cob |-> cob, lean |-> lean,
                                   alDia |-> TRUE]]

\* AJ-4: al tomar el bloqueo con una orden vigente, se vuelve a sellar como si se
\* emitiera de nuevo: identificador nuevo y lo escrito para su capítulo, borrado.
Resellar(b) ==
    [b EXCEPT !.orden.canjeado = FALSE,
              !.lotes = IF b.orden.agente = "bibliotecario"
                        THEN [b.lotes EXCEPT ![b.orden.capitulo] = 0]
                        ELSE b.lotes]

-------------------------------------------------------------------------------
(* Desenlaces: maquina.aplicar_desenlace y los manejadores.                  *)

Aceptado(res) ==
    res \in {"acepta", "acepta_con_hechos", "acepta_sin_hechos", "pasa", "no_pasa"}

\* Una versión nueva de un capítulo deja sin validez lo evaluado sobre la anterior.
Invalidar(b) ==
    [b EXCEPT !.gates = [k \in 0..TopeCiclos |-> [b.gates[k] EXCEPT !.alDia = FALSE]],
              !.juezAlDia = FALSE]

ConVersion(b, c, origen, det) ==
    [Invalidar(b) EXCEPT !.vig[c] = Version(origen, det)]

\* maquina._desenlace_de_paso: un fallo fuera del bucle gasta `intentos_paso`.
FalloDePaso(b) ==
    IF b.intentosPaso + 1 < TopeIntentos
    THEN [b EXCEPT !.intentosPaso = b.intentosPaso + 1]
    ELSE Transitar(b, DestinoDeFracaso(b), "tope_agotado")

\* maquina._gates, con el veredicto del juez y los gates de TC-4.
Gates(b, veredicto, S) ==
    LET g == b.gates[b.ciclos]
        j == [b EXCEPT !.juezAlDia = (veredicto = "pasa")]
        verdes == g.hay /\ g.cob /\ g.lean /\ veredicto = "pasa"
    IN IF verdes
       THEN Transitar(j, (IF b.paradaFinal THEN "aprobacion_final" ELSE "publicacion"),
                      "gates_verdes")
       ELSE IF b.ciclos < TopeCiclos
            THEN [Transitar(j, "revision", "gates_con_fallos")
                     EXCEPT !.ciclos = b.ciclos + 1,
                            !.rev = [pend |-> S, fase |-> "revisor"]]
            ELSE Transitar(j, DestinoDeFracaso(b), "revisiones_agotadas")

\* Paso 9: publicar al registrar al Exportador (TC-4); la versión N+1 se añade.
Publicar(b) ==
    LET v == [c \in Caps |-> [b.vig[c] EXCEPT !.enPub = TRUE]]
        t == Transitar(b, "publicada", "version_publicada")
    IN [t EXCEPT !.vig = v,
                 !.pubs = Append(b.pubs, v),
                 !.av.esRegeneracion = TRUE,
                 !.gates = GatesSinEvaluar,
                 !.juezAlDia = FALSE,
                 !.cambio = IF b.cambio = "confirmado" THEN "aplicado" ELSE b.cambio]

DesenlacePaso(b, o, res, S) ==
    IF ~Aceptado(res) THEN FalloDePaso(b)
    ELSE LET a == [b EXCEPT !.intentosPaso = 0] IN
         CASE o.agente = "extractor-hechos" ->
                 [a EXCEPT !.av.extraccionHecha = TRUE,
                           !.av.hechosPendientes = (res = "acepta_con_hechos")]
           [] o.agente = "agente-contexto" /\ o.estado = "intake" ->
                 [a EXCEPT !.av.briefNormalizado = TRUE]
           [] o.agente = "agente-contexto" /\ o.estado = "contexto" ->
                 [a EXCEPT !.av.contextoValidado = TRUE]
           [] o.agente = "planificador" ->
                 [a EXCEPT !.av.plan = TRUE, !.av.notasPlan = FALSE]
           [] o.agente = "escaletista" -> [a EXCEPT !.av.fichas = TRUE]
           [] o.agente = "juez-manuscrito" -> Gates(a, res, S)
           [] o.agente = "exportador" -> Publicar(a)
           [] o.agente = "interprete-cambios" ->
                 [a EXCEPT !.av.cambioPropuesto = TRUE, !.cambio = "propuesto"]

\* maquina._desenlace_de_capitulo (Q5): el fallo de contenido gasta un intento del
\* capítulo y vuelve al Escritor; el de forma repite solo ese agente. La versión de
\* un capítulo que pasa a `revision_humana` no la vuelve a leer nadie antes de
\* reescribirla o restaurarla, y se olvida como en `Olvidar`.
DesenlaceCapitulo(b, o, res) ==
    LET c == o.capitulo
        k == b.cap[c]
        tipo == IF o.agente = "escritor" /\ res = "forma" THEN "contenido"
                ELSE IF o.agente = "bibliotecario" /\ res \in {"contenido", "contenido_veto"}
                     THEN "forma"
                     ELSE res
        a == [b EXCEPT !.intentosPaso = 0]
    IN IF tipo = "acepta"
       THEN CASE o.agente = "escritor" ->
                    [ConVersion(a, c, "bucle", FALSE) EXCEPT !.cap[c].estado = "borrador"]
              [] o.agente = "editor-estilo" ->
                    [a EXCEPT !.cap[c].estado = "verificado", !.vig[c].det = TRUE]
              [] o.agente = "juez-capitulo" ->
                    [a EXCEPT !.cap[c].estado = "aprobado", !.vig[c].juez = TRUE]
              [] o.agente = "bibliotecario" ->
                    [a EXCEPT !.cap[c].terminado = TRUE, !.vig[c].bib = TRUE]
       ELSE IF tipo \in {"contenido", "contenido_veto"}
            THEN IF k.intentos + 1 < TopeIntentos
                 THEN [a EXCEPT !.cap[c] = [estado |-> "pendiente",
                                            intentos |-> k.intentos + 1,
                                            terminado |-> FALSE]]
                 ELSE LET ag == [a EXCEPT !.cap[c].estado = "revision_humana",
                                          !.cap[c].intentos = k.intentos + 1,
                                          !.vig[c] = SinVersion]
                      IN IF tipo = "contenido_veto"
                         THEN Transitar(ag, DestinoDeFracaso(ag), "veto_agotado")
                         ELSE ag
            ELSE IF b.intentosPaso + 1 < TopeIntentos
                 THEN [b EXCEPT !.intentosPaso = b.intentosPaso + 1]
                 ELSE [a EXCEPT !.cap[c].estado = "revision_humana", !.vig[c] = SinVersion]

\* spec-backend-2 §3.7 (no está en el código).
DesenlaceRevision(b, o, res) ==
    LET c == o.capitulo
        a == [b EXCEPT !.intentosPaso = 0]
    IN IF res # "acepta" THEN FalloDePaso(b)
       ELSE IF o.agente = "revisor"
            THEN [ConVersion(a, c, "revision", TRUE) EXCEPT !.rev.fase = "bibliotecario"]
            ELSE LET r == [a EXCEPT !.vig[c].bib = TRUE,
                                    !.rev = [pend |-> b.rev.pend \ {c},
                                             fase |-> "revisor"]]
                 IN IF r.rev.pend = {}
                    THEN Transitar(r, "verificacion_manuscrito", "revision_hecha")
                    ELSE r

\* El manejador del Bibliotecario (B-16): sin lo escrito de su capítulo, fallo.
Manejar(b, o, res) ==
    IF o.agente = "bibliotecario" /\ res = "acepta" /\ b.lotes[o.capitulo] = 0
    THEN "forma"
    ELSE res

AplicarDesenlace(b, res, S) ==
    LET o == b.orden
        r == Manejar(b, o, res)
        b0 == [b EXCEPT !.orden = SinOrden]
        b1 == IF o.estado \in {"capitulos", "regeneracion"}
              THEN DesenlaceCapitulo(b0, o, r)
              ELSE IF o.estado = "revision"
                   THEN DesenlaceRevision(b0, o, r)
                   ELSE DesenlacePaso(b0, o, r, S)
    IN Derivaciones(b1)

-------------------------------------------------------------------------------
(* Acciones humanas: maquina.aplicar_accion_humana.                          *)

\* maquina._reabrir (RF-64b).
Reabrir(b) ==
    [b EXCEPT !.cap = [c \in Caps |->
                         IF b.cap[c].estado = "revision_humana" THEN CapInicial
                         ELSE b.cap[c]],
              !.ciclos = 0]

Humana(b, accion, S) ==
    LET b0 == [b EXCEPT !.orden = SinOrden] IN
    CASE accion = "aprobar_plan" -> Transitar(b0, "escaleta", "plan_aprobado")
      [] accion = "cambios_plan" ->
            Transitar([b0 EXCEPT !.av.notasPlan = TRUE], "planificacion",
                      "plan_con_cambios")
      [] accion = "aprobar_final" -> Transitar(b0, "publicacion", "final_aprobado")
      [] accion = "notas_final" ->
            [Transitar(b0, "revision", "final_con_notas")
                EXCEPT !.rev = [pend |-> S, fase |-> "revisor"]]
      [] accion = "pedir_cambio" ->
            [Transitar(b0, "cambio_solicitado", "peticion_lector")
                EXCEPT !.cambio = "recibido"]
      [] accion = "confirmar_cambio" ->
            \* Paso 9a (no está en el código): se reabren los capítulos afectados.
            Transitar([b0 EXCEPT !.av.cambioPropuesto = FALSE,
                                 !.ciclos = 0,
                                 !.cambio = "confirmado",
                                 !.gates = GatesSinEvaluar,
                                 !.juezAlDia = FALSE,
                                 !.cap = [c \in Caps |->
                                            IF c \in S THEN CapInicial ELSE b0.cap[c]]],
                      "regeneracion", "cambio_confirmado")
      [] accion = "rechazar_cambio" ->
            Transitar([b0 EXCEPT !.av.cambioPropuesto = FALSE, !.cambio = "rechazado"],
                      "publicada", "cambio_rechazado")
      [] accion = "reintentar" ->
            (LET destino == DestinoDeReintentar[b.detenidaDesde]
                 r == IF destino = "capitulos" THEN Reabrir(b0) ELSE b0
             IN Transitar(r, destino, "reintentar"))

-------------------------------------------------------------------------------
VARIABLES
    bd,        \* la base del proyecto
    bloqueo,   \* las columnas bloqueo_* de la fila del proyecto
    ej,        \* lo que cada ejecutor tiene en su ventana: se pierde al caer
    cota,      \* contadores de las cotas del modelo; no existen en el código
    fantasma   \* marcas para las invariantes 2 y 6; no existen en el código

vars == <<bd, bloqueo, ej, cota, fantasma>>

TieneBloqueo(e) == bloqueo.vigente /\ bloqueo.titular = e /\ ej[e].tok = "actual"

TitularVivo == \E e \in Ejecutores : bloqueo.titular = e /\ ej[e].tok = "actual"

\* Otro ejecutor tiene el bloqueo vigente: si `e` escribe ahora, trabajan los dos.
OtroTrabaja(e) == \E f \in Ejecutores \ {e} : TieneBloqueo(f)

\* Nadie lanza /generar ni /regenerar sobre un proyecto que espera a un humano.
HayTrabajo == bd.orden.hay \/ Decision(Derivaciones(bd)).tipo = "lanzar"

Init ==
    /\ \E pp, pf \in BOOLEAN : bd = BdInicial(pp, pf)
    /\ bloqueo = [titular |-> Nadie, vigente |-> FALSE]
    /\ ej = [e \in Ejecutores |-> EjInactivo]
    /\ cota = [caidas |-> 0, caducidades |-> 0, reintentos |-> 0,
               cambiosPlan |-> 0, notasFinal |-> 0, cambios |-> 0]
    /\ fantasma = [concurrente |-> FALSE, espurio |-> FALSE]

-------------------------------------------------------------------------------
(* Un ejecutor: la skill orquestar-novela (architecture.md §8).              *)

\* bloqueo.tomar_bloqueo: libre o caducado. Todo token anterior queda viejo.
\* Con AJ-4, la generación sube y la orden vigente se vuelve a sellar: las copias
\* que tengan los demás ejecutores quedan con el sello viejo.
Tomar(e) ==
    /\ ej[e].pc = "inactivo"
    /\ ~bloqueo.vigente
    /\ HayTrabajo
    /\ bloqueo' = [titular |-> e, vigente |-> TRUE]
    /\ LET resella == SelloConGeneracion /\ bd.orden.hay
       IN /\ bd' = IF resella THEN Resellar(bd) ELSE bd
          /\ ej' = [x \in Ejecutores |->
                      IF x = e
                      THEN [ej[e] EXCEPT !.pc = "listo", !.tok = "actual"]
                      ELSE [ej[x] EXCEPT
                              !.tok = IF ej[x].tok = "actual" THEN "viejo" ELSE ej[x].tok,
                              !.ord.sello = IF resella THEN FALSE ELSE ej[x].ord.sello]]
    /\ UNCHANGED <<cota, fantasma>>

\* persistencia.emitir_siguiente_orden, y el lanzamiento del subagente que indica:
\* una invocación es un intento (§3.2). Caer entre pedir y lanzar es lo mismo que
\* caer con el subagente lanzado y sin efectos todavía.
Pedir(e) ==
    /\ ej[e].pc = "listo"
    /\ IF ~TieneBloqueo(e)
       THEN /\ ej' = [ej EXCEPT ![e] = EjInactivo]
            /\ UNCHANGED bd
       ELSE IF bd.orden.hay
       THEN /\ ej' = [ej EXCEPT ![e] = [@ EXCEPT !.pc = "corriendo", !.ord = CopiaDe(bd.orden),
                                                !.texto = "no", !.escribio = FALSE]]
            /\ UNCHANGED bd
       ELSE LET r == Derivaciones(bd)
                d == Decision(r)
            IN IF d.tipo = "lanzar"
               THEN /\ IF r.estado = "verificacion_manuscrito" /\ GatesPorEvaluar(r)
                       THEN \E cob, lean \in BOOLEAN : bd' = Emitir(EvaluarGates(r, cob, lean), d)
                       ELSE bd' = Emitir(r, d)
                    /\ ej' = [ej EXCEPT ![e] = [@ EXCEPT !.pc = "corriendo",
                                                        !.ord = CopiaDe(bd'.orden),
                                                        !.texto = "no", !.escribio = FALSE]]
               ELSE /\ bd' = r
                    /\ ej' = [ej EXCEPT ![e].pc = "soltando"]
    /\ UNCHANGED <<bloqueo, cota, fantasma>>

\* /mcp/entrada: canjea el identificador de un solo uso. No mira el bloqueo:
\* MCP no transporta la identidad del llamante (architecture.md §7).
Canjear(e) ==
    /\ ej[e].pc = "corriendo"
    /\ ej[e].ord.agente \in AgentesDeEntrada
    /\ ej[e].texto = "no"
    /\ LET valido == bd.orden.hay /\ ej[e].ord.vigente
                     /\ (SelloConGeneracion => ej[e].ord.sello)
       IN IF valido /\ ~bd.orden.canjeado
          THEN /\ bd' = [bd EXCEPT !.orden.canjeado = TRUE]
               /\ ej' = [ej EXCEPT ![e].texto = "ok"]
               /\ fantasma' = [fantasma EXCEPT !.concurrente =
                                                   fantasma.concurrente \/ OtroTrabaja(e)]
          ELSE /\ ej' = [ej EXCEPT ![e].texto = "no_disponible"]
               /\ fantasma' = [fantasma EXCEPT !.espurio =
                                                   fantasma.espurio \/ (valido /\ TieneBloqueo(e))]
               /\ UNCHANGED bd
    /\ UNCHANGED <<bloqueo, cota>>

\* /mcp/escritura (B-16): la escritura se etiqueta con el capítulo de la orden
\* vigente. Sin C-1 solo comprueba que la orden vigente es de Bibliotecario.
EscribirBiblia(e) ==
    /\ ej[e].pc = "corriendo"
    /\ ej[e].ord.agente = "bibliotecario"
    /\ ~ej[e].escribio
    /\ ej' = [ej EXCEPT ![e].escribio = TRUE]
    /\ LET valido == IF SelloConGeneracion
                     THEN bd.orden.hay /\ ej[e].ord.vigente /\ ej[e].ord.sello
                     ELSE bd.orden.hay /\ bd.orden.agente = "bibliotecario"
           c == bd.orden.capitulo
       IN IF valido
          THEN /\ bd' = [bd EXCEPT !.lotes[c] = IF bd.lotes[c] < 2 THEN bd.lotes[c] + 1 ELSE 2]
               /\ fantasma' = [fantasma EXCEPT !.concurrente =
                                                   fantasma.concurrente \/ OtroTrabaja(e)]
          ELSE UNCHANGED <<bd, fantasma>>
    /\ UNCHANGED <<bloqueo, cota>>

Resultados(o) ==
    CASE o.agente = "extractor-hechos" -> {"acepta_con_hechos", "acepta_sin_hechos", "forma"}
      [] o.agente = "agente-contexto" /\ o.estado = "contexto" -> {"acepta", "contenido", "forma"}
      [] o.agente = "escritor" -> {"acepta", "contenido"}
      [] o.agente = "editor-estilo" -> {"acepta", "contenido", "contenido_veto", "forma"}
      [] o.agente = "juez-capitulo" -> {"acepta", "contenido", "forma"}
      [] o.agente = "juez-manuscrito" -> {"pasa", "no_pasa", "forma"}
      [] OTHER -> {"acepta", "forma"}

\* El subagente devuelve su salida. Qué salida es se elige al registrarla: entre
\* las dos acciones nada depende de ella.
Terminar(e) ==
    /\ ej[e].pc = "corriendo"
    /\ (ej[e].ord.agente \in AgentesDeEntrada) => (ej[e].texto # "no")
    /\ ej' = [ej EXCEPT ![e].pc = "con_resultado"]
    /\ UNCHANGED <<bd, bloqueo, cota, fantasma>>

\* Sin el texto no confiable, el Extractor o el Intérprete solo pueden fallar.
SalidasPosibles(x) ==
    IF x.ord.agente \in AgentesDeEntrada /\ x.texto # "ok" THEN {"forma"}
    ELSE Resultados(x.ord)

\* persistencia.registrar_resultado.
Registrar(e) ==
    /\ ej[e].pc = "con_resultado"
    /\ IF ~TieneBloqueo(e)
       THEN /\ ej' = [ej EXCEPT ![e] = EjInactivo]
            /\ UNCHANGED bd
       ELSE IF ~ej[e].ord.vigente \/ (SelloConGeneracion /\ ~ej[e].ord.sello)
       THEN /\ ej' = [ej EXCEPT ![e].pc = "listo", ![e].ord = OrdNula]
            /\ UNCHANGED bd
       ELSE /\ \E res \in SalidasPosibles(ej[e]),
               S \in (IF ej[e].ord.agente = "juez-manuscrito" THEN Afectables ELSE {{}}) :
                  bd' = AplicarDesenlace(bd, res, S)
            /\ ej' = [x \in Ejecutores |->
                        IF x = e
                        THEN [ej[e] EXCEPT !.pc = "listo", !.ord = OrdNula]
                        ELSE [ej[x] EXCEPT !.ord.vigente = FALSE]]
    /\ UNCHANGED <<bloqueo, cota, fantasma>>

\* bloqueo.soltar_bloqueo: suelta el propio, vigente o caducado.
Soltar(e) ==
    /\ ej[e].pc = "soltando"
    /\ bloqueo' = IF bloqueo.titular = e /\ ej[e].tok = "actual"
                  THEN [titular |-> Nadie, vigente |-> FALSE]
                  ELSE bloqueo
    /\ ej' = [ej EXCEPT ![e] = EjInactivo]
    /\ UNCHANGED <<bd, cota, fantasma>>

\* La sesión muere: pierde su ventana. La base y el bloqueo no cambian.
Caer(e) ==
    /\ cota.caidas < MaxCaidas
    /\ ej[e].pc # "inactivo"
    /\ ej' = [ej EXCEPT ![e] = EjInactivo]
    /\ cota' = [cota EXCEPT !.caidas = cota.caidas + 1]
    /\ UNCHANGED <<bd, bloqueo, fantasma>>

\* bloqueo.DURACION: caduca a los 30 minutos si nadie lo renueva.
CaducarTrasCaida ==
    /\ bloqueo.vigente
    /\ ~TitularVivo
    /\ bloqueo' = [bloqueo EXCEPT !.vigente = FALSE]
    /\ UNCHANGED <<bd, ej, cota, fantasma>>

\* Un titular vivo que no renueva a tiempo: un subagente de más de 30 minutos.
CaducarEnVida ==
    /\ bloqueo.vigente
    /\ TitularVivo
    /\ cota.caducidades < MaxCaducidades
    /\ bloqueo' = [bloqueo EXCEPT !.vigente = FALSE]
    /\ cota' = [cota EXCEPT !.caducidades = cota.caducidades + 1]
    /\ UNCHANGED <<bd, ej, fantasma>>

-------------------------------------------------------------------------------
(* El humano. No necesita el bloqueo (Q7).                                   *)

\* persistencia.decidir: una orden vigente se cierra como caducada.
Decidir(accion, S) ==
    /\ bd' = Derivaciones(Humana(bd, accion, S))
    /\ ej' = [x \in Ejecutores |-> [ej[x] EXCEPT !.ord.vigente = FALSE]]

SubirBrief ==
    /\ bd.estado = "intake"
    /\ ~bd.av.brief
    /\ \E libre \in BOOLEAN :
          bd' = [bd EXCEPT !.av.brief = TRUE, !.av.textoLibre = libre]
    /\ UNCHANGED <<bloqueo, ej, cota, fantasma>>

ConfirmarHechos ==
    /\ bd.estado = "intake"
    /\ bd.av.hechosPendientes
    /\ ~bd.orden.hay
    /\ bd' = [bd EXCEPT !.av.hechosPendientes = FALSE]
    /\ UNCHANGED <<bloqueo, ej, cota, fantasma>>

AprobarPlan ==
    /\ bd.estado = "aprobacion_plan"
    /\ Decidir("aprobar_plan", {})
    /\ UNCHANGED <<bloqueo, cota, fantasma>>

CambiosPlan ==
    /\ bd.estado = "aprobacion_plan"
    /\ cota.cambiosPlan < MaxCambiosPlan
    /\ Decidir("cambios_plan", {})
    /\ cota' = [cota EXCEPT !.cambiosPlan = cota.cambiosPlan + 1]
    /\ UNCHANGED <<bloqueo, fantasma>>

AprobarFinal ==
    /\ bd.estado = "aprobacion_final"
    /\ Decidir("aprobar_final", {})
    /\ UNCHANGED <<bloqueo, cota, fantasma>>

NotasFinal ==
    /\ bd.estado = "aprobacion_final"
    /\ cota.notasFinal < MaxNotasFinal
    /\ \E S \in Afectables : Decidir("notas_final", S)
    /\ cota' = [cota EXCEPT !.notasFinal = cota.notasFinal + 1]
    /\ UNCHANGED <<bloqueo, fantasma>>

PedirCambio ==
    /\ bd.estado = "publicada"
    /\ cota.cambios < MaxCambios
    /\ Decidir("pedir_cambio", {})
    /\ cota' = [cota EXCEPT !.cambios = cota.cambios + 1]
    /\ UNCHANGED <<bloqueo, fantasma>>

ConfirmarCambio ==
    /\ bd.estado = "cambio_solicitado"
    /\ bd.av.cambioPropuesto
    /\ \E S \in Afectables : Decidir("confirmar_cambio", S)
    /\ UNCHANGED <<bloqueo, cota, fantasma>>

RechazarCambio ==
    /\ bd.estado = "cambio_solicitado"
    /\ bd.av.cambioPropuesto
    /\ Decidir("rechazar_cambio", {})
    /\ UNCHANGED <<bloqueo, cota, fantasma>>

Reintentar ==
    /\ bd.estado = "detenida"
    /\ cota.reintentos < MaxReintentos
    /\ Decidir("reintentar", {})
    /\ cota' = [cota EXCEPT !.reintentos = cota.reintentos + 1]
    /\ UNCHANGED <<bloqueo, fantasma>>

\* Lo que el humano acaba haciendo en una espera (supuesto de la liveness, §3.4).
HumanoResponde ==
    \/ SubirBrief \/ ConfirmarHechos
    \/ AprobarPlan \/ CambiosPlan
    \/ AprobarFinal \/ NotasFinal
    \/ ConfirmarCambio \/ RechazarCambio

Humano == HumanoResponde \/ PedirCambio \/ Reintentar

-------------------------------------------------------------------------------
PasosEjecutor(e) ==
    \/ Tomar(e) \/ Pedir(e) \/ Canjear(e) \/ EscribirBiblia(e)
    \/ Terminar(e) \/ Registrar(e) \/ Soltar(e)

Next ==
    \/ \E e \in Ejecutores : PasosEjecutor(e) \/ Caer(e)
    \/ CaducarTrasCaida
    \/ CaducarEnVida
    \/ Humano

Fairness ==
    /\ \A e \in Ejecutores : WF_vars(PasosEjecutor(e))
    /\ WF_vars(CaducarTrasCaida)
    /\ WF_vars(HumanoResponde)

Spec == Init /\ [][Next]_vars /\ Fairness

\* Los dos ejecutores son intercambiables. Solo para las ejecuciones de seguridad:
\* TLC no admite simetría al comprobar liveness.
Simetria == Permutations(Ejecutores)

-------------------------------------------------------------------------------
(* Tipos y coherencia: maquina.incoherencias() y los CHECK de esquema.sql.   *)

TipoCap == [estado : EstadosCap, intentos : 0..TopeIntentos, terminado : BOOLEAN]
TipoVersion == [det : BOOLEAN, juez : BOOLEAN, bib : BOOLEAN,
                origen : {"bucle", "revision"}, enPub : BOOLEAN]

TypeOK ==
    /\ bd.estado \in Estados
    /\ bd.detenidaDesde \in Estados \cup {Ninguno}
    /\ bd.cap \in [Caps -> TipoCap]
    /\ bd.vig \in [Caps -> TipoVersion]
    /\ bd.orden.agente \in Agentes \cup {Ninguno}
    /\ bd.lotes \in [Caps -> 0..2]
    /\ bd.rev.pend \subseteq Caps
    /\ bd.cambio \in {Ninguno, "recibido", "propuesto", "confirmado", "rechazado",
                      "aplicado", "fallido"}
    /\ bloqueo.titular \in Ejecutores \cup {Nadie}
    /\ \A e \in Ejecutores :
          /\ ej[e].pc \in {"inactivo", "listo", "corriendo",
                           "con_resultado", "soltando"}
          /\ ej[e].tok \in {Ninguno, "actual", "viejo"}
          /\ (ej[e].tok = "actual") => (bloqueo.titular = e)

Coherencia ==
    /\ (bd.estado = "detenida") <=> (bd.detenidaDesde # Ninguno)
    /\ (bd.detenidaDesde # Ninguno) => (bd.detenidaDesde \in OrigenesDeDetenida)
    /\ \A c \in Caps : bd.cap[c].terminado => (bd.cap[c].estado = "aprobado")
    /\ bd.orden.hay => (bd.orden.estado = bd.estado)
    /\ \A e \in Ejecutores : ej[e].ord.vigente => bd.orden.hay
    /\ (bd.estado = "revision") => (bd.rev.pend # {})

-------------------------------------------------------------------------------
(* Las seis invariantes de architecture.md §3.4.                             *)

\* 1. Nunca se publica una versión con un capítulo que no ha pasado los
\*    validadores que le tocan, ni con gates evaluados sobre otras versiones.
ListoParaPublicar(b) ==
    /\ \A c \in Caps :
          /\ b.cap[c].estado = "aprobado"
          /\ b.cap[c].terminado
          /\ b.vig[c].det
          /\ b.vig[c].bib
          /\ (b.vig[c].origen = "bucle") => b.vig[c].juez
    /\ LET g == b.gates[b.ciclos] IN g.hay /\ g.alDia /\ g.cob /\ g.lean
    /\ b.juezAlDia

Inv1_PublicaVerificado ==
    [][Len(bd'.pubs) > Len(bd.pubs) => ListoParaPublicar(bd)]_vars

\* 2. La reanudación no duplica ni pierde: la biblia no recibe dos lotes para
\*    un capítulo, una caída no gasta un intento, y un capítulo terminado
\*    conserva lo que lo terminó.
Inv2_SinDuplicados == \A c \in Caps : bd.lotes[c] <= 1

Inv2_ReanudarSinCoste == ~fantasma.espurio

Inv2_NoPierde ==
    \A c \in Caps : bd.cap[c].terminado =>
        (bd.vig[c].det /\ (bd.vig[c].bib \/ c \in bd.rev.pend))

\* 3. Publicar la N+1 no modifica la N, y en `publicada` la vigente es la última.
Inv3_VersionAnterior ==
    [][/\ Len(bd'.pubs) >= Len(bd.pubs)
       /\ \A i \in 1..Len(bd.pubs) : bd'.pubs[i] = bd.pubs[i]]_vars

Inv3_PublicadaCoherente ==
    (bd.estado = "publicada") =>
        /\ Len(bd.pubs) > 0
        /\ \A c \in Caps :
              /\ bd.cap[c].estado = "aprobado"
              /\ bd.cap[c].terminado
              /\ bd.vig[c] = bd.pubs[Len(bd.pubs)][c]

\* 4. Los reintentos nunca superan el límite.
Inv4_Topes ==
    /\ bd.intentosPaso \in 0..(TopeIntentos - 1)
    /\ bd.ciclos \in 0..TopeCiclos
    /\ \A c \in Caps :
          bd.cap[c].intentos \in
              0..(IF bd.cap[c].estado = "revision_humana" THEN TopeIntentos
                  ELSE TopeIntentos - 1)
    /\ bd.orden.hay => (bd.orden.intento \in 1..TopeIntentos)

\* 5. Una parada humana activa no se sale sin acción humana.
EnParada(b) ==
    \/ b.estado \in ParadasHumanas
    \/ (b.estado = "cambio_solicitado" /\ b.av.cambioPropuesto)

Inv5_ParadaHumana ==
    [][(EnParada(bd) /\ bd'.estado # bd.estado) => Humano]_vars

\* 6. Dos ejecutores nunca trabajan a la vez: un solo token vale, y nadie escribe
\*    en el proyecto mientras otro tiene el bloqueo vigente. Lo que escriba un
\*    ejecutor solo, con el bloqueo ya caducado, no cuenta aquí: que no sobreviva
\*    al relevo lo vigila la invariante 2.
Inv6_UnSoloEjecutor ==
    /\ \A e1, e2 \in Ejecutores : (TieneBloqueo(e1) /\ TieneBloqueo(e2)) => e1 = e2
    /\ ~fantasma.concurrente

-------------------------------------------------------------------------------
(* Liveness (§3.4): con equidad débil en el sistema y en las respuestas del  *)
(* humano, y con un número finito de caídas y caducidades.                   *)

Terminal == bd.estado \in {"publicada", "detenida"}

Termina == [](~Terminal => <>Terminal)

CambioTermina ==
    [](bd.cambio = "confirmado" => <>(bd.cambio \in {"aplicado", "fallido"}))

===============================================================================
