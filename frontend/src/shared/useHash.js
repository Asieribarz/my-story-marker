import { useSyncExternalStore } from 'react'

/** @param {() => void} avisar */
function suscribir(avisar) {
  window.addEventListener('hashchange', avisar)
  return () => window.removeEventListener('hashchange', avisar)
}

const hashActual = () => window.location.hash

/** El «#» de la dirección; se vuelve a leer en cada cambio. */
export function useHash() {
  return useSyncExternalStore(suscribir, hashActual)
}
