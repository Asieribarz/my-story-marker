import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { escribirVentana, leerVentana } from '../navegacion.js'

const P = '0123456789abcdef0123456789abcdef'

describe('leerVentana y escribirVentana', () => {
  const ventanas = [
    { pestana: 'leer', proyecto: null },
    { pestana: 'leer', proyecto: P },
    { pestana: 'metricas', proyecto: null },
    { pestana: 'metricas', proyecto: P },
    { pestana: 'nueva', proyecto: null },
    { pestana: 'nueva', proyecto: P },
  ]
  for (const v of ventanas) {
    it(`ida y vuelta de ${v.pestana} ${v.proyecto ? 'con' : 'sin'} proyecto`, () =>
      assert.deepEqual(leerVentana(escribirVentana(v.pestana, v.proyecto)), v))
  }

  it('las direcciones de la lectura siguen siendo de la lectura', () => {
    for (const hash of [`#/${P}/v2`, `#/${P}/v1/cap/3`, `#/${P}/v1/fichas`]) {
      assert.deepEqual(leerVentana(hash), { pestana: 'leer', proyecto: P })
    }
  })

  it('un proyecto mal formado no se elige', () => {
    assert.deepEqual(leerVentana('#/metricas/abc'), { pestana: 'metricas', proyecto: null })
    assert.deepEqual(leerVentana(`#/nueva/${P}/sobra`), { pestana: 'nueva', proyecto: null })
    assert.deepEqual(leerVentana('#/cualquiera'), { pestana: 'leer', proyecto: null })
  })
})
