"""V-10 (RNF-11): toda dependencia declarada está en la tabla de architecture.md §7."""

import re
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def dependencias_declaradas() -> list[str]:
    datos = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    especificaciones = list(datos["project"].get("dependencies", []))
    for grupo in datos.get("dependency-groups", {}).values():
        especificaciones.extend(grupo)
    nombres = []
    for especificacion in especificaciones:
        coincidencia = re.match(r"[A-Za-z0-9._-]+", especificacion)
        assert coincidencia, especificacion
        nombres.append(coincidencia.group(0).lower())
    return nombres


def tabla_de_tecnologia() -> str:
    texto = (RAIZ / "docs" / "architecture.md").read_text(encoding="utf-8")
    inicio = texto.index("## 7. Tecnología")
    fin = texto.index("\n## 8.", inicio)
    return texto[inicio:fin].lower()


def no_acordadas(nombres: list[str], tabla: str) -> list[str]:
    # Palabra completa: un nombre corto como «py» no debe darse por acordado dentro de otro.
    return [
        nombre
        for nombre in nombres
        if not re.search(rf"(?<![\w-]){re.escape(nombre)}(?![\w-])", tabla)
    ]


def test_toda_dependencia_esta_acordada_en_la_tabla() -> None:
    assert no_acordadas(dependencias_declaradas(), tabla_de_tecnologia()) == []


def test_una_dependencia_ausente_de_la_tabla_se_detecta() -> None:
    assert no_acordadas(["sqlalchemy"], tabla_de_tecnologia()) == ["sqlalchemy"]
    assert no_acordadas(["py", "tik"], tabla_de_tecnologia()) == ["py", "tik"]
