/**
 * ON-E2E — Symbolgrößen des Einrichtungs-Assistenten kommen aus tokens.css.
 *
 * BEFUND (Wegwerf-Stack mit leerer Datenbank, Playwright):
 * `AssistentSchritte.vue` gab dem Haken `:size="'var(--assistent-schritt-
 * haken)'"`. `width`/`height` sind SVG-**Attribute** und nehmen nur echte
 * Längen — der Browser meldete das JE SYMBOL in der Konsole:
 *
 *   Error: <svg> attribute width: Expected length, "var(--assistent-…".
 *
 * Zusätzlich standen die übrigen Größen als ZAHLEN im Markup (`29.12`,
 * `13.52`, `17`, `18`, `14`) — gegen die Regel „keine Größen-Zahlen in
 * Komponenten" und für den bisherigen Wächter (`waechter-tokens.test.mjs`)
 * unsichtbar, weil der nur FARBEN prüft.
 *
 * Dieser Test hält beides fest:
 *   1. Kein Zahlen-Wert als `:size` — jede Größe ist ein Token aus tokens.css.
 *   2. Das Token kommt als CSS (style) an und NICHT als Attribut-Länge:
 *      `width`/`height` tragen den Platzhalter `1` (Browsermeldung entfällt).
 *   3. Die verwendeten Tokens stehen wirklich in tokens.css.
 *
 * Läuft wie die übrigen Frontend-Tests im Docker-Build (node --test).
 */
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { test } from 'node:test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HIER = path.dirname(fileURLToPath(import.meta.url))
// Wurzel finden (wie tools/css-ssot-bestand.mjs): der Ordner mit src/ und tests/.
function findeWurzel(start) {
  let dir = start
  for (let i = 0; i < 4; i += 1) {
    const src = path.join(dir, 'src')
    if (existsSync(src) && statSync(src).isDirectory()) return dir
    dir = path.dirname(dir)
  }
  return path.resolve(start, '..')
}
const FRONTEND = findeWurzel(HIER)
const EINRICHTUNG = path.join(FRONTEND, 'src/diakonos/components/einrichtung')
const TOKENS = readFileSync(path.join(FRONTEND, 'src/diakonos/tokens.css'), 'utf8')

/** Alle .vue-Dateien des Assistenten (Seite + Schritte). */
function dateien() {
  const seite = path.join(FRONTEND, 'src/diakonos/pages/einrichtung')
  return [EINRICHTUNG, seite].flatMap((ordner) =>
    readdirSync(ordner)
      .filter((name) => name.endsWith('.vue'))
      .map((name) => path.join(ordner, name)),
  )
}

/** `name="haken" :size="…"` — der Wert ist das, was zählt. */
function groessen(quelle) {
  return [...quelle.matchAll(/:size="([^"]*)"/g)].map((treffer) => treffer[1].trim())
}

const treffer = dateien().flatMap((datei) => {
  const quelle = readFileSync(datei, 'utf8')
  return groessen(quelle).map((wert) => ({ datei: path.basename(datei), wert, quelle }))
})

test('Symbolgrößen des Assistenten sind Tokens, keine Zahlen und kein var() im Attribut', () => {
  assert.ok(treffer.length >= 5, `zu wenige gefundene :size-Bindungen (${treffer.length})`)
  for (const { datei, wert, quelle } of treffer) {
    // 1. `var(…)` darf NICHT ins SVG-Attribut gelangen (`Expected length`).
    //    Der Token ist Pflicht; die Komponente setzt ihn als style und hält
    //    das Attribut bei `1` — das prüft der zweite Test.
    // Der Wert ist entweder direkt `var(--…)` oder eine Konstante der Datei,
    // die auf ein Token zeigt (`const haken = 'var(--assistent-…)'`).
    const token = wert.includes('var(--')
      ? wert
      : (quelle.match(new RegExp(`const ${wert} = '(var\\(--[^']*)'`)) || [])[1] || ''
    assert.ok(
      token.includes('var(--'),
      `${datei}: :size="${wert}" ist kein Token — Größen stehen in tokens.css`,
    )
    // 2. Zahlen sind keine Tokens (Ausnahme: der Platzhalter `1` in der
    //    Komponente selbst ist ein Attribut-Wert, kein :size-Aufruf).
    assert.ok(
      !/^[\d.]+$/.test(wert),
      `${datei}: :size="${wert}" ist eine Zahl — Größen stehen in tokens.css`,
    )
    // 3. Der genannte Token muss es geben (Tippfehler wären still).
    for (const name of token.match(/--[a-z0-9-]+/g) || []) {
      assert.ok(TOKENS.includes(`${name}:`), `${datei}: Token ${name} fehlt in tokens.css`)
    }
  }
})

test('AssistentSymbol setzt die Größe als CSS und hält das Attribut bei echtem Wert', () => {
  const quelle = readFileSync(path.join(EINRICHTUNG, 'AssistentSymbol.vue'), 'utf8')
  // Die Größe kommt als style — dort sind Tokens erlaubt und wirksam.
  assert.match(quelle, /:style="\{ width: size, height: size \}"/)
  // Das Attribut trägt NIE eine Variable (die Browser-Meldung „Expected length").
  assert.ok(!/:width="size"/.test(quelle), ':width darf nicht direkt an size hängen')
  assert.ok(!/:height="size"/.test(quelle), ':height darf nicht direkt an size hängen')
  // Rückfall für Aufrufer, die keine Größe nennen: ebenfalls ein Token.
  assert.match(quelle, /default: 'var\(--icon-md\)'/)
})
