import { useState } from 'react'

import { Cargando, ErrorAccion, ErrorCarga } from '../shared/Estados.jsx'
import { escribirVentana } from '../shared/navegacion.js'
import { fechaCorta, nombreDeEstado } from '../shared/proyectos.js'
import { useCarga } from '../shared/useCarga.js'
import {
  confirmarHechos,
  decidirFinal,
  decidirPlan,
  generar,
  obtenerEstado,
  obtenerHechos,
  obtenerPlan,
  reintentar,
} from './api.js'
import { useSondeo } from './useSondeo.js'

const SONDEO_MS = 5000

const NOMBRE_DE_CAPITULO = {
  pendiente: 'pendiente',
  borrador: 'borrador',
  editado: 'editado',
  verificado: 'verificado',
  aprobado: 'aprobado',
  revision_humana: 'para revisar',
}

/**
 * El seguimiento de un proyecto: en qué fase está, qué agente trabaja, cómo van los
 * capítulos y, cuando el proyecto espera a la persona, la decisión que le toca: confirmar
 * los hechos extraídos, aprobar el plan o el manuscrito, o reintentar si se detuvo.
 * Generar lo hace el worker del backend: el botón encola el trabajo y el sondeo enseña cómo
 * va. En Claude Code, `/generar` hace lo mismo desde una sesión.
 */
export default function Seguimiento({ proyecto }) {
  const sondeo = useSondeo(`estado:${proyecto}`, (senal) => obtenerEstado(proyecto, senal), SONDEO_MS)
  const e = sondeo.dato
  if (!e) return sondeo.error ? <ErrorCarga error={sondeo.error} reintentar={sondeo.refrescar} /> : <Cargando />

  const trabajando = e.orden_vigente
  return (
    <>
      <div className="tarjeta">
        <p className="seguimiento-estado">
          <span className="chip">{nombreDeEstado(e.estado)}</span>
          {e.estado === 'detenida' && e.detenida_desde ? ` desde «${nombreDeEstado(e.detenida_desde)}»` : null}
        </p>
        <p className="ayuda">
          Creada el {fechaCorta(e.creado)} · paradas: plan {e.parada_plan ? 'sí' : 'no'}, final {e.parada_final ? 'sí' : 'no'} ·
          ciclos de revisión {e.ciclos_revision}
        </p>
        {trabajando ? (
          <p>
            Trabajando ahora: <strong>{trabajando.agente}</strong>
            {trabajando.capitulo ? ` · capítulo ${trabajando.capitulo}` : ''} · intento {trabajando.intento}, desde{' '}
            {fechaCorta(trabajando.emitida)}
            {e.bloqueo ? ` (${e.bloqueo.tipo === 'worker' ? 'el worker' : 'una sesión'})` : ''}
          </p>
        ) : null}
        {sondeo.error ? <ErrorAccion error={sondeo.error} /> : null}
      </div>

      {e.capitulos.length > 0 ? (
        <>
          <h2>Capítulos</h2>
          <ol className="capitulos-estado">
            {e.capitulos.map((c) => (
              <li key={c.numero} className={`capitulo-estado capitulo-${c.estado}`}>
                <span className="capitulo-estado-numero">{c.numero}</span>
                <span>{NOMBRE_DE_CAPITULO[c.estado] ?? c.estado}</span>
                {c.intentos > 1 ? <span className="ayuda">{c.intentos} intentos</span> : null}
              </li>
            ))}
          </ol>
        </>
      ) : null}

      <h2>Qué toca ahora</h2>
      <Accion estado={e} proyecto={proyecto} refrescar={sondeo.refrescar} />
    </>
  )
}

function Accion({ estado, proyecto, refrescar }) {
  switch (estado.estado) {
    case 'intake':
      return <Hechos estado={estado} proyecto={proyecto} refrescar={refrescar} />
    case 'aprobacion_plan':
      return <AprobarPlan proyecto={proyecto} refrescar={refrescar} />
    case 'aprobacion_final':
      return <AprobarFinal proyecto={proyecto} refrescar={refrescar} />
    case 'detenida':
      return <Reintentar proyecto={proyecto} refrescar={refrescar} />
    case 'publicada':
      return (
        <div className="tarjeta">
          <p>La novela está publicada.</p>
          <div className="acciones">
            <a className="boton boton-primario" href={escribirVentana('leer', proyecto)}>
              Leerla
            </a>
            <a className="boton" href={escribirVentana('metricas', proyecto)}>
              Ver cómo se hizo
            </a>
          </div>
        </div>
      )
    default:
      return <Generar estado={estado} proyecto={proyecto} refrescar={refrescar} />
  }
}

const CAUSA_DE_FALLO = {
  claude_no_disponible: 'no se encontró el comando claude en la máquina del backend',
  salida_con_error: 'Claude Code terminó con un error',
  tiempo_agotado: 'se agotó el tiempo máximo',
  caida: 'el proceso murió',
  sin_parada: 'Claude Code terminó antes de llegar a una parada',
}

