/**
 * DEC-B5 — Ressourcen: eigene Anfragen freigeben (mit Recht) + Ansicht
 * „Eigene Anfragen“.
 *
 * Befund DMB-fd818e23a4b6 (Dev-Modus, 08.11.): Die Oberfläche zeigte an
 * eigenen Anfragen „Freigeben“/„Ablehnen“, der Server lehnte sie aber ab
 * („Eigene Anfragen können nicht selbst moderiert werden.“) — der Klick
 * endete in einem (doppelten) Fehler-Toast. Entscheidung Manuel 09.11.:
 * „Wenn man die Rechte hat, soll man es freigeben können.“
 *
 * Die Server-Seite sichern die pytest-Tests
 * `backend/tests/test_devb5_eigene_anfragen.py`.
 */
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import test from 'node:test'

import {
  anfrageSchluessel,
  anfragenAnderer,
  brauchtZuruecknehmen,
  darfSelbstFreigeben,
  zaehleOffene,
} from '../src/diakonos/composables/ressourcenEigeneAnfragen.mjs'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

const RESSOURCEN = lies('pages/Ressourcen.vue')

// ── Regel: Freigeben/Ablehnen nur MIT Recht und nur solange offen ──────────

test('DEC-B5: eigene offene Anfrage mit Freigaberecht bekommt Freigeben/Ablehnen', () => {
  assert.equal(darfSelbstFreigeben({ status: 'Angefragt', darf_entscheiden: true }), true)
})

test('DEC-B5: OHNE Freigaberecht keine Knöpfe (nicht erst ein Fehler beim Klick)', () => {
  assert.equal(darfSelbstFreigeben({ status: 'Angefragt', darf_entscheiden: false }), false)
  // Der Server liefert das Feld gar nicht (alte Antwort) -> fail closed.
  assert.equal(darfSelbstFreigeben({ status: 'Angefragt' }), false)
})

test('DEC-B5: eine entschiedene Anfrage lässt sich nicht erneut entscheiden', () => {
  assert.equal(darfSelbstFreigeben({ status: 'Bestätigt', darf_entscheiden: true }), false)
  assert.equal(darfSelbstFreigeben({ status: 'Abgelehnt', darf_entscheiden: true }), false)
})

// ── Regel: Zurücknehmen nur für eigene OFFENE Buchungen ────────────────────

test('DEC-B5: Zurücknehmen für eigene offene Buchung ohne Freigaberecht', () => {
  assert.equal(brauchtZuruecknehmen({ status: 'Angefragt', quelle: 'buchung' }), true)
})

test('DEC-B5: kein Zurücknehmen an entschiedenen Anfragen', () => {
  assert.equal(brauchtZuruecknehmen({ status: 'Bestätigt', quelle: 'buchung' }), false)
  assert.equal(brauchtZuruecknehmen({ status: 'Abgelehnt', quelle: 'buchung' }), false)
})

test('DEC-B5: mit Freigaberecht stehen Freigeben/Ablehnen statt Zurücknehmen', () => {
  const a = { status: 'Angefragt', quelle: 'buchung', darf_entscheiden: true }
  assert.equal(brauchtZuruecknehmen(a), false)
})

test('DEC-B5: Termin-Anfrage bietet kein Zurücknehmen (kein Endpunkt dafür)', () => {
  assert.equal(brauchtZuruecknehmen({ status: 'Angefragt', quelle: 'termin' }), false)
})

// ── Schluessel: Buchung und Termin-Zeile koennen gleich heissen ────────────

test('DEC-B5: der Schluessel unterscheidet Buchungen von Termin-Zeilen', () => {
  assert.equal(anfrageSchluessel({ id: 'X-1', quelle: 'buchung' }), 'buchung-X-1')
  assert.equal(anfrageSchluessel({ id: 'X-1', quelle: 'termin' }), 'termin-X-1')
  // Ohne Quelle gilt Buchung (Bestandsverhalten von get_meine_buchungen).
  assert.equal(anfrageSchluessel({ id: 'X-1' }), 'buchung-X-1')
  assert.notEqual(
    anfrageSchluessel({ id: 'X-1' }),
    anfrageSchluessel({ id: 'X-1', quelle: 'termin' }),
  )
})

