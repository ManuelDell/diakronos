/**
 * DEP-2b — WÄCHTER: die Grundreset-Regeln haben Spezifitaet 0.
 *
 * Befund HOCH aus der Operator-Runde zu DEP-2: `grundreset.css` schrieb
 *   [type='button'], button { background: none; border: 0; padding: 0 }
 * `[type='button']` wiegt (0,1,0) — genau so viel wie eine Komponentenklasse
 * wie `.dk-ui-chip` (0,1,0). Bei gleicher Spezifitaet entscheidet die
 * Reihenfolge, und die ist im Buendel NICHT die der Quelldatei: `index.css`
 * zieht das Reset per `@import` nach oben, Vite sammelt die `@import`-Inhalte
 * aber ein und haengt sie hinter die direkt geschriebenen Regeln. Ergebnis:
 * die Filterchips verloren Rahmen, Hintergrund und Innenabstand — im
 * Bildvergleich `beitraege-mobil` bis 8,4 % Pixeldiff.
 *
 * Dieser Test haelt die Reparatur fest. Er prueft NICHT den Pixeldiff (das
 * macht der Screenshot-Vergleich), sondern die Ursache:
 *
 *   A) Jeder Selektor in grundreset.css steht in `:where(...)` — oder ist eine
 *      begruendete Ausnahme (AUSNAHMEN, siehe unten). `:where()` zaehlt selbst
 *      mit Spezifitaet 0 und gibt sie NICHT an seinen Inhalt weiter.
 *   B) Die Praxisprobe: fuer die Reset-Regeln wird die CSS-Spezifitaet wirklich
 *      ausgerechnet und gegen `.dk-ui-chip` gestellt. Waere sie hoeher, faellt
 *      der Test — auch wenn jemand spaeter `:where()` wieder entfernt.
 *   C) Das Buendel: steht dist/css/*.css vorliegt, muessen die Reset-Regeln
 *      darin VOR den `.dk-ui-chip`-Regeln stehen. Das ist die zweite Haelfte
 *      der Absicherung — selbst bei gleicher Spezifitaet darf die Reihenfolge
 *      nicht gegen die Komponente laufen.
 *
 * Was der Test NICHT abdeckt: `[hidden] { display: none !important }`. Das ist
 * Absicht und keine Spezifitaetsfrage — `!important` schlaegt jede normale
 * Deklaration; das Reset muss `display`-Utilities ueberstimmen koennen, sonst
 * blieben per `v-show` ausgeblendete Elemente sichtbar.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const DATEI = path.join(frontend, 'src', 'grundreset.css')

/** Ausnahmen: Selektor -> Begruendung. Nur `!important`-Regeln gehoeren hierher. */
const AUSNAHMEN = new Map([
  ['[hidden]', 'muss display-Utilities per !important ueberstimmen (v-show/hidden-Attribut)'],
])

function ohneKommentare(text) {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|\s)\/\/[^\n]*/g, '$1')
}

/**
 * Zerlegt CSS in Regeln { selektoren: [...], rumpf: '...' }.
 * Reicht fuer die flache Struktur der Reset-Datei (keine Verschachtelung,
 * keine Media-Queries) — und genau das soll dort auch nie entstehen: eine
 * Reset-Regel in einem @media-Block waere eine Gestaltungsregel und gehoert
 * in die Komponente.
 */
function regeln(css) {
  const out = []
  const re = /([^{}]+)\{([^{}]*)\}/g
  let m
  while ((m = re.exec(css))) {
    out.push({ selektoren: selektorenListe(m[1]), rumpf: m[2].trim() })
  }
  return out
}

/**
 * Trennt eine Selektorliste an Kommas, die NICHT in Klammern stehen.
 * Wichtig fuer `:where(button, input, select)` — ein naives `split(',')`
 * zerlegt die Funktionsargumente und meldet danach Phantom-Selektoren
 * (`input`, `optgroup`, `textarea)`) als Verstoss.
 */
function selektorenListe(text) {
  const out = []
  let tiefe = 0, aktuell = ''
  for (const zeichen of text) {
    if (zeichen === '(' || zeichen === '[') tiefe += 1
    if (zeichen === ')' || zeichen === ']') tiefe -= 1
    if (zeichen === ',' && tiefe === 0) { out.push(aktuell.trim()); aktuell = ''; continue }
    aktuell += zeichen
  }
  if (aktuell.trim()) out.push(aktuell.trim())
  return out.filter(Boolean)
}

