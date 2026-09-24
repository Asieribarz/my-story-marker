import { useEffect, useState } from 'react'

/**
 * Carga asíncrona atada a una clave: al cambiar la clave, o al reintentar, se cancela
 * la petición anterior y el resultado viejo deja de mostrarse. Nunca pinta el resultado
 * de una clave distinta de la actual, aunque llegue tarde.
 *
 * @template T
 * @param {string} clave identifica lo que se carga; `cargar` solo debe depender de ella
 * @param {(senal: AbortSignal) => Promise<T>} cargar
 */
export function useCarga(clave, cargar) {
  const [intento, setIntento] = useState(0)
  const id = `${clave}#${intento}`
  const [resultado, setResultado] = useState(
    /** @type {{ id: string | null, dato: T | null, error: unknown }} */ ({ id: null, dato: null, error: null }),
  )

  useEffect(() => {
    const ac = new AbortController()
    cargar(ac.signal).then(
      (dato) => {
        if (!ac.signal.aborted) setResultado({ id, dato, error: null })
      },
      (error) => {
        if (!ac.signal.aborted) setResultado({ id, dato: null, error })
      },
    )
    return () => ac.abort()
    // `cargar` es una función nueva en cada render y depende solo de `clave`, que va en `id`.
  }, [id])

  const listo = resultado.id === id
  return {
    cargando: !listo,
    dato: listo ? resultado.dato : null,
    error: listo ? resultado.error : null,
    reintentar: () => setIntento((i) => i + 1),
  }
}
