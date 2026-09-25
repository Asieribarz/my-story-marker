"""V-1 (RNF-01): matar el proceso a mitad y reanudar pierde como mucho el trabajo de un
subagente, nunca la posición en el grafo.

Un subproceso crea el proyecto, avanza hasta el punto indicado y muere con `os._exit`, sin
cerrar nada ni deshacer transacciones. Después se reabre el proyecto y se comprueba que el
estado leído es el esperado y que se puede seguir desde él.

Se mata en cada estado del grafo: en los que tienen agente, a mitad del registro del
resultado de su orden, con un manejador de ensayo que escribe y muere; en las paradas, a
mitad de la acción humana que las saca. Los estados que aún no tienen manejador se colocan
con `apoyo.forzar`. Además, puntos concretos de `intake` y del bucle de capítulo.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from backend.intake.entrada import canjear
from backend.proyecto.abierto import abrir_proyecto
from backend.proyecto.bloqueo import tomar_bloqueo
from backend.proyecto.maquina import AGENTES_DEL_ESTADO, AccionHumana, EsperarHumano, MotivoEspera
from backend.proyecto.orden import OrdenEmitida
from backend.proyecto.persistencia import (
    CapituloLeido,
    decidir,
    emitir_siguiente_orden,
    leer_estado,
)
from backend.proyecto.tests.apoyo import (
    HECHO,
    NORMALIZADO,
    TEXTO_LIBRE,
    despues,
    registrar,
    transiciones,
)
from backend.shared.tipos import Agente, DesenlaceOrden, EstadoCapitulo, TipoEjecutor
from backend.shared.tipos import EstadoProyecto as E

RAIZ = Path(__file__).resolve().parents[3]
MUERTE = 17

# El subproceso: solo ASCII, porque viaja como argumento de la línea de órdenes.
_SUBPROCESO = """
import json, os, sys
from pathlib import Path
from backend.intake.persistencia import confirmar_hechos, guardar_brief, hechos_pendientes
from backend.proyecto import manejadores
from backend.proyecto.bloqueo import tomar_bloqueo
from backend.proyecto.maquina import Desenlace
from backend.proyecto import persistencia
from backend.proyecto.maquina import AccionHumana
from backend.proyecto.persistencia import (
    crear_proyecto, decidir, emitir_siguiente_orden)
from backend.proyecto.tests.apoyo import registrar
from backend.proyecto.tests.apoyo import AHORA, BRIEF, HECHO, MOMENTO, TEXTO_LIBRE, forzar
from backend.shared.tipos import Agente, EstadoProyecto, TipoEjecutor

raiz, modo = Path(sys.argv[1]), sys.argv[2]
for sin_herramienta in (Agente.ESCRITOR, Agente.JUEZ_MANUSCRITO, Agente.EXPORTADOR,
                        Agente.INTERPRETE_CAMBIOS):
    manejadores.CONSTRUCTORES_DE_ENTRADA[sin_herramienta] = lambda solicitud, base: base
manejadores.FASES_PREVIAS.clear()
proyecto = crear_proyecto(AHORA, raiz_proyectos=raiz)
token = tomar_bloqueo(proyecto, TipoEjecutor.SESION, AHORA).token

def avisar(emitida):
    orden = None if emitida is None else emitida.id
    datos = {"id": proyecto.identificador, "token": token, "orden": orden}
    print(json.dumps(datos), flush=True)

def morir_tras(funcion):
    def a_medias(*argumentos):
        funcion(*argumentos)
        os._exit(17)
    return a_medias

