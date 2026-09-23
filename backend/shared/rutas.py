"""Disposición del directorio de un proyecto (spec1.md §5.3).

Único sitio de backend/ donde se construyen rutas de datos (V-24). Toda ruta sale de un
identificador de proyecto validado, así que ningún código puede apuntar a un proyecto
distinto del que la petición identifica, ni escaparse del directorio de proyectos.
"""

import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

VARIABLE_RAIZ = "MSM_PROYECTOS"
RAIZ_POR_DEFECTO = Path(__file__).resolve().parents[2] / "proyectos"
_IDENTIFICADOR = re.compile(r"[0-9a-f]{32}")
_CAMBIO = re.compile(r"[0-9]{1,9}")


class IdentificadorInvalido(ValueError):
    pass


def raiz_de_proyectos() -> Path:
    valor = os.environ.get(VARIABLE_RAIZ)
    return Path(valor) if valor else RAIZ_POR_DEFECTO


def nuevo_identificador() -> str:
    return uuid.uuid4().hex


def _clave_capitulo(numero: int, version: int, intento: int) -> tuple[str, str]:
    if not (1 <= numero <= 10 and version >= 1 and 1 <= intento <= 3):
        raise ValueError(f"capítulo {numero}, versión {version}, intento {intento} fuera de rango")
    return f"cap-{numero:02d}", f"v{version}-intento{intento}"


@dataclass(frozen=True)
class DisposicionProyecto:
    identificador: str
    raiz: Path

    @classmethod
    def de(cls, identificador: str, raiz_proyectos: Path | None = None) -> "DisposicionProyecto":
        if not _IDENTIFICADOR.fullmatch(identificador):
            raise IdentificadorInvalido(f"identificador de proyecto no válido: {identificador!r}")
        base = raiz_proyectos if raiz_proyectos is not None else raiz_de_proyectos()
        return cls(identificador, base / identificador)

    @property
    def base(self) -> Path:
        return self.raiz / "proyecto.sqlite"

    @property
    def capitulos(self) -> Path:
        return self.raiz / "capitulos"

    @property
    def prompts(self) -> Path:
        return self.raiz / "prompts"

    @property
    def export(self) -> Path:
        return self.raiz / "export"

    @property
    def verificacion(self) -> Path:
        return self.raiz / "verificacion"

    @property
    def brief(self) -> Path:
        """Texto no confiable del comprador (RF-14): solo se entrega por /mcp/entrada."""
        return self.raiz / "brief"

    @property
    def cambios(self) -> Path:
        """Peticiones del lector, no confiables (RF-120)."""
        return self.raiz / "cambios"

    @property
    def texto_libre(self) -> Path:
        return self.brief / "texto_libre.txt"

    def peticion(self, cambio: int) -> Path:
        if not _CAMBIO.fullmatch(str(cambio)):
            raise ValueError(f"identificador de cambio no válido: {cambio!r}")
        return self.cambios / f"peticion-{cambio}.txt"

    def capitulo(self, numero: int, version: int, intento: int) -> Path:
        carpeta, nombre = _clave_capitulo(numero, version, intento)
        return self.capitulos / carpeta / f"{nombre}.md"

    def borrador(self, numero: int, version: int, intento: int) -> Path:
        """La salida del Escritor tal cual (§4.1.5); `capitulo()` es el texto que edita el
        Editor."""
        carpeta, nombre = _clave_capitulo(numero, version, intento)
        return self.capitulos / carpeta / f"{nombre}.borrador.md"

    def prompt(self, numero: int, version: int, intento: int) -> Path:
        """El prompt entero, para auditoría (RF-58)."""
        carpeta, nombre = _clave_capitulo(numero, version, intento)
        return self.prompts / carpeta / f"{nombre}.prompt.md"

    def prompt_parte(self, numero: int, version: int, intento: int, parte: int) -> Path:
        """§4.1.4: la parte `parte` (desde 1) del prompt, que es lo que lee el Escritor."""
        if parte < 1:
            raise ValueError(f"parte de prompt no válida: {parte}")
        carpeta, nombre = _clave_capitulo(numero, version, intento)
        return self.prompts / carpeta / f"{nombre}.prompt.parte-{parte}.md"

    def desglose(self, numero: int, version: int, intento: int) -> Path:
        """Desglose por bloque del ensamblado (RF-59b), junto a su prompt."""
        carpeta, nombre = _clave_capitulo(numero, version, intento)
        return self.prompts / carpeta / f"{nombre}.desglose.json"

    def pasada(self, numero: int) -> Path:
        """AJ-3: los ficheros de los gates de una pasada de verificación de manuscrito."""
        if numero < 1:
            raise ValueError(f"pasada no válida: {numero}")
        return self.verificacion / f"pasada-{numero}"

    def version_novela(self, numero: int) -> Path:
        if numero < 1:
            raise ValueError(f"versión de novela no válida: {numero}")
        return self.export / f"v{numero}"

    def relativa(self, ruta: Path) -> str:
        """Ruta guardada en la base: relativa al proyecto, con barras de POSIX (RNF-08)."""
        return ruta.relative_to(self.raiz).as_posix()

    def absoluta(self, relativa: str) -> Path:
        ruta = (self.raiz / relativa).resolve()
        if not ruta.is_relative_to(self.raiz.resolve()):
            raise ValueError(f"la ruta {relativa!r} sale del directorio del proyecto")
        return ruta

    def apartada(self) -> "DisposicionProyecto":
        """El mismo proyecto apartado para borrarlo (RF-09a): un directorio hermano cuyo nombre
        no es un identificador, así que nada lo abre por su id. Único en cada llamada."""
        nombre = f".borrando-{self.identificador}-{uuid.uuid4().hex}"
        return DisposicionProyecto(self.identificador, self.raiz.with_name(nombre))

    def crear_directorios(self) -> None:
        carpetas = (
            self.capitulos,
            self.prompts,
            self.export,
            self.verificacion,
            self.brief,
            self.cambios,
        )
        for carpeta in carpetas:
            carpeta.mkdir(parents=True, exist_ok=True)
