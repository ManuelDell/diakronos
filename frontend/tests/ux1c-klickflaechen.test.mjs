/**
 * UX1c — Klickflächen 40/44 px.
 *
 * Geprüft wird, was die Karte zusagt (C1, C2), soweit es sich an der Quelle
 * ablesen lässt; das Tippziel am laufenden Browser weist der Bildschirmtest
 * nach (tools/demo/uiux-pruefung.py, Bericht unter
 * /root/.hermes/scratch/diakronos-uiux/ux1c/).
 *
 *   T1  `--control-h` steht auf 40 px und wird im `(pointer: coarse)`-Block
 *       auf 44 px gesetzt — dieselbe eine Quelle wie bisher, nur benutzt.
 *
 *   T2  Der grobe Zeiger hebt die Klickflächen auf `--control-h` an: die
 *       früheren 24-px-Regeln (Befund „heute Minimum 24 px in index.css
 *       ~1780-1797 — ersetzen“) sind verschwunden, und Knöpfe, Menüpunkte,
 *       Listenzeilen, Reiter, Kästchen-Trefferflächen und Tabellenzellen
 *       nennen `var(--control-h)`.
 *
 *   T3  DkButton „sm“ bleibt auf dem feinen Zeiger mindestens 32 px hoch
 *       (`--filter-h-sm`, ein Token — kein Literal in der Komponente).
 *
 *   T4  Seitenleisten-Einträge sind auf dem Desktop mindestens 36 px hoch
 *       (`--sb-item-h`); das Maß hängt nicht an der Zeigerart, weil die
 *       Leiste am groben Zeiger ausgeblendet ist.
 *
 *   T5  Ganze Listenzeile klickbar (C2): jede Tabelle mit Sortier-Kopf und
 *       Zeilen-Ziel benutzt die gedehnte Linkfläche
 *       (`.dk-zellen-link--dehnen`) — und die Fläche ist in index.css
 *       definiert. Lieder-, Mitglieder- und Adressbuchliste führen zu
 *       Detailseiten und sind damit abgedeckt; die Beiträge-Karten
 *       (`.bt-post`) sind selbst die Fläche einer Karte.
 *
 *   T6  Kein neuer fester Wert: der Bestand aus tools/abstand-bestand.txt
 *       bleibt unverändert (er darf nur schrumpfen) und die neuen Maße in
 *       tokens.css sind Tokens, keine Literale in den Komponenten.
 *
 * Läuft wie die übrigen Frontend-Tests im Docker-Build (node --test) und
 * liest ausschließlich Dateien INNERHALB von `frontend/` (Regel 13).
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'

import { FRONTEND, bestand, liesBestand } from '../tools/abstand-bestand.mjs'

function lies(rel) {
  return readFileSync(path.join(FRONTEND, rel.replace(/^frontend\//, '')), 'utf8')
}

const TOKENS = lies('frontend/src/diakonos/tokens.css')
const INDEX = lies('frontend/src/diakonos/index.css')
const BUTTON = lies('frontend/src/diakonos/components/ui/DkButton.vue')

/** Nur der grobe-Zeiger-Block. Er steht am DATEIENDE (Review UX1c 07.11.,
 * Punkt 1: am Dateianfang, vor den `@import`s, war er ungültig und verlor
 * gegen die späteren Grundregeln). Gesucht wird der Block deshalb als
 * LETZTER Treffer; einen zweiten gibt es in der Datei nicht. */
function groberZeiger(css) {
  const start = css.lastIndexOf('@media (pointer: coarse)')
  assert.ok(start >= 0, 'kein `@media (pointer: coarse)`-Block gefunden')
  // bis zur passenden schließenden Klammer (der Block ist verschachtelt)
  const auf = css.indexOf('{', start)
  let tiefe = 0
  for (let i = auf; i < css.length; i++) {
    if (css[i] === '{') tiefe++
    else if (css[i] === '}' && --tiefe === 0) return css.slice(start, i + 1)
  }
  throw new Error('Zeiger-Block nicht geschlossen')
}

/** Derselbe Block, aber robust: Kommentare zuerst entfernen (sie nennen die
 * Zeigerart im Text) und bis zur passenden schließenden Klammer lesen. */
