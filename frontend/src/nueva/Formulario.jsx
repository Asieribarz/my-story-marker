import { useState } from 'react'

import { ErrorAccion } from '../shared/Estados.jsx'
import { escribirVentana } from '../shared/navegacion.js'
import { crearProyecto, enviarBrief } from './api.js'
import {
  CON_SEGUNDO,
  OCASIONES,
  PAPELES,
  RELACIONES,
  SUBGENEROS,
  TIPOS_DE_HECHO,
  TONOS,
  destinatarioVacio,
  hechoVacio,
  respuestasDe,
} from './brief.js'

const inicial = () => ({
  destinatario: destinatarioVacio(),
  segundo: destinatarioVacio(),
  ocasion: 'cumpleanos',
  relacion: 'hijo',
  edad_lector: '',
  hechos: [hechoVacio()],
  vetos_palabras: '',
  vetos_temas: '',
  dedicatoria: '',
  tono: '',
  subgenero: '',
  final: '',
  texto_libre: '',
  etiqueta: '',
  parada_plan: false,
  parada_final: false,
})

/**
 * El brief de una novela nueva, con los bloques de la entrevista de `/entrevista`: crea el
 * proyecto y envía las respuestas y el texto libre. El texto libre va directo al backend,
 * que lo guarda como no confiable y solo lo entrega al Extractor (RF-14). Si el brief falla
 * después de crear el proyecto, se vuelve a enviar al mismo: no quedan proyectos huérfanos.
 */
