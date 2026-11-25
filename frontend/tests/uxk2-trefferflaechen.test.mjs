/**
 * UX-K2 · WÄCHTER — Mindest-Trefferfläche 44 px an den Bausteinen.
 *
 * Anlass (Nachmessung 25.11., docs/ux/nachmessung-2026-11-25/): 144 Ziele
 * waren auf dem Handy kleiner als 44 px, keine der 66 mobilen Ansichten war
 * frei. Die Karte UX-K2 verlangt den Fix im BAUSTEIN, nicht je Seite:
 *
 *   · Das Maß steht EINMAL als Token (`--treffer-grob: 44px`) und wird am
 *     groben Zeiger ausdrücklich gesetzt — es ist NICHT einstellbar.
 *   · Jeder betroffene Baustein trägt die Mindestfläche in SEINEM Stil. Das
 *     ist keine Doppelung, sondern notwendig: die Baustile sind `scoped`,
 *     im Bündel also `.klasse[data-v-…]` (zwei Klassen) — die globale Regel
 *     in `index.css` (eine Klasse) verliert dagegen, egal mit wie vielen
 *     `!important`. Genau daran scheiterten die 44 px in der Nachmessung
 *     (Reiter 84×32, „⋯“ 34×44, Kästchen 13×13).
 *   · Der Desktop (feiner Zeiger) bleibt kompakt: jede neue Regel steht in
 *     einem `@media (pointer: coarse)`-Block.
 *   · Kästchen werden NICHT aufgeblasen (kein `transform: scale`), die
 *     Trefferfläche wächst über Label/Fläche.
 *
 * Geprüft wird an der QUELLE (Regel 13: nur Dateien innerhalb von
 * `frontend/`). Die Zahlen am laufenden Browser weist der Messlauf nach
 * (`docs/ux/nachmessung-2026-11-25/messlauf.py` im Wegwerf-Stack uxk2).
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const FRONTEND = new URL('../', import.meta.url).pathname
const lies = (rel) => readFileSync(path.join(FRONTEND, rel.replace(/^frontend\//, '')), 'utf8')

const TOKENS = lies('frontend/src/diakonos/tokens.css')
const INDEX = lies('frontend/src/diakonos/index.css')

/**
 * Nur der `(pointer: coarse)`-Block einer Datei (erste schließende Klammer
 * auf gleicher Tiefe). Kommentare werden vorher entfernt — sie nennen die
 * Zeigerart im Text.
 */
