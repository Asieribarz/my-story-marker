// Comprueba ficheros lectura.json o versiones.json contra el contrato de specs/plan-frontend.md §5.
//
//   npm run validar-lectura -- ../proyectos/<id>/export/v1/lectura.json [más ficheros…]
//
// Sale con código 1 si algún fichero no cumple.

import { readFileSync } from 'node:fs'

import { validarLectura, validarVersiones } from '../src/lectura/contrato.js'

const ficheros = process.argv.slice(2)
if (ficheros.length === 0) {
  console.error('Uso: npm run validar-lectura -- <lectura.json | versiones.json> [...]')
  process.exit(2)
}

let fallos = 0
for (const fichero of ficheros) {
  let dato
  try {
    dato = JSON.parse(readFileSync(fichero, 'utf8'))
  } catch (error) {
    console.error(`✗ ${fichero}: no se puede leer como JSON (${error.message})`)
    fallos += 1
    continue
  }
  const errores = dato && 'versiones' in dato ? validarVersiones(dato) : validarLectura(dato)
  if (errores.length === 0) console.log(`✓ ${fichero}`)
  else {
    fallos += 1
    console.error(`✗ ${fichero}`)
    for (const e of errores) console.error(`  · ${e}`)
  }
}
process.exit(fallos === 0 ? 0 : 1)
