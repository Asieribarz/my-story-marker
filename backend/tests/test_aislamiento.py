"""V-24 (RNF-09): toda conexión y toda ruta de backend/ se derivan de shared/.

Análisis estático sobre el código de backend/, pruebas excluidas:
- Solo `shared/db.py`, la fábrica de conexión, abre conexiones: nadie más llama a
  `sqlite3.connect` ni importa `connect` de `sqlite3`. Importar `sqlite3` para sus tipos
  y excepciones está permitido.
- Ninguna ruta se construye desde un literal (`Path("...")`, `pathlib.Path("...")`,
  `open("...")`) fuera de `shared/rutas.py`, la disposición del directorio de proyecto.
  `Path(__file__)` vale: apunta al propio código, no a datos de un proyecto.
"""

import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
FABRICA_DE_CONEXION = Path("shared/db.py")
DISPOSICION = Path("shared/rutas.py")
CONSTRUCTORES_DE_RUTA = {"Path", "PurePath", "PosixPath", "WindowsPath", "open"}


def _nombre_llamado(llamada: ast.Call) -> str | None:
    if isinstance(llamada.func, ast.Name):
        return llamada.func.id
    if isinstance(llamada.func, ast.Attribute):
        return llamada.func.attr
    return None


def _abre_conexion(nodo: ast.AST) -> bool:
    if isinstance(nodo, ast.ImportFrom) and (nodo.module or "").split(".")[0] == "sqlite3":
        return any(alias.name == "connect" for alias in nodo.names)
    if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute):
        valor = nodo.func.value
        return nodo.func.attr == "connect" and isinstance(valor, ast.Name) and valor.id == "sqlite3"
    return False


def _ruta_literal(nodo: ast.AST) -> bool:
    if not isinstance(nodo, ast.Call) or _nombre_llamado(nodo) not in CONSTRUCTORES_DE_RUTA:
        return False
    primero = nodo.args[0] if nodo.args else None
    return isinstance(primero, ast.Constant) and isinstance(primero.value, str)


def infracciones(codigo: str, relativa: Path) -> list[str]:
    encontradas = []
    for nodo in ast.walk(ast.parse(codigo)):
        linea = getattr(nodo, "lineno", 0)
        if relativa != FABRICA_DE_CONEXION and _abre_conexion(nodo):
            encontradas.append(f"{relativa}:{linea} abre una conexión SQLite")
        if relativa != DISPOSICION and _ruta_literal(nodo):
            encontradas.append(f"{relativa}:{linea} construye una ruta literal")
    return encontradas


def modulos_de_codigo() -> list[Path]:
    return [
        ruta for ruta in BACKEND.rglob("*.py") if "tests" not in ruta.relative_to(BACKEND).parts
    ]


def test_conexiones_y_rutas_solo_desde_shared() -> None:
    encontradas = []
    for ruta in modulos_de_codigo():
        relativa = ruta.relative_to(BACKEND)
        encontradas.extend(infracciones(ruta.read_text(encoding="utf-8"), relativa))
    assert encontradas == []


def test_detecta_una_conexion_fuera_de_la_fabrica() -> None:
    otra = Path("capitulo/biblia.py")
    assert infracciones("import sqlite3\nsqlite3.connect('x')\n", otra) != []
    assert infracciones("from sqlite3 import connect\n", otra) != []
    assert infracciones("import sqlite3\nc: sqlite3.Connection\n", otra) == []
    assert infracciones("import sqlite3\nsqlite3.connect(ruta)\n", FABRICA_DE_CONEXION) == []


def test_detecta_una_ruta_literal_fuera_de_la_disposicion() -> None:
    otra = Path("cambio/cola.py")
    assert infracciones('Path("proyectos/otro")\n', otra) != []
    assert infracciones('pathlib.Path("proyectos/otro")\n', otra) != []
    assert infracciones('open("biblia.sqlite")\n', otra) != []
    assert infracciones("Path(__file__).parent\n", Path("capitulo/estimador.py")) == []
    assert infracciones('Path("proyectos")\n', DISPOSICION) == []
