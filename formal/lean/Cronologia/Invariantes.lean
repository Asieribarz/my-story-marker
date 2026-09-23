import Cronologia.Tipos

/-!
# Las tres invariantes de `architecture.md` §4.2

Cada invariante es una función que devuelve la lista de sus violaciones, y la comprobación
es que esa lista está vacía. Todo es recursión estructural sobre listas finitas, para que
`decide` pueda reducirlo.

Solo se compara cuando el orden es seguro (`decisiones-backend.md` §4.2): una fecha parcial
es un intervalo, y dos intervalos que se solapan no están ni antes ni después.
-/

namespace Cronologia

/-- `a` termina con seguridad antes de que empiece `b`. -/
def Momento.antesSeguro : Momento → Momento → Bool
  | .recuerdo _ hasta, .recuerdo desde _ => hasta < desde
  | .recuerdo _ _, .historia _ _ => true
  | .historia _ _, .recuerdo _ _ => false
  | .historia d₁ f₁, .historia d₂ f₂ => d₁ < d₂ || (d₁ == d₂ && f₁.orden < f₂.orden)

/-- `a` y `b` son con seguridad el mismo momento. Solo ocurre en la historia, con el mismo
día y la misma franja: dos recuerdos del mismo día pueden ser uno de mañana y otro de noche. -/
def Momento.mismoSeguro : Momento → Momento → Bool
  | .historia d₁ f₁, .historia d₂ f₂ => d₁ == d₂ && f₁.orden == f₂.orden
  | _, _ => false

/-- `List.flatMap`, sin depender de su nombre, que ha cambiado entre versiones de Lean. -/
def concatMap {α β : Type} (f : α → List β) : List α → List β
  | [] => []
  | x :: xs => f x ++ concatMap f xs

/-- El padre de la localización `id`, si está en la lista. -/
def padreDe (ls : List Localizacion) (id : Nat) : Option Nat :=
  match ls.find? (fun l => l.id == id) with
  | some l => l.padre
  | none => none

/-- `x` es `a` o está dentro de `a`, subiendo como mucho `n` padres. El combustible acota
la subida aunque la lista tuviera un ciclo. -/
def dentroDe (ls : List Localizacion) (a : Nat) : Nat → Nat → Bool
  | 0, _ => false
  | n + 1, x =>
    x == a ||
      (match padreDe ls x with
       | some p => dentroDe ls a n p
       | none => false)

/-- Dos lugares son compatibles si uno contiene al otro: estar en una casa y en el pueblo
que la contiene no es estar en dos sitios. -/
def compatibles (ls : List Localizacion) (a b : Nat) : Bool :=
  dentroDe ls a (ls.length + 1) b || dentroDe ls b (ls.length + 1) a

/-! ## 1. Un personaje no está en dos lugares en el mismo momento -/

/-- `personaje` está en los eventos `primero` y `segundo`, que son el mismo momento y
ocurren en lugares que no se contienen el uno al otro. -/
structure ChoqueLugar where
  personaje : Nat
  primero : Nat
  segundo : Nat
  deriving DecidableEq, Repr

def choquesLugar (n : Novela) : List ChoqueLugar :=
  concatMap (fun e₁ =>
    concatMap (fun e₂ =>
      if e₁.id < e₂.id && e₁.momento.mismoSeguro e₂.momento
          && !compatibles n.localizaciones e₁.lugar e₂.lugar then
        (e₁.presentes.filter (fun p => e₂.presentes.contains p)).map
          (fun p => { personaje := p, primero := e₁.id, segundo := e₂.id })
      else []) n.eventos) n.eventos

def lugarUnico (n : Novela) : Bool := (choquesLugar n).isEmpty

/-! ## 2. Nadie aparece después de un evento que lo excluye -/

/-- `personaje` aparece en `evento`, que es con seguridad posterior a `excluye`, el evento
de su muerte o su partida. -/
structure Reaparicion where
  personaje : Nat
  excluye : Nat
  evento : Nat
  deriving DecidableEq, Repr

def reapariciones (n : Novela) : List Reaparicion :=
  concatMap (fun e₁ =>
    match e₁.excluye with
    | none => []
    | some p =>
      (n.eventos.filter (fun e₂ =>
          e₂.presentes.contains p && e₁.momento.antesSeguro e₂.momento)).map
        (fun e₂ => { personaje := p, excluye := e₁.id, evento := e₂.id })) n.eventos

def sinReaparicion (n : Novela) : Bool := (reapariciones n).isEmpty

/-! ## 3. Nadie aparece en un evento fechado antes de nacer

Es la forma de la invariante de edad que decide TC-2: la v1 no compara edades explícitas.
Solo los recuerdos tienen fecha de calendario; la historia no se compara. -/

/-- El intervalo de nacimiento del personaje `id`, si se conoce. -/
def nacimientoDe (ps : List Personaje) (id : Nat) : Option (Nat × Nat) :=
  match ps.find? (fun p => p.id == id) with
  | some p => p.nacimiento
  | none => none

/-- `personaje` está en `evento`, un recuerdo que termina antes del primer día en que pudo
nacer. -/
structure AntesDeNacer where
  personaje : Nat
  evento : Nat
  deriving DecidableEq, Repr

def antesDeNacer (n : Novela) : List AntesDeNacer :=
  concatMap (fun e =>
    match e.momento with
    | .historia _ _ => []
    | .recuerdo _ hasta =>
      (e.presentes.filter (fun p =>
          match nacimientoDe n.personajes p with
          | some (desde, _) => hasta < desde
          | none => false)).map
        (fun p => { personaje := p, evento := e.id })) n.eventos

def nacidoAntes (n : Novela) : Bool := (antesDeNacer n).isEmpty

end Cronologia
