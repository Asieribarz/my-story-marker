"""El objeto de contexto: las 9 dimensiones de definitions.md como modelos Pydantic v2.

Fuente única del esquema (D-4). Aquí van los tipos y los valores permitidos (RF-20, RF-23,
RF-27): lo que se puede comprobar mirando un campo. Las reglas que cruzan campos —las
coherencias de definitions.md §10 y el resto de RF-24/RF-25— viven en `validacion.py`,
para que el informe las recoja todas en vez de pararse en la primera.

Todo modelo prohíbe claves desconocidas: los datos excluidos de definitions.md §9
(documento de identidad, teléfono, email…) no son claves del contexto y se rechazan.
"""

import re
from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

VERSION_ONTOLOGIA = "1.0.0"


class Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Texto = Annotated[str, Field(min_length=1)]
Nivel = Annotated[int, Field(ge=0, le=2)]
Capitulo = Annotated[int, Field(ge=1, le=10)]

# ─── §9 Personalización ──────────────────────────────────────────────────────


class Papel(StrEnum):
    PROTAGONISTA = "protagonista"
    COPROTAGONISTA = "coprotagonista"
    SECUNDARIO_CLAVE = "secundario_clave"


class Ocasion(StrEnum):
    CUMPLEANOS = "cumpleanos"
    BODA = "boda"
    ANIVERSARIO = "aniversario"
    JUBILACION = "jubilacion"
    NACIMIENTO = "nacimiento"
    GRADUACION = "graduacion"
    SIN_OCASION = "sin_ocasion"


class Relacion(StrEnum):
    HIJO = "hijo"
    PAREJA = "pareja"
    PADRE_MADRE = "padre_madre"
    ABUELO = "abuelo"
    AMIGO = "amigo"
    COMPANERO = "companero"
    OTRA = "otra"


class TipoHecho(StrEnum):
    EVENTO = "evento"
    RASGO = "rasgo"
    SER_QUERIDO = "ser_querido"
    LUGAR = "lugar"
    OBJETO = "objeto"
    FRASE = "frase"


class Prioridad(StrEnum):
    OBLIGATORIO = "obligatorio"
    DESEABLE = "deseable"


class OrigenHecho(StrEnum):
    ENTREVISTA = "entrevista"
    TEXTO_LIBRE = "texto_libre"
    LECTOR = "lector"


_FECHA_PARCIAL = re.compile(r"\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?")
_PERIODO = re.compile(r"[a-z][a-z_]*")


def es_fecha(momento: str) -> bool:
    """Un momento con fecha (`AAAA`, `AAAA-MM`, `AAAA-MM-DD`), no un periodo aproximado."""
    return _FECHA_PARCIAL.fullmatch(momento) is not None


class Destinatario(Modelo):
    nombre: Texto
    fecha_nacimiento: date | None = None
    edad: Annotated[int, Field(ge=0, le=120)] | None = None
    rasgos: tuple[Texto, ...] = ()
    # Sin valor por defecto en el modelo: lo rellena `validacion.py` y lo declara (RF-26).
    papel: Papel


class Hecho(Modelo):
    id: Annotated[str, Field(pattern=r"^[a-z0-9_]{1,32}$")]
    tipo: TipoHecho
    texto: Texto
    prioridad: Prioridad
    origen: OrigenHecho
    # Solo los `evento`: fecha (`AAAA`, `AAAA-MM`, `AAAA-MM-DD`) o periodo (`infancia`…).
    momento: str | None = None
    lugar: str | None = None

    @field_validator("momento", mode="before")
    @classmethod
    def _momento(cls, valor: object) -> object:
        if isinstance(valor, date):
            return valor.isoformat()
        if isinstance(valor, str) and not (es_fecha(valor) or _PERIODO.fullmatch(valor)):
            raise ValueError("fecha AAAA, AAAA-MM o AAAA-MM-DD, o un periodo como `infancia`")
        return valor


class TextoLibre(Modelo):
    ref: Texto
    confiable: Literal[False] = False


class Vetos(Modelo):
    palabras: tuple[Texto, ...] = ()
    temas: tuple[Texto, ...] = ()


class Personalizacion(Modelo):
    destinatario: Destinatario
    segundo_destinatario: Destinatario | None = None
    ocasion: Ocasion
    relacion: Relacion
    edad_lector: Annotated[int, Field(ge=0, le=120)]
    hechos: tuple[Hecho, ...] = ()
    texto_libre: TextoLibre | None = None
    vetos: Vetos = Vetos()
    dedicatoria: str | None = None


# ─── §2 Tipo de aventura y tono ──────────────────────────────────────────────


class Subgenero(StrEnum):
    EXPEDICION = "expedicion"
    NAUTICA = "nautica"
    CAPA_Y_ESPADA = "capa_y_espada"
    TESORO = "tesoro"
    FANTASIA_EPICA = "fantasia_epica"
    CIENCIA_FICCION = "ciencia_ficcion"
    STEAMPUNK = "steampunk"
    URBANA = "urbana"
    ROAD_NOVEL = "road_novel"


