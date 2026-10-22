import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

/**
 * P3-4b — Restpunkte 2 (Ressourcen-Kachel) und 7 (Fokusring).
 *
 * K2 · Fokusring auf der hellen Seitenleiste (WCAG 1.4.11, ≥ 3:1):
 *   Der globale `--focus-ring` (navy-400, #3e4d78) erreicht auf dem
 *   Seitenleisten-Grundton (navy-700, #11183a) nur 2,09:1 — unsichtbar. Die
 *   Seitenleiste braucht deshalb eine eigene, deckende Ringfarbe
 *   (`--focus-ring-side`). Der Test rechnet den Kontrast aus den TOKEN-Werten
 *   des Stilblatts nach (keine abgeschriebenen Zahlen) und prüft, dass die
 *   Seitenleisten-Regel diese Farbe verwendet.
 *
 * W3 · Ressourcen-Kachel: Die Kachel muss als Ganzes anwählbar sein, ohne
 *   verschachtelte Knöpfe (Knopf im Knopf) und ohne zweites Tab-Ziel.
 * K1 · Keine undefinierte Klasse `rs-icon-12` mehr in Ressourcen.vue.
 */
const root = new URL('../', import.meta.url)
const lies = p => readFileSync(new URL(p, root), 'utf8')

const tokens = lies('src/diakonos/tokens.css')
const index = lies('src/diakonos/index.css')
const ressourcen = lies('src/diakonos/pages/Ressourcen.vue')

/** Alle Token-Werte aus den :root- bzw. [data-theme=dark]-Blöcken einsammeln. */
function tokenWerte(css) {
  const werte = {}
  for (const m of css.matchAll(/--([\w-]+):\s*([^;]+);/g)) {
    if (!(m[1] in werte)) werte[m[1]] = m[2].trim()
  }
  return werte
}

/** Wert eines Tokens auflösen (`var(--x)`-Ketten, direktes Hex). */
function wert(token, werte, tiefe = 0) {
  if (tiefe > 8) return null
  const roh = werte[token]
  if (!roh) return null
  const alias = roh.match(/^var\(--([\w-]+)\)$/)
  if (alias) return wert(alias[1], werte, tiefe + 1)
  return /^#[0-9a-f]{6}$/i.test(roh) ? roh : null
}

function luminanz(hex) {
  const h = hex.slice(1)
  const teile = [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16) / 255)
  const f = c => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
  const [r, g, b] = teile.map(f)
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function kontrast(a, b) {
  const [hell, dunkel] = [luminanz(a), luminanz(b)].sort((x, y) => y - x)
  return (hell + 0.05) / (dunkel + 0.05)
}

const ohneKommentare = css => css.replace(/\/\*[\s\S]*?\*\//g, '')

/** Regelkörper aus EINEM Stilblatt (Seiten der SPA tragen ihre Stile selbst). */
function regelKorper(selektor, quelle = index) {
  for (const m of ohneKommentare(quelle).matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const selek = m[1].split(',').map(s => s.trim().replace(/\s+/g, ' '))
    if (selek.includes(selektor)) return m[2]
  }
  return null
}

test('K2: Fokusring der Seitenleiste erreicht 3:1 auf dem Seitenleisten-Grund', () => {
  const hell = tokenWerte(tokens)
  const ring = wert('focus-ring-side', hell)
  const grund = wert('side-bg', hell)
  assert.ok(ring, '--focus-ring-side fehlt (hell)')
  assert.ok(grund, '--side-bg fehlt (hell)')
  const verhaeltnis = kontrast(ring, grund)
  assert.ok(verhaeltnis >= 3,
    `Fokusring auf der hellen Seitenleiste nur ${verhaeltnis.toFixed(2)}:1 (≥ 3 nötig)`)
})

test('K2: der globale Ring haette auf der hellen Seitenleiste NICHT gereicht', () => {
  const hell = tokenWerte(tokens)
  const alt = wert('focus-ring', hell)
  const grund = wert('side-bg', hell)
  assert.ok(kontrast(alt, grund) < 3,
    'Wenn der globale Ring hier schon ≥ 3:1 hätte, bräuchte es keinen eigenen Token')
})

test('K2: die Seitenleisten-Fokuszustaende nutzen die eigene Ringfarbe', () => {
  const kopf = regelKorper('.dk-sb-nav a:focus-visible')
  assert.ok(kopf, 'Regel für Seitenleisten-Links fehlt')
  assert.match(kopf, /outline:\s*2px solid var\(--focus-ring-side\)/)
  const fuss = regelKorper('.dk-sb-logout:focus-visible')
  assert.match(fuss, /var\(--focus-ring-side\)/, 'Abmelde-Knopf nutzt noch den globalen Ring')
})

test('K2: auch im Dunkelmodus bleibt ein eigener Ring gesetzt', () => {
  const dunkelBlock = tokens.slice(tokens.indexOf('[data-theme="dark"]'))
  assert.match(dunkelBlock, /--focus-ring-side:\s*var\(--dk-navy-200\)/,
    '--focus-ring-side fehlt im Dunkelmodus')
})

test('W3: die Kachel ist als Ganzes anwählbar (gedehnter Titelknopf, keine Knöpfe im Knopf)', () => {
  const kachel = regelKorper('.rs-card-title--knopf::after', ressourcen)
  assert.ok(kachel, 'gedehnte Linkfläche der Kachel fehlt')
  assert.match(kachel, /position:\s*absolute/)
  assert.match(kachel, /inset:\s*0/)
  assert.match(regelKorper('.rs-card', ressourcen), /position:\s*relative/,
    'die Kachel muss Bezugsrahmen sein (sonst liegt die Fläche über der ganzen Seite)')
  assert.match(regelKorper('.rs-btn-book', ressourcen),
    /z-index:\s*1/, 'der „Buchen"-Knopf muss über der Linkfläche liegen')
  // Kein verschachtelter Knopf: der Titel ist ein <button>, aber ohne Knopf darin.
  const abschnitt = ressourcen.slice(ressourcen.indexOf('class="dk-content-card rs-card"'),
    ressourcen.indexOf('<!-- List View -->'))
  assert.match(abschnitt, /<button[\s\S]*?class="rs-card-title rs-card-title--knopf"[\s\S]*?<\/button>/,
    'der Titelknopf fehlt')
  assert.ok(!/<button[\s\S]*?<button/.test(abschnitt), 'Knopf im Knopf')
})

test('K1: die undefinierte Klasse rs-icon-12 ist verschwunden', () => {
  assert.ok(!/rs-icon-12/.test(ressourcen), 'Ressourcen.vue nutzt noch rs-icon-12')
  assert.ok(!/\.rs-icon-12\s*\{/.test(index), 'rs-icon-12 ist wieder definiert — dann dk-icon-xs vereinheitlichen')
  assert.match(ressourcen, /class="dk-icon-xs"/, 'Symbole brauchen die definierte Klasse dk-icon-xs')
})
