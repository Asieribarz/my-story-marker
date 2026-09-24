"""CLI de la sesión contra el backend (specs/plan-agentes.md A-1). La skill `orquestar-novela`
habla con la API solo a través de este script.

    uv run --project . --no-sync --quiet python .claude/harness/msm.py <orden> [argumentos]

Imprime siempre una línea JSON. Códigos de salida: 0 bien; 2 uso incorrecto; 3 el backend
respondió con error; 4 falta estado local (bloqueo, orden o salida); 5 no hay backend.

Órdenes:

    crear [--parada-plan] [--parada-final] [--etiqueta TEXTO] [--grupo novelas|evals]
    proyectos
    estado <proyecto>
    bloqueo tomar|renovar|soltar <proyecto> [--tipo sesion|worker]
    siguiente <proyecto>
    acuse <proyecto> [--orden N]
    brief <proyecto> --respuestas FICHERO|- [--texto-libre FICHERO]
    brief <proyecto> --desde-brief evals/eN-<nombre>/input/brief.json
    hechos <proyecto>
    confirmar <proyecto> [--si 1,2] [--no 3]
    reintentar <proyecto> [--notas TEXTO]

`<proyecto>` es el identificador entero o un prefijo único de al menos 4 caracteres; se
resuelve al entero antes de nada, así que el prompt, el estado local y el hook siempre ven el
identificador completo. `proyectos` lista los proyectos con su etiqueta y su título.

`brief` lee el texto libre del fichero y lo envía sin imprimirlo (E-3); con `--desde-brief`
toma de un brief de evaluación solo `entrada.respuestas` y `entrada.texto_libre_fichero`, y
nunca su oráculo (`evaluacion`). `siguiente` renueva
el bloqueo (o lo retoma si caducó), guarda la orden y devuelve en `prompt` el texto exacto
para el subagente. `acuse` enseña lo que registró el hook `SubagentStop`, que es la única vía
de registro: este script nunca envía a `/resultado`. Espera al hook hasta `--espera` segundos,
porque el subagente puede entregar (`SubagentHandback`) antes de que el hook termine.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import comun  # noqa: E402


class Salida(Exception):
    def __init__(self, codigo: int, datos: dict[str, Any]):
        self.codigo = codigo
        self.datos = datos


def _imprimir(datos: Any) -> None:
    sys.stdout.buffer.write((json.dumps(datos, ensure_ascii=False) + "\n").encode("utf-8"))


def _token(proyecto: str) -> str:
    token = comun.leer_token(proyecto)
    if token is None:
        raise Salida(4, {"error": "no hay bloqueo tomado desde esta máquina: `bloqueo tomar`"})
    return token


# ─── Órdenes ─────────────────────────────────────────────────────────────────


def crear(args: argparse.Namespace) -> Any:
    cuerpo: dict[str, Any] = {"parada_plan": args.parada_plan, "parada_final": args.parada_final}
    if args.etiqueta:
        cuerpo["etiqueta"] = args.etiqueta
    cuerpo["grupo"] = args.grupo
    estado = comun.peticion("POST", "/proyectos", cuerpo)
    return {"proyecto": estado["identificador"], "estado": estado["estado"], "grupo": args.grupo}


def proyectos(args: argparse.Namespace) -> Any:
    """Los proyectos del backend, del más reciente al más antiguo, con su nombre legible."""
    filas = comun.peticion("GET", "/proyectos")["proyectos"]
    return {
        "proyectos": [
            {
                k: fila.get(k)
                for k in ("identificador", "grupo", "etiqueta", "titulo", "estado", "creado")
            }
            for fila in filas
        ]
    }


# Un prefijo más corto casi siempre sería ambiguo, y leído en un log no dice qué proyecto es.
PREFIJO_MINIMO = 4


def resolver_proyecto(valor: str) -> str:
    """El identificador entero a partir de él mismo o de un prefijo único de al menos
    `PREFIJO_MINIMO` caracteres (`/generar 1a62`). Ambiguo o sin coincidencias, falla con la
    lista de candidatos."""
    if comun.es_identificador(valor):
        return valor
    if not (PREFIJO_MINIMO <= len(valor) < 32 and all(c in "0123456789abcdef" for c in valor)):
        raise comun.ErrorHarness(
            f"identificador de proyecto no válido: {valor!r} (el entero, o un prefijo de al "
            f"menos {PREFIJO_MINIMO} caracteres hexadecimales en minúscula)"
        )
    filas = comun.peticion("GET", "/proyectos")["proyectos"]
    candidatos = [f for f in filas if str(f["identificador"]).startswith(valor)]
    if len(candidatos) == 1:
        return str(candidatos[0]["identificador"])
    raise Salida(
        2,
        {
            "error": f"el prefijo {valor!r} "
            + ("no es de ningún proyecto" if not candidatos else "es de varios proyectos"),
            "candidatos": [
                {k: f.get(k) for k in ("identificador", "etiqueta", "titulo", "estado")}
                for f in candidatos
            ],
        },
    )


def estado(args: argparse.Namespace) -> Any:
    datos = comun.peticion("GET", f"/proyectos/{args.proyecto}/estado")
    vigente = datos.get("orden_vigente")
    return {
        "proyecto": datos["identificador"],
        "estado": datos["estado"],
        "detenida_desde": datos.get("detenida_desde"),
        "capitulos": {str(c["numero"]): c["estado"] for c in datos.get("capitulos", [])},
        "orden_vigente": None
        if vigente is None
        else {k: vigente.get(k) for k in ("id", "agente", "intento", "capitulo", "registro")},
        "bloqueo": datos.get("bloqueo"),
    }


def bloqueo(args: argparse.Namespace) -> Any:
    ruta = f"/proyectos/{args.proyecto}/bloqueo"
    if args.accion == "soltar":
        token = comun.leer_token(args.proyecto)
        if token is not None:
            comun.peticion("DELETE", ruta, token=token)
        comun.borrar_bloqueo(args.proyecto)
        return {"bloqueo": "suelto"}
    if args.accion == "renovar":
        datos = comun.peticion("POST", ruta, token=_token(args.proyecto))
    else:
        guardado = comun.leer_token(args.proyecto)
        datos = None
        if guardado is not None:
            # Una sesión reanudada con su propio bloqueo aún vigente lo renueva.
            try:
                datos = comun.peticion("POST", ruta, token=guardado)
            except comun.ErrorBackend:
                comun.borrar_bloqueo(args.proyecto)
        if datos is None:
            datos = comun.peticion("POST", ruta, {"tipo": args.tipo})
    comun.guardar_bloqueo(args.proyecto, datos)
    return {"bloqueo": datos["tipo"], "caduca": datos["caduca"]}


def _renovar_o_retomar(proyecto: str) -> str:
    """Renueva el bloqueo propio; si caducó mientras la sesión esperaba, lo vuelve a tomar.
    Si lo tiene otro ejecutor, el error del backend sube tal cual."""
    ruta = f"/proyectos/{proyecto}/bloqueo"
    try:
        datos = comun.peticion("POST", ruta, token=_token(proyecto))
    except comun.ErrorBackend as error:
        cuerpo = error.cuerpo if isinstance(error.cuerpo, dict) else {}
        if cuerpo.get("codigo") != "bloqueo_requerido":
            raise
        tipo = comun.leer_tipo_bloqueo(proyecto) or "sesion"
        datos = comun.peticion("POST", ruta, {"tipo": tipo})
    comun.guardar_bloqueo(proyecto, datos)
    return str(datos["token"])


def siguiente(args: argparse.Namespace) -> Any:
    token = _renovar_o_retomar(args.proyecto)
    # La orden del juez de manuscrito corre antes los gates de Lean (hasta 2 × 600 s, M-27).
    decision = comun.peticion(
        "POST", f"/proyectos/{args.proyecto}/siguiente", token=token, espera=1500.0
    )
    if decision.get("decision") != "orden":
        return decision
    orden = decision["orden"]
    comun.guardar_orden(args.proyecto, orden)
    return {
        "decision": "orden",
        "orden": orden["id"],
        "agente": orden["agente"],
        "intento": orden["intento"],
        "capitulo": orden.get("capitulo"),
        "prompt": comun.prompt_para_subagente(args.proyecto, orden),
    }


# El hook `SubagentStop` tiene 180 s de tope (settings.json); `acuse` espera lo mismo.
ESPERA_POR_DEFECTO = 180.0
ESPERA_ENTRE_LECTURAS = 1.0


def acuse(args: argparse.Namespace) -> Any:
    """Lo que registró el hook para la orden. La skill no registra nada (P-2)."""
    orden = comun.leer_orden(args.proyecto, args.orden)
    if orden is None:
        raise Salida(4, {"error": "no hay orden guardada: pide antes `siguiente`"})
    numero = int(orden["id"])
    limite = time.monotonic() + max(0.0, args.espera)
    guardado = comun.leer_acuse(args.proyecto, numero)
    while guardado is None and time.monotonic() < limite:
        time.sleep(ESPERA_ENTRE_LECTURAS)
        guardado = comun.leer_acuse(args.proyecto, numero)
    if guardado is None:
        raise Salida(
            4,
            {
                "error": f"el hook no dejó acuse de la orden {numero}: el subagente no terminó, "
                "o no se lanzó con el `prompt` que dio `siguiente`",
            },
        )
    if not guardado.get("registrado"):
        raise Salida(3, {"error": "el hook no pudo registrar", "acuse": guardado})
    return comun.resumen_registro(guardado["respuesta"])


# Claves de un brief de evaluación que no son respuestas del comprador: `evaluacion` es el
# oráculo de lo que debe saltar. Si llegaran como respuestas, la evaluación dejaría de valer.
_CLAVES_DE_EVALUACION = frozenset({"evaluacion", "cabecera"})


def _ruta_de_brief(valor: str, base: Path) -> Path:
    ruta = Path(valor)
    if ruta.is_absolute() or ruta.exists():
        return ruta
    for candidata in (base / ruta, comun.RAIZ_REPO / ruta):
        if candidata.exists():
            return candidata
    return ruta


def _leer_respuestas(args: argparse.Namespace) -> tuple[Any, str | None]:
    """Las respuestas y la ruta del texto libre, de `--desde-brief` o de `--respuestas`."""
    if args.desde_brief:
        fichero = Path(args.desde_brief)
        brief_eval = json.loads(fichero.read_text(encoding="utf-8"))
        entrada = brief_eval.get("entrada") if isinstance(brief_eval, dict) else None
        if not isinstance(entrada, dict) or not isinstance(entrada.get("respuestas"), dict):
            raise Salida(2, {"error": "el brief no trae `entrada.respuestas`"})
        texto = entrada.get("texto_libre_fichero")
        ruta = str(_ruta_de_brief(texto, fichero.parent)) if isinstance(texto, str) else None
        return entrada["respuestas"], args.texto_libre or ruta
    if not args.respuestas:
        raise Salida(2, {"error": "indica --respuestas FICHERO|- o --desde-brief FICHERO"})
    crudo = (
        sys.stdin.buffer.read().decode("utf-8")
        if args.respuestas == "-"
        else Path(args.respuestas).read_text(encoding="utf-8")
    )
    try:
        respuestas = json.loads(crudo)
    except json.JSONDecodeError as error:
        raise Salida(2, {"error": f"las respuestas no son JSON: {error}"}) from None
    if isinstance(respuestas, dict) and _CLAVES_DE_EVALUACION & respuestas.keys():
        raise Salida(
            2,
            {
                "error": "esto es un brief de evaluación entero, no las respuestas del comprador: "
                "usa --desde-brief, que envía solo `entrada.respuestas`",
            },
        )
    return respuestas, args.texto_libre


def brief(args: argparse.Namespace) -> Any:
    respuestas, ruta_texto = _leer_respuestas(args)
    cuerpo: dict[str, Any] = {"respuestas": respuestas}
    if ruta_texto:
        texto = Path(ruta_texto).read_text(encoding="utf-8").strip()
        if texto:
            cuerpo["texto_libre"] = texto
    guardado = comun.peticion("POST", f"/proyectos/{args.proyecto}/brief", cuerpo)
    # El texto libre no se imprime nunca: solo si se envió.
    return {"brief": "guardado", **guardado}


def hechos(args: argparse.Namespace) -> Any:
    return comun.peticion("GET", f"/proyectos/{args.proyecto}/hechos")


def confirmar(args: argparse.Namespace) -> Any:
    def ids(valor: str | None) -> list[int]:
        return [int(x) for x in (valor or "").split(",") if x.strip()]

    decisiones = [{"hecho": h, "confirmado": True} for h in ids(args.si)]
    decisiones += [{"hecho": h, "confirmado": False} for h in ids(args.no)]
    if not decisiones:
        raise Salida(2, {"error": "indica al menos un hecho con --si o --no"})
    return comun.peticion(
        "POST", f"/proyectos/{args.proyecto}/hechos/confirmacion", {"decisiones": decisiones}
    )


def reintentar(args: argparse.Namespace) -> Any:
    cuerpo = {"notas": args.notas} if args.notas else None
    datos = comun.peticion("POST", f"/proyectos/{args.proyecto}/reintentar", cuerpo)
    return {"proyecto": datos["identificador"], "estado": datos["estado"]}


# ─── Entrada ─────────────────────────────────────────────────────────────────


def _analizador() -> argparse.ArgumentParser:
    raiz = argparse.ArgumentParser(prog="msm.py", description=__doc__.split("\n\n")[0])
    sub = raiz.add_subparsers(dest="orden", required=True)

    p = sub.add_parser("crear")
    p.add_argument("--parada-plan", action="store_true")
    p.add_argument("--parada-final", action="store_true")
    p.add_argument("--etiqueta")
    p.add_argument("--grupo", choices=comun.GRUPOS, default="novelas")
    p.set_defaults(funcion=crear)

    p = sub.add_parser("proyectos")
    p.set_defaults(funcion=proyectos)

    for nombre, funcion in (("estado", estado), ("siguiente", siguiente), ("hechos", hechos)):
        p = sub.add_parser(nombre)
        p.add_argument("proyecto")
        p.set_defaults(funcion=funcion)

    p = sub.add_parser("bloqueo")
    p.add_argument("accion", choices=("tomar", "renovar", "soltar"))
    p.add_argument("proyecto")
    p.add_argument("--tipo", choices=("sesion", "worker"), default="sesion")
    p.set_defaults(funcion=bloqueo)

    p = sub.add_parser("acuse")
    p.add_argument("proyecto")
    p.add_argument("--orden", type=int)
    p.add_argument("--espera", type=float, default=ESPERA_POR_DEFECTO)
    p.set_defaults(funcion=acuse)

    p = sub.add_parser("brief")
    p.add_argument("proyecto")
    p.add_argument("--respuestas")
    p.add_argument("--desde-brief")
    p.add_argument("--texto-libre")
    p.set_defaults(funcion=brief)

    p = sub.add_parser("confirmar")
    p.add_argument("proyecto")
    p.add_argument("--si")
    p.add_argument("--no")
    p.set_defaults(funcion=confirmar)

    p = sub.add_parser("reintentar")
    p.add_argument("proyecto")
    p.add_argument("--notas")
    p.set_defaults(funcion=reintentar)
    return raiz


def main(argv: list[str] | None = None) -> int:
    args = _analizador().parse_args(argv)
    try:
        if getattr(args, "proyecto", None):
            args.proyecto = resolver_proyecto(args.proyecto)
        _imprimir(args.funcion(args))
        return 0
    except Salida as salida:
        _imprimir(salida.datos)
        return salida.codigo
    except comun.ErrorHarness as error:
        _imprimir({"error": str(error)})
        return 2
    except comun.ErrorBackend as error:
        _imprimir(
            {
                "error": "el backend respondió con error",
                "http": error.estado,
                **(error.cuerpo if isinstance(error.cuerpo, dict) else {"detalle": error.cuerpo}),
            }
        )
        return 3
    except comun.SinBackend as error:
        _imprimir({"error": str(error)})
        return 5


if __name__ == "__main__":
    sys.exit(main())
