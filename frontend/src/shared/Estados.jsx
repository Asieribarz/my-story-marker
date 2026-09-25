import { ErrorApi } from './api.js'

/** Solo se ve si la carga tarda: el retraso está en el CSS. */
export function Cargando() {
  return <p className="cargando">Cargando…</p>
}

export function ErrorCarga({ error, reintentar }) {
  const detalle = error instanceof ErrorApi ? error.detalle : 'Algo ha fallado al cargar los datos.'
  return (
    <div className="estado" role="alert">
      <p>{detalle}</p>
      {reintentar ? (
        <button type="button" className="boton" onClick={reintentar}>
          Reintentar
        </button>
      ) : null}
    </div>
  )
}

/** El error de una acción (enviar, confirmar), en línea junto al botón que la lanzó. */
export function ErrorAccion({ error }) {
  if (!error) return null
  const detalle = error instanceof ErrorApi ? error.detalle : 'Algo ha fallado. Vuelve a intentarlo.'
  return (
    <p className="error-accion" role="alert">
      {detalle}
    </p>
  )
}