/**
 * Spezifitaet nach CSS-Spezifikation (a,b,c):
 *   a = IDs, b = Klassen/Attribute/Pseudo-Klassen, c = Elemente/Pseudo-Elemente.
 * `:where(...)` zaehlt als (0,0,0) und seine Argumente werden NICHT gezaehlt —
 * deshalb wird der Inhalt vorher entfernt. `:is()`/`:not()` tragen das Maximum
 * ihrer Argumente, darauf kommt es hier nicht an: dieser Test verlangt
 * `:where()` und wuerde `:is()` als Verstoss melden.
 */
function spezifitaet(selektor) {
  let s = selektor.trim()
  // :where(...) neutralisieren (auch geschachtelt, daher Schleife)
  let vorher
  do {
    vorher = s
    s = s.replace(/:where\((?:[^()]|\([^()]*\))*\)/g, '')
  } while (s !== vorher)

  // Attributselektoren entfernen, aber zaehlen
  let b = 0
  s = s.replace(/\[[^\]]*\]/g, () => { b += 1; return '' })

  const a = (s.match(/#[\w-]+/g) || []).length
  b += (s.match(/\.[\w-]+/g) || []).length
  b += (s.match(/:(?!:)[\w-]+(\([^)]*\))?/g) || []).length
  const c = (s.match(/(^|[\s>+~])[a-zA-Z][\w-]*/g) || []).length
  const pseudoElemente = (s.match(/::[\w-]+/g) || []).length
  return [a, b, c + pseudoElemente]
}

const vergleiche = (x, y) => x[0] - y[0] || x[1] - y[1] || x[2] - y[2]

// ── A) Jeder Selektor steht in :where(...) ────────────────────────────────

