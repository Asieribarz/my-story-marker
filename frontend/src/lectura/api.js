// @ts-check
/**
 * El único módulo cliente de la API de lectura (specs/plan-frontend.md F-3, §5.1).
 *
 * Nada más en la lectura sabe de dónde salen los datos: responden los ficheros de
 * fixture/, con la misma forma que export/vN/lectura.json, o la API real del backend
 * (FUENTE = 'api', la de uso), con el cliente común de shared/api.js.
 */

import { BASE, ErrorApi, pedir } from '../shared/api.js'

export { ErrorApi }

/** @typedef {import('./contrato.js').Lectura} Lectura */
/** @typedef {import('./contrato.js').Versiones} Versiones */
/** @typedef {import('./contrato.js').CapituloLectura} CapituloLectura */

const FUENTE = /** @type {'fixture' | 'api'} */ ('api')

/** El proyecto de los datos ficticios de fixture/. */
const PROYECTO_DEL_FIXTURE = '0123456789abcdef0123456789abcdef'

const ficheros = /** @type {Record<string, () => Promise<any>>} */ (
  import.meta.glob('./fixture/**/*.json', { import: 'default' })
)

/**
 * @param {string} proyecto
 * @param {string} fichero
 */
async function desdeFixture(proyecto, fichero) {
  const cargar = ficheros[`./fixture/${fichero}`]
  if (proyecto !== PROYECTO_DEL_FIXTURE) {
    throw new ErrorApi('No existe ninguna novela con ese enlace.', { codigo: 'no_encontrado', estado: 404 })
  }
  if (!cargar) throw new ErrorApi('Esa versión de la novela no existe.', { codigo: 'no_encontrado', estado: 404 })
  // Una copia, para que nadie modifique el módulo compartido por accidente.
  return structuredClone(await cargar())
}

/**
 * @param {string} ruta sin barra inicial
 * @param {AbortSignal} [senal]
 */
function desdeApi(ruta, senal) {
  return pedir(ruta, { senal })
}

/** El proyecto que se abre sin nada en la dirección: solo existe con el fixture. */
export function proyectoPorDefecto() {
  return FUENTE === 'fixture' ? PROYECTO_DEL_FIXTURE : null
}

/**
 * GET /proyectos/{id}/versiones
 * @param {string} proyecto @param {AbortSignal} [senal]
 * @returns {Promise<Versiones>}
 */
export function obtenerVersiones(proyecto, senal) {
  return FUENTE === 'fixture'
    ? desdeFixture(proyecto, 'versiones.json')
    : desdeApi(`proyectos/${proyecto}/versiones`, senal)
}

/**
 * GET /proyectos/{id}/versiones/{v}/lectura
 * @param {string} proyecto @param {number} version @param {AbortSignal} [senal]
 * @returns {Promise<Lectura>}
 */
export function obtenerLectura(proyecto, version, senal) {
  return FUENTE === 'fixture'
    ? desdeFixture(proyecto, `v${version}/lectura.json`)
    : desdeApi(`proyectos/${proyecto}/versiones/${version}/lectura`, senal)
}

/**
 * GET /proyectos/{id}/versiones/{v}/capitulos/{n}
 * @param {string} proyecto @param {number} version @param {number} numero @param {AbortSignal} [senal]
 * @returns {Promise<CapituloLectura>}
 */
export async function obtenerCapitulo(proyecto, version, numero, senal) {
  if (FUENTE === 'api') return desdeApi(`proyectos/${proyecto}/versiones/${version}/capitulos/${numero}`, senal)
  /** @type {Lectura} */
  const lectura = await desdeFixture(proyecto, `v${version}/lectura.json`)
  const capitulo = lectura.capitulos.find((c) => c.numero === numero)
  if (!capitulo) throw new ErrorApi('Esta versión no tiene ese capítulo.', { codigo: 'no_encontrado', estado: 404 })
  return capitulo
}

/**
 * GET /proyectos/{id}/versiones/{v}/pdf; el fixture no tiene PDF.
 * @param {string} proyecto @param {number} version
 * @returns {string | null}
 */
export function urlPdf(proyecto, version) {
  return FUENTE === 'api' ? `${BASE}/proyectos/${proyecto}/versiones/${version}/pdf` : null
}
