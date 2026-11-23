/**
 * LEISTE-2 — Kalender ohne App-Kopfzeile (Manuel 23.11., Befund DMB-f503,
 * Entwurf „05/06 Kalender A“): „Die Leiste ist beim Kalender unnötig. Hier
 * kann Monat, Woche und Co. Auswahl sein. Gib dem Kalender mehr Platz.“
 *
 *   K1  Derselbe Mechanismus wie LEISTE-1 (router.js), kein zweiter Weg:
 *       #/kalender läuft Vollbild MIT Seitenleiste, seine Unterseiten nicht.
 *   K2  Am Handy ist die Seitenleiste trotzdem erreichbar: ☰ vorn im
 *       Kalender-Kopf, ausgelöst über dasselbe Ereignis wie bei Nachrichten.
 *
 * Lauf: node --test tests/leiste2-*.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

function vollbildLogik() {
  const quelle = lies('router.js')
  const a = quelle.indexOf('const VOLLBILD_MUSTER')
  const b = quelle.indexOf('export function darfSeitenleiste')
  const ende = quelle.indexOf('\n}\n', b) + 3
  const ctx = {}
  vm.createContext(ctx)
  vm.runInContext(`${quelle.slice(a, ende).replace(/^export /gm, '')}
this.vollbildRoute = vollbildRoute; this.darfSeitenleiste = darfSeitenleiste`, ctx)
  return ctx
}

test('LEISTE-2 · K1: #/kalender läuft Vollbild mit Seitenleiste, Unterseiten nicht', () => {
  const { vollbildRoute, darfSeitenleiste } = vollbildLogik()
  assert.equal(vollbildRoute('#/kalender'), true, 'der Kalender trägt weiter die App-Kopfzeile')
  assert.equal(vollbildRoute('#/kalender?ansicht=woche'), true)
  assert.equal(darfSeitenleiste('#/kalender'), true, 'der Kalender verliert die Seitenleiste')
  for (const h of ['#/kalender/import', '#/kalender/verwalten', '#/kalender/pruefen']) {
    assert.equal(vollbildRoute(h), false, `${h} verliert die App-Kopfzeile`)
  }
})

test('LEISTE-2 · K2: ☰ im Handy-Kopf des Kalenders öffnet die Schublade der App', () => {
  const seite = lies('pages/Kalender.vue')
  const tpl = seite.slice(0, seite.indexOf('<script'))
  const schmal = tpl.slice(tpl.indexOf('<template v-if="istSchmal">'), tpl.indexOf('<KalenderPruefZeile'))
  assert.match(schmal, /<MenueKnopf @oeffnen="\$emit\('open-menu'\)" \/>/,
    'kein Menü-Knopf im Handy-Kopf des Kalenders (der eine Baustein MenueKnopf.vue)')
  assert.ok(schmal.indexOf('<MenueKnopf') < schmal.indexOf('<KalenderKopfMobil'),
    'der Menü-Knopf steht nicht VOR dem Kalender-Kopf')
  assert.match(seite, /defineEmits\(\['open-menu'\]\)/, 'Kalender meldet `open-menu` nicht an')
})
