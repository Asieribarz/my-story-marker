import Cronologia

/-!
# Casos de prueba de las tres invariantes (V-27)

Cada caso negativo infringe una sola invariante, y el teorema dice que la comprobación da
`false` y con qué violación exacta. Los casos de control rozan la regla sin infringirla:
un lugar dentro de otro, el mismo día en franjas distintas, intervalos que se solapan.

Si una regla deja de detectar su caso, o empieza a disparar en uno de control, este
fichero deja de compilar: `lake build Pruebas`.

Datos ficticios. Los días son `date.toordinal()`: 738521 es el 2023-01-01.
-/

open Cronologia

namespace Pruebas

/-- El pueblo (1) contiene la casa (2), que contiene el desván (3); la playa (4) está aparte. -/
def lugares : List Localizacion :=
  [ { id := 1, padre := none },
    { id := 2, padre := some 1 },
    { id := 3, padre := some 2 },
    { id := 4, padre := none } ]

/-- 1 nació en enero de 2023; 2 no tiene fecha de nacimiento. -/
def gente : List Personaje :=
  [ { id := 1, nacimiento := some (738521, 738551) },
    { id := 2, nacimiento := none } ]

def novelaCon (eventos : List Evento) : Novela :=
  { localizaciones := lugares, personajes := gente, eventos := eventos }

def ev (id : Nat) (m : Momento) (lugar : Nat) (presentes : List Nat)
    (excluye : Option Nat := none) : Evento :=
  { id := id, momento := m, lugar := lugar, presentes := presentes, excluye := excluye }

/-! ## 1. Lugar único -/

/-- El mismo personaje en la casa y en la playa, el día 1 por la mañana. -/
def dosSitios : Novela :=
  novelaCon [ ev 1 (.historia 1 .manana) 2 [1, 2], ev 2 (.historia 1 .manana) 4 [1] ]

theorem dosSitios_falla : lugarUnico dosSitios = false := by decide
theorem dosSitios_choque :
    choquesLugar dosSitios = [{ personaje := 1, primero := 1, segundo := 2 }] := by decide

/-- Control: el desván está dentro del pueblo; no es estar en dos sitios. -/
def anidados : Novela :=
  novelaCon [ ev 1 (.historia 1 .manana) 3 [1], ev 2 (.historia 1 .manana) 1 [1] ]

theorem anidados_pasa : lugarUnico anidados = true := by decide

/-- Control: mismo día, franjas distintas. -/
def otraFranja : Novela :=
  novelaCon [ ev 1 (.historia 1 .manana) 2 [1], ev 2 (.historia 1 .tarde) 4 [1] ]

theorem otraFranja_pasa : lugarUnico otraFranja = true := by decide

/-- Control: dos recuerdos del mismo día en sitios distintos no son el mismo momento. -/
def recuerdosDelDia : Novela :=
  novelaCon [ ev 1 (.recuerdo 738900 738900) 2 [1], ev 2 (.recuerdo 738900 738900) 4 [1] ]

theorem recuerdosDelDia_pasa : lugarUnico recuerdosDelDia = true := by decide

/-- Control: en el mismo momento y en sitios distintos, pero sin nadie en común. -/
def sinComun : Novela :=
  novelaCon [ ev 1 (.historia 2 .noche) 2 [1], ev 2 (.historia 2 .noche) 4 [2] ]

theorem sinComun_pasa : lugarUnico sinComun = true := by decide

/-! ## 2. Nadie reaparece tras un evento que lo excluye -/

/-- E3: la partida de 2 es un recuerdo, y 2 vuelve a salir en la historia. -/
def partidaYVuelta : Novela :=
  novelaCon [ ev 1 (.recuerdo 738700 738730) 4 [1, 2] (some 2), ev 2 (.historia 3 .tarde) 2 [2] ]

