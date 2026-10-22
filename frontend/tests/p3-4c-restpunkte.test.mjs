/**
 * P3-4c — Waechter fuer die letzten Design-Reste aus P3-4b:
 *
 *   OP-HANDY-26  Tippziele am Handy unter 24 px (WCAG 2.5.8). Gemessen waren
 *                Termin-Chips 47×22, „Aktualisieren“ 22×22, „Plan öffnen“
 *                67×17, Sichtbarkeits-Kästchen 16×16, Dialog-✕ 24–32.
 *   DES-03       Gruppen-Kachel: Hover-Effekt hing an einem Inline-Handler und
 *                ging beim Umbau auf <a> verloren; der Schatten war fest und im
 *                Dunkelmodus kaum sichtbar.
 *
 * Die Regeln stehen zentral in index.css bzw. Gruppen.vue — dieser Test haelt
 * sie fest, damit sie bei der naechsten Aufraeumrunde nicht still verschwinden.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const root = new URL('../', import.meta.url)
const lies = p => readFileSync(new URL(p, root), 'utf8')

const INDEX_CSS = 'src/diakonos/index.css'
const GRUPPEN = 'src/diakonos/pages/Gruppen.vue'

/** Der Block `@media (hover: none) and (pointer: coarse) { … }` im Stylesheet. */
function groberZeigerBlock(css) {
  const start = css.indexOf('@media (hover: none) and (pointer: coarse)')
  assert.ok(start >= 0, 'Regel fuer groben Zeiger fehlt in index.css')
  // Bis zur passenden schliessenden Klammer mitzaehlen.
  let tiefe = 0
  let i = css.indexOf('{', start)
  const ab = i
  for (; i < css.length; i += 1) {
    if (css[i] === '{') tiefe += 1
    else if (css[i] === '}') {
      tiefe -= 1
      if (tiefe === 0) return css.slice(ab, i + 1)
    }
  }
  throw new Error('Block nicht geschlossen')
}

test('OP-HANDY-26: kleine Knoepfe, Chips und Kaestchen sind am Handy mindestens 24 px hoch', () => {
  const block = groberZeigerBlock(lies(INDEX_CSS))
  assert.match(block, /min-height:\s*24px/,
    'im Grob-Zeiger-Block fehlt die Mindesthoehe 24 px (WCAG 2.5.8)')
  for (const selektor of ['.dk-btn', '.dk-btn-sm', '.dk-btn-icon', '.dk-filter-chip',
                          'input[type="checkbox"]', 'input[type="radio"]']) {
    assert.ok(block.includes(selektor),
      `${selektor} fehlt bei den Mindesthoehen — das Tippziel bleibt zu klein`)
  }
  assert.match(block, /min-width:\s*24px/,
    'Symbole/Kaestchen brauchen auch 24 px Breite')
})

test('OP-HANDY-26: das Kaestchen ist ueber die ganze Beschriftung antippbar', () => {
  const block = groberZeigerBlock(lies(INDEX_CSS))
  assert.match(block, /label:has\(>\s*input\[type="checkbox"\]\)/,
    'ohne Label-Flaeche bleibt nur das 16-px-Kaestchen als Tippziel')
  assert.match(block, /label:has\(>\s*input\[type="radio"\]\)/,
    'dasselbe gilt fuer Auswahlknoepfe (radio)')
})

test('OP-HANDY-26: die Regel gilt NUR bei grobem Zeiger (Desktop bleibt dicht)', () => {
  const css = lies(INDEX_CSS)
  // Die 24-px-Regeln duerfen nicht ausserhalb des Grob-Zeiger-Blocks stehen.
  const aussen = css.replace(groberZeigerBlock(css), '')
  const treffer = aussen.match(/[^{}]*min-height:\s*24px[^}]*}/g) || []
  const verdaechtig = treffer.filter(t => /\.dk-btn-sm|\.dk-filter-chip|dk-btn-icon/.test(t))
  assert.deepEqual(verdaechtig, [],
    'eine 24-px-Regel steht ausserhalb des Grob-Zeiger-Blocks — der Desktop wird mitgezogen')
})

test('DES-03: die Gruppen-Kachel reagiert wieder auf die Maus (CSS, kein Inline-Handler)', () => {
  const gruppen = lies(GRUPPEN)
  assert.match(gruppen, /\.gr-kachel:hover\s*\{/,
    'kein :hover fuer .gr-kachel — der Effekt ging beim Umbau auf <a> verloren')
  assert.match(gruppen, /\.gr-kachel:focus-visible\s*\{/,
    'Tastaturnutzer brauchen einen sichtbaren Fokus auf der Kachel')
  assert.ok(!/@(mouseenter|mouseover)=/.test(gruppen),
    'Hover laeuft wieder ueber einen Inline-Handler statt ueber CSS')
  assert.match(gruppen, /:href="'#\/gruppe\/'/, 'die Kachel ist kein Link mehr')
})

test('DES-03: der Kachel-Schatten kommt aus Tokens (Dunkelmodus sichtbar)', () => {
  const gruppen = lies(GRUPPEN)
  assert.match(gruppen, /\.gr-kachel\s*\{[^}]*box-shadow:\s*var\(--dk-shadow-/,
    'der Schatten ist fest statt aus dem Token-System — im Dunkelmodus kaum sichtbar')
  assert.match(gruppen, /\.gr-kachel:hover\s*\{[^}]*box-shadow:\s*var\(--dk-shadow-/,
    'der Hover-Schatten muss ebenfalls aus Tokens kommen')
})
