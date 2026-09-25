// @ts-check
/**
 * Cliente de las rutas de cambio (spec-backend-1.md §5.1, TC-12; plan-frontend.md §7). La petición
 * del lector se envía y ninguna respuesta la devuelve (V-29).
 */

import { pedir } from '../shared/api.js'

/**
 * @typedef {'interpretando' | 'propuesto' | 'obsoleto' | 'rechazado' | 'regenerando' | 'fallido' | 'publicado'} EstadoCambio
 * @typedef {{ tipo: 'cambio' | 'nuevo', hecho: string, valor_anterior: string | null, valor_nuevo: string }} Propuesta
 * @typedef {{ id: number, estado: EstadoCambio, version: number, capitulo: number, parrafos: [number, number] | null,
 *   propuesta: Propuesta | null, capitulos: number[], version_nueva: number | null, motivo: string | null }} Cambio
 */

/** Lo que admite el backend en fragmento y petición (`TOPE_PETICION`). */
export const TOPE = 4000

/** @param {string} proyecto */
const base = (proyecto) => `proyectos/${proyecto}/cambios`

/**
 * POST /proyectos/{id}/cambios (RF-120)
 * @param {string} proyecto
 * @param {{ version: number, capitulo: number, fragmento: string, parrafos: [number, number] | null, peticion: string }} cuerpo
 * @returns {Promise<Cambio>}
 */
export function pedirCambio(proyecto, cuerpo) {
  return pedir(base(proyecto), { metodo: 'POST', cuerpo })
}

/**
 * GET /proyectos/{id}/cambios/{c}
 * @param {string} proyecto @param {number} cambio @param {AbortSignal} [senal]
 * @returns {Promise<Cambio>}
 */
export function obtenerCambio(proyecto, cambio, senal) {
  return pedir(`${base(proyecto)}/${cambio}`, { senal })
}

/**
 * POST /proyectos/{id}/cambios/{c}/confirmacion (RF-122)
 * @param {string} proyecto @param {number} cambio @param {boolean} confirmado
 * @returns {Promise<Cambio>}
 */
export function decidirCambio(proyecto, cambio, confirmado) {
  return pedir(`${base(proyecto)}/${cambio}/confirmacion`, {
    metodo: 'POST',
    cuerpo: { decision: confirmado ? 'confirmado' : 'rechazado' },
  })
}
