/**
 * DEV-B6b — Grund- vs. Handy-Selektoren (Review-Nacharbeit 10.11., Punkt 2).
 *
 * WARUM DIESER TEST
 * Commit c4028e52 hat beim Entfernen der `:global()`-Selektoren in mehreren
 * Dateien die Rollen VERTAUSCHT (Suchen/Ersetzen traf die falsche der beiden
 * Regeln):
 *
 *   * `Befehlspalette.vue`: die GRUNDREGELN der Hülle/Suchzeile/Zeile/Ort/Fuß
 *     trugen plötzlich den Handy-Präfix, die Handy-Feinheiten standen ohne
 *     Präfix — Strg+K am Desktop hatte damit keine fixierte, abgedunkelte
 *     Hülle und keine Zeilen-Polsterung.
 *   * `KronosSidebar.vue`: Schließen-Knopf vertauscht — am Desktop sichtbar
 *     „✕“ oben rechts, im Handy-Overlay weg.
 *   * `ModerationSidebar.vue`: die Spalte stand ÜBERALL auf `display: none`.
 *   * `Kalender.vue`: `.kronos-page-content { overflow-y: auto }` galt
 *     überall (Desktop-Kalender bekam einen Scrollbalken).
 *
 * Der Test prüft die Zuordnung an den QUELLTEXTEN (die Kaskade selbst ist im
 * Wegwerf-Stack belegt, siehe Kartenkommentar). Muster: `tests/fix6b-kaskade
 * .test.mjs` — kein Vue-Mount nötig, damit der Test ohne Build läuft.
 *
 * Die Handy-Lage ist die EINE Klasse `.dk-app--handy` (`composables/handyLage
 * .mjs`, gesetzt in `App.vue`) — kein zweiter Media-String (DEV-B6).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const SRC = resolve('src/diakonos')
const lies = (rel) => readFileSync(resolve(SRC, rel), 'utf8')

/** Der `<style>`-Teil einer SFC (letzter Block; mehr gibt es nicht). */
function stil(rel) {
  const text = lies(rel)
  const i = text.lastIndexOf('<style')
  assert.ok(i >= 0, `${rel}: <style>-Block fehlt`)
  return text.slice(i)
}

/**
 * Sucht die Regel, die GENAU diese Selektoren-Kette trägt (eine Zeile mit `{`
 * am Zeilenende) und liefert ihren Deklarationsblock. B6-N3: CSS-Kommentare
 * werden vorher entfernt — die Umbaute lag innerhalb eines Kommentarblocks
 * (vorher ein Blockkommentar, jetzt eine gewöhnliche Regel) und die alte
 * Suche hätte die Regel samt Kommentar verschluckt.
 */
