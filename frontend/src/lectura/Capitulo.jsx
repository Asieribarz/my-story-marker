import { obtenerCapitulo } from './api.js'
import Cinta from './Cinta.jsx'
import { Cargando, ErrorCarga } from './Estados.jsx'
import Fragmento from './Fragmento.jsx'
import { capituloEnLetra } from './modelo.js'
import { escribirRuta } from './ruta.js'
import { useCarga } from '../shared/useCarga.js'

/**
 * Un capítulo de una versión. Quien lo pinta le pone `key` por capítulo, así que cada
 * capítulo empieza con su estado limpio. El título sale de la lectura y el texto, de
 * GET …/capitulos/{n}.
 */
export default function Capitulo({ ruta, lectura }) {
  const { proyecto, version, capitulo: numero } = ruta
  const carga = useCarga(`capitulo:${proyecto}:${version}:${numero}`, (senal) =>
    obtenerCapitulo(proyecto, version, numero, senal),
  )

  const actual = lectura.capitulos.find((c) => c.numero === numero)
  const anterior = lectura.capitulos.find((c) => c.numero === numero - 1)
  const siguiente = lectura.capitulos.find((c) => c.numero === numero + 1)
  const cambiado = lectura.cambiados.includes(numero)
  const enlace = (n) => escribirRuta({ pantalla: 'capitulo', proyecto, version, capitulo: n })
  const nombre = (c) => c.titulo ?? capituloEnLetra(c.numero)

  return (
    <article className="capitulo" aria-labelledby="capitulo-titulo">
      {cambiado ? <Cinta className="capitulo-cinta" /> : null}
      <header className="capitulo-cabecera">
        {actual.titulo ? <p className="capitulo-numero">{capituloEnLetra(numero)}</p> : null}
        <h1 id="capitulo-titulo" className="capitulo-titulo">
          {nombre(actual)}
        </h1>
        {cambiado ? <p className="capitulo-cambiado">Cambiado en esta versión</p> : null}
      </header>

      <div className="texto">
        {carga.error ? (
          <ErrorCarga error={carga.error} reintentar={carga.reintentar} />
        ) : carga.dato ? (
          <Fragmento html={carga.dato.html} />
        ) : (
          <Cargando />
        )}
      </div>

      <nav className="capitulo-pie" aria-label="Capítulos">
        {anterior ? (
          <a className="pie-anterior" rel="prev" href={enlace(anterior.numero)}>
            <span className="pie-rotulo">Anterior</span>
            <span className="pie-titulo">{nombre(anterior)}</span>
          </a>
        ) : (
          <span />
        )}
        <a className="pie-indice" href={escribirRuta({ pantalla: 'portada', proyecto, version })}>
          Índice
        </a>
        {siguiente ? (
          <a className="pie-siguiente" rel="next" href={enlace(siguiente.numero)}>
            <span className="pie-rotulo">Siguiente</span>
            <span className="pie-titulo">{nombre(siguiente)}</span>
          </a>
        ) : (
          <span />
        )}
      </nav>
    </article>
  )
}