/**
 * Lanzar la generación: el botón encola un trabajo y el worker lo lanza con `claude -p`. Con
 * un trabajo en cola o en curso, cómo va; si el último falló, por qué, y el botón reanuda.
 */
function Generar({ estado, proyecto, refrescar, antes }) {
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)
  const trabajo = estado.trabajo
  const activo = trabajo && (trabajo.estado === 'en_cola' || trabajo.estado === 'en_curso')
  const fallido = trabajo && trabajo.generacion && trabajo.estado === 'fallido'
  const sesion = estado.bloqueo?.tipo === 'sesion'

  const lanzar = async () => {
    setEnviando(true)
    setError(null)
    try {
      await generar(proyecto)
      refrescar()
    } catch (fallo) {
      setError(fallo)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="tarjeta">
      {antes ? <p>{antes}</p> : null}
      {activo && trabajo.estado === 'en_curso' ? (
        <p>Generando en segundo plano. Esta página se actualiza sola; puedes cerrarla y volver luego.</p>
      ) : activo ? (
        <p>
          {sesion
            ? 'En cola: una sesión de Claude Code está trabajando en ella, y el trabajo empieza cuando la suelte.'
            : 'En cola: empieza en cuanto el backend quede libre.'}
        </p>
      ) : (
        <>
          {fallido ? (
            <p>
              <strong>La última generación se detuvo:</strong> {CAUSA_DE_FALLO[trabajo.causa] ?? trabajo.causa}. Lo hecho no se pierde:
              generar otra vez sigue desde donde se quedó.
            </p>
          ) : null}
          {sesion ? <p>Hay una sesión de Claude Code trabajando en ella.</p> : null}
          <div className="acciones">
            <button type="button" className="boton boton-primario" disabled={enviando} onClick={lanzar}>
              {fallido || estado.capitulos.some((c) => c.estado !== 'pendiente') ? 'Seguir generando' : 'Generar la novela'}
            </button>
          </div>
        </>
      )}
      <p className="ayuda">
        También se puede seguir desde Claude Code, abierto en el repositorio: <code className="codigo">/generar {proyecto}</code>
      </p>
      <ErrorAccion error={error} />
    </div>
  )
}

function Hechos({ estado, proyecto, refrescar }) {
  const carga = useCarga(`hechos:${proyecto}`, (senal) => obtenerHechos(proyecto, senal))
  const [decisiones, setDecisiones] = useState({})
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)

  if (carga.error) return <ErrorCarga error={carga.error} reintentar={carga.reintentar} />
  if (!carga.dato) return <Cargando />
  const hechos = carga.dato.hechos
  if (hechos.length === 0) {
    return (
      <Generar
        estado={estado}
        proyecto={proyecto}
        refrescar={refrescar}
        antes="El brief está enviado. Si trae texto libre, el Extractor te propondrá hechos aquí para que confirmes cuáles entran."
      />
    )
  }

  const enviar = async () => {
    setEnviando(true)
    setError(null)
    try {
      await confirmarHechos(
        proyecto,
        Object.entries(decisiones).map(([hecho, confirmado]) => ({ hecho: Number(hecho), confirmado })),
      )
      setDecisiones({})
      carga.reintentar()
      refrescar()
    } catch (fallo) {
      setError(fallo)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="tarjeta tarjeta-aviso">
      <p>El Extractor ha sacado estos hechos de tu texto libre. Solo los que confirmes entran en la novela.</p>
      <ul className="hechos-propuestos">
        {hechos.map((h) => (
          <li key={h.id}>
            <p>
              <span className="chip">{h.tipo.replaceAll('_', ' ')}</span> {h.texto}
              {h.momento || h.lugar ? <span className="ayuda"> · {[h.momento, h.lugar].filter(Boolean).join(', ')}</span> : null}
            </p>
            <div className="acciones">
              <label className="casilla">
                <input
                  type="radio"
                  name={`hecho-${h.id}`}
                  checked={decisiones[h.id] === true}
                  onChange={() => setDecisiones((d) => ({ ...d, [h.id]: true }))}
                />
                Entra
              </label>
              <label className="casilla">
                <input
                  type="radio"
                  name={`hecho-${h.id}`}
                  checked={decisiones[h.id] === false}
                  onChange={() => setDecisiones((d) => ({ ...d, [h.id]: false }))}
                />
                No entra
              </label>
            </div>
          </li>
        ))}
      </ul>
      <button
        type="button"
        className="boton boton-primario"
        disabled={enviando || Object.keys(decisiones).length === 0}
        onClick={enviar}
      >
        Guardar mi decisión
      </button>
      <p className="ayuda">Después podrás seguir generando desde aquí.</p>
      <ErrorAccion error={error} />
    </div>
  )
}

