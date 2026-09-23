// @ts-check
/**
 * Filtro del HTML de capítulo (specs/plan-frontend.md F-6).
 *
 * Recorre un árbol ya analizado —en el navegador, el de DOMParser, que es inerte— y
 * devuelve una descripción con solo las etiquetas de la lista blanca, que Fragmento.jsx
 * pinta como elementos de React. Nunca se asigna HTML como cadena, así que lo que no está
 * en la lista no llega a existir: los atributos se pierden salvo data-p, una etiqueta
 * desconocida se desenvuelve y deja su texto, y las que llevan código se descartan enteras.
 */

import { ETIQUETAS_PERMITIDAS } from './contrato.js'

/**
 * Lo mínimo que se usa de un nodo del DOM; las pruebas lo construyen a mano.
 * @typedef {{
 *   nodeType: number,
 *   nodeName: string,
 *   nodeValue: string | null,
 *   childNodes: ArrayLike<NodoDom>,
 *   getAttribute?: (nombre: string) => string | null,
 * }} NodoDom
 */

/** @typedef {string | { etiqueta: string, p?: number, hijos: Nodo[] }} Nodo */

const TEXTO = 3
const ELEMENTO = 1
const PERMITIDAS = new Set(ETIQUETAS_PERMITIDAS)
const VACIAS = new Set(['hr', 'br'])
const DESCARTADAS = new Set([
  'script',
  'style',
  'template',
  'noscript',
  'iframe',
  'object',
  'embed',
  'svg',
  'math',
  'textarea',
  'select',
  'title',
])

/**
 * @param {NodoDom} raiz el body del documento analizado
 * @returns {Nodo[]}
 */
export function sanear(raiz) {
  return Array.from(raiz.childNodes).flatMap(nodo)
}

/**
 * @param {NodoDom} n
 * @returns {Nodo[]}
 */
function nodo(n) {
  if (n.nodeType === TEXTO) return n.nodeValue ? [n.nodeValue] : []
  if (n.nodeType !== ELEMENTO) return []

  const etiqueta = n.nodeName.toLowerCase()
  if (DESCARTADAS.has(etiqueta)) return []
  if (VACIAS.has(etiqueta)) return [{ etiqueta, hijos: [] }]

  const hijos = sanear(n)
  if (!PERMITIDAS.has(etiqueta)) return hijos
  if (etiqueta === 'p') {
    const p = Number(n.getAttribute?.('data-p'))
    return [Number.isInteger(p) && p > 0 ? { etiqueta, p, hijos } : { etiqueta, hijos }]
  }
  return [{ etiqueta, hijos }]
}
