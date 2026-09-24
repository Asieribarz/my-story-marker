"""El panel (`panel.py`): `GET /proyectos` y `GET /proyectos/{id}/metricas`.

Cada regla tiene una prueba que la dispara y su control (spec-backend-2 R-5). Todos los
datos de persona son ficticios (`apoyo.py`).
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from backend.proyecto.tests.apoyo import BRIEF, MOMENTO, NORMALIZADO
from backend.proyecto.tests.cliente_api import ClienteApi, cliente_api, error
from backend.shared.rutas import METADATOS

META = {"modelo": "sonnet", "tokens_entrada": 1000, "tokens_salida": 200, "duracion_ms": 4000}


@pytest.fixture
def api(tmp_path: Path) -> Iterator[ClienteApi]:
    with cliente_api(tmp_path) as cliente:
        yield cliente


def _metricas(api: ClienteApi, proyecto: str) -> dict[str, Any]:
    respuesta = api.http.get(f"/proyectos/{proyecto}/metricas")
    assert respuesta.status_code == 200, respuesta.text
    cuerpo: dict[str, Any] = respuesta.json()
    return cuerpo


# ─── Lista ───────────────────────────────────────────────────────────────────


def test_sin_proyectos_la_lista_esta_vacia(api: ClienteApi) -> None:
    assert api.http.get("/proyectos").json() == {"proyectos": []}


def test_lista_los_proyectos_del_mas_reciente_al_mas_antiguo(api: ClienteApi) -> None:
    primero = api.crear()
    api.reloj.avanzar(5)
    segundo = api.crear()
    filas = api.http.get("/proyectos").json()["proyectos"]
    assert [f["identificador"] for f in filas] == [segundo, primero]
    assert filas[1] == {
        "identificador": primero,
        "grupo": "novelas",
        "etiqueta": None,
        "estado": "intake",
        "creado": MOMENTO,
        "versiones": 0,
        "titulo": None,
    }


def test_no_lista_lo_que_no_es_un_proyecto(api: ClienteApi) -> None:
    proyecto = api.crear()
    novelas = api.raiz / "novelas"
    (novelas / ("a" * 32)).mkdir()  # identificador válido, sin base
    (novelas / "notas").mkdir()  # identificador no válido
    (novelas / ("b" * 32)).write_text("", encoding="utf-8")  # fichero, no carpeta
    filas = api.http.get("/proyectos").json()["proyectos"]
    assert [f["identificador"] for f in filas] == [proyecto]


def test_la_etiqueta_de_la_creacion_sale_en_la_lista(api: ClienteApi) -> None:
    respuesta = api.http.post("/proyectos", json={"etiqueta": "  Regalo de prueba  "})
    assert respuesta.status_code == 201, respuesta.text
    [fila] = api.http.get("/proyectos").json()["proyectos"]
    assert fila["etiqueta"] == "Regalo de prueba"


def test_un_proyecto_de_evaluacion_queda_en_evals(api: ClienteApi) -> None:
    creado = api.http.post("/proyectos", json={"grupo": "evals"}).json()["identificador"]
    novela = api.crear()
    assert (api.raiz / "evals" / creado / "proyecto.sqlite").is_file()
    assert (api.raiz / "novelas" / novela / "proyecto.sqlite").is_file()
    grupos = {
        f["identificador"]: f["grupo"] for f in api.http.get("/proyectos").json()["proyectos"]
    }
    assert grupos == {creado: "evals", novela: "novelas"}
    assert api.estado(creado)["estado"] == "intake"


@pytest.mark.parametrize("grupo", ["", "otro", "../evals", "Evals"])
def test_un_grupo_desconocido_se_rechaza(api: ClienteApi, grupo: str) -> None:
    assert error(api.http.post("/proyectos", json={"grupo": grupo}))[:2] == (422, "validacion")


@pytest.mark.parametrize("etiqueta", ["", "   ", "x" * 61, "dos\nlíneas", "tab\tulador"])
def test_una_etiqueta_invalida_se_rechaza(api: ClienteApi, etiqueta: str) -> None:
    respuesta = api.http.post("/proyectos", json={"etiqueta": etiqueta})
    assert error(respuesta)[:2] == (422, "validacion")
    assert api.http.get("/proyectos").json() == {"proyectos": []}


def test_una_etiqueta_de_sesenta_caracteres_se_acepta(api: ClienteApi) -> None:
    assert api.http.post("/proyectos", json={"etiqueta": "x" * 60}).status_code == 201


def test_una_base_sin_columna_de_etiqueta_se_lista_sin_ella(api: ClienteApi) -> None:
    proyecto = api.crear()
    with api.abrir(proyecto) as abierto:
        abierto.conexion.execute("ALTER TABLE proyecto DROP COLUMN etiqueta")
    [fila] = api.http.get("/proyectos").json()["proyectos"]
    assert (fila["identificador"], fila["etiqueta"]) == (proyecto, None)


def _publicar_a_mano(api: ClienteApi, proyecto: str, metadatos: str | None) -> None:
    with api.abrir(proyecto) as abierto:
        abierto.conexion.execute(
            "INSERT INTO version_novela (numero, publicada) VALUES (1, ?)", (MOMENTO,)
        )
        if metadatos is not None:
            ruta = abierto.disposicion.fichero_de_version(1, METADATOS)
            ruta.parent.mkdir(parents=True)
            ruta.write_text(metadatos, encoding="utf-8")


def test_el_titulo_es_el_de_la_ultima_version(api: ClienteApi) -> None:
    proyecto = api.crear()
    _publicar_a_mano(api, proyecto, json.dumps({"titulo": "El faro de papel"}))
    fila = api.http.get("/proyectos").json()["proyectos"][0]
    assert (fila["versiones"], fila["titulo"]) == (1, "El faro de papel")


@pytest.mark.parametrize("metadatos", [None, "no es json", "[]", '{"titulo": 3}'])
def test_sin_metadatos_legibles_no_hay_titulo(api: ClienteApi, metadatos: str | None) -> None:
    proyecto = api.crear()
    _publicar_a_mano(api, proyecto, metadatos)
    fila = api.http.get("/proyectos").json()["proyectos"][0]
    assert (fila["versiones"], fila["titulo"]) == (1, None)


# ─── Métricas ────────────────────────────────────────────────────────────────


def test_metricas_de_un_proyecto_inexistente(api: ClienteApi) -> None:
    respuesta = api.http.get(f"/proyectos/{'0' * 32}/metricas")
    assert error(respuesta)[:2] == (404, "proyecto_inexistente")


def test_un_proyecto_recien_creado_no_tiene_consumo(api: ClienteApi) -> None:
    proyecto = api.crear()
    api.reloj.avanzar(3)
    cuerpo = _metricas(api, proyecto)
    resumen = cuerpo["resumen"]
    assert (resumen["estado"], resumen["duracion_s"]) == ("intake", 180)
    assert resumen["intentos"] == {
        "ordenes": 0,
        "aceptadas": 0,
        "rechazadas": 0,
        "caducadas": 0,
        "reintentos": 0,
    }
    assert resumen["consumo"]["tokens_entrada"] == 0
    assert cuerpo["fases"] == [
        {"fase": "intake", "entradas": 1, "duracion_s": 180, "en_curso": True}
    ]
    assert (cuerpo["agentes"], cuerpo["capitulos"], cuerpo["juez"]) == ([], [], None)


def test_un_reintento_cuenta_y_suma_su_consumo(api: ClienteApi) -> None:
    proyecto = api.crear()
    token = api.tomar(proyecto)
    api.siguiente(proyecto, token)
    assert api.enviar_brief(proyecto, BRIEF).status_code == 200
    primera = api.orden(proyecto, token)
    fallida = api.registrar(proyecto, token, primera["id"], "sin bloque JSON", META)
    assert fallida.json()["desenlace"] == "rechazada"

    api.reloj.avanzar(10)
    segunda = api.orden(proyecto, token)
    assert segunda["intento"] == 2
    aceptada = api.registrar(proyecto, token, segunda["id"], NORMALIZADO, META)
    assert aceptada.json()["estado"] == "contexto"
    api.reloj.avanzar(2)

    cuerpo = _metricas(api, proyecto)
    [agente] = cuerpo["agentes"]
    assert agente["agente"] == "agente-contexto"
    assert agente["modelos"] == ["sonnet"]
    assert agente["intentos"] == {
        "ordenes": 2,
        "aceptadas": 1,
        "rechazadas": 1,
        "caducadas": 0,
        "reintentos": 1,
    }
    assert agente["consumo"] == {
        "tokens_entrada": 2000,
        "tokens_salida": 400,
        "tokens_cache_creacion": 0,
        "tokens_cache_lectura": 0,
        "duracion_ms": 8000,
        "con_metadatos": 2,
    }
    assert cuerpo["resumen"]["intentos"]["reintentos"] == 1
    assert cuerpo["fases"] == [
        {"fase": "intake", "entradas": 1, "duracion_s": 600, "en_curso": False},
        {"fase": "contexto", "entradas": 1, "duracion_s": 120, "en_curso": True},
    ]
    assert cuerpo["resumen"]["duracion_s"] == 720


def test_un_intento_sin_metadatos_no_suma_consumo(api: ClienteApi) -> None:
    proyecto = api.crear()
    token = api.tomar(proyecto)
    api.siguiente(proyecto, token)
    api.enviar_brief(proyecto, BRIEF)
    orden = api.orden(proyecto, token)
    api.aceptado(proyecto, token, orden["id"], NORMALIZADO)
    [agente] = _metricas(api, proyecto)["agentes"]
    assert agente["intentos"]["reintentos"] == 0
    assert (agente["consumo"]["con_metadatos"], agente["consumo"]["tokens_entrada"]) == (0, 0)
    assert agente["modelos"] == []


def test_publicada_la_duracion_acaba_en_la_publicacion(api: ClienteApi) -> None:
    proyecto = api.crear()
    with api.abrir(proyecto) as abierto:
        abierto.conexion.executemany(
            "INSERT INTO transicion (momento, origen, destino, causa) VALUES (?, ?, ?, 'prueba')",
            [
                ("2026-09-23T10:05:00Z", "intake", "publicacion"),
                ("2026-09-23T10:20:00Z", "publicacion", "publicada"),
            ],
        )
        abierto.conexion.execute("UPDATE proyecto SET estado = 'publicada'")
    api.reloj.avanzar(120)
    cuerpo = _metricas(api, proyecto)
    assert cuerpo["resumen"]["duracion_s"] == 1200
    assert cuerpo["fases"][-1] == {
        "fase": "publicada",
        "entradas": 1,
        "duracion_s": 0,
        "en_curso": False,
    }


def test_el_juez_es_la_ultima_evaluacion(api: ClienteApi) -> None:
    proyecto = api.crear()
    with api.abrir(proyecto) as abierto:
        abierto.conexion.executemany(
            "INSERT INTO informe_juez (evaluacion, version_novela, revisor, ciclo, criterio, "
            "puntuacion, justificacion, momento) VALUES (?, 1, ?, ?, ?, ?, 'ficticia', ?)",
            [
                ("vieja", "juez", 0, "tono", 2, "2026-09-23T10:00:00Z"),
                ("humana", "humano", 1, "tono", 1, "2026-09-23T12:00:00Z"),
                ("nueva", "juez", 1, "tono", 4, "2026-09-23T11:00:00Z"),
                ("nueva", "juez", 1, "continuidad", 5, "2026-09-23T11:00:00Z"),
            ],
        )
    assert _metricas(api, proyecto)["juez"] == {
        "version_novela": 1,
        "ciclo": 1,
        "puntuaciones": [
            {"criterio": "tono", "puntuacion": 4},
            {"criterio": "continuidad", "puntuacion": 5},
        ],
    }