function groberZeigerSauber(css) {
  const ohne = css.replace(/\/\*[\s\S]*?\*\//g, '')
  const start = ohne.lastIndexOf('@media (pointer: coarse)')
  assert.ok(start >= 0, 'kein `@media (pointer: coarse)`-Block gefunden')
  const auf = ohne.indexOf('{', start)
  let tiefe = 0
  for (let i = auf; i < ohne.length; i++) {
    if (ohne[i] === '{') tiefe++
    else if (ohne[i] === '}' && --tiefe === 0) return ohne.slice(start, i + 1)
  }
  return ohne.slice(start)
}

// ── T1: Grundmaß und Erhöhung am groben Zeiger ──────────────────────────────
test('UX1c/T1: --control-h ist 40 px, am groben Zeiger 44 px', () => {
  assert.match(TOKENS, /--control-h:\s*40px/, 'Grundmaß 40 px fehlt in tokens.css')
  // Die Neusetzung steht in tokens.css selbst: index.css wird per @import
  // eingesammelt und landet im Bündel HINTER tokens.css — eine dortige
  // `:root`-Neusetzung verlor dadurch immer (gemessen C3: 40 px).
  const grob = groberZeigerSauber(TOKENS)
  assert.match(grob, /--control-h:\s*44px/, 'am groben Zeiger fehlen die 44 px')
  assert.ok(
    TOKENS.lastIndexOf('--control-h: 44px') > TOKENS.indexOf('--control-h: 40px'),
    'die 44 px müssen hinter dem 40-px-Grundmaß stehen (Kaskade)',
  )
  // `--filter-h`/`--control-h-lg` werden ebenfalls nachgezogen: sie werden
  // EINMAL in :root ausgewertet und blieben beim Zeigerwechsel auf 40 px.
  assert.match(grob, /--filter-h:\s*var\(--control-h\)/, '--filter-h im Zeiger-Block fehlt')
  assert.match(grob, /--control-h-lg:\s*44px/, '--control-h-lg im Zeiger-Block fehlt')
})

// ── T2: die 24-px-Regeln sind weg, --control-h gilt ─────────────────────────
test('UX1c/T2: keine 24-px-Tippziele mehr am groben Zeiger', () => {
  const grob = groberZeiger(INDEX)
  assert.doesNotMatch(grob, /min-height:\s*24px/, 'die alten 24-px-Tippziele stehen noch')
  assert.doesNotMatch(grob, /min-width:\s*24px/, 'die alten 24-px-Tippziele stehen noch')
})

test('UX1c/T2: Knöpfe, Menüpunkte, Listenzeilen, Reiter und Zellen nutzen --control-h', () => {
  const grob = groberZeiger(INDEX)
  // Die Zielgruppen der Karte, je einmal ausdrücklich in einer Regelzeile.
  const erwartet = [
    // UX1g hat die Alt-Knopfreihe entfernt: es gibt nur noch `DkButton`
    // (`.dk-ui-btn`). Die 44 px hängen jetzt an diesem einen Baustein.
    ['.dk-ui-btn', 'DkButton (md und sm)'],
    ['.dk-filter-chip', 'Filterchip'],
    ['.dk-ui-chip', 'Chip'],
    ['.dk-nav-item', 'Menüpunkt der Seitenleiste'],
    ['.dk-sb-profil-punkt', 'Menüpunkt des Profilmenüs'],
    ['.dk-sb-theme-btn', 'Hell/Dunkel-Knopf der Seitenleiste'],
    ['.dk-icon-btn', 'Symbolknopf der Kopfleiste'],
    ['.dk-ui-bz', 'Eintrag der Bereichsliste'],
    ['.ei-eintrag', 'Eintrag der Einstellungen-Liste'],
    ['.dk-ui-segment-item', 'Segment-/Umschaltknopf'],
    ['.toggle-btn', 'Umschalter der Kalenderkopfzeile'],
    ['.dk-tab', 'Reiter (Alt-Reihe)'],
    ['.dk-ui-tab', 'Reiter (DkTabs)'],
    ['.dk-bn-tab', 'Reiter der unteren Leiste'],
    // Review UX1c 07.11., Punkt 6: `min-height` an `tr`/`td` ist auf
    // Tabellenzellen wirkungslos — die Zeilenfläche entsteht über die
    // gedehnte Linkfläche (`.dk-zellen-link--dehnen`, T5), nicht über eine
    // Höhenregel. Beides ist hier deshalb NICHT mehr gefordert.
    ['label:has(> input[type="checkbox"])', 'Kästchen-Trefferfläche'],
    ['input[type="radio"]', 'Radio-Trefferfläche'],
    // Review UX1c 07.11., Punkt 3: Die Termin-Kachel (`.ec-event`) hat KEINE
    // Höhenregel mehr — mit `min-height: var(--control-h)` verschwanden im
    // Monatsraster alle Termine (nur „+1 weitere“, abgeschnitten, Kopfleiste
    // umgebrochen). Sie steht als begründete Ausnahme im Messbericht.
    ['.ec-day-foot a', '„+N weitere“ im Monatsraster'],
    ['input', 'Eingabefeld'],
  ]
  for (const [selektor, name] of erwartet) {
    assert.ok(grob.includes(selektor), `${name}: Selektor fehlt im grobe-Zeiger-Block (${selektor})`)
  }
  // Jede Regel, die eine dieser Flächen anhebt, muss das Token benutzen —
  // nicht 44 als Literal (Konzept: eine Quelle).
  assert.ok((grob.match(/var\(--control-h\)/g) || []).length >= 6, 'zu wenige Regeln ziehen --control-h')
})

test('UX1c/T2: eine Komponentenhöhe kann die 44 px nicht mehr unterlaufen', () => {
  // Gemessen (C3): DkButton bringt `height: var(--filter-h)` aus der SFC mit,
  // DkSegment `height: calc(var(--control-h) - 6px)`. Ohne Vorrang bliebe es
  // bei 40/34 px. Der Vorrang steht NUR im grobe-Zeiger-Block.
  const grob = groberZeiger(INDEX)
  assert.match(grob, /\.dk-ui-btn[\s\S]{0,200}min-height:\s*var\(--control-h\)\s*!important/,
    'DkButton: min-height ohne Vorrang bleibt unter der Komponentenhöhe')
  const aussen = INDEX.replace(grob, '')
  assert.doesNotMatch(aussen, /min-height:\s*var\(--control-h\)\s*!important/,
    '`!important` auf --control-h steht außerhalb des Zeiger-Blocks (Desktop bliebe nicht dicht)')
})

// ── T3: DkButton sm ≥ 32 px auf feinem Zeiger ───────────────────────────────
test('UX1c/T3: DkButton sm ist auf dem Desktop mindestens 32 px hoch', () => {
  assert.match(TOKENS, /--filter-h-sm:\s*32px/, 'Token --filter-h-sm fehlt')
  const sm = BUTTON.match(/\.dk-ui-btn--sm\s*\{([^}]*)\}/)
  assert.ok(sm, 'Regel .dk-ui-btn--sm fehlt in DkButton.vue')
  assert.match(sm[1], /max\(32px,\s*var\(--filter-h-sm\)\)/, 'sm zieht nicht auf das 32-px-Token')
  assert.doesNotMatch(sm[1], /height:\s*28px/, 'die alten 28 px stehen noch')
})

