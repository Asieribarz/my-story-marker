/**
 * La cinta de marcapáginas que marca un capítulo cambiado (plan-frontend.md F-5).
 * Sin `etiqueta` es solo dibujo; con ella, los lectores de pantalla la oyen.
 */
export default function Cinta({ etiqueta, className = '' }) {
  return etiqueta ? (
    <span className={`cinta ${className}`}>
      <span className="solo-lectores">{etiqueta}</span>
    </span>
  ) : (
    <span className={`cinta ${className}`} aria-hidden="true" />
  )
}
