import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { kontrast, AA_KONTRAST } from '../src/shared/kachelfarbe.mjs'

/**
 * UX-K1 — Kontrast über die Tokens (Nachmessung 25.11.: 242 Verstöße < 4,5:1).
 *
 * Die Nachmessung fand 72 Muster; fast alle hatten EINE Ursache im Token, nicht
 * auf der Seite:
 *
 *   • `--subtle` (#6b7088 hell / #6a7199 dunkel) erfüllte AA nur auf Weiß —
 *     auf `--surface-2` und `--surface-hover` waren es 4,43 bzw. 3,55:1.
 *     Betroffen: Tabellenkopf, Wochenzahl, leere Tabellenkacheln, „⋯“,
 *     „Strg K“, Brotkrumen-Trenner (31 der 242 Verstöße allein im Dunkelmodus).
 *   • `--accent` (#c9952f) war als SCHRIFT auf Weiß 2,57:1 — aktiver Reiter,
 *     Handy-Fußleiste, „Aktiv“-Abzeichen.
 *   • Die Avatar-Paare: Paar 2 war als einziges DUNKEL, die Schrift kam aber
 *     aus `--text` (im Dunkelmodus hell) → 1,35 / 2,12:1.
 *   • Status-Schriften knapp unter AA (#2f7d4f 4,42:1, #a86a12 3,96:1).
 *   • `--primary-ink` auf einer eigenen Navy-Fläche (Gruppenkreis) im
 *     Dunkelmodus fast schwarz → 2,44:1.
 *
 * Der Wächter rechnet die Zusage nach — nicht die Zahlen. Er liest die Tokens
 * aus `tokens.css`, löst `var(--…)` in BEIDEN Themes auf und prüft die
 * Farbpaare, die die Bausteine wirklich zusammenbringen. Damit fällt auch ein
 * späterer Rückbau auf (Gegenprobe unten).
 */

