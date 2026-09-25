// @ts-check
/** Cliente de GET /proyectos/{id}/metricas (backend/proyecto/panel.py). */

import { pedir } from '../shared/api.js'

/**
 * @typedef {{ tokens_entrada: number, tokens_salida: number, tokens_cache_creacion: number,
 *   tokens_cache_lectura: number, duracion_ms: number, con_metadatos: number }} Consumo
 * @typedef {{ ordenes: number, aceptadas: number, rechazadas: number, caducadas: number, reintentos: number }} Intentos
 * @typedef {{
 *   resumen: { estado: string, creado: string, duracion_s: number, intentos: Intentos, consumo: Consumo,
 *     ciclos_revision: number, pasadas_manuscrito: number, versiones_publicadas: number },
 *   fases: { fase: string, entradas: number, duracion_s: number, en_curso: boolean }[],
 *   agentes: { agente: string, modelos: string[], intentos: Intentos, consumo: Consumo }[],
 *   capitulos: { capitulo: number, versiones: number, intentos: Intentos, consumo: Consumo }[],
 *   verificadores: { verificador: string, informes: number, hallazgos: number, graves: number }[],
 *   juez: { version_novela: number, ciclo: number, puntuaciones: { criterio: string, puntuacion: number }[] } | null,
 *   cambios: { pedidos: number, publicados: number, rechazados: number, fallidos: number, regeneraciones: number },
 * }} Metricas
 */

/**
 * @param {string} proyecto @param {AbortSignal} [senal]
 * @returns {Promise<Metricas>}
 */
export function obtenerMetricas(proyecto, senal) {
  return pedir(`proyectos/${proyecto}/metricas`, { senal })
}
