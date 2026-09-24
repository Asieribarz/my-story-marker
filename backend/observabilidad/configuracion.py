"""Las claves de Langfuse: del entorno o, si no están, del `.env` de la raíz del repositorio.

Sin las dos claves no hay configuración y nada se envía: las pruebas y quien clone el
repositorio sin cuenta no necesitan nada. `MSM_LANGFUSE=0` lo apaga aunque haya claves.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from backend.shared.rutas import FICHERO_ENV

VARIABLE_INTERRUPTOR = "MSM_LANGFUSE"
URL_POR_DEFECTO = "https://cloud.langfuse.com"
# El valor de ejemplo de `.env.example`: copiado tal cual, no es una clave.
MARCADOR = "TU_CLAVE_AQUI"


@dataclass(frozen=True)
class Configuracion:
    clave_publica: str
    clave_secreta: str
    url: str

    def __repr__(self) -> str:
        # La clave secreta no sale nunca en un log ni en una traza de error.
        return f"Configuracion(clave_publica={self.clave_publica!r}, url={self.url!r})"


def leer_env(fichero: Path) -> dict[str, str]:
    """`CLAVE=valor` por línea; ignora comentarios, líneas vacías y comillas envolventes."""
    if not fichero.is_file():
        return {}
    valores: dict[str, str] = {}
    for linea in fichero.read_text(encoding="utf-8-sig").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        clave = clave.strip().removeprefix("export ").strip()
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        valores[clave] = valor
    return valores


def de_entorno(
    entorno: Mapping[str, str] | None = None, fichero: Path = FICHERO_ENV
) -> Configuracion | None:
    entorno = os.environ if entorno is None else entorno
    if entorno.get(VARIABLE_INTERRUPTOR) == "0":
        return None
    valores = {**leer_env(fichero), **{k: v for k, v in entorno.items() if v}}
    publica = valores.get("LANGFUSE_PUBLIC_KEY")
    secreta = valores.get("LANGFUSE_SECRET_KEY")
    if not publica or not secreta or MARCADOR in publica or MARCADOR in secreta:
        return None
    url = valores.get("LANGFUSE_BASE_URL") or valores.get("LANGFUSE_HOST") or URL_POR_DEFECTO
    return Configuracion(publica, secreta, url.rstrip("/"))
