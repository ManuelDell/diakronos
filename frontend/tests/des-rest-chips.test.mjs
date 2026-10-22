/**
 * DES-01 · Filter-Chips: ein Baustein statt 28 handgebauter Knopfzeilen (S9).
 *
 * Befund: Filterknöpfe standen in 12 Seiten als rohe `<button>`-Zeilen, mal
 * mit `dk-filter-chip`, mal mit eigenen Klassen, und Mitglieder nutzte einen
 * anderen Baustein (DkSegment). Dazu kam: Ein Chip liess sich nicht abwählen,
 * die Zahl am Chip war teils die Gesamtzahl, und ohne Treffer blieb die Zeile
 * wortlos leer.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  chipsAus, chipsMitZahlen, filtereNachChip, istAlle, naechsterChip, chipSprechtext,
} from '../src/diakonos/composables/filterChips.mjs'

const gruppen = [
  { name: 'A', gruppenname: 'Chor', dienstbereich_name: 'Musik' },
  { name: 'B', gruppenname: 'Band', dienstbereich_name: 'Musik' },
  { name: 'C', gruppenname: 'Küche', dienstbereich_name: 'Gemeinde' },
  { name: 'D', gruppenname: 'Ohne', dienstbereich_name: '' },
]

test('DES-01 · „Alle“ steht vorn und zählt alle Einträge', () => {
  const chips = chipsAus(gruppen, (g) => g.dienstbereich_name)
  assert.equal(chips[0].id, 'alle')
  assert.equal(chips[0].label, 'Alle')
  assert.equal(chips[0].anzahl, 4)
})

test('DES-01 · je Dienstbereich ein Chip, deutsch sortiert, mit eigener Zahl', () => {
  const chips = chipsAus(gruppen, (g) => g.dienstbereich_name)
  assert.deepEqual(chips.slice(1).map(c => [c.label, c.anzahl]), [
    ['Gemeinde', 1],
    ['Musik', 2],
    ['Ohne Zuordnung', 1],
  ])
})

test('DES-01 · ein fehlender Dienstbereich bekommt einen verständlichen Namen', () => {
  const chips = chipsAus(gruppen, (g) => g.dienstbereich_name)
  // Vorher hiess das „Unbekannt“ — ein erfundener Name für eine leere Angabe.
  assert.equal(chips.some(c => c.label === 'Unbekannt'), false)
  assert.equal(chips.some(c => c.label === 'Ohne Zuordnung'), true)
})

test('DES-01 · leere Liste ergibt genau einen „Alle“-Chip mit 0', () => {
  const chips = chipsAus([], (g) => g.dienstbereich_name)
  assert.deepEqual(chips, [{ id: 'alle', label: 'Alle', anzahl: 0 }])
})

test('DES-01 · Filterung nach Chip stimmt mit der Zahl am Chip überein', () => {
  const chips = chipsAus(gruppen, (g) => g.dienstbereich_name)
  for (const chip of chips) {
    assert.equal(
      filtereNachChip(gruppen, chip.id, (g) => g.dienstbereich_name).length,
      chip.anzahl,
      `Chip „${chip.label}“ zeigt eine andere Zahl als die Filterung liefert`,
    )
  }
})

test('DES-01 · ohne Auswahl bleibt die volle Liste', () => {
  assert.equal(filtereNachChip(gruppen, 'alle', (g) => g.dienstbereich_name).length, 4)
  assert.equal(filtereNachChip(gruppen, '', (g) => g.dienstbereich_name).length, 4)
  assert.equal(filtereNachChip(gruppen, null, (g) => g.dienstbereich_name).length, 4)
})

test('DES-01 · ein zweiter Klick auf denselben Chip wählt ihn ab (S9)', () => {
  assert.equal(naechsterChip('Musik', 'Musik'), 'alle')
  assert.equal(naechsterChip('alle', 'Musik'), 'Musik')
  assert.equal(naechsterChip('Musik', 'Gemeinde'), 'Gemeinde')
  // „Alle“ ist der Ruhezustand und schaltet sich nicht selbst ab.
  assert.equal(naechsterChip('Musik', 'alle'), 'alle')
})

test('DES-01 · istAlle erkennt die leeren Formen', () => {
  for (const wert of ['', null, undefined, 'alle']) assert.equal(istAlle(wert), true)
  assert.equal(istAlle('Musik'), false)
  assert.equal(istAlle(0), false)
})

test('DES-01 · Ja/Nein-Chips: „Alle“ summiert die Einzelzahlen', () => {
  const chips = chipsMitZahlen([{ id: 'frei', label: 'Frei', anzahl: 3 }, { id: 'belegt', label: 'Belegt', anzahl: 2 }])
  assert.deepEqual(chips, [
    { id: 'alle', label: 'Alle', anzahl: 5 },
    { id: 'frei', label: 'Frei', anzahl: 3 },
    { id: 'belegt', label: 'Belegt', anzahl: 2 },
  ])
})

test('DES-01 · Vorlesehilfe nennt Zahl und Auswahl', () => {
  assert.equal(chipSprechtext({ id: 'alle', label: 'Alle', anzahl: 26 }, 'alle'), 'Alle, 26 Treffer, gewählt')
  assert.equal(chipSprechtext({ id: 'Musik', label: 'Musik', anzahl: 2 }, 'Musik'), 'Musik, 2 Treffer, gewählt')
  assert.equal(chipSprechtext({ id: 'Musik', label: 'Musik', anzahl: 2 }, 'alle'), 'Musik, 2 Treffer')
})