function groberZeiger(quelle, letzter = false) {
  const ohne = quelle.replace(/\/\*[\s\S]*?\*\//g, '')
  const start = letzter ? ohne.lastIndexOf('@media (pointer: coarse)') : ohne.indexOf('@media (pointer: coarse)')
  assert.ok(start >= 0, 'kein `@media (pointer: coarse)`-Block gefunden')
  const auf = ohne.indexOf('{', start)
  let tiefe = 0
  for (let i = auf; i < ohne.length; i++) {
    if (ohne[i] === '{') tiefe++
    else if (ohne[i] === '}' && --tiefe === 0) return ohne.slice(start, i + 1)
  }
  throw new Error('Zeiger-Block nicht geschlossen')
}

/** Alle `(pointer: coarse)`-Blöcke einer Datei (Reihenfolge der Datei). */
function alleBlöcke(quelle) {
  const ohne = quelle.replace(/\/\*[\s\S]*?\*\//g, '')
  const blöcke = []
  let ab = 0
  for (;;) {
    const start = ohne.indexOf('@media (pointer: coarse)', ab)
    if (start < 0) break
    const auf = ohne.indexOf('{', start)
    let tiefe = 0
    let ende = ohne.length
    for (let i = auf; i < ohne.length; i++) {
      if (ohne[i] === '{') tiefe++
      else if (ohne[i] === '}' && --tiefe === 0) { ende = i + 1; break }
    }
    blöcke.push(ohne.slice(start, ende))
    ab = ende
  }
  return blöcke
}

/** Stellen (von/bis) aller `(pointer: coarse)`-Blöcke, ohne Kommentare. */
function alleBlöckeStellen(ohne) {
  const stellen = []
  let ab = 0
  for (;;) {
    const start = ohne.indexOf('@media (pointer: coarse)', ab)
    if (start < 0) return stellen
    const auf = ohne.indexOf('{', start)
    let tiefe = 0
    let ende = ohne.length
    for (let i = auf; i < ohne.length; i++) {
      if (ohne[i] === '{') tiefe++
      else if (ohne[i] === '}' && --tiefe === 0) { ende = i + 1; break }
    }
    stellen.push([start, ende])
    ab = ende
  }
}

/** Der `<style>`-Block einer .vue-Datei (ohne Kommentare). */
function stilVon(quelle) {
  const treffer = quelle.match(/<style[^>]*>([\s\S]*?)<\/style>/)
  assert.ok(treffer, 'kein <style>-Block')
  return treffer[1].replace(/\/\*[\s\S]*?\*\//g, '')
}

// ── 1 · das Token ───────────────────────────────────────────────────────────
test('UX-K2/T1: es gibt EIN benanntes Maß „44 px am Finger“ und es ist fix', () => {
  // UX-K2b (Review): Das Token stand zweimal in tokens.css (`:root` und
  // `(pointer: coarse)`). EINE Deklaration reicht — der Wert ist ohnehin
  // unveränderlich 44 px (kein Einstellungswert der Gestaltung).
  assert.match(TOKENS, /--treffer-grob:\s*44px/,
    'das Token --treffer-grob fehlt in tokens.css — dann stünde die 44 als Literal in jeder Komponente')
  const deklarationen = [...TOKENS.matchAll(/--treffer-grob:\s*([^;]+);/g)]
  assert.equal(deklarationen.length, 1,
    `--treffer-grob ist ${deklarationen.length}× deklariert — eine Quelle reicht`)
  // Nicht einstellbar: der Wert steht als Zahl im Stylesheet, nicht als
  // `var(--…)` auf einen Gestaltungswert (die Gestaltung darf ihn nicht kippen).
  const zeile = deklarationen[0][1].trim()
  assert.equal(zeile, '44px', `--treffer-grob muss 44px sein (ist: ${zeile})`)
})

// ── 2 · die Bausteine, die die Nachmessung benannt hat ──────────────────────
const BAUSTEINE = [
  // [Datei, Selektor im grobe-Zeiger-Block, Kurzname aus der Nachmessung]
  ['frontend/src/diakonos/components/ui/DkButton.vue', '.dk-ui-btn', 'Knopf (DkButton)'],
  ['frontend/src/diakonos/components/ui/DkReiter.vue', '.dk-ui-reiter-punkt', 'Reiter-Punkt (84×32)'],
  ['frontend/src/diakonos/components/DiensteReiter.vue', '.dk-dienste-reiter-punkt', 'Dienste-Reiter'],
  ['frontend/src/diakonos/components/ui/DkAktionen.vue', '.dk-ui-aktionen-ausloeser', '„⋯“ (34×44)'],
  ['frontend/src/diakonos/components/ui/DkFilterChips.vue', '.dk-ui-chip', 'Ansicht-Chip (40×44)'],
  ['frontend/src/diakonos/components/ui/DkCheckbox.vue', '.dk-ui-checkbox', 'Kästchen-Zeile (DkCheckbox)'],
  ['frontend/src/diakonos/pages/einstellungen/Anmeldung.vue', '.an-option', 'Kästchen-Zeile (.an-option)'],
]

test('UX-K2/T2: jeder betroffene Baustein trägt die Mindestfläche am groben Zeiger', () => {
  for (const [datei, selektor, name] of BAUSTEINE) {
    const quelle = lies(datei)
    const stil = datei.endsWith('.vue') ? stilVon(quelle) : quelle
    // Der Block MIT dem Selektor (Dateien tragen mehrere Zeiger-Blöcke: der
    // Sprunglink steht bei seiner Regel, die Sammel-Regeln am Dateiende).
    const block = alleBlöcke(stil).find((b) => b.includes(selektor))
    assert.ok(block,
      `${name}: ${selektor} fehlt im grobe-Zeiger-Block von ${datei}`)
    // Der Baustein zieht das Maß aus dem Token — kein Literal 44px.
    const regel = block.slice(block.indexOf(selektor))
    const rumpf = regel.slice(0, regel.indexOf('}') + 1)
    assert.match(rumpf, /min-(height|width):\s*var\(--treffer-grob\)|height:\s*var\(--treffer-grob\)|width:\s*var\(--treffer-grob\)/,
      `${name}: zieht seine Fläche nicht aus --treffer-grob`)
    // Kein Literal NEBEN dem Token: `min-height: 44px; min-height: var(--treffer-grob)`
    // (Rückfall + Quelle, wie bei DkReiter) ist erlaubt, eine 44 allein nicht.
    if (/44px/.test(rumpf)) {
      assert.match(rumpf, /min-height:\s*var\(--treffer-grob\)|height:\s*var\(--treffer-grob\)|width:\s*var\(--treffer-grob\)/,
        `${name}: feste 44px statt --treffer-grob (eine Quelle für das Maß)`)
    }
  }
})

// ── 3 · Kästchen werden nicht aufgeblasen ───────────────────────────────────
test('UX-K2/T3: kein Kästchen wird skaliert (Trefferfläche statt aufgeblasenes Bild)', () => {
  for (const datei of [
    'frontend/src/diakonos/index.css',
    'frontend/src/diakonos/kronos.css',
    'frontend/src/diakonos/components/ui/DkCheckbox.vue',
  ]) {
    const stil = lies(datei)
    assert.doesNotMatch(stil, /(checkbox|radio)[^{]*\{[^}]*transform:\s*scale/,
      `${datei}: ein Kästchen wird per scale aufgeblasen (Fläche wächst stattdessen über Label/Zeile)`)
  }
  // Das Kästchen selbst bleibt klein: 16 px im Baustein, 18 px in der
  // Kalenderliste (Desktop) — beide unverändert.
  assert.match(lies('frontend/src/diakonos/components/ui/DkCheckbox.vue'), /width:\s*16px/,
    'DkCheckbox-Kästchen ist nicht mehr 16 px')
  assert.match(lies('frontend/src/diakonos/kronos.css'), /\.calendar-item input\[type=checkbox\]\s*\{[\s\S]*?width:\s*18px/,
    'Kalender-Kästchen ist auf dem Desktop nicht mehr 18 px')
})

// ── 4 · Desktop bleibt kompakt ──────────────────────────────────────────────
test('UX-K2/T4: das Grundmaß bleibt 40 px — der Desktop wird nicht mitgezogen', () => {
  assert.match(TOKENS, /--control-h:\s*40px/, 'Grundmaß --control-h ist nicht mehr 40 px')
  // Keine 44er-Mindestfläche AUSSERHALB eines Zeiger-Blocks: wer sie global
  // setzt, zieht den Desktop mit. Geschnitten wird an den Stellen aus der
  // QUELLE (vorher/nachher), nicht am normalisierten Text — der entfernt
  // Kommentare und findet die Blöcke darin nicht wieder.
  const blöcke = alleBlöcke(INDEX)
  assert.ok(blöcke.length >= 1, 'kein Zeiger-Block in index.css gefunden')
  const ohneKommentare = INDEX.replace(/\/\*[\s\S]*?\*\//g, '')
  const stellen = alleBlöckeStellen(ohneKommentare)
  let ohneZeiger = ''
  let ab = 0
  for (const [von, bis] of stellen) {
    ohneZeiger += ohneKommentare.slice(ab, von)
    ab = bis
  }
  ohneZeiger += ohneKommentare.slice(ab)
  assert.doesNotMatch(ohneZeiger, /min-height:\s*var\(--treffer-grob\)/,
    'eine Mindestfläche aus --treffer-grob steht außerhalb des Zeiger-Blocks (Desktop wäre nicht mehr kompakt)')
})

// ── 5 · Kästchen-Trefferfläche am LABEL, nicht am Kästchen ───────────────────
test('UX-K2/T5: Kästchen — die Fläche hängt am Label, das Kästchen bleibt klein', () => {
  const block = groberZeiger(INDEX, true)
  assert.match(block, /label:has\(> input\[type="checkbox"\]\)[\s\S]{0,240}min-height:\s*var\(--control-h\)/,
    'die Trefferflächen-Regel am Label fehlt (Kästchen bleiben 13×13)')
  // UX-K2b (Review): Am INPUT darf KEINE Mindestfläche mehr stehen —
  // `min-width`/`min-height` schlagen `width`/`height` und bliesen jedes
  // Kästchen auf 44×44. Getroffen wird über Label/Behälter.
  for (const datei of [
    'frontend/src/diakonos/index.css',
    'frontend/src/diakonos/kronos.css',
    'frontend/src/diakonos/components/ui/DkCheckbox.vue',
    'frontend/src/diakonos/pages/einstellungen/Anmeldung.vue',
  ]) {
    const stile = alleBlöcke(lies(datei))
    for (const b of stile) {
      assert.doesNotMatch(b,
        /(^|[},])\s*input\[type="?(checkbox|radio)"?\]\s*[,{][^}]*min-(width|height):/m,
        `${datei}: ein Zeiger-Block setzt min-width/min-height am Kästchen selbst`)
    }
  }
})

// ── 5b · Benachrichtigungs-Panel: Breite aus der Breite, nicht aus dem Knopf ─
test('UX-K2b/A: .dk-notify-panel hängt nicht an der Breite der Glocke', () => {
  // Nur die GRUNDREGEL (letztes Vorkommen von `.dk-notify-panel {` OHNE
  // weiteren Selektor davor — die @media-Regel am Dateiende setzt nur Ort).
  const regel = [...INDEX.matchAll(/(^|\n)\.dk-notify-panel\s*\{/g)].pop()
  assert.ok(regel, 'Regel `.dk-notify-panel` fehlt in index.css')
  const ab = regel.index + regel[0].length
  const rumpf = INDEX.slice(ab, ab + INDEX.slice(ab).indexOf('}'))
  const eigenschaften = rumpf.replace(/\/\*[\s\S]*?\*\//g, '')
  // `left: 0; right: 0; width: auto` machte das Panel so schmal wie seinen
  // Bezugsrahmen (die Glocke, ~44 px) — auf allen Geräten.
  assert.doesNotMatch(eigenschaften, /left:\s*0/,
    '.dk-notify-panel setzt `left: 0` (Panel wird so schmal wie die Glocke)')
  assert.doesNotMatch(eigenschaften, /width:\s*auto/,
    '.dk-notify-panel setzt `width: auto` (Breite käme aus dem Bezugsrahmen)')
  assert.match(eigenschaften, /right:\s*0/, '.dk-notify-panel hängt nicht mehr an `right: 0`')
  assert.match(eigenschaften, /width:\s*min\(\s*360px/,
    '.dk-notify-panel hat keine feste Höchstbreite mehr')
  assert.match(eigenschaften, /100vw\s*-\s*2\s*\*\s*var\(--sp-3\)/,
    'die Überlauf-Bremse `calc(100vw - 2 * var(--sp-3))` fehlt')
})

// ── 5c · Reihenfolge: Kalender-Zeile nach der Grundregel des Kästchens ───────
test('UX-K2b/B: der Touch-Block der Kalenderzeile steht NACH der Grundregel', () => {
  const stil = lies('frontend/src/diakonos/kronos.css').replace(/\/\*[\s\S]*?\*\//g, '')
  const grund = stil.search(/\.calendar-item input\[type=checkbox\]\s*\{/)
  assert.ok(grund > 0, 'Grundregel `.calendar-item input[type=checkbox]` fehlt')
  // Der Block, der die Mindestfläche der ZEILE setzt.
  const treffer = [...stil.matchAll(/@media \(pointer: coarse\)\s*\{[\s\S]*?\n\}/g)]
    .filter((m) => /\.calendar-item(,|\s*\{)/.test(m[0]))
  assert.equal(treffer.length, 1, `genau EIN Touch-Block für .calendar-item erwartet (sind: ${treffer.length})`)
  assert.ok(treffer[0].index > grund,
    'der Touch-Block für .calendar-item steht VOR der Grundregel — bei gleicher Spezifität gewinnt die spätere Regel, die Fläche wäre wirkungslos')
  // Und er setzt keine Breite/Höhe am Kästchen (nur an Zeile/Beschriftung).
  assert.doesNotMatch(treffer[0][0], /input\[type=checkbox\][^{]*\{[^}]*\b(width|height):/,
    'der Touch-Block bläht das Kästchen selbst auf (Fläche gehört an Zeile/Label)')
  // Das Häkchen-Zeichen ist gültiges CSS mit Anführungszeichen.
  assert.doesNotMatch(stil, /content:\s*✔/, 'kronos.css: Content-Zeichen ohne Anführungszeichen (ungültig)')
})

// ── 5d · Innenabstand-Links: Fläche per ::after, kein Layout-Eingriff ───────
test('UX-K2b/C: die Innenabstand-Links wachsen per ::after-Feld, nicht per min-height', () => {
  // review: min-height + inline-flex an Inline-Verweisen machte Tabellenzeilen
  // höher und unterdrückte Umbruch/Ellipse. Die Fläche kommt deshalb aus einem
  // unsichtbaren Feld mit festem negativem `inset`.
  const quelle = [INDEX, lies('frontend/src/diakonos/components/ui/DkPageHeader.vue'),
    lies('frontend/src/diakonos/pages/GruppeDetail.vue')].join('\n')
  // Fläche = unsichtbares `::after` mit festem negativem `inset`. Geprüft wird
  // über den Quelltext-Index (kein Selektor im Regex — Punkt-Escape-Fallen).
  const quellen = [INDEX, lies('frontend/src/diakonos/components/ui/DkPageHeader.vue'),
    lies('frontend/src/diakonos/pages/GruppeDetail.vue')]
  for (const selektor of ['.dk-ui-brot-link', '.grup-link', '.pr-md-planlink', '.msv-link',
    '.wl-wiki-title', '.dk-kal-pop-ziel']) {
    const stellen = quellen.flatMap((q) => {
      const i = q.indexOf(selektor + '::after')
      return i >= 0 ? [q.slice(i, i + 260)] : []
    })
    assert.ok(stellen.length > 0, `${selektor}: kein ::after-Feld (keine Trefferfläche)`)
    assert.ok(stellen.some((r) => /inset:\s*calc\(\(var\(--treffer-grob\) - 100%\) \/ -2\)\s+calc\(-1 \* var\(--treffer-seite\)\)/.test(r)),
      `${selektor}: das ::after-Feld hat nicht die Trefferflächen-Höhe (calc aus --treffer-grob, Seiten NEGATIV aus --treffer-seite — positiv schrumpft das Feld)`)
  }
  // Keine echte Mindesthöhe mehr an diesen Inline-Verweisen (sie verschiebt
  // Zeilen und Layout).
  const blöcke = [INDEX, lies('frontend/src/diakonos/components/ui/DkPageHeader.vue'),
    lies('frontend/src/diakonos/pages/GruppeDetail.vue')]
  for (const b of blöcke) {
    for (const m of b.matchAll(/\.(grup-link|dk-ui-brot-link|pr-md-planlink|msv-link|wl-wiki-title|dk-kal-pop-ziel)\s*\{[^}]*\}/g)) {
      assert.doesNotMatch(m[0], /min-height:/,
        `${m[0].slice(0, 40)}…: min-height an einem Inline-Verweis (Layout verschiebt sich)`)
    }
  }
  // `.dk-crumb` ist keine Fläche (nicht klickbare Krümel/Trenner).
  const ohneZiel = INDEX.replace(/\/\*[\s\S]*?\*\//g, '')
  for (const b of alleBlöcke(ohneZiel)) {
    assert.doesNotMatch(b, /^\s*\.dk-crumb\s*[,{]/m,
      'index.css: `.dk-crumb` steht wieder als Trefferfläche (trifft auch nicht klickbare <span>)')
  }
})

// ── 6 · die Messung selbst prüft Elemente, nicht Zeilen ─────────────────────
test('UX-K2/T6: die Messung zählt Kästchen mit (sonst bliebe der Befund unsichtbar)', () => {
  const werkzeug = readFileSync(new URL('../../tools/demo/uiux-pruefung.py', import.meta.url), 'utf8')
  const skript = werkzeug.match(/MESS_SKRIPT = r"""([\s\S]*?)"""/)[1]
  assert.match(skript, /input/, 'die Trefferflächen-Messung fragt keine `input` ab')
  assert.match(skript, /minTreffer/, 'die Mindestgröße wird nicht geprüft')
})
