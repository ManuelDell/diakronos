/**
 * P1-5c — Kalender/CalDAV-Restpunkte (Node `--test`).
 *
 * Frontend-Anteil der Restbefunde aus drei Reviews:
 *
 *   (4) Nur 00:00–00:00 (bzw. `all_day`) ist „Ganztägig“; 14:00–14:00 zeigt
 *       die Uhrzeit. Ausfuehrbar getestet in
 *       `frontend/tests/p1-3-kalender-fenster.test.mjs` (über die geteilte
 *       Funktion `dayEventLabel.mjs`).
 *   (9) Die Antwort des Serien-Updates (`verworfen`/`meldung`) erreicht die
 *       Oberflaeche — hier als Verhaltenstest der reinen Entscheidungsfunktion
 *       `serienMeldung()`; die Verdrahtung selbst wird per Quelltext geprueft.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { serienMeldung } from '../src/diakonos/composables/serienMeldung.mjs'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

const MODALS = lies('components/kronos/ModerationModals.vue')

// ── (9) Meldung ueber verworfenen Serien-Status erreicht die Oberflaeche ────

test('P1-5c (9): ein verworfener Status erzeugt einen Warnhinweis', () => {
  // ROT vorher: `saveSeries` verwarf die Serverantwort — der Nutzer glaubte an
  // eine wirksame Statusaenderung.
  const m = serienMeldung({
    success: true,
    verworfen: ['status'],
    meldung: 'Der Serien-Status wurde nicht geaendert: die Freigabe ist eine '
      + 'Moderationshandlung (Terminmoderation).',
  })
  assert.ok(m, 'keine Meldung erzeugt')
  assert.equal(m.type, 'warning')
  assert.match(m.text, /Der Serien-Status wurde nicht geaendert/)
  assert.match(m.text, /Freigabe \(Status\)/)
})

test('P1-5c (9): ein reiner Hinweis bleibt ein Hinweis (kein Fehler)', () => {
  const m = serienMeldung({
    success: true,
    aenderung_wartet: true,
    wartende_termine: 3,
    meldung: '3 Termin(e) der Serie warten auf Freigabe (Terminmoderation).',
  })
  assert.ok(m)
  assert.equal(m.type, 'info')
  assert.match(m.text, /warten auf Freigabe/)
})

test('P1-5c (9): ohne Meldung wird nichts gezeigt', () => {
  assert.equal(serienMeldung({ success: true, updated_count: 4 }), null)
  assert.equal(serienMeldung(null), null)
  assert.equal(serienMeldung({ meldung: '' }), null)
})

test('P1-5c (9): `saveSeries` wertet die Serverantwort aus', () => {
  assert.match(MODALS, /import \{ serienMeldung \} from '\.\.\/\.\.\/composables\/serienMeldung\.mjs'/)
  assert.match(MODALS, /const antwort = await updateSeriesBatchFast\(/)
  assert.match(MODALS, /showSeriesMeldung\(antwort\)/)
})
