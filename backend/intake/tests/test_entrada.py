"""E-6 · identificadores de un solo uso de `/mcp/entrada` (RF-14, parte de V-29).

El canje sirve una vez. Un identificador desconocido, usado, caducado, mal formado o de
otro proyecto falla con la misma excepción y el mismo mensaje, y un canje que falla no
consume nada. La base guarda la huella del secreto, nunca el secreto.

Todos los datos son ficticios (`backend/proyecto/tests/apoyo.py`).
"""

import hashlib
import re
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.intake.entrada import (
    CADUCIDAD,
    MARGEN_DE_ENTREGA,
    canjear,
    emitir,
    emitir_texto_libre,
    entregable,
    invalidar,
    retirar,
)
from backend.intake.persistencia import guardar_brief
from backend.proyecto.abierto import Proyecto
from backend.proyecto.errores import EntradaNoCanjeable
from backend.proyecto.persistencia import crear_proyecto
from backend.proyecto.tests.apoyo import AHORA, BRIEF, MOMENTO, TEXTO_LIBRE
from backend.shared.tipos import RecursoEntrada

MENSAJE = str(EntradaNoCanjeable())
OTRO_TEXTO = "Colecciona conchas de la playa del norte."


def _con_texto(tmp_path: Path, texto: str | None = TEXTO_LIBRE) -> Proyecto:
    proyecto = crear_proyecto(AHORA, raiz_proyectos=tmp_path)
    guardar_brief(proyecto.conexion, proyecto.disposicion, BRIEF, texto, MOMENTO)
    return proyecto


@pytest.fixture
def proyecto(tmp_path: Path) -> Iterator[Proyecto]:
    with _con_texto(tmp_path) as abierto:
        yield abierto


def _emitido(proyecto: Proyecto, minutos: int = 0) -> str:
    ahora = AHORA + timedelta(minutes=minutos)
    return emitir_texto_libre(proyecto.conexion, proyecto.disposicion, ahora).identificador


def _no_canjea(identificador: str, raiz: Path, minutos: int = 1) -> None:
    with pytest.raises(EntradaNoCanjeable) as fallo:
        canjear(identificador, AHORA + timedelta(minutes=minutos), raiz)
    assert str(fallo.value) == MENSAJE


def _filas(proyecto: Proyecto) -> list[tuple[object, ...]]:
    return [
        tuple(f)
        for f in proyecto.conexion.execute("SELECT * FROM identificador_entrada ORDER BY huella")
    ]


# ─── Emitir ──────────────────────────────────────────────────────────────────


def test_el_identificador_lleva_el_proyecto_y_un_secreto_que_no_se_deriva_de_el(
    proyecto: Proyecto,
) -> None:
    primero, segundo = _emitido(proyecto), _emitido(proyecto)
    prefijo, secreto = primero.split(".")
    assert prefijo == proyecto.identificador
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", secreto)
    assert proyecto.identificador not in secreto
    assert primero != segundo and segundo.split(".")[0] == prefijo


def test_la_base_guarda_la_huella_del_secreto_y_nunca_el_secreto(proyecto: Proyecto) -> None:
    emitido = emitir_texto_libre(proyecto.conexion, proyecto.disposicion, AHORA)
    secreto = emitido.identificador.split(".")[1]
    fila = proyecto.conexion.execute("SELECT * FROM identificador_entrada").fetchone()
    assert fila["huella"] == hashlib.sha256(secreto.encode("ascii")).hexdigest()
    assert (fila["recurso"], fila["ruta"], fila["consumido"]) == (
        "texto_libre",
        "brief/texto_libre.txt",
        None,
    )
    assert (fila["emitido"], fila["caduca"]) == ("2026-09-23T10:00:00Z", "2026-09-23T10:30:00Z")
    assert emitido.caduca == AHORA + CADUCIDAD
    assert emitido.como_entrada() == {
        "identificador": emitido.identificador,
        "caduca": "2026-09-23T10:30:00Z",
    }
    assert all(secreto not in str(valor) for valor in tuple(fila))


def test_sin_texto_libre_no_hay_identificador_que_emitir(tmp_path: Path) -> None:
    with _con_texto(tmp_path, texto=None) as proyecto, pytest.raises(LookupError):
        emitir_texto_libre(proyecto.conexion, proyecto.disposicion, AHORA)


def test_no_se_emite_un_identificador_para_una_ruta_fuera_del_proyecto(
    proyecto: Proyecto,
) -> None:
    with pytest.raises(ValueError, match="sale del directorio"):
        emitir(
            proyecto.conexion, proyecto.disposicion, RecursoEntrada.PETICION, "../otro.txt", AHORA
        )
    assert _filas(proyecto) == []


def test_la_lista_de_recursos_coincide_con_el_esquema(proyecto: Proyecto) -> None:
    sql = proyecto.conexion.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'identificador_entrada'"
    ).fetchone()["sql"]
    lista = re.search(r"CHECK \(recurso IN \(([^)]*)\)\)", sql)
    assert lista is not None
    assert set(re.findall(r"'([^']+)'", lista.group(1))) == set(RecursoEntrada)


# ─── Canjear ─────────────────────────────────────────────────────────────────


def test_el_canje_entrega_el_texto_una_vez_y_el_segundo_falla(
    proyecto: Proyecto, tmp_path: Path
) -> None:
    identificador = _emitido(proyecto)
    assert canjear(identificador, AHORA + timedelta(minutes=1), tmp_path) == TEXTO_LIBRE
    consumido = proyecto.conexion.execute("SELECT consumido FROM identificador_entrada")
    assert consumido.fetchone()["consumido"] == "2026-09-23T10:01:00Z"
    _no_canjea(identificador, tmp_path, minutos=2)


