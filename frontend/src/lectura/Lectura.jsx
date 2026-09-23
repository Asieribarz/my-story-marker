import { useEffect } from 'react'

import './lectura.css'

import { obtenerLectura, obtenerVersiones, proyectoPorDefecto } from './api.js'
import Barra from './Barra.jsx'
import Capitulo from './Capitulo.jsx'
import { Aviso, Cargando, ErrorCarga, Redirigir } from './Estados.jsx'
import Fichas from './Fichas.jsx'
import { fechaLegible, versionVigente } from './modelo.js'
import Portada from './Portada.jsx'
import { escribirRuta } from './ruta.js'
import { useCarga } from './useCarga.js'
import { useRuta } from './useRuta.js'

/**
 * La funcionalidad de lectura entera: lee la dirección (plan-frontend.md §4), carga las
 * versiones del proyecto y la lectura de la versión pedida, y pinta su pantalla.
 */
export default function Lectura() {
  const ruta = useRuta()

  if (ruta.pantalla === 'sin_proyecto') {
    const proyecto = proyectoPorDefecto()
    return proyecto ? (
      <Redirigir a={{ pantalla: 'vigente', proyecto }} />
    ) : (
      <Aviso titulo="Abre el enlace de tu novela">
        Esta dirección no dice qué novela abrir. Usa el enlace que recibiste con ella.
      </Aviso>
    )
  }
  if (ruta.pantalla === 'desconocida') {
    return (
      <Aviso titulo="Esta página no existe">
        Revisa el enlace o <a href="#/">vuelve al principio</a>.
      </Aviso>
    )
  }
  return <Proyecto key={ruta.proyecto} ruta={ruta} />
}

function Proyecto({ ruta }) {
  const carga = useCarga(`versiones:${ruta.proyecto}`, (senal) => obtenerVersiones(ruta.proyecto, senal))

  if (carga.error) return <ErrorCarga error={carga.error} reintentar={carga.reintentar} />
  if (!carga.dato) return <Cargando />

  const versiones = carga.dato
  const vigente = versionVigente(versiones)
  if (ruta.pantalla === 'vigente') {
    return <Redirigir a={{ pantalla: 'portada', proyecto: ruta.proyecto, version: vigente }} />
  }

  const publicada = versiones.versiones.find((v) => v.version === ruta.version)
  if (!publicada) {
    return (
      <Aviso titulo={`No hay versión ${ruta.version}`}>
        La más reciente es la {vigente}. <a href={escribirRuta({ ...ruta, version: vigente })}>Leer la versión {vigente}</a>.
      </Aviso>
    )
  }
  return <Version key={ruta.version} ruta={ruta} versiones={versiones} publicada={publicada} vigente={vigente} />
}

function Version({ ruta, versiones, publicada, vigente }) {
  const carga = useCarga(`lectura:${ruta.proyecto}:${ruta.version}`, (senal) =>
    obtenerLectura(ruta.proyecto, ruta.version, senal),
  )
  const lectura = carga.dato
  const direccion = escribirRuta(ruta)

  useEffect(() => {
    document.title = lectura ? tituloDelDocumento(lectura, ruta) : 'Tu novela'
    // `ruta` se describe entera en `direccion`.
  }, [lectura, direccion])

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [direccion])

  if (carga.error) return <ErrorCarga error={carga.error} reintentar={carga.reintentar} />
  if (!lectura) return <Cargando />

  return (
    <>
      <Barra ruta={ruta} titulo={lectura.portada.titulo} versiones={versiones} vigente={vigente} />
      {ruta.version !== vigente ? (
        <p className="aviso-version">
          Estás leyendo la versión {ruta.version}, del {fechaLegible(publicada.publicada)}.{' '}
          <a href={escribirRuta({ ...ruta, version: vigente })}>Leer la versión {vigente}, la más reciente</a>.
        </p>
      ) : null}
      <Pantalla ruta={ruta} lectura={lectura} />
    </>
  )
}

function Pantalla({ ruta, lectura }) {
  if (ruta.pantalla === 'portada') return <Portada ruta={ruta} lectura={lectura} />
  if (ruta.pantalla === 'fichas') return <Fichas ruta={ruta} lectura={lectura} />
  if (!lectura.capitulos.some((c) => c.numero === ruta.capitulo)) {
    return (
      <Aviso titulo={`Esta novela no tiene capítulo ${ruta.capitulo}`}>
        Tiene {lectura.capitulos.length}.{' '}
        <a href={escribirRuta({ pantalla: 'portada', proyecto: ruta.proyecto, version: ruta.version })}>
          Ir al índice
        </a>
        .
      </Aviso>
    )
  }
  return (
    <main>
      <Capitulo key={ruta.capitulo} ruta={ruta} lectura={lectura} />
    </main>
  )
}

function tituloDelDocumento(lectura, ruta) {
  const libro = lectura.portada.titulo
  if (ruta.pantalla === 'fichas') return `Personajes y lugares | ${libro}`
  if (ruta.pantalla === 'capitulo') {
    const capitulo = lectura.capitulos.find((c) => c.numero === ruta.capitulo)
    return capitulo ? `${capitulo.titulo ?? `Capítulo ${capitulo.numero}`} | ${libro}` : libro
  }
  return libro
}
