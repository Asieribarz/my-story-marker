import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { sanear } from '../sanear.js'

/** Nodos con la forma mínima que usa sanear, en lugar de un DOM real. */
const texto = (t) => ({ nodeType: 3, nodeName: '#text', nodeValue: t, childNodes: [] })
const comentario = (t) => ({ nodeType: 8, nodeName: '#comment', nodeValue: t, childNodes: [] })
const el = (nombre, atributos = {}, hijos = []) => ({
  nodeType: 1,
  nodeName: nombre.toUpperCase(),
  nodeValue: null,
  childNodes: hijos.map((h) => (typeof h === 'string' ? texto(h) : h)),
  getAttribute: (a) => (a in atributos ? atributos[a] : null),
})
const raiz = (...hijos) => el('body', {}, hijos)

describe('sanear', () => {
  it('conserva la lista blanca con el número de párrafo', () => {
    const r = raiz(
      el('p', { 'data-p': '1' }, ['—Hola, ', el('em', {}, ['dijo']), '.', el('br')]),
      el('hr'),
      el('blockquote', {}, [el('p', { 'data-p': '2' }, [el('strong', {}, ['Fin'])])]),
    )
    assert.deepEqual(sanear(r), [
      { etiqueta: 'p', p: 1, hijos: ['—Hola, ', { etiqueta: 'em', hijos: ['dijo'] }, '.', { etiqueta: 'br', hijos: [] }] },
      { etiqueta: 'hr', hijos: [] },
      { etiqueta: 'blockquote', hijos: [{ etiqueta: 'p', p: 2, hijos: [{ etiqueta: 'strong', hijos: ['Fin'] }] }] },
    ])
  })

  it('descarta enteras las etiquetas que llevan código', () => {
    const r = raiz(
      el('p', { 'data-p': '1' }, ['A', el('script', {}, ['alert(1)']), 'B']),
      el('style', {}, ['p { display: none }']),
      el('iframe', { src: 'https://ejemplo.invalid' }),
      el('svg', {}, [el('script', {}, ['alert(2)'])]),
    )
    assert.deepEqual(sanear(r), [{ etiqueta: 'p', p: 1, hijos: ['A', 'B'] }])
  })

  it('desenvuelve una etiqueta desconocida y conserva solo su texto', () => {
    const r = raiz(
      el('p', { 'data-p': '1' }, [
        el('a', { href: 'javascript:alert(1)' }, ['un enlace']),
        el('span', { style: 'color:red' }, [el('em', {}, ['dentro'])]),
      ]),
    )
    assert.deepEqual(sanear(r), [
      { etiqueta: 'p', p: 1, hijos: ['un enlace', { etiqueta: 'em', hijos: ['dentro'] }] },
    ])
  })

  it('pierde los atributos, incluidos los de evento', () => {
    const r = raiz(el('img', { src: 'x', onerror: 'alert(1)' }), el('em', { onclick: 'alert(2)' }, ['x']))
    assert.deepEqual(sanear(r), [{ etiqueta: 'em', hijos: ['x'] }])
  })

  it('ignora un data-p que no es un entero positivo', () => {
    for (const p of [null, '0', '-1', 'uno', '1.5']) {
      assert.deepEqual(sanear(raiz(el('p', p === null ? {} : { 'data-p': p }, ['x']))), [
        { etiqueta: 'p', hijos: ['x'] },
      ])
    }
  })

  it('descarta comentarios y el contenido de las etiquetas vacías', () => {
    const r = raiz(comentario('<script>'), el('br', {}, ['no debería estar']), texto(''))
    assert.deepEqual(sanear(r), [{ etiqueta: 'br', hijos: [] }])
  })
})
