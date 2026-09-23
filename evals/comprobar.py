"""Comprueba los briefs de evaluación contra el validador del backend.

Uso, desde la raíz del repositorio:  uv run python -m evals.comprobar

Todos los datos de evals/ son ficticios. Por cada brief de evals/briefs/:
1. La cabecera lo declara ficticio, y `entrada` da un cuerpo válido de POST /brief. El texto
   libre no se lee, porque es no confiable: solo se mira que su fichero exista y no esté vacío.
2. `respuestas.personalizacion` encaja en el modelo de definitions.md §9 y `depurar` no le
   quita nada: las respuestas no traen datos excluidos.
3. Su contexto de referencia da exactamente los hallazgos de
   `evaluacion.validador_contexto`, validado con la `fecha_referencia` de la cabecera.
4. El contexto conserva el destinatario y los hechos de la entrevista tal como los dio el
   comprador. Solo cambia el `lugar` de los eventos, que pasa a ser el id de una localización.

pytest, mypy y ruff no miran este fichero: solo miran backend/.
"""

import io
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.contexto.modelos import Personalizacion
from backend.contexto.validacion import validar
from backend.intake.datos_excluidos import depurar
from backend.intake.router import Brief

RAIZ = Path(__file__).resolve().parents[1]
BRIEFS = RAIZ / "evals" / "briefs"
CLAVES_DEL_COMPRADOR = (
    "destinatario",
    "segundo_destinatario",
    "ocasion",
    "relacion",
    "edad_lector",
    "vetos",
    "dedicatoria",
)


def _leer(ruta: Path) -> Any:
    return json.loads(ruta.read_text(encoding="utf-8"))


def _sin_lugar(hecho: dict[str, Any]) -> dict[str, Any]:
    return {clave: valor for clave, valor in hecho.items() if clave != "lugar"}


def comprobar(ruta: Path) -> list[str]:
    brief = _leer(ruta)
    cabecera, entrada, evaluacion = brief["cabecera"], brief["entrada"], brief["evaluacion"]
    errores: list[str] = []

    if cabecera.get("ficticio") is not True:
        errores.append("la cabecera no lo declara ficticio")
    if set(entrada) != {"respuestas", "texto_libre_fichero"}:
        errores.append("`entrada` lleva solo `respuestas` y `texto_libre_fichero`")
    fichero = entrada.get("texto_libre_fichero")
    if fichero is not None:
        texto_libre = RAIZ / fichero
        if not texto_libre.is_file() or texto_libre.stat().st_size == 0:
            errores.append(f"falta el texto libre {fichero}, o está vacío")
    cuerpo = {
        "respuestas": entrada.get("respuestas"),
        "texto_libre": None if fichero is None else "(no se lee)",
    }
    try:
        Brief.model_validate(cuerpo)
    except ValidationError as error:
        errores.append(f"`entrada` no es un cuerpo de POST /brief: {error.error_count()} errores")

    personalizacion = entrada["respuestas"]["personalizacion"]
    try:
        Personalizacion.model_validate(personalizacion)
    except ValidationError as error:
        errores += [
            f"respuestas fuera de §9: {'.'.join(map(str, e['loc']))}: {e['msg']}"
            for e in error.errors(include_url=False)
        ]
    _, descartes = depurar(entrada["respuestas"])
    errores += [f"depurar descartaría {d.campo} ({d.tipo})" for d in descartes]

    contexto = _leer(RAIZ / cabecera["contexto_referencia"])
    informe = validar(contexto, date.fromisoformat(cabecera["fecha_referencia"]))
    obtenidos = sorted((h.regla, h.localizacion) for h in informe.hallazgos)
    esperados = sorted(
        (h["regla"], h["localizacion"])
        for h in evaluacion["validador_contexto"]["hallazgos_esperados"]
    )
    if obtenidos != esperados:
        errores.append(f"hallazgos {obtenidos}; se esperaban {esperados}")
    if not esperados and not informe.valido:
        errores.append("el contexto de referencia no es válido")

    dado = contexto["novela"]["personalizacion"]
    errores += [
        f"el contexto cambia `{clave}` respecto al brief"
        for clave in CLAVES_DEL_COMPRADOR
        if dado.get(clave) != personalizacion.get(clave)
    ]
    if (dado.get("texto_libre") is None) != (fichero is None):
        errores.append("el brief y el contexto no coinciden en si hay texto libre")
    en_contexto = {h["id"]: h for h in dado["hechos"]}
    for hecho in personalizacion["hechos"]:
        suyo = en_contexto.get(hecho["id"])
        if suyo is None or _sin_lugar(suyo) != _sin_lugar(hecho):
            errores.append(f"el contexto cambia o pierde el hecho {hecho['id']}")
    return errores


def main() -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    fallidos = 0
    for ruta in sorted(BRIEFS.glob("*.json")):
        errores = comprobar(ruta)
        fallidos += bool(errores)
        print(f"{'FALLA' if errores else 'ok'}  {ruta.name}")
        for error in errores:
            print(f"      · {error}")
    return 1 if fallidos else 0


if __name__ == "__main__":
    sys.exit(main())
