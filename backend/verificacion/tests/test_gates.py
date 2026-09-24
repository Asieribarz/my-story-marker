"""V-27 (RF-111, RF-112) y V-28 (RF-110): los gates deterministas de manuscrito.

Cronologías sintéticas que infringen cada invariante, con su control. Sin `lake` en la
máquina, se prueba la generación determinista y la lectura de una salida simulada; la
ejecución real lleva `skipif`. Todos los datos son ficticios.
"""

import json
import shutil
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.contexto.modelos import es_fecha, es_momento
from backend.proyecto.abierto import Proyecto, abrir_proyecto
from backend.proyecto.bloqueo import tomar_bloqueo
from backend.proyecto.manejadores import OrdenNoEmitible
from backend.proyecto.orden import OrdenEmitida
from backend.proyecto.persistencia import emitir_siguiente_orden
from backend.shared.rutas import DisposicionProyecto
from backend.shared.tipos import Agente, TipoEjecutor
from backend.verificacion import gates
from backend.verificacion.consultas import leer_biblia
from backend.verificacion.cronologia import (
    INTERVALO_SIN_FECHA,
    Biblia,
    EventoBiblia,
    SalidaLeanIlegible,
    generar,
    intervalo,
    leer_informe,
)
from backend.verificacion.gates import EjecucionLean, ejecutar_gates
from backend.verificacion.tests.apoyo import IDENTIFICADOR, MOMENTO, evento, proyecto

VERDE = '{"lugar_unico":[],"exclusion":[],"nacimiento":[]}'
AHORA = datetime(2026, 9, 23, 10, tzinfo=UTC)


@pytest.fixture
def base(tmp_path: Path) -> Iterator[tuple[DisposicionProyecto, sqlite3.Connection]]:
    disposicion, conexion = proyecto(tmp_path)
    yield disposicion, conexion
    conexion.close()


def _fila(c: sqlite3.Connection, gate: str) -> tuple[int, dict[str, object]] | None:
    f = c.execute("SELECT ok, detalle FROM gate_resultado WHERE pasada = 1 AND gate = ?", (gate,))
    fila = f.fetchone()
    return None if fila is None else (int(fila["ok"]), json.loads(fila["detalle"]))


def _simular(monkeypatch: pytest.MonkeyPatch, codigo: int, salida: str) -> None:
    monkeypatch.setattr(gates, "localizar_lake", lambda: "lake")
    monkeypatch.setattr(gates, "ejecutar_lean", lambda _l, _f: EjecucionLean(codigo, salida))


# ─── V-28 · cobertura ────────────────────────────────────────────────────────


def test_v28_hecho_obligatorio_sin_uso_senala_los_capitulos_de_su_ficha(
    base: tuple[DisposicionProyecto, sqlite3.Connection], monkeypatch: pytest.MonkeyPatch
) -> None:
    disposicion, c = base
    _simular(monkeypatch, 0, VERDE)
    # Un uso en una versión que ya no es la vigente no cuenta.
    c.execute("INSERT INTO hecho_uso (hecho, capitulo, version) VALUES ('h_faro', 3, 1)")
    ejecutar_gates(c, disposicion, 1, MOMENTO)
    assert _fila(c, "cobertura") == (
        0,
        {"capitulos": [3, 5], "sin_uso": ["h_faro"], "por_hecho": {"h_faro": [3, 5]}},
    )


def test_v28_control_con_uso_en_la_version_vigente(
    base: tuple[DisposicionProyecto, sqlite3.Connection], monkeypatch: pytest.MonkeyPatch
) -> None:
    disposicion, c = base
    _simular(monkeypatch, 0, VERDE)
    c.execute("INSERT INTO hecho_uso (hecho, capitulo, version) VALUES ('h_faro', 7, 2)")
    ejecutar_gates(c, disposicion, 1, MOMENTO)
    assert _fila(c, "cobertura") == (1, {"capitulos": [], "sin_uso": [], "por_hecho": {}})


# ─── V-27 · generación determinista ──────────────────────────────────────────


