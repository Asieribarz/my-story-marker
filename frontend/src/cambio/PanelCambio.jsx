import { useEffect, useState } from 'react'

import './cambio.css'

import { ErrorAccion } from '../shared/Estados.jsx'
import { TOPE, decidirCambio, obtenerCambio, pedirCambio } from './api.js'
import { leerSeleccion } from './seleccion.js'

/** Mientras el backend trabaja, la web vuelve a preguntar cada tanto (plan-frontend.md §7). */
const SONDEO_MS = 3000
const EN_CURSO = new Set(['interpretando', 'regenerando'])

/** @param {string} proyecto */
const clave = (proyecto) => `msm:cambio:${proyecto}`

function recordar(proyecto, id) {
  try {
    if (id === null) sessionStorage.removeItem(clave(proyecto))
    else sessionStorage.setItem(clave(proyecto), String(id))
  } catch {
    // Sin almacenamiento, el seguimiento solo dura lo que la página.
  }
}

function recordado(proyecto) {
  try {
    const valor = Number(sessionStorage.getItem(clave(proyecto)))
    return Number.isInteger(valor) && valor >= 1 ? valor : null
  } catch {
    return null
  }
}

/**
 * La edición de la historia (plan-frontend.md §7): seleccionar un fragmento del capítulo,
 * pedir el cambio, ver la propuesta del Intérprete, confirmarla o descartarla, y seguir la
 * regeneración hasta la versión nueva. Vive por encima de la versión, así que el
 * seguimiento sobrevive a cambiar de capítulo o de versión, y a recargar la página.
 *
 * @param {{ ruta: import('../lectura/ruta.js').Ruta & { proyecto: string }, vigente: number | null,
 *   alPublicar: (version: number) => void }} props
 */
export default function PanelCambio({ ruta, vigente, alPublicar }) {
  const proyecto = ruta.proyecto
  const [fase, setFase] = useState(() => {
    const id = recordado(proyecto)
    return id === null ? { tipo: 'libre' } : { tipo: 'recuperando', id }
  })
  const [viva, setViva] = useState(null)
  const [peticion, setPeticion] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)
  const [vuelta, setVuelta] = useState(0)

  const puedeSeleccionar =
    fase.tipo === 'libre' && ruta.pantalla === 'capitulo' && vigente !== null && ruta.version === vigente

  // La selección es del documento: se escucha mientras se puede pedir un cambio.
  useEffect(() => {
    if (!puedeSeleccionar) {
      setViva(null)
      return undefined
    }
    const leer = () => setViva(leerSeleccion(document.getSelection()))
    document.addEventListener('selectionchange', leer)
    return () => document.removeEventListener('selectionchange', leer)
  }, [puedeSeleccionar])

  // Recuperar el cambio recordado y sondear mientras el backend trabaja.
  const id = fase.tipo === 'recuperando' ? fase.id : fase.tipo === 'seguimiento' ? fase.cambio.id : null
  const sondear = fase.tipo === 'recuperando' || (fase.tipo === 'seguimiento' && EN_CURSO.has(fase.cambio.estado))
  useEffect(() => {
    if (!sondear || id === null) return undefined
    const ac = new AbortController()
    const espera = setTimeout(
      () => {
        obtenerCambio(proyecto, id, ac.signal).then(
          (cambio) => {
            if (ac.signal.aborted) return
            setFase({ tipo: 'seguimiento', cambio })
            setVuelta((v) => v + 1)
          },
          (fallo) => {
            if (ac.signal.aborted) return
            if (fase.tipo === 'recuperando') {
              recordar(proyecto, null)
              setFase({ tipo: 'libre' })
            } else {
              setError(fallo)
              setVuelta((v) => v + 1)
            }
          },
        )
      },
      fase.tipo === 'recuperando' ? 0 : SONDEO_MS,
    )
    return () => {
      clearTimeout(espera)
      ac.abort()
    }
    // `vuelta` relanza el sondeo tras cada respuesta, aunque el estado no cambie.
  }, [proyecto, id, sondear, vuelta])

  const redactar = () => {
    if (!viva) return
    setFase({ tipo: 'redactando', seleccion: { ...viva, version: ruta.version, capitulo: ruta.capitulo } })
    setPeticion('')
    setError(null)
  }

  const cerrar = () => {
    recordar(proyecto, null)
    setFase({ tipo: 'libre' })
    setError(null)
  }

  const enviar = async (evento) => {
    evento.preventDefault()
    const { seleccion } = fase
    setEnviando(true)
    setError(null)
    try {
      const cambio = await pedirCambio(proyecto, {
        version: seleccion.version,
        capitulo: seleccion.capitulo,
        fragmento: seleccion.fragmento,
        parrafos: seleccion.parrafos,
        peticion: peticion.trim(),
      })
      recordar(proyecto, cambio.id)
      setPeticion('')
      setFase({ tipo: 'seguimiento', cambio })
    } catch (fallo) {
      setError(fallo)
    } finally {
      setEnviando(false)
    }
  }

  const decidir = async (confirmado) => {
    setEnviando(true)
    setError(null)
    try {
      const cambio = await decidirCambio(proyecto, fase.cambio.id, confirmado)
      setFase({ tipo: 'seguimiento', cambio })
    } catch (fallo) {
      setError(fallo)
    } finally {
      setEnviando(false)
    }
  }

  if (fase.tipo === 'libre') {
    if (!puedeSeleccionar) return null
    return viva ? (
      <div className="cambio-flotante">
        {/* mousedown no se deja propagar: si no, el clic borraría la selección antes de leerla. */}
        <button type="button" className="boton boton-primario" onMouseDown={(e) => e.preventDefault()} onClick={redactar}>
          ✎ Pedir un cambio sobre esta selección
        </button>
      </div>
    ) : (
      <p className="cambio-pista">Selecciona un fragmento del capítulo para pedir un cambio en la historia.</p>
    )
  }

  if (fase.tipo === 'recuperando') return null

  if (fase.tipo === 'redactando') {
    const { seleccion } = fase
    const largo = seleccion.fragmento.length > TOPE
    return (
      <aside className="cambio-panel" aria-label="Pedir un cambio">
        <form onSubmit={enviar}>
          <h2>Pedir un cambio · capítulo {seleccion.capitulo}</h2>
          {/* El fragmento es del lector: siempre como texto, nunca como HTML. */}
          <blockquote className="cambio-cita">
            {seleccion.fragmento.length > 400 ? `${seleccion.fragmento.slice(0, 400)}…` : seleccion.fragmento}
          </blockquote>
          {largo ? <p className="error-accion">El fragmento es demasiado largo: selecciona un trozo más corto.</p> : null}
          <label className="campo">
            <span>¿Qué quieres cambiar?</span>
            <textarea
              value={peticion}
              onChange={(e) => setPeticion(e.target.value)}
              maxLength={TOPE}
              placeholder="Por ejemplo: la brújula era de su abuela, no de su abuelo."
              required
            />
          </label>
          <div className="cambio-acciones">
            <button type="submit" className="boton boton-primario" disabled={enviando || largo || !peticion.trim()}>
              {enviando ? 'Enviando…' : 'Pedir el cambio'}
            </button>
            <button type="button" className="boton" onClick={cerrar} disabled={enviando}>
              Cancelar
            </button>
          </div>
          <ErrorAccion error={error} />
        </form>
      </aside>
    )
  }

  const { cambio } = fase
  return (
    <aside className="cambio-panel" aria-label="Tu cambio" aria-live="polite">
      <h2>Tu cambio · capítulo {cambio.capitulo}</h2>
      <Seguimiento cambio={cambio} />
      <div className="cambio-acciones">
        {cambio.estado === 'propuesto' ? (
          <>
            <button type="button" className="boton boton-primario" onClick={() => decidir(true)} disabled={enviando}>
              Confirmar el cambio
            </button>
            <button type="button" className="boton" onClick={() => decidir(false)} disabled={enviando}>
              Descartar
            </button>
          </>
        ) : null}
        {cambio.estado === 'publicado' && cambio.version_nueva !== null ? (
          <button
            type="button"
            className="boton boton-primario"
            onClick={() => {
              cerrar()
              alPublicar(cambio.version_nueva)
            }}
          >
            Leer la versión {cambio.version_nueva}
          </button>
        ) : null}
        {EN_CURSO.has(cambio.estado) || cambio.estado === 'propuesto' ? null : (
          <button type="button" className="boton" onClick={cerrar}>
            Cerrar
          </button>
        )}
      </div>
      <ErrorAccion error={error} />
    </aside>
  )
}

