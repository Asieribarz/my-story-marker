// @ts-check
/**
 * Contrato de lectura (specs/plan-frontend.md §5): tipos y validador.
 *
 * Sin JSX ni APIs del navegador, porque lo usan también node:test y
 * scripts/validar-lectura.js, que comprueba un lectura.json real del backend.
 * Cada validador devuelve la lista de errores, con la ruta de la clave; vacía si cumple.
 */

/** @typedef {{ numero: number, titulo: string | null, html: string }} CapituloLectura */
/** @typedef {{ id: string, nombre: string, rol: string[], descripcion?: string | null, capitulos: number[] }} Personaje */
/** @typedef {{ id: string, nombre: string, descripcion?: string | null, padre: string | null, capitulos: number[] }} Lugar */
/**
 * @typedef {{
 *   version: number,
 *   anterior: number | null,
 *   cambiados: number[],
 *   portada: { titulo: string, dedicatoria: string | null },
 *   capitulos: CapituloLectura[],
 *   personajes: Personaje[],
 *   lugares: Lugar[],
 * }} Lectura
 */
/** @typedef {{ version: number, publicada: string, cambiados: number[] }} VersionPublicada */
/** @typedef {{ versiones: VersionPublicada[] }} Versiones */

export const NUMERO_CAPITULOS = 10

/** La lista blanca del HTML de capítulo; la comparte el filtro del navegador (sanear.js). */
export const ETIQUETAS_PERMITIDAS = ['p', 'em', 'strong', 'blockquote', 'hr', 'br']

/** Roles narrativos de definitions.md §4. */
export const ROLES = [
  'protagonista',
  'antagonista',
  'mentor',
  'aliado',
  'alivio_comico',
  'interes_romantico',
  'guardian_umbral',
  'traidor',
  'secundario',
]

const FECHA_ISO = /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})?)?$/
const ETIQUETA = /<(\/?)([a-zA-Z][a-zA-Z0-9-]*)([^>]*)>/g
const ATRIBUTO_P = /^\s+data-p="([1-9]\d*)"\s*$/

/** @param {unknown} v @returns {v is Record<string, unknown>} */
const esObjeto = (v) => typeof v === 'object' && v !== null && !Array.isArray(v)
/** @param {unknown} v @returns {v is number} */
const esEntero = (v) => Number.isInteger(v)
/** @param {unknown} v @returns {v is string} */
const esTextoNoVacio = (v) => typeof v === 'string' && v.trim() !== ''

/**
 * Números de capítulo ascendentes, sin repetir y dentro de 1..10.
 * @param {unknown} lista @param {string} ruta @param {string[]} errores
 */
function comprobarNumeros(lista, ruta, errores) {
  if (!Array.isArray(lista)) {
    errores.push(`${ruta}: se esperaba una lista de números de capítulo`)
    return
  }
  lista.forEach((n, i) => {
    if (!esEntero(n) || n < 1 || n > NUMERO_CAPITULOS) {
      errores.push(`${ruta}[${i}]: ${JSON.stringify(n)} no es un capítulo entre 1 y ${NUMERO_CAPITULOS}`)
    } else if (i > 0 && esEntero(lista[i - 1]) && n <= lista[i - 1]) {
      errores.push(`${ruta}: los capítulos deben ir ascendentes y sin repetir`)
    }
  })
}

/**
 * El HTML de un capítulo: solo la lista blanca, sin más atributo que data-p en cada
 * p, numerado desde 1 en orden de aparición, y ningún «<» suelto.
 * @param {string} html @param {string} ruta @param {string[]} errores
 */
