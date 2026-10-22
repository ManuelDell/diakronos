/**
 * P1-1b — Nacharbeit Kalender (Node `--test`).
 *
 * Quelltext-Waechter fuer die Frontend-Seite der Review-Befunde
 * (Befund):
 *
 *   B2/W2  Drag&Drop meldet, wenn die Aenderung als offener Vorschlag wartet
 *          (`aenderung_wartet` in der Serverantwort darf nicht verschwiegen
 *          werden — sonst sieht der Termin wie "zurueckgesprungen" aus).
 *   W2     Die Moderationsliste nutzt `geaenderte_felder` und zeigt den
 *          Zusatzfall "nur weitere Ressourcen geaendert" an.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

const EVENTS_API = lies('composables/useEventsApi.js')
const KALENDER = lies('components/kronos/KronosCalendar.vue')
const AENDERUNGEN = lies('components/kronos/ModerationAenderungen.vue')

// ── B2: Drag&Drop kennt das Vorschlags-Ergebnis ────────────────────────────

test('P1-1b: updateEvent liefert wartet/ok zurueck (kein reines true)', () => {
  assert.match(EVENTS_API, /return \{ ok: true, wartet: Boolean\(nachricht\.aenderung_wartet\)/)
  assert.match(EVENTS_API, /aenderung_wartet/)
})

test('P1-1b: Kalender meldet das wartende Ergebnis nach Drop/Resize', () => {
  assert.match(KALENDER, /function meldeWartendeAenderung/)
  assert.match(KALENDER, /ergebnis = await eventsApi\.updateEvent/)
  // Beide Wege (Drop und Resize) melden.
  const aufrufe = KALENDER.match(/meldeWartendeAenderung\(ergebnis\)/g) || []
  assert.ok(aufrufe.length >= 2, `nur ${aufrufe.length} Meldung(en) verdrahtet`)
  assert.match(KALENDER, /import \{ showToast \}/)
})

// ── W2: Moderationsliste zeigt die geaenderten Felder ─────────────────────

test('P1-1b: Moderationsliste kennt geaenderte_felder', () => {
  assert.match(AENDERUNGEN, /geaenderte_felder/)
  assert.match(AENDERUNGEN, /nur weitere Ressourcen/)
})