theorem partidaYVuelta_falla : sinReaparicion partidaYVuelta = false := by decide
theorem partidaYVuelta_reaparicion :
    reapariciones partidaYVuelta = [{ personaje := 2, excluye := 1, evento := 2 }] := by decide

/-- La muerte de 2 el día 2 por la tarde, y 2 aparece esa misma noche. -/
def muerteYNoche : Novela :=
  novelaCon [ ev 1 (.historia 2 .tarde) 2 [1, 2] (some 2), ev 2 (.historia 2 .noche) 2 [2] ]

theorem muerteYNoche_falla : sinReaparicion muerteYNoche = false := by decide

/-- Control: aparece en un recuerdo, anterior a la historia, y en la misma franja de su
muerte, que no es posterior. -/
def antesYDurante : Novela :=
  novelaCon [ ev 1 (.historia 2 .tarde) 2 [1, 2] (some 2),
              ev 2 (.recuerdo 738900 738930) 4 [2],
              ev 3 (.historia 2 .tarde) 1 [2] ]

theorem antesYDurante_pasa : sinReaparicion antesYDurante = true := by decide

/-- Control: dos recuerdos que se solapan no tienen orden seguro. -/
def solapados : Novela :=
  novelaCon [ ev 1 (.recuerdo 738700 738760) 4 [2] (some 2), ev 2 (.recuerdo 738750 738790) 4 [2] ]

theorem solapados_pasa : sinReaparicion solapados = true := by decide

/-! ## 3. Nadie aparece en un evento fechado antes de nacer -/

/-- 1 nació en enero de 2023 y aparece en un recuerdo del verano de 2022. -/
def antesDeNacerCaso : Novela :=
  novelaCon [ ev 1 (.recuerdo 738337 738367) 4 [1, 2] ]

theorem antesDeNacer_falla : nacidoAntes antesDeNacerCaso = false := by decide
theorem antesDeNacer_violacion :
    antesDeNacer antesDeNacerCaso = [{ personaje := 1, evento := 1 }] := by decide

/-- Control: un recuerdo de «enero de 2023» se solapa con el mes de su nacimiento. -/
def mesDeNacer : Novela :=
  novelaCon [ ev 1 (.recuerdo 738521 738551) 2 [1] ]

theorem mesDeNacer_pasa : nacidoAntes mesDeNacer = true := by decide

/-- Control: sin fecha de nacimiento no se compara, y la historia no tiene fecha. -/
def sinFecha : Novela :=
  novelaCon [ ev 1 (.recuerdo 700000 700010) 4 [2], ev 2 (.historia 1 .manana) 4 [1] ]

theorem sinFecha_pasa : nacidoAntes sinFecha = true := by decide

/-! ## Cada caso negativo infringe solo su invariante -/

theorem dosSitios_solo_lugar :
    sinReaparicion dosSitios = true ∧ nacidoAntes dosSitios = true := by decide
theorem partidaYVuelta_solo_exclusion :
    lugarUnico partidaYVuelta = true ∧ nacidoAntes partidaYVuelta = true := by decide
theorem antesDeNacer_solo_nacimiento :
    lugarUnico antesDeNacerCaso = true ∧ sinReaparicion antesDeNacerCaso = true := by decide

/-! ## El informe -/

/-- info: {"lugar_unico":[{"personaje":1,"eventos":[1,2]}],"exclusion":[],"nacimiento":[]} -/
#guard_msgs in
#eval violaciones dosSitios

/-- info: {"lugar_unico":[],"exclusion":[{"personaje":2,"excluye":1,"evento":2}],"nacimiento":[]} -/
#guard_msgs in
#eval violaciones partidaYVuelta

/-- info: {"lugar_unico":[],"exclusion":[],"nacimiento":[{"personaje":1,"evento":1}]} -/
#guard_msgs in
#eval violaciones antesDeNacerCaso

/-- info: {"lugar_unico":[],"exclusion":[],"nacimiento":[]} -/
#guard_msgs in
#eval violaciones anidados

end Pruebas
