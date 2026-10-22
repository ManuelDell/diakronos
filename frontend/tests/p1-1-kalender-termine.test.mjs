/**
 * P1-1 — Kalender: Termine anlegen/bearbeiten zuverlaessig (Node `--test`).
 *
 * Quelltext-Waechter fuer die Befunde des Nachtberichts, deren Ursache im
 * Frontend liegt. Geprueft werden die Zusagen, die man sonst nur im Browser
 * sieht — jeweils hart am Quelltext:
 *
 *   UXK-R1   Datum kommt aus dem reinen Tag (`slice(0,10)`), keine zweite Uhrzeit
 *   UXK-R2   HTTP-Status entscheidet ueber Erfolg (nicht `data.message`)
 *   UXK-R5   Status wird beim Bearbeiten mitgesendet
 *   UXK-R6   „Als Konflikt markieren“ setzt status='Konflikt'
 *   UXK-002  Doppelklick-Schutz am Hintergrund
 *   UXK-009  maxlength=140 an beiden Titel-Feldern
 *   UXK-R10  Umschalter nur mit Schreibrecht + Hinweis statt falscher Meldung
 *   OP-ADMIN-1  Serienende-Feld existiert beim Oeffnen (v-show, watch-Bindung)
 *   OP-ADMIN-R2 Wiederholung bei „Serientermin“ ist Pflicht
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

const KALENDER = lies('pages/Kalender.vue')
const CREATE = lies('components/kronos/KronosEventCreate.vue')
const EDIT = lies('components/kronos/KronosEventEdit.vue')
const SERIES = lies('components/kronos/KronosSeriesDialog.vue')
const TOPBAR = lies('components/kronos/KronosTopbar.vue')
const MODERATION = lies('pages/Moderation.vue')
const AENDERUNGEN = lies('components/kronos/ModerationAenderungen.vue')

/** Quelltext ohne Kommentare — ein Waechter soll Code pruefen, nicht Prosa. */
const ohneKommentare = (q) => String(q)
  .replace(/<!--[\s\S]*?-->/g, '')
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/^\s*\/\/.*$/gm, '')

// ── UXK-R1: kein doppeltes T mehr ──────────────────────────────────────────

test('UXK-R1: onDateClick nimmt nur den Tag aus info.dateStr', () => {
  assert.match(KALENDER, /String\(info\.dateStr \|\| ''\)\.slice\(0, 10\)/)
  // Der alte Fehler war `${info.dateStr}T${h}:${m}`.
  assert.ok(
    !/\$\{info\.dateStr\}T\$\{h\}/.test(KALENDER),
    'info.dateStr wird wieder direkt mit einer Uhrzeit verkettet'
  )
})

test('UXK-R1: Standardzeit aus dem Baustein (S8: 19:00) und +1 h', () => {
  // OP-UI-20: Der Vorschlag kommt jetzt aus `vorschlagBeginn()` (S8: 19:00,
  // angeklickte Stunde schlaegt ihn). Die Zusage bleibt dieselbe: Ein Klick
  // ohne Uhrzeit erzeugt einen vollstaendigen, plausiblen Zeitraum.
  assert.match(KALENDER, /return vorschlagBeginn\(\)/)
  assert.match(KALENDER, /import \{ vorschlagBeginn \} from '\.\.\/composables\/datumZeit\.mjs'/)
  assert.match(KALENDER, /function defaultEndZeit/)
})

// ── UXK-R2: Fehler werden nicht mehr als Erfolg gewertet ───────────────────

