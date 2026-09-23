import Cinta from './Cinta.jsx'
import EnlacesACapitulos from './EnlacesACapitulos.jsx'
import { capituloEnLetra } from './modelo.js'
import { escribirRuta } from './ruta.js'

/** Cubierta, dedicatoria, novedades de la versión e índice. */
export default function Portada({ ruta, lectura }) {
  const { titulo, dedicatoria } = lectura.portada
  const { cambiados } = lectura
  const base = { proyecto: ruta.proyecto, version: ruta.version }

  return (
    <article className="portada">
      <div className="cubierta">
        <h1 className="cubierta-titulo">{titulo}</h1>
      </div>

      {dedicatoria ? <p className="dedicatoria">{dedicatoria}</p> : null}

      {cambiados.length > 0 ? (
        <aside className="novedades" aria-label="Novedades de esta versión">
          <Cinta />
          <p>
            En la versión {lectura.version} {cambiados.length === 1 ? 'ha cambiado el capítulo' : 'han cambiado los capítulos'}{' '}
            <EnlacesACapitulos numeros={cambiados} ruta={ruta} lectura={lectura} marcar={false} />. En el índice
            llevan la cinta.
          </p>
        </aside>
      ) : null}

      <nav className="indice" aria-labelledby="indice-titulo">
        <h2 id="indice-titulo">Índice</h2>
        <ol>
          {lectura.capitulos.map((c) => (
            <li key={c.numero}>
              <a href={escribirRuta({ ...base, pantalla: 'capitulo', capitulo: c.numero })}>
                <span className="indice-numero">{c.numero}</span>
                <span className="indice-titulo">{c.titulo ?? capituloEnLetra(c.numero)}</span>
                {cambiados.includes(c.numero) ? <Cinta etiqueta="Cambiado en esta versión" /> : null}
              </a>
            </li>
          ))}
        </ol>
        <p className="indice-fichas">
          <a href={escribirRuta({ ...base, pantalla: 'fichas' })}>Personajes y lugares</a>
        </p>
      </nav>
    </article>
  )
}
