// @ts-check
/**
 * Del formulario a las `respuestas` del brief (POST /brief), con las claves de la entrevista
 * de `/entrevista` y los valores permitidos de backend/contexto/modelos.py. El Agente de
 * contexto normaliza lo demás; lo que falte lo señala el validador.
 */

export const OCASIONES = [
  ['cumpleanos', 'Cumpleaños'],
  ['boda', 'Boda'],
  ['aniversario', 'Aniversario'],
  ['jubilacion', 'Jubilación'],
  ['nacimiento', 'Nacimiento'],
  ['graduacion', 'Graduación'],
  ['sin_ocasion', 'Sin ocasión'],
]

export const RELACIONES = [
  ['hijo', 'Hijo o hija'],
  ['pareja', 'Pareja'],
  ['padre_madre', 'Padre o madre'],
  ['abuelo', 'Abuelo o abuela'],
  ['amigo', 'Amistad'],
  ['companero', 'Compañero o compañera'],
  ['otra', 'Otra'],
]

export const PAPELES = [
  ['protagonista', 'Protagonista'],
  ['coprotagonista', 'Coprotagonista'],
  ['secundario_clave', 'Secundario clave'],
]

export const TIPOS_DE_HECHO = [
  ['evento', 'Un recuerdo (con cuándo y dónde)'],
  ['ser_querido', 'Una persona o animal querido'],
  ['lugar', 'Un lugar'],
  ['objeto', 'Un objeto'],
  ['frase', 'Una frase suya literal'],
  ['rasgo', 'Un rasgo'],
]

export const TONOS = [
  ['', 'Sin preferencia'],
  ['epico', 'Épico'],
  ['ligero', 'Ligero'],
  ['pulp', 'Pulp'],
  ['melancolico', 'Melancólico'],
]

export const SUBGENEROS = [
  ['', 'Sin preferencia'],
  ['expedicion', 'Expedición'],
  ['nautica', 'Náutica'],
  ['capa_y_espada', 'Capa y espada'],
  ['tesoro', 'Búsqueda del tesoro'],
  ['fantasia_epica', 'Fantasía épica'],
  ['ciencia_ficcion', 'Ciencia ficción'],
  ['steampunk', 'Steampunk'],
  ['urbana', 'Urbana'],
  ['road_novel', 'Road novel'],
]

/** Las ocasiones con dos destinatarios. */
export const CON_SEGUNDO = new Set(['boda', 'aniversario'])

export const destinatarioVacio = () => ({ nombre: '', fecha_nacimiento: '', edad: '', rasgos: '', papel: 'protagonista' })

let siguienteUid = 1
export const hechoVacio = () => ({
  uid: siguienteUid++,
  tipo: 'evento',
  texto: '',
  prioridad: 'obligatorio',
  momento: '',
  lugar: '',
})

/** @param {string} texto */
const lista = (texto) =>
  texto
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)

/** @param {string} valor */
const numero = (valor) => (valor === '' ? undefined : Number(valor))

/** @param {ReturnType<typeof destinatarioVacio>} d */
function destinatario(d) {
  return limpio({
    nombre: d.nombre.trim(),
    fecha_nacimiento: d.fecha_nacimiento || undefined,
    edad: numero(d.edad),
    rasgos: lista(d.rasgos),
    papel: d.papel,
  })
}

/**
 * Quita las claves sin valor: el brief solo lleva lo que la persona contestó.
 * @param {Record<string, unknown>} objeto
 */
function limpio(objeto) {
  return Object.fromEntries(Object.entries(objeto).filter(([, v]) => v !== undefined && v !== ''))
}

/**
 * @param {any} f el estado del formulario
 * @returns {Record<string, unknown>}
 */
export function respuestasDe(f) {
  const hechos = f.hechos
    .filter((h) => h.texto.trim())
    .map((h, i) =>
      limpio({
        id: `h${i + 1}`,
        tipo: h.tipo,
        texto: h.texto.trim(),
        prioridad: h.prioridad,
        origen: 'entrevista',
        momento: h.tipo === 'evento' ? h.momento.trim() || undefined : undefined,
        lugar: h.tipo === 'evento' ? h.lugar.trim() || undefined : undefined,
      }),
    )
  const preferencias = limpio({
    tono: f.tono || undefined,
    subgenero: f.subgenero ? { primario: f.subgenero } : undefined,
    final: f.final.trim() || undefined,
  })
  return {
    personalizacion: limpio({
      destinatario: destinatario(f.destinatario),
      segundo_destinatario: CON_SEGUNDO.has(f.ocasion) ? destinatario(f.segundo) : null,
      ocasion: f.ocasion,
      relacion: f.relacion,
      edad_lector: numero(f.edad_lector),
      hechos,
      vetos: { palabras: lista(f.vetos_palabras), temas: lista(f.vetos_temas) },
      dedicatoria: f.dedicatoria.trim() || undefined,
    }),
    ...(Object.keys(preferencias).length > 0 ? { preferencias } : {}),
  }
}