test('UXK-R2: Bearbeiten/Löschen pruefen res.ok und success', () => {
  assert.match(EDIT, /if \(!res\.ok \|\| !data \|\| data\.exc \|\| data\.message\?\.success !== true\)/)
  assert.ok(!/if \(data\.message\) \{/.test(EDIT), 'alter Erfolgstest if (data.message) noch da')
  assert.ok(!/alert\(/.test(EDIT), 'alert() im Edit-Dialog noch vorhanden')
})

test('UXK-R2: Serien-Dialog wertet die Antwort aus (Loeschen meldet Fehler)', () => {
  assert.match(SERIES, /if \(!res\.ok \|\| !data \|\| data\.exc \|\| data\.message\?\.success !== true\)/)
  assert.match(SERIES, /showToast\(/)
})

// ── UXK-R5: Status wird mitgesendet ────────────────────────────────────────

test('UXK-R5: Edit-Dialog sendet status im Payload', () => {
  assert.match(EDIT, /status: form\.status \|\| null/)
})

// ── UXK-R6: „Als Konflikt markieren“ ───────────────────────────────────────

test("UXK-R6: result === 'conflict' setzt status='Konflikt'", () => {
  assert.match(CREATE, /if \(result === 'conflict'\) form\.status = 'Konflikt'/)
  assert.match(EDIT, /if \(result === 'conflict'\) form\.status = 'Konflikt'/)
})

// ── UXK-002: Doppelklick-Schutz ────────────────────────────────────────────

test('UXK-002: Hintergrund ignoriert Klicks direkt nach dem Oeffnen', () => {
  assert.match(CREATE, /function onBackdropClick/)
  assert.match(CREATE, /if \(Date\.now\(\) - geoeffnet_am < 400\) return/)
  assert.match(EDIT, /function onBackdropClick/)
})

// ── UXK-009: maxlength 140 ─────────────────────────────────────────────────

test('UXK-009: beide Titel-Felder begrenzen auf 140 Zeichen', () => {
  const createTitel = /maxlength="140"[^>]*placeholder="Termintitel"/
  const editTitel = /maxlength="140"[^>]*placeholder="Termintitel"/
  assert.match(CREATE, createTitel)
  assert.match(EDIT, editTitel)
})

// ── UXK-R10: Schreibrecht ──────────────────────────────────────────────────

test('UXK-R10: Kalender-Seite kennt hasWriteRight und gibt es an die Topbar', () => {
  assert.match(KALENDER, /const hasWriteRight = computed/)
  assert.match(KALENDER, /:canWrite="hasWriteRight"/)
  assert.match(KALENDER, /if \(mode === 'edit' && !hasWriteRight\.value\) return/)
})

test('UXK-R10: Topbar blendet den Umschalter ohne Schreibrecht aus', () => {
  assert.match(TOPBAR, /v-if="canWrite" class="toggle-container"/)
  assert.match(TOPBAR, /Nur lesen/)
  assert.match(TOPBAR, /canWrite: \{ type: Boolean/)
})

test('UXK-R10: Create-Dialog nennt den Grund statt falscher Pflichtfeldmeldung', () => {
  assert.match(CREATE, /DkHint v-if="!calendars\.length"/)
  assert.match(CREATE, /kein\s+Kalender mit Schreibrecht/)
})

// ── OP-ADMIN-1: Serienende wird gebunden ───────────────────────────────────

test('OP-ADMIN-1: Serien-Felder existieren beim Oeffnen (v-show statt v-if)', () => {
  // Beide Felder stehen unter `v-show`, damit sie beim Oeffnen des Dialogs
  // schon existieren (mit `v-if` blieb das Serienende frueher wirkungslos).
  assert.match(CREATE, /v-show="form\.is_series"[\s\S]{0,200}?label-datum="Serienende"/)
  assert.match(CREATE, /v-show="form\.is_series" label="Wiederholung" required/)
  assert.ok(
    !/v-if="form\.is_series"/.test(CREATE),
    'Serien-Feld wieder unter v-if — es existiert beim Oeffnen dann nicht'
  )
})

test('OP-ADMIN-1: das Serienende ist ein eigenes Datumsfeld und bleibt bedienbar', () => {
  // War der Fehler: ein Textfeld, das der Kalender beim Einblenden nicht band —
  // das Serienende wurde still verworfen. Seit OP-UI-20 ist es DkDatumZeit
  // (echtes Datumsfeld, eigener Zustand) und haengt nicht mehr an einer
  // Bindungs-Reihenfolge. Der Waechter prueft jetzt genau das.
  const block = CREATE.match(/<DkDatumZeit[\s\S]*?\/>/g) || []
  const serienende = block.find(b => /form\.series_end/.test(b))
  assert.ok(serienende, 'Serienende wird ueber DkDatumZeit gebunden')
  assert.match(serienende, /:mit-zeit="false"/)
  assert.match(serienende, /v-show="form\.is_series"/)
  assert.ok(!/flatpickr/.test(ohneKommentare(CREATE)), 'flatpickr ist in diesem Dialog nicht mehr noetig')
})

test('OP-ADMIN-1: Serienende wird im Payload mitgeschickt', () => {
  assert.match(CREATE, /payload\.series_end = form\.series_end \|\| null/)
})

// ── OP-ADMIN-R2: Wiederholung ist Pflicht ──────────────────────────────────

test('OP-ADMIN-R2: Serientermin ohne Wiederholung wird abgelehnt', () => {
  assert.match(CREATE, /if \(form\.is_series && !form\.repeat_type\)/)
  assert.match(CREATE, /Bitte eine Wiederholung wählen/)
})

// ── Dev-Befund 16.10.: deutsches Datumsformat im Dialog ────────────────────

test('Deutsches Format: Datum/Uhrzeit ueber DkDatumZeit, Modell bleibt Serverformat', () => {
  // Vorher hing die deutsche Anzeige an flatpickr (`altInput`/`altFormat`).
  // Jetzt macht das der Baustein — deutsch angezeigt, ISO im Modell, am Handy
  // die native Auswahl. Beide Dialoge nutzen ihn.
  for (const [name, quelle] of [['Create', CREATE], ['Edit', EDIT]]) {
    assert.match(quelle, /<DkDatumZeit/, `${name}: DkDatumZeit fehlt`)
    assert.match(quelle, /v-model="form\.element_start"/, `${name}: Beginn nicht gebunden`)
    assert.match(quelle, /v-model:ende-model-value="form\.element_end"/, `${name}: Ende nicht gebunden`)
    assert.ok(!/flatpickr/.test(ohneKommentare(quelle)), `${name}: flatpickr liefert wieder ISO-Werte im Feld`)
    assert.ok(!/type="datetime-local"/.test(quelle), `${name}: eigene Datumseingabe statt Baustein`)
  }
  const baustein = lies('components/ui/DkDatumZeit.vue')
  assert.match(baustein, /type="date"/)
  assert.match(baustein, /type="time"/)
  assert.match(baustein, /vorschauText/, 'deutsche Rueckmeldung fehlt')
})

test('Deutsches Format: Serienende zeigt ein deutsches Datum', () => {
  // Die Anzeige kommt aus DkDatumZeit (`vorschau`: „Mi., 30.12.2026“), nicht
  // mehr aus zwei getrennten flatpickr-Bindungen.
  const baustein = lies('components/ui/DkDatumZeit.vue')
  assert.match(baustein, /vorschau\(/)
  assert.match(CREATE, /label-datum="Serienende"/)
})

// ── Operator-Regel 16.10.: Moderation der Terminaenderung ──────────────────

test('Operator-Regel: Moderation zeigt offene Änderungen (alt/neu)', () => {
  assert.match(MODERATION, /ModerationAenderungen/)
  assert.match(AENDERUNGEN, /get_offene_aenderungen/)
  assert.match(AENDERUNGEN, /aenderung_freigeben/)
  assert.match(AENDERUNGEN, /aenderung_ablehnen/)
  assert.match(AENDERUNGEN, /Bisher/)
  assert.match(AENDERUNGEN, /Neu/)
})

test('Operator-Regel: Bearbeiten meldet „wartet auf Freigabe“', () => {
  assert.match(EDIT, /aenderung_wartet/)
  assert.match(EDIT, /wartet auf Freigabe/)
})
