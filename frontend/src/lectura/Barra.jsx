import { urlPdf } from './api.js'
import { escribirRuta } from './ruta.js'
import { navegar } from './useRuta.js'

/**
 * Título, personajes y lugares, PDF y selector de versión. Cambiar de versión conserva
 * la pantalla: del capítulo 3 de la v1 al capítulo 3 de la v2.
 */
export default function Barra({ ruta, titulo, versiones, vigente }) {
  const enVersion = (pantalla) => escribirRuta({ pantalla, proyecto: ruta.proyecto, version: ruta.version })
  const pdf = urlPdf(ruta.proyecto, ruta.version)

  return (
    <header className="barra">
      <a className="barra-titulo" href={enVersion('portada')}>
        {titulo}
      </a>
      <nav className="barra-nav" aria-label="Novela">
        <a href={enVersion('fichas')} aria-current={ruta.pantalla === 'fichas' ? 'page' : undefined}>
          Personajes y lugares
        </a>
        {pdf ? (
          <a href={pdf} download>
            Descargar en PDF
          </a>
        ) : null}
        <label className="barra-version">
          Versión
          <select value={ruta.version} onChange={(e) => navegar({ ...ruta, version: Number(e.target.value) })}>
            {versiones.versiones.toReversed().map((v) => (
              <option key={v.version} value={v.version}>
                {v.version === vigente ? `${v.version}, la más reciente` : v.version}
              </option>
            ))}
          </select>
        </label>
      </nav>
    </header>
  )
}
