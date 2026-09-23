"""Lo que comparten `msm.py` y los dos hooks: configuración, estado local, HTTP y la forma de
los contratos con el backend (specs/plan-agentes.md §4).

Solo biblioteca estándar (A-1): corre con el Python del proyecto pero no importa `backend/`.
Si un contrato del backend cambia, cambia este módulo y nada más:

- `cuerpo_de_resultado` es P-1: cómo se convierte lo que devolvió un subagente en el cuerpo
  de `POST /resultado`.
- `prompt_para_subagente` es A-4: la cabecera `orden: <proyecto>:<n>` y la entrada de la orden.

El estado local vive en `.claude/estado/`, ignorado por git: el token del bloqueo (que el hook
necesita para registrar desde otro proceso), las órdenes pedidas, las salidas y los acuses de
registro que deja el hook (A-5), la auditoría (P-5) y el uso (P-6).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RAIZ_REPO = Path(__file__).resolve().parents[2]
DIR_AGENTES = RAIZ_REPO / ".claude" / "agents"

# Los nombres de `backend/shared/tipos.py` (Agente). `test_definiciones.py` comprueba que
# coinciden, y que hay un fichero por nombre en `.claude/agents/`.
AGENTES = frozenset(
    {
        "agente-contexto",
        "extractor-hechos",
        "planificador",
        "escaletista",
        "escritor",
        "editor-estilo",
        "juez-capitulo",
        "bibliotecario",
        "juez-manuscrito",
        "revisor",
        "exportador",
        "interprete-cambios",
    }
)
# P-1, propuesta B-7 §4.1.3: estos devuelven Markdown; el resto, un bloque JSON.
AGENTES_MARKDOWN = frozenset({"escritor", "editor-estilo", "revisor"})

# P-1 y P-6 (decisiones-backend.md §4.1): el contrato final de `/resultado` es
# `{orden, salida_cruda, metadatos?}` y llega con el bloque 2 del backend. Hasta entonces,
# `resultado`: el cuerpo `{orden, resultado}` con la salida ya estructurada aquí.
CONTRATO_RESULTADO = os.environ.get("MSM_CONTRATO_RESULTADO", "resultado")

_IDENTIFICADOR = re.compile(r"[0-9a-f]{32}")
# AJ-4: el sello es opaco, `<proyecto>:<orden>:<generación>`. Solo se lee el proyecto.
_CABECERA = re.compile(r"^\s*orden:\s*(([0-9a-f]{32}):[^\s]+)\s*$")
_BLOQUE_JSON = re.compile(r"```json[ \t]*\r?\n(.*?)\r?\n[ \t]*```", re.DOTALL)
_TITULO = re.compile(r"^#[ \t]+(.+?)\s*$")


# ─── Configuración ───────────────────────────────────────────────────────────


def url_backend() -> str:
    return os.environ.get("MSM_BACKEND", "http://127.0.0.1:8000").rstrip("/")


def raiz_proyectos(cwd: Path | None = None) -> Path:
    """La misma raíz que `backend/shared/rutas.py`: `MSM_PROYECTOS` o `proyectos/` del repo."""
    valor = os.environ.get("MSM_PROYECTOS")
    if not valor:
        return RAIZ_REPO / "proyectos"
    ruta = Path(valor)
    return ruta if ruta.is_absolute() else (cwd or Path.cwd()) / ruta


def dir_estado() -> Path:
    base = Path(os.environ.get("MSM_ESTADO") or RAIZ_REPO / ".claude" / "estado")
    base.mkdir(parents=True, exist_ok=True)
    ignorar = base / ".gitignore"
    if not ignorar.exists():
        ignorar.write_text("*\n", encoding="utf-8")
    return base


def ahora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def validar_proyecto(proyecto: str) -> str:
    if not _IDENTIFICADOR.fullmatch(proyecto):
        raise ErrorHarness(f"identificador de proyecto no válido: {proyecto!r}")
    return proyecto


# ─── Errores ─────────────────────────────────────────────────────────────────


class ErrorHarness(Exception):
    """Un fallo del lado de la sesión: estado local ausente o incoherente."""


class ErrorBackend(Exception):
    """El backend respondió con error: `{codigo, requisito, detalle}` (TC-11)."""

    def __init__(self, estado: int, cuerpo: Any):
        self.estado = estado
        self.cuerpo = cuerpo
        super().__init__(f"HTTP {estado}: {json.dumps(cuerpo, ensure_ascii=False)[:600]}")


class SinBackend(Exception):
    """No hay backend escuchando en `url_backend()`."""


# ─── HTTP ────────────────────────────────────────────────────────────────────


def peticion(
    metodo: str,
    ruta: str,
    cuerpo: Any = None,
    token: str | None = None,
    espera: float = 120.0,
) -> Any:
    datos = None if cuerpo is None else json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
    cabeceras = {"Accept": "application/json"}
    if datos is not None:
        cabeceras["Content-Type"] = "application/json"
    if token:
        cabeceras["X-Bloqueo"] = token
    req = urllib.request.Request(url_backend() + ruta, data=datos, headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=espera) as respuesta:
            texto = respuesta.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        texto = error.read().decode("utf-8", errors="replace")
        try:
            detalle: Any = json.loads(texto)
        except json.JSONDecodeError:
            detalle = texto
        raise ErrorBackend(error.code, detalle) from None
    except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
        raise SinBackend(
            f"no hay backend en {url_backend()} ({error}); arráncalo con "
            "`uv run uvicorn backend.app:app`"
        ) from None
    return json.loads(texto) if texto.strip() else None


# ─── Estado local por proyecto ───────────────────────────────────────────────


def _dir_proyecto(proyecto: str) -> Path:
    carpeta = dir_estado() / validar_proyecto(proyecto)
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _escribir_json(ruta: Path, datos: Any) -> None:
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    temporal.replace(ruta)


def _leer_json(ruta: Path) -> Any:
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def guardar_bloqueo(proyecto: str, bloqueo: dict[str, Any]) -> None:
    _escribir_json(_dir_proyecto(proyecto) / "bloqueo.json", bloqueo)


def leer_token(proyecto: str) -> str | None:
    bloqueo = _leer_json(_dir_proyecto(proyecto) / "bloqueo.json")
    return None if bloqueo is None else str(bloqueo["token"])


def leer_tipo_bloqueo(proyecto: str) -> str | None:
    bloqueo = _leer_json(_dir_proyecto(proyecto) / "bloqueo.json")
    return None if bloqueo is None else str(bloqueo.get("tipo") or "") or None


def borrar_bloqueo(proyecto: str) -> None:
    (_dir_proyecto(proyecto) / "bloqueo.json").unlink(missing_ok=True)


def _clave_de_sello(sello: str) -> str:
    return hashlib.sha256(sello.encode("utf-8")).hexdigest()[:24]


def guardar_orden(proyecto: str, orden: dict[str, Any]) -> None:
    carpeta = _dir_proyecto(proyecto)
    numero = int(orden["id"])
    _escribir_json(carpeta / f"orden-{numero}.json", orden)
    _escribir_json(carpeta / "ultima-orden.json", {"id": numero})
    _escribir_json(
        carpeta / f"sello-{_clave_de_sello(sello_de(proyecto, orden))}.json", {"id": numero}
    )


def orden_de_sello(proyecto: str, sello: str) -> int | None:
    """El id de la orden que se pidió con ese sello, si la pidió esta máquina."""
    datos = _leer_json(_dir_proyecto(proyecto) / f"sello-{_clave_de_sello(sello)}.json")
    return None if datos is None else int(datos["id"])


def leer_orden(proyecto: str, orden: int | None = None) -> dict[str, Any] | None:
    carpeta = _dir_proyecto(proyecto)
    if orden is None:
        ultima = _leer_json(carpeta / "ultima-orden.json")
        if ultima is None:
            return None
        orden = int(ultima["id"])
    datos = _leer_json(carpeta / f"orden-{orden}.json")
    return None if datos is None else dict(datos)


def guardar_salida(proyecto: str, orden: int, agente: str, texto: str) -> None:
    carpeta = _dir_proyecto(proyecto)
    (carpeta / f"salida-{orden}.md").write_text(texto, encoding="utf-8")
    _escribir_json(carpeta / f"salida-{orden}.json", {"agente": agente, "guardada": ahora()})


def leer_salida(proyecto: str, orden: int) -> str | None:
    ruta = _dir_proyecto(proyecto) / f"salida-{orden}.md"
    return ruta.read_text(encoding="utf-8") if ruta.exists() else None


def guardar_acuse(proyecto: str, orden: int, acuse: dict[str, Any]) -> None:
    _escribir_json(_dir_proyecto(proyecto) / f"acuse-{orden}.json", {**acuse, "momento": ahora()})


def leer_acuse(proyecto: str, orden: int) -> dict[str, Any] | None:
    datos = _leer_json(_dir_proyecto(proyecto) / f"acuse-{orden}.json")
    return None if datos is None else dict(datos)


def anotar(fichero: str, registro: dict[str, Any]) -> None:
    """Una línea JSON en `auditoria.jsonl`, `uso.jsonl` o `errores.jsonl`."""
    linea = json.dumps({"momento": ahora(), **registro}, ensure_ascii=False)
    with (dir_estado() / fichero).open("a", encoding="utf-8") as salida:
        salida.write(linea + "\n")


# ─── Contratos: la orden hacia el subagente y su resultado hacia el backend ──


@dataclass(frozen=True)
class Cabecera:
    proyecto: str
    sello: str

    @property
    def orden(self) -> int | None:
        """El id de la orden: el que se guardó con este sello; si no, el segundo segmento
        mientras el backend no mande sello propio (hoy el sello es `<proyecto>:<id>`)."""
        guardada = orden_de_sello(self.proyecto, self.sello)
        if guardada is not None:
            return guardada
        partes = self.sello.split(":")
        return int(partes[1]) if len(partes) > 1 and partes[1].isdigit() else None


def sello_de(proyecto: str, orden: dict[str, Any]) -> str:
    """AJ-4: el sello de `/siguiente`, tal cual. Sin él, `<proyecto>:<id>`."""
    sello = orden.get("sello")
    return str(sello) if sello else f"{validar_proyecto(proyecto)}:{int(orden['id'])}"


def leer_cabecera(texto: str | None) -> Cabecera | None:
    """A-4: la cabecera es la primera línea no vacía del prompt del subagente."""
    for linea in (texto or "").splitlines():
        if linea.strip():
            encontrada = _CABECERA.match(linea)
            return None if encontrada is None else Cabecera(encontrada[2], encontrada[1])
    return None


def prompt_para_subagente(proyecto: str, orden: dict[str, Any]) -> str:
    """Lo que la skill pasa tal cual al subagente: la cabecera y la entrada de la orden."""
    entrada = {
        "proyecto": proyecto,
        "agente": orden["agente"],
        "intento": orden["intento"],
        "capitulo": orden.get("capitulo"),
        "entrada": orden.get("entrada", {}),
    }
    return (
        f"orden: {sello_de(proyecto, orden)}\n\n"
        "Esta es tu orden. Trabaja según tus instrucciones y devuelve solo la salida que "
        "piden, empezando por la línea de la cabecera de arriba.\n\n"
        f"```json\n{json.dumps(entrada, ensure_ascii=False, indent=1)}\n```\n"
    )


def _sin_cabecera(texto: str) -> str:
    lineas = texto.strip().splitlines()
    if lineas and _CABECERA.match(lineas[0]):
        lineas = lineas[1:]
    return "\n".join(lineas).strip()


def metadatos(uso: dict[str, Any], version_prompt: str | None) -> dict[str, Any]:
    """P-6: los `metadatos` de `/resultado`, todos opcionales, con los nombres del backend."""
    tokens = uso.get("tokens") or {}
    datos = {
        "modelo": uso.get("modelo"),
        "tokens_entrada": tokens.get("input_tokens"),
        "tokens_salida": tokens.get("output_tokens"),
        "tokens_cache_creacion": tokens.get("cache_creation_input_tokens"),
        "tokens_cache_lectura": tokens.get("cache_read_input_tokens"),
        "duracion_ms": uso.get("duracion_ms"),
        "version_prompt": version_prompt,
    }
    return {clave: valor for clave, valor in datos.items() if valor is not None}


def cuerpo_de_resultado(
    orden: int,
    agente: str,
    salida: str,
    meta: dict[str, Any] | None = None,
    sello: str | None = None,
) -> dict[str, Any]:
    """P-1. Con el contrato final, la salida va sin tocar y el backend la extrae y valida;
    `orden` es entonces el **sello** que llevaba el prompt, no el id (AJ-4, §4.1.7).

    Con el de hoy (`{orden, resultado}`), se estructura aquí:

    - Escritor, Editor y Revisor: `{titulo, texto}` desde `# título` y el cuerpo.
    - El resto: el último bloque ```json de la salida, ya parseado.

    Una salida que no encaja se envía igualmente, como texto: el backend la valida, la
    rechaza y cuenta el intento (RF-77a). Aquí no se decide si una salida vale.
    """
    if CONTRATO_RESULTADO == "salida_cruda":
        if not sello:
            raise ErrorHarness("el contrato final de /resultado exige el sello de la orden")
        final: dict[str, Any] = {"orden": sello, "salida_cruda": salida}
        if meta:
            final["metadatos"] = meta
        return final
    cuerpo = _sin_cabecera(salida)
    if agente in AGENTES_MARKDOWN:
        lineas = cuerpo.splitlines()
        titulo = _TITULO.match(lineas[0]) if lineas else None
        if titulo is None:
            return {"orden": orden, "resultado": cuerpo}
        return {
            "orden": orden,
            "resultado": {"titulo": titulo[1], "texto": "\n".join(lineas[1:]).strip()},
        }
    bloques = _BLOQUE_JSON.findall(cuerpo)
    if bloques:
        try:
            return {"orden": orden, "resultado": json.loads(bloques[-1])}
        except json.JSONDecodeError:
            pass
    return {"orden": orden, "resultado": cuerpo}


def resumen_registro(respuesta: dict[str, Any], limite: int = 4000) -> dict[str, Any]:
    """Lo que la skill necesita ver de un registro, con el informe acotado."""
    detalle = json.dumps(respuesta.get("detalle", {}), ensure_ascii=False)
    return {
        "orden": respuesta.get("orden"),
        "agente": respuesta.get("agente"),
        "desenlace": respuesta.get("desenlace"),
        "tipo": respuesta.get("tipo"),
        "estado": respuesta.get("estado"),
        "capitulo": respuesta.get("capitulo"),
        "estado_capitulo": respuesta.get("estado_capitulo"),
        "repetido": respuesta.get("repetido"),
        "detalle": detalle if len(detalle) <= limite else detalle[:limite] + "…(recortado)",
    }
