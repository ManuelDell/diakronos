/**
 * AUSTRITT (A1/A3/A4/A5) — Waechter fuer die Oberflaeche.
 *
 * Geprueft wird, was sich ohne Browser pruefen laesst und beim Umbau leicht
 * kaputtgeht:
 *
 *  * der Dialog fragt Begruendung und Datum ab (kein `confirm()`),
 *  * die Knoepfe haengen am ZUSTAND der Person (Austritt <-> Reaktivieren),
 *  * die Liste blendet Ausgetretene standardmaessig aus (der Status-Chip ist
 *    der einzige Weg, kein zweiter Schalter),
 *  * der Server liefert die Kuerzung — das Frontend baut sie NICHT nach.
 */
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const lies = (p) => readFileSync(new URL('../src/diakonos/' + p, import.meta.url), 'utf8')
const dialog = lies('components/austritt/AustrittDialog.vue')
const detail = lies('pages/MitgliedDetail.vue')
const liste = lies('pages/Mitglieder.vue')
const api = lies('composables/useAustritt.js')

test('Austrittsdialog: Begruendung ist optional, Datum und Bestaetigung ohne confirm()', () => {
  // AUSTRITT-b (N1): die Karte verlangt eine OPTIONALE Begruendung — die
  // Unterscheidung Austritt/Ausschluss trifft der Server (Status/`austritt`),
  // nicht ein Pflichtfeld im Dialog.
  assert.match(dialog, /label="Begründung \(optional\)"/)
  assert.match(dialog, /v-model="grund"/)
  assert.match(dialog, /v-model="datum"/)
  assert.ok(!/Bitte eine Begründung eintragen/.test(dialog), 'keine Begruendungspflicht')
  assert.ok(!/\n\s+required\n/.test(dialog), 'kein required am Feld')
  assert.match(dialog, /maxlength="500"/)
  // Kein Browser-confirm: die Entscheidung gehoert in den Dialog.
  // Geprueft wird das SKRIPT (der Kommentarkopf nennt den alten Weg).
  const skript = dialog.slice(dialog.indexOf('<script setup>'))
  assert.ok(!/\bconfirm\(/.test(skript))
  assert.match(dialog, /emit\('austritt'/)
  assert.match(dialog, /emit\('reaktivieren'/)
})

test('Detailseite: Austritt und Reaktivieren haengen am Zustand der Person', () => {
  assert.match(detail, /austrittLage\.art === 'austritt'/)
  assert.match(detail, />Reaktivieren</)
  assert.match(detail, /Austritt \/ Deaktivieren/)
  // Der Reaktivieren-Knopf erscheint NUR beim Austritt, nicht beim Ausschluss.
  assert.match(detail, /canEdit && austrittLage\.art === 'ausschluss'/)
  assert.match(detail, /Ausgeschlossen seit/)
  assert.match(detail, /Ausgetreten seit/)
})

test('Liste: Ausgetretene nur ueber den Status-Chip (kein zweiter Schalter)', () => {
  // AUSTRITT-b (N4): der tote Schalter (`zeigtAusgetretene`,
  // `ausgetreteneUmschalten`, „Ausgetretene anzeigen“) ist entfernt — es gibt
  // genau EINEN Weg, Ausgetretene anzuzeigen: den Status-Chip „Ausgetreten“.
  assert.ok(!/zeigtAusgetretene|ausgetreteneUmschalten|Ausgetretene anzeigen/.test(liste))
  assert.match(liste, /'Passiver Gast', 'Ausgetreten'\]/)
  assert.match(liste, /if \(s === 'Ausgetreten'\) return 'err'/)
})

test('Kuerzung kommt vom Server — das Frontend rechnet sie nicht nach', () => {
  // Keine eigene Namenskuerzung/Maskierung im Client (Sonst gaebe es zwei
  // Wahrheiten, und die API lieferte weiter Klarnamen).
  for (const quelle of [liste, detail]) {
    assert.ok(!/maskiereMail|kuerzeName|vorname\s*\+\s*'\.'/.test(quelle))
  }
  assert.match(api, /mitglied_austritt/)
  assert.match(api, /mitglied_reaktivieren/)
  // AUSTRITT-d (NB3): die Art kommt vom Server, nicht aus der Begruendung.
  assert.match(api, /const art = a\.art \?\? \(a\.ausgetreten \? 'austritt' : ''\)/)
  assert.ok(!/a\.grund === null \|\| a\.grund === ''/.test(api),
    'die Art darf NICHT aus der (optionalen) Begruendung abgeleitet werden')
})

test('Hinweis: Reaktivieren stellt den Kontozustand von vorher wieder her', () => {
  // AUSTRITT-c (M1): der alte Text behauptete das GEGENTEIL („eine vorher
  // gesetzte Kontosperre muss danach neu gesetzt werden“). Gesperrt bleibt
  // gesperrt.
  assert.match(detail, /war das Konto vorher\s+gesperrt, bleibt es gesperrt/)
  assert.ok(!/Kontosperre muss danach neu/.test(detail))
})

test('lage(): die Art kommt vom Server, auch ohne Begruendung', () => {
  // AUSTRITT-d (NB3): Austritt ohne Begruendung ist ein Austritt — der Knopf
  // „Reaktivieren“ haengt daran, und Nicht-Admins lesen „Ausgetreten“.
  const fn = api.match(/export function lage\([\s\S]*?\n}/)[0].replace('export ', '')
  const lage = new Function(`${fn}; return lage`)()
  assert.equal(lage({ ausgetreten: true, art: 'austritt', grund: '' }).art, 'austritt')
  assert.equal(lage({ ausgetreten: true, art: 'austritt', seit: '2026-10-01' }).seit, '2026-10-01')
  assert.equal(lage({ ausgetreten: false, art: 'ausschluss', seit: '2026-09-01' }).art, 'ausschluss')
  assert.equal(lage({ ausgetreten: false, art: '' }).art, '')
  assert.equal(lage(null).art, '')
})

test('Datum wird deutsch angezeigt, ISO bleibt ISO', () => {
  const fn = api.match(/export function datumDeutsch[\s\S]*?\n}/)[0].replace('export ', '')
  const datumDeutsch = new Function(`${fn}; return datumDeutsch`)()
  assert.equal(datumDeutsch('2026-10-01'), '01.10.2026')
  assert.equal(datumDeutsch(''), '')
  assert.equal(datumDeutsch('unbekannt'), 'unbekannt')
})
