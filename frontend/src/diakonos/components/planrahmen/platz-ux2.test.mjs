import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

// FACH 2: Der Composable ruft den Server-Endpunkt 'platz_hinzufuegen' mit
// plan/termin/feld_pfad auf und gibt ihn über usePlanrahmen() frei. Kein
// erfundener Endpunktname, kein anderer Parametersatz.
test('platzHinzufuegen ist als Endpunkt verdrahtet und exportiert', () => {
  const source = readFileSync(new URL('../../composables/usePlanrahmen.js', import.meta.url), 'utf8')
  assert.match(source, /call\('platz_hinzufuegen',\s*\{\s*plan,\s*termin,\s*feld_pfad:\s*feldPfad\s*\}\)/)
  assert.match(source, /platzHinzufuegen,/)
})

// Regression: Die Sichtbarkeit von '+ <Feld> hinzufuegen' hing früher an
// 'props.slots.length' (irgendein Slot des Termins). Sobald ein anderer Slot
// (z. B. Lied) existierte, verschwand der Knopf für das noch leere Feld.
// Der Knopf muss sich am GEKLICKTEN Feldpfad entscheiden.
test('kannPlatzHinzufuegen richtet sich nach dem Zielpfad, nicht nach fremden Slots', () => {
  const source = readFileSync(new URL('./PrEditor.vue', import.meta.url), 'utf8')
  const block = source.slice(source.indexOf('const kannPlatzHinzufuegen'))
  const bis = block.indexOf('})')
  const rumpf = block.slice(0, bis)
  assert.doesNotMatch(
    rumpf,
    /props\.slots\.length/,
    'Der Knopf darf nicht von unrelated Slots desselben Termins abhaengen',
  )
  assert.match(rumpf, /slot\.value/)
})