class Tono(StrEnum):
    EPICO = "epico"
    LIGERO = "ligero"
    PULP = "pulp"
    MELANCOLICO = "melancolico"


class Publico(StrEnum):
    INFANTIL = "infantil"
    JUVENIL = "juvenil"
    ADULTO = "adulto"
    CROSSOVER = "crossover"


class Mision(StrEnum):
    RESCATE = "rescate"
    BUSQUEDA = "busqueda"
    DESCUBRIMIENTO = "descubrimiento"
    CARRERA = "carrera"
    PROTECCION = "proteccion"


class ConflictoExterno(StrEnum):
    NATURALEZA = "persona_vs_naturaleza"
    PERSONA = "persona_vs_persona"
    SOCIEDAD = "persona_vs_sociedad"
    DESCONOCIDO = "persona_vs_desconocido"


class Subgeneros(Modelo):
    primario: Subgenero
    secundarios: Annotated[tuple[Subgenero, ...], Field(max_length=2)] = ()


class MacGuffin(Modelo):
    nombre: Texto
    descripcion: Texto
    por_que_importa: Texto


class Conflicto(Modelo):
    externo: Annotated[tuple[ConflictoExterno, ...], Field(min_length=1)]
    interno: Texto


class Contenido(Modelo):
    """Nivel 0-2 por categoría: el nivel 3 no existe en este producto (RF-25)."""

    violencia: Nivel
    romance: Nivel
    lenguaje: Nivel
    sensibles: Nivel


class TipoAventura(Modelo):
    subgenero: Subgeneros
    mision: Mision
    macguffin: MacGuffin
    conflicto: Conflicto
    contenido: Contenido


# ─── §3 Formato y longitud ───────────────────────────────────────────────────


class Cierre(StrEnum):
    CLIFFHANGER = "cliffhanger"
    PAUSA = "pausa"
    GIRO = "giro"
    PREGUNTA = "pregunta"
    IMAGEN = "imagen"


class Cronologia(StrEnum):
    LINEAL = "lineal"
    ANALEPSIS = "analepsis"


class LongitudCapitulo(Modelo):
    """RF-27: igual para todos los públicos, fija en [1000, 1500]."""

    min: Literal[1000]
    max: Literal[1500]


class Formato(Modelo):
    palabras_objetivo: Annotated[int, Field(ge=10_000, le=15_000)]
    tolerancia: Annotated[int, Field(ge=0, le=100)] | None = None
    capitulos: Literal[10]
    longitud_capitulo: LongitudCapitulo
    cierre_capitulo: Cierre | Annotated[tuple[Cierre, ...], Field(min_length=10, max_length=10)]
    titulacion: Texto
    cronologia: Cronologia
    curva_tension: Annotated[
        tuple[Annotated[int, Field(ge=0, le=10)], ...], Field(min_length=10, max_length=10)
    ]


# ─── §1 Estructura narrativa ─────────────────────────────────────────────────


class ModeloEstructural(StrEnum):
    TRES_ACTOS = "tres_actos"
    VIAJE_HEROE = "viaje_heroe"
    EPISODICO = "episodico"


class TipoFinal(StrEnum):
    CERRADO = "cerrado"
    ABIERTO = "abierto"
    AGRIDULCE = "agridulce"
    GANCHO_SAGA = "gancho_saga"
    GIRO_FINAL = "giro_final"


Tramo = Annotated[tuple[Capitulo, Capitulo], Field(description="Primer y último capítulo")]
Porcentaje = Annotated[int, Field(ge=0, le=100)]


class Planteamiento(Modelo):
    capitulos: Tramo
    porcentaje: Porcentaje
    detonante: Texto


class Nudo(Modelo):
    capitulos: Tramo
    porcentaje: Porcentaje
    punto_medio: Capitulo
    crisis: Capitulo


class Desenlace(Modelo):
    capitulos: Tramo
    porcentaje: Porcentaje
    climax: Capitulo
    final: TipoFinal


class Estructura(Modelo):
    modelo: ModeloEstructural
    planteamiento: Planteamiento
    nudo: Nudo
    desenlace: Desenlace


# ─── §4 Personajes ───────────────────────────────────────────────────────────


class Rol(StrEnum):
    PROTAGONISTA = "protagonista"
    ANTAGONISTA = "antagonista"
    MENTOR = "mentor"
    ALIADO = "aliado"
    ALIVIO_COMICO = "alivio_comico"
    INTERES_ROMANTICO = "interes_romantico"
    GUARDIAN_UMBRAL = "guardian_umbral"
    TRAIDOR = "traidor"
    SECUNDARIO = "secundario"


