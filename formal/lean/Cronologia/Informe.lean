import Cronologia.Invariantes

/-!
# El informe que lee el backend

`#eval violaciones novela` imprime una sola línea JSON con los ids de los eventos
implicados en cada violación (`specs/plan-formal.md` §3.3). Las claves son fijas y las
listas salen en el orden de `novela.eventos`, así que la misma novela da la misma línea.
-/

namespace Cronologia

private def lista (xs : List String) : String := "[" ++ ",".intercalate xs ++ "]"

def ChoqueLugar.json (c : ChoqueLugar) : String :=
  "{\"personaje\":" ++ toString c.personaje ++
    ",\"eventos\":[" ++ toString c.primero ++ "," ++ toString c.segundo ++ "]}"

def Reaparicion.json (r : Reaparicion) : String :=
  "{\"personaje\":" ++ toString r.personaje ++
    ",\"excluye\":" ++ toString r.excluye ++
    ",\"evento\":" ++ toString r.evento ++ "}"

def AntesDeNacer.json (a : AntesDeNacer) : String :=
  "{\"personaje\":" ++ toString a.personaje ++ ",\"evento\":" ++ toString a.evento ++ "}"

def informe (n : Novela) : String :=
  "{\"lugar_unico\":" ++ lista ((choquesLugar n).map ChoqueLugar.json) ++
    ",\"exclusion\":" ++ lista ((reapariciones n).map Reaparicion.json) ++
    ",\"nacimiento\":" ++ lista ((antesDeNacer n).map AntesDeNacer.json) ++ "}"

/-- Imprime el informe de la novela en una línea. -/
def violaciones (n : Novela) : IO Unit := IO.println (informe n)

end Cronologia
