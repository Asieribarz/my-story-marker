"""Genera una novela coherente de tamaño dado para la prueba de tamaño de `decide`.

specs/spec-backend-2.md §4.2: «con muchos eventos, `decide` puede agotar la recursión».
La novela generada no infringe ninguna invariante, que es el caso más caro: `decide` tiene
que recorrer todos los pares sin encontrar nada. Tiene la forma del fichero que escribe el
backend (specs/plan-formal.md §3.1), con eventos que rozan las reglas: dos eventos en cada
franja, en lugares anidados y con gente en común; una partida en un recuerdo y una muerte al
final de la historia.

Solo usa la librería estándar y es determinista: la misma llamada da el mismo fichero.

    python scripts/generar_tamano.py 80        # escribe tamano/Tamano80.lean
"""

import random
import sys
from pathlib import Path

FRANJAS = ("manana", "tarde", "noche")
BASE = Path(__file__).resolve().parents[1]


def localizaciones() -> list[tuple[int, int | None]]:
    """5 macro, cada una con 3 meso y cada meso con 2 micro: 50 localizaciones."""
    filas: list[tuple[int, int | None]] = [(i, None) for i in range(1, 6)]
    siguiente = 6
    for macro in range(1, 6):
        for _ in range(3):
            meso = siguiente
            filas.append((meso, macro))
            siguiente += 1
            for _ in range(2):
                filas.append((siguiente, meso))
                siguiente += 1
    return filas


def novela(eventos_historia: int, semilla: int = 7) -> str:
    azar = random.Random(semilla)
    lugares = localizaciones()
    micros = [i for i, padre in lugares if padre is not None and padre > 5]
    padre_de = dict(lugares)
    personajes = list(range(1, 13))
    # Nacimientos entre 1950 y 2015 (ordinales de Python); el 12 sin fecha.
    nacimiento = {p: azar.randint(711858, 735599) for p in personajes[:-1]}
    partido, muerto = 11, 10
    lineas_eventos: list[str] = []
    ident = 1

    def evento(momento: str, lugar: int, presentes: list[int], excluye: int | None) -> None:
        nonlocal ident
        exc = "none" if excluye is None else f"some {excluye}"
        lineas_eventos.append(
            f"        {{ id := {ident}, momento := {momento}, lugar := {lugar}, "
            f"presentes := {sorted(presentes)}, excluye := {exc} }}"
        )
        ident += 1

    # 20 recuerdos en 2024, después de todos los nacimientos. El último es la partida de 11.
    for k in range(20):
        dia = 738886 + 10 * k
        vivos = [p for p in personajes if p != partido] if k < 19 else [partido]
        presentes = azar.sample(vivos, k=min(3, len(vivos)))
        excluye = partido if k == 19 else None
        evento(f".recuerdo {dia} {dia + 5}", azar.choice(micros), presentes, excluye)

    # La historia: dos eventos por franja, el segundo en el lugar que contiene al primero.
    en_historia = [p for p in personajes if p != partido]
    for i in range(eventos_historia // 2):
        dia, franja = i // 3 + 1, FRANJAS[i % 3]
        momento = f".historia {dia} .{franja}"
        ultimo = i == eventos_historia // 2 - 1
        vivos = en_historia if ultimo else [p for p in en_historia if p != muerto]
        micro = azar.choice(micros)
        comunes = azar.sample(vivos, k=2)
        evento(momento, micro, comunes, muerto if ultimo else None)
        evento(momento, padre_de[micro] or micro, comunes + azar.sample(
            [p for p in vivos if p not in comunes], k=1), None)

    filas_lugares = ",\n".join(
        f"        {{ id := {i}, padre := {'none' if p is None else f'some {p}'} }}"
        for i, p in lugares
    )
    filas_personajes = ",\n".join(
        f"        {{ id := {p}, nacimiento := "
        f"{f'some ({nacimiento[p]}, {nacimiento[p]})' if p in nacimiento else 'none'} }}"
        for p in personajes
    )
    return (
        "-- Prueba de tamaño generada por scripts/generar_tamano.py. Datos ficticios.\n"
        "import Cronologia\nopen Cronologia\n\n"
        "def novela : Novela :=\n"
        f"  {{ localizaciones :=\n      [\n{filas_lugares} ],\n"
        f"    personajes :=\n      [\n{filas_personajes} ],\n"
        f"    eventos :=\n      [\n{','.join(chr(10) + l for l in lineas_eventos)[1:]} ] }}\n\n"
        "theorem lugar_unico : lugarUnico novela = true := by decide\n"
        "theorem sin_reaparicion : sinReaparicion novela = true := by decide\n"
        "theorem nacido_antes : nacidoAntes novela = true := by decide\n\n"
        "#eval violaciones novela\n"
    )


def main() -> None:
    eventos = int(sys.argv[1])
    salida = BASE / "tamano" / f"Tamano{eventos}.lean"
    salida.parent.mkdir(exist_ok=True)
    salida.write_bytes(novela(eventos).encode("utf-8"))
    print(salida)


if __name__ == "__main__":
    main()