if modo == "en_estado":
    estado = EstadoProyecto(sys.argv[3])
    accion = sys.argv[4]
    desde = EstadoProyecto.CONTEXTO if estado is EstadoProyecto.DETENIDA else None
    if estado is EstadoProyecto.INTAKE:
        guardar_brief(proyecto.conexion, proyecto.disposicion, BRIEF, TEXTO_LIBRE, MOMENTO)
    else:
        forzar(proyecto, estado, detenida_desde=desde, parada_plan=True, parada_final=True)
    if estado is EstadoProyecto.REVISION:
        # M-6: una revisión siempre tiene capítulos; aquí, el 3 que señala la cobertura.
        proyecto.conexion.execute("UPDATE proyecto SET pasadas = 1")
        proyecto.conexion.execute(
            "INSERT INTO gate_resultado VALUES (1, 'cobertura', 0, ?)",
            (json.dumps({"capitulos": [3]}),))
    if accion == "registrar":
        orden = emitir_siguiente_orden(proyecto, token, AHORA)
        def escribe(contexto, resultado):
            contexto.conexion.execute(
                "INSERT INTO auditoria (momento, tipo, detalle) VALUES (?, 'policy', '{}')",
                (MOMENTO,))
            return manejadores.Salida(Desenlace.aceptado())
        manejadores.MANEJADORES[orden.agente] = morir_tras(escribe)
        avisar(orden)
        registrar(proyecto, orden.id, {"ensayo": True}, token, AHORA)
    else:
        persistencia._persistir = morir_tras(persistencia._persistir)
        avisar(None)
        decidir(proyecto, AccionHumana(accion), AHORA, notas="a medias")
    sys.exit(1)

if modo == "capitulo_tras_un_fallo":
    forzar(proyecto, EstadoProyecto.CAPITULOS)
    def rechaza(contexto, resultado):
        return manejadores.Salida(Desenlace.contenido(), {"motivo": "sin titulo"})
    manejadores.MANEJADORES[Agente.ESCRITOR] = rechaza
    escritor = emitir_siguiente_orden(proyecto, token, AHORA)
    registrar(proyecto, escritor.id, {"texto": ""}, token, AHORA)
    avisar(escritor)
    os._exit(17)

guardar_brief(proyecto.conexion, proyecto.disposicion, BRIEF, TEXTO_LIBRE, MOMENTO)
orden = emitir_siguiente_orden(proyecto, token, AHORA)

if modo == "tras_un_fallo":
    registrar(proyecto, orden.id, "no es un sobre", token, AHORA)
    avisar(orden)
    os._exit(17)
if modo == "tras_emitir":
    avisar(orden)
    os._exit(17)
if modo == "durante_el_registro":
    real = manejadores.MANEJADORES[Agente.EXTRACTOR_HECHOS]
    def a_medias(contexto, resultado):
        real(contexto, resultado)
        os._exit(17)
    manejadores.MANEJADORES[Agente.EXTRACTOR_HECHOS] = a_medias
    avisar(orden)
    registrar(proyecto, orden.id, {"hechos": [HECHO]}, token, AHORA)
if modo == "tras_registrar":
    registrar(proyecto, orden.id, {"hechos": [HECHO]}, token, AHORA)
    avisar(orden)
    os._exit(17)
if modo == "antes_de_registrar":
    registrar(proyecto, orden.id, {"hechos": [HECHO]}, token, AHORA)
    pendientes = hechos_pendientes(proyecto.conexion)
    confirmar_hechos(proyecto.conexion, {f["id"]: True for f in pendientes}, MOMENTO)
    normalizar = emitir_siguiente_orden(proyecto, token, AHORA)
    avisar(normalizar)
    os._exit(17)