export function comprobarHtml(html, ruta, errores) {
  let etiquetas = 0
  let esperado = 1
  for (const [, cierre, nombre, atributos] of html.matchAll(ETIQUETA)) {
    etiquetas += 1
    const etiqueta = nombre.toLowerCase()
    if (!ETIQUETAS_PERMITIDAS.includes(etiqueta)) {
      errores.push(`${ruta}: etiqueta <${etiqueta}> fuera de la lista blanca`)
      continue
    }
    if (cierre) continue
    if (etiqueta === 'p') {
      const marca = ATRIBUTO_P.exec(atributos)
      if (!marca) {
        errores.push(`${ruta}: el párrafo ${esperado} no lleva data-p="${esperado}" como único atributo`)
      } else if (Number(marca[1]) !== esperado) {
        errores.push(`${ruta}: data-p="${marca[1]}" donde tocaba ${esperado}`)
      }
      esperado += 1
    } else if (atributos.replace('/', '').trim() !== '') {
      errores.push(`${ruta}: <${etiqueta}> no admite atributos`)
    }
  }
  if (esperado === 1) errores.push(`${ruta}: el capítulo no tiene ningún párrafo`)
  if ((html.match(/</g) ?? []).length !== etiquetas) {
    errores.push(`${ruta}: hay un «<» que no abre una etiqueta permitida; el texto debe llegar escapado`)
  }
}

/**
 * @param {unknown} lista @param {string} ruta @param {string[]} errores
 * @returns {Set<string>} los ids vistos
 */
function comprobarIds(lista, ruta, errores) {
  const ids = new Set()
  if (!Array.isArray(lista)) {
    errores.push(`${ruta}: se esperaba una lista`)
    return ids
  }
  lista.forEach((e, i) => {
    if (!esObjeto(e)) {
      errores.push(`${ruta}[${i}]: se esperaba un objeto`)
      return
    }
    if (!esTextoNoVacio(e.id)) errores.push(`${ruta}[${i}].id: falta`)
    else if (ids.has(e.id)) errores.push(`${ruta}[${i}].id: «${e.id}» repetido`)
    else ids.add(e.id)
    if (!esTextoNoVacio(e.nombre)) errores.push(`${ruta}[${i}].nombre: falta`)
    if (e.descripcion !== undefined && e.descripcion !== null && typeof e.descripcion !== 'string') {
      errores.push(`${ruta}[${i}].descripcion: debe ser texto`)
    }
    comprobarNumeros(e.capitulos, `${ruta}[${i}].capitulos`, errores)
  })
  return ids
}

/**
 * Valida un lectura.json completo, con el HTML de cada capítulo.
 * @param {unknown} dato
 * @returns {string[]}
 */
