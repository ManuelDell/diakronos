/**
 * UX1d — Wächter: Karten ohne Rahmen, weniger Linien.
 *
 * Drei Befunde der Karte, je eine Prüfung, alle am Quelltext (kein Browser):
 *
 *   T1  D1 · Karten ohne Rahmen, Kopf ohne Kopflinie
 *       a) `tokens.css` führt die Tokens dieser Karte: `--schatten-karte`,
 *          `--rahmen-farbe-leise` und `--karte-rand` — in BEIDEN Themes.
 *       b) `DkCard.vue` schreibt `border: var(--karte-rand)` (nicht
 *          `1px solid …`), nimmt den Schatten aus `--schatten-karte`, hat
 *          KEINE `border-bottom` im Kopf und keine Versalien (`uppercase`)
 *          im Titel; der Titel steht in `--fs-h3` (16 px)/600.
 *       c) `--karte-rand` hängt an der Gestaltungs-Einstellung: die Zeile
 *          `--karte-rand: var(--karte-rahmen…)` steht in tokens.css, sonst
 *          bliebe ein in UX1j gewählter Rahmen wirkungslos.
 *
 *   T2  D2 · „Rahmen in Rahmen“ aufgelöst, Trennlinien leise
 *       Die Widget-Karte (index.css), die Kacheln der Mitglieder-Übersicht
 *       und die Abschnittsliste der Einstellungen tragen keinen festen
 *       Rahmen mehr; die Listen (Datenschutz-Personen, Löschanträge,
 *       Aufgabenliste, Widget-Listen, Tabellenzeilen) trennen mit
 *       `--rahmen-farbe-leise` oder mit Abstand — nicht mit einer harten
 *       Linie. Die Aufgabenliste der Übersicht kommt ohne Linie aus (S3).
 *
 *   T3  D3 · kein Neuladen-Knopf je Karte, „Stand hh:mm“ statt dessen
 *       `BaseWidgetCard.vue` hat keinen Aktualisieren-Knopf mehr (weder als
 *       Knopf noch als Titel „Aktualisieren“), dafür einen Stand-Hinweis
 *       `Stand hh:mm` in Tertiärfarbe (`--subtle`), der erst nach dem
 *       ersten Ladevorgang erscheint (kein erfundenes „Stand 00:00“).
 *
 * Warum Quelltext und nicht DOM: die vier Karten-Familien liegen in
 * gescoptem CSS bzw. in einer globalen Datei; der Wächter soll den Build
 * nicht brauchen (er läuft im node--test-Lauf des Images, Regel 13).
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const HIER = path.dirname(new URL(import.meta.url).pathname)
const FRONTEND = path.resolve(HIER, '..')

const lies = (rel) => readFileSync(path.join(FRONTEND, rel), 'utf8')

const TOKENS = 'src/diakonos/tokens.css'
const INDEX = 'src/diakonos/index.css'
const DKCARD = 'src/diakonos/components/ui/DkCard.vue'
const WIDGET = 'src/diakonos/components/widgets/BaseWidgetCard.vue'
const UEBERSICHT = 'src/diakonos/pages/mitglieder/Uebersicht.vue'
const EINSTELLUNGEN = 'src/diakonos/pages/Einstellungen.vue'
const DATENSCHUTZ = 'src/diakonos/pages/mitglieder/Datenschutz.vue'
const LOESCHANTRAEGE = 'src/diakonos/components/mitglieder/LoeschantraegeListe.vue'

/** Der Block eines Datenblocks in tokens.css: heller `:root` bzw. dunkler Teil. */
function dunklerTeil(tokens) {
  const i = tokens.search(/^\[data-theme="dark"\],?\s*$/m)
  assert.ok(i > 0, 'Dunkelmodus-Block fehlt in tokens.css')
  return tokens.slice(i)
}