export default function Formulario() {
  const [f, setF] = useState(inicial)
  const [creado, setCreado] = useState(null)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)
  const [descartes, setDescartes] = useState(null)

  const poner = (clave, valor) => setF((antes) => ({ ...antes, [clave]: valor }))
  const ponerEn = (grupo) => (clave, valor) => setF((antes) => ({ ...antes, [grupo]: { ...antes[grupo], [clave]: valor } }))
  const ponerHecho = (uid, clave, valor) =>
    setF((antes) => ({ ...antes, hechos: antes.hechos.map((h) => (h.uid === uid ? { ...h, [clave]: valor } : h)) }))

  const enviar = async (evento) => {
    evento.preventDefault()
    setEnviando(true)
    setError(null)
    try {
      const etiqueta = f.etiqueta.trim()
      const pedido = { parada_plan: f.parada_plan, parada_final: f.parada_final, ...(etiqueta ? { etiqueta } : {}) }
      const proyecto = creado ?? (await crearProyecto(pedido)).identificador
      setCreado(proyecto)
      const texto = f.texto_libre.trim()
      const guardado = await enviarBrief(proyecto, { respuestas: respuestasDe(f), ...(texto ? { texto_libre: texto } : {}) })
      if (guardado.descartes.length > 0) setDescartes({ proyecto, lista: guardado.descartes })
      else window.location.hash = escribirVentana('nueva', proyecto)
    } catch (fallo) {
      setError(fallo)
    } finally {
      setEnviando(false)
    }
  }

  if (descartes) {
    return (
      <div className="tarjeta tarjeta-aviso">
        <h2>Brief enviado</h2>
        <p>
          Se han descartado algunos datos que la novela no debe guardar:{' '}
          {descartes.lista.map((d) => `${d.campo} (${d.tipo})`).join(', ')}.
        </p>
        <a className="boton boton-primario" href={escribirVentana('nueva', descartes.proyecto)}>
          Ir al seguimiento
        </a>
      </div>
    )
  }

  const hayHechos = f.hechos.some((h) => h.texto.trim())

  return (
    <form className="formulario" onSubmit={enviar}>
      <p className="nota-privacidad">
        Cuenta solo lo que la novela necesita. Nunca incluyas documento de identidad, teléfono, email, dirección exacta,
        datos bancarios ni de salud: si aparecen, el backend los descarta.
      </p>

      <fieldset>
        <legend>Nombre del proyecto (opcional)</legend>
        <p className="ayuda">Solo para reconocerlo en la lista hasta que la novela tenga título. No sale en la novela.</p>
        <Campo etiqueta="Por ejemplo, «Regalo de cumpleaños, septiembre»">
          <input maxLength={60} value={f.etiqueta} disabled={creado !== null} onChange={(e) => poner('etiqueta', e.target.value)} />
        </Campo>
      </fieldset>

      <fieldset>
        <legend>A quién se la regalas</legend>
        <Destinatario valor={f.destinatario} poner={ponerEn('destinatario')} obligatorio />
      </fieldset>

      <fieldset>
        <legend>Ocasión y lectura</legend>
        <div className="rejilla">
          <Campo etiqueta="Ocasión">
            <select value={f.ocasion} onChange={(e) => poner('ocasion', e.target.value)}>
              {OCASIONES.map(([v, n]) => (
                <option key={v} value={v}>
                  {n}
                </option>
              ))}
            </select>
          </Campo>
          <Campo etiqueta="Qué es para ti">
            <select value={f.relacion} onChange={(e) => poner('relacion', e.target.value)}>
              {RELACIONES.map(([v, n]) => (
                <option key={v} value={v}>
                  {n}
                </option>
              ))}
            </select>
          </Campo>
          <Campo etiqueta="Edad de quien la leerá">
            <input type="number" min="0" max="120" required value={f.edad_lector} onChange={(e) => poner('edad_lector', e.target.value)} />
          </Campo>
        </div>
      </fieldset>

      {CON_SEGUNDO.has(f.ocasion) ? (
        <fieldset>
          <legend>Segundo destinatario</legend>
          <Destinatario valor={f.segundo} poner={ponerEn('segundo')} obligatorio />
        </fieldset>
      ) : null}

      <fieldset>
        <legend>Hechos que no pueden faltar</legend>
        <p className="ayuda">Hasta cinco imprescindibles y los deseables que quieras.</p>
        {f.hechos.map((h, i) => (
          <div className="hecho" key={h.uid}>
            <div className="rejilla">
              <Campo etiqueta={`Hecho ${i + 1}: qué es`}>
                <select value={h.tipo} onChange={(e) => ponerHecho(h.uid, 'tipo', e.target.value)}>
                  {TIPOS_DE_HECHO.map(([v, n]) => (
                    <option key={v} value={v}>
                      {n}
                    </option>
                  ))}
                </select>
              </Campo>
              <Campo etiqueta="Prioridad">
                <select value={h.prioridad} onChange={(e) => ponerHecho(h.uid, 'prioridad', e.target.value)}>
                  <option value="obligatorio">Imprescindible</option>
                  <option value="deseable">Deseable</option>
                </select>
              </Campo>
            </div>
            <Campo etiqueta="Cuéntalo">
              <textarea value={h.texto} onChange={(e) => ponerHecho(h.uid, 'texto', e.target.value)} />
            </Campo>
            {h.tipo === 'evento' ? (
              <div className="rejilla">
                <Campo etiqueta="Cuándo (AAAA, AAAA-MM, AAAA-MM-DD o «infancia»)">
                  <input value={h.momento} onChange={(e) => ponerHecho(h.uid, 'momento', e.target.value)} />
                </Campo>
                <Campo etiqueta="Dónde">
                  <input value={h.lugar} onChange={(e) => ponerHecho(h.uid, 'lugar', e.target.value)} />
                </Campo>
              </div>
            ) : null}
            {f.hechos.length > 1 ? (
              <button
                type="button"
                className="boton-texto"
                onClick={() => poner('hechos', f.hechos.filter((x) => x.uid !== h.uid))}
              >
                Quitar este hecho
              </button>
            ) : null}
          </div>
        ))}
        <button type="button" className="boton" onClick={() => poner('hechos', [...f.hechos, hechoVacio()])}>
          + Añadir otro hecho
        </button>
      </fieldset>

      <fieldset>
        <legend>Lo que no debe aparecer</legend>
        <div className="rejilla">
          <Campo etiqueta="Palabras (separadas por comas)">
            <input value={f.vetos_palabras} onChange={(e) => poner('vetos_palabras', e.target.value)} />
          </Campo>
          <Campo etiqueta="Temas (separados por comas)">
            <input value={f.vetos_temas} onChange={(e) => poner('vetos_temas', e.target.value)} />
          </Campo>
        </div>
      </fieldset>

      <fieldset>
        <legend>Dedicatoria y preferencias</legend>
        <Campo etiqueta="Dedicatoria de la portada">
          <textarea value={f.dedicatoria} onChange={(e) => poner('dedicatoria', e.target.value)} />
        </Campo>
        <div className="rejilla">
          <Campo etiqueta="Tono">
            <select value={f.tono} onChange={(e) => poner('tono', e.target.value)}>
              {TONOS.map(([v, n]) => (
                <option key={v} value={v}>
                  {n}
                </option>
              ))}
            </select>
          </Campo>
          <Campo etiqueta="Tipo de aventura">
            <select value={f.subgenero} onChange={(e) => poner('subgenero', e.target.value)}>
              {SUBGENEROS.map(([v, n]) => (
                <option key={v} value={v}>
                  {n}
                </option>
              ))}
            </select>
          </Campo>
        </div>
        <Campo etiqueta="Cómo te gustaría que acabara (opcional)">
          <input value={f.final} onChange={(e) => poner('final', e.target.value)} />
        </Campo>
      </fieldset>

      <fieldset>
        <legend>Una anécdota o carta (opcional)</legend>
        <p className="ayuda">
          Se guarda aparte como texto no confiable. Solo la lee el Extractor, que te propondrá hechos para que confirmes cuáles
          entran.
        </p>
        <Campo etiqueta="Texto libre">
          <textarea className="texto-libre" value={f.texto_libre} onChange={(e) => poner('texto_libre', e.target.value)} />
        </Campo>
      </fieldset>

      <fieldset>
        <legend>Paradas para revisar</legend>
        <label className="casilla">
          <input type="checkbox" checked={f.parada_plan} disabled={creado !== null} onChange={(e) => poner('parada_plan', e.target.checked)} />
          Quiero aprobar el plan antes de que se escriba
        </label>
        <label className="casilla">
          <input type="checkbox" checked={f.parada_final} disabled={creado !== null} onChange={(e) => poner('parada_final', e.target.checked)} />
          Quiero aprobar el manuscrito antes de publicarlo
        </label>
      </fieldset>

      <div className="formulario-pie">
        <button type="submit" className="boton boton-primario" disabled={enviando || !f.destinatario.nombre.trim()}>
          {enviando ? 'Enviando…' : creado ? 'Volver a enviar el brief' : 'Crear la novela'}
        </button>
        {!hayHechos ? <span className="ayuda">Sin hechos, la novela solo se personaliza con los datos del destinatario.</span> : null}
      </div>
      <ErrorAccion error={error} />
    </form>
  )
}

