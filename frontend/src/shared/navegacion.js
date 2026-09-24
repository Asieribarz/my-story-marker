// @ts-check
/**
 * Las tres ventanas de la web detrás de «#» (plan-frontend.md §4). La lectura conserva
 * sus direcciones (`#/<proyecto>/…`, lectura/ruta.js); las otras dos llevan prefijo:
 *
 *   #/metricas                → métricas, sin proyecto elegido
 *   #/metricas/<proyecto>     → métricas de un proyecto
 *   #/nueva                   → el formulario de una novela nueva
 *   #/nueva/<proyecto>        → el seguimiento de un proyecto
 *
 * Un identificador de proyecto son 32 hexadecimales, así que «metricas» y «nueva» nunca
 * se confunden con uno.
 */

/** @typedef {'leer' | 'metricas' | 'nueva'} Pestana */
/** @typedef {{ pestana: Pestana, proyecto: string | null }} Ventana */

const PROYECTO = /^[0-9a-f]{32}$/

/**
 * @param {string} hash el de location.hash, con o sin «#»
 * @returns {Ventana}
 */
export function leerVentana(hash) {
  const partes = hash.replace(/^#?\/?/, '').replace(/\/$/, '').split('/')
  const [primera, segunda, ...resto] = partes
  if (primera === 'metricas' || primera === 'nueva') {
    const proyecto = segunda !== undefined && PROYECTO.test(segunda) && resto.length === 0 ? segunda : null
    return { pestana: primera, proyecto }
  }
  return { pestana: 'leer', proyecto: PROYECTO.test(primera ?? '') ? primera : null }
}

/**
 * @param {Pestana} pestana
 * @param {string | null} proyecto
 * @returns {string} el hash, con «#»
 */
export function escribirVentana(pestana, proyecto) {
  if (pestana === 'leer') return proyecto ? `#/${proyecto}` : '#/'
  return proyecto ? `#/${pestana}/${proyecto}` : `#/${pestana}`
}
