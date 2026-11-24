/**
 * BEF-KAL-UNTEN — Kalender am Handy: die untere Leiste verdeckt keine Termine
 * mehr, „Termin anlegen“ wird ein runder „+“-Knopf (Manuel 24.11., Befund
 * DMB-d43df8406c05, Wunsch aus DMB-b329fefa1f4d).
 *
 * Nach LEISTE-2 läuft der Kalender ohne App-Kopfzeile (`#/kalender` ist
 * Vollbild, `router.js`), und genau dabei ging der Platz für die UNTERE Leiste
 * verloren:
 *
 *   U1  Der Platz unten steht an EINER Stelle (`--leiste-unten-h` in
 *       tokens.css) und wird von der Liste (Tagesliste) wie vom Raster
 *       (Monat/Woche) benutzt — Leiste + Sicherheitszone, kein Rohwert.
 *   U2  Die Höhe der Mobil-Flächen zieht KEIN `--topbar-h` mehr ab: die
 *       Kopfzeile gibt es auf dieser Seite nicht (LEISTE-2), die 56 px fehlten
 *       also am Ende.
 *   U3  `.dk-content` trägt den Fußabstand bei Vollbild-Seiten NICHT mehr
 *       (er klaut dem Flex-Kasten die Höhe) — der Abstand steht an der Seite.
 *   U4  Der Knopf ist am Handy ein KREIS mit „+“ und `aria-label="Termin
 *       anlegen"`; die Pille gibt es nur noch ohne Fingerzeiger.
 *   U5  Nachrichten (gleicher Vollbild-Modus, LEISTE-1): die Seite trägt den
 *       Fußabstand selbst, die Eingabe liegt über der Leiste.
 *   U6  Gegenprobe der Prüfregeln an einer alten Fassung (≥ 2 rot).
 *
 * Lauf: TZ=Europe/Berlin node --test tests/bef-kal-unten-handy.test.mjs
 *       (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const SRC = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, SRC), 'utf8')

/** Alle <style>-Blöcke einer SFC (ohne Kommentare) — eine Fläche zum Prüfen. */
function stil(rel) {
  const ganz = lies(rel)
  const bloecke = [...ganz.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1])
  const roh = bloecke.length ? bloecke.join('\n') : ganz
  // Kommentare raus — sie NENNEN alte Werte („vorher topbar-h“), sind aber
  // keine Regel.
  return roh.replace(/\/\*[\s\S]*?\*\//g, '')
}

/** Körper einer Regel (erster Treffer des Selektors, ohne Kommentare). */
function regel(css, selektor) {
  const idx = css.indexOf(selektor)
  assert.ok(idx >= 0, `Regel fehlt: ${selektor}`)
  const start = css.indexOf('{', idx)
  const ende = css.indexOf('}', start)
  assert.ok(start > 0 && ende > start, `Regel ohne Körper: ${selektor}`)
  return css.slice(start + 1, ende)
}

/** Hat die Regel den Selektor GENAU (nicht nur als Anfang eines längeren)? */
function hatRegel(css, selektor) {
  return css.split('\n').some((z) => z.trim() === `${selektor} {`) || css.includes(`${selektor} {`)
}

/**
 * Ein Wert „Leiste + Sicherheitszone“ — als Token-Kette, nie als Zahl.
 * Erlaubt: `var(--leiste-unten-h)` / `var(--bottom-nav-h)`, dazu
 * `env(safe-area-inset-bottom…)` und `calc()` aus Tokens.
 */