// ── Moderatorenliste ohne eigene Anfragen ──────────────────────────────────

test('DEC-B5: eigene Anfragen stehen nicht doppelt in „Offene Anfragen“', () => {
  const liste = [
    { id: 'A', gebucht_von: 'mir' },
    { id: 'B', gebucht_von: 'andere' },
  ]
  assert.deepEqual(anfragenAnderer(liste, 'mir').map(a => a.id), ['B'])
})

test('DEC-B5: ohne eigenen Nutzer bleibt die Liste unveraendert', () => {
  const liste = [{ id: 'A', gebucht_von: 'mir' }]
  assert.deepEqual(anfragenAnderer(liste, ''), liste)
  assert.deepEqual(anfragenAnderer(null, 'mir'), [])
})

test('DEC-B5: Kopfzahl zaehlt nur offene Anfragen', () => {
  assert.equal(zaehleOffene([{ status: 'Angefragt' }, { status: 'Bestätigt' }]), 1)
  assert.equal(zaehleOffene([]), 0)
})

// ── Quelltextwachen der Seite ─────────────────────────────────────────────

test('DEC-B5: die Seite hat einen eigenen Bereich „Eigene Anfragen“', () => {
  assert.match(RESSOURCEN, />\s*Eigene Anfragen\s*</)
  assert.match(RESSOURCEN, /v-if="eigeneOffene\.length"/)
  assert.match(RESSOURCEN, /v-for="a in eigeneAnfragen"/)
})

test('DEC-B5: Freigeben/Ablehnen an eigenen Anfragen haengen an darfSelbstFreigeben', () => {
  assert.match(RESSOURCEN, /v-if="darfSelbstFreigeben\(a\)"/)
  assert.match(RESSOURCEN, /@click="approveEigene\(a\)"/)
  // Die frueheren, ungeprueften Knöpfe an eigenen Anfragen sind weg: der
  // Bereich „Offene Anfragen“ iteriert ueber die Liste ohne eigene Eintraege.
  assert.match(RESSOURCEN, /v-for="a in anfragenAndererListe"/)
})

test('DEC-B5: die eigene Freigabe laeuft ueber denselben Endpunkt wie fremde', () => {
  assert.match(RESSOURCEN, /async function approveEigene\(a\)/)
  assert.match(RESSOURCEN, /await entscheideAnfrage\(a, 'bestaetigen'\)/)
})

test('DEC-B5: entschiedene Anfragen tragen keine leere Aktionsleiste', () => {
  // Gefunden bei der Sichtprüfung: leere graue Balken an entschiedenen
  // Anfragen. Die Aktionszeile entsteht nur, wenn es Knöpfe gibt.
  assert.match(
    RESSOURCEN,
    /<div v-if="darfSelbstFreigeben\(a\) \|\| brauchtZuruecknehmen\(a\)" class="rs-anfrage-actions">/,
  )
})

test('DEC-B5: Zurücknehmen storniert nur die eigene Buchung', () => {
  assert.match(RESSOURCEN, /async function ruecknahme\(a\)/)
  assert.match(RESSOURCEN, /v-else-if="brauchtZuruecknehmen\(a\)"/)
  assert.match(RESSOURCEN, /apiCall\('diakronos\.diakonos\.api\.ressourcen\.delete_buchung', \{\s*\n\s*buchung_id: a\.id,/)
})

test('DEC-B5: alle geaenderten Dateien existieren', () => {
  for (const p of ['pages/Ressourcen.vue', 'composables/ressourcenEigeneAnfragen.mjs']) {
    assert.ok(existsSync(new URL(p, root)), p)
  }
})
