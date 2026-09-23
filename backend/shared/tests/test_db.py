"""Paso 1: la fábrica de conexión y el esquema."""

import re
import sqlite3
from pathlib import Path

import pytest

from backend.shared.db import conectar, crear_base, transaccion
from backend.shared.tipos import EstadoCapitulo, EstadoProyecto, Severidad

SPEC = Path(__file__).resolve().parents[3] / "specs" / "spec1.md"
AHORA = "2026-09-23T10:00:00Z"


@pytest.fixture
def base(tmp_path: Path) -> sqlite3.Connection:
    return crear_base(tmp_path / "proyecto.sqlite")


def _tablas(conexion: sqlite3.Connection) -> set[str]:
    filas = conexion.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {fila["name"] for fila in filas}


def _lista_check(conexion: sqlite3.Connection, tabla: str, columna: str) -> set[str]:
    fila = conexion.execute("SELECT sql FROM sqlite_master WHERE name = ?", (tabla,)).fetchone()
    coincidencia = re.search(rf"\b{columna}\b[^,]*?CHECK \({columna} IN \(([^)]*)\)", fila["sql"])
    assert coincidencia, f"{tabla}.{columna} no tiene CHECK con lista cerrada"
    return set(re.findall(r"'([^']+)'", coincidencia.group(1)))


def test_una_conexion_recien_abierta_tiene_los_pragmas(tmp_path: Path) -> None:
    conexion = conectar(tmp_path / "nueva.sqlite")
    assert conexion.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conexion.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conexion.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_el_esquema_cubre_las_tablas_de_la_spec(base: sqlite3.Connection) -> None:
    texto = SPEC.read_text(encoding="utf-8")
    seccion = texto[texto.index("## 6. Modelo de datos") : texto.index("## 7. Requisitos")]
    de_la_spec = set(re.findall(r"^\| `(\w+)` \|", seccion, flags=re.MULTILINE))
    assert len(de_la_spec) > 30
    assert de_la_spec - _tablas(base) == set()


def test_todas_las_tablas_son_strict(base: sqlite3.Connection) -> None:
    filas = base.execute(
        "SELECT name, strict FROM pragma_table_list "
        "WHERE schema = 'main' AND type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    assert len(filas) > 30
    assert {f["name"] for f in filas if f["strict"] != 1} == set()


def test_las_listas_de_estado_coinciden_con_los_tipos(base: sqlite3.Connection) -> None:
    assert _lista_check(base, "proyecto", "estado") == set(EstadoProyecto)
    assert _lista_check(base, "capitulo", "estado") == set(EstadoCapitulo)
    assert _lista_check(base, "informe", "severidad") == set(Severidad)
    en_version = _lista_check(base, "capitulo_version", "estado")
    assert en_version == set(EstadoCapitulo) - {EstadoCapitulo.PENDIENTE}


def test_las_claves_ajenas_se_aplican(base: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        base.execute(
            "INSERT INTO relacion (origen, destino, tipo) VALUES ('nadie', 'otro', 'alianza')"
        )


def test_strict_rechaza_un_tipo_equivocado(base: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        base.execute("INSERT INTO capitulo (numero, intentos) VALUES (1, 'tres')")


def test_la_clave_de_intento_es_unica(base: sqlite3.Connection) -> None:
    base.execute("INSERT INTO capitulo (numero) VALUES (3)")
    fila = (3, 2, 1, "borrador", "capitulos/cap-03/v2-intento1.md", AHORA)
    sql = (
        "INSERT INTO capitulo_version (capitulo, version, intento, estado, ruta, creado) "
        "VALUES (?, ?, ?, ?, ?, ?)"
    )
    base.execute(sql, fila)
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        base.execute(sql, fila)


def test_el_historial_es_append_only(base: sqlite3.Connection) -> None:
    base.execute(
        "INSERT INTO transicion (momento, origen, destino, causa) VALUES (?, ?, ?, ?)",
        (AHORA, "intake", "contexto", "prueba"),
    )
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        base.execute("UPDATE transicion SET destino = 'publicada'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        base.execute("DELETE FROM transicion")


def test_una_version_publicada_no_se_modifica(base: sqlite3.Connection) -> None:
    base.execute("INSERT INTO version_novela (numero, publicada) VALUES (1, ?)", (AHORA,))
    with pytest.raises(sqlite3.IntegrityError, match="RF-95"):
        base.execute("UPDATE version_novela SET publicada = 'otra'")
    with pytest.raises(sqlite3.IntegrityError, match="RF-95"):
        base.execute("DELETE FROM version_novela")


def test_la_transaccion_deshace_si_falla(base: sqlite3.Connection) -> None:
    with pytest.raises(RuntimeError), transaccion(base):
        base.execute("INSERT INTO glosario (termino, categoria) VALUES ('Nala', 'nombre')")
        raise RuntimeError("fallo a mitad")
    assert base.execute("SELECT count(*) FROM glosario").fetchone()[0] == 0

    with transaccion(base):
        base.execute("INSERT INTO glosario (termino, categoria) VALUES ('Nala', 'nombre')")
    assert base.execute("SELECT count(*) FROM glosario").fetchone()[0] == 1


def test_la_transaccion_anidada_se_compone_con_la_exterior(base: sqlite3.Connection) -> None:
    sql = "INSERT INTO glosario (termino, categoria) VALUES (?, 'nombre')"
    with transaccion(base):
        base.execute(sql, ("Nala",))
        with pytest.raises(RuntimeError), transaccion(base):
            base.execute(sql, ("Aitana",))
            raise RuntimeError("falla la interior")
        with transaccion(base):
            base.execute(sql, ("Brújula",))
        assert base.in_transaction
    terminos = {f["termino"] for f in base.execute("SELECT termino FROM glosario")}
    assert terminos == {"Nala", "Brújula"}

    with pytest.raises(RuntimeError), transaccion(base):
        with transaccion(base):
            base.execute(sql, ("Faro",))
        raise RuntimeError("falla la exterior después de confirmar la interior")
    assert base.execute("SELECT count(*) FROM glosario").fetchone()[0] == 2


def test_no_se_crea_dos_veces_la_misma_base(tmp_path: Path) -> None:
    ruta = tmp_path / "proyecto.sqlite"
    crear_base(ruta).close()
    with pytest.raises(FileExistsError):
        crear_base(ruta)