// ── T4: Seitenleiste Desktop ≥ 36 px ────────────────────────────────────────
test('UX1c/T4: Seitenleisten-Einträge sind auf dem Desktop mindestens 36 px hoch', () => {
  assert.match(TOKENS, /--sb-item-h:\s*36px/, 'Token --sb-item-h fehlt')
  const nav = INDEX.match(/\.dk-nav-item\s*\{([^}]*)\}/)
  assert.ok(nav, 'Regel .dk-nav-item fehlt')
  assert.match(nav[1], /min-height:\s*var\(--sb-item-h\)/, 'Menüpunkt zieht nicht auf --sb-item-h')
})

// ── T5: ganze Listenzeile klickbar ──────────────────────────────────────────
test('UX1c/T5: die gedehnte Linkfläche ist zentral definiert', () => {
  assert.match(INDEX, /a\.dk-zellen-link\.dk-zellen-link--dehnen::after\s*\{[^}]*inset:\s*0/)
})

test('UX1c/T5: Listen mit Detailseite dehnen den Zeilenlink über die ganze Zeile', () => {
  for (const datei of [
    'frontend/src/diakonos/pages/Mitglieder.vue',
    'frontend/src/diakonos/pages/Lieder.vue',
    'frontend/src/diakonos/pages/Adressbuch.vue',
  ]) {
    assert.ok(
      lies(datei).includes('dk-zellen-link--dehnen'),
      `${datei}: kein durchgehend klickbares Zeilenziel`,
    )
  }
})

// ── T6: kein neuer fester Wert ──────────────────────────────────────────────
test('UX1c/T6: der Bestand fester Abstandswerte wächst nicht', () => {
  const jetzt = bestand()
  const eingefroren = liesBestand()
  for (const [datei, zahl] of jetzt) {
    const alt = eingefroren.get(datei) ?? 0
    assert.ok(zahl <= alt, `${datei}: ${zahl} feste Werte (erlaubt ${alt}) — Bestand darf nur schrumpfen`)
  }
  for (const [datei, alt] of eingefroren) {
    assert.ok(jetzt.has(datei), `${datei}: behobene Fundstelle nicht nachgezogen (war ${alt})`)
  }
})

test('UX1c/T6: die neuen Maße stehen in tokens.css, nicht in der Komponente', () => {
  // Kartentext: "keine festen Werte in Komponenten" — die zwei neuen Maße
  // sind Tokens; wer sie in eine Komponente schreibt, bricht die Regel.
  for (const datei of [
    'frontend/src/diakonos/components/ui/DkButton.vue',
    'frontend/src/diakonos/components/AppBottomNav.vue',
  ]) {
    const text = lies(datei)
    assert.ok(!/min-height:\s*44px/.test(text), `${datei}: 44 px hart notiert`)
    assert.ok(!/min-height:\s*40px/.test(text), `${datei}: 40 px hart notiert`)
  }
})
