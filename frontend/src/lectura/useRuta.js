import { useHash } from '../shared/useHash.js'
import { escribirRuta, leerRuta } from './ruta.js'

/** La ruta de la dirección actual; se vuelve a leer en cada cambio de «#». */
export function useRuta() {
  return leerRuta(useHash())
}

/**
 * @param {import('./ruta.js').Ruta} ruta
 * @param {{ reemplazar?: boolean }} [opciones] reemplazar no deja entrada en el historial
 */
export function navegar(ruta, { reemplazar = false } = {}) {
  const hash = escribirRuta(ruta)
  if (reemplazar) window.location.replace(hash)
  else window.location.hash = hash
}
