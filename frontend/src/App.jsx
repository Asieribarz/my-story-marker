import Cabecera from './shared/Cabecera.jsx'
import { Cargando } from './shared/Estados.jsx'
import { leerVentana } from './shared/navegacion.js'
import { obtenerProyectos } from './shared/proyectos.js'
import { useCarga } from './shared/useCarga.js'
import { useHash } from './shared/useHash.js'

import Lectura from './lectura/Lectura.jsx'
import Metricas from './metricas/Metricas.jsx'
import Nueva from './nueva/Nueva.jsx'

/**
 * Las tres ventanas (plan-frontend.md §4): Leer —con la edición de cambio/—, Métricas y
 * Nueva novela. La lista de proyectos se vuelve a pedir al cambiar de proyecto, que es
 * cuando puede haber uno nuevo.
 */
export default function App() {
  const ventana = leerVentana(useHash())
  const carga = useCarga(`proyectos:${ventana.pestana}:${ventana.proyecto}`, obtenerProyectos)
  const proyectos = carga.dato?.proyectos ?? []

  return (
    <>
      <Cabecera ventana={ventana} proyectos={proyectos} />
      {ventana.pestana === 'metricas' ? (
        <Metricas key={ventana.proyecto} proyecto={ventana.proyecto} proyectos={carga.dato ? proyectos : null} />
      ) : ventana.pestana === 'nueva' ? (
        <Nueva key={ventana.proyecto} proyecto={ventana.proyecto} proyectos={proyectos} />
      ) : !ventana.proyecto && !carga.dato && !carga.error ? (
        <Cargando />
      ) : (
        <Lectura porDefecto={proyectos.find((p) => p.versiones > 0)?.identificador ?? null} />
      )}
    </>
  )
}
