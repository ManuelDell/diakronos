/**
 * UX1b — Bestandsrechner fuer feste Schriftgroessen und -gewichte.
 *
 * Nach dem Muster von ON-0b (`css-ssot-bestand.mjs`) und UX1a
 * (`abstand-bestand.mjs`): `--schreiben` schreibt die eingefrorene Liste,
 * ohne Schalter gibt der Rechner den Bestand als Text aus. Test und Liste
 * koennen dadurch nicht auseinanderlaufen.
 *
 * WAS GEZAHLT WIRD (Karte UX1b B2)
 * --------------------------------
 * Je Fundstelle EIN Zaehler, in `frontend/src/**` (.vue/.css/.js/.mjs),
 * AUSSER `frontend/src/diakonos/tokens.css` (die Quelle selbst):
 *
 *   font-size       mit einem FESTEN Wert: eine Zahl mit Laengeneinheit
 *                   (px/rem/em/pt/…) ungleich 0
 *   font-weight     mit einer FESTEN Zahl ungleich 0 (die Einheit fehlt hier
 *                   von Natur aus — `600` ist so fest wie `13px`)
 *   font            Kurzschreibweise MIT Groesse (`font: 600 14px/1.4 …`)
 *                   — sie traegt zwei Entscheidungen auf einmal
 *   font-variant-numeric
 *                   mit festem Wert (`tabular-nums`) — das ist seit UX1b
 *                   eine Token-Entscheidung (`--fs-tabular`)
 *
 * ERLAUBT (zaehlen nicht):
 *   var(--…)          jede Form (`font-size: var(--fs-sm)`)
 *   inherit, initial, unset, revert, revert-layer, smaller, larger, normal,
 *   bolder, lighter, medium, bold(→ zaehlt, siehe unten), 0, 0px, 0rem
 *   calc()/clamp()/min()/max() AUSSCHLIESSLICH aus var(--…) und Zahlen ohne
 *   Einheit
 *   Kommentare (`/* … *​/`, `// …`)
 *
 * GEGENPROBEN (im Test festgehalten, `ux1b-schriften.test.mjs`):
 *   13px, .5rem, -2px          -> zaehlen (fester Wert)
 *   0, 0px, var(--fs-sm)       -> zaehlen NICHT
 *   font-weight: 600, bold     -> zaehlen (bold = 700, keine Stufe)
 *   font-weight: var(--fw-h)   -> zaehlt NICHT
 *   :style-Bindungen mit Text  -> zaehlen mit
 *
 * WARUM DIE DATEI IN `frontend/tools/` LIEGT
 * Der Image-Build fuehrt die Tests in `frontend/` aus (backend/Dockerfile,
 * Stage `frontend`, node --test). Alles, was dieser Rechner braucht, liegt IN
 * `frontend/`; er rechnet relativ zu SEINER eigenen Datei.
 */
import { existsSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

/** `frontend/` — Ordner, der `src/` und `tools/` enthaelt. */
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
export const LISTE = path.join(FRONTEND, 'tools', 'schrift-bestand.txt')

/** Die Quelle selbst — hier DUERFEN Rohwerte stehen. */
export const QUELLE = 'frontend/src/diakonos/tokens.css'

/** Die Eigenschaften, die geprueft werden. */
export const EIGENSCHAFTEN = ['font-size', 'font-weight', 'font', 'font-variant-numeric']

/** Eine Deklaration `eigenschaft: wert` bis `;`, `{` oder `}`. */
const EIGEN_MUSTER = new RegExp(
  `(?<![\\w-])(${EIGENSCHAFTEN.map((e) => e.replace(/-/g, '\\-')).join('|')})\\s*:\\s*([^;{}]+)`,
  'gi',
)

/** Ein fester Laengenwert: Zahl + Einheit (px/rem/em/…) ungleich 0. */
const FESTE_LAENGE = /(?<![a-z0-9_])(-?(?:\d+(?:\.\d+)?|\.\d+))(px|rem|em|pt|pc|cm|mm|in|ex|ch|q)\b/gi
/** Eine feste Zahl OHNE Einheit (font-weight) ungleich 0 — `bold` gleich mit. */
const FESTE_ZAHL = /(?<![a-z0-9_.#-])(-?(?:\d+(?:\.\d+)?|\.\d+))(?![\w%])/i
const SCHLUESSELWORT_FETT = /\b(bold|bolder|lighter)\b/i
const NULL = /^-?0+(?:\.0+)?$/

// Kommentare erreichen den Browser nie — sie sind keine Gestaltung.
// `/* … *​/` und `//`-Zeilen, aber NICHT `https://` (Doppelpunkt davor).
const KOMMENTAR = /\/\*[\s\S]*?\*\/|(?:^|[\s;{}])\/\/[^\n]*/g

/** Ist EIN Laengenwert fest (nicht 0)? */
function istFest(zahl) {
  return !NULL.test(zahl)
}

/**
 * Traegt ein Deklarationswert einen festen Schrift-Wert?
 * `var(--…)` und `calc(…)` ueber Tokens sind erlaubt; steht in `calc()` eine
 * nackte Zahl MIT Einheit, ist das wieder ein fester Wert.
 */
export function wertIstFest(eigenschaft, wert) {
  const art = eigenschaft.toLowerCase()
  // Anfuehrungszeichen weg: `:style="{ fontSize: '13px' }"`.
  const ohneVar = String(wert)
    .replace(/var\(--[\w-]+(?:\s*,[^)]*)?\)/gi, ' ')
    .replace(/(?:calc|clamp|min|max)\([^()]*(?:\([^()]*\)[^()]*)*\)/gi, (m) =>
      /var\(--/i.test(m) ? ' ' : m,
    )
    .replace(/['"]/g, ' ')

  if (art === 'font-weight') {
    if (SCHLUESSELWORT_FETT.test(ohneVar)) return true
    const m = FESTE_ZAHL.exec(ohneVar)
    return Boolean(m && istFest(m[1]))
  }
  if (art === 'font-variant-numeric') {
    // `tabular-nums`, `lining-nums`, `normal` — alles fest; `var(--…)` ist
    // oben schon entfernt und trifft hier als Leerraum ein.
    return /[a-z]/i.test(ohneVar)
  }
  if (art === 'font') {
    // Nur die Kurzschreibweise MIT Groesse ist eine Schriftgroessen-Fundstelle.
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

/** Alle Fundstellen eines Textes — `[{ eigenschaft, wert }]`. */
export function fundstellen(text) {
  const ohneKommentar = text.replace(KOMMENTAR, ' ')
  const treffer = []
  for (const m of ohneKommentar.matchAll(EIGEN_MUSTER)) {
    const wert = m[2].trim()
    if (!wertIstFest(m[1], wert)) continue
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

const KOPF = `# UX1b — eingefrorener Bestand fester Schriftgroessen und -gewichte.
#
# Geprueft: ALLE frontend/src/** (.vue/.css/.js/.mjs) AUSSER
#           frontend/src/diakonos/tokens.css (die Quelle selbst).
# Format:   relativer/pfad\tnzahl_fundstellen
# Fundstelle = \`font-size\` mit festem Laengenwert (px/rem/… != 0) |
#              \`font-weight\` mit fester Zahl (600, 650, bold …) |
#              \`font\`-Kurzschreibweise MIT Groesse |
#              \`font-variant-numeric\` mit festem Wert (tabular-nums).
#              Erlaubt: 0, var(--…), calc() aus var(--…). Inline-Stile zaehlen mit.
#
# REGEL (Karte UX1b B2): Diese Liste darf NUR SCHRUMPFEN.
#   * hoehere Zahl oder neuer Eintrag       -> rot
#     (frontend/tests/ux1b-schriften.test.mjs)
#   * behobene Fundstelle nicht nachgezogen -> rot
#   * neue Datei mit festen Werten          -> rot (nicht in der Liste = 0 erlaubt)
# Die fuenf Groessen (12/14/16/20/26) und drei Gewichte (400/500/600) stehen
# als Tokens in tokens.css; Komponenten schreiben \`var(--fs-…)\`/\`var(--fw-…)\`.
# Erzeugt mit (aus frontend/ heraus): node tools/schrift-bestand.mjs --schreiben
`

export function alsText() {
  const jetzt = bestand()
  const zeilen = [...jetzt].map(([pfad, zahl]) => `${pfad}\t${zahl}`).join('\n')
  const summe = [...jetzt.values()].reduce((a, b) => a + b, 0)
  return `${KOPF}#\n# Stand (UX1b, eingefroren): ${summe} Fundstellen in ${jetzt.size} Dateien.\n${zeilen}\n`
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const text = alsText()
  if (process.argv.includes('--schreiben')) writeFileSync(LISTE, text)
  process.stdout.write(text)
}