class Arco(StrEnum):
    POSITIVO = "positivo"
    NEGATIVO = "negativo"
    PLANO = "plano"
    REDENCION = "redencion"
    CORRUPCION = "corrupcion"


class Tratamiento(StrEnum):
    TU = "tu"
    USTED = "usted"
    VOS = "vos"


class Registro(StrEnum):
    CULTO = "culto"
    ESTANDAR = "estandar"
    COLOQUIAL = "coloquial"
    ARCAIZANTE = "arcaizante"


class OrigenPersonaje(Modelo):
    """`real` con `fuente`: `destinatario`, `segundo_destinatario` o el id de un hecho."""

    tipo: Literal["real", "ficticio"]
    fuente: str | None = None


class Voz(Modelo):
    registro: Registro | None = None
    tratamiento: Tratamiento | None = None
    muletillas: tuple[Texto, ...] = ()


class Evolucion(Modelo):
    creencia_inicial: Texto
    conducta_inicial: Texto
    creencia_final: Texto
    conducta_final: Texto
    momento_cambio: Capitulo
    detonante: Texto
    que_cambia: Annotated[tuple[Texto, ...], Field(min_length=2)]


class Personaje(Modelo):
    id: Annotated[str, Field(pattern=r"^[a-z0-9_]{1,32}$")]
    origen: OrigenPersonaje
    rol: Annotated[tuple[Rol, ...], Field(min_length=1)]
    deseo: str | None = None
    necesidad: str | None = None
    herida: str | None = None
    defecto: str | None = None
    arco: Arco
    voz: Voz | None = None
    evolucion: Evolucion | None = None


# ─── §5 Espacios y mundo ─────────────────────────────────────────────────────


class TipoMundo(StrEnum):
    REAL_HISTORICO = "real_historico"
    CONTEMPORANEO = "contemporaneo"
    ALTERNATIVO = "alternativo"
    SECUNDARIO = "secundario"
    FUTURO = "futuro"


class NivelEspacial(StrEnum):
    MACRO = "macro"
    MESO = "meso"
    MICRO = "micro"


class Epoca(Modelo):
    fecha_inicio: int | Texto
    duracion_historia: Texto


class Localizacion(Modelo):
    id: Annotated[str, Field(pattern=r"^[a-z0-9_]{1,32}$")]
    nivel: NivelEspacial
    padre: str | None = None


class Etapa(Modelo):
    id: str
    dias_viaje: Annotated[int, Field(ge=0)]


class ReglaMundo(Modelo):
    regla: Texto
    limites: Texto
    costes: Texto
    excepciones: tuple[Texto, ...] = ()


class Mundo(Modelo):
    tipo: TipoMundo
    epoca: Epoca
    localizaciones: Annotated[tuple[Localizacion, ...], Field(min_length=1)]
    ruta: Annotated[tuple[Etapa, ...], Field(min_length=2)]
    reglas: tuple[ReglaMundo, ...] = ()
    peligros: tuple[Texto, ...] = ()


# ─── §6 Lenguaje y estilo ────────────────────────────────────────────────────


class Narrador(StrEnum):
    PRIMERA = "primera"
    TERCERA_LIMITADA = "tercera_limitada"
    TERCERA_OMNISCIENTE = "tercera_omnisciente"
    MULTIPLE = "multiple"


class TiempoVerbal(StrEnum):
    PRETERITO = "preterito"
    PRESENTE = "presente"


class Dialogo(Modelo):
    proporcion: Porcentaje
    convencion: Literal["raya", "comillas"]
    tratamiento: Tratamiento | None = None


class Lenguaje(Modelo):
    idioma: Literal["es-ES"]
    narrador: Narrador
    tiempo: TiempoVerbal
    registro: Registro
    voz: Texto
    dialogo: Dialogo
    lexico: tuple[Texto, ...] = ()
    prohibidas: tuple[Texto, ...] = ()


# ─── §7 Temas y §8 Control ───────────────────────────────────────────────────


class Tema(Modelo):
    central: Texto
    pregunta_dramatica: Texto
    subtemas: tuple[Texto, ...] = ()
    mensaje: str | None = None


class Control(Modelo):
    validaciones: tuple[Texto, ...] = ()
    lineas_rojas: tuple[Texto, ...] = ()


# ─── Raíz ────────────────────────────────────────────────────────────────────


class Novela(Modelo):
    personalizacion: Personalizacion
    publico: Publico
    tono: Tono
    tipo_aventura: TipoAventura
    formato: Formato
    estructura: Estructura
    personajes: Annotated[tuple[Personaje, ...], Field(min_length=1)]
    mundo: Mundo
    lenguaje: Lenguaje
    tema: Tema
    control: Control = Control()


class Contexto(Modelo):
    """Raíz del objeto de contexto, con la clave `novela` de definitions.md §12."""

    novela: Novela
