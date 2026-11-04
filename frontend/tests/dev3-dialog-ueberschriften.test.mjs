/**
 * DEV-3 · Dunkelmodus: Überschriften und Text in Dialogen und Karten
 *
 * Befund DMB-ab3be95cc15a: `.dk-modal h3` (index.css) hatte keine Farbe. Eine
 * Überschrift ohne Farbe erbt die Farbe ihres Elternteils; steht dort nichts
 * (oder eine feste helle Farbe), wird die Schrift im Dunkelmodus schwarz auf
 * dunkelblauer Fläche — betroffen war der Dialog „Wert bearbeiten“
 * (PrEditor → DkModal variant planrahmen).
 *
 * Operator-Zusatz aus Review DEV-1: Auch der Titel des Dialogs „Neue Gruppe“
 * war kontrastarm und das Namensfeld blieb weiß — `.dk-ui-eingabe` war nur
 * genannt, aber nirgends gestaltet (helle Browser-Vorgabe).
 *
 * Dieser Wächter prüft die ECHTEN Quelltexte (keine Kopien):
 *   1. Jede Überschriftenregel (h1–h4) in index.css, kronos.css und in den
 *      Komponenten-Dateien setzt eine Farbe aus Tokens (`var(--…)`, ohne
 *      festen Fallback).
 *   2. Die Farbregeln in `.dk-modal`, `.dk-ui-dialog` und `.dk-ui-card`
 *      (Titel, Fließtext) nutzen Tokens.
 *   3. `.dk-ui-eingabe` (Eingabefelder in Dialogen) hat eine Gestalt aus
 *      Tokens statt der hellen Browser-Vorgabe.
 *   4. Nirgends steht ein fester Farbwert als Fallback in `var(--…, #…)` —
 *      der greift, sobald eine Variable fehlt, und färbt dann auch im
 *      Dunkelmodus hell.
 *
 * Läuft im Docker-Build über den Globb `tests/dev3-*.test.mjs`.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs'

const WURZEL = new URL('../src/diakonos/', import.meta.url)
const read = (p) => readFileSync(new URL(p, WURZEL), 'utf8')

// Feste Farbe: #rgb/#rrggbb, rgb()/rgba(), hsl()/hsla()
const FESTE_FARBE = /#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(/
const FARB_DEKLARATION = /(^|[;{\s])(color|background|background-color|border-color|fill|stroke)\s*:\s*([^;{}]+)/g

/**
 * Zerlegt ein Stylesheet in Regeln { selektor, rumpf } (verschachtelte
 * @media-Blöcke werden aufgelöst, @keyframes bleiben als Regel stehen).
 * `bedingungen` sammelt die umschließenden @media/@supports-Köpfe — nötig,
 * um Touch-Regeln von Desktop-Regeln zu unterscheiden.
 */