function Seguimiento({ cambio }) {
  switch (cambio.estado) {
    case 'interpretando':
      return <p className="cambio-espera">El Intérprete está leyendo tu petición…</p>
    case 'propuesto': {
      const p = cambio.propuesta
      if (!p) return <p>Hay una propuesta lista.</p>
      return p.tipo === 'nuevo' ? (
        <dl className="cambio-propuesta">
          <dt>Nuevo hecho</dt>
          <dd className="cambio-nuevo">{p.valor_nuevo}</dd>
        </dl>
      ) : (
        <dl className="cambio-propuesta">
          <dt>Antes</dt>
          <dd className="cambio-antes">{p.valor_anterior ?? '—'}</dd>
          <dt>Después</dt>
          <dd className="cambio-nuevo">{p.valor_nuevo}</dd>
        </dl>
      )
    }
    case 'regenerando':
      return (
        <p className="cambio-espera">
          Regenerando {cambio.capitulos.length === 1 ? 'el capítulo' : 'los capítulos'} {cambio.capitulos.join(', ')}… Puede
          tardar varios minutos; puedes seguir leyendo.
        </p>
      )
    case 'publicado':
      return <p>Listo: el cambio está en la versión {cambio.version_nueva}, con sus capítulos cambiados marcados.</p>
    case 'obsoleto':
      return <p>Lo pediste sobre una versión que ya no es la más reciente. Vuelve a pedirlo sobre la vigente.</p>
    case 'rechazado':
      return <p>Descartado. La novela sigue como estaba.</p>
    case 'fallido':
      return (
        <p>
          La regeneración ha fallado{cambio.motivo ? ` (${cambio.motivo})` : ''}. La versión vigente sigue siendo la
          anterior.
        </p>
      )
    default:
      return <p>{cambio.estado}</p>
  }
}
