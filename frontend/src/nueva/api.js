// @ts-check
/**
 * Cliente de lo que la persona decide al crear y seguir una novela (spec-backend-1.md §5.1): crear
 * el proyecto, enviar el brief, confirmar hechos, las dos paradas y reintentar. Todas son
 * acciones humanas: ninguna exige el bloqueo (Q7). Generar encola un trabajo que el worker
 * del backend lanza con `claude -p`; en Claude Code, `/generar <proyecto>` hace lo mismo.
 */

import { pedir } from '../shared/api.js'

/** @param {string} proyecto */
const de = (proyecto) => `proyectos/${proyecto}`

/**
 * POST /proyectos (RF-01, RF-05)
 * @param {{ parada_plan: boolean, parada_final: boolean, etiqueta?: string }} pedido
 * @returns {Promise<{ identificador: string }>}
 */
export function crearProyecto(pedido) {
  return pedir('proyectos', { metodo: 'POST', cuerpo: pedido })
}

/**
 * POST /proyectos/{id}/brief (RF-10, RF-14). Volver a enviarlo sustituye el anterior.
 * @param {string} proyecto
 * @param {{ respuestas: Record<string, unknown>, texto_libre?: string }} cuerpo
 * @returns {Promise<{ descartes: { tipo: string, campo: string }[], texto_libre: boolean }>}
 */
export function enviarBrief(proyecto, cuerpo) {
  return pedir(`${de(proyecto)}/brief`, { metodo: 'POST', cuerpo })
}

/** GET /proyectos/{id}/estado (RF-02) @param {string} proyecto @param {AbortSignal} [senal] */
export function obtenerEstado(proyecto, senal) {
  return pedir(`${de(proyecto)}/estado`, { senal })
}

/** GET /proyectos/{id}/hechos (RF-15) @param {string} proyecto @param {AbortSignal} [senal] */
export function obtenerHechos(proyecto, senal) {
  return pedir(`${de(proyecto)}/hechos`, { senal })
}

/**
 * POST /proyectos/{id}/hechos/confirmacion (RF-15)
 * @param {string} proyecto @param {{ hecho: number, confirmado: boolean }[]} decisiones
 */
export function confirmarHechos(proyecto, decisiones) {
  return pedir(`${de(proyecto)}/hechos/confirmacion`, { metodo: 'POST', cuerpo: { decisiones } })
}

/** GET /proyectos/{id}/plan (RF-35) @param {string} proyecto @param {AbortSignal} [senal] */
export function obtenerPlan(proyecto, senal) {
  return pedir(`${de(proyecto)}/plan`, { senal })
}

/**
 * POST /proyectos/{id}/plan/aprobacion (RF-36)
 * @param {string} proyecto @param {'aprobado' | 'cambios'} decision @param {string | null} notas
 */
export function decidirPlan(proyecto, decision, notas) {
  return pedir(`${de(proyecto)}/plan/aprobacion`, { metodo: 'POST', cuerpo: { decision, notas } })
}

/**
 * POST /proyectos/{id}/aprobacion-final (RF-05, M-6)
 * @param {string} proyecto @param {'aprobado' | 'cambios'} decision @param {string | null} notas
 * @param {number[] | null} capitulos
 */
export function decidirFinal(proyecto, decision, notas, capitulos) {
  return pedir(`${de(proyecto)}/aprobacion-final`, { metodo: 'POST', cuerpo: { decision, notas, capitulos } })
}

/** POST /proyectos/{id}/reintentar (RF-64b) @param {string} proyecto @param {string | null} notas */
export function reintentar(proyecto, notas) {
  return pedir(`${de(proyecto)}/reintentar`, { metodo: 'POST', cuerpo: { notas } })
}

/**
 * POST /proyectos/{id}/generacion (TC-8): encola la generación, o devuelve el trabajo que ya
 * espera. 409 si el proyecto está en una parada que decide la persona.
 * @param {string} proyecto
 * @returns {Promise<{ trabajo: number }>}
 */
export function generar(proyecto) {
  return pedir(`${de(proyecto)}/generacion`, { metodo: 'POST' })
}
