/-!
# Los tipos del fichero de cronología

Es el contrato con el backend (`specs/spec-backend-2.md` §4.2, `specs/plan-formal.md`
§3.1): por cada novela, el backend escribe un `.lean` que importa `Cronologia` y define
`novela : Novela`. Todo son ids numéricos, con su correspondencia en un JSON aparte, y
listas ordenadas por id. No hay ningún texto libre.
-/

namespace Cronologia

/-- La franja de un día de la historia. -/
inductive Franja where
  | manana
  | tarde
  | noche
  deriving DecidableEq, Repr

/-- El orden de las franjas dentro de un día. -/
def Franja.orden : Franja → Nat
  | .manana => 0
  | .tarde => 1
  | .noche => 2

/-- Cuándo ocurre un evento, en una de las dos escalas de B-6.

- `recuerdo desde hasta`: un recuerdo del comprador, como intervalo cerrado de días de
  calendario contados como `date.toordinal()` de Python (el 1 es el 0001-01-01). Una fecha
  parcial es el intervalo entero: `2023-07` va del 1 al 31 de julio. Un periodo sin fecha
  segura va con el intervalo más ancho que se pueda afirmar.
- `historia dia franja`: la acción de la novela, en el día `D<dia>`.

Toda la historia es posterior a todos los recuerdos. -/
inductive Momento where
  | recuerdo (desde hasta : Nat)
  | historia (dia : Nat) (franja : Franja)
  deriving DecidableEq, Repr

structure Localizacion where
  id : Nat
  /-- La localización que la contiene; `none` en una `macro`. -/
  padre : Option Nat
  deriving DecidableEq, Repr

structure Personaje where
  id : Nat
  /-- Intervalo cerrado de días en que pudo nacer; `none` si no se sabe. -/
  nacimiento : Option (Nat × Nat)
  deriving DecidableEq, Repr

structure Evento where
  id : Nat
  momento : Momento
  lugar : Nat
  presentes : List Nat
  /-- El personaje al que el evento excluye de ahí en adelante, por muerte o partida. -/
  excluye : Option Nat
  deriving DecidableEq, Repr

structure Novela where
  localizaciones : List Localizacion
  personajes : List Personaje
  eventos : List Evento
  deriving Repr

end Cronologia
