import { useEffect } from 'react'

import { ErrorApi } from './api.js'
import { escribirRuta } from './ruta.js'
import { navegar } from './useRuta.js'

/** Una página sin novela: dirección inválida, versión o capítulo que no existen. */
export function Aviso({ titulo, children }) {
  return (
    <main className="estado">
      <h1>{titulo}</h1>
      <p>{children}</p>
    </main>
  )
}

/** Solo se ve si la carga tarda: el retraso está en el CSS. */
export function Cargando() {
  return <p className="cargando">Cargando…</p>
}

export function ErrorCarga({ error, reintentar }) {
  const detalle = error instanceof ErrorApi ? error.detalle : 'Algo ha fallado al cargar la novela.'
  return (
    <div className="estado" role="alert">
      <p>{detalle}</p>
      <button type="button" onClick={reintentar}>
        Reintentar
      </button>
    </div>
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