/** Aprobar o pedir cambios con notas: el formulario común de las dos paradas. */
function Decision({ titulo, children, decidir, refrescar, conCapitulos = false }) {
  const [notas, setNotas] = useState('')
  const [capitulos, setCapitulos] = useState([])
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)
  const [hecho, setHecho] = useState(false)

  const enviar = async (decision) => {
    setEnviando(true)
    setError(null)
    try {
      await decidir(decision, notas.trim() || null, capitulos.length > 0 ? capitulos : null)
      setHecho(true)
      refrescar()
    } catch (fallo) {
      setError(fallo)
    } finally {
      setEnviando(false)
    }
  }

  if (hecho) return <p className="ayuda">Decisión guardada.</p>
  return (
    <div className="tarjeta tarjeta-aviso">
      <p>{titulo}</p>
      {children}
      <label className="campo">
        <span>Notas (obligatorias si pides cambios)</span>
        <textarea value={notas} onChange={(e) => setNotas(e.target.value)} />
      </label>
      {conCapitulos ? (
        <fieldset className="capitulos-a-revisar">
          <legend>Capítulos que revisar (ninguno marcado: todos)</legend>
          {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
            <label key={n} className="casilla">
              <input
                type="checkbox"
                checked={capitulos.includes(n)}
                onChange={(e) =>
                  setCapitulos((c) => (e.target.checked ? [...c, n].sort((a, b) => a - b) : c.filter((x) => x !== n)))
                }
              />
              {n}
            </label>
          ))}
        </fieldset>
      ) : null}
      <div className="acciones">
        <button type="button" className="boton boton-primario" disabled={enviando} onClick={() => enviar('aprobado')}>
          Aprobar
        </button>
        <button type="button" className="boton" disabled={enviando || !notas.trim()} onClick={() => enviar('cambios')}>
          Pedir cambios
        </button>
      </div>
      <ErrorAccion error={error} />
    </div>
  )
}

function AprobarPlan({ proyecto, refrescar }) {
  const carga = useCarga(`plan:${proyecto}`, (senal) => obtenerPlan(proyecto, senal))
  const plan = carga.dato
  return (
    <Decision
      titulo="El plan está listo y espera tu aprobación. Después, sigue generando desde aquí."
      decidir={(decision, notas) => decidirPlan(proyecto, decision, notas)}
      refrescar={refrescar}
    >
      {carga.error ? <ErrorCarga error={carga.error} reintentar={carga.reintentar} /> : null}
      {plan ? (
        <dl className="plan-resumen">
          <dt>Pregunta dramática</dt>
          <dd>{plan.plan.pregunta_dramatica}</dd>
          <dt>Final</dt>
          <dd>{String(plan.plan.tipo_final).replaceAll('_', ' ')}</dd>
          <dt>Curva de tensión</dt>
          <dd>
            <span className="curva" aria-label={`Tensión por capítulo: ${plan.plan.curva_tension.join(', ')}`}>
              {plan.plan.curva_tension.map((t, i) => (
                <span key={i} className="curva-barra" style={{ '--alto': t / 10 }} title={`Capítulo ${i + 1}: ${t}`} />
              ))}
            </span>
          </dd>
          <dt>Personajes</dt>
          <dd>{plan.personajes.map((p) => p.nombre).join(', ')}</dd>
          <dt>Lugares</dt>
          <dd>{plan.mundo.localizaciones.map((l) => l.nombre).join(', ')}</dd>
        </dl>
      ) : null}
    </Decision>
  )
}

function AprobarFinal({ proyecto, refrescar }) {
  return (
    <Decision
      titulo="El manuscrito está verificado y espera tu aprobación final. Aprobarlo lo publica; si pides cambios, vuelve a revisión."
      decidir={(decision, notas, capitulos) => decidirFinal(proyecto, decision, notas, decision === 'cambios' ? capitulos : null)}
      refrescar={refrescar}
      conCapitulos
    />
  )
}

function Reintentar({ proyecto, refrescar }) {
  const [notas, setNotas] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)
  const enviar = async () => {
    setEnviando(true)
    setError(null)
    try {
      await reintentar(proyecto, notas.trim() || null)
      refrescar()
    } catch (fallo) {
      setError(fallo)
    } finally {
      setEnviando(false)
    }
  }
  return (
    <div className="tarjeta tarjeta-aviso">
      <p>
        El proyecto se detuvo al agotar los intentos de un paso. Reintentar vuelve a esa fase con el contador a cero; después,
        sigue generando desde aquí.
      </p>
      <label className="campo">
        <span>Notas (opcional)</span>
        <textarea value={notas} onChange={(e) => setNotas(e.target.value)} />
      </label>
      <div className="acciones">
        <button type="button" className="boton boton-primario" disabled={enviando} onClick={enviar}>
          Reintentar
        </button>
      </div>
      <ErrorAccion error={error} />
    </div>
  )
}
