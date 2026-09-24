import { escribirVentana } from './navegacion.js'
import { nombreDeEstado, nombreDeProyecto } from './proyectos.js'

const PESTANAS = [
  { pestana: 'leer', nombre: 'Leer' },
  { pestana: 'metricas', nombre: 'Métricas' },
  { pestana: 'nueva', nombre: 'Nueva novela' },
]

/**
 * El logo, las tres ventanas y el proyecto elegido. Cambiar de proyecto conserva la
 * ventana; la lectura de otro proyecto empieza en su versión vigente.
 * @param {{ ventana: import('./navegacion.js').Ventana, proyectos: import('./proyectos.js').ProyectoListado[] }} props
 */
export default function Cabecera({ ventana, proyectos }) {
  const elegir = (proyecto) => {
    window.location.hash = escribirVentana(ventana.pestana, proyecto || null)
  }
  const conocido = proyectos.some((p) => p.identificador === ventana.proyecto)

  return (
    <header className="cabecera">
      <a className="cabecera-logo" href="#/" aria-label="Inicio">
        <img src="/logo.png" alt="qaracter" width="1412" height="326" />
      </a>
      <nav aria-label="Ventanas">
        <ul className="pestanas">
          {PESTANAS.map(({ pestana, nombre }) => (
            <li key={pestana}>
              <a
                href={escribirVentana(pestana, pestana === 'nueva' ? null : ventana.proyecto)}
                aria-current={ventana.pestana === pestana ? 'page' : undefined}
              >
                {nombre}
              </a>
            </li>
          ))}
        </ul>
      </nav>
      {proyectos.length > 0 ? (
        <label className="selector-proyecto">
          Novela
          <select value={conocido ? ventana.proyecto : ''} onChange={(e) => elegir(e.target.value)}>
            {conocido ? null : <option value="">Elige una novela…</option>}
            {proyectos.map((p) => (
              <option key={p.identificador} value={p.identificador}>
                {nombreDeProyecto(p)} — {nombreDeEstado(p.estado)}
              </option>
            ))}
          </select>
        </label>
      ) : null}
    </header>
  )
}
