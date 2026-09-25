import { useEffect } from 'react'

import { Cargando, ErrorCarga } from '../shared/Estados.jsx'
import { escribirRuta } from './ruta.js'
import { navegar } from './useRuta.js'

export { Cargando, ErrorCarga }

/** Una página sin novela: dirección inválida, versión o capítulo que no existen. */
export function Aviso({ titulo, children }) {
  return (
    <main className="estado">
      <h1>{titulo}</h1>
      <p>{children}</p>
    </main>
  )
}

/** Sustituye la dirección actual, sin dejar la vieja en el historial. */
export function Redirigir({ a }) {
  const destino = escribirRuta(a)
  useEffect(() => {
    navegar(a, { reemplazar: true })
    // `a` se describe entera en `destino`.
  }, [destino])
  return <Cargando />
}