function regeln(text) {
  const ohneKommentare = text.replace(/\/\*[\s\S]*?\*\//g, '')
  const ergebnis = []
  const stapel = []
  const bedingungen = []
  let puffer = ''
  for (const zeichen of ohneKommentare) {
    if (zeichen === '{') {
      const kopf = puffer.trim()
      stapel.push(kopf)
      if (kopf.startsWith('@')) bedingungen.push(kopf)
      puffer = ''
    } else if (zeichen === '}') {
      const selektor = stapel.pop() || ''
      const rumpf = puffer
      puffer = ''
      if (selektor.startsWith('@')) bedingungen.pop()
      // Verschachtelte Blöcke (@media, @supports) sind keine Selektoren.
      else if (selektor) ergebnis.push({ selektor, rumpf, bedingungen: [...bedingungen] })
    } else {
      puffer += zeichen
    }
  }
  return ergebnis
}

/**
 * Der OP-HANDY-14 Medien-Kontext (grober Zeiger).
 *
 * FIX-6: Touch-Anpassungen fragen seit der Operator-Entscheidung (27.10.) nur
 * noch den Zeiger ab: `(pointer: coarse)`. FIX-6c: die frühere zweite
 * Alternative (`not ((pointer: fine)`) ist ENTFERNT — sie war genau das
 * Kriterium, das abgeschafft wurde, und hätte eine solche Regel hier weiter
 * als Touch-Kontext durchgehen lassen. Touch ist `(pointer: coarse)`, fertig.
 */
const TOUCH_MEDIA = /\bpointer:\s*coarse\b/

/** Farbdeklarationen einer Regel. */
function farben(rumpf) {
  const treffer = []
  FARB_DEKLARATION.lastIndex = 0
  let m
  while ((m = FARB_DEKLARATION.exec(rumpf)) !== null) treffer.push(m[3].trim())
  return treffer
}

/** Ist der Wert ausschließlich `var(--…)` (mehrere, durch Leerzeichen)? */
function nurTokens(wert) {
  const ohneVar = wert.replace(/var\(\s*--[\w-]+\s*\)/g, '').trim()
  return ohneVar === ''
}

// ── 1 · Überschriftenebenen h1–h4 ──────────────────────────────────────────
const STYLESHEETS = ['index.css', 'kronos.css']

test('DEV-3 · jede Überschriftenregel in den Stylesheets setzt eine Token-Farbe', () => {
  const fehler = []
  for (const datei of STYLESHEETS) {
    for (const { selektor, rumpf } of regeln(read(datei))) {
      const selektoren = selektor.split(',').map((s) => s.trim())
      const betrifftUeberschrift = selektoren.some((s) => /(^|[\s>+~])h[1-4]\b/.test(s))
      if (!betrifftUeberschrift) continue
      const farbwerte = farben(rumpf).filter((w) => w.split(' ').length === 1)
      // Regeln, die nur Größe/Gewicht/Abstand setzen, sind erlaubt — die
      // Grundfarbe kommt aus der zentralen h1..h4-Regel. Verboten sind
      // FESTE Farben (die im Dunkelmodus nicht mitgehen).
      for (const wert of farben(rumpf)) {
        if (FESTE_FARBE.test(wert)) fehler.push(`${datei} · ${selektor} → ${wert}`)
      }
      if (farbwerte.length && !farbwerte.every(nurTokens) && !farbwerte.some((w) => w.includes('var(--'))) {
        fehler.push(`${datei} · ${selektor} → Farbe ohne Token: ${farbwerte.join(' ')}`)
      }
    }
  }
  assert.deepEqual(fehler, [], 'Überschriften dürfen nur Token-Farben tragen:\n' + fehler.join('\n'))
})

test('DEV-3 · die zentrale Regel gibt h1–h4 die Textfarbe des Themes', () => {
  const css = read('index.css')
  assert.match(
    css,
    /h1\s*,\s*h2\s*,\s*h3\s*,\s*h4\s*\{\s*color:\s*var\(--text\)\s*;\s*\}/,
    'index.css: h1, h2, h3, h4 bekommen color: var(--text)',
  )
})

test('DEV-3 · .dk-modal h3 trägt die Textfarbe aus den Tokens (Befund DMB-ab3be95cc15a)', () => {
  const css = read('index.css')
  const regel = regeln(css).find((r) => r.selektor === '.dk-modal h3')
  assert.ok(regel, 'index.css: Regel .dk-modal h3 vorhanden')
  assert.match(regel.rumpf, /color:\s*var\(--dk-text\)/,
    '.dk-modal h3 → color: var(--dk-text)')
})

// ── 2 · Dialog- und Kartenkomponenten ──────────────────────────────────────
const KOMPONENTEN = [
  ['components/ui/DkDialog.vue', '.dk-ui-dialog-titel', 'der Dialogtitel („Neue Gruppe“)'],
  ['components/ui/DkCard.vue', '.dk-ui-card-titel', 'der Kartentitel'],
]

for (const [datei, selektor, was] of KOMPONENTEN) {
  test(`DEV-3 · ${was} nutzt die Textfarbe der Tokens`, () => {
    const text = read(datei)
    const regel = regeln(text).find((r) => r.selektor === selektor)
    assert.ok(regel, `${datei}: Regel ${selektor} vorhanden`)
    const farbwerte = farben(regel.rumpf)
    assert.ok(farbwerte.length > 0, `${datei}: ${selektor} setzt eine Farbe`)
    for (const wert of farbwerte) {
      assert.ok(!FESTE_FARBE.test(wert), `${datei}: ${selektor} hat eine feste Farbe (${wert})`)
      assert.ok(nurTokens(wert), `${datei}: ${selektor} nutzt nur var(--…) (${wert})`)
    }
    assert.match(regel.rumpf, /color:\s*var\(--(dk-)?text\)/,
      `${datei}: ${selektor} → color: var(--text)`)
  })
}

test('DEV-3 · .dk-modal und .dk-ui-dialog nutzen für Fläche und Schrift nur Tokens', () => {
  const index = regeln(read('index.css'))
  const dialogs = regeln(read('components/ui/DkDialog.vue'))
  const alle = [...index, ...dialogs].filter((r) => /(^|[\s,])\.dk-(modal|ui-dialog)([\s,{:.-]|$)/.test(r.selektor))
  assert.ok(alle.length > 0, 'Regeln für .dk-modal/.dk-ui-dialog gefunden')
  const fehler = []
  for (const { selektor, rumpf } of alle) {
    for (const wert of farben(rumpf)) {
      if (FESTE_FARBE.test(wert)) fehler.push(`${selektor} → ${wert}`)
    }
  }
  assert.deepEqual(fehler, [], 'Dialoge dürfen nur Token-Farben tragen:\n' + fehler.join('\n'))
})

// ── 3 · Eingabefelder in Dialogen ──────────────────────────────────────────
test('DEV-3 · .dk-ui-eingabe hat eine Gestalt aus Tokens (kein weißes Browserfeld)', () => {
  const regel = regeln(read('index.css')).find(
    (r) => r.selektor.split(',').map((s) => s.trim()).includes('.dk-ui-eingabe')
      && /background:/.test(r.rumpf),
  )
  assert.ok(regel, 'index.css: .dk-ui-eingabe steht in einer Farbregel')
  assert.match(regel.rumpf, /background:\s*var\(--dk-surface\)/,
    '.dk-ui-eingabe → background: var(--dk-surface)')
  assert.match(regel.rumpf, /color:\s*var\(--dk-text\)/,
    '.dk-ui-eingabe → color: var(--dk-text)')
  // UX1a: die Breite kommt aus --rahmen-breite (1px) statt als Rohwert.
  assert.match(regel.rumpf, /border:\s*(?:var\(--rahmen-breite\)|1px) solid var\(--dk-border\)/,
    '.dk-ui-eingabe → border aus Token')
})

// Review DEV-3 (1): OP-HANDY-14 hebt Felder am Touchgerät auf 16 px, damit
// iOS-Safari beim Antippen nicht hineinzoomt. Eine spätere Regel mit gleicher
// Spezifität und eigener font-size würde das still wieder aushebeln.
const TOUCH_MINDESTGROESSE = 16

test('DEV-3 · OP-HANDY-14 bleibt wirksam: am Touchgerät ≥16 px, keine spätere Überschreibung', () => {
  // Alle Regeln, die eine Schriftgröße für ein Feld setzen — in Quellreihenfolge.
  const feldSchrift = []
  for (const { selektor, rumpf, bedingungen } of regeln(read('index.css'))) {
    const treffer = rumpf.match(/(^|[;\s])font-size\s*:\s*([^;]+)/)
    if (!treffer) continue
    const nenntFeld = /(^|[\s,>])(input|select|textarea|\.dk-ui-eingabe|\.dk-form-input|\.dk-form-select)\b/
    if (!nenntFeld.test(selektor)) continue
    feldSchrift.push({
      selektor,
      groesse: treffer[2].trim(),
      touch: bedingungen.some((b) => TOUCH_MEDIA.test(b)),
    })
  }
  const touch = feldSchrift.filter(
    (r) => r.touch && r.selektor.split(',').map((s) => s.trim()).includes('.dk-ui-eingabe'),
  )
  assert.ok(touch.length > 0, 'index.css: Touch-Regel für Felder vorhanden')
  assert.equal(parseFloat(touch[touch.length - 1].groesse), TOUCH_MINDESTGROESSE,
    `Touch-Regel setzt ${TOUCH_MINDESTGROESSE} px (gefunden: ${touch[touch.length - 1].groesse})`)

  // Nur die Touch-Regel darf `.dk-ui-eingabe` eine Schriftgröße geben —
  // gleich an welcher Stelle des Stylesheets.
  const konkurrenz = regeln(read('index.css')).filter((r) => {
    if (!/font-size\s*:/.test(r.rumpf)) return false
    if (r.bedingungen.some((b) => TOUCH_MEDIA.test(b))) return false
    return r.selektor.split(',').map((s) => s.trim()).includes('.dk-ui-eingabe')
  })
  assert.deepEqual(konkurrenz.map((r) => `${r.selektor} → ${r.rumpf.match(/font-size\s*:[^;]*/)[0]}`), [],
    'Nur die Touch-Regel (OP-HANDY-14) darf die Schriftgröße von `.dk-ui-eingabe` bestimmen:\n'
      + konkurrenz.map((r) => r.selektor).join('\n'))
})

// Review DEV-3 (2): Die Farbregel sollte nicht die Form app-weiter Felder
// mitbestimmen. Form (Breite, Innenabstand, Radius) nur im Dialog-Kontext.
test('DEV-3 · .dk-ui-eingabe bekommt Form nur im Dialog, nicht app-weit', () => {
  // DEV-4 hat diese Grenze ABSICHTLICH aufgehoben: Das Profil benutzt
  // `.dk-ui-eingabe` auch außerhalb von Dialogen, dort stand das Feld ohne
  // Radius/Innenabstand neben runden Auswahlfeldern. Die Grundform kommt
  // jetzt aus den Tokens; der Dialog-Block bleibt bestehen.
  // Geprüft wird deshalb: die Dialog-Regel existiert weiterhin, und KEIN
  // Selektor der Grundform schränkt sie auf eine einzelne Seite ein.
  const betroffen = regeln(read('index.css')).filter((r) =>
    r.selektor.split(',').some((s) => s.trim().endsWith('.dk-ui-eingabe'))
      && /(^|[;\s])(width|padding|border-radius)\s*:/.test(r.rumpf),
  )
  assert.ok(
    betroffen.some((r) => /^\.dk-(modal|ui-dialog)\s+\.dk-ui-eingabe$/.test(r.selektor.split(',')[0].trim())),
    'index.css: Dialog-Regel für die Feldform vorhanden',
  )
  const fehler = []
  for (const r of betroffen) {
    for (const s of r.selektor.split(',').map((x) => x.trim()).filter((x) => x.endsWith('.dk-ui-eingabe'))) {
      // Erlaubt: die Grundform selbst und ihre beiden Dialog-Fassungen.
      if (!/^(\.dk-ui-eingabe|\.dk-(modal|ui-dialog)\s+\.dk-ui-eingabe)$/.test(s)) {
        fehler.push(`${r.selektor} → ${s}`)
      }
    }
  }
  assert.deepEqual(fehler, [],
    'Form von .dk-ui-eingabe nur über die Grundform und den Dialog-Kontext '
      + '(.dk-modal/.dk-ui-dialog), nicht seitenweise:\n' + fehler.join('\n'))
})

// ── 4 · keine festen Farb-Fallbacks in var(--…, #…) ────────────────────────
function quelldateien(verzeichnis) {
  const pfad = new URL(verzeichnis, WURZEL)
  if (!existsSync(pfad)) return []
  const ergebnis = []
  for (const name of readdirSync(pfad)) {
    if (name === 'node_modules') continue
    const kind = new URL(name, pfad)
    if (statSync(kind).isDirectory()) ergebnis.push(...quelldateien(verzeichnis + name + '/'))
    else if (name.endsWith('.vue') || name.endsWith('.css')) ergebnis.push(verzeichnis + name)
  }
  return ergebnis
}

test('DEV-3 · kein fester Farbwert als var()-Fallback', () => {
  const FALLBACK = /var\(\s*--[\w-]+\s*,\s*(#[0-9a-fA-F]{3,8}|rgba?\s*\(|hsla?\s*\()/
  const fehler = []
  for (const datei of quelldateien('')) {
    const text = readFileSync(new URL(datei, WURZEL), 'utf8')
    text.split('\n').forEach((zeile, i) => {
      // tokens.css ist die einzige Quelle für Rohwerte.
      if (datei === 'tokens.css') return
      if (!FALLBACK.test(zeile)) return
      // Kommentarzeilen (auch mehrzeilige) beschreiben das Verbot nur.
      const ohneKommentar = zeile.replace(/\/\*.*?\*\//g, '')
      if (/^\s*(\/\*|\*)/.test(ohneKommentar) || ohneKommentar.trim() === '') return
      fehler.push(`${datei}:${i + 1} → ${zeile.trim()}`)
    })
  }
  assert.deepEqual(
    fehler, [],
    'Feste Farb-Fallbacks verboten — der Fallback greift im Dunkelmodus hell:\n' + fehler.join('\n'),
  )
})

console.log('DEV-3: Wächter für Dialoge/Karten bestanden')
