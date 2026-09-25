import { useEffect } from 'react'

import './metricas.css'

import { Cargando, ErrorCarga } from '../shared/Estados.jsx'
import { escribirVentana } from '../shared/navegacion.js'
import { fechaCorta, nombreDeEstado, nombreDeProyecto } from '../shared/proyectos.js'
import { useCarga } from '../shared/useCarga.js'
import { obtenerMetricas } from './api.js'
import { compacto, duracion, entero, modeloCorto, tokensTotales } from './formato.js'

/**
 * Las métricas de creación del proyecto elegido: tiempo, intentos y reintentos, tokens y
 * tiempo de agente, por fase, agente y capítulo; hallazgos de los verificadores, la nota
 * del juez y los cambios del lector. El gasto es de suscripción: tokens y tiempo, no dinero.
 *
 * @param {{ proyecto: string | null, proyectos: import('../shared/proyectos.js').ProyectoListado[] | null }} props
 */
export default function Metricas({ proyecto, proyectos }) {
  useEffect(() => {
    document.title = 'Métricas'
  }, [])

  // Sin proyecto elegido, el más reciente.
  const primero = proyectos?.[0]?.identificador ?? null
  useEffect(() => {
    if (!proyecto && primero) window.location.replace(escribirVentana('metricas', primero))
  }, [proyecto, primero])

  if (!proyecto) {
    if (proyectos === null || primero) return <Cargando />
    return (
      <main className="panel">
        <h1>Métricas</h1>
        <p className="panel-sub">
          Aún no hay proyectos. <a href="#/nueva">Crea una novela</a> y aquí verás cómo se hizo.
        </p>
      </main>
    )
  }
  const listado = proyectos?.find((p) => p.identificador === proyecto) ?? null
  return <Panel proyecto={proyecto} listado={listado} />
}