def test_caduca_a_los_treinta_minutos_de_emitirlo(proyecto: Proyecto, tmp_path: Path) -> None:
    justo_antes = _emitido(proyecto)
    en_punto = _emitido(proyecto)
    limite = AHORA + CADUCIDAD
    assert canjear(justo_antes, limite - timedelta(seconds=1), tmp_path) == TEXTO_LIBRE
    _no_canjea(en_punto, tmp_path, minutos=30)
    _no_canjea(en_punto, tmp_path, minutos=31)


def test_desconocido_mal_formado_y_de_un_proyecto_inexistente_fallan_igual(
    proyecto: Proyecto, tmp_path: Path
) -> None:
    valido = _emitido(proyecto)
    prefijo, secreto = valido.split(".")
    otro_secreto = "A" * 43
    for intento in [
        f"{prefijo}.{otro_secreto}",  # desconocido
        f"{'0' * 32}.{secreto}",  # de un proyecto que no existe
        prefijo,
        secreto,
        f"{prefijo}.",
        f"{prefijo}.{secreto}x",
        f"{prefijo.upper()}.{secreto}",
        f"{prefijo}.{secreto}\n",
        f"../{prefijo}.{secreto}",
        "",
    ]:
        _no_canjea(intento, tmp_path)
    # Ninguno de los fallos ha consumido el bueno.
    assert canjear(valido, AHORA + timedelta(minutes=1), tmp_path) == TEXTO_LIBRE


def test_el_identificador_de_un_proyecto_no_abre_el_texto_de_otro(tmp_path: Path) -> None:
    with (
        _con_texto(tmp_path) as uno,
        _con_texto(tmp_path, texto=OTRO_TEXTO) as otro,
    ):
        de_uno, de_otro = _emitido(uno), _emitido(otro)
        cruzado = f"{otro.identificador}.{de_uno.split('.')[1]}"
        _no_canjea(cruzado, tmp_path)
        assert canjear(de_otro, AHORA + timedelta(minutes=1), tmp_path) == OTRO_TEXTO
        assert canjear(de_uno, AHORA + timedelta(minutes=1), tmp_path) == TEXTO_LIBRE


def test_un_canje_que_falla_no_consume_nada(proyecto: Proyecto, tmp_path: Path) -> None:
    identificador = _emitido(proyecto)
    antes = _filas(proyecto)
    _no_canjea(identificador, tmp_path, minutos=45)
    assert _filas(proyecto) == antes


def test_sin_el_fichero_del_texto_falla_igual_y_no_consume(
    proyecto: Proyecto, tmp_path: Path
) -> None:
    identificador = _emitido(proyecto)
    proyecto.disposicion.texto_libre.unlink()
    antes = _filas(proyecto)
    _no_canjea(identificador, tmp_path)
    assert _filas(proyecto) == antes


@settings(max_examples=60, deadline=None)
@given(texto=st.text())
def test_ningun_texto_arbitrario_canjea_y_todos_fallan_con_el_mismo_mensaje(
    tmp_path_factory: pytest.TempPathFactory, texto: str
) -> None:
    raiz = tmp_path_factory.getbasetemp() / "arbitrarios"
    _no_canjea(texto, raiz)


# ─── Entrega con la orden, retirada e invalidación ──────────────────────────


def test_solo_se_entrega_un_identificador_sin_canjear_y_con_margen(
    proyecto: Proyecto, tmp_path: Path
) -> None:
    identificador = _emitido(proyecto)
    conexion = proyecto.conexion
    limite = AHORA + CADUCIDAD - MARGEN_DE_ENTREGA
    assert entregable(conexion, identificador, limite)
    assert not entregable(conexion, identificador, limite + timedelta(seconds=1))
    assert not entregable(conexion, identificador, AHORA + CADUCIDAD)
    canjear(identificador, AHORA + timedelta(minutes=1), tmp_path)
    assert not entregable(conexion, identificador, AHORA + timedelta(minutes=1))
    prefijo = identificador.split(".")[0]
    assert not entregable(conexion, f"{prefijo}.{'A' * 43}", AHORA)
    assert not entregable(conexion, "mal formado", AHORA)


def test_retirar_deja_sin_efecto_el_que_no_se_ha_canjeado(
    proyecto: Proyecto, tmp_path: Path
) -> None:
    sin_canjear, canjeado = _emitido(proyecto), _emitido(proyecto)
    canjear(canjeado, AHORA + timedelta(minutes=1), tmp_path)
    antes = _filas(proyecto)
    retirar(proyecto.conexion, canjeado)
    assert _filas(proyecto) == antes  # el canjeado queda como registro del canje
    retirar(proyecto.conexion, sin_canjear)
    retirar(proyecto.conexion, "mal formado")
    assert len(_filas(proyecto)) == 1
    _no_canjea(sin_canjear, tmp_path)


def test_invalidar_retira_los_de_un_recurso_sin_canjear(proyecto: Proyecto, tmp_path: Path) -> None:
    uno, otro = _emitido(proyecto), _emitido(proyecto)
    canjear(uno, AHORA + timedelta(minutes=1), tmp_path)
    invalidar(proyecto.conexion, RecursoEntrada.PETICION)
    assert len(_filas(proyecto)) == 2
    invalidar(proyecto.conexion, RecursoEntrada.TEXTO_LIBRE)
    assert [fila[1] for fila in _filas(proyecto)] == ["texto_libre"]
    _no_canjea(otro, tmp_path)
