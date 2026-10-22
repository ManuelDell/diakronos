/**
 * P1-2 — Kalender: Datenverlust und Loeschen (Node `--test`).
 *
 * Quelltext-Waechter fuer die Befunde des Nachtberichts, deren Ursache im
 * Frontend liegt:
 *
 *   UXK-R3   „Gesamte Serie löschen" / „Alle nachfolgenden löschen" fragt mit
 *            der Folge in Zahlen nach; nach dem Löschen lädt der Kalender neu.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

const KALENDER = lies('pages/Kalender.vue')
const SERIES = lies('components/kronos/KronosSeriesDialog.vue')

// ── UXK-R3: Rueckfrage vor dem Serien-Loeschen nennt die Folge in Zahlen ───

test('UXK-R3: Serien-Dialog fragt vor dem Loeschen nach', () => {
  assert.match(SERIES, /confirmLoeschen/)
  assert.match(SERIES, /Das lässt sich nicht rückgängig machen/)
})

test('UXK-R3: Rueckfrage nennt die Anzahl der Termine', () => {
  // Die Warnung ist ein eigenes computed, das `series_count` aus dem Kalender
  // auswertet (Backend haengt die Seriengroesse an extendedProps).
  assert.match(SERIES, /const loeschWarnung = computed/)
  assert.match(SERIES, /eventData\.value\?\.series_count/)
  assert.match(SERIES, /Termine werden gelöscht/)
})

test('UXK-R3: Fall ohne bekannte Anzahl bleibt formulierungssicher', () => {
  assert.match(SERIES, /typeof n === 'number' && n > 0 \? n : null/)
})

// ── UXK-R3: Kalender laedt nach dem Loeschen neu ───────────────────────────

test('UXK-R3: Kalender holt nach dem Serien-Loeschen die Termine neu', () => {
  // Frueher behandelte onEventClick nur 'edit'; nach 'deleted' blieben die
  // geloeschten Termine bis zum Neuladen sichtbar.
  assert.match(
    KALENDER,
    /action === 'deleted'[\s\S]{0,400}refetchEvents\(\)/
  )
})
