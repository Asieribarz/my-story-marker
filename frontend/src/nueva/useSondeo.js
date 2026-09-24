import { useEffect, useState } from 'react'

/**
 * Carga `cargar` al montar y cada `ms` milisegundos, conservando el último dato mientras
 * llega el siguiente: el seguimiento no parpadea en cada vuelta. `refrescar` lanza una
 * vuelta ya, tras una acción de la persona.
 *
 * @template T
 * @param {string} clave identifica lo que se carga; `cargar` solo debe depender de ella
 * @param {(senal: AbortSignal) => Promise<T>} cargar
 * @param {number} ms
 */
export function useSondeo(clave, cargar, ms) {
  const [vuelta, setVuelta] = useState(0)
  const [resultado, setResultado] = useState(
    /** @type {{ clave: string | null, dato: T | null, error: unknown }} */ ({ clave: null, dato: null, error: null }),
  )

  useEffect(() => {
    const ac = new AbortController()
    cargar(ac.signal).then(
      (dato) => {
        if (!ac.signal.aborted) setResultado({ clave, dato, error: null })
      },
      (error) => {
        if (!ac.signal.aborted) setResultado((antes) => ({ ...antes, clave, error }))
      },
    )
    const espera = setTimeout(() => setVuelta((v) => v + 1), ms)
    return () => {
      clearTimeout(espera)
      ac.abort()
    }
    // `cargar` es una función nueva en cada render y depende solo de `clave`.
  }, [clave, vuelta, ms])

  const propio = resultado.clave === clave
  return {
    dato: propio ? resultado.dato : null,
    error: propio ? resultado.error : null,
    refrescar: () => setVuelta((v) => v + 1),
  }
}
