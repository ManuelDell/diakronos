/**
 * UX1a — Bestandsrechner fuer feste Abstands-, Rahmen- und Radius-Werte.
 * UX1a2 (F5) — Waechter-Luecken geschlossen.
 *
 * Zwei Rechner in einer Datei, nach dem Muster von ON-0b
 * (`css-ssot-bestand.mjs`): `--schreiben` schreibt die eingefrorene Liste,
 * ohne Schalter gibt der Rechner den Bestand als Text aus. Test und Liste
 * koennen dadurch nicht auseinanderlaufen.
 *
 * WAS GEZAHLT WIRD (Karte UX1a A2/A3, erweitert in UX1a2 F5)
 * ---------------------------------------------------------
 * Gezaehlt wird jede EIGENSCHAFT aus der Menge in `EIGENSCHAFTEN`
 * in ALLEN ihren Langformen (UX1a2 F5 — vorher fehlten 15 Formen, in denen
 * Abstaende unsichtbar blieben):
 *
 *   margin / margin-top / -right / -bottom / -left
 *   margin-inline / -block, margin-inline-start / -end, -block-start / -end
 *   padding / padding-top / … / padding-block-end (dieselben acht Formen)
 *   inset / inset-block / inset-inline / inset-block-start … -inline-end
 *   row-gap / column-gap / gap
 *   top / right / bottom / left
 *   border(+ -top|-right|-bottom|-left)(+ -width)
 *   border-radius(+-top-left|-top-right|-bottom-left|-bottom-right)
 *
 * wenn IHR WERT einen festen Laengenwert enthaelt: px/rem/em/… ungleich 0.
 * Je Eigenschaft zaehlt EINE Fundstelle, auch wenn der Wert mehrere feste
 * Zahlen traegt (`margin: 4px 8px` ist eine Fundstelle, nicht zwei).
 *
 * Kurzschreibweisen sind eingeschlossen, weil `border: 1px solid var(--x)`
 * genau so ein fester Wert ist wie `border-width: 1px` (Auflage des
 * Orchestrators). Inline-Stile (`style="…"`) werden wie in ON-0b mitgezaehlt.
 * `:style`-BINDUNGEN MIT TEXT (`:style="{ padding: '4px' }"`) sind seit
 * UX1a2 F5 erfasst: der Wert bricht nicht mehr am Anfuehrungszeichen ab.
 *
 * ERLAUBT (zaehlen nicht):
 *   0            (`margin: 0` ist kein Abstand), auch `0px`, `0.0rem`
 *   auto         (`margin: 0 auto`)
 *   %            (`padding-inline: 10%`)
 *   var(--…)     (auch mitten im Wert: `border: 1px solid var(--rahmen-farbe)`
 *                 zaehlt NUR wegen der 1px — steht dort kein fester Wert,
 *                 ist die Deklaration sauber)
 *   calc()/clamp()/min()/max() aus var(--…) und Zahlen ohne Einheit
 *   Vorgabewerte: inherit, initial, unset, revert, none, normal,
 *   thin/medium/thick
 *
 * GEGENPROBEN (UX1a2 F5, im Test festgehalten): `-4px`/`-0.5rem` (negatives
 * Mass) zaehlen, `.5rem` (ohne fuehrende Null) zaehlt, `margin-top: 4px`
 * zaehlt, `:style="{ padding: '4px' }"` zaehlt; `calc(var(--sp-1) * -1)`
 * zaehlt NICHT (die Zahlen sind Tokens/Operatoren, kein Rohmass).
 *
 * GEPRUEFTE QUELLEN
 *   * `frontend/src/**` (.vue/.css/.js/.mjs), AUSSER
 *     `frontend/src/diakonos/tokens.css` (die Quelle selbst)
 *   * `frontend/src/ssot/seiten.css` (A3, Server-Seiten-Rahmen) — liegt
 *     bereits in `src/` und ist damit abgedeckt.
 *
 * WARUM DIE DATEI IN `frontend/tools/` LIEGT
 * Wie bei ON-0b: der Image-Build fuehrt die Tests in `frontend/` aus
 * (backend/Dockerfile, Stage `frontend`, node --test). Alles, was dieser
 * Rechner braucht, liegt IN `frontend/`; er rechnet relativ zu SEINER Datei.
 */
import { existsSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

/** Die Wurzel `frontend/` — Ordner, der `src/` und `tools/` enthaelt. */
function findeWurzel() {
  const start = path.dirname(fileURLToPath(import.meta.url))
  let dir = start
  for (let i = 0; i < 3; i += 1) {
    if (existsSync(path.join(dir, 'src')) && existsSync(path.join(dir, 'tools'))) return dir
    dir = path.dirname(dir)
  }
  return path.resolve(start, '..')
}

export const FRONTEND = findeWurzel()
export const SRC = path.join(FRONTEND, 'src')
export const LISTE = path.join(FRONTEND, 'tools', 'abstand-bestand.txt')

/** Die Quelle selbst — hier DUERFEN Rohwerte stehen. */
export const QUELLE = 'frontend/src/diakonos/tokens.css'

/**
 * Die Eigenschaften, deren Werte aus der Skala kommen muessen.
 * Reihenfolge/Laenge ist Teil des Vertrags: eine neue Eigenschaft hier
 * aufzunehmen macht den Bestand sichtbar groesser — das ist eine
 * Entscheidung (Karte), kein Nebeneffekt.
 *
 * UX1a2 (F5): die Langformen sind vollstaendig — physikalische und logische
 * Seiten, dazu die `inset`-Familie. Vorher fehlten margin-top/-right/-bottom/
 * -left, padding-*, margin-/padding-inline|block(-start|-end) und inset-*
 * (15 Formen, in denen Abstaende unsichtbar blieben).
 */
export const EIGENSCHAFTEN = [
  // Abstaende: Kurzform + physikalische und logische Langformen
  'margin',
  'margin-top',
  'margin-right',
  'margin-bottom',
  'margin-left',
  'margin-inline',
  'margin-inline-start',
  'margin-inline-end',
  'margin-block',
  'margin-block-start',
  'margin-block-end',
  'padding',
  'padding-top',
  'padding-right',
  'padding-bottom',
  'padding-left',
  'padding-inline',
  'padding-inline-start',
  'padding-inline-end',
  'padding-block',
  'padding-block-start',
  'padding-block-end',
  // Abstand zwischen Kindern
  'gap',
  'row-gap',
  'column-gap',
  // Lage (Abstand zur Kante)
  'inset',
  'inset-block',
  'inset-block-start',
  'inset-block-end',
  'inset-inline',
  'inset-inline-start',
  'inset-inline-end',
  'top',
  'right',
  'bottom',
  'left',
  // Rahmen
  'border',
  'border-width',
  'border-top',
  'border-top-width',
  'border-right',
  'border-right-width',
  'border-bottom',
  'border-bottom-width',
  'border-left',
  'border-left-width',
  // Radien
  'border-radius',
  'border-top-left-radius',
  'border-top-right-radius',
  'border-bottom-left-radius',
  'border-bottom-right-radius',
]

/** Namen, laengste zuerst — sonst gewaenne `margin` gegen `margin-top`. */
const NACH_LAENGE = [...EIGENSCHAFTEN].sort((a, b) => b.length - a.length)

/**
 * Eine Deklaration: `eigenschaft: wert`.
 *
 * Der Wert laeuft bis zum naechsten `;`, `{` oder `}`. Anfuehrungszeichen
 * beenden ihn NICHT mehr — sonst waere `:style="{ padding: '4px' }"`
 * (UX1a2 F5) unsichtbar. Der Zeichenvorrat der Wertklasse ist auf alles
 * ausser diesen drei Zeichen gesetzt; ein Objekt-Literal liefert damit
 * hoechstens `4px'` als Wert — genau das, was `wertIstFest` lesen soll.
 */
const EIGEN_MUSTER = new RegExp(
  `(?<![\\w-])(${NACH_LAENGE.map((e) => e.replace(/-/g, '\\-')).join('|')})\\s*:\\s*([^;{}]+)`,
  'gi',
)

/**
 * Ein fester Laengenwert: Zahl + Einheit, ungleich 0.
 * `0px` ist 0 und damit erlaubt; `0.5rem`, `.5rem` und `-4px` sind fest.
 *
 * Das fuehrende Minus gehoert zum Treffer (UX1a2 F5: negative Werte
 * zaehlen mit). Davor darf kein Wortzeichen stehen; ein Punkt ist erlaubt,
 * damit `.5rem` (ohne fuehrende Null) erkannt wird.
 */
const FESTE_LAENGE = /(?<![a-z0-9_])(-?(?:\d+(?:\.\d+)?|\.\d+))(px|rem|em|pt|pc|cm|mm|in|ex|ch|q)\b/gi
const NULL = /^-?0+(?:\.0+)?$/

// Kommentare erreichen den Browser nie — sie sind keine Gestaltung.
// `/* … */` und `//`-Zeilen (JS/MJS), aber NICHT `https://` (Doppelpunkt
// davor) — sonst wuerde eine URL den Rest der Zeile verschlucken.
const KOMMENTAR = /\/\*[\s\S]*?\*\/|(?:^|[\s;{}])\/\/[^\n]*/g

/** Ist EIN Laengenwert fest (nicht 0, nicht aus einem Token)? */
function istFest(zahl) {
  return !NULL.test(zahl)
}

/**
 * Traegt ein Deklarationswert einen festen Laengenwert?
 * `var(--… )` und `calc(…)` ueber Tokens sind erlaubt; steht in `calc()`
 * eine nackte Zahl, ist das wieder ein fester Wert.
 *
 * UX1a2 (F5) — zwei Ergaenzungen:
 *   1. Anfuehrungszeichen werden entfernt, damit `'4px'` aus einer
 *      `:style`-Bindung als 4px gelesen wird.
 *   2. `calc(var(--sp-1) * -1)` ist ERLAUBT: die Klammer enthaelt ein Token,
 *      die Zahlen darin sind Operatoren ohne Einheit. `calc(100% - 4px)`
 *      bleibt dagegen ein fester Wert (kein var darin) — die Klammer zaehlt
 *      dann normal mit.
 */
export function wertIstFest(wert) {
  const ohneVar = wert
    .replace(/var\(--[\w-]+(?:\s*,[^)]*)?\)/gi, ' ')
    .replace(/(?:calc|clamp|min|max)\([^()]*(?:\([^()]*\)[^()]*)*\)/gi, (m) =>
      /var\(--/i.test(m) ? ' ' : m,
    )
    .replace(/['"]/g, '')
  if (/\b(auto|inherit|initial|unset|revert|revert-layer|none|normal|thin|medium|thick)\b/i.test(ohneVar)) {
    // Steht daneben noch eine feste Laenge, bleibt es ein fester Wert.
    for (const m of ohneVar.matchAll(FESTE_LAENGE)) {
      if (istFest(m[1])) return true
    }
    return false
  }
  for (const m of ohneVar.matchAll(FESTE_LAENGE)) {
    if (istFest(m[1])) return true
  }
  return false
}

/**
 * Alle Fundstellen eines Textes — je Eigenschaft ein Eintrag.
 * Rueckgabe: `[{ eigenschaft, wert }]` (Wert gekuerzt, fuer Meldungen).
 */
export function fundstellen(text) {
  const ohneKommentar = text.replace(KOMMENTAR, ' ')
  const treffer = []
  for (const m of ohneKommentar.matchAll(EIGEN_MUSTER)) {
    const wert = m[2].trim()
    if (!wertIstFest(wert)) continue
    treffer.push({ eigenschaft: m[1].toLowerCase(), wert })
  }
  return treffer
}

/** Pfad in Listen-Schreibweise (`frontend/src/…`) — Wurzel ist `frontend/`. */
export function relativ(absolut) {
  return `frontend/${path.relative(FRONTEND, absolut).split(path.sep).join('/')}`
}

function* dateien(dir) {
  for (const name of readdirSync(dir)) {
    const p = path.join(dir, name)
    const st = statSync(p)
    if (st.isDirectory()) {
      if (name === 'node_modules' || name === 'dist') continue
      yield* dateien(p)
    } else if (/\.(vue|css|js|mjs)$/.test(name)) yield p
  }
}

/** Gezaehlte Fundstellen je Datei (nur Dateien mit > 0). */
export function bestand() {
  const werte = new Map()
  for (const p of dateien(SRC)) {
    const rel = relativ(p)
    if (rel === QUELLE) continue
    if (rel.endsWith('.test.mjs')) continue
    const zahl = fundstellen(readFileSync(p, 'utf8')).length
    if (zahl > 0) werte.set(rel, zahl)
  }
  return new Map([...werte].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)))
}

/** Die eingefrorene Liste lesen (Datei darf fehlen -> leer). */
export function liesBestand(datei = LISTE) {
  let text = ''
  try {
    text = readFileSync(datei, 'utf8')
  } catch {
    return new Map()
  }
  const werte = new Map()
  for (const zeile of text.split('\n')) {
    const z = zeile.trim()
    if (!z || z.startsWith('#')) continue
    const [pfad, zahl] = z.split('\t')
    if (!pfad || !/^\d+$/.test((zahl || '').trim())) continue
    werte.set(pfad.trim(), Number(zahl.trim()))
  }
  return werte
}

const KOPF = `# UX1a — eingefrorener Bestand fester Abstands-/Rahmen-/Radius-Werte.
# UX1a2 (F5): Waechter-Luecken geschlossen — Langformen (margin-top/-right/
#             -bottom/-left, padding-*, margin-/padding-inline|block(-start|-end),
#             inset-*), negative Werte (-4px), Werte ohne fuehrende Null (.5rem)
#             und :style-Bindungen mit Text ('4px') zaehlen jetzt mit.
#
# Geprueft: ALLE frontend/src/** (.vue/.css/.js/.mjs) AUSSER
#           frontend/src/diakonos/tokens.css (die Quelle selbst).
# Format:   relativer/pfad\tnzahl_fundstellen
# Fundstelle = eine der Eigenschaften margin*/padding*/gap/row-gap/column-gap/
#              inset*/top/right/bottom/left/border*/border-radius* in jeder
#              Langform, mit einem FESTEN Laengenwert (px/rem/em/… != 0).
#              Kurzschreibweisen (border: 1px solid …) und Inline-Stile zaehlen mit.
#              Erlaubt: 0, auto, %, var(--…), calc() aus var(--…).
#
# REGEL (Karte UX1a, A2): Diese Liste darf NUR SCHRUMPFEN.
#   * hoehere Zahl oder neuer Eintrag       -> rot
#     (frontend/tests/ux1a-abstand-tokens.test.mjs)
#   * behobene Fundstelle nicht nachgezogen -> rot
#   * neue Datei mit festen Werten          -> rot (nicht in der Liste = 0 erlaubt)
# Erzeugt mit (aus frontend/ heraus): node tools/abstand-bestand.mjs --schreiben
`

export function alsText() {
  const jetzt = bestand()
  const zeilen = [...jetzt].map(([pfad, zahl]) => `${pfad}\t${zahl}`).join('\n')
  const summe = [...jetzt.values()].reduce((a, b) => a + b, 0)
  return `${KOPF}#\n# Stand (UX1a2, F5): ${summe} Fundstellen in ${jetzt.size} Dateien.\n${zeilen}\n`
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const text = alsText()
  if (process.argv.includes('--schreiben')) writeFileSync(LISTE, text)
  process.stdout.write(text)
}