export function validarLectura(dato) {
  /** @type {string[]} */
  const errores = []
  if (!esObjeto(dato)) return ['la lectura debe ser un objeto']

  const { version, anterior } = dato
  if (!esEntero(version) || version < 1) errores.push('version: debe ser un entero ≥ 1')
  else if (anterior !== (version === 1 ? null : version - 1)) {
    errores.push(`anterior: debe ser ${version === 1 ? 'null' : version - 1}`)
  }

  comprobarNumeros(dato.cambiados, 'cambiados', errores)
  if (anterior === null && Array.isArray(dato.cambiados) && dato.cambiados.length > 0) {
    errores.push('cambiados: la primera versión no tiene capítulos cambiados')
  }

  const portada = dato.portada
  if (!esObjeto(portada)) errores.push('portada: falta')
  else {
    if (!esTextoNoVacio(portada.titulo)) errores.push('portada.titulo: falta')
    if (portada.dedicatoria !== null && typeof portada.dedicatoria !== 'string') {
      errores.push('portada.dedicatoria: debe ser texto o null')
    }
  }

  const capitulos = dato.capitulos
  if (!Array.isArray(capitulos) || capitulos.length !== NUMERO_CAPITULOS) {
    errores.push(`capitulos: deben ser exactamente ${NUMERO_CAPITULOS}`)
  }
  if (Array.isArray(capitulos)) {
    capitulos.forEach((c, i) => {
      const ruta = `capitulos[${i}]`
      if (!esObjeto(c)) {
        errores.push(`${ruta}: se esperaba un objeto`)
        return
      }
      if (c.numero !== i + 1) errores.push(`${ruta}.numero: debe ser ${i + 1}`)
      if (c.titulo !== null && !esTextoNoVacio(c.titulo)) errores.push(`${ruta}.titulo: texto o null`)
      if (typeof c.html !== 'string') errores.push(`${ruta}.html: falta`)
      else comprobarHtml(c.html, `${ruta}.html`, errores)
    })
  }

  comprobarIds(dato.personajes, 'personajes', errores)
  if (Array.isArray(dato.personajes)) {
    dato.personajes.forEach((p, i) => {
      if (!esObjeto(p)) return
      if (!Array.isArray(p.rol) || p.rol.length === 0) errores.push(`personajes[${i}].rol: falta`)
      else {
        for (const r of p.rol) {
          if (typeof r !== 'string' || !ROLES.includes(r)) {
            errores.push(`personajes[${i}].rol: ${JSON.stringify(r)} no es un rol de definitions §4`)
          }
        }
      }
    })
  }

  const ids = comprobarIds(dato.lugares, 'lugares', errores)
  if (Array.isArray(dato.lugares)) {
    /** @type {Map<string, unknown>} */
    const padres = new Map()
    dato.lugares.forEach((l, i) => {
      if (!esObjeto(l)) return
      if (l.padre !== null && !(typeof l.padre === 'string' && ids.has(l.padre))) {
        errores.push(`lugares[${i}].padre: ${JSON.stringify(l.padre)} no es null ni el id de otro lugar`)
      }
      if (typeof l.id === 'string') padres.set(l.id, l.padre)
    })
    for (const inicio of padres.keys()) {
      const vistos = new Set([inicio])
      let actual = padres.get(inicio)
      while (typeof actual === 'string' && padres.has(actual)) {
        if (vistos.has(actual)) {
          errores.push(`lugares: «${inicio}» está en un ciclo de padres`)
          break
        }
        vistos.add(actual)
        actual = padres.get(actual)
      }
    }
  }

  return errores
}

/**
 * Valida la respuesta de GET /versiones.
 * @param {unknown} dato
 * @returns {string[]}
 */
export function validarVersiones(dato) {
  /** @type {string[]} */
  const errores = []
  if (!esObjeto(dato) || !Array.isArray(dato.versiones) || dato.versiones.length === 0) {
    return ['versiones: se esperaba { versiones: [...] } con al menos una versión']
  }
  dato.versiones.forEach((v, i) => {
    const ruta = `versiones[${i}]`
    if (!esObjeto(v)) {
      errores.push(`${ruta}: se esperaba un objeto`)
      return
    }
    if (v.version !== i + 1) errores.push(`${ruta}.version: debe ser ${i + 1}`)
    if (typeof v.publicada !== 'string' || !FECHA_ISO.test(v.publicada)) {
      errores.push(`${ruta}.publicada: debe ser una fecha ISO 8601`)
    }
    comprobarNumeros(v.cambiados, `${ruta}.cambiados`, errores)
    if (i === 0 && Array.isArray(v.cambiados) && v.cambiados.length > 0) {
      errores.push(`${ruta}.cambiados: la primera versión no tiene capítulos cambiados`)
    }
  })
  return errores
}

/**
 * Las versiones y sus lecturas cuentan lo mismo: una lectura por versión, con el
 * mismo número y los mismos capítulos cambiados.
 * @param {Versiones} versiones
 * @param {Lectura[]} lecturas
 * @returns {string[]}
 */
export function validarCoherencia(versiones, lecturas) {
  /** @type {string[]} */
  const errores = []
  if (lecturas.length !== versiones.versiones.length) {
    errores.push(`hay ${versiones.versiones.length} versiones y ${lecturas.length} lecturas`)
  }
  for (const v of versiones.versiones) {
    const lectura = lecturas.find((l) => l.version === v.version)
    if (!lectura) errores.push(`la versión ${v.version} no tiene lectura`)
    else if (JSON.stringify(lectura.cambiados) !== JSON.stringify(v.cambiados)) {
      errores.push(`versión ${v.version}: cambiados no coincide con los de su lectura`)
    }
  }
  return errores
}