const root = new URL('../', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

/**
 * Regeln eines Blattes als {selektor, rumpf, medien} — Reihenfolge bleibt
 * erhalten. `medien` ist die umschließende `@media`-Bedingung ('' = keine).
 * Verschachtelte Blöcke werden über eine Tiefenzählung verfolgt: eine flache
 * Regex über `{…}` verwechselt den `@media print`-Block mit einer Regel und
 * lässt ihn in der Kaskade gewinnen (er steht zuletzt).
 */
function regeln(css) {
  // `@import "…";` steht vor der ersten Regel und endet mit `;` — ohne diese
  // Zeile landete der Import-Text im Selektor der ersten `:root`-Regel (und
  // die Farbskala §1 wäre unsichtbar).
  const text = css.replace(/\/\*[\s\S]*?\*\//g, '').replace(/@import[^;]*;/g, '')
  const ergebnis = []
  let tiefe = 0
  let medien = ''
  let selektorAb = 0
  for (let i = 0; i < text.length; i += 1) {
    const zeichen = text[i]
    if (zeichen === '{') {
      const kopf = text.slice(selektorAb, i).trim()
      if (tiefe === 0) {
        // REVIEW UX-K1: `@keyframes` enthält selbst Regeln (`0% { … }`). Wer
        // ihn wie eine normale Regel behandelt, landet nach seinem ersten `}`
        // im Inneren und liest den REST DER DATEI falsch — genau das ließ
        // `.diakonos-toast-aktion` aus der Regel-Liste verschwinden und den
        // Quelltext-Wächter blind werden. Block ganz überspringen.
        if (kopf.startsWith('@keyframes') || kopf.startsWith('@font-face')) {
          let klammern = 1
          let j = i + 1
          while (j < text.length && klammern > 0) {
            if (text[j] === '{') klammern += 1
            else if (text[j] === '}') klammern -= 1
            j += 1
          }
          i = j - 1
          selektorAb = j
          continue
        }
        if (kopf.startsWith('@media')) {
          medien = kopf
          tiefe += 1
          selektorAb = i + 1
          continue
        }
        // Regel auf oberster Ebene: Rumpf bis zur schließenden Klammer.
        // REVIEW UX-K1b: Der PARSER war die eigentliche Lücke. Ein naives
        // `indexOf('}')` endet am ERSTEN `}` — schachtelt eine Regel ein
        // `@media`/`@supports` (in Schublade, Fußleiste, Kalender mehrfach der
        // Fall), „gewinnt“ die geschachtelte Regel gegen die äußere und der
        // Rest des Blocks (Fläche, Schrift) fällt weg. Deshalb bis zur
        // passenden Klammer zählen und auch ein `;` im Rumpf zulassen.
        let ende = i + 1
        let klammern = 1
        while (ende < text.length && klammern > 0) {
          if (text[ende] === '{') klammern += 1
          else if (text[ende] === '}') klammern -= 1
          ende += 1
        }
        ende -= 1
        ergebnis.push({ selektor: kopf, rumpf: text.slice(i + 1, ende), medien })
        i = ende
        selektorAb = ende + 1
        continue
      }
      tiefe += 1
      continue
    }
    if (zeichen === '}') {
      tiefe -= 1
      if (tiefe === 0) medien = ''
      selektorAb = i + 1
    }
  }
  return ergebnis
}

/**
 * Die Token einer Theme-Wurzel: :root (hell) bzw. der Dunkel-Block.
 * `:root` und `[data-theme="dark"]` stehen MEHRFACH im Blatt (Farbskala,
 * Semantik, Aliase, Druck) — die Regel „letzte Deklaration gewinnt“ gilt hier
 * NICHT: der `@media print`-Block wird am Bildschirm nie ausgewertet. Er wird
 * deshalb übersprungen (sein Selektor beginnt mit `@`), nicht herausgeschnitten
 * — ein Ausschneiden per Klammernzählung verrutschte an den verschachtelten
 * Regeln und riss die halbe Datei mit.
 */
function tokenSatz(css, dunkel) {
  const werte = {}
  for (const r of regeln(css)) {
    // Nur was am BILDSCHIRM gilt: `@media print` steht zuletzt im Blatt und
    // würde die Theme-Werte sonst mit der hellen Fassung überschreiben.
    if (r.medien) continue
    const teile = r.selektor.split(',').map((s) => s.trim())
    const treffer = teile.find((s) =>
      dunkel ? /^(\[data-theme="dark"\]|:root\[data-theme="dark"\])$/.test(s)
        : s === ':root')
    if (!treffer) continue
    for (const m of r.rumpf.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
      werte[m[1]] = m[2].trim()
    }
    // Kurzform `--a: x; --b: y;` in EINER Zeile steht in tokens.css mehrfach
    // für die Avatar-Paare — die Deklarationen oben erfassen sie, weil `;`
    // das Trennzeichen ist. Ein `/* Kommentar */` AM ZEILENENDE ist oben schon
    // entfernt; ein Rest (z. B. `#fff   /* … */`) wäre keine Hex-Farbe mehr.
  }
  return werte
}

/**
 * `var(--x)` rekursiv auflösen; was keine Hex-Farbe ist, bleibt als Text.
 * Die ROH-Skala (`--dk-navy-*`, `--dk-ink-*`, `--dk-warm-*` …) steht nur in
 * `:root` und ist themenunabhängig — fehlt ein Name im Dunkel-Satz, gilt der
 * helle Wert (sonst bliebe jede auf die Skala zeigende Fläche leer).
 * `rgba(r,g,b,a)` (die weichen Statusflächen im Dunkelmodus) wird über
 * `unten` gemischt — eine Fläche ist erst mit ihrer Deckkraft eine Fläche.
 */
function loese(werte, name, tiefe = 0, unten = null) {
  if (tiefe > 8) return ''
  const samen = werte[name] !== undefined ? werte : HELL
  const wert = samen[name]
  if (wert === undefined) return ''
  const m = wert.match(/^var\((--[\w-]+)\)$/)
  if (m) return loese(samen, m[1], tiefe + 1, unten)
  if (!unten) return wert
  const a = wert.match(/^rgba?\(\s*([\d.]+)\s*[,\s]\s*([\d.]+)\s*[,\s]\s*([\d.]+)\s*(?:[,\/]\s*([\d.]+)\s*)?\)$/)
  if (!a) return wert
  const alpha = a[4] === undefined ? 1 : Number(a[4])
  const bg = unten.replace('#', '')
  const misch = [0, 1, 2].map((i) => Math.round(
    Number(a[1 + i]) * alpha + parseInt(bg.slice(i * 2, i * 2 + 2), 16) * (1 - alpha)))
  return '#' + misch.map((v) => v.toString(16).padStart(2, '0')).join('')
}

function farbe(werte, name, unten = null) {
  const wert = loese(werte, name, 0, unten)
  assert.match(wert, /^#[0-9a-fA-F]{6}$/, `${name} ist keine Hex-Farbe (${wert})`)
  return wert
}

const tokens = lies('src/diakonos/tokens.css')
const HELL = tokenSatz(tokens, false)
const DUNKEL = tokenSatz(tokens, true)

/**
 * Alle Flächen, auf denen Schrift steht. `--dk-warm-200` gehört NICHT dazu: es
 * ist `--line-strong`, also eine Rahmen-/Trennfarben-Stufe und kein
 * Hintergrund einer Schriftfläche.
 */
const FLAECHEN = {
  hell: ['--bg', '--bg-subtle', '--surface', '--surface-2', '--surface-hover', '--accent-soft'],
  dunkel: ['--bg', '--bg-subtle', '--surface', '--surface-2', '--surface-hover', '--side-bg', '--side-bg2'],
}

/**
 * REVIEW UX-K1: Die DUNKLEN Flächen, auf denen im hellen Theme ebenfalls
 * Schrift steht — die Seitenleiste (in beiden Themes navy), ihr zweiter Ton
 * (Toast, Schublade) und `--primary` (Markenfläche; im Dunkelmodus WEISS).
 * Hier gilt NICHT `--accent` (hell #826310: 2,55–3,08:1), sondern
 * `--accent-auf-marke` (hell #f1d391: 9,9–11,9:1).
 */
const NAVY_FLAECHEN = {
  hell: ['--side-bg', '--side-bg2', '--primary'],
  dunkel: ['--side-bg', '--side-bg2'], // --primary ist dunkel Weiß, s. eigener Test
}

function pruefePaar(theme, schriftName, flaecheName, zusatz = '') {
  const werte = theme === 'hell' ? HELL : DUNKEL
  const schrift = farbe(werte, schriftName)
  // Eine durchsichtige Fläche (die weichen Statusflächen im Dunkelmodus:
  // `rgba(47,125,79,.22)`) wird über die Karte gemischt, auf der sie liegt.
  const flaeche = farbe(werte, flaecheName, farbe(werte, '--surface'))
  const wert = kontrast(schrift, flaeche)
  assert.ok(wert >= AA_KONTRAST,
    `${theme}: ${schriftName} (${schrift}) auf ${flaecheName} (${flaeche}) nur ` +
    `${wert.toFixed(2)}:1${zusatz}`)
  return wert
}

// ── 1 · Die gedämpfte Schrift trägt auf JEDER Fläche ──────────────────────
test('UX-K1: --subtle erreicht AA auf jeder Fläche, hell und dunkel', () => {
  for (const theme of ['hell', 'dunkel']) {
    for (const flaeche of FLAECHEN[theme]) {
      pruefePaar(theme, '--subtle', flaeche)
    }
  }
})

test('UX-K1: --muted und --text tragen ebenfalls auf jeder Fläche', () => {
  for (const theme of ['hell', 'dunkel']) {
    for (const name of ['--muted', '--text']) {
      for (const flaeche of FLAECHEN[theme]) pruefePaar(theme, name, flaeche)
    }
  }
})

test('UX-K1: Gegenprobe — die alten Werte verfehlten AA (Test wäre sonst sinnlos)', () => {
  // REVIEW UX-K1: Die Fläche kommt aus dem TOKEN, nicht als Hex-Konstante —
  // sonst prüfte der Test nur seine eigene Zahl und nicht die Zusage.
  const hellFlaeche = farbe(HELL, '--surface-2')
  const dunkelFlaeche = farbe(DUNKEL, '--surface-2')
  assert.ok(kontrast('#6b7088', hellFlaeche) < AA_KONTRAST, 'alter heller Wert war schon konform')
  assert.ok(kontrast('#6a7199', dunkelFlaeche) < AA_KONTRAST, 'alter dunkler Wert war schon konform')
  // Und der NEUE Wert trägt dort (sonst wäre die Gegenprobe inhaltslos).
  assert.ok(kontrast(farbe(HELL, '--subtle'), hellFlaeche) >= AA_KONTRAST)
  assert.ok(kontrast(farbe(DUNKEL, '--subtle'), dunkelFlaeche) >= AA_KONTRAST)
})

// ── 2 · Der Akzent ist Schrift UND Fläche ─────────────────────────────────
test('UX-K1: --accent trägt als Schrift auf jeder HELLEN Fläche', () => {
  // REVIEW UX-K1: Auf den dunklen Flächen (Seitenleiste, Toast, Logo,
  // --primary) trägt --accent seit der Abdunklung NICHT mehr — dort steht
  // --accent-auf-marke (eigener Test unten). FLAECHEN enthält deshalb nur
  // noch helle Schriftgründe; --side-bg/--side-bg2 im Dunkelmodus sind
  // dort schon immer die Ausnahme (dunkel ist der Akzent gold-300 = 9–10:1).
  for (const theme of ['hell', 'dunkel']) {
    for (const flaeche of FLAECHEN[theme]) pruefePaar(theme, '--accent', flaeche)
  }
})

test('UX-K1 (Review): --accent-auf-marke trägt auf JEDER dunklen Markenfläche', () => {
  // Die Ursache: der helle Akzent ist als Schrift abgedunkelt (#826310) und
  // stand auf der Seitenleiste bei 3,08:1, auf --primary bei 2,55:1. Für
  // Schrift auf dunklen Flächen gibt es --accent-auf-marke.
  for (const theme of ['hell', 'dunkel']) {
    for (const flaeche of NAVY_FLAECHEN[theme]) {
      pruefePaar(theme, '--accent-auf-marke', flaeche)
    }
  }
  // --primary ist im Dunkelmodus WEISS (dort ist Weiß der Markenton) — der
  // Akzent darauf ist gold-100 auf Weiß; das prüft derselbe Aufruf nicht,
  // deshalb hier ausdrücklich als Fläche mit --primary-ink als Schrift.
  pruefePaar('dunkel', '--primary-ink', '--primary')
})

/**
 * REVIEW UX-K1b, Punkt 6: `FLAECHEN.hell` kennt die dunklen Schriftgründe gar
 * nicht — der helle Satz prüfte `--accent` nur auf Weiß und Grau. Die
 * Seitenleiste, ihr zweiter Ton und `--primary` stehen im hellen Theme
 * ebenfalls als Fläche da (und im Dunkelmodus sind es dieselben Namen, nur
 * anders belegt). Deshalb werden sie hier mitgeprüft — mit dem Token, das
 * dort als Schrift bestimmt ist.
 */

/** Flächen, auf denen `--accent-auf-marke` NICHT als Schrift gilt. */
const HELLE_SCHRIFTFLAECHEN = ['--bg', '--bg-subtle', '--surface', '--surface-2', '--surface-hover', '--accent-soft']

test('UX-K1b: --side-bg, --side-bg2 und --primary stehen auch im hellen Satz', () => {
  for (const name of ['--side-bg', '--side-bg2', '--primary']) {
    assert.ok(HELL[name] !== undefined, `${name} fehlt im hellen Token-Satz`)
    // Die Fläche ist wirklich dunkel — sonst prüfte der Test unten ins Leere.
    assert.ok(kontrast(farbe(HELL, name), '#ffffff') >= AA_KONTRAST,
      `${name} (${farbe(HELL, name)}) ist im hellen Theme keine dunkle Fläche`)
  }
})

test('UX-K1b: --accent-auf-marke hält auf JEDER dunklen Schriftfläche >= 4,5:1 (hell)', () => {
  // Die Review-Auflage: der Wert muss als SCHRIFT (nicht als Fläche) auf den
  // Navy-Gründen des hellen Themes tragen — Sidebar, Toast (--side-bg2),
  // Logo/Monogramm (--side-bg) und --primary.
  for (const flaeche of ['--side-bg', '--side-bg2', '--primary']) {
    const wert = pruefePaar('hell', '--accent-auf-marke', flaeche)
    assert.ok(wert >= AA_KONTRAST, `hell: --accent-auf-marke auf ${flaeche} nur ${wert.toFixed(2)}:1`)
  }
  // Und es ist die einzige Marken-Schriftstufe, die das schafft: --accent
  // selbst fällt dort durch (3,08 bzw. 2,55:1) — genau der Review-Befund.
  for (const flaeche of ['--side-bg', '--side-bg2', '--primary']) {
    assert.ok(kontrast(farbe(HELL, '--accent'), farbe(HELL, flaeche)) < AA_KONTRAST,
      `hell: --accent auf ${flaeche} wäre inzwischen konform — Test anpassen`)
  }
})

test('UX-K1b: auf hellen Flächen bleibt --accent-auf-marke unzulässig (nur Navy-Schrift)', () => {
  // Spiegelt den Quelltext-Wächter auf der WERT-Ebene: das helle Gold
  // (#f1d391) ist als Schrift auf Weiß/den hellen Gründen nicht lesbar.
  for (const flaeche of HELLE_SCHRIFTFLAECHEN) {
    const wert = kontrast(farbe(HELL, '--accent-auf-marke'), farbe(HELL, flaeche))
    assert.ok(wert < AA_KONTRAST,
      `hell: --accent-auf-marke auf ${flaeche} trägt ${wert.toFixed(2)}:1 — dann gehört es dort nicht hin`)
  }
})

test('UX-K1b: --side-text trägt auf der Seitenleiste (hell und dunkel)', () => {
  // REVIEW UX-K1b: Die Leisten-Schrift ist ein EIGENES Token und stand bisher
  // in keiner Prüfung. `--warn` gehört NICHT dazu: es ist eine Statusfarbe für
  // Karten (dort eigener Test) und steht als Schrift nirgends auf der Leiste
  // (geprüft: die Leisten-Bausteine nehmen --dk-sb-text*, #fff oder die
  // Akzentstufe). Eine Prüfung „--warn auf Navy“ hätte einen Verstoß erfunden.
  for (const theme of ['hell', 'dunkel']) {
    for (const flaeche of ['--side-bg', '--side-bg2']) pruefePaar(theme, '--side-text', flaeche)
  }
  for (const flaeche of ['--side-bg', '--side-bg2']) pruefePaar('hell', '--side-text-muted', flaeche)
})

test('UX-K1b: --focus-ring-side ist auf beiden Navy-Gründen sichtbar (>= 3:1, hell und dunkel)', () => {
  for (const theme of ['hell', 'dunkel']) {
    for (const flaeche of ['--side-bg', '--side-bg2']) {
      const werte = theme === 'hell' ? HELL : DUNKEL
      const wert = kontrast(farbe(werte, '--focus-ring-side'), farbe(werte, flaeche))
      assert.ok(wert >= 3, `${theme}: --focus-ring-side auf ${flaeche} nur ${wert.toFixed(2)}:1`)
    }
  }
})

test('UX-K1 (Review): der abgedunkelte Akzent wäre auf Navy NICHT lesbar', () => {
  // Gegenprobe zur Ursache: genau dieser Fall (--accent auf der Leiste) ist
  // der Grund für --accent-auf-marke. Sie gilt nur für das HELLE Theme — im
  // Dunkelmodus IST der Akzent gold-300 und trägt auf Navy (9–10:1); dort
  // ist --accent-auf-marke (gold-100) nur die feinere Stufe. Fällt die
  // Zusicherung, ist der helle Akzent wieder lesbar — dann darf der Test weg.
  for (const flaeche of NAVY_FLAECHEN.hell) {
    const wert = kontrast(farbe(HELL, '--accent'), farbe(HELL, flaeche))
    assert.ok(wert < AA_KONTRAST,
      `hell: --accent auf ${flaeche} trägt jetzt ${wert.toFixed(2)}:1 — ` +
      '--accent-auf-marke ist damit nicht mehr nötig, Test anpassen')
  }
})

test('UX-K1: --accent trägt als FLÄCHE mit der Akzent-Schrift', () => {
  for (const theme of ['hell', 'dunkel']) {
    pruefePaar(theme, '--marke-weiss-ink', '--accent-flaeche', ' (Schrift auf der Akzentfläche)')
  }
  // Widerlegt: der alte Ton #c9952f mit Weiß = 2,68:1, und im Dunkelmodus
  // war die Akzent-Schrift `--dk-brand-800` (hell) auf gold-300 = 1,36:1.
  // REVIEW UX-K1: die Flächen sind die ECHTEN Tokenwerte, nicht Hex-Kopien.
  assert.ok(kontrast('#c9952f', farbe(HELL, '--marke-weiss-ink')) < AA_KONTRAST,
    'der alte Akzent bestand mit Weiß schon')
  assert.ok(kontrast('#d6dcea', farbe(DUNKEL, '--accent-flaeche')) < AA_KONTRAST,
    'der alte Dunkelwert bestand schon')
})

test('UX-K1: die Akzent-Balken tragen als Fläche >= 3:1 (WCAG 1.4.11)', () => {
  for (const theme of ['hell', 'dunkel']) {
    const werte = theme === 'hell' ? HELL : DUNKEL
    for (const name of ['--accent-flaeche', '--accent-leiste']) {
      for (const flaeche of FLAECHEN[theme]) {
        const wert = kontrast(farbe(werte, name), farbe(werte, flaeche))
        assert.ok(wert >= 3, `${theme}: ${name} auf ${flaeche} nur ${wert.toFixed(2)}:1`)
      }
    }
  }
})

test('UX-K1: --accent-auf-marke liest sich auf der dunklen Seitenleiste', () => {
  // Der Akzent auf der (in beiden Themes dunklen) Leiste — Schublade, die
  // Marke im Marker. Die Leiste ist eine EIGENE dunkle Fläche, nicht --surface.
  for (const theme of ['hell', 'dunkel']) {
    const werte = theme === 'hell' ? HELL : DUNKEL
    for (const flaeche of ['--side-bg', '--side-bg2']) {
      const wert = kontrast(farbe(werte, '--accent-auf-marke'), farbe(werte, flaeche))
      assert.ok(wert >= AA_KONTRAST,
        `${theme}: --accent-auf-marke auf ${flaeche} nur ${wert.toFixed(2)}:1`)
    }
  }
})

// ── 2b · Quelltext-Wächter: auf Navy-Flächen steht nicht var(--accent) ────
/**
 * Die Regel, die die Nachbesserung erzwingt: `--accent` ist im hellen Theme
 * Schrift auf HELLEN Flächen. Wo der Grund navy ist (Seitenleiste, Toast,
 * Logo-Monogramm, --primary), gehört `--accent-auf-marke` hin.
 *
 * Der Wächter muss ZWEI Formen sehen:
 *   1. Die Regel setzt Navy-Hintergrund UND Schrift in einem Rumpf.
 *   2. Die Schrift steht in einer UNTERGEORDNETEN Regel (`.diakonos-toast`
 *      trägt `--side-bg`, `.diakonos-toast-aktion` setzt nur die Schrift und
 *      erbt die Fläche). Deshalb wird je Regel geprüft, ob die Fläche im
 *      eigenen Rumpf ODER in einem Vorfahren-Selektor derselben Datei steht
 *      (`.a` ist Vorfahre von `.a.b`, `.a > .b`, `.a .b`, `.a:hover .b`).
 *
 * Zurückhaltend: nur `color` in der Rolle „Schrift" — `background`,
 * `border` und `box-shadow` sind Flächen und dürfen `--accent` führen.
 */
const NAVY_GRUENDE = [
  'var(--side-bg)', 'var(--side-bg2)', 'var(--dk-sb-bg)', 'var(--dk-sb-bg2)',
  'var(--primary)', 'var(--marke-flaeche)',
]

/** Klassen-/ID-Namen eines Selektors (ohne Pseudo-Klassen und Attributteile). */
function namen(selektor) {
  return [...selektor.matchAll(/\.([\w-]+)|#([\w-]+)/g)].map((m) => m[1] || m[2])
}

/**
 * Steht `name` auf oder unter einem Navy-Träger? Ein Element INNERHALB eines
 * Navy-Behälters erbt dessen Fläche, ohne dass der Selektor das ausdrückt
 * (`.diakonos-toast-aktion` in `.diakonos-toast`, `.dk-sb-admin-toggle.is-on`
 * in `.dk-sidebar`). Drei Wege:
 *   1. der Name selbst trägt Navy,
 *   2. BEM: ein Navy-Name ist Präfix (`toast` ⊂ `toast-aktion`),
 *   3. BEHÄLTER: der Selektor läuft unter einem bekannten Leisten-Container.
 *
 * REVIEW UX-K1b: Punkt 3 war die Lücke dieser Funktion. Sie kannte die
 * Behälter nur als `Set` der Datei, in der sie definiert sind — stand die
 * Fläche in einer ANDEREN Datei (`index.css` `.dk-sidebar`,
 * `KronosSidebar.vue` `.kronos-sidebar`), war der Träger unsichtbar. Jetzt
 * kommen die Behälter aus ALLEN geprüften Dateien; die Präfixe sind aus den
 * echten Leisten-Klassen abgeleitet und um die Markenflächen-Bezeichner
 * ergänzt.
 */
const NAVY_BEHAELTER = ['dk-sidebar', 'kronos-sidebar', 'diakonos-toast', 'dk-sb-nav', 'dk-sb-foot']
// Präfixe aus den Behälternamen ableiten (`.toast-aktion` in `.diakonos-toast`,
// `.dk-sb-nav` in `.dk-sidebar`) plus die Bausteine, die NICHT nach ihrem
// Behälter heißen (`.dk-nav-item` in `.dk-sidebar`).
const NAVY_PRAEFIXE = [...new Set([...NAVY_BEHAELTER.flatMap((b) => [b.split('-').slice(1).join('-'), b]),
  'dk-nav-item', 'dk-nav-badge'])]

function liegtAufNavy(name, navyNamen) {
  if (navyNamen.has(name)) return true
  for (const n of navyNamen) {
    if (name.startsWith(`${n}-`) || name.startsWith(`${n}__`)) return true
  }
  return false
}

/**
 * Liegt der Name unter einem Navy-BEHÄLTER (Sidebar, Schublade, Toast,
 * Fußleiste, Kronos-Leiste)? REVIEW UX-K1b: Das ist die STRIKTE Stufe — die
 * Behälter-Fläche wird nur vererbt, wenn niemand dazwischen etwas anderes
 * malt. Deshalb wird sie nur dort herangezogen, wo der Selektor nicht schon
 * selbst eine Fläche setzt (siehe Test: „is-active“ trägt selbst --primary).
 */
function unterNavyBehaelter(name, navyNamen) {
  // REVIEW UX-K1b: Die Prüfung fragt NICHT „hat dieser Name selbst eine
  // Navy-Regel“, sondern „gehört dieser Name zur Leiste“. Der Anlass war
  // Punkt 3: `.dk-sb-admin-toggle.is-on` liegt in `.dk-sidebar`, hat aber
  // keine eigene Fläche — die frühere Fassung übersprang es und ließ die
  // Mutation grün. Deshalb zählt hier: existiert im Blatt überhaupt ein
  // Navy-Behälter, und ist der Name einer seiner Bausteine (gleicher Name,
  // `behälter-…`, `…-behälter`) oder einer der Leisten-Kerne, deren Kinder
  // (`dk-nav-badge` in `dk-nav-item` in `dk-sb-nav`).
  if (!NAVY_BEHAELTER.some((b) => navyNamen.has(b))) return false
  // `.dk-sb-admin-toggle` ist kein Präfix-Kind von `.dk-sidebar`, sondern ein
  // eigenständiger Baustein IM Blatt — deshalb zählt auch der bloße
  // `sb-`-Stamm, den die Seitenleisten-Bausteine teilen.
  const STAEM = ['sb', 'nav', 'toast']
  const KERN = ['dk-nav', 'dk-sb-nav', 'dk-sb-foot', 'dk-nav-item', 'toast', 'diakonos-toast']
  const passt = (teil, ganz) => teil === ganz || teil.startsWith(`${ganz}-`) || teil.startsWith(`${ganz}__`)
  const baustein = (n) => STAEM.some((s) => passt(n, s) || passt(n, `dk-${s}`))
  for (const b of NAVY_BEHAELTER) {
    if (navyNamen.has(b) && (passt(name, b) || passt(b, name))) return true
  }
  return KERN.some((k) => passt(name, k)) || baustein(name)
}
/**
 * REVIEW UX-K1b: die zweite Form von „Navy-Grund“ ist der ABDUNKLER
 * (`background: color-mix(in oklch, var(--dk-navy-900) 45%, transparent)`) an
 * Dialogen und Schubladen. Ein Element darin steht effektiv auf Navy — der
 * Abdunkler zählt deshalb als Träger.
 *
 * NICHT als Navy-Grund zählt hier die Akzentfläche (`--accent-soft`,
 * `--accent-flaeche`): dort ist `var(--accent)` als Schrift RICHTIG und trägt
 * (4,95–5,61:1, eigener Test oben). Ein erster Anlauf zählte sie mit und
 * meldete `.dk-badge-brand` fälschlich als Verstoß — die Prüfung war zu breit,
 * nicht der Code falsch.
 */
function setztNavy(rumpf) {
  const bg = [...rumpf.matchAll(/(?:^|;)\s*background(?:-color)?\s*:\s*([^;]+)/g)].map((m) => m[1])
  return bg.some((wert) => NAVY_GRUENDE.slice(0, 4).some((g) => wert.includes(g)))
    || bg.some((wert) => {
      // Abdunkler (`color-mix(… --dk-navy-900 45%, transparent)`) färbt den
      // Grund der Kinder. Eine DECKENDE Navy-Fläche (`rgba(0,5,31,.85)` am
      // Punkt eines aktiven Eintrags) ist dagegen die Fläche des Elements
      // selbst — der Punkt darin wird weiß gesetzt, das ist eine bewusste
      // Kombination und kein Navy-Grund für die Schrift.
      //
      // REVIEW UX-K1b (Mutationsprobe M3): `rgba(212,162,76,.12)` auf dem
      // Admin-Schalter ist ein GOLDSTICH, kein Navy — die frühere Fassung
      // fragte nur nach „rgba und irgendwo navy“ und hielt den Grünton des
      // Schalters für einen Navy-Grund. Verlangt wird deshalb: die Farbe
      // selbst ist die Navy-Skala (`--dk-navy-*` oder ein Hex der Skala).
      if (/var\(--dk-navy-\d00\)/.test(wert)) {
        const m = wert.match(/(\d{1,3})\s*%\s*,\s*transparent/)
        const a = wert.match(/rgba\([^)]*,\s*([\d.]+)\s*\)/)
        if (m) return Number(m[1]) <= 60
        if (a) return Number(a[1]) <= 0.6
        return false
      }
      return /(?:rgba?|color-mix)\([^)]*(?:0\s*,\s*5\s*,\s*31|#0{0,2}0?51f)/i.test(wert)
        && /(?:\.\d+|%|transparent)/.test(wert)
      const m = wert.match(/(\d{1,3})\s*%\s*,\s*transparent/)
      const a = wert.match(/rgba\([^)]*,\s*([\d.]+)\s*\)/)
      if (m) return Number(m[1]) <= 60
      if (a) return Number(a[1]) <= 0.6
      return false
    })
}

/** Nur die Schriftfarbe — `background`/`border`/`box-shadow` sind Flächen. */
function schriftfarben(rumpf) {
  return [...rumpf.matchAll(/(?:^|;)\s*color\s*:\s*([^;]+)/g)].map((x) => x[1].trim())
}

/**
 * Alle Regelquellen, die den Wächter interessieren: die von Hand genannten
 * Dateien PLUS jedes andere Blatt unter `src/`. REVIEW UX-K1b: Punkt 4 stand
 * in `Assistent.vue` und `seiten.css`, also in Dateien, die nur einzeln
 * eingetragen waren — eine neue Datei mit demselben Fehler wäre unsichtbar
 * geblieben. Die Handliste bleibt vorn (Fehlermeldung zuerst dort), der Rest
 * wird angehängt.
 */
function stilquellen() {
  const fest = [
    'src/diakonos/tokens.css',
    'src/diakonos/index.css',
    'src/diakonos/components/einrichtung/LogoMarke.vue',
    'src/diakonos/pages/einrichtung/Assistent.vue',
    'src/ssot/seiten.css',
  ]
  const rollend = []
  const lauf = (verz) => {
    for (const e of readdirSync(new URL(verz, root), { withFileTypes: true })) {
      const pfad = `${verz}${e.name}`
      if (e.isDirectory()) lauf(`${pfad}/`)
      else if (/\.(css|vue)$/.test(e.name) && !fest.includes(pfad)) rollend.push(pfad)
    }
  }
  lauf('src/')
  return [...fest, ...rollend.sort()]
}

/**
 * Eigene Fläche eines Selektors aus einer REGEL-Menge — inklusive
 * Pseudo-Kindern wie `::after`: `.dk-nav-item.is-active::before` ist ein
 * Teil von `.dk-nav-item.is-active`, dessen Fläche es zeichnet.
 */
function eigeneFlaeche(selektor, alleRegeln) {
  // REVIEW UX-K1b: Das Element hat eine eigene Fläche, wenn IRGENDEINE Regel
  // des Blattes sie ihm gibt — auch `[data-theme="dark"] …` oder
  // `.is-collapsed …` (Suffixe, die die Zierregel nicht trägt), und auch ein
  // `background` in einer ANDEREN Regel desselben Selektors.
  const teile = selektor.split(',').map((s) => s.trim())
  const teileMitFlaeche = new Set()
  for (const r of alleRegeln) {
    if (!/(?:^|;)\s*background(?:-color)?\s*:/.test(r.rumpf)) continue
    for (const s of r.selektor.split(',').map((x) => x.trim())) teileMitFlaeche.add(s)
  }
  // Ein Zier-Kind (`…::before`) gehört zu seinem Element: hat das Element eine
  // eigene Fläche, ist der Balken `background` KEIN Akzent-auf-Navy-Fall
  // (`.dk-nav-item.is-active` malt `--side-active` und fasst es ausdrücklich als
  // Ausnahme fest). Ein Textfilter auf `::before` würde die Zierregel sonst
  // mit der Elternregel verwechseln.
  const ziehtFlaeche = teile.some((t) => /::?(?:before|after)$/.test(t)
    ? teileMitFlaeche.has(t.replace(/::?(?:before|after)$/, ''))
    : teileMitFlaeche.has(t))
  return ziehtFlaeche
}

/** Der <style>-Teil einer .vue-Datei (das Template führt keine Regeln). */
function stilVon(roh, datei) {
  if (!datei.endsWith('.vue')) return roh
  return (roh.match(/<style[^>]*>([\s\S]*?)<\/style>/g) || []).join('\n')
}

/**
 * Der Grund, auf dem eine KIND-Regel (`…::before`, `…::after`) liegt, ist der
 * Grund seines Elements: `.dk-nav-item.is-active::before` zeichnet den Balken
 * auf dem aktiven Eintrag. Ist das Element navy, gilt dort ebenfalls
 * `--accent-auf-marke` (und nicht `--accent`).
 */
function elternNamen(selektor) {
  return namen(selektor.replace(/::?(?:before|after|first-line|first-letter)/g, ''))
}

/**
 * Zierflächen (`background: var(--accent)`) eines Rumpfes — Balken und
 * Unterstriche (Mutationsprobe M4: `.dk-nav-item.is-active::before`). Auf einem
 * Navy-Grund gehört dort `--accent-auf-marke` hin.
 */
function akzentflaechen(rumpf) {
  return [...rumpf.matchAll(/(?:^|;)\s*background(?:-color)?\s*:\s*var\(--(?:dk-)?accent\)\s*(?=;|$)/g)].map((m) => m[0])
}

function eigeneAkzentflaeche(selektor, alleRegeln) {
  return alleRegeln.some((r) => {
    const eigene = r.selektor.split(',').map((x) => x.trim()).includes(selektor)
    if (!eigene) return false
    const rumpf = `${r.rumpf};`
    // Der Akzent als FLÄCHE des Elements …
    if (/(?:^|;)\s*background(?:-color)?\s*:\s*var\(--(?:dk-)?accent\)\s*;/.test(rumpf)) return true
    // … oder als SCHRIFT auf einer Fläche, die ihrerseits der Akzent ist
    // (Mutationsprobe M1: `.dk-nav-badge` setzt `--accent-flaeche` und nimmt
    // `--accent` als Schrift — ohne diese Zeile blieb M1 grün).
    return /(?:^|;)\s*color\s*:\s*var\(--(?:dk-)?accent\)\s*;/.test(rumpf)
      && /(?:^|;)\s*background(?:-color)?\s*:\s*var\(--accent-(?:flaeche|leiste|soft)\)/.test(rumpf)
  })
}

// Zwei Formen des Fehlers, beide durch die Mutationsprobe belegt:
//   a) `--accent` als SCHRIFT auf einer Fläche, die selbst der Akzent ist
//      (`.dk-badge-brand` mit `--accent-soft`) — trägt 5,3:1 und ist RICHTIG;
//      falsch ist der Akzent auf einer AKZENTFLÄCHE, wenn `--marke-weiss-ink`
//      gemeint ist. Geprüft wird deshalb nur, wo der Grund aus der
//      Akzent-FLÄCHEN-Stufe kommt (`--accent-flaeche`, `--accent-leiste`).
//   b) `--accent` als ZIERFLÄCHE (Balken) auf einem Element, das auf Navy
//      steht (`.dk-nav-item.is-active::before`, M4).
/**
 * Liegt ein Element-Name in der DATEI auf einem Navy-Grund? Prüft den Namen
 * selbst (Fläche) und seine Behälter (Leisten, Meldungen). Für Zier-Regeln
 * (`…::before`) zählt das Element ohne Pseudo-Teil.
 */
function ueberNavy(name, datei) {
  const rs = regeln(stilVon(lies(datei), datei))
  const navyNamen = new Set()
  for (const r of rs) if (setztNavy(r.rumpf)) for (const n of namen(r.selektor)) navyNamen.add(n)
  return liegtAufNavy(name, navyNamen) || unterNavyBehaelter(name, navyNamen)
}

test('UX-K1b: Akzent als Schrift auf einer Akzentflaeche führt --marke-weiss-ink', () => {
  const verstoesse = []
  for (const datei of stilquellen()) {
    for (const r of regeln(stilVon(lies(datei), datei))) {
      if (!/(?:^|;)\s*background(?:-color)?\s*:\s*var\(--accent-(?:flaeche|leiste)\)/.test(r.rumpf)) continue
      for (const wert of schriftfarben(r.rumpf)) {
        if (/var\(--(?:dk-)?accent\)/.test(wert)) verstoesse.push(`${datei} → ${r.selektor}: color: ${wert}`)
      }
    }
  }
  assert.deepEqual(verstoesse, [],
    'Auf einer Akzentfläche gehört --marke-weiss-ink als Schrift, nicht --accent:\n' + verstoesse.join('\n'))
})

test('UX-K1b: Akzent als ZIERFLÄCHE auf einem Navy-Element (Balken, Unterstrich)', () => {
  const verstoesse = []
  for (const datei of stilquellen()) {
    for (const r of regeln(stilVon(lies(datei), datei))) {
      if (!akzentflaechen(r.rumpf).length) continue
      const eigeneNavy = setztNavy(r.rumpf)
      const aufNavy = eigeneNavy || elternNamen(r.selektor).some((n) => ueberNavy(n, datei))
      if (!aufNavy) continue
      verstoesse.push(`${datei} → ${r.selektor}: background: var(--accent)`)
    }
  }
  assert.deepEqual(verstoesse, [],
    'Auf einer Navy-Fläche gehört --accent-auf-marke als Balken/Unterstrich:\n' + verstoesse.join('\n'))
})

test('UX-K1 (Review): keine Regel setzt var(--accent) auf einer Navy-Fläche', () => {
  // Drei Wege auf einen Navy-Grund, in dieser Reihenfolge:
  //   1. die Regel malt die Fläche selbst (`background: var(--side-bg)`),
  //   2. sie erbt sie per BEM-Namen (`toast` ⊂ `toast-aktion`),
  //   3. sie steht unter einem Navy-BEHÄLTER (`.dk-sidebar`, `.dk-schublade`,
  //      `.diakonos-toast`, …) — aber nur, wenn sie nicht selbst eine Fläche
  //      setzt: `.ld-tab.is-active` trägt `--primary` und färbt darin das
  //      Sternchen; das ist eine bewusste Kombination, keine Vererbung.
  const verstoesse = []
  const quellen = stilquellen()
  // Nur ELEMENT-Behälter zählen als Träger: `--primary`/`--marke-flaeche` sind
  // auch Knopf- und Reiterflächen (`.ld-tab.is-active`, `.assistent-kreis`);
  // ein Element darin steht auf der Fläche, nicht auf der Marke. Die Behälter
  // sind die Leisten und Meldungen.
  const behaelter = new Set()
  for (const datei of quellen) {
    const rollen = new Map()
    for (const r of regeln(stilVon(lies(datei), datei))) {
      const bg = [...r.rumpf.matchAll(/(?:^|;)\s*background(?:-color)?\s*:\s*([^;]+)/g)].map((m) => m[1])
      // Eine Navy-Fläche ODER ein Abdunkler (`color-mix(… --dk-navy-900 …)`)
      // an einem Container: beides färbt den Grund der Kinder.
      const navy = setztNavy(r.rumpf)
      for (const n of namen(r.selektor)) rollen.set(n, rollen.get(n) || navy)
    }
    // Ein Name, der IRGENDWO eine Navy-Fläche bekommt, zählt als Träger.
    for (const [n, navy] of rollen) if (navy) behaelter.add(n)
  }
  for (const datei of quellen) {
    const regelnDerDatei = regeln(stilVon(lies(datei), datei))
    for (const r of regelnDerDatei) {
      const eigeneNavy = setztNavy(r.rumpf)
      const namenDerRegel = namen(r.selektor)
      // REVIEW UX-K1b: `behaelter` enthält nur NAVY-TRÄGER — der zweite Weg
      // (BEM-Präfix) braucht alle Namen, sonst bleibt `.dk-sb-admin-toggle`
      // unsichtbar (Mutationsprobe M3). Deshalb wird gegen die Träger-Menge UND
      // die Behälter-Menge geprüft.
      const erbtNavy = namenDerRegel.some((n) => liegtAufNavy(n, behaelter))
        || namenDerRegel.some((n) => unterNavyBehaelter(n, behaelter))
      // Die Fläche steht ggf. in einer ANDEREN Regel desselben Blattes
      // (`.dk-nav-item.is-active` malt sie, `…::before` zeichnet den Balken).
      const flaecheSetzt = eigeneFlaeche(r.selektor, regelnDerDatei)
      const imBehaelter = !flaecheSetzt && namenDerRegel.some((n) => unterNavyBehaelter(n, behaelter))
      // `zierAufNavy` zählt nur auf echten Behältern, nicht auf jeder Navy-Fläche.
      // Zierfläche (Unterstrich, Balken) auf einem Navy-Element: das Element
      // selbst trägt Navy (`.dk-nav-item.is-active`), die Fläche steht als
      // `background` in einer anderen Regel desselben Blattes
      // (`…::before`) — oder umgekehrt.
      // Zierfläche: das Element trägt Navy UND eine Familie-Regel malt den
      // Akzent (`…::before { background: var(--accent) }`), oder umgekehrt.
      const zierAufNavy = eigeneNavy && eigeneAkzentflaeche(r.selektor, regelnDerDatei)
        || eigeneAkzentflaeche(r.selektor, regelnDerDatei) && erbtNavy
      if (!eigeneNavy && !erbtNavy && !imBehaelter && !zierAufNavy) continue
      for (const wert of schriftfarben(r.rumpf)) {
        if (/var\(--(?:dk-)?accent\)/.test(wert)) {
          verstoesse.push(`${datei} → ${r.selektor}: color: ${wert}`)
        }
      }
    }
  }
  assert.deepEqual(verstoesse, [],
    'Auf einer Navy-Fläche gehört --accent-auf-marke als Schrift, nicht --accent:\n' +
    verstoesse.join('\n'))
})

test('UX-K1b: angesprungene Dunkelflächen (--primary, --marke-flaeche) führen nicht --accent als Schrift', () => {
  // Form (c) aus dem Review: `.dk-monogramm` stand mit `color: var(--accent)`
  // auf `background: var(--primary)` — ein Einzelkämpfer ohne Behälter und
  // ohne Akzentfläche, den der Wächter oben nur über die Navy-Liste sieht.
  // Hier ausdrücklich, damit ein späterer Umbau der Listen ihn nicht verliert.
  const verstoesse = []
  for (const datei of stilquellen()) {
    for (const r of regeln(stilVon(lies(datei), datei))) {
      const bg = /(?:^|;)\s*background(?:-color)?\s*:\s*var\(--(?:primary|marke-flaeche|side-bg|side-bg2)\)/.test(r.rumpf)
      if (!bg) continue
      for (const wert of schriftfarben(r.rumpf)) {
        if (/var\(--(?:dk-)?accent\)/.test(wert)) verstoesse.push(`${datei} → ${r.selektor}: color: ${wert}`)
      }
    }
  }
  assert.deepEqual(verstoesse, [], 'var(--accent) als Schrift auf einer Dunkelfläche:\n' + verstoesse.join('\n'))
})

// ── 3 · Avatare: Fläche und Schrift aus EINEM Paar ────────────────────────
test('UX-K1: jedes Avatar-Paar erreicht AA — in BEIDEN Themes', () => {
  // Entscheidend: die Paare stehen nur in §1 (:root) und gelten in beiden
  // Themes. Deshalb wird JEDES Paar in beiden Sätzen nachgerechnet.
  for (let i = 1; i <= 6; i += 1) {
    for (const theme of ['hell', 'dunkel']) {
      pruefePaar(theme, `--dk-avatar-${i}-ink`, `--dk-avatar-${i}-bg`)
    }
  }
})

test('UX-K1: kein Avatar-Paar ist im Dunkelmodus dunkel (Schrift kommt aus dem Paar)', () => {
  // Die Regression war Paar 2: dunkle Fläche + Theme-Schrift --text (dunkel
  // hell) = 1,35 / 2,12:1. Deshalb: jede Fläche ist hell genug für dunkle
  // Schrift — geprüft über `#12183a`, die dunkelste Marken-Schrift.
  for (let i = 1; i <= 6; i += 1) {
    const bg = farbe(HELL, `--dk-avatar-${i}-bg`)
    assert.ok(kontrast(bg, '#12183a') >= AA_KONTRAST,
      `--dk-avatar-${i}-bg (${bg}) ist zu dunkel für dunkle Schrift`)
  }
})

test('UX-K1: kein Avatar-Token hat ein Dunkel-Gegenstück (die Paare gelten in beiden Themes)', () => {
  for (let i = 1; i <= 6; i += 1) {
    for (const teil of ['bg', 'ink']) {
      assert.equal(DUNKEL[`--dk-avatar-${i}-${teil}`], undefined,
        `--dk-avatar-${i}-${teil} steht auch im Dunkel-Block — dann muss der Test beide Werte kennen`)
    }
  }
})

test('UX-K1: der Gruppenkreis trägt in beiden Themes', () => {
  for (const theme of ['hell', 'dunkel']) {
    pruefePaar(theme, '--dk-avatar-gruppe-ink', '--dk-avatar-gruppe-bg')
  }
})

test('UX-K1: die Avatar-Regeln setzen die Schrift aus dem PAAR, nicht aus --text', () => {
  const personen = lies('src/diakonos/components/personen/PersonenListe.vue')
  assert.match(personen, /color:\s*var\(--pz-avatar-ink/,
    'PersonenListe: der Kreis nimmt die Theme-Schrift statt der Paar-Schrift')
  assert.ok(!/\.dk-avatar\.pz-avatar\s*\{[^}]*color:\s*var\(--text\)/.test(personen),
    'PersonenListe: --text steht wieder im Avatar')
  assert.match(personen, /--pz-avatar-ink'\]:\s*ink|'--pz-avatar-ink':\s*ink/,
    'PersonenListe: avatarStil gibt die Paar-Schrift nicht weiter')

  const gruppe = lies('src/diakonos/pages/GruppeDetail.vue')
  assert.match(gruppe, /\.grup-avatar\s*\{[^}]*color:\s*var\(--dk-avatar-gruppe-ink\)/,
    'GruppeDetail: der Kreis nimmt --primary-ink statt der Paar-Schrift')
  const seite = lies('src/diakonos/pages/GruppeDetail.vue')
  assert.ok(!/\.grup-avatar\s*\{[^}]*color:\s*var\(--primary-ink\)/.test(seite),
    'GruppeDetail: --primary-ink (dunkel fast schwarz) steht wieder im Kreis')
})

// ── 4 · Status- und Abzeichen-Schriften ───────────────────────────────────
test('UX-K1: Abzeichen-Schriften erreichen AA auf ihrer weichen Fläche', () => {
  for (const theme of ['hell', 'dunkel']) {
    pruefePaar(theme, '--badge-ink-ok', '--ok-soft')
    pruefePaar(theme, '--badge-ink-warn', '--warn-soft')
    pruefePaar(theme, '--badge-ink-info', '--info-soft')
    pruefePaar(theme, '--badge-ink-warn', '--accent-soft')
  }
  // Gegenprobe: die alten Rohwerte verfehlten AA — auf den ECHTEN Flächen.
  assert.ok(kontrast('#2f7d4f', farbe(HELL, '--ok-soft')) < AA_KONTRAST, 'altes Grün bestand schon')
  assert.ok(kontrast('#a86a12', farbe(HELL, '--warn-soft')) < AA_KONTRAST, 'altes Amber bestand schon')
})

test('UX-K1: die Status-TÖNE (dk-badge-*) tragen als Schrift auf ihrer weichen Fläche', () => {
  // `.dk-badge-success` schreibt `color: var(--ok)` auf `var(--ok-soft)`.
  for (const theme of ['hell', 'dunkel']) {
    for (const [ton, flaeche] of [['--ok', '--ok-soft'], ['--err', '--err-soft'], ['--info', '--info-soft']]) {
      pruefePaar(theme, ton, flaeche)
    }
  }
})

// ── 5 · Schrift auf Akzentflächen (Marke, Zähler) ─────────────────────────
test('UX-K1: --marke-weiss-ink trägt auf jeder Akzentfläche', () => {
  for (const theme of ['hell', 'dunkel']) {
    pruefePaar(theme, '--marke-weiss-ink', '--accent-flaeche')
  }
  // Der Moderations-Zähler (Ressourcen) nahm --dk-brand-800: im Dunkelmodus
  // ist das HELL (DES-R4) → 1,36:1 auf gold-300.
  assert.ok(kontrast('#d6dcea', farbe(DUNKEL, '--accent-flaeche')) < AA_KONTRAST,
    'alter Zähler-Wert bestand schon')
})

// ── 7 · Gegenprobe: der Wächter schlägt bei einem Rückbau an ──────────────
test('UX-K1: Gegenprobe — mit den alten Werten schlägt die Rechnung an', () => {
  // Simuliert den Rückbau: heller/dunkler Grauwert und der alte Akzent.
  // REVIEW UX-K1: die Flächen sind die ECHTEN Tokenwerte (nicht Hex-Kopien) —
  // sonst prüft der Test nur seine eigene Konstante.
  const dunkelFlaeche = farbe(DUNKEL, '--surface-2')
  const hellFlaeche = farbe(HELL, '--surface-2')
  assert.ok(kontrast('#6a7199', dunkelFlaeche) < AA_KONTRAST,
    'der Wächter würde den alten --subtle-Wert (dunkel) durchlassen')
  assert.ok(kontrast('#6b7088', hellFlaeche) < AA_KONTRAST,
    'der Wächter würde den alten --subtle-Wert (hell) durchlassen')
  assert.ok(kontrast('#c9952f', farbe(HELL, '--bg')) < AA_KONTRAST,
    'der Wächter würde den alten Akzent auf der Fläche durchlassen')
  assert.ok(kontrast('#12183a', farbe(HELL, '--dk-avatar-2-bg')) < AA_KONTRAST ||
    kontrast(farbe(DUNKEL, '--text'), farbe(HELL, '--dk-avatar-2-bg')) < AA_KONTRAST,
    'der alte Avatar-Fall (dunkle Fläche + Theme-Schrift) wäre nicht aufgefallen')
})

test('UX-K1: die Markenflächen tragen weiter', () => {
  for (const theme of ['hell', 'dunkel']) {
    pruefePaar(theme, '--marke-ink', '--marke-flaeche')
  }
  // `--fab-flaeche` ist im Dunkelmodus ein `color-mix` — der FAB trägt dort
  // über seine Fläche (3,2:1 zur Karte) und weiße Schrift (5,5:1, s. tokens.css).
  // Geprüft wird die helle Fassung, die ein reiner Hex-Wert ist.
  pruefePaar('hell', '--fab-ink', '--fab-flaeche')
})

// ── UX-K1c (Operator-Review): Akzent auf Navy in Regeln, die der Wächter oben
// nicht erreicht (Stern im aktiven Lied-Reiter, eigene Chat-Blase, Undo-Kante).
// Feste Liste statt Heuristik: Regel → erwarteter Wert.
test('UX-K1c: Akzent auf Navy in Reiter, Chat-Blase und Undo-Kante führt --accent-auf-marke', () => {
  const faelle = [
    ['src/diakonos/pages/LiedDetail.vue', '.ld-tab.is-active .ld-tab-star'],
    ['src/diakonos/components/chat/ChatBlase.vue', '.dk-chat-blase.is-ich .dk-chat-erwaehnung.is-meine'],
    ['src/diakonos/components/chat/ChatBlase.vue', '.dk-chat-blase.is-erwaehnt.is-ich'],
    ['src/diakonos/index.css', '.diakonos-toast--undo'],
  ]
  for (const [datei, selektor] of faelle) {
    const r = regeln(stilVon(lies(datei), datei)).find((x) => x.selektor.trim() === selektor)
    assert.ok(r, `${datei}: Regel ${selektor} fehlt`)
    assert.match(r.rumpf, /var\(--accent-auf-marke\)/, `${datei} → ${selektor}`)
    assert.doesNotMatch(r.rumpf, /var\(--(?:dk-)?accent\)/, `${datei} → ${selektor}`)
  }
})

test('UX-K1d: die Prüf-Zahl im Kalender-Panel nutzt den Text-Ton, nicht den Zustands-Ton', () => {
  // UX-NACHMESSUNG-2: `.dk-pruef-panel-zahl` stand auf `--warn` (#a86a12,
  // 4,43:1 auf Weiß) — ein Zustands-Ton, keine Schriftfarbe.
  const quelle = lies('src/diakonos/components/kronos/KalenderPruefPanel.vue')
  const regel = quelle.match(/\.dk-pruef-panel-zahl\s*\{([^}]*)\}/)
  assert.ok(regel, 'Regel .dk-pruef-panel-zahl gefunden')
  const token = regel[1].match(/color:\s*var\((--[\w-]+)\)/)?.[1]
  assert.equal(token, '--badge-ink-warn')
  for (const [satz, name] of [[HELL, 'hell'], [DUNKEL, 'dunkel']]) {
    const wert = kontrast(farbe(satz, token), farbe(satz, '--surface'))
    assert.ok(wert >= AA_KONTRAST, `${name}: ${wert.toFixed(2)}:1 auf --surface`)
  }
  assert.ok(kontrast(farbe(HELL, '--warn'), farbe(HELL, '--surface')) < AA_KONTRAST,
    'Gegenprobe: --warn als Schrift war wirklich zu schwach')
})

test('UX-K1e: der Wiki-Titel im Übersichts-Widget nutzt --link (AA in beiden Themes)', () => {
  // UX-NACHMESSUNG-3: `a.wl-wiki-title` stand auf `--dk-brand-400` — im
  // Dunkelmodus #6e7ca6 auf --surface, 4,31:1. `--link` hat je Theme einen
  // eigenen, dafür gedachten Wert.
  const css = lies('src/diakonos/index.css')
  for (const sel of ['.wl-wiki-title', '.wl-wiki-title:hover']) {
    const esc = sel.replace(/[.:]/g, (z) => '\\' + z)
    const regel = css.match(new RegExp('^' + esc + '\\s*\\{([^}]*)\\}', 'm'))
    assert.ok(regel, `Regel ${sel} gefunden`)
    const token = regel[1].match(/(?:^|;)\s*color:\s*var\((--[\w-]+)\)/)?.[1]
    assert.equal(token, '--link', sel)
  }
  for (const [satz, name] of [[HELL, 'hell'], [DUNKEL, 'dunkel']]) {
    const wert = kontrast(farbe(satz, '--link'), farbe(satz, '--surface'))
    assert.ok(wert >= AA_KONTRAST, `${name}: ${wert.toFixed(2)}:1 auf --surface`)
  }
  assert.ok(kontrast(farbe(DUNKEL, '--dk-brand-400'), farbe(DUNKEL, '--surface')) < AA_KONTRAST,
    'Gegenprobe: --dk-brand-400 war im Dunkelmodus wirklich zu schwach')
})
