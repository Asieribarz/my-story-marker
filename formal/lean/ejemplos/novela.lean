-- Ejemplo del fichero que genera el backend por novela (specs/plan-formal.md §3.1).
-- Datos ficticios. La correspondencia de ids va en un JSON aparte: aquí no hay texto.
import Cronologia
open Cronologia

def novela : Novela :=
  { localizaciones :=
      [ { id := 1, padre := none },
        { id := 2, padre := some 1 },
        { id := 3, padre := some 2 },
        { id := 4, padre := none },
        { id := 5, padre := some 4 } ],
    personajes :=
      [ { id := 1, nacimiento := some (736431, 736431) },
        { id := 2, nacimiento := some (725007, 725372) },
        { id := 3, nacimiento := none } ],
    eventos :=
      [ { id := 1, momento := .recuerdo 738702 738732, lugar := 5, presentes := [1, 2],
          excluye := none },
        { id := 2, momento := .recuerdo 738886 738886, lugar := 2, presentes := [1, 2],
          excluye := none },
        { id := 3, momento := .historia 1 .manana, lugar := 3, presentes := [1, 3],
          excluye := none },
        { id := 4, momento := .historia 1 .manana, lugar := 1, presentes := [1],
          excluye := none },
        { id := 5, momento := .historia 1 .tarde, lugar := 4, presentes := [1, 3],
          excluye := none },
        { id := 6, momento := .historia 2 .noche, lugar := 5, presentes := [1, 3],
          excluye := some 3 },
        { id := 7, momento := .historia 3 .manana, lugar := 2, presentes := [1, 2],
          excluye := none } ] }

theorem lugar_unico : lugarUnico novela = true := by decide
theorem sin_reaparicion : sinReaparicion novela = true := by decide
theorem nacido_antes : nacidoAntes novela = true := by decide

#eval violaciones novela