function istLeistenAbstand(wert) {
  const ohne = String(wert || '').replace(/\s+/g, ' ').trim()
  if (!/var\(--(?:leiste-unten-h|bottom-nav-h)\)/.test(ohne)) return false
  if (!/env\(\s*safe-area-inset-bottom/.test(ohne)) return false
  // Kein roher Längenwert (px/rem) im Abstand — nur Tokens und calc().
  return !/\d+(?:\.\d+)?(?:px|rem|em)\b/.test(ohne)
}

// ══ U1 · Der Platz unten steht an EINER Stelle ═════════════════════════════

test('BEF-KAL-UNTEN/U1: ein Token nennt „was unten im Bild liegt" (nicht je Seite neu)', () => {
  const tokens = stil('tokens.css')
  assert.match(tokens, /--leiste-unten-h:\s*var\(--bottom-nav-h\)/,
    'ohne `--leiste-unten-h` (aus `--bottom-nav-h`) rechnet jede Seite ihren eigenen Wert')
  assert.match(tokens, /--bottom-nav-h:\s*64px/, 'die Leiste bleibt 64 px hoch (Token, kein Rohwert in den Seiten)')
})

test('BEF-KAL-UNTEN/U1: Tagesliste UND Raster halten die untere Leiste frei', () => {
  const css = stil('pages/Kalender.vue')

  // Tagesliste (Listen-Ansicht: Mini-Monat + Termine).
  const liste = regel(css, '\n.kal-a10-liste {')
  assert.match(liste, /padding-bottom:/, 'die Tagesliste hat keinen Fußabstand — die letzte Zeile läge unter der Leiste')
  const abstand = /padding-bottom:\s*([^;]+);/.exec(liste)[1]
  assert.ok(istLeistenAbstand(abstand),
    `Fußabstand der Tagesliste ist Leiste + Sicherheitszone (Token), ist aber: ${abstand.trim()}`)
  assert.match(liste, /overflow-y:\s*auto/, 'die Liste scrollt selbst')

  // Raster (Monat/Woche).
  const raster = regel(css, '\n.kal-mobil-raster {')
  const rasterAbstand = /padding:\s*([^;]+);/.exec(raster)[1]
  assert.ok(istLeistenAbstand(rasterAbstand),
    `Fußabstand des Rasters ist Leiste + Sicherheitszone (Token), ist aber: ${rasterAbstand.trim()}`)
})

test('BEF-KAL-UNTEN/U1: der runde Knopf schwebt ÜBER der Leiste, nicht in ihr', () => {
  const css = stil('pages/Kalender.vue')
  const fab = regel(css, '\n.kal-fab {')
  const unten = /bottom:\s*calc\(([^;]+)\);/.exec(fab)
  assert.ok(unten, 'der Knopf hat keine Rechnung für seine Höhe über der Leiste')
  // `--sp-8` (64 px) hält ihn über einer 64-px-Leiste; die Sicherheitszone
  // kommt dazu (iPhone: Home-Indikator).
  assert.match(unten[1], /--sp-8/, 'der Abstand zum unteren Rand kommt aus der Skala (--sp-8)')
  assert.match(unten[1], /env\(safe-area-inset-bottom\)/, 'und beachtet die Sicherheitszone des Geräts')

  // Querformat: dort ist die Leiste der Bezug (gleiche Regel wie bisher).
  assert.match(css, /@media \(max-height: 480px\) and \(orientation: landscape\) \{[\s\S]*?\.dk-app--handy \.kal-fab \{[\s\S]*?var\(--bottom-nav-h\)/,
    'im Querformat muss `bottom` die untere Leiste mitrechnen')
})

// ══ U2 · Kein `--topbar-h`-Abzug mehr ══════════════════════════════════════

test('BEF-KAL-UNTEN/U2: die Mobil-Flächen ziehen KEINE App-Kopfzeile mehr ab (LEISTE-2)', () => {
  const css = stil('pages/Kalender.vue')
  // Bis LEISTE-2 stand hier `100vh - var(--topbar-h) - …`. Die Kopfzeile gibt
  // es auf `#/kalender` nicht mehr — die 56 px fehlten am unteren Rand.
  assert.doesNotMatch(css, /height:\s*calc\([^;]*var\(--topbar-h\)/, 
    'die Kopfzeilen-Höhe wird auf einer Seite ohne Kopfzeile abgezogen')
  assert.match(css, /\.kal-a10-liste \{[^}]*height:\s*calc\(100vh -/,
    'die Tagesliste rechnet ihre Höhe aus der Fensterhöhe')
})

// ══ U3 · Der Kasten `.dk-content` trägt den Abstand nicht mehr ═════════════

test('BEF-KAL-UNTEN/U3: bei Vollbild-Seiten gilt der Kasten-Abstand NICHT (Höhe bleibt beim Inhalt)', () => {
  const css = stil('index.css')
  // Grundregel für alle Handy-Seiten bleibt (sonst läge jede Seite unter der Leiste).
  assert.match(css, /\.dk-app--handy \.dk-content \{[^}]*padding-bottom:\s*calc\(var\(--bottom-nav-h\)/,
    'die Grundregel für `.dk-content` fehlt')
  // Vollbild-Seiten sind die Flex-Säule ihrer Seite — dort klaut der Abstand
  // dem Inhalt die Höhe (Befund: unterste Zeile der Tagesliste unter der Leiste).
  const ausnahme = /\.dk-app--handy \.dk-content\.dk-content--vollbild \{([^}]*)\}/.exec(css)
  assert.ok(ausnahme, 'die Ausnahme für Vollbild-Seiten fehlt — der Kasten-Abstand bliebe doppelt')
  assert.match(ausnahme[1], /padding-bottom:\s*0\s*!important/,
    'die Ausnahme muss den Abstand wirklich aufheben (!important gegen die Grundregel)')

  // Und die Marke hängt an der Adresse (App.vue), nicht an der Seitenstruktur.
  const app = readFileSync(new URL('App.vue', SRC), 'utf8')
  assert.match(app, /'dk-content--vollbild':\s*isVollbildMode/,
    '`dk-content--vollbild` hängt nicht am Vollbild-Modus')
})

// ══ U4 · Der Knopf am Handy: Kreis mit „+“ ═════════════════════════════════

test('BEF-KAL-UNTEN/U4: der Handy-Knopf ist rund, trägt nur „+“ und heißt trotzdem „Termin anlegen“', () => {
  const ganz = lies('pages/Kalender.vue')
  const tpl = ganz.slice(0, ganz.indexOf('<script'))

  // Der Knopf ist an der Handy-Lage erkennbar (dieselbe Quelle wie das Layout).
  const knopf = /<button[\s\S]*?class="kal-fab"[\s\S]*?<\/button>/.exec(tpl)
  assert.ok(knopf, 'der schwebende Knopf fehlt')
  assert.match(knopf[0], /:class="\{ 'kal-fab--rund': istHandyLage \}"/,
    'am Handy trägt der Knopf nicht die runde Form — die Pille verdeckt Termine')
  assert.match(knopf[0], /aria-label="Termin anlegen"/,
    'der Name „Termin anlegen“ muss als Vorlesehilfe am Knopf bleiben (nur das + ist zu sehen)')
  // Die Beschriftung erscheint NUR, wo der Knopf keine runde Form hat.
  assert.match(knopf[0], /<span v-if="!istHandyLage">Termin anlegen<\/span>/,
    'die Beschriftung muss am Handy verschwinden (sonst bliebe die Pille)')
  assert.match(knopf[0], /<DkSymbol name="hinzufuegen"/, 'das „+“ ist der vorhandene Symbol-Baustein (UX1g2)')

  // Die runde Form: quadratisch (Breite = Höhe), Kreis über `--badge-r`.
  const css = stil('pages/Kalender.vue')
  const rund = regel(css, '\n.kal-fab--rund {')
  assert.match(rund, /border-radius:\s*var\(--badge-r\)/, 'rund heißt: `--badge-r` (Kreis-Token)')
  assert.match(rund, /width:\s*calc\(var\(--treffer-handy\)[^;]*\)/, 'die Breite kommt aus dem Treffer-Maß')
  const basis = regel(css, '\n.kal-fab {')
  assert.match(basis, /right:\s*var\(--pad\)/, 'der Kreis bleibt rechts am Rand')
  assert.match(basis, /min-height:\s*56px/, 'die Höhe bleibt 56 px (Knopfhöhe)')
  // Kein Rohwert in der runden Form (Abstände/Radien kommen aus Tokens).
  assert.doesNotMatch(rund, /\d+(?:\.\d+)?px/, 'feste px-Werte in der runden Form')
})

test('BEF-KAL-UNTEN/U4: ohne Finger bleibt die Pille mit Beschriftung (Desktop-Nähe, keine Regression)', () => {
  const css = stil('pages/Kalender.vue')
  const rund = regel(css, '\n.kal-fab--rund {')
  // Die runde Form gilt NUR über die Klasse — die Basis-Pille behält ihren
  // Außenabstand und ihre Beschriftung (`padding: 0 var(--sp-5)`).
  assert.ok(!/^\.kal-fab\b/m.test(rund), 'die runde Form überschreibt nicht die Basisregel')
  const basis = regel(css, '\n.kal-fab {')
  assert.match(basis, /padding:\s*0 var\(--sp-5\)/, 'die Pille behält ihre Innenabstände')
})

// ══ U5 · Nachrichten (gleicher Vollbild-Modus) ═════════════════════════════

test('BEF-KAL-UNTEN/U5: Nachrichten halten die Leiste mit demselben Token frei', () => {
  const css = stil('pages/Nachrichten.vue')
  const handy = regel(css, '\n.dk-app--handy .dk-chat {')
  const abstand = /padding-bottom:\s*([^;]+);/.exec(handy)
  assert.ok(abstand, 'die Chat-Seite hat am Handy keinen Fußabstand')
  assert.ok(istLeistenAbstand(abstand[1]),
    `Fußabstand der Chat-Seite ist Leiste + Sicherheitszone (Token), ist aber: ${abstand[1].trim()}`)
  assert.match(handy, /overflow:\s*hidden/, 'die Seite selbst scrollt nicht — der Verlauf rollt innen')
  // Der Verlauf ist der rollende Teil INNEN (Spalte füllt den Rest, Eingabe
  // steht fest): `.dk-chat-verlauf` als Flex-Spalte mit `height: 100%`.
  const verlauf = regel(css, '\n.dk-chat-verlauf {')
  assert.match(verlauf, /flex-direction:\s*column/, 'der Verlauf ist eine Spalte (Kopf · Liste · Eingabe)')
  assert.doesNotMatch(verlauf, /position:\s*fixed/, 'die Eingabe ist kein schwebendes Element — nichts liegt über der Leiste')
  assert.match(css, /\.dk-chat-eingabe \{/, 'die Eingabe bleibt der feste Block unter dem Verlauf')
})

// ══ U6 · Gegenprobe: die Prüfregeln schlagen an der alten Fassung an ═══════

/** Die alte Tagesliste (Stand vor dieser Karte, aus dem Befund rekonstruiert). */
const ALTE_LISTE = `
.kal-a10-liste {
  flex: 1 1 auto;
  min-height: 0;
  height: calc(100vh - var(--topbar-h) - var(--sp-8) - env(safe-area-inset-bottom));
  overflow-y: auto;
  padding-bottom: calc(var(--sp-8) + var(--sp-4));
}
`
/** Der alte Knopf (breite Pille mit Beschriftung). */
const ALTER_KNOPF = `
.kal-fab {
  position: fixed;
  right: var(--pad);
  bottom: calc(var(--sp-8) + env(safe-area-inset-bottom));
  min-height: 56px;
  padding: 0 var(--sp-5);
  border-radius: var(--badge-r);
}
`

test('BEF-KAL-UNTEN/U6: Gegenprobe — der alte Fußabstand (nur --sp-8) fällt durch', () => {
  const liste = regel(ALTE_LISTE, '\n.kal-a10-liste {')
  const abstand = /padding-bottom:\s*([^;]+);/.exec(liste)[1]
  assert.equal(istLeistenAbstand(abstand), false,
    'der Prüfer hält 80 px für „Leiste + Sicherheitszone“ — Gegenprobe ungültig')
  assert.match(liste, /var\(--topbar-h\)/, 'der alte Abzug steht in der Gegenprobe')
})

test('BEF-KAL-UNTEN/U6: Gegenprobe — die alte Pille ist KEIN Kreis ohne Beschriftung', () => {
  // Die alte Form hat keinen quadratischen Anteil und keine Klasse fürs Handy.
  assert.equal(/\n\.kal-fab--rund \{/.test(ALTER_KNOPF), false, 'die Gegenprobe kennt die runde Form schon')
  const alt = regel(ALTER_KNOPF, '\n.kal-fab {')
  assert.equal(/width:\s*calc\(var\(--treffer-handy\)/.test(alt), false,
    'die alte Pille hätte die Prüfung „quadratisch“ bestanden — Gegenprobe ungültig')
  // Und der Prüfer für „Leiste + Sicherheitszone" lehnt 80 px ab (zweite Probe).
  assert.equal(istLeistenAbstand('calc(var(--sp-8) + var(--sp-4))'), false)
  assert.equal(istLeistenAbstand('calc(var(--leiste-unten-h) + env(safe-area-inset-bottom) + var(--sp-4))'), true)
})
