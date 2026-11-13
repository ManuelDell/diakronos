/**
 * DEV-4b · Wächter: Nacharbeit aus dem DEV-4-Review (Opus).
 *
 *   1. HOCH — `[data-theme="dark"] .dk-tab.is-active { color: var(--dk-navy-900) }`
 *      stand in index.css und setzte die Beschriftung des aktiven Reiters auf
 *      Dunkelblau auf dunkler Fläche (.dk-tab hat `background: none`). Betroffen:
 *      Planrahmen-Reiter (Plan.vue, PlantypEditor.vue, Stammdaten.vue). Es gilt
 *      wieder die hell-weisse Regel für den Dunkelmodus (index.css, Tabs-Block).
 *   2. NIEDRIG — wirkungslose Regeln: `--primary-ink` ist im Dunkelmodus schon
 *      `--dk-navy-900` (tokens.css). Die zusätzliche Dunkelmodus-Regel in
 *      DkButton.vue / kronos.css setzt denselben Wert nochmal und entfällt.
 *   3. NIEDRIG — der Dialog-Block von `.dk-ui-eingabe` wiederholt Innenabstand,
 *      Radius und font-family der Grundform; stehen bleibt nur `width: 100%`.
 *
 * Läuft im Docker-Build über den Globb `tests/dev4-*.test.mjs`.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const WURZEL = new URL('../src/diakonos/', import.meta.url)
const read = (p) => readFileSync(new URL(p, WURZEL), 'utf8')

/** Zerlegt ein Stylesheet in Regeln { selektor, rumpf }. */
function regeln(text) {
  const ohneKommentare = text.replace(/\/\*[\s\S]*?\*\//g, '')
  const ergebnis = []
  const stapel = []
  let puffer = ''
  for (const zeichen of ohneKommentare) {
    if (zeichen === '{') {
      stapel.push(puffer.trim())
      puffer = ''
    } else if (zeichen === '}') {
      const selektor = stapel.pop() || ''
      if (!selektor.startsWith('@') && selektor) ergebnis.push({ selektor, rumpf: puffer })
      puffer = ''
    } else {
      puffer += zeichen
    }
  }
  return ergebnis
}

/** Alle Selektoren einer (ggf. mit Komma geteilten) Regel. */
const selektoren = (selektor) => selektor.split(',').map((s) => s.trim())

/** Schriftfarbe der Regel, oder null. */
const schriftfarbe = (rumpf) => {
  const m = rumpf.match(/(^|[;{\s])color\s*:\s*([^;]+)/)
  return m ? m[2].trim() : null
}

/** Tokens, die im Dunkelmodus DUNKEL sind (dunkle Markenstufen). */
const DUNKLE_TOKENS = ['--dk-navy-9', '--dk-navy-8', '--dk-navy-7', '--dk-brand-50', '--dk-brand-100']

// ── 1 · aktiver Reiter im Dunkelmodus ──────────────────────────────────────
test('DEV-4b · aktiver .dk-tab hat im Dunkelmodus keine dunkle Schriftfarbe', () => {
  const css = read('index.css')
  const regelnAlle = regeln(css)

  // Alle Regeln, die den aktiven Reiter im Dunkelmodus anfassen.
  const dunkleReiter = []
  for (const r of regelnAlle) {
    for (const s of selektoren(r.selektor)) {
      if (s.startsWith('[data-theme="dark"]') && /\.dk-tab\.is-active$/.test(s)) {
        dunkleReiter.push({ selektor: s, rumpf: r.rumpf })
      }
    }
  }
  assert.equal(dunkleReiter.length, 1,
    'index.css: genau EINE Dunkelmodus-Regel für .dk-tab.is-active')

  const wert = schriftfarbe(dunkleReiter[0].rumpf)
  assert.ok(wert, '.dk-tab.is-active (dunkel): Schriftfarbe muss gesetzt sein')
  // Kein Token, das im Dunkelmodus dunkel ist → dunkelblau auf dunkler Fläche.
  for (const token of DUNKLE_TOKENS) {
    assert.ok(!wert.includes(token),
      `.dk-tab.is-active (dunkel): ${wert} ist im Dunkelmodus dunkel → Reiter unlesbar`)
  }
  assert.equal(wert, '#fff', '.dk-tab.is-active (dunkel): helle Beschriftung auf dunkler Fläche')

  // Die helle Regel für den Hellmodus bleibt unangetastet.
  const hell = regelnAlle.filter((r) => selektoren(r.selektor).includes('.dk-tab.is-active'))
  assert.ok(hell.length, 'index.css: Regel .dk-tab.is-active (hell)')
  assert.match(hell[0].rumpf, /color:\s*var\(--dk-brand-800\)/, 'Hellmodus unverändert')
})

test('DEV-4b · Planrahmen-Reiter tragen die Klasse .dk-tab (kein eigener Farbwert)', () => {
  // Die drei Seiten der Karte dürfen den Reiter nicht lokal umfärben —
  // sonst liefe die Korrektur ins Leere.
  for (const datei of [
    'pages/planrahmen/Plan.vue',
    'pages/planrahmen/PlantypEditor.vue',
    'pages/planrahmen/Stammdaten.vue',
  ]) {
    const text = read(datei)
    assert.match(text, /class="dk-tab"/, `${datei}: Reiter mit der Bibliotheksklasse .dk-tab`)
    const stil = (text.match(/<style[\s\S]*?<\/style>/g) || []).join('\n')
    const faerbt = regeln(stil).filter((r) => /\.dk-tab\b/.test(r.selektor) && schriftfarbe(r.rumpf))
    assert.deepEqual(faerbt.map((r) => r.selektor), [],
      `${datei}: kein eigener Farbwert für .dk-tab`)
  }
})

// ── 2 · wirkungslose --primary-ink-Regeln ──────────────────────────────────
test('DEV-4b · im Dunkelmodus ist --primary-ink bereits dunkelblau (Begründung der Löschung)', () => {
  const tokens = read('tokens.css')
  const dunkel = regeln(tokens).filter(
    (r) => r.selektor.includes('[data-theme="dark"]') && /--primary-ink\s*:/.test(r.rumpf),
  )
  assert.ok(dunkel.length, 'tokens.css: --primary-ink im dunklen Theme')
  // MT-7 (Nacharbeit 12.11., Review-Punkt 10): Der Druck-Block setzt fürs Papier
  // ALLE Farben der hellen Fassung, auch `--primary-ink`. `regeln` ordnet keine
  // At-Regeln zu — der Block trägt deshalb den Selektor `:root` wie der helle
  // Satz. Erkannt wird er an seiner Marke `color-scheme: light`, die keine
  // Bildschirm-Fassung der Dunkel-Tokens setzt.
  const bildschirmDunkel = dunkel.filter((r) => !/color-scheme:\s*light/.test(r.rumpf))
  assert.ok(bildschirmDunkel.length, 'tokens.css: --primary-ink im dunklen Theme (Bildschirm)')
  assert.match(bildschirmDunkel[bildschirmDunkel.length - 1].rumpf, /--primary-ink:\s*var\(--dk-navy-900\)/,
    '--primary-ink zeigt im Dunkelmodus schon auf --dk-navy-900 → Extraregeln wirkungslos')
})

test('DEV-4b · keine doppelte Dunkelmodus-Regel für --primary/--danger in DkButton.vue', () => {
  const knopf = read('components/ui/DkButton.vue')
  const doppelt = regeln(knopf).filter(
    (r) => r.selektor.includes('[data-theme="dark"]'),
  )
  assert.deepEqual(doppelt.map((r) => r.selektor), [],
    'DkButton.vue: Dunkelmodus-Regel setzt nur --primary-ink nach → entfällt')
  // Der helle Zustand behält --primary-ink (dort ist es weiß).
  const hell = regeln(knopf).find((r) => r.selektor === '.dk-ui-btn--primary')
  assert.ok(hell && /color:\s*var\(--primary-ink\)/.test(hell.rumpf), 'heller Zustand unverändert')
})

test('DEV-4b · keine doppelte Dunkelmodus-Regel für .btn-primary in kronos.css', () => {
  const kronos = read('kronos.css')
  const doppelt = regeln(kronos).filter((r) => r.selektor.includes('[data-theme="dark"] .btn-primary'))
  assert.deepEqual(doppelt.map((r) => r.selektor), [],
    'kronos.css: Dunkelmodus-Regel für .btn-primary wirkungslos → entfällt')
  const hell = regeln(kronos).find((r) => r.selektor === '.btn-primary')
  assert.ok(hell, 'kronos.css: .btn-primary im hellen Theme vorhanden')
})

// ── 3 · Dialog-Block von .dk-ui-eingabe ────────────────────────────────────
test('DEV-4b · Dialog-Block von .dk-ui-eingabe setzt nur noch width: 100%', () => {
  const css = read('index.css')
  const dialog = regeln(css).filter((r) =>
    selektoren(r.selektor).every((s) => /^(\.dk-modal|\.dk-ui-dialog) \.dk-ui-eingabe$/.test(s)) &&
    (r.selektor.includes('.dk-modal') || r.selektor.includes('.dk-ui-dialog')))
  assert.ok(dialog.length, 'index.css: Dialog-Block .dk-ui-eingabe')
  for (const r of dialog) {
    const deklarationen = r.rumpf
      .split(';')
      .map((d) => d.trim())
      .filter(Boolean)
    assert.deepEqual(deklarationen, ['width: 100%'],
      `${r.selektor}: nur die Breite bleibt (Form steht in der Grundform)`)
  }
  // Grundform bleibt: Innenabstand + Radius, KEIN width, KEINE font-size.
  const basis = regeln(css).filter((r) => r.selektor === '.dk-ui-eingabe')
  assert.ok(basis.length, 'index.css: Grundform .dk-ui-eingabe')
  const rumpf = basis.map((r) => r.rumpf).join(';')
  // UX1a: Innenabstand aus der Skala (--sp-2 = 8 px, --sp-3 = 12 px).
  assert.match(rumpf, /padding:\s*(?:var\(--sp-2\) var\(--sp-3\)|8px 12px)/, 'Grundform: Innenabstand bleibt')
  assert.match(rumpf, /border-radius:\s*var\(--radius\)/, 'Grundform: Radius aus Token bleibt')
  assert.doesNotMatch(rumpf, /(^|[;{\s])width\s*:/, 'Grundform: kein width')
  assert.doesNotMatch(rumpf, /font-size\s*:/, 'Grundform: keine font-size')
})