sys.exit(1)
"""


def _matar_en(raiz: Path, modo: str, *argumentos: str) -> dict[str, Any]:
    proceso = subprocess.run(
        [sys.executable, "-c", _SUBPROCESO, str(raiz), modo, *argumentos],
        cwd=RAIZ,
        env={**os.environ, "PYTHONPATH": str(RAIZ)},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proceso.returncode == MUERTE, proceso.stderr
    datos: dict[str, Any] = json.loads(proceso.stdout.strip().splitlines()[-1])
    return datos


def _hechos(conexion: Any) -> int:
    return int(conexion.execute("SELECT count(*) FROM hecho_propuesto").fetchone()[0])


@pytest.mark.parametrize("modo", ["tras_emitir", "durante_el_registro"])
def test_la_orden_persistida_sobrevive_y_el_registro_a_medias_no(tmp_path: Path, modo: str) -> None:
    muerto = _matar_en(tmp_path, modo)
    with abrir_proyecto(muerto["id"], tmp_path) as proyecto:
        leido = leer_estado(proyecto, despues(31))
        assert leido.estado is E.INTAKE
        vigente = leido.orden_vigente
        assert vigente is not None
        assert (vigente.id, vigente.agente, vigente.intento) == (
            muerto["orden"],
            Agente.EXTRACTOR_HECHOS,
            1,
        )
        assert _hechos(proyecto.conexion) == 0
        # La sesión muerta no soltó el bloqueo: caduca, y una sesión nueva sigue. A los 31
        # minutos también caducó el identificador de /mcp/entrada de la orden (RF-14): la
        # misma orden llega con uno nuevo, que el Extractor relanzado puede canjear.
        token = tomar_bloqueo(proyecto, TipoEjecutor.SESION, despues(31)).token
        reanudada = emitir_siguiente_orden(proyecto, token, despues(31))
        assert isinstance(reanudada, OrdenEmitida)
        assert (reanudada.id, reanudada.agente, reanudada.intento, reanudada.estado) == (
            vigente.id,
            Agente.EXTRACTOR_HECHOS,
            1,
            E.INTAKE,
        )
        identificador = reanudada.entrada["texto_libre"]["identificador"]
        assert canjear(identificador, despues(31), tmp_path) == TEXTO_LIBRE
        registro = registrar(proyecto, reanudada.id, {"hechos": [HECHO]}, token, despues(32))
        assert registro.desenlace is DesenlaceOrden.ACEPTADA
        assert _hechos(proyecto.conexion) == 1
        siguiente = emitir_siguiente_orden(proyecto, token, despues(32))
        assert siguiente == EsperarHumano(MotivoEspera.CONFIRMACION_HECHOS)


def test_el_resultado_registrado_sobrevive_y_repetirlo_no_duplica(tmp_path: Path) -> None:
    muerto = _matar_en(tmp_path, "tras_registrar")
    with abrir_proyecto(muerto["id"], tmp_path) as proyecto:
        token = muerto["token"]
        leido = leer_estado(proyecto, despues(1))
        assert (leido.estado, leido.orden_vigente) == (E.INTAKE, None)
        repetido = registrar(proyecto, muerto["orden"], {"hechos": [HECHO]}, token, despues(1))
        assert repetido.repetido
        assert _hechos(proyecto.conexion) == 1


def test_el_contador_de_paso_sobrevive_al_reinicio(tmp_path: Path) -> None:
    """RF-07a: una sesión nueva recibe el segundo intento, no vuelve a empezar desde el primero."""
    muerto = _matar_en(tmp_path, "tras_un_fallo")
    with abrir_proyecto(muerto["id"], tmp_path) as proyecto:
        assert leer_estado(proyecto, despues(31)).intentos_paso == 1
        token = tomar_bloqueo(proyecto, TipoEjecutor.SESION, despues(31)).token
        otra = emitir_siguiente_orden(proyecto, token, despues(31))
        assert isinstance(otra, OrdenEmitida)
        assert (otra.agente, otra.intento) == (Agente.EXTRACTOR_HECHOS, 2)
        assert otra.entrada["informe_anterior"] is not None


def test_el_contador_del_capitulo_sobrevive_al_reinicio(tmp_path: Path) -> None:
    """RF-07: el intento del capítulo vive en su fila; el Escritor recibe el segundo."""
    muerto = _matar_en(tmp_path, "capitulo_tras_un_fallo")
    with abrir_proyecto(muerto["id"], tmp_path) as proyecto:
        leido = leer_estado(proyecto, despues(31))
        assert (leido.estado, leido.capitulos[0]) == (
            E.CAPITULOS,
            CapituloLeido(1, EstadoCapitulo.PENDIENTE, 1),
        )
        token = tomar_bloqueo(proyecto, TipoEjecutor.SESION, despues(31)).token
        escritor = emitir_siguiente_orden(proyecto, token, despues(31))
        assert isinstance(escritor, OrdenEmitida)
        assert (escritor.agente, escritor.capitulo, escritor.intento) == (Agente.ESCRITOR, 1, 2)
        assert escritor.entrada["informe_anterior"] == {"motivo": "sin titulo"}


def test_morir_antes_de_registrar_pierde_solo_el_trabajo_del_subagente(tmp_path: Path) -> None:
    muerto = _matar_en(tmp_path, "antes_de_registrar")
    with abrir_proyecto(muerto["id"], tmp_path) as proyecto:
        token = muerto["token"]
        vigente = emitir_siguiente_orden(proyecto, token, despues(1))
        assert isinstance(vigente, OrdenEmitida)
        assert (vigente.id, vigente.agente, vigente.estado) == (
            muerto["orden"],
            Agente.AGENTE_CONTEXTO,
            E.INTAKE,
        )
        registro = registrar(proyecto, vigente.id, NORMALIZADO, token, despues(2))
        assert registro.estado is E.CONTEXTO


# ─── En cada estado del grafo ────────────────────────────────────────────────

# La acción humana que saca de cada parada; la que se interrumpe a medias.
_SALIDA_DE_LA_PARADA = {
    E.APROBACION_PLAN: AccionHumana.APROBAR_PLAN,
    E.APROBACION_FINAL: AccionHumana.APROBAR_FINAL,
    E.PUBLICADA: AccionHumana.PEDIR_CAMBIO,
    E.DETENIDA: AccionHumana.REINTENTAR,
}


def _filas(conexion: Any, tabla: str) -> int:
    return int(conexion.execute(f"SELECT count(*) FROM {tabla}").fetchone()[0])


def test_cada_estado_esta_cubierto() -> None:
    assert set(AGENTES_DEL_ESTADO) | set(_SALIDA_DE_LA_PARADA) == set(E)


@pytest.mark.parametrize("estado", sorted(AGENTES_DEL_ESTADO))
def test_morir_a_mitad_del_registro_en_cada_estado_con_agente(tmp_path: Path, estado: E) -> None:
    """La orden emitida sobrevive, lo escrito a medias por su manejador no, y una sesión
    nueva recibe la misma orden."""
    muerto = _matar_en(tmp_path, "en_estado", estado.value, "registrar")
    with abrir_proyecto(muerto["id"], tmp_path) as proyecto:
        leido = leer_estado(proyecto, despues(31))
        vigente = leido.orden_vigente
        assert leido.estado is estado
        assert vigente is not None
        assert (vigente.id, vigente.estado, vigente.intento) == (muerto["orden"], estado, 1)
        assert vigente.agente in AGENTES_DEL_ESTADO[estado]
        assert leido.intentos_paso == 0
        assert _filas(proyecto.conexion, "auditoria") == 0
        assert transiciones(proyecto.conexion) == []

        token = tomar_bloqueo(proyecto, TipoEjecutor.SESION, despues(31)).token
        reanudada = emitir_siguiente_orden(proyecto, token, despues(31))
        assert isinstance(reanudada, OrdenEmitida)
        assert (reanudada.id, reanudada.agente, reanudada.intento) == (
            vigente.id,
            vigente.agente,
            1,
        )


@pytest.mark.parametrize("parada", sorted(_SALIDA_DE_LA_PARADA))
def test_morir_a_mitad_de_la_accion_humana_en_cada_parada(tmp_path: Path, parada: E) -> None:
    """La acción humana va entera o no va: tras morir, el proyecto sigue en la parada, sin
    decisión ni transición registradas, y la misma acción lo saca de ella."""
    accion = _SALIDA_DE_LA_PARADA[parada]
    muerto = _matar_en(tmp_path, "en_estado", parada.value, accion.value)
    with abrir_proyecto(muerto["id"], tmp_path) as proyecto:
        leido = leer_estado(proyecto, despues(1))
        assert (leido.estado, leido.orden_vigente) == (parada, None)
        assert _filas(proyecto.conexion, "decision_humana") == 0
        assert transiciones(proyecto.conexion) == []
        assert decidir(proyecto, accion, despues(1)).estado is not parada
