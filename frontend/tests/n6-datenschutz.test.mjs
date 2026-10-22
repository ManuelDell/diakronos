import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { gefiltertePersonen, zweiteBestaetigung } from '../src/diakonos/components/mitglieder/datenschutz.mjs'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = p => readFileSync(new URL(p, root), 'utf8')

test('N6: Personenfilter statt Protokollzählung, Suche nach Name und E-Mail', () => {
  const personen = [
    { vorname: 'Änne', email: 'anna@example.org', dsgvo_status: 'ok' },
    { vorname: 'Ben', dsgvo_status: 'widerrufen' },
    { vorname: 'Clara', dsgvo_status: 'fehlt' },
  ]
  assert.equal(gefiltertePersonen(personen, '', '').length, 3)
  assert.equal(gefiltertePersonen(personen, 'ok', 'EXAMPLE').length, 1)
  assert.equal(gefiltertePersonen(personen, '', '  änne ').length, 1)
  assert.equal(gefiltertePersonen(personen, 'fehlt', 'Ben').length, 0)
})

test('N6: zwei Schritte plus exakter Text, kein Durchklicken ohne Text', () => {
  assert.equal(zweiteBestaetigung(1, 'ANONYMISIEREN'), false)
  assert.equal(zweiteBestaetigung(2, ''), false)
  assert.equal(zweiteBestaetigung(2, 'anonymisieren'), false)
  assert.equal(zweiteBestaetigung(2, 'ANONYMISIEREN'), true)
})

test('N6: Verwaltungsreiter ersetzt die falsche eigene DSGVO-Seite', () => {
  assert.equal(existsSync(new URL('pages/Dsgvo.vue', root)), false)
  assert.match(lies('pages/mitglieder/Bereich.vue'), /import\('\.\/Datenschutz.vue'\)/)
  assert.doesNotMatch(lies('router.js'), /Dsgvo:|import\('\.\/pages\/Dsgvo.vue'\)/)
  const page = lies('pages/mitglieder/Datenschutz.vue')
  assert.match(page, /get_loeschantraege/)
  assert.match(page, /createObjectURL/)
  assert.match(page, /nur_antrag: istAntrag.value/)
  assert.match(page, /:close-on-overlay="false"/)
  assert.match(page, /zweiteBestaetigung\(schritt.value, wort.value\)/)
  assert.match(page, /if \(sendet.value\) return/)
  assert.doesNotMatch(page, /window.confirm|window.prompt|alert\(/)
})