test('T1a · tokens.css führt die Karten-Tokens in beiden Themes', () => {
  const tokens = lies(TOKENS)
  const hell = tokens.slice(0, dunklerTeil(tokens).length ? tokens.search(/^\[data-theme="dark"\],?\s*$/m) : undefined)
  const dunkel = dunklerTeil(tokens)

  // Heller Teil: die drei Tokens dieser Karte sind definiert.
  for (const name of ['schatten-karte', 'rahmen-farbe-leise']) {
    assert.match(hell, new RegExp(`--${name}\\s*:`), `--${name} fehlt im hellen Teil`)
    assert.match(dunkel, new RegExp(`--${name}\\s*:`), `--${name} fehlt im Dunkelmodus`)
  }
  // Der Standard ist „kein Rahmen“ und kommt aus der Gestaltungs-Einstellung.
  assert.match(
    hell,
    /--karte-rand\s*:\s*var\(--karte-rahmen\b/,
    '--karte-rand muss aus --karte-rahmen (UX1j) kommen, sonst wirkt die Einstellung nicht',
  )
  // Der sanfte Schatten ist NICHT --shadow-md (das ist für schwebende
  // Flächen) und im Dunkelmodus nicht dasselbe rgba wie im hellen.
  const hellerSchatten = /--schatten-karte\s*:\s*([^;]+);/.exec(hell)
  assert.ok(hellerSchatten, '--schatten-karte fehlt im hellen Teil')
  assert.doesNotMatch(hellerSchatten[1], /shadow-md/, '--schatten-karte darf nicht auf --shadow-md zeigen')
  const dunklerSchatten = /--schatten-karte\s*:\s*([^;]+);/.exec(dunkel)
  assert.ok(dunklerSchatten, '--schatten-karte fehlt im Dunkelmodus')
  assert.notEqual(dunklerSchatten[1].trim(), hellerSchatten[1].trim(), 'Dark-Schatten muss sich vom hellen unterscheiden')
})

test('T1b · DkCard: kein Rahmen, keine Kopflinie, Titel normal geschrieben', () => {
  const quelle = lies(DKCARD)

  assert.match(quelle, /border:\s*var\(--karte-rand\)/, 'DkCard holt ihren Rahmen aus --karte-rand')
  assert.doesNotMatch(quelle, /border:\s*1px solid/, 'DkCard darf keinen festen 1px-Rahmen tragen')
  assert.match(quelle, /box-shadow:\s*var\(--schatten-karte\)/, 'DkCard braucht den sanften Kartenschatten')
  assert.doesNotMatch(quelle, /border-bottom|border-top/, 'DkCard hat keine Kopf-/Fußlinie mehr (Abstand statt Linie)')
  assert.doesNotMatch(quelle, /text-transform:\s*uppercase/, 'DkCard-Titel nicht in Versalien')
  assert.doesNotMatch(quelle, /letter-spacing/, 'kein Versalien-Sperrsatz im Kartenkopf')

  // Titel: 16 px (--fs-h3) in Gewicht 600.
  const titelRegel = /\.dk-ui-card-titel\s*\{([^}]*)\}/.exec(quelle)
  assert.ok(titelRegel, '.dk-ui-card-titel fehlt')
  assert.match(titelRegel[1], /font-size:\s*var\(--fs-h3\)/, 'Kartentitel in --fs-h3 (16 px)')
  assert.match(titelRegel[1], /font-weight:\s*600/, 'Kartentitel in Gewicht 600')
})

