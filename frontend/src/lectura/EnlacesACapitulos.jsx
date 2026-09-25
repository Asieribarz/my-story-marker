import { Fragment } from 'react'

import { capituloEnLetra, separadores } from './modelo.js'
import { escribirRuta } from './ruta.js'

/**
 * «1, 2 y 5», cada número enlazado a su capítulo en la misma versión. Con `marcar`, los
 * cambiados en esta versión llevan la cinta.
 */
export default function EnlacesACapitulos({ numeros, ruta, lectura, marcar = true }) {
  const seps = separadores(numeros.map(String))
  return numeros.map((n, i) => {
    const capitulo = lectura.capitulos.find((c) => c.numero === n)
    const cambiado = marcar && lectura.cambiados.includes(n)
    return (
      <Fragment key={n}>
        <a
          href={escribirRuta({ pantalla: 'capitulo', proyecto: ruta.proyecto, version: ruta.version, capitulo: n })}
          title={capitulo?.titulo ?? capituloEnLetra(n)}
          className={cambiado ? 'enlace-cambiado' : undefined}
        >
          {n}
          {cambiado ? <span className="solo-lectores"> (cambiado en esta versión)</span> : null}
        </a>
        {seps[i]}
      </Fragment>
    )
  })
}