def test_v27_el_fichero_es_determinista_utf8_sin_bom_y_con_lf(
    base: tuple[DisposicionProyecto, sqlite3.Connection],
) -> None:
    _, c = base
    evento(c, None, "casa", [], momento="2023-07", excluye="leo")
    evento(c, 2, "isla", ["leo", "ana"], dia=2, franja="tarde")
    uno, otro = generar(leer_biblia(c)), generar(leer_biblia(c))
    assert uno.lean_bytes == otro.lean_bytes
    assert uno.correspondencia_bytes == otro.correspondencia_bytes
    assert not uno.lean_bytes.startswith(b"\xef\xbb\xbf") and b"\r" not in uno.lean_bytes
    lean = uno.lean
    assert lean.startswith("import Cronologia\nopen Cronologia\n")
    assert "{ id := 1, padre := some 3 }" in lean  # casa (1) dentro de pueblo (3)
    assert f".recuerdo {intervalo('2023-07')[0]} {intervalo('2023-07')[1]}" in lean
    assert "momento := .historia 2 .tarde, lugar := 2, presentes := [1, 2]" in lean
    assert "excluye := some 2" in lean
    assert lean.count("by decide +kernel") == 3 and "#eval violaciones novela" in lean
    assert uno.correspondencia["eventos"][1] == {"id": 2, "evento": 2, "capitulo": 2}


def test_v27_intervalos_de_fechas_parciales_y_periodos() -> None:
    assert intervalo("2023-07-15")[0] == intervalo("2023-07-15")[1]
    assert intervalo("2024-02")[1] - intervalo("2024-02")[0] == 28
    assert intervalo("2023")[1] - intervalo("2023")[0] == 364
    assert intervalo("infancia") == INTERVALO_SIN_FECHA


# ─── V-27 · lectura del informe y gate ───────────────────────────────────────

ROJOS = {
    "lugar_unico": '{"lugar_unico":[{"personaje":1,"eventos":[1,2]}],"exclusion":[],'
    '"nacimiento":[]}',
    "exclusion": '{"lugar_unico":[],"exclusion":[{"personaje":2,"excluye":1,"evento":2}],'
    '"nacimiento":[]}',
    "nacimiento": '{"lugar_unico":[],"exclusion":[],"nacimiento":[{"personaje":1,"evento":1}]}',
}


