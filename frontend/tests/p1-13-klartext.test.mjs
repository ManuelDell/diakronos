// P1-13 / UXP-R14: Meldungstexte duerfen nicht verstuemmelt werden.
//
// Befund: `meldungsKurz` erkannte mit /(?:fuer|für|Pflichtfeld) ([\w…]+)/
// einen "Feldpfad" NACH dem Wort "für" und ersetzte jedes Vorkommen dieses
// Wortes im Text durch die Feldbeschriftung. Dadurch wurde aus
// "Dank für Golgatha: erst 0 von 2 Uebungen ..." die Meldung
// "Dank für Eintrag erst 0 von 2 Uebungen ..." und aus
// "Dafür fehlt dir die Berechtigung." wurde "Dafür Eintrag dir die
// Berechtigung.".
//
// Die Behebung nimmt den Pfad NUR noch aus m.feld_pfad/m.pfad (bzw. aus der
// ausdruecklichen Feld-Form "Feld '...'"), nie aus freiem Text.
import test from 'node:test'
import assert from 'node:assert/strict'
import { meldungsKurz } from '../src/diakonos/components/planrahmen/klartext.mjs'

const definition = { felder: [
  { id: 'lieder', name: 'Lied', art: 'eintrag', inhalt: [{ id: 'dirigent', name: 'Dirigent', art: 'person' }] },
] }

test('UXP-R14: Liedttitel mit "für" bleibt unveraendert', () => {
  const text = 'Dank für Golgatha: erst 0 von 2 Uebungen vor So., 11.10.2026.'
  const kurz = meldungsKurz({ meldung: text, feld_pfad: 'lieder[0]' }, definition)
  assert.match(kurz, /Dank für Golgatha/)
  assert.doesNotMatch(kurz, /Eintrag/)
})

test('UXP-R14: "Dafür fehlt dir die Berechtigung." bleibt lesbar', () => {
  const kurz = meldungsKurz({ meldung: 'Dafür fehlt dir die Berechtigung.' }, definition)
  assert.equal(kurz, 'Dafür fehlt dir die Berechtigung.')
})

test('UXP-R14: echte Feldpfade werden weiterhin ersetzt', () => {
  const kurz = meldungsKurz({
    meldung: 'Für lieder[0].dirigent gibt es keinen passenden Vorschlag.',
    feld_pfad: 'lieder[0].dirigent',
  }, definition)
  assert.match(kurz, /Lied 1 · Dirigent/)
  assert.doesNotMatch(kurz, /lieder\[0\]|\.dirigent/)
})

test('UXP-R14: ausdrueckliche Feld-Form wird ersetzt, freier Text nicht', () => {
  const kurz = meldungsKurz({ meldung: "Feld 'lieder[0].dirigent' ist leer." }, definition)
  // Der Pfad in Anfuehrungszeichen wird zur Beschriftung, der Satz bleibt.
  assert.equal(kurz, "Feld 'Lied 1 · Dirigent' ist leer.")
  assert.doesNotMatch(kurz, /lieder\[0\]|\.dirigent/)
})

test('UXP-R14: "Uebungen" wird als "Übungen" ausgegeben', () => {
  const kurz = meldungsKurz({
    meldung: 'Lied 3: erst 0 von 2 Uebungen vor So., 11.10.2026.',
    feld_pfad: 'lieder[0]',
  }, definition)
  assert.match(kurz, /Übungen/)
  assert.doesNotMatch(kurz, /Uebungen/)
})
