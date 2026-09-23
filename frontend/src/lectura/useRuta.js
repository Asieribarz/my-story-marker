import { useSyncExternalStore } from 'react'

import { escribirRuta, leerRuta } from './ruta.js'

/** @param {() => void} avisar */
function suscribir(avisar) {
  window.addEventListener('hashchange', avisar)
  return () => window.removeEventListener('hashchange', avisar)
}

const hashActual = () => window.location.hash

/** La ruta de la dirección actual; se vuelve a leer en cada cambio de «#». */
export function useRuta() {
  return leerRuta(useSyncExternalStore(suscribir, hashActual))
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
