"""La biblia: «a fecha N−1» (B-2, base de V-22), B-16, B-9 antes de escribir y §6.2."""

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from backend.capitulo.biblia import (
    FinDeCapitulo,
    Resumen,
    actualizar_estado_personaje,
    borrar_lo_escrito,
    continuidad_antes_de_escribir,
    escribir_resumen,
    inventario_a_fecha,
    personajes_a_fecha,
    presentes_excluidos,
    registrar_evento,
    registrar_traspaso,
    resumen_acumulado,
    salto_imposible,
)
from backend.capitulo.tests.referencia import MOMENTO, biblia_de_referencia, verificar
from backend.contexto.tests.referencia import referencia
from backend.escaleta.consultas import guardar_escaleta
from backend.escaleta.modelos import SalidaEscaletista
from backend.escaleta.tests.referencia import salida_escaletista

Escritura = tuple[int, str, str | None]
ESCRITURAS = st.lists(
    st.tuples(
        st.integers(1, 10),
        st.sampled_from(["herida", "cansada", "alegre"]),
        st.sampled_from([None, "prot", "nala"]),
    ),
    max_size=12,
)


@settings(max_examples=30, deadline=None)
@given(escrituras=ESCRITURAS, borrado=st.integers(1, 10))
def test_toda_lectura_ve_la_ultima_fila_anterior_a_n(
    escrituras: list[Escritura], borrado: int
) -> None:
    """B-2: a fecha N−1 vale la última escritura con capítulo < N, y el capítulo 0 es el
    estado inicial. B-16: borrar lo escrito para un capítulo es como no haberlo escrito."""
    with tempfile.TemporaryDirectory() as carpeta:
        conexion = biblia_de_referencia(Path(carpeta) / "proyecto.sqlite")
        try:
            verificar(conexion, *range(1, 11))
            modelo: dict[int, tuple[str, str | None]] = {0: ("Junto a Aitana", "prot")}
            for capitulo, estado, poseedor in escrituras:
                actualizar_estado_personaje(conexion, capitulo, "nala", estado)
                registrar_traspaso(conexion, capitulo, "brujula", poseedor)
                modelo[capitulo] = (estado, poseedor)

            def comprobar() -> None:
                for n in range(1, 12):
                    (nala,) = personajes_a_fecha(conexion, n, ["nala"])
                    (brujula,) = inventario_a_fecha(conexion, n)
                    esperado = modelo[max(c for c in modelo if c < n)]
                    assert (nala.estado, brujula.poseedor) == esperado, n

            comprobar()
            borrar_lo_escrito(conexion, borrado)
            modelo.pop(borrado, None)
            comprobar()
        finally:
            conexion.close()


def test_un_presente_excluido_por_el_contexto_se_detecta_antes_de_escribir(
    tmp_path: Path,
) -> None:
    """B-9, R-2: la partida de Nala viene del contexto (capítulo 0), así que excluye desde
    el capítulo 1. Control: Aitana no está excluida."""
    datos = referencia()
    datos["novela"]["personalizacion"]["hechos"][1]["excluye"] = {"fuente": "h1", "tipo": "partida"}
    conexion = biblia_de_referencia(tmp_path / "proyecto.sqlite", datos)
    hallazgos = continuidad_antes_de_escribir(conexion, 1)
    assert [(h.regla, h.evidencia.split(":")[0]) for h in hallazgos] == [
        ("RF-74 · presente_excluido", "nala")
    ]
    assert presentes_excluidos(conexion, 1, ["prot"]) == ()


def test_un_mencionado_excluido_no_se_bloquea(tmp_path: Path) -> None:
    """R-2, control: quien solo sale en un recuerdo va en `mencionados` y no se bloquea."""
    datos = referencia()
    datos["novela"]["personalizacion"]["hechos"][1]["excluye"] = {"fuente": "h1", "tipo": "partida"}
    conexion = biblia_de_referencia(tmp_path / "proyecto.sqlite", datos)
    escaleta = salida_escaletista()
    for ficha in escaleta["fichas"]:
        ficha["presentes"].remove("nala")
        ficha["mencionados"] = ["nala"]
    guardar_escaleta(conexion, SalidaEscaletista.model_validate(escaleta))
    assert all(continuidad_antes_de_escribir(conexion, n) == () for n in range(1, 11))


def test_un_salto_de_dias_imposible_por_la_ruta_se_detecta(tmp_path: Path) -> None:
    """B-9, RF-76: de la casa a la cueva hay tres días de ruta. Control: la escaleta de
    referencia, a un día por etapa, no dispara nada."""
    conexion = biblia_de_referencia(tmp_path / "proyecto.sqlite")
    assert all(continuidad_antes_de_escribir(conexion, n) == () for n in range(1, 11))
    desde_casa = FinDeCapitulo(1, "casa_abuela")
    (viaje,) = salto_imposible(conexion, 8, 2, "cueva_final", desde_casa)
    assert (viaje.regla, viaje.esperado) == (
        "RF-76 · viaje_imposible",
        "al menos 3 días de viaje según la ruta",
    )
    (atras,) = salto_imposible(conexion, 8, 2, "cueva_final", FinDeCapitulo(3, "faro"))
    assert atras.regla == "RF-76 · dia_retrocede"
    assert salto_imposible(conexion, 8, 4, "cueva_final", desde_casa) == ()


