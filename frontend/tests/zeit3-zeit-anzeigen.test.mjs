/**
 * ZEIT-3 — Serverzeitpunkte werden in der Zeitzone der Gemeinde angezeigt.
 *
 * Zwei Stellen gaben den rohen UTC-Wert aus (zwischen 0 und 2 Uhr Ortszeit
 * mit dem VORTAGSDATUM, sonst 1–2 Stunden daneben):
 *
 *   1. `components/widgets/OpenSignupsWidget.vue`  „Erstellt: {{item.creation}}“
 *   2. `pages/devmodus/Befunde.vue`                „Zeit … b.zeitpunkt“
 *
 * Beide laufen ueber `serverZeitText` aus `shared/zeit.mjs` (ZEIT-2).
 *
 * Abgrenzung (Review ZEIT-3): Die Datensicherung schreibt Name und
 * `begonnen_am` seit BACKUP-1 in ORTSZEIT (`sicherung/lauf.py`,
 * `jetzt_ortszeit`). `zeitpunktText` formatiert deshalb nur um und rechnet
 * NICHT — sonst stuende eine 03:00-Sicherung als „05:00 Uhr“ da.
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import { serverZeitText, GEMEINDE_ZONE } from '../src/shared/zeit.mjs'

const HIER = dirname(fileURLToPath(import.meta.url))
const lies = (rel) => readFileSync(join(HIER, '..', 'src', rel), 'utf8')

// ── 1. Die Rechnung ────────────────────────────────────────────────────────

test('ZEIT-3: 23:30 UTC ist in Berlin schon der naechste Tag (MEZ)', () => {
  assert.equal(GEMEINDE_ZONE, 'Europe/Berlin')
  assert.equal(serverZeitText('2026-11-09 23:30:00'), '10.11.2026, 00:30')
  assert.equal(serverZeitText('2026-11-09T23:30:00.123456'), '10.11.2026, 00:30')
  assert.equal(serverZeitText('2026-11-09T23:30:00Z'), '10.11.2026, 00:30')
})

test('ZEIT-3: Sommerzeit wird beachtet (MESZ = +2)', () => {
  assert.equal(serverZeitText('2026-07-01 22:30:00'), '02.07.2026, 00:30')
  assert.equal(serverZeitText('2026-07-01T12:00:00'), '01.07.2026, 14:00')
})

test('ZEIT-3: Befund-Zeitpunkt mit Sekunden', () => {
  assert.equal(serverZeitText('2026-11-09T23:30:45', { second: '2-digit' }),
    '10.11.2026, 00:30:45')
})

test('ZEIT-3: Leerwerte ergeben Leertext (Platzhalter setzt die Anzeige)', () => {
  assert.equal(serverZeitText(null), '')
  assert.equal(serverZeitText(''), '')
})

// ── 2. Die Anzeigen ────────────────────────────────────────────────────────

test('ZEIT-3: OpenSignupsWidget zeigt „Erstellt“ ueber serverZeitText', () => {
  const quelle = lies('diakonos/components/widgets/OpenSignupsWidget.vue')
  assert.match(quelle, /serverZeitText\(item\.creation\)/)
  assert.ok(!/Erstellt:\s*\{\{\s*item\.creation\s*\}\}/.test(quelle),
    '„Erstellt: {{ item.creation }}“ war der Befund — der rohe Wert ist zurueck')
  assert.match(quelle, /from '\.\.\/\.\.\/\.\.\/shared\/zeit\.mjs'/)
})

test('ZEIT-3: Befunde.vue zeigt den Befund-Zeitpunkt ueber serverZeitText', () => {
  const quelle = lies('diakonos/pages/devmodus/Befunde.vue')
  assert.match(quelle, /serverZeitText\(b\.zeitpunkt/)
  assert.ok(!/\{\{\s*b\.zeitpunkt\s*\|\|/.test(quelle),
    '„{{ b.zeitpunkt || … }}“ war der Befund — der rohe Wert ist zurueck')
  assert.match(quelle, /from '\.\.\/\.\.\/\.\.\/shared\/zeit\.mjs'/)
})

test('ZEIT-3: Datensicherung rechnet NICHT um (Zeitpunkte sind Ortszeit)', () => {
  const helfer = lies('diakonos/composables/useSicherung.js')
  assert.ok(!/serverZeit/.test(helfer),
    'Sicherungszeitpunkte sind Ortszeit (lauf.jetzt_ortszeit) — keine UTC-Umrechnung')
})