@pytest.mark.parametrize("clave", sorted(ROJOS))
def test_v27_cada_violacion_da_el_gate_rojo_con_los_capitulos_de_sus_eventos(
    clave: str,
    base: tuple[DisposicionProyecto, sqlite3.Connection],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disposicion, c = base
    evento(c, 4, "casa", ["ana", "leo"], dia=1, excluye="leo")
    evento(c, 6, "isla", ["ana", "leo"], dia=3)
    salida = "error: Tactic 'decide' proved that the proposition ... is false\n" + ROJOS[clave]
    _simular(monkeypatch, 1, salida)
    ejecutar_gates(c, disposicion, 1, MOMENTO)
    fila = _fila(c, "lean")
    assert fila is not None and fila[0] == 0
    esperado = [4] if clave == "nacimiento" else [4, 6]
    assert fila[1]["capitulos"] == esperado
    assert (disposicion.pasada(1) / "cronologia.lean").is_file()
    assert fila[1]["fichero"] == "verificacion/pasada-1/cronologia.lean"


def test_v27_control_verde_e_idempotente(
    base: tuple[DisposicionProyecto, sqlite3.Connection], monkeypatch: pytest.MonkeyPatch
) -> None:
    disposicion, c = base
    _simular(monkeypatch, 0, VERDE + "\n")
    ejecutar_gates(c, disposicion, 1, MOMENTO)
    _simular(monkeypatch, 1, ROJOS["exclusion"])
    ejecutar_gates(c, disposicion, 1, MOMENTO)
    assert _fila(c, "lean") == (
        1,
        {
            "capitulos": [],
            "eventos": [],
            "violaciones": json.loads(VERDE),
            "fichero": "verificacion/pasada-1/cronologia.lean",
        },
    )
    assert c.execute("SELECT count(*) FROM gate_resultado").fetchone()[0] == 2


@pytest.mark.parametrize(
    ("codigo", "salida"),
    [(1, VERDE), (0, ROJOS["exclusion"]), (1, "error: unknown module"), (0, "{no es json")],
)
def test_v27_salida_ilegible(codigo: int, salida: str) -> None:
    with pytest.raises(SalidaLeanIlegible):
        leer_informe(codigo, salida)


def test_sin_lean_la_orden_no_se_emite_y_no_queda_fila_de_lean(
    base: tuple[DisposicionProyecto, sqlite3.Connection], monkeypatch: pytest.MonkeyPatch
) -> None:
    disposicion, c = base
    monkeypatch.setattr(gates, "localizar_lake", lambda: None)
    with pytest.raises(OrdenNoEmitible) as error:
        ejecutar_gates(c, disposicion, 1, MOMENTO)
    assert error.value.causa == "lean_no_disponible" and error.value.capitulo is None
    assert _fila(c, "lean") is None and _fila(c, "cobertura") is not None


# ─── V-27 · Lean real ────────────────────────────────────────────────────────


def _novela(eventos: list[EventoBiblia], nacimiento: str | None = None) -> Biblia:
    return Biblia(
        localizaciones=(("casa", "pueblo"), ("isla", None), ("pueblo", None)),
        personajes=(("ana", nacimiento), ("leo", None)),
        eventos=tuple(eventos),
    )


def _ev(
    i: int,
    lugar: str,
    presentes: tuple[str, ...],
    *,
    dia: int | None = None,
    franja: str | None = None,
    momento: str | None = None,
    excluye: str | None = None,
) -> EventoBiblia:
    return EventoBiblia(i, i, momento, dia, franja, lugar, presentes, excluye)


CASOS = {
    "lugar_unico": _novela(
        [
            _ev(1, "casa", ("ana",), dia=1, franja="manana"),
            _ev(2, "isla", ("ana",), dia=1, franja="manana"),
        ]
    ),
    "exclusion": _novela(
        [_ev(1, "casa", ("leo",), dia=1, excluye="leo"), _ev(2, "isla", ("leo",), dia=2)]
    ),
    "nacimiento": _novela([_ev(1, "casa", ("ana",), momento="1980-01")], nacimiento="1990-05-01"),
    "control": _novela(
        [
            _ev(1, "casa", ("ana",), dia=1, franja="manana"),
            _ev(2, "pueblo", ("ana",), dia=1, franja="manana"),
        ]
    ),
}


@pytest.mark.skipif(shutil.which("lake") is None, reason="sin elan/lake en esta máquina")
@pytest.mark.parametrize("caso", sorted(CASOS))
def test_v27_lean_real_detecta_cada_invariante(caso: str, tmp_path: Path) -> None:
    fichero = tmp_path / "cronologia.lean"
    fichero.write_bytes(generar(CASOS[caso]).lean_bytes)
    lake = gates.localizar_lake()
    assert lake is not None
    ejecucion = gates.ejecutar_lean(lake, fichero)
    informe = leer_informe(ejecucion.codigo, ejecucion.salida)
    con_violaciones = sorted(k for k, v in informe.items() if v)
    assert con_violaciones == ([] if caso == "control" else [caso])


# ─── M-6: nunca un gate rojo sin capítulo ────────────────────────────────────


def test_un_hecho_sin_ficha_va_al_capitulo_con_menos_hechos(
    base: tuple[DisposicionProyecto, sqlite3.Connection], monkeypatch: pytest.MonkeyPatch
) -> None:
    """M-6: sin ficha que lo pida, el capítulo con menos hechos en su ficha (el 1: el 3 y el
    5 ya tienen uno). Control: los que sí tienen ficha siguen con los suyos."""
    disposicion, c = base
    _simular(monkeypatch, 0, VERDE)
    c.execute(
        "INSERT INTO hecho (id, tipo, texto, prioridad, origen) "
        "VALUES ('h_luna', 'objeto', 'Una luna ficticia', 'obligatorio', 'entrevista')"
    )
    ejecutar_gates(c, disposicion, 1, MOMENTO)
    fila = _fila(c, "cobertura")
    assert fila is not None and fila[0] == 0
    assert fila[1]["capitulos"] == [1, 3, 5]
    assert fila[1]["por_hecho"] == {"h_faro": [3, 5], "h_luna": [1]}


def test_lean_rojo_solo_con_eventos_del_contexto_es_contexto_incoherente(
    base: tuple[DisposicionProyecto, sqlite3.Connection], monkeypatch: pytest.MonkeyPatch
) -> None:
    """M-6: ningún Revisor corrige el contexto: `error` sin fila de Lean (no gasta ciclo)."""
    disposicion, c = base
    evento(c, None, "casa", ["ana", "leo"], momento="2001", excluye="leo")
    evento(c, None, "isla", ["ana", "leo"], momento="2002")
    salida = (
        "error: Tactic 'decide' proved that the proposition ... is false\n" + ROJOS["exclusion"]
    )
    _simular(monkeypatch, 1, salida)
    with pytest.raises(OrdenNoEmitible) as error:
        ejecutar_gates(c, disposicion, 1, MOMENTO)
    assert error.value.causa == "contexto_incoherente"
    assert _fila(c, "lean") is None


# ─── Fechas imposibles ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("momento", "valida"),
    [("2023-02-30", False), ("2023-04-31", False), ("0000", False), ("2024-02-29", True)],
)
def test_una_fecha_imposible_no_es_fecha_ni_momento(momento: str, valida: bool) -> None:
    assert es_fecha(momento) is valida and es_momento(momento) is valida