test('T2 · kein „Rahmen in Rahmen“, Trennlinien leise', () => {
  const index = lies(INDEX)
  const widgetKarte = /\.dk-widget-card\s*\{([^}]*)\}/.exec(index)
  assert.ok(widgetKarte, '.dk-widget-card fehlt in index.css')
  assert.doesNotMatch(widgetKarte[1], /border:\s*1px/, 'Widget-Karte ohne festen Rahmen')
  assert.match(widgetKarte[1], /border:\s*var\(--karte-rand\)/, 'Widget-Karte folgt der Einstellung')
  assert.match(widgetKarte[1], /box-shadow:\s*var\(--schatten-karte\)/, 'Widget-Karte braucht den Schatten')

  // Keine Kopflinie in den Widget-Karten, kein Versalien-Titel.
  const widgetKopf = /\.dk-widget-header\s*\{([^}]*)\}/.exec(index)
  assert.ok(widgetKopf)
  assert.doesNotMatch(widgetKopf[1], /border-bottom/, 'Widget-Kopf ohne Linie')
  const widgetTitel = /\.dk-widget-title\s*\{([^}]*)\}/.exec(index)
  assert.ok(widgetTitel)
  assert.doesNotMatch(widgetTitel[1], /text-transform:\s*uppercase/, 'Widget-Titel nicht in Versalien')
  assert.match(widgetTitel[1], /font-size:\s*var\(--fs-h3\)/, 'Widget-Titel 16 px')

  // Übersicht-Kacheln: Fläche + Schatten statt Rahmen.
  const kachel = lies(UEBERSICHT)
  const kachelRegel = /\.dk-ui-kachel\s*\{([^}]*)\}/.exec(kachel)
  assert.ok(kachelRegel, '.dk-ui-kachel fehlt')
  assert.doesNotMatch(kachelRegel[1], /border:\s*1px/, 'Kachel ohne festen Rahmen')
  assert.match(kachelRegel[1], /box-shadow:\s*var\(--schatten-karte\)/, 'Kachel braucht den Schatten')
  assert.doesNotMatch(kachel, /border-top:\s*1px|border-bottom:\s*1px/, 'Übersicht trennt mit Abstand, nicht mit Linie')

  // Einstellungen: die Abschnittsliste ist keine Karte mit eigenem Rahmen.
  const einst = lies(EINSTELLUNGEN)
  const liste = /\.ei-liste\s*\{([^}]*)\}/.exec(einst)
  assert.ok(liste, '.ei-liste fehlt')
  assert.doesNotMatch(liste[1], /border:\s*1px/, 'Abschnittsliste ohne festen Rahmen')

  // Listen: leise Linie statt harter Kante.
  for (const [datei, name] of [
    [DATENSCHUTZ, 'Datenschutz-Personenliste'],
    [LOESCHANTRAEGE, 'Löschanträge'],
  ]) {
    const text = lies(datei)
    assert.doesNotMatch(
      text,
      /border-(?:top|bottom):\s*1px solid var\(--(?:dk-)?border\)/,
      `${name}: harte Linie statt --rahmen-farbe-leise`,
    )
  }
  assert.match(lies(DATENSCHUTZ), /--rahmen-farbe-leise/, 'Datenschutz-Liste trennt leise')
  assert.match(lies(LOESCHANTRAEGE), /--rahmen-farbe-leise/, 'Löschanträge trennen leise')
})

test('T3 · kein Neuladen-Knopf je Karte, „Stand hh:mm“ in Tertiärfarbe', () => {
  const quelle = lies(WIDGET)

  // Kein Knopf und auch kein Titel „Aktualisieren“ mehr.
  assert.doesNotMatch(quelle, /title="Aktualisieren"/, 'der Neuladen-Knopf je Karte muss weg sein')
  assert.doesNotMatch(quelle, /dk-widget-action-btn[\s\S]{0,200}Aktualisieren/, 'kein Aktualisieren-Knopf in der Werkzeugleiste')

  // Statt dessen der Stand-Hinweis.
  assert.match(quelle, /Stand \$\{stunde\}:\$\{minute\}/, 'Stand-Hinweis „Stand hh:mm“ fehlt')
  assert.match(quelle, /class="dk-widget-stand"/, 'Stand-Hinweis braucht seine Klasse für die Gestaltung')

  // Erscheint NUR nach einem Ladevorgang (kein erfundener Stand).
  assert.match(
    quelle,
    /const stand = ref\(null\)/,
    'der Stand beginnt leer — sonst stünde vor dem ersten Laden eine erfundene Uhrzeit',
  )
  assert.match(quelle, /v-if="!collapsed && standText"/, 'der Stand erscheint nur, wenn es einen gibt')

  // Gestaltung: Tertiärfarbe (--subtle), 12 px, Ziffern auf einer Breite.
  const css = lies(INDEX)
  const stand = /\.dk-widget-stand\s*\{([^}]*)\}/.exec(css)
  assert.ok(stand, '.dk-widget-stand fehlt in index.css')
  assert.match(stand[1], /color:\s*var\(--subtle\)/, 'Stand in Tertiärfarbe')
  assert.match(stand[1], /font-variant-numeric:\s*tabular-nums/, 'Stand mit gleich breiten Ziffern')
})