function Panel({ proyecto, listado }) {
  const carga = useCarga(`metricas:${proyecto}`, (senal) => obtenerMetricas(proyecto, senal))
  if (carga.error) return <ErrorCarga error={carga.error} reintentar={carga.reintentar} />
  if (!carga.dato) return <Cargando />
  const m = carga.dato
  const r = m.resumen
  const tokens = tokensTotales(r.consumo)

  return (
    <main className="panel">
      <div className="panel-cabeza">
        <div>
          <h1>{listado ? nombreDeProyecto(listado) : 'Métricas'}</h1>
          <p className="panel-sub">
            <span className="chip">{nombreDeEstado(r.estado)}</span> · creada el {fechaCorta(r.creado)}
          </p>
        </div>
        <button type="button" className="boton" onClick={carga.reintentar}>
          Actualizar
        </button>
      </div>

      <section aria-label="Resumen" className="cifras">
        <Cifra titulo="Tiempo total" valor={duracion(r.duracion_s)} nota={r.estado === 'publicada' ? 'hasta publicarse' : 'hasta ahora'} />
        <Cifra titulo="Tiempo de agentes" valor={duracion(r.consumo.duracion_ms / 1000)} nota="suma de los intentos" />
        <Cifra titulo="Intentos" valor={entero(r.intentos.ordenes)} nota={`${entero(r.intentos.aceptadas)} aceptados`} />
        <Cifra
          titulo="Reintentos"
          valor={entero(r.intentos.reintentos)}
          nota={`${entero(r.intentos.rechazadas)} rechazados · ${entero(r.intentos.caducadas)} caducados`}
        />
        <Cifra
          titulo="Tokens"
          valor={compacto(tokens)}
          nota={`${compacto(r.consumo.tokens_entrada)} entrada · ${compacto(r.consumo.tokens_salida)} salida`}
        />
        <Cifra
          titulo="Caché"
          valor={compacto(r.consumo.tokens_cache_lectura)}
          nota={`leídos · ${compacto(r.consumo.tokens_cache_creacion)} escritos`}
        />
        <Cifra titulo="Ciclos de revisión" valor={entero(r.ciclos_revision)} nota={`${entero(r.pasadas_manuscrito)} pasadas de verificación`} />
        <Cifra
          titulo="Versiones"
          valor={entero(r.versiones_publicadas)}
          nota={`${entero(m.cambios.pedidos)} cambios pedidos · ${entero(m.cambios.publicados)} publicados`}
        />
      </section>

      <p className="nota">
        El gasto es de suscripción: se mide en tokens y en tiempo de agente, no en dinero.{' '}
        {r.intentos.ordenes > 0
          ? `${entero(r.consumo.con_metadatos)} de ${entero(r.intentos.ordenes)} intentos traen el consumo que registra el hook; los demás no suman.`
          : null}
      </p>

      <h2>Tiempo por fase</h2>
      <Tabla
        columnas={['Fase', 'Entradas', 'Duración', '']}
        filas={m.fases.map((f) => ({
          clave: f.fase,
          celdas: [
            <>
              {nombreDeEstado(f.fase)} {f.en_curso ? <span className="chip">en curso</span> : null}
            </>,
            entero(f.entradas),
            duracion(f.duracion_s),
          ],
          valor: f.duracion_s,
          etiqueta: duracion(f.duracion_s),
        }))}
      />

      <h2>Por agente</h2>
      {m.agentes.length === 0 ? (
        <p className="nota">Aún no ha trabajado ningún agente.</p>
      ) : (
        <Tabla
          columnas={['Agente', 'Modelo', 'Intentos', 'Reintentos', 'Rechazados', 'Entrada', 'Salida', 'Caché leída', 'Tiempo', 'Tokens']}
          filas={m.agentes.map((a) => ({
            clave: a.agente,
            celdas: [
              a.agente,
              a.modelos.map(modeloCorto).join(', ') || '—',
              entero(a.intentos.ordenes),
              entero(a.intentos.reintentos),
              entero(a.intentos.rechazadas),
              compacto(a.consumo.tokens_entrada),
              compacto(a.consumo.tokens_salida),
              compacto(a.consumo.tokens_cache_lectura),
              duracion(a.consumo.duracion_ms / 1000),
            ],
            valor: tokensTotales(a.consumo),
            etiqueta: `${entero(tokensTotales(a.consumo))} tokens`,
          }))}
        />
      )}

      <h2>Por capítulo</h2>
      {m.capitulos.length === 0 ? (
        <p className="nota">Aún no se ha escrito ningún capítulo.</p>
      ) : (
        <Tabla
          columnas={['Capítulo', 'Versiones', 'Intentos', 'Reintentos', 'Rechazados', 'Tokens', 'Tiempo', '']}
          filas={m.capitulos.map((c) => ({
            clave: c.capitulo,
            celdas: [
              c.capitulo,
              entero(c.versiones),
              entero(c.intentos.ordenes),
              entero(c.intentos.reintentos),
              entero(c.intentos.rechazadas),
              compacto(tokensTotales(c.consumo)),
              duracion(c.consumo.duracion_ms / 1000),
            ],
            valor: c.intentos.reintentos,
            etiqueta: `${entero(c.intentos.reintentos)} reintentos`,
          }))}
        />
      )}

      <h2>Verificadores</h2>
      {m.verificadores.length === 0 ? (
        <p className="nota">Aún no hay informes de verificación.</p>
      ) : (
        <Tabla
          columnas={['Verificador', 'Informes', 'Graves', 'Hallazgos']}
          filas={m.verificadores.map((v) => ({
            clave: v.verificador,
            celdas: [v.verificador, entero(v.informes), entero(v.graves)],
            valor: v.hallazgos,
            etiqueta: `${entero(v.hallazgos)} hallazgos`,
          }))}
        />
      )}

      <h2>Juez de manuscrito</h2>
      {m.juez === null ? (
        <p className="nota">El juez aún no ha puntuado el manuscrito.</p>
      ) : (
        <>
          <p className="nota">
            Última evaluación: versión {m.juez.version_novela}, ciclo de revisión {m.juez.ciclo}. De 1 a 5.
          </p>
          <Tabla
            columnas={['Criterio', 'Puntuación']}
            maximo={5}
            filas={m.juez.puntuaciones.map((p) => ({
              clave: p.criterio,
              celdas: [p.criterio.replaceAll('_', ' ')],
              valor: p.puntuacion,
              etiqueta: `${p.puntuacion} / 5`,
            }))}
          />
        </>
      )}

      <h2>Cambios del lector</h2>
      <section aria-label="Cambios del lector" className="cifras cifras-pequenas">
        <Cifra titulo="Pedidos" valor={entero(m.cambios.pedidos)} />
        <Cifra titulo="Publicados" valor={entero(m.cambios.publicados)} />
        <Cifra titulo="Descartados u obsoletos" valor={entero(m.cambios.rechazados)} />
        <Cifra titulo="Fallidos" valor={entero(m.cambios.fallidos)} />
        <Cifra titulo="Regeneraciones" valor={entero(m.cambios.regeneraciones)} nota="trabajos del worker" />
      </section>
    </main>
  )
}

function Cifra({ titulo, valor, nota }) {
  return (
    <div className="cifra">
      <p className="cifra-titulo">{titulo}</p>
      <p className="cifra-valor">{valor}</p>
      {nota ? <p className="cifra-nota">{nota}</p> : null}
    </div>
  )
}

/**
 * Una tabla cuya última columna es una barra de una sola serie. El valor va escrito junto a
 * la barra: el color no lleva información que el texto no diga.
 */
function Tabla({ columnas, filas, maximo }) {
  const tope = maximo ?? Math.max(1, ...filas.map((f) => f.valor))
  return (
    <div className="tabla-envoltorio">
      <table className="tabla">
        <thead>
          <tr>
            {columnas.map((c, i) => (
              <th key={i} scope="col" className={i > 0 && i < columnas.length - 1 ? 'num' : undefined}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((f) => (
            <tr key={f.clave}>
              {f.celdas.map((c, i) => (i === 0 ? <th key={i} scope="row">{c}</th> : <td key={i} className="num">{c}</td>))}
              <td title={f.etiqueta}>
                <div className="celda-barra">
                  <span className="barra-dato" style={{ '--fraccion': Math.min(1, f.valor / tope) }} aria-hidden="true" />
                  <span className="barra-etiqueta">{f.etiqueta}</span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