function Destinatario({ valor, poner, obligatorio }) {
  return (
    <div className="rejilla">
      <Campo etiqueta="Nombre, tal como quieres que aparezca">
        <input required={obligatorio} value={valor.nombre} onChange={(e) => poner('nombre', e.target.value)} />
      </Campo>
      <Campo etiqueta="Fecha de nacimiento">
        <input type="date" value={valor.fecha_nacimiento} onChange={(e) => poner('fecha_nacimiento', e.target.value)} />
      </Campo>
      <Campo etiqueta="o edad">
        <input type="number" min="0" max="120" value={valor.edad} onChange={(e) => poner('edad', e.target.value)} />
      </Campo>
      <Campo etiqueta="Papel en la historia">
        <select value={valor.papel} onChange={(e) => poner('papel', e.target.value)}>
          {PAPELES.map(([v, n]) => (
            <option key={v} value={v}>
              {n}
            </option>
          ))}
        </select>
      </Campo>
      <Campo etiqueta="De 3 a 5 rasgos (separados por comas)" ancho>
        <input value={valor.rasgos} onChange={(e) => poner('rasgos', e.target.value)} />
      </Campo>
    </div>
  )
}

function Campo({ etiqueta, children, ancho = false }) {
  return (
    <label className={ancho ? 'campo campo-ancho' : 'campo'}>
      <span>{etiqueta}</span>
      {children}
    </label>
  )
}
