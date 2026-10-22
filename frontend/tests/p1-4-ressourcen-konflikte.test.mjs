/**
 * P1-4 — Ressourcen: Bestaetigen/Ablehnen und Konflikte (Node `--test`).
 *
 * Quelltext-Waechter fuer die Befunde des Nachtberichts, deren Ursache im
 * Frontend liegt:
 *
 *   OP-HANDY-4  „Bestätigen“/„Ablehnen“ rief `decide_buchung` unter dem
 *               Tippfehler-Pfad `diakronos.diakronos.api...` auf (HTTP 404).
 *               Jede Raumanfrage blieb unbeantwortbar.
 *   UXK-R8      Konflikthinweis war unlesbar: `v-if="a.konflikt_hinweis"`
 *               ist bei `[]` wahr („[]“ auf jeder Anfrage), der Toast zeigte
 *               „[object Object]“.
 *   OP-HANDY-12 Die Verfuegbarkeitsleiste las `_datum_von`/`_datum_bis`, die
 *               der Endpunkt nie liefert -> immer „alles frei“. Sie laedt nun
 *               Buchungen UND Kalendertermine.
 *   OP-EVENT-14 Die Buchung kannte nur EIN Datum; „Verschieben“ rief
 *               `editBooking` nie auf.
 *   OP-HANDY-20 „Meine Buchungen“/Details erschienen ohne Sprung 1.500 px
 *               tiefer.
 *   OP-UI-21    Das Datum kam aus `toISOString()` (UTC) -> nachts gestern.
 *   DES-R14     Feld „bis“ ragte aus dem Dialog (Zeile ohne minmax(0,1fr)).
 *   OP-EVENT-10 Der Status-Chip der Termin-Ressourcen war frei klickbar.
 *   OP-EVENT-11 Der Konfliktdialog nannte Ressourcenbuchungen nicht mit
 *               wer/wann/wofür.
 *
 * Die Serverseite sichern die pytest-Tests
 * `backend/tests/test_p1_4_ressourcen_konflikte.py`.
 */
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import test from 'node:test'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

const RESSOURCEN = lies('pages/Ressourcen.vue')
const ENTSCHEIDUNG = lies('composables/ressourcenEntscheidung.js')
const CREATE = lies('components/kronos/KronosEventCreate.vue')
const EDIT = lies('components/kronos/KronosEventEdit.vue')
const DIALOG = lies('components/kronos/KronosConflictDialog.vue')

// ── OP-HANDY-4: richtiger Endpunkt-Pfad ─────────────────────────────────────
//
// P1-4b/B1: Die Zuordnung Anfrage -> Endpunkt liegt in
// `composables/ressourcenEntscheidung.js` (verhaltensgetestet, s.
// `ressourcenEntscheidung.test.mjs`). Hier bleibt die Wache erhalten, dass der
// Tippfehler-Pfad nirgends vorkommt.

test('P1-4b: der Buchungs-Endpunkt wird unter diakronos.diakonos.api... gebildet', () => {
  assert.match(ENTSCHEIDUNG, /diakronos\.diakonos\.api\.ressourcen/)
  assert.match(ENTSCHEIDUNG, /decide_buchung/)
})

test('P1-4b: der Tippfehler-Pfad kommt in keiner der Quellen vor', () => {
  // Gemeint ist die Nachtbefund-Variante mit DOPPELTEM „diakronos“
  // (`diakronos.diakronos.api...`, OP-HANDY-4). Der korrekte Modulpfad ist
  // `diakronos.diakonos.api...` — der darf selbstverstaendlich vorkommen.
  assert.doesNotMatch(RESSOURCEN, /diakronos\.diakronos\.api/)
  assert.doesNotMatch(ENTSCHEIDUNG, /diakronos\.diakronos\.api/)
})

