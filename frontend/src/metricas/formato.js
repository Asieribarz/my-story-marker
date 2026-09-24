// @ts-check
/** Cómo se escriben las cifras de las métricas. */

const ENTERO = new Intl.NumberFormat('es-ES')
const COMPACTO = new Intl.NumberFormat('es-ES', { notation: 'compact', maximumFractionDigits: 1 })

/** @param {number} n */
export const entero = (n) => ENTERO.format(n)

/** @param {number} n */
export const compacto = (n) => COMPACTO.format(n)

/**
 * 45 s · 12 min · 3 h 05 min · 2 d 4 h
 * @param {number} segundos
 */
export function duracion(segundos) {
  const s = Math.max(0, Math.round(segundos))
  if (s < 60) return `${s} s`
  const min = Math.floor(s / 60)
  if (min < 60) return `${min} min`
  const h = Math.floor(min / 60)
  if (h < 48) return `${h} h ${String(min % 60).padStart(2, '0')} min`
  return `${Math.floor(h / 24)} d ${h % 24} h`
}

/** @param {{ tokens_entrada: number, tokens_salida: number, tokens_cache_creacion: number, tokens_cache_lectura: number }} c */
export const tokensTotales = (c) => c.tokens_entrada + c.tokens_salida + c.tokens_cache_creacion + c.tokens_cache_lectura

/**
 * `claude-haiku-4-5-20251001` → `haiku-4-5`: sin el prefijo común ni la fecha de la versión.
 * @param {string} modelo
 */
export const modeloCorto = (modelo) => modelo.replace(/^claude-/, '').replace(/-\d{8}$/, '')
