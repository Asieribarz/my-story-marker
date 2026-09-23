import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

import { validarCoherencia, validarLectura, validarVersiones } from '../contrato.js'

const leer = (ruta) => JSON.parse(readFileSync(new URL(`../fixture/${ruta}`, import.meta.url), 'utf8'))

/** Una lectura mínima que cumple el contrato; cada prueba rompe una cosa. */
function base() {
  return {
    version: 2,
    anterior: 1,
    cambiados: [3],
    portada: { titulo: 'Título', dedicatoria: null },
    capitulos: Array.from({ length: 10 }, (_, i) => ({
      numero: i + 1,
      titulo: `Capítulo ${i + 1}`,
      html: '<p data-p="1">Uno.</p><hr><p data-p="2">—Dos <em>y</em> <strong>tres</strong>.<br/>Cuatro &lt; cinco.</p>',
    })),
    personajes: [{ id: 'prot', nombre: 'Protagonista', rol: ['protagonista'], capitulos: [1, 2] }],
    lugares: [
      { id: 'macro', nombre: 'Región', padre: null, capitulos: [] },
      { id: 'micro', nombre: 'Casa', descripcion: 'Una casa.', padre: 'macro', capitulos: [1] },
    ],
  }
}

const conHtml = (html) => {
  const l = base()
  l.capitulos[0].html = html
  return l
}

describe('el fixture cumple el contrato', () => {
  const versiones = leer('versiones.json')
  const lecturas = versiones.versiones.map((v) => leer(`v${v.version}/lectura.json`))

  it('versiones', () => assert.deepEqual(validarVersiones(versiones), []))
  for (const l of lecturas) {
    it(`lectura de la versión ${l.version}`, () => assert.deepEqual(validarLectura(l), []))
  }
  it('las versiones cuadran con sus lecturas', () =>
    assert.deepEqual(validarCoherencia(versiones, lecturas), []))
  it('declara que sus datos son ficticios', () => {
    for (const d of [versiones, ...lecturas]) assert.match(d._aviso, /ficticios/)
  })
})

describe('validarLectura', () => {
  it('acepta la lectura base', () => assert.deepEqual(validarLectura(base()), []))

  it('ignora las claves que no conoce', () =>
    assert.deepEqual(validarLectura({ ...base(), _aviso: 'x', extra: 1 }), []))

  it('rechaza una etiqueta fuera de la lista blanca', () => {
    const errores = validarLectura(conHtml('<p data-p="1">Hola<script>alert(1)</script></p>'))
    assert.ok(errores.some((e) => e.includes('<script>')))
  })

  it('rechaza atributos de más en un párrafo', () => {
    const errores = validarLectura(conHtml('<p data-p="1" onclick="x()">Hola</p>'))
    assert.ok(errores.some((e) => e.includes('único atributo')))
  })

  it('rechaza atributos en las demás etiquetas', () => {
    const errores = validarLectura(conHtml('<p data-p="1"><em class="x">Hola</em></p>'))
    assert.ok(errores.some((e) => e.includes('no admite atributos')))
  })

  it('rechaza párrafos mal numerados', () => {
    const errores = validarLectura(conHtml('<p data-p="1">A</p><p data-p="3">B</p>'))
    assert.ok(errores.some((e) => e.includes('tocaba 2')))
  })

  it('rechaza un «<» sin escapar', () => {
    const errores = validarLectura(conHtml('<p data-p="1">3 < 4</p>'))
    assert.ok(errores.some((e) => e.includes('escapado')))
  })

  it('rechaza un comentario HTML', () => {
    const errores = validarLectura(conHtml('<p data-p="1">A</p><!-- nota -->'))
    assert.ok(errores.some((e) => e.includes('escapado')))
  })

  it('rechaza un capítulo sin párrafos', () => {
    assert.ok(validarLectura(conHtml('<hr>')).some((e) => e.includes('ningún párrafo')))
  })

  it('exige exactamente diez capítulos', () => {
    const l = base()
    l.capitulos.pop()
    assert.ok(validarLectura(l).some((e) => e.includes('exactamente 10')))
  })

  it('exige que anterior sea la versión previa', () => {
    assert.ok(validarLectura({ ...base(), anterior: null }).some((e) => e.startsWith('anterior')))
    assert.ok(
      validarLectura({ ...base(), version: 1, anterior: null }).some((e) => e.includes('primera versión')),
    )
  })

  it('exige capítulos cambiados ascendentes y en rango', () => {
    assert.ok(validarLectura({ ...base(), cambiados: [7, 3] }).some((e) => e.includes('ascendentes')))
    assert.ok(validarLectura({ ...base(), cambiados: [11] }).some((e) => e.includes('entre 1 y 10')))
  })

  it('rechaza un rol que no es de definitions §4', () => {
    const l = base()
    l.personajes[0].rol = ['villano']
    assert.ok(validarLectura(l).some((e) => e.includes('villano')))
  })

  it('rechaza ids repetidos', () => {
    const l = base()
    l.personajes.push({ ...l.personajes[0] })
    assert.ok(validarLectura(l).some((e) => e.includes('repetido')))
  })

  it('rechaza un padre desconocido y un ciclo de padres', () => {
    const desconocido = base()
    desconocido.lugares[1].padre = 'nadie'
    assert.ok(validarLectura(desconocido).some((e) => e.includes('"nadie"')))

    const ciclo = base()
    ciclo.lugares[0].padre = 'micro'
    assert.ok(validarLectura(ciclo).some((e) => e.includes('ciclo')))
  })
})

describe('validarVersiones y validarCoherencia', () => {
  const versiones = {
    versiones: [
      { version: 1, publicada: '2026-09-20', cambiados: [] },
      { version: 2, publicada: '2026-09-22T10:30:00Z', cambiados: [3] },
    ],
  }

  it('acepta versiones consecutivas con fecha ISO', () => assert.deepEqual(validarVersiones(versiones), []))

  it('rechaza una lista vacía, un salto de versión y una fecha que no es ISO', () => {
    assert.equal(validarVersiones({ versiones: [] }).length, 1)
    const salto = { versiones: [versiones.versiones[0], { ...versiones.versiones[1], version: 3 }] }
    assert.ok(validarVersiones(salto).some((e) => e.includes('debe ser 2')))
    const fecha = { versiones: [{ ...versiones.versiones[0], publicada: '20/09/2026' }] }
    assert.ok(validarVersiones(fecha).some((e) => e.includes('ISO')))
  })

  it('detecta cambiados distintos entre la versión y su lectura', () => {
    const v1 = { ...base(), version: 1, anterior: null, cambiados: [] }
    const v2 = { ...base(), cambiados: [4] }
    assert.ok(validarCoherencia(versiones, [v1, v2]).some((e) => e.includes('versión 2')))
  })
})