def test_el_resumen_acumulado_compacta_los_actos_cerrados(tmp_path: Path) -> None:
    """§6.2, RF-55: el acto 1 (capítulos 1 y 2) viaja como un resumen de acto; el acto en
    curso, capítulo a capítulo. Los resúmenes de capítulo no se borran (RF-87)."""
    conexion = biblia_de_referencia(tmp_path / "proyecto.sqlite")
    verificar(conexion, 1, 2, 3)
    for capitulo in (1, 2, 3):
        escribir_resumen(conexion, capitulo, "capitulo", f"Pasa lo del {capitulo}.", MOMENTO)
    escribir_resumen(conexion, 2, "acto", "Aitana encuentra el mapa.", MOMENTO)
    conexion.execute("UPDATE capitulo SET version_vigente = 1 WHERE numero <= 3")
    assert resumen_acumulado(conexion, 4) == (
        Resumen("acto", 1, "Aitana encuentra el mapa."),
        Resumen("capitulo", 3, "Pasa lo del 3."),
    )
    assert resumen_acumulado(conexion, 2) == (Resumen("capitulo", 1, "Pasa lo del 1."),)
    assert (
        conexion.execute("SELECT count(*) FROM resumen WHERE ambito = 'capitulo'").fetchone()[0]
        == 3
    )


def test_vale_el_resumen_de_la_version_vigente_no_el_de_la_mas_alta(tmp_path: Path) -> None:
    """RF-87, B-17: con la versión 2 del capítulo 2 en curso (una regeneración a medias), el
    capítulo siguiente sigue leyendo los resúmenes de la vigente, la 1."""
    conexion = biblia_de_referencia(tmp_path / "proyecto.sqlite")
    verificar(conexion, 1, 2)
    escribir_resumen(conexion, 1, "capitulo", "Pasa lo del 1.", MOMENTO)
    escribir_resumen(conexion, 2, "capitulo", "Pasa lo del 2.", MOMENTO)
    escribir_resumen(conexion, 2, "acto", "Aitana encuentra el mapa.", MOMENTO)
    conexion.execute("UPDATE capitulo SET version_vigente = 1 WHERE numero <= 2")
    conexion.execute(
        "INSERT INTO capitulo_version (capitulo, version, intento, estado, ruta, creado) "
        "VALUES (2, 2, 1, 'verificado', 'capitulos/cap-02/v2-intento1.md', ?)",
        (MOMENTO,),
    )
    escribir_resumen(conexion, 2, "capitulo", "Otra cosa en el 2.", MOMENTO)
    escribir_resumen(conexion, 2, "acto", "Otro acto.", MOMENTO)
    assert resumen_acumulado(conexion, 3) == (Resumen("acto", 1, "Aitana encuentra el mapa."),)
    conexion.execute("DELETE FROM resumen WHERE ambito = 'acto'")
    assert resumen_acumulado(conexion, 3) == (
        Resumen("capitulo", 1, "Pasa lo del 1."),
        Resumen("capitulo", 2, "Pasa lo del 2."),
    )


def test_registrar_el_mismo_evento_dos_veces_no_lo_duplica(tmp_path: Path) -> None:
    """La herramienta anuncia `idempotent_hint`: repetir la llamada devuelve el mismo id.
    Control: otro día es otro evento."""
    conexion = biblia_de_referencia(tmp_path / "proyecto.sqlite")
    verificar(conexion, 1)
    primero = registrar_evento(conexion, 1, "Abre el cofre.", "casa_abuela", ["nala"], dia=1)
    assert (
        registrar_evento(conexion, 1, "Abre el cofre.", "casa_abuela", ["nala"], dia=1) == primero
    )
    otro = registrar_evento(conexion, 1, "Abre el cofre.", "casa_abuela", ["nala"], dia=2)
    assert otro != primero
    cuenta = "SELECT count(*) FROM evento WHERE capitulo = 1"
    assert conexion.execute(cuenta).fetchone()[0] == 2
    assert conexion.execute("SELECT count(*) FROM evento_personaje").fetchone()[0] == 2


def test_un_recuerdo_con_fecha_imposible_no_se_registra(tmp_path: Path) -> None:
    """Un `2023-02-30` no entra en la biblia: después rompería la cronología de Lean."""
    import pytest

    from backend.capitulo.biblia import EscrituraInvalida

    conexion = biblia_de_referencia(tmp_path / "proyecto.sqlite")
    verificar(conexion, 1)
    with pytest.raises(EscrituraInvalida):
        registrar_evento(conexion, 1, "Un recuerdo.", "casa_abuela", [], momento="2023-02-30")
