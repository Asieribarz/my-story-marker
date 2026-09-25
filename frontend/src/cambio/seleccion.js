// @ts-check
/**
 * La selección del lector dentro del texto de un capítulo, anclada a los `data-p` de su
 * primer y último párrafo (plan-frontend.md §7, B-14). Fuera del texto no hay selección.
 */

/**
 * @param {Node | null} nodo
 * @returns {number | null}
 */
function parrafoDe(nodo) {
  const elemento = nodo instanceof Element ? nodo : (nodo?.parentElement ?? null)
  const parrafo = elemento?.closest('.texto [data-p]')
  const valor = Number(parrafo?.getAttribute('data-p'))
  return Number.isInteger(valor) && valor >= 1 ? valor : null
}

/**
 * @param {Selection | null} seleccion
 * @returns {{ fragmento: string, parrafos: [number, number] } | null}
 */
export function leerSeleccion(seleccion) {
  if (!seleccion || seleccion.isCollapsed || seleccion.rangeCount === 0) return null
  const fragmento = seleccion.toString().trim()
  if (!fragmento) return null
  const a = parrafoDe(seleccion.anchorNode)
  const b = parrafoDe(seleccion.focusNode)
  if (a === null || b === null) return null
  return { fragmento, parrafos: a <= b ? [a, b] : [b, a] }
}