test('jeder Reset-Selektor steht in :where(...) (Spezifitaet 0)', () => {
  const css = ohneKommentare(fs.readFileSync(DATEI, 'utf8'))
  assert.ok(css.trim().length > 0, 'grundreset.css ist leer')

  const verstoss = []
  for (const { selektoren } of regeln(css)) {
    for (const sel of selektoren) {
      if (AUSNAHMEN.has(sel)) continue
      if (/^:where\(/.test(sel)) continue
      verstoss.push(sel)
    }
  }
  assert.deepEqual(verstoss, [],
    'Diese Reset-Selektoren stehen nicht in :where(...) und koennen Komponentenklassen '
    + 'wie .dk-ui-chip ueberstimmen (Regressionsbefund DEP-2b): ' + verstoss.join(' | '))
})

test('keine Reset-Regel mit Spezifitaet > 0 (nachgerechnet)', () => {
  const css = ohneKommentare(fs.readFileSync(DATEI, 'utf8'))
  const zuHoch = []
  for (const { selektoren, rumpf } of regeln(css)) {
    // `!important`-Regeln sind von der Spezifitaetsfrage ausgenommen (AUSNAHMEN).
    if (/!important/.test(rumpf)) continue
    for (const sel of selektoren) {
      const wert = spezifitaet(sel)
      if (vergleiche(wert, [0, 0, 0]) > 0) zuHoch.push(`${sel} -> (${wert.join(',')})`)
    }
  }
  assert.deepEqual(zuHoch, [],
    'Reset-Regeln mit Spezifitaet > 0 (0,0,0 erwartet): ' + zuHoch.join(' | '))
})

test('Praxisprobe: Reset verliert gegen .dk-ui-chip', () => {
  // Der Fall, der den Befund ausgeloest hat: `[type='button']` gegen die
  // Chip-Klasse. Nach der Reparatur muss die Reset-Regel nachgeben.
  const css = ohneKommentare(fs.readFileSync(DATEI, 'utf8'))
  const chip = spezifitaet('.dk-ui-chip')
  const buttonReset = regeln(css)
    .flatMap(r => r.selektoren.map(sel => ({ sel, rumpf: r.rumpf })))
    .filter(r => /\[type='button'\]|\[type="button"\]/.test(r.sel))
  assert.ok(buttonReset.length, 'die Button-Reset-Regel fehlt ganz (background/border/padding)')

  for (const { sel, rumpf } of buttonReset) {
    // Nur die Aussehen-Deklarationen pruefen; `cursor`/`-webkit-appearance`
    // sind unkritisch, weil die Chip-Klasse sie selbst setzt.
    if (!/background:\s*none|border:\s*0|padding:\s*0/.test(rumpf)) continue
    assert.ok(vergleiche(spezifitaet(sel), chip) < 0,
      `${sel} (${spezifitaet(sel).join(',')}) ist nicht schwaecher als .dk-ui-chip `
      + `(${chip.join(',')}) — der Chip verliert wieder Rahmen, Hintergrund und Innenabstand`)
  }
})

// ── B2) Layer: das Reset liegt in `@layer reset` ──────────────────────────

test('grundreset.css liegt vollstaendig in @layer reset', () => {
  // Die HAELFTE der Reparatur, die auch die REIHENFOLGE im Buendel heilt.
  // Ohne sie entscheidet die Byte-Position: Vite stellt per @import
  // eingesammelte Regeln hinter die direkt geschriebenen, das Reset landete
  // NACH .dk-ui-chip (gemessen) — und dann verliert der Chip.
  const css = ohneKommentare(fs.readFileSync(DATEI, 'utf8')).trim()
  assert.match(css, /^@layer\s+reset\s*\{/,
    'grundreset.css beginnt nicht mit `@layer reset {` — dann entscheidet wieder '
    + 'die Stelle im Buendel statt der Layer')
  assert.match(css, /\}\s*$/,
    'grundreset.css schliesst den @layer-Block nicht am Dateiende '
    + '(alles muss INNERHALB des Layers stehen)')

  // Keine Regel ausserhalb des Layers: alles zwischen `@layer reset {` und der
  // letzten schliessenden Klammer wird geprueft. Eine Regel ausserhalb ist
  // ungelayerte Konkurrenz zu den Komponenten.
  const innen = css.slice(css.indexOf('{') + 1, css.lastIndexOf('}'))
  const klammerbilanz = (innen.match(/\{/g) || []).length - (innen.match(/\}/g) || []).length
  assert.equal(klammerbilanz, 0,
    'innerhalb von @layer reset stimmen die Klammern nicht — es steht eine Regel ausserhalb')
})

test('index.css legt die Layer-Reihenfolge mit reset zuerst fest', () => {
  const index = ohneKommentare(
    fs.readFileSync(path.join(frontend, 'src', 'diakonos', 'index.css'), 'utf8'))
  const m = index.match(/@layer\s+([\w\s,.-]+);/)
  assert.ok(m, 'index.css deklariert keine Layer-Reihenfolge (`@layer reset, …;`)')
  const reihenfolge = m[1].split(',').map(s => s.trim()).filter(Boolean)
  assert.equal(reihenfolge[0], 'reset',
    `reset muss der ERSTE (schwaechste) Layer sein, steht aber an ${reihenfolge.indexOf('reset') + 1}. `
    + 'Stelle: ' + reihenfolge.join(' -> '))
  // Die Layer der Beteiligten muessen in der Reihenfolge vorkommen.
  for (const layer of ['theme', 'utilities']) {
    assert.ok(reihenfolge.includes(layer),
      `Layer "${layer}" (Tailwind) fehlt in der Reihenfolge — sonst legt ihn Tailwind selbst an`)
  }
})

test('registrierung und organigramm setzen die Layer-Reihenfolge VOR dem Reset', () => {
  // Die beiden Einstiege laden index.css NICHT; ohne eigene Deklaration legt
  // ihr Buendel die Reihenfolge implizit nach der Stelle fest — und das Reset
  // kann dann wieder ueber den Komponenten landen.
  const datei = path.join(frontend, 'src', 'layer-reihenfolge.css')
  assert.ok(fs.existsSync(datei), 'src/layer-reihenfolge.css fehlt')
  const reihenfolgeDatei = ohneKommentare(fs.readFileSync(datei, 'utf8'))
  const m = reihenfolgeDatei.match(/@layer\s+([\w\s,.-]+);/)
  assert.ok(m, 'layer-reihenfolge.css deklariert keine Reihenfolge')
  assert.equal(m[1].split(',').map(s => s.trim())[0], 'reset',
    'reset muss auch hier der erste (schwaechste) Layer sein')

  for (const einstieg of ['registrierung', 'organigramm']) {
    const main = ohneKommentare(
      fs.readFileSync(path.join(frontend, 'src', einstieg, 'main.js'), 'utf8'))
    const posReihenfolge = main.indexOf('layer-reihenfolge.css')
    const posReset = main.indexOf('grundreset.css')
    assert.ok(posReihenfolge >= 0, `${einstieg}/main.js laedt layer-reihenfolge.css nicht`)
    assert.ok(posReihenfolge < posReset,
      `${einstieg}/main.js laedt die Layer-Reihenfolge NACH dem Grundreset — dann ist sie zu spaet`)
  }
  // gast laedt das Reset ueber index.css und Tailwind ueber style.css: die
  // Reihenfolge muss vor BEIDEN stehen.
  const gast = ohneKommentare(fs.readFileSync(path.join(frontend, 'src', 'gast', 'main.js'), 'utf8'))
  const posGast = gast.indexOf('layer-reihenfolge.css')
  assert.ok(posGast >= 0, 'gast/main.js laedt layer-reihenfolge.css nicht')
  assert.ok(posGast < gast.indexOf('style.css') && posGast < gast.indexOf('index.css'),
    'gast/main.js laedt die Layer-Reihenfolge zu spaet')
})

// ── C) Buendel: Reset steht vor den Komponentenregeln ─────────────────────

test('im Buendel liegt das Reset im Layer reset (nicht in der Byte-Reihenfolge)', () => {
  const verzeichnis = path.join(frontend, 'dist', 'css')
  if (!fs.existsSync(verzeichnis)) {
    // Im Build-Kontext existiert dist/ erst nach dem Vite-Lauf; der Test laeuft
    // dort VOR dem Build (siehe Dockerfile). Ohne Buendel ist Punkt C nicht
    // pruefbar — A und B gelten unabhaengig davon.
    return
  }
  const dateien = fs.readdirSync(verzeichnis).filter(f => f.endsWith('.css'))
  assert.ok(dateien.length, 'dist/css enthaelt kein CSS')

  // Die fruehere Fassung dieses Tests verlangte „Reset VOR .dk-ui-chip in den
  // Bytes". Das war die falsche Pruefung: gemessen stand das Reset bei Byte
  // 56273 und .dk-ui-chip bei 1307 — Vite stellt per @import eingesammelte
  // Regeln hinter die direkt geschriebenen. Die REIHENFOLGE ist im Buendel
  // also nicht verlaesslich; verlaesslich ist nur der LAYER. Deshalb prueft
  // dieser Test jetzt, dass das Reset wirklich im Layer `reset` steht und
  // dessen Reihenfolge im Buendel zuerst deklariert wird.
  for (const datei of dateien) {
    const css = ohneKommentare(fs.readFileSync(path.join(verzeichnis, datei), 'utf8'))
    if (!css.includes('.dk-ui-chip')) continue  // nicht die SPA-Datei

    const layerDeklaration = css.match(/@layer\s+([\w\s,.-]+);/)
    assert.ok(layerDeklaration,
      `${datei}: keine @layer-Reihenfolge im Buendel — dann entscheidet die Byte-Position`)
    const reihenfolge = layerDeklaration[1].split(',').map(s => s.trim()).filter(Boolean)
    assert.equal(reihenfolge[0], 'reset',
      `${datei}: reset ist nicht der erste Layer (${reihenfolge.join(' -> ')}) — `
      + 'damit kann das Reset Komponenten wie .dk-ui-chip ueberstimmen')

    // Das box-sizing-Reset muss INNERHALB von `@layer reset { … }` stehen.
    const start = css.indexOf('@layer reset')
    assert.ok(start >= 0, `${datei}: kein @layer reset-Block im Buendel`)
    const blockEnde = css.indexOf('@layer', start + 1)
    const block = css.slice(start, blockEnde < 0 ? undefined : blockEnde)
    assert.match(block, /box-sizing:\s*border-box/,
      `${datei}: das box-sizing-Reset steht NICHT im Layer reset — es kann die Chips `
      + 'wieder ueberschreiben (genau der Befund)')
  }
})