function blockMit(rel, selektoren) {
  const css = stil(rel).replace(/\/\*[\s\S]*?\*\//g, '')
  const teile = Array.isArray(selektoren) ? selektoren : [selektoren]
  for (const s of teile) {
    const re = new RegExp(`(?:^|\\})\\s*${s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*\\{([^}]*)\\}`, 'm')
    const m = re.exec(css)
    if (m) return m[1]
  }
  return null
}

/** Es gibt KEINE Regel mit genau dieser Kette. */
function ohneRegel(rel, selektor) {
  return blockMit(rel, selektor) === null
}

// ── Befehlspalette ─────────────────────────────────────────────────────────
test('DEV-B6b: Befehlspalette — Grundregeln gelten OHNE Handy-Lage', () => {
  const grund = {
    'dk-palette-huelle': ['position: fixed', 'inset: 0', 'background: var(--overlay)'],
    'dk-palette-suchzeile': ['display: flex', 'border-bottom'],
    'dk-palette-zeile': ['display: flex', 'min-height: var(--control-h)'],
    'dk-palette-ort': ['flex: none', 'text-overflow: ellipsis'],
    'dk-palette-fuss': ['display: flex', 'background: var(--surface-2)'],
  }
  for (const [klasse, merkmale] of Object.entries(grund)) {
    const block = blockMit('components/Befehlspalette.vue', `.${klasse}`)
    assert.ok(block, `Grundregel .${klasse} fehlt (ohne Handy-Praefix, sonst fehlt sie am Desktop)`)
    for (const m of merkmale) {
      assert.ok(block.includes(m), `Grundregel .${klasse} braucht „${m}“`)
    }
  }
})

test('DEV-B6b: Befehlspalette — die Handy-Feinheiten tragen den Handy-Präfix', () => {
  const css = stil('components/Befehlspalette.vue')
  // Die engen Handy-Maße (volle Breite/Höhe, kleinere Polster) stehen
  // ausschließlich unter `.dk-app--handy`.
  assert.match(css, /\.dk-app--handy \.dk-palette-huelle\s*\{[^}]*padding: var\(--sp-4\)/s,
    'Handy-Polster der Hülle hängt an der Handy-Lage')
  assert.match(css, /\.dk-app--handy \.dk-palette\s*\{[^}]*width: 100%/s,
    'volle Breite am Handy hängt an der Handy-Lage')
  assert.match(css, /\.dk-app--handy \.dk-palette-suchzeile\s*\{[^}]*min-height: var\(--control-h\)/s,
    'Suchzeilen-Höhe am Handy hängt an der Handy-Lage')
  assert.match(css, /\.dk-app--handy \.dk-palette-zeile\s*\{[^}]*min-height: var\(--control-h\)/s,
    'Zeilen-Höhe am Handy hängt an der Handy-Lage')
  assert.match(css, /\.dk-app--handy \.dk-palette-ort\s*\{[^}]*max-width: 45%/s,
    'Orts-Breite am Handy hängt an der Handy-Lage')
  assert.match(css, /\.dk-app--handy \.dk-palette-fuss\s*\{[^}]*padding: var\(--sp-2\) var\(--sp-4\)/s,
    'Fuß-Polster am Handy hängt an der Handy-Lage')
})

// ── KronosSidebar ──────────────────────────────────────────────────────────
test('DEV-B6b: KronosSidebar — Schließen-Knopf nur im Handy-Overlay', () => {
  const grund = blockMit('components/kronos/KronosSidebar.vue', '.kronos-sidebar-close')
  assert.ok(grund, 'Grundregel .kronos-sidebar-close fehlt')
  assert.match(grund, /display:\s*none/, 'Grundregel: der Knopf ist AUS (Desktop hat keinen)')

  const handy = blockMit('components/kronos/KronosSidebar.vue', '.dk-kalenderliste-overlay .kronos-sidebar-close')
  // B6-N2 (Punkt 1, Regel 19): Die Klasse hieß hier `.dk-app--handy` — richtig
  // ist sie am OVERLAY, weil die Liste seit DEV-B6b auch im schmalen
  // MAUS-Fenster (≤ 1100 px) ein Overlay ist und dort denselben ✕ braucht.
  // Die Seite setzt die Klasse, wenn sie das Overlay führt (NUR schmales
  // Maus-Fenster — die Handy-Lage bleibt beim Popover).
  // B6-N3 (Punkt D): Sie hieß irreführend `dk-overlay-handy` („Handy“ war
  // genau das Gegenteil gemeint) und heißt jetzt `dk-kalenderliste-overlay`.
  assert.ok(handy, 'Overlay-Regel .dk-kalenderliste-overlay .kronos-sidebar-close fehlt')
  assert.match(handy, /display:\s*flex/, 'im Overlay ist der Knopf AN')
  assert.match(handy, /position:\s*absolute/, 'im Overlay sitzt der Knopf oben rechts')
  // Review 12.11., Punkt 7: Klickfläche und Abstand aus den Tokens — am
  // groben Zeiger ist `--control-h` 44 px, feste 32 px waren zu klein.
  assert.match(handy, /width:\s*var\(--control-h\)/, '✕-Breite kommt aus --control-h')
  assert.match(handy, /height:\s*var\(--control-h\)/, '✕-Höhe kommt aus --control-h')
  assert.match(handy, /top:\s*var\(--sp-\d\)/, 'Abstand oben aus der Abstandsskala')
  assert.ok(!/(?:^|\s)(?:width|height):\s*\d+px/.test(handy),
    'keine feste px-Größe mehr am ✕-Knopf')
})

test('B6-N3: der ✕ der Kalenderliste ist ein DkSymbol, kein Textzeichen', () => {
  // Punkt C: `&times;` ist ein Textzeichen mit eigener Schriftmetrik und
  // skaliert nicht mit den Symbolen; die Symbole kommen zentral aus
  // `components/ui/symbole.mjs` (`abbrechen` = zwei gekreuzte Striche).
  const text = lies('components/kronos/KronosSidebar.vue')
  const knopf = /class="kronos-sidebar-close"[\s\S]*?<\/button>/.exec(text)
  assert.ok(knopf, 'Schließen-Knopf fehlt')
  assert.match(knopf[0], /<DkSymbol\s+name="abbrechen"/,
    'der ✕ zeichnet das zentrale Symbol „abbrechen“')
  assert.ok(!/&times;|&#215;|&#10005;|✕/.test(knopf[0]),
    'kein Textzeichen als ✕ (Symbolfamilie bleibt einheitlich)')
  // Das Symbol muss im Vorrat liegen, sonst zeichnet DkSymbol NICHTS.
  const symbole = readFileSync(resolve(SRC, 'components/ui/symbole.mjs'), 'utf8')
  assert.match(symbole, /^\s*abbrechen:\s*\{/m, 'Symbol „abbrechen“ fehlt im Vorrat')
  // Und der Import steht in der Datei (sonst bliebe das Element leer).
  assert.match(text, /import DkSymbol from '\.\.\/ui\/DkSymbol\.vue'/, 'DkSymbol wird importiert')
})

// ── ModerationSidebar ──────────────────────────────────────────────────────
test('DEV-B6b: ModerationSidebar — Spalte verschwindet nur in der Handy-Lage', () => {
  assert.ok(ohneRegel('components/kronos/ModerationSidebar.vue', '.dk-sidebar--moderation'),
    'es darf KEINE unbedingte Regel `.dk-sidebar--moderation` geben (sonst fehlt die Spalte am Desktop)')
  const handy = blockMit('components/kronos/ModerationSidebar.vue', '.dk-app--handy .dk-sidebar--moderation')
  assert.ok(handy, 'Handy-Regel für die Spalte fehlt')
  assert.match(handy, /display:\s*none/, 'in der Handy-Lage ist die Spalte aus')
})

// ── Kalender ───────────────────────────────────────────────────────────────
test('DEV-B6b: Kalender — overflow-y:auto nur im Handy-Querformat', () => {
  const css = stil('pages/Kalender.vue')
  // Die Grundregel der Seite bleibt ohne Scrollen.
  const grund = blockMit('pages/Kalender.vue', '.kronos-page-content')
  assert.ok(grund, 'Grundregel .kronos-page-content fehlt')
  assert.match(grund, /overflow:\s*hidden/, 'Grundregel: kein Scrollen (Desktop)')
  assert.ok(!/overflow-y:\s*auto/.test(grund), 'die Grundregel darf kein overflow-y:auto tragen')

  // Die Ausnahme steht im Querformat-Block UND mit Handy-Klasse.
  const m = /@media \(orientation: landscape\) and \(max-height: 480px\)\s*\{([\s\S]*?)\n\}/.exec(css)
  assert.ok(m, 'Querformat-Block (orientation: landscape) and (max-height: 480px) fehlt')
  assert.match(m[1], /\.dk-app--handy \.kronos-page-content\s*\{[^}]*overflow-y:\s*auto/s,
    'overflow-y:auto steht nur im Handy-Querformat')
  assert.ok(ohneRegel('pages/Kalender.vue', '.kronos-page-content { overflow-y: auto }') ||
    !/(?:^|\})\s*\.kronos-page-content\s*\{[^}]*overflow-y:\s*auto/.test(css),
  'es darf keine unbedingte overflow-y:auto-Regel für .kronos-page-content geben')
})

// ── Kalenderliste: EIN Weg ─────────────────────────────────────────────────
test('DEV-B6b: Kalenderliste — Overlay hat left:0 und der Knopf öffnet es überall, wo es Overlay ist (≤ 1100 px, Maus)', async () => {
  const css = readFileSync(resolve(SRC, 'kronos.css'), 'utf8')
  const m = /@media \(max-width: 1100px\)\s*\{([\s\S]*?)\n\}/.exec(css)
  assert.ok(m, 'Block @media (max-width: 1100px) für .kronos-sidebar-inpage fehlt')
  assert.match(m[1], /\.kronos-sidebar-inpage\s*\{[^}]*left:\s*0/s,
    'das Überlager-Overlay braucht left:0 (sonst ragt es über die App-Seitenleiste)')

  // Entscheidung Operator (10.11.): EIN Weg. Dieselbe Abfrage wie die
  // Overlay-Regel (1100 px) — nicht 720 px, sonst führt der Knopf zwischen
  // 721 und 1100 px ins Popover, obwohl die Liste dort ein Overlay ist.
  const { SEITENLEISTE_SCHMAL_ABFRAGE } = await import('../src/diakonos/composables/handyLage.mjs')
  assert.equal(SEITENLEISTE_SCHMAL_ABFRAGE, '(max-width: 1100px)', 'Abfrage und kronos.css-Grenze laufen auseinander')
  const seite = lies('pages/Kalender.vue')
  // B6-N2 (Punkt 1, Regel 19): Die Prüfung suchte den `matchMedia`-Aufruf IN
  // der Funktion. Die Lage wird jetzt EINMAL als reaktive Quelle gelesen
  // (`leistenLageLesen` + `listeAlsOverlay`, damit ✕, Schleier und Escape
  // dieselbe Antwort sehen) — die Aussage bleibt: Knopf-Zweig hängt an der
  // schmalen Leiste (genau der 1100-px-Abfrage).
  // Review 12.11., Punkt 2: Die HANDY-Lage ist AUSGENOMMEN — dort bleibt es
  // beim freigegebenen A10-Popover. `listeAlsOverlay` lautet deshalb
  // `!istHandyLage && schmaleLeiste`; ohne das `!` öffnete der Knopf in der
  // Handy-Lage das Overlay statt des Popovers.
  const fn = /function kalenderAuswahlUmschalten\(\) \{([\s\S]*?)\n\}/.exec(seite)
  assert.ok(fn, 'kalenderAuswahlUmschalten fehlt')
  const lage = /const listeAlsOverlay = computed\(\(\) => !istHandyLage\.value && schmaleLeiste\.value\)/.exec(seite)
  assert.ok(lage, 'listeAlsOverlay: Overlay NUR im schmalen Maus-Fenster, nicht in der Handy-Lage')
  assert.match(seite, /leistenAbfrage = window\.matchMedia\(SEITENLEISTE_SCHMAL_ABFRAGE\)/,
    'schmale Leiste kommt aus derselben 1100-px-Abfrage wie das Overlay-CSS')
  assert.match(fn[1], /if \(listeAlsOverlay\.value\)/,
    'der Knopf öffnet das Overlay genau dort, wo kronos.css es setzt')
  assert.ok(!/KALENDER_HANDY_PX/.test(fn[1]), 'keine zweite Grenze (720 px) im Knopf-Zweig')
  // Handy-Lage: Popover wie A10 — der Popover-Zweig folgt NACH dem Overlay-Zweig.
  assert.ok(fn[1].indexOf('auswahlOffen.value = true') > fn[1].indexOf('kronosSidebar.auf()'))
  // Punkt 8: Beim Öffnen wandert der Fokus ins Overlay, und der Auslöser
  // meldet den Overlay-Zustand (`aria-expanded`), nicht nur das Popover.
  assert.match(fn[1], /nextTick\(fokusInsOverlay\)/,
    'Öffnen setzt den Fokus ins Overlay')
  assert.match(seite, /:auswahlOffen="auswahlOffen \|\| kronosSidebar\.offen\.value"/,
    'aria-expanded des Kalender-Knopfs kennt den Overlay-Zustand')
})

// ── Inhaltsregeln hängen an der BREITE ─────────────────────────────────────
/** Alle Deklarationsblöcke, deren Selektor-Kopf `muster` enthält. */
function bloecke(css, muster) {
  const treffer = []
  const re = new RegExp(muster.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g')
  let m
  while ((m = re.exec(css))) {
    const auf = css.indexOf('{', m.index)
    if (auf < 0) continue
    const zu = css.indexOf('}', auf)
    if (zu < 0) continue
    treffer.push(css.slice(auf + 1, zu))
  }
  return treffer
}

/** Steht der Text irgendwo in einem @media-Block mit dieser Grenze? */
function inBreitenBlock(css, grenze, pruefung) {
  const re = new RegExp(`@media \\(max-width: ${grenze}px\\)\\s*\\{`, 'g')
  let m
  while ((m = re.exec(css))) {
    // Block bis zur passenden schließenden Klammer (verschachtelte @media!).
    let tiefe = 0
    let i = css.indexOf('{', m.index)
    const ab = i + 1
    for (; i < css.length; i += 1) {
      if (css[i] === '{') tiefe += 1
      else if (css[i] === '}') {
        tiefe -= 1
        if (tiefe === 0) {
          if (pruefung(css.slice(ab, i))) return true
          break
        }
      }
    }
  }
  return false
}

test('DEV-B6b: Inhaltsumbrüche hängen an der Breite, nicht am Zeiger', () => {
  const css = readFileSync(resolve(SRC, 'index.css'), 'utf8')
  const faelle = [
    ['.dk-grid-cols-2', '.dk-grid-cols-2'], ['.dk-grid-cols-3', '.dk-grid-cols-3'],
    ['.dk-grid-cols-4', '.dk-grid-cols-4'],
    ['.dk-widget-large', '.dk-widget-large'], ['.dk-widget-full', '.dk-widget-full'],
    ['.dk-stats-row', '.dk-stats-row'], ['.dk-quick-row', '.dk-quick-row'],
    ['.diakonos-toast-container', '.diakonos-toast-container'],
  ]
  for (const [name, selektor] of faelle) {
    // (a) KEINE Regel dieser Klasse hängt an der Handy-Lage.
    const mitHandy = bloecke(css, `\\.dk-app--handy[^{}]*\\${selektor}`)
    assert.equal(mitHandy.length, 0, `${name} darf NICHT an der Handy-Lage hängen (Inhalts-Umbruch = Breite)`)
    // (b) Der Umbruch steht in einem @media (max-width: 720px)-Block.
    assert.ok(inBreitenBlock(css, 720, (block) => block.includes(`\n  ${selektor}`) || block.includes(` ${selektor}`)),
      `${name} muss im Block @media (max-width: 720px) stehen`)
  }
})

// ── Tote Regel (Punkt 5) ───────────────────────────────────────────────────
test('DEV-B6b: die tote Menü-Knopf-Regel in .dk-sb-top ist entfernt', () => {
  // CSS-Kommentare zählen nicht: der Hinweis auf die entfernte Regel steht
  // bewusst als Kommentar in der Datei.
  const css = readFileSync(resolve(SRC, 'index.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
  // Regel = Selektor-Kopf mit `{`.
  assert.ok(!/\.dk-sb-top\s+\.dk-menue-knopf\s*\{/.test(css),
    'die tote Regel `.is-collapsed .dk-sb-top .dk-menue-knopf` steht noch (Knopf liegt in der Kopfzeile)')
})
