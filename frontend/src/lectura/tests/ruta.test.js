import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { escribirRuta, leerRuta } from '../ruta.js'

const P = '0123456789abcdef0123456789abcdef'

describe('leerRuta y escribirRuta', () => {
  const rutas = [
    { pantalla: 'vigente', proyecto: P },
    { pantalla: 'portada', proyecto: P, version: 2 },
    { pantalla: 'fichas', proyecto: P, version: 1 },
    { pantalla: 'capitulo', proyecto: P, version: 3, capitulo: 10 },
  ]
  for (const ruta of rutas) {
    it(`ida y vuelta de ${ruta.pantalla}`, () => assert.deepEqual(leerRuta(escribirRuta(ruta)), ruta))
  }

  it('sin nada detrás de «#» no hay proyecto', () => {
    for (const hash of ['', '#', '#/']) assert.deepEqual(leerRuta(hash), { pantalla: 'sin_proyecto' })
  })

  it('admite una barra final', () => {
    assert.deepEqual(leerRuta(`#/${P}/v2/`), { pantalla: 'portada', proyecto: P, version: 2 })
  })

  it('rechaza lo que no es una dirección de la lectura', () => {
    const invalidas = [
      '#/no-es-un-proyecto',
      `#/${P.toUpperCase()}`,
      `#/${P}/2`,
      `#/${P}/v0`,
      `#/${P}/v02`,
      `#/${P}/v2/cap`,
      `#/${P}/v2/cap/0`,
      `#/${P}/v2/cap/tres`,
      `#/${P}/v2/cap/3/mas`,
      `#/${P}/v2/fichas/1`,
      `#/${P}/v2/otra`,
      `#//${P}`,
    ]
    for (const hash of invalidas) assert.deepEqual(leerRuta(hash), { pantalla: 'desconocida' }, hash)
  })
})
