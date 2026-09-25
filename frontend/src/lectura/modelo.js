// @ts-check
/**
 * Lo que la lectura deriva de los datos para pintarlos. Nada de esto es estado: se
 * calcula en cada render a partir de la lectura y las versiones.
 */

/** @typedef {import('./contrato.js').Versiones} Versiones */
/** @typedef {import('./contrato.js').Lugar} Lugar */

/**
 * La vigente es la última publicada (plan-frontend.md §5.3).
 * @param {Versiones} versiones
 */
export function versionVigente(versiones) {
  return versiones.versiones[versiones.versiones.length - 1].version
}

/**
 * «y» se vuelve «e» ante el sonido /i/ inicial: «aliado e interés romántico», pero
 * «hierba» o «hielo» mantienen la «y».
 * @param {string} siguiente
 */
export function conjuncion(siguiente) {
  return /^h?[ií](?![aeouáéóú])/i.test(siguiente) ? 'e' : 'y'
}

/**
 * El separador que va detrás de cada elemento de una enumeración: «1, 2 y 5».
 * @param {string[]} elementos
 * @returns {string[]}
 */
export function separadores(elementos) {
  const n = elementos.length
  return elementos.map((_, i) => {
    if (i === n - 1) return ''
    if (i === n - 2) return ` ${conjuncion(elementos[i + 1])} `
    return ', '
  })
}

/** @param {string[]} elementos */
export function enumerar(elementos) {
  const seps = separadores(elementos)
  return elementos.map((e, i) => e + seps[i]).join('')
}

const EN_LETRA = ['uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve', 'diez']

/**
 * «Capítulo tres», como en un libro; más allá de diez, en cifras.
 * @param {number} numero
 */
export function capituloEnLetra(numero) {
  return `Capítulo ${EN_LETRA[numero - 1] ?? numero}`
}

/** @type {Record<string, string>} */
const NOMBRES_DE_ROL = {
  alivio_comico: 'alivio cómico',
  interes_romantico: 'interés romántico',
  guardian_umbral: 'guardián del umbral',
}

/** @param {string[]} roles */
export function rolesLegibles(roles) {
  return enumerar(roles.map((r) => NOMBRES_DE_ROL[r] ?? r))
}

/**
 * Fecha legible en español. Una fecha sin hora se toma como fecha local, no como
 * medianoche UTC, para que «2026-09-20» no se lea «19 de septiembre» al oeste de Greenwich.
 * @param {string} iso
 */
export function fechaLegible(iso) {
  const soloFecha = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  const fecha = soloFecha
    ? new Date(Number(soloFecha[1]), Number(soloFecha[2]) - 1, Number(soloFecha[3]))
    : new Date(iso)
  return new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'long', year: 'numeric' }).format(
    fecha,
  )
}

/** @typedef {{ lugar: Lugar, hijos: NodoLugar[] }} NodoLugar */

/**
 * Los lugares anidados según padre, en el orden en que llegan. Un padre desconocido
 * cuelga el lugar de la raíz en vez de perderlo.
 * @param {Lugar[]} lugares
 * @returns {NodoLugar[]}
 */
export function arbolDeLugares(lugares) {
  /** @type {Map<string, NodoLugar>} */
  const nodos = new Map(lugares.map((l) => [l.id, { lugar: l, hijos: [] }]))
  /** @type {NodoLugar[]} */
  const raices = []
  for (const l of lugares) {
    const nodo = /** @type {NodoLugar} */ (nodos.get(l.id))
    const padre = l.padre === null ? undefined : nodos.get(l.padre)
    if (padre && padre !== nodo) padre.hijos.push(nodo)
    else raices.push(nodo)
  }
  return raices
}
