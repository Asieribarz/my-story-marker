import EnlacesACapitulos from './EnlacesACapitulos.jsx'
import { arbolDeLugares, rolesLegibles } from './modelo.js'

/** Personajes y lugares de la versión, con los capítulos donde aparece cada uno (RF-97). */
export default function Fichas({ ruta, lectura }) {
  const apariciones = (numeros) =>
    numeros.length > 0 ? (
      <p className="ficha-apariciones">
        Aparece en {numeros.length === 1 ? 'el capítulo' : 'los capítulos'}{' '}
        <EnlacesACapitulos numeros={numeros} ruta={ruta} lectura={lectura} />.
      </p>
    ) : null

  const lugares = (nodos) => (
    <ul className="lugares">
      {nodos.map(({ lugar, hijos }) => (
        <li key={lugar.id} className="ficha">
          <h3 className="ficha-nombre">{lugar.nombre}</h3>
          {lugar.descripcion ? <p>{lugar.descripcion}</p> : null}
          {apariciones(lugar.capitulos)}
          {hijos.length > 0 ? lugares(hijos) : null}
        </li>
      ))}
    </ul>
  )

  return (
    <article className="fichas">
      <h1 className="fichas-titulo">Personajes y lugares</h1>

      <section aria-labelledby="fichas-personajes">
        <h2 id="fichas-personajes">Personajes</h2>
        <ul>
          {lectura.personajes.map((p) => (
            <li key={p.id} className="ficha">
              <div className="ficha-cabeza">
                <h3 className="ficha-nombre">{p.nombre}</h3>
                <span className="ficha-rol">{rolesLegibles(p.rol)}</span>
              </div>
              {p.descripcion ? <p>{p.descripcion}</p> : null}
              {apariciones(p.capitulos)}
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="fichas-lugares">
        <h2 id="fichas-lugares">Lugares</h2>
        {lugares(arbolDeLugares(lectura.lugares))}
      </section>
    </article>
  )
}