def test_una_biblia_que_no_se_traduce_es_cronologia_invalida(
    base: tuple[DisposicionProyecto, sqlite3.Connection], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cualquier `ValueError` al generar el `.lean` es `error` con causa, no un 500 en
    `/siguiente` que se repite para siempre."""
    disposicion, c = base

    def rompe(_biblia: Biblia) -> None:
        raise ValueError("day is out of range for month")

    monkeypatch.setattr(gates, "generar", rompe)
    with pytest.raises(OrdenNoEmitible) as error:
        ejecutar_gates(c, disposicion, 1, MOMENTO)
    assert error.value.causa == "cronologia_invalida"


# ─── M-27: Lean fuera de la transacción de escritura ─────────────────────────


def test_lean_corre_sin_bloquear_la_escritura_y_el_juez_recibe_el_manuscrito(
    base: tuple[DisposicionProyecto, sqlite3.Connection], monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-4, M-27: mientras Lean corre, otra conexión puede escribir (no hay `BEGIN
    IMMEDIATE` abierto). La orden del juez lleva dónde está el manuscrito: la versión
    vigente aprobada de cada capítulo."""
    disposicion, c = base
    abierto = Proyecto(disposicion, c)
    token = tomar_bloqueo(abierto, TipoEjecutor.SESION, AHORA).token
    libre: list[bool] = []

    def lean(_lake: str, _fichero: Path) -> EjecucionLean:
        with abrir_proyecto(IDENTIFICADOR, disposicion.raiz.parent) as otro:
            otro.conexion.execute("PRAGMA busy_timeout = 0")
            try:
                otro.conexion.execute("BEGIN IMMEDIATE")
                otro.conexion.execute("ROLLBACK")
                libre.append(True)
            except sqlite3.OperationalError:
                libre.append(False)
        return EjecucionLean(0, VERDE)

    monkeypatch.setattr(gates, "localizar_lake", lambda: "lake")
    monkeypatch.setattr(gates, "ejecutar_lean", lean)
    orden = emitir_siguiente_orden(abierto, token, AHORA)
    assert isinstance(orden, OrdenEmitida) and orden.agente is Agente.JUEZ_MANUSCRITO
    assert libre == [True]
    assert _fila(c, "lean") is not None and _fila(c, "cobertura") is not None
    assert orden.entrada["manuscrito"] == [
        {"capitulo": n, "version": 2, "intento": 1, "etapa": "editado"} for n in range(1, 11)
    ]
