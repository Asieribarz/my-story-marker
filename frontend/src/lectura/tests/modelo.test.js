import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  arbolDeLugares,
  capituloEnLetra,
  conjuncion,
  enumerar,
  fechaLegible,
  rolesLegibles,
  versionVigente,
} from '../modelo.js'

describe('enumerar', () => {
  it('une con comas y la conjunción final', () => {
    assert.equal(enumerar([]), '')
    assert.equal(enumerar(['3']), '3')
    assert.equal(enumerar(['3', '7']), '3 y 7')
    assert.equal(enumerar(['1', '2', '5']), '1, 2 y 5')
  })

  it('usa «e» ante el sonido /i/, no ante «hie»', () => {
    assert.equal(conjuncion('interés'), 'e')
    assert.equal(conjuncion('Iván'), 'e')
    assert.equal(conjuncion('hijo'), 'e')
    assert.equal(conjuncion('hielo'), 'y')
    assert.equal(conjuncion('Chispa'), 'y')
    assert.equal(rolesLegibles(['aliado', 'interes_romantico']), 'aliado e interés romántico')
  })
})

describe('capituloEnLetra', () => {
  it('escribe en letra del uno al diez', () => {
    assert.equal(capituloEnLetra(1), 'Capítulo uno')
    assert.equal(capituloEnLetra(10), 'Capítulo diez')
    assert.equal(capituloEnLetra(11), 'Capítulo 11')
  })
})

describe('fechaLegible', () => {
  it('toma una fecha sin hora como fecha local', () => {
    assert.equal(fechaLegible('2026-09-20'), '20 de septiembre de 2026')
  })
})

describe('versionVigente', () => {
  it('es la última publicada', () => {
    assert.equal(versionVigente({ versiones: [{ version: 1 }, { version: 2 }] }), 2)
  })
})

describe('arbolDeLugares', () => {
  const lugar = (id, padre) => ({ id, nombre: id, padre, capitulos: [] })

  it('anida según padre y conserva el orden', () => {
    const arbol = arbolDeLugares([lugar('costa', null), lugar('puerto', 'costa'), lugar('casa', 'puerto'), lugar('isla', 'costa')])
    const ids = (nodos) => nodos.map((n) => [n.lugar.id, ids(n.hijos)])
    assert.deepEqual(ids(arbol), [['costa', [['puerto', [['casa', []]]], ['isla', []]]]])
  })

  it('cuelga de la raíz un lugar con padre desconocido', () => {
    const arbol = arbolDeLugares([lugar('a', null), lugar('b', 'nadie')])
    assert.deepEqual(arbol.map((n) => n.lugar.id), ['a', 'b'])
  })
})
