import { useEffect } from 'react'

import './nueva.css'

import { escribirVentana } from '../shared/navegacion.js'
import { fechaCorta, nombreDeEstado, nombreDeProyecto } from '../shared/proyectos.js'
import Formulario from './Formulario.jsx'
import Seguimiento from './Seguimiento.jsx'

/**
 * La tercera ventana: sin proyecto, el formulario de una novela nueva y la lista de las que
 * están en marcha; con proyecto, su seguimiento.
 *
 * @param {{ proyecto: string | null, proyectos: import('../shared/proyectos.js').ProyectoListado[] }} props
 */
export default function Nueva({ proyecto, proyectos }) {
  useEffect(() => {
    document.title = proyecto ? 'Seguimiento' : 'Nueva novela'
  }, [proyecto])

  if (proyecto) {
    const listado = proyectos.find((p) => p.identificador === proyecto)
    return (
      <main className="panel">
        <h1>{listado ? nombreDeProyecto(listado) : 'Seguimiento'}</h1>
        <p className="panel-sub">
          Seguimiento de la creación · <a href="#/nueva">Crear otra novela</a>
        </p>
        <Seguimiento proyecto={proyecto} />
      </main>
    )
  }

  const enMarcha = proyectos.filter((p) => p.estado !== 'publicada')
  return (
    <main className="panel">
      <h1>Nueva novela</h1>
      <p className="panel-sub">
        Cuéntanos a quién se la regalas. Al enviarlo se crea el proyecto, y la generación se lanza desde su
        seguimiento.
      </p>
      {enMarcha.length > 0 ? (
        <section className="tarjeta en-marcha" aria-label="En marcha">
          <h2>En marcha</h2>
          <ul>
            {enMarcha.map((p) => (
              <li key={p.identificador}>
                <a href={escribirVentana('nueva', p.identificador)}>{nombreDeProyecto(p)}</a>{' '}
                <span className="chip">{nombreDeEstado(p.estado)}</span>{' '}
                <span className="ayuda">{fechaCorta(p.creado)}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <Formulario />
    </main>
  )
}
