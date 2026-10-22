import assert from 'node:assert/strict'
import { test } from 'node:test'
import { feldPruefPfad, meldungenAmFeld } from '../src/diakonos/components/planrahmen/editor.mjs'

test('Feldpfade trennen rekursive Indizes unabhängig von abschließendem Slash', () => {
  assert.equal(feldPruefPfad('felder/', 0), 'felder/0')
  assert.equal(feldPruefPfad('felder/0/inhalt', 1), 'felder/0/inhalt/1')
  assert.equal(feldPruefPfad('/terminreihen/0/felder/', 2), 'terminreihen/0/felder/2')
})

test('Meldungen gehören zum betroffenen Feld, nicht zu gleich beginnenden Indizes', () => {
  const messages = [
    {pfad:'/felder/1/id', meldung:'Kennung fehlt'},
    {pfad:'/felder/10/id', meldung:'Anderes Feld'},
    {pfad:'/felder/1/inhalt/0/id', meldung:'Unterfeld'},
  ]
  assert.deepEqual(meldungenAmFeld(messages, 'felder/1'), [messages[0], messages[2]])
  assert.deepEqual(meldungenAmFeld(messages, 'felder/1/inhalt/0'), [messages[2]])
})
