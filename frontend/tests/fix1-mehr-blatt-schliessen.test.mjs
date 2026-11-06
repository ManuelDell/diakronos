/**
 * FIX-1 (überholt durch UX3e) — das „Mehr“-Blatt der Handy-Navigation gibt es
 * nicht mehr.
 *
 * Der Befund DMB-a2d846875201 („Einklappen nicht möglich“) betraf den Kopf des
 * „Mehr“-Blattes in `AppBottomNav.vue`. UX3e hat das Blatt ersatzlos entfernt
 * (Entscheidung Manuel 2026-11-03): Die untere Leiste zeigt fünf feste Ziele,
 * alles Weitere steht in der Menü-Schublade, die das Menü-Symbol oben links
 * öffnet (Entwurf A9).
 *
 * Diese Datei bleibt bestehen, damit der alte Befund nicht stillschweigend
 * wiederkehrt: Sie hält fest, dass es weder Blatt noch „Mehr“-Knopf gibt, und
 * dass die Schließwege der Schublade (Kopf, Esc, Zurück, Wischen, Überlappung)
 * vorhanden sind. Die vollständige Prüfung steht in
 * `ux3e-handy-navigation.test.mjs`.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const WURZEL = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, WURZEL), 'utf8')

const NAV = lies('components/AppBottomNav.vue')
const SCHUBLADE = lies('components/AppMenueSchublade.vue')
const ohneKommentare = (t) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/<!--[\s\S]*?-->/g, '')

test('FIX-1/UX3e · das „Mehr“-Blatt ist ersatzlos entfallen', () => {
  const nav = ohneKommentare(NAV)
  assert.ok(!/dk-bn-sheet/.test(nav), 'kein Blatt (dk-bn-sheet) mehr in der Leiste')
  assert.ok(!/showMore|toggleMore|closeMore/.test(nav), 'kein Blatt-Zustand mehr')
  assert.ok(!/>\s*Mehr\s*</.test(nav), 'kein „Mehr“-Knopf mehr')
})

test('FIX-1/UX3e · die Schublade ist überall schließbar (der alte Befund bleibt behoben)', () => {
  const s = ohneKommentare(SCHUBLADE)
  // (1) Kopf/Schließen-Knopf, (2) Überlappung, (3) Esc + Fokus, (4) Zurück, (5) Wischen.
  assert.match(s, /class="dk-schublade-schliessen"/, 'eigener Schließen-Knopf')
  assert.match(s, /@click\.self="\$emit\('schliessen'\)"/, 'Tippen daneben schließt')
  assert.match(s, /useDialogFokus\(/, 'Esc und Tab-Kreis')
  assert.match(s, /useZurueckSchliesst\(/, 'Zurück-Taste/-Geste')
  assert.match(s, /wischEnde/, 'Wischen nach links')
})
