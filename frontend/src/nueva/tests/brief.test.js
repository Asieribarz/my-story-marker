// Todos los datos de persona son ficticios.
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { destinatarioVacio, hechoVacio, respuestasDe } from '../brief.js'

const formulario = (cambios = {}) => ({
  destinatario: { ...destinatarioVacio(), nombre: ' Nadia ', edad: '10', rasgos: 'curiosa, valiente,, ' },
  segundo: destinatarioVacio(),
  ocasion: 'cumpleanos',
  relacion: 'hijo',
  edad_lector: '10',
  hechos: [{ ...hechoVacio(), tipo: 'objeto', texto: 'Una linterna azul', momento: '2020', lugar: 'la playa' }],
  vetos_palabras: '',
  vetos_temas: 'arañas',
  dedicatoria: '',
  tono: '',
  subgenero: '',
  final: '',
  texto_libre: '',
  ...cambios,
})

describe('respuestasDe', () => {
  it('lleva las claves de la entrevista con lo contestado', () => {
    assert.deepEqual(respuestasDe(formulario()), {
      personalizacion: {
        destinatario: { nombre: 'Nadia', edad: 10, rasgos: ['curiosa', 'valiente'], papel: 'protagonista' },
        segundo_destinatario: null,
        ocasion: 'cumpleanos',
        relacion: 'hijo',
        edad_lector: 10,
        hechos: [{ id: 'h1', tipo: 'objeto', texto: 'Una linterna azul', prioridad: 'obligatorio', origen: 'entrevista' }],
        vetos: { palabras: [], temas: ['arañas'] },
      },
    })
  })

  it('solo un recuerdo lleva cuándo y dónde', () => {
    const [hecho] = respuestasDe(formulario({ hechos: [{ ...hechoVacio(), texto: 'La excursión', momento: '2020-07', lugar: 'el faro' }] }))
      .personalizacion.hechos
    assert.equal(hecho.tipo, 'evento')
    assert.deepEqual([hecho.momento, hecho.lugar], ['2020-07', 'el faro'])
  })

  it('los hechos vacíos no se envían y los demás se numeran seguidos', () => {
    const hechos = respuestasDe(
      formulario({ hechos: [{ ...hechoVacio(), texto: '  ' }, { ...hechoVacio(), tipo: 'frase', texto: '¡Al abordaje!' }] }),
    ).personalizacion.hechos
    assert.deepEqual(
      hechos.map((h) => [h.id, h.tipo]),
      [['h1', 'frase']],
    )
  })

  it('el segundo destinatario solo va en boda o aniversario', () => {
    const segundo = { ...destinatarioVacio(), nombre: 'Leo' }
    assert.equal(respuestasDe(formulario({ segundo })).personalizacion.segundo_destinatario, null)
    assert.equal(respuestasDe(formulario({ ocasion: 'boda', segundo })).personalizacion.segundo_destinatario.nombre, 'Leo')
  })

  it('las preferencias solo van si se eligió alguna', () => {
    assert.equal('preferencias' in respuestasDe(formulario()), false)
    assert.deepEqual(respuestasDe(formulario({ tono: 'epico', subgenero: 'nautica' })).preferencias, {
      tono: 'epico',
      subgenero: { primario: 'nautica' },
    })
  })
})
