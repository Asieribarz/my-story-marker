// @ts-check
/**
 * Direcciones de la lectura detrás de «#» (specs/plan-frontend.md §4).
 *
 *   #/<proyecto>                     → la versión vigente
 *   #/<proyecto>/v<N>                → portada e índice
 *   #/<proyecto>/v<N>/cap/<n>        → capítulo
 *   #/<proyecto>/v<N>/fichas         → personajes y lugares
 */

/**
 * @typedef {{ pantalla: 'sin_proyecto' }
 *   | { pantalla: 'desconocida' }
 *   | { pantalla: 'vigente', proyecto: string }
 *   | { pantalla: 'portada', proyecto: string, version: number }
 *   | { pantalla: 'fichas', proyecto: string, version: number }
 *   | { pantalla: 'capitulo', proyecto: string, version: number, capitulo: number }} Ruta
 */

/** El identificador opaco de spec1.md §5.3. */
const PROYECTO = /^[0-9a-f]{32}$/
const VERSION = /^v([1-9]\d{0,5})$/
const NUMERO = /^[1-9]\d{0,5}$/

/** @type {Ruta} */
const DESCONOCIDA = { pantalla: 'desconocida' }

/**
 * @param {string} hash el de location.hash, con o sin «#»
 * @returns {Ruta}
 */
export function leerRuta(hash) {
  const cuerpo = hash.replace(/^#?\/?/, '').replace(/\/$/, '')
  if (cuerpo === '') return { pantalla: 'sin_proyecto' }

  const [proyecto, v, seccion, n, ...resto] = cuerpo.split('/')
  if (!PROYECTO.test(proyecto)) return DESCONOCIDA
  if (v === undefined) return { pantalla: 'vigente', proyecto }

  const marca = VERSION.exec(v)
  if (!marca) return DESCONOCIDA
  const version = Number(marca[1])

  if (seccion === undefined) return { pantalla: 'portada', proyecto, version }
  if (seccion === 'fichas' && n === undefined) return { pantalla: 'fichas', proyecto, version }
  if (seccion === 'cap' && n !== undefined && NUMERO.test(n) && resto.length === 0) {
    return { pantalla: 'capitulo', proyecto, version, capitulo: Number(n) }
  }
  return DESCONOCIDA
}

/**
 * @param {Ruta} ruta
 * @returns {string} el hash, con «#»
 */
export function escribirRuta(ruta) {
  switch (ruta.pantalla) {
    case 'vigente':
      return `#/${ruta.proyecto}`
    case 'portada':
      return `#/${ruta.proyecto}/v${ruta.version}`
    case 'fichas':
      return `#/${ruta.proyecto}/v${ruta.version}/fichas`
    case 'capitulo':
      return `#/${ruta.proyecto}/v${ruta.version}/cap/${ruta.capitulo}`
    default:
      return '#/'
  }
}
