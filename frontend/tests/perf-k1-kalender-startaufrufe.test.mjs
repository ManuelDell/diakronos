/**
 * PERF-K1 — Ein Abgleich der Kalender-Startaufrufe (Prüfung am Quelltext).
 *
 * BEFUND (Manuel, 17.11.): „Kalenderdaten brauchen sehr lange zum Laden“.
 * Im Vorbau-Image gemessen (10 Kalender / 50 Nutzer / 312 Termine):
 * `get_calendar_events` = 110 803 SQL-Abfragen für EINE Monatsansicht, weil der
 * Rechte-Kern JE TERMIN neu gefragt wurde. Die Server-Seite prüft das
 * Abfrage-Limit in `backend/tests/test_perf_k1_kalender_abfragen.py`.
 *
 * Diese Datei hält die FRONTEND-Seite desselben Befunds fest — sie ist ein
 * Quelltext-Wächter (kein Mount): beim Aufbau der Kalender-Seite ging eine
 * Reihe von Endpunkten mehrfach bzw. unnötig seriell heraus.
 *
 *  1. `get_current_user_context` — die Seite ist der EINE Besitzer; die Leiste
 *     fragt nicht mehr selbst, sie liest den Stand der Seite
 *     (`:benutzer-kontext`).
 *  2. `get_kanban_board_data` — die Seite holt EINE Antwort für goldene Punkte
 *     UND die Spalte „Zu prüfen“; das Panel fragt beim Aufbau nicht mehr.
 *  3. `get_kalender_verwaltung` bleibt bei EINEM Besitzer (UI-R3e, unverändert).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const hier = dirname(fileURLToPath(import.meta.url))
const SRC = resolve(hier, '..', 'src', 'diakonos')
const lies = (rel) => fs.readFileSync(join(SRC, rel), 'utf8')

const seite = lies('pages/Kalender.vue')
const leiste = lies('components/kronos/KronosSidebar.vue')
const panel = lies('components/kronos/KalenderPruefPanel.vue')

/** Zählt Aufrufe einer Methode in einer Quelldatei (ohne Kommentarzeilen). */
function aufrufe(quelle, methode) {
  return quelle.split('\n')
    .filter((z) => !/^\s*(\/\/|\*|\/\*)/.test(z))
    .filter((z) => z.includes(methode)).length
}

test('Leiste fragt get_current_user_context NICHT mehr selbst', () => {
  assert.equal(aufrufe(leiste, 'get_current_user_context'), 0,
    'die Leiste holt den Benutzer-Kontext wieder selbst (Seite ist der Besitzer, PERF-K1)')
  assert.match(leiste, /benutzerKontext: \{ type: Object/,
    'die Leiste nimmt den Kontext der Seite nicht als Prop an')
})

test('Kalender-Seite reicht ihren Benutzer-Kontext an die Leiste', () => {
  assert.match(seite, /:benutzer-kontext="benutzerKontext"/,
    'die Seite gibt ihren Kontext nicht an die Leiste (dann fragt die Leiste wieder selbst)')
})

test('Prüf-Spalte fragt get_kanban_board_data beim Aufbau NICHT selbst', () => {
  const ohneKommentar = panel.split('\n')
    .filter((z) => !/^\s*(\/\/|\*|\/\*)/.test(z)).join('\n')
  // `laden()` bleibt als Nachladeweg NACH einer Änderung — beim Aufbau läuft
  // es nicht mehr (kein `onMounted(... laden())`).
  assert.doesNotMatch(ohneKommentar, /onMounted\([\s\S]*?\bladen\(\)/,
    'das Panel lädt beim Aufbau wieder selbst (die Seite ist der Besitzer, PERF-K1)')
  assert.match(panel, /zeilen: \{ type: Array/, 'das Panel nimmt die Zeilen der Seite nicht an')
  assert.match(seite, /:zeilen="pruefZeilen"/,
    'die Seite reicht ihre Prüf-Zeilen nicht an die Spalte')
})

test('Die Seite holt die Prüf-Zeilen EINMAL (goldene Punkte und Spalte)', () => {
  const zahl = aufrufe(seite, 'getBoardData(')
  assert.equal(zahl, 1,
    `getBoardData() steht ${zahl}x in der Seite — eine Antwort, zwei Leser (PERF-K1)`)
})

test('get_kalender_verwaltung bleibt bei EINEM Besitzer (UI-R3e)', () => {
  assert.equal(aufrufe(leiste, 'ladenKalenderVerwaltung'), 0,
    'die Leiste lädt die Verwaltung wieder selbst')
})
