// @ts-check
/**
 * El cliente HTTP común de la web: lo usan `lectura/`, `cambio/`, `metricas/` y `nueva/`,
 * cada una desde su propio `api.js`. Sigue spec-backend-1.md §5.1 y el modelo de error de TC-11.
 */

/** Vite reenvía /api al backend en desarrollo (vite.config.js). */
export const BASE = '/api'

export class ErrorApi extends Error {
  /**
   * @param {string} detalle lo que se enseña a la persona
   * @param {{ codigo?: string, requisito?: string | null, estado?: number }} [datos]
   */
  constructor(detalle, datos = {}) {
    super(detalle)
    this.name = 'ErrorApi'
    this.detalle = detalle
    this.codigo = datos.codigo ?? null
    this.requisito = datos.requisito ?? null
    this.estado = datos.estado ?? null
  }
}

/**
 * Una validación de FastAPI (422) trae `detail` como lista de errores de Pydantic.
 * @param {any} lista
 */
function detalleDeValidacion(lista) {
  if (!Array.isArray(lista) || lista.length === 0) return null
  return lista
    .slice(0, 3)
    .map((e) => `${Array.isArray(e.loc) ? e.loc.slice(1).join(' › ') : ''}: ${e.msg}`)
    .join(' · ')
}

/**
 * @param {string} ruta sin barra inicial
 * @param {{ senal?: AbortSignal, metodo?: string, cuerpo?: unknown }} [opciones]
 */
export async function pedir(ruta, { senal, metodo = 'GET', cuerpo } = {}) {
  let respuesta
  try {
    respuesta = await fetch(`${BASE}/${ruta}`, {
      method: metodo,
      signal: senal,
      headers: cuerpo === undefined ? { Accept: 'application/json' } : { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    })
  } catch (error) {
    if (senal?.aborted) throw error
    throw new ErrorApi('No se ha podido conectar con el servidor. Comprueba que el backend está arrancado.', {
      codigo: 'sin_conexion',
    })
  }
  if (!respuesta.ok) {
    const leido = await respuesta.json().catch(() => null)
    // TC-11: {codigo, requisito, detalle}, suelto o dentro del «detail» de FastAPI.
    const error = leido?.detalle ? leido : leido?.detail
    const detalle =
      typeof error?.detalle === 'string'
        ? error.detalle
        : (detalleDeValidacion(leido?.detail) ?? `El servidor respondió con el estado ${respuesta.status}.`)
    throw new ErrorApi(detalle, { codigo: error?.codigo, requisito: error?.requisito, estado: respuesta.status })
  }
  return respuesta.status === 204 ? null : respuesta.json()
}
