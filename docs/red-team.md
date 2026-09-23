# red-team.md — Registro de red team

> Propósito: dejar escrito cada ataque deliberado contra el sistema —qué se lanzó, qué defensa tenía que pararlo y qué pasó de verdad— **en el momento en que se lanza** ([plan-entrega.md](../specs/plan-entrega.md) §3). Las fuentes previstas son el brief E2 de inyección (H1) y las peticiones adversariales de V-29 (H6), que se recogen en H7.
>
> Un ataque que pasa es un resultado, no un hueco en el registro, y se escribe igual. Si obliga a cambiar algo, el cambio tiene también su entrada en [iteraciones.md](iteraciones.md), y cada una cita a la otra.

---

## Formato

Una entrada por **ataque**, no por sesión ni por brief. E2 lleva dos ataques, la inyección en el texto libre y el intento de sacar datos de otro proyecto, así que son dos entradas.

```markdown
### R-NN · AAAA-MM-DD · Hn · El ataque en una línea

- **Ataque:** vector y punto de entrada (texto libre, petición de cambio, salida de un agente…), el fichero que lo contiene y cómo se lanzó. Lo bastante para repetirlo.
- **Resultado esperado:** la defensa que tenía que pararlo, con su referencia (`RF-n`, `V-n`, §).
- **Resultado obtenido:** qué pasó de verdad, con su evidencia: la fila de `auditoria`, el informe o la salida del agente.
- **Defensa que lo paró:** la que actuó de verdad, que puede no ser la esperada. Si no lo paró nada: **ninguna**.
- **Qué se cambió y dónde:** qué cambió porque el ataque pasó, o porque lo paró otra defensa en vez de la esperada. Con la entrada de iteraciones.md que lo recoge.
```

| Campo | Regla |
|---|---|
| `R-NN` | Correlativo y sin huecos. No se reutiliza |
| Fecha | La del día en que se lanzó el ataque |
| Hito | El de [plan-entrega.md](../specs/plan-entrega.md) §3 en el que se lanzó |
| Qué se cambió y dónde | Un «nada» declarado vale; un campo vacío, no |

- Se añade al final, y una entrada no se reescribe. Si se repite un ataque después de un cambio, la repetición es una entrada nueva que cita la anterior.
- **El texto del ataque no se copia aquí.** Se cita el fichero del brief o de la petición donde vive y, si hace falta, se resume. `docs/` lo leen los agentes de desarrollo, y una inyección copiada al pie de la letra sería una inyección contra ellos.
- Si el ataque buscaba datos (de otro proyecto, secretos), la evidencia dice si salieron y de qué tipo eran, **nunca el valor**, igual que el audit log.
- Todo dato de persona es ficticio (AGENTS.md).

---

## Entradas

Todavía ninguna. Las primeras llegan con el brief E2 (H1).