// ── Uebersicht: ALLE apiCall-Namen der Seite nutzen einen bekannten Modulpfad ─
//
// Die Nachtpruefung verlangte einen Smoke-Test, der alle apiCall-Namen gegen
// die Registry prueft. Die Python-Registry ist im Frontend-Bauschritt nicht
// ladbar — der Test prueft deshalb jeden Aufruf gegen die Liste der
// Backend-Module, die laut `FRAPPE_MODULE` als SPA-Endpunkt registriert sind.
// Genau dieser Abgleich haette OP-HANDY-4 (doppeltes „diakronos“) gefunden.
const BEKANNTE_MODULE = [
  'diakronos.diakonos.api.ressourcen',
  'diakronos.kronos.api.permissions',
  'diakronos.kronos.api.ressource_api',
  'diakronos.kronos.api.event_crud',
]

test('P1-4: jeder apiCall-Pfad der Seite nutzt ein bekanntes Backend-Modul', () => {
  const pfade = [...RESSOURCEN.matchAll(/apiCall\(\s*'([^']+)'/g)].map(m => m[1])
  assert.ok(pfade.length > 0, 'Die Seite ruft mindestens einen Endpunkt auf')
  for (const pfad of pfade) {
    const modul = pfad.split('.').slice(0, -1).join('.')
    assert.ok(
      BEKANNTE_MODULE.includes(modul),
      `apiCall-Pfad ohne bekanntes Backend-Modul: ${pfad}`,
    )
  }
})

// ── UXK-R8: Konflikthinweis lesbar ─────────────────────────────────────────

test('P1-4: Konfliktbanner prueft die Laenge statt nur Wahrheit', () => {
  assert.match(RESSOURCEN, /v-if="konfliktHinweise\(a\)\.length"/)
  assert.match(RESSOURCEN, /function konfliktHinweise\(a\) \{/)
})

test('P1-4: Konflikteintraege werden als Text zusammengesetzt, nicht roh', () => {
  assert.match(RESSOURCEN, /function konfliktText\(k\) \{/)
  assert.match(RESSOURCEN, /typeof k === 'string'/)
  assert.match(RESSOURCEN, /Überschneidung mit/)
})

test('P1-4: der Toast nutzt konfliktSatz statt der Rohliste', () => {
  assert.match(RESSOURCEN, /if \(res\?\.konflikt_hinweis\?\.length\) \{\s*\n\s*showToast\(konfliktSatz\(res\.konflikt_hinweis\), 'warning'\)/)
})

// ── OP-HANDY-12: Verfuegbarkeitsleiste laedt echte Belegung ────────────────

test('P1-4: Verfuegbarkeit liest die gelieferten ISO-Zeitstempel', () => {
  assert.match(RESSOURCEN, /function ueberlappt\(eintrag, von, bis\)/)
  assert.match(RESSOURCEN, /eintrag\?\.datum_von \?\? eintrag\?\.von/)
})

test('P1-4: die Belegung laedt auch Kalendertermine (check_verfuegbarkeit)', () => {
  assert.match(RESSOURCEN, /apiCall\('diakronos\.diakonos\.api\.ressourcen\.check_verfuegbarkeit'/)
  assert.match(RESSOURCEN, /terminBelegung\.value = \(res\?\.kalender_konflikte \|\| \[\]\)/)
})

test('P1-4: kein Zugriff mehr auf die nie gelieferten _datum_von/_datum_bis', () => {
  assert.doesNotMatch(RESSOURCEN, /b\._datum_von/)
  assert.doesNotMatch(RESSOURCEN, /b\._datum_bis/)
})

// ── OP-EVENT-14: Von/Bis mit Datum + Verschieben ───────────────────────────

test('P1-4: das Buchungsformular hat Von und Bis getrennt (Datum + Zeit)', () => {
  assert.match(RESSOURCEN, /v-model="bookingForm\.endDate"/)
  assert.match(RESSOURCEN, /v-model="bookingForm\.startTime"/)
  assert.match(RESSOURCEN, /v-model="bookingForm\.endTime"/)
})

test('P1-4: „Verschieben“ ruft editBooking auf', () => {
  assert.match(RESSOURCEN, /title="Verschieben" @click="editBooking\(b\)"/)
})

test('P1-4: das Verschieben schickt den neuen Zeitraum mit', () => {
  // datum_bis kommt jetzt aus endDate, nicht mehr aus dem Startdatum.
  assert.match(RESSOURCEN, /const datum_bis = `\$\{f\.endDate\} \$\{f\.endTime\}:00`/)
})

// ── OP-HANDY-20: Sprung zum Panel ──────────────────────────────────────────

test('P1-4: „Meine Buchungen“ und Details springen zum Panel', () => {
  assert.match(RESSOURCEN, /function scrollZuPanel\(\)/)
  assert.match(RESSOURCEN, /scrollIntoView\?\.\(\{ behavior: 'smooth', block: 'start' \}\)/)
  assert.match(RESSOURCEN, /@click="toggleMyBookings"/)
})

// ── OP-UI-21: lokales Datum ────────────────────────────────────────────────

test('P1-4: das Vorschlagsdatum ist lokal, nicht UTC', () => {
  assert.match(RESSOURCEN, /function heuteLokal\(\)/)
  assert.match(RESSOURCEN, /toLocaleDateString\('sv-SE'\)/)
  assert.doesNotMatch(RESSOURCEN, /new Date\(\)\.toISOString\(\)\.split\('T'\)\[0\]/)
})

// ── DES-R14: Formular-Zeile laeuft nicht mehr aus dem Dialog ───────────────

test('P1-4: die Formularzeile nutzt minmax(0,1fr)', () => {
  assert.match(RESSOURCEN, /grid-template-columns: minmax\(0, 1fr\) minmax\(0, 1fr\)/)
})

// ── OP-EVENT-10: Status-Chip nur fuer Ressourcenmoderatoren ────────────────

for (const [name, quelle] of [['Erstellen', CREATE], ['Bearbeiten', EDIT]]) {
  test(`P1-4: Status-Chip (${name}) ist an istRessourcenmoderator gebunden`, () => {
    assert.match(quelle, /v-if="istRessourcenmoderator"[\s\S]*?status-chip-btn/)
    assert.match(quelle, /const istRessourcenmoderator = ref\(false\)/)
    assert.match(quelle, /get_session_info/)
  })
}

// ── OP-EVENT-11: Konfliktdialog nennt Buchungen ────────────────────────────

test('P1-4: der Konfliktdialog zeigt Zweck, Zeitraum und Bucher der Buchung', () => {
  assert.match(DIALOG, /v-for="b in \(c\.buchungen \|\| \[\]\)"/)
  assert.match(DIALOG, /b\.zeitraum/)
  assert.match(DIALOG, /b\.nutzer/)
})

test('P1-4: der doppelte :key="c.ressource" ist behoben', () => {
  assert.doesNotMatch(DIALOG, /:key="c\.ressource"/)
  assert.match(DIALOG, /:key="`\$\{c\?\.ressource \|\| 'r'\}-\$\{i\}`"/)
})

// ── Waechter: die neuen Seiten/Komponenten kompilieren ─────────────────────
//
// (Der eigentliche SFC-Compile laeuft in planrahmen-vue-compile.test.mjs fuer
//  den Planrahmen; Ressourcen.vue liegt ausserhalb. Hier genuegt die
//  Existenzpruefung der geaenderten Dateien.)
test('P1-4: alle geaenderten Dateien existieren', () => {
  for (const p of [
    'pages/Ressourcen.vue',
    'components/kronos/KronosEventCreate.vue',
    'components/kronos/KronosEventEdit.vue',
    'components/kronos/KronosConflictDialog.vue',
  ]) {
    assert.ok(existsSync(new URL(p, root)), p)
  }
})
