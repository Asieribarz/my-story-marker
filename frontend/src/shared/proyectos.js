// @ts-check
/**
 * La lista de proyectos que comparten las tres ventanas (GET /proyectos) y cómo se nombra
 * cada estado del grafo ante la persona.
 */

import { pedir } from './api.js'

/**
 * @typedef {{ identificador: string, etiqueta: string | null, estado: string, creado: string, versiones: number, titulo: string | null }} ProyectoListado
 */

/**
 * @param {AbortSignal} [senal]
 * @returns {Promise<{ proyectos: ProyectoListado[] }>}
 */
export function obtenerProyectos(senal) {
  return pedir('proyectos', { senal })
}

/** @type {Record<string, string>} */
export const NOMBRE_DE_ESTADO = {
  intake: 'Recogiendo el brief',
  contexto: 'Validando el contexto',
  planificacion: 'Planificando',
  aprobacion_plan: 'Esperando tu aprobación del plan',
  escaleta: 'Escribiendo la escaleta',
  capitulos: 'Escribiendo capítulos',
  verificacion_manuscrito: 'Verificando el manuscrito',
  revision: 'Revisando',
  aprobacion_final: 'Esperando tu aprobación final',
  publicacion: 'Publicando',
  publicada: 'Publicada',
  cambio_solicitado: 'Interpretando un cambio',
  regeneracion: 'Regenerando',
  detenida: 'Detenida',
}

/** @param {string} estado */
export function nombreDeEstado(estado) {
  return NOMBRE_DE_ESTADO[estado] ?? estado
}

/** @param {string} instante ISO-8601 */
export function fechaCorta(instante) {
  const fecha = new Date(instante)
  return Number.isNaN(fecha.getTime())
    ? instante
    : fecha.toLocaleString('es-ES', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

/**
 * El título de la última versión publicada; si no la hay, la etiqueta que se puso al crear.
 * Sin ninguna de las dos, la fecha y el principio del identificador, que es el prefijo que
 * acepta `/generar`.
 * @param {ProyectoListado} p
 */
export function nombreDeProyecto(p) {
  return p.titulo ?? p.etiqueta ?? `Sin título · ${fechaCorta(p.creado)} · ${p.identificador.slice(0, 6)}`
}
