import { createElement } from 'react'

import { sanear } from './sanear.js'

/**
 * El HTML de un capítulo, filtrado por la lista blanca y pintado como elementos de React
 * (plan-frontend.md F-6). DOMParser crea un documento inerte: no ejecuta scripts ni carga
 * imágenes, y de él solo se lee la estructura.
 */
export default function Fragmento({ html }) {
  const documento = new DOMParser().parseFromString(html, 'text/html')
  return pintar(sanear(documento.body))
}

/** @param {import('./sanear.js').Nodo[]} nodos */
function pintar(nodos) {
  // La lista no se reordena nunca: el capítulo entero se remonta al cambiar (Capitulo.jsx).
  return nodos.map((n, i) =>
    typeof n === 'string'
      ? n
      : createElement(n.etiqueta, { key: i, 'data-p': n.p }, n.hijos.length > 0 ? pintar(n.hijos) : undefined),
  )
}
