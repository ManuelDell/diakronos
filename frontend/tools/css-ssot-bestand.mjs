/**
 * ON-0b — Bestandsrechner fuer den Vue-Teil der CSS-Single-Source-of-Truth.
 *
 * EIN Rechner fuer Test und Liste: `--schreiben` schreibt die Datei,
 * ohne Schalter gibt er den Bestand als Text aus. Damit koennen Test und
 * Liste nicht auseinanderlaufen.
 *
 * WARUM DIE DATEI HIER LIEGT (frontend/tools/, nicht ../tools/)
 * Der Image-Build fuehrt die Tests in `frontend/` aus (backend/Dockerfile,
 * Stage `frontend`, node --test). Ein Rechner ausserhalb von `frontend/`
 * muesste in den Build-Kontext kopiert werden — und ein Import aus `tests/`
 * wuerde ihn beim Bündeln dorthin kopieren, wonach er das Repo nicht mehr
 * findet (im Image-Build gemessen). Alles, was dieser Rechner braucht
 * (frontend/src, frontend/tools), liegt IN `frontend/`; er rechnet deshalb
 * relativ zu SEINER eigenen Datei. Die eingefrorene Liste steht daneben
 * (css-ssot-bestand.txt).
 *
 * Regeln (Karte ON-0b, F1):
 *   * Geprueft werden ALLE `src/**` mit .vue/.css/.js/.mjs
 *     — AUSSER `src/diakonos/tokens.css` (die Quelle selbst).
 *   * Gezaehlt wird JEDE Fundstelle:
 *       farbe  #rgb/#rrggbb/#rrggbbaa, rgb()/rgba(), hsl()/hsla()
 *       ff     `font-family:` mit konkretem Wert (nicht inherit/var())
 *       font   `font:`-Kurzschreibweise, die einen Schriftnamen nennt
 *              (`font: 12px/1.2 system-ui, sans-serif`), oder eine, die
 *              Anfuehrungszeichen/Komma traegt (`font: 12px/1.2 "Foo Bar"`)
 *              — ON-0c (R4): vorher fiel der letzte Fall durchs Raster
 *   * Inline-Stile (`style="…"`) sind Text wie jeder andere und werden
 *     deshalb mitgezaehlt.
 *   * Ausnahmen (dokumentiert, zaehlen NICHT) stehen in AUSNAHMEN:
 *     Datendaten-Farben — Werte, die aus fremden Daten kommen (Google-,
 *     Kalenderfarben) und keine Gestaltung sind.
 */
import { existsSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

/** `frontend/` — die Wurzel, auf die sich alle Pfade in der Liste beziehen. */
// Der Testbündler (vite.config.mjs) legt diese Datei nach `./build/tools/`
// (im Docker-Build: /build), damit der Pfad auch in `tests/` der Server-Seite
// liegt — die Tests laufen in /build. Die Wurzel ist deshalb NICHT immer
// `..`: der Ordner, der `src/` und `tools/` enthält, gewinnt.
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
export const LISTE = path.join(FRONTEND, 'tools', 'css-ssot-bestand.txt')

/** Die Quelle selbst — hier DUERFEN Rohwerte stehen. */
export const QUELLE = 'frontend/src/diakonos/tokens.css'

/**
 * Dokumentierte Ausnahmen: Datei -> Liste erlaubter Fundstellen-Literale.
 * Jede Fundstelle im Text, die einem Literal entspricht, wird nicht
 * gezaehlt. Nur Datendaten — keine Gestaltung.
 */
export const AUSNAHMEN = {
  // Google-Kalenderfarbe (Markenfarbe des Fremdsystems, kommt so aus der
  // API und wird unveraendert weitergegeben).
  'frontend/src/diakonos/pages/KalenderImport.vue': ['#4285F4'],
  // Kalender-Standardfarben (Datensatz-Farbe je Kalender) und die
  // Darstellungsfarben der Dienst-Monate: Werte aus der Datenbank.
  'frontend/src/diakonos/components/planrahmen/meine-dienste-monate.mjs': [
    '#e0b866',
    '#e0b163',
    '#5b6178',
    '#9ba3c1',
    '#8fb2ff',
  ],
  // Kachelfarben: Zuordnung Kennung -> Farbe, kommt aus den Einstellungen.
  'frontend/src/shared/kachelfarbe.mjs': [
    '#12183a',
    '#2563eb',
    '#db2777',
    '#78716c',
    '#2d78f0',
    '#ee2266',
  ],
  // Kalenderfarbe der Ereignis-Texte (Datenfeld).
  'frontend/src/diakonos/components/kronos/KronosCalendar.vue': ['#12183a'],
}

// Kommentar im JS/CSS: `/* … */` und `// …`. Ein Farbwert in einem Kommentar
// erreicht den Browser nie und ist keine Gestaltung.
const KOMMENTAR = /\/\*[\s\S]*?\*\/|(?:^|\s)\/\/[^\n]*/g

const FARB = /#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(/g
const FF = /font-family\s*:\s*([^;}"']*)/gi
// ON-0c (R4): Der Wert darf Anfuehrungszeichen ENTHALTEN (`"Foo Bar"`,
// `'Foo Bar'`) — vorher endete die Erfassung am ersten Anfuehrungszeichen,
// und `font: 12px/1.2 "Foo Bar"` fiel komplett durchs Raster.
const FSHORT = /\bfont\s*:\s*((?:[^;}"']|"[^"]*"|'[^']*')+)/gi
const KEINE_EIGENE_SCHRIFT = /^\s*(inherit|var\(--[\w-]+\)|revert|unset|initial|normal)\s*$/i
const SCHRIFTNAME =
  /\b(Arial|Helvetica|Inter|Roboto|Georgia|Times|Verdana|Tahoma|system-ui|sans-serif|serif|monospace|ui-monospace|Menlo|Consolas|-apple-system|BlinkMacSystemFont)\b/i

/** Pfad in Listen-Schreibweise (`frontend/src/…`) — Wurzel ist `frontend/`. */
export function relativ(absolut) {
  const pfad = path.relative(FRONTEND, absolut).split(path.sep).join('/')
  // Die Liste nennt Pfade ab der Repo-Wurzel (`frontend/src/…`).
  return `frontend/${pfad}`
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

/**
 * ON-0c (R4): Kurzschreibweise mit ANFUEHRUNGSZEICHEN oder KOMMA zaehlt immer
 * als Schriftwahl — auch wenn kein bekannter Name aus SCHRIFTNAME dabei ist
 * (`font: 12px/1.2 "Foo Bar"`). Vorher fiel genau dieser Fall durchs Raster.
 */
const FSHORT_FAMILIE = /["',]/

/** Alle Fundstellen einer Datei — als Liste der gefundenen Literale. */
export function fundstellen(text) {
  const ohneKommentar = text.replace(KOMMENTAR, ' ')
  const treffer = []
  for (const m of ohneKommentar.matchAll(FARB)) treffer.push(m[0])
  for (const m of ohneKommentar.matchAll(FF)) {
    if (!KEINE_EIGENE_SCHRIFT.test(m[1])) treffer.push(`font-family:${m[1].trim()}`)
  }
  for (const m of ohneKommentar.matchAll(FSHORT)) {
    // Ein Treffer, der schon als `font-family:` erfasst wurde, zaehlt nicht
    // doppelt: der Ausdruck `\bfont\s*:` verlangt den Doppelpunkt direkt nach
    // `font`, `font-family:` hat dort einen Bindestrich — es gibt also keinen
    // Ueberschneidungsfall.
    if (SCHRIFTNAME.test(m[1]) || FSHORT_FAMILIE.test(m[1])) {
      treffer.push(`font:${m[1].trim()}`)
    }
  }
  return treffer
}

/** Gezaehlte Fundstellen je Datei (Ausnahmen abgezogen). */
export function bestand() {
  const werte = new Map()
  for (const p of dateien(SRC)) {
    const rel = relativ(p)
    if (`frontend/${path.relative(FRONTEND, p).split(path.sep).join('/')}` === QUELLE) continue
    if (rel.endsWith('.test.mjs')) continue
    const text = readFileSync(p, 'utf8')
    const erlaubt = AUSNAHMEN[rel] || []
    const zahl = fundstellen(text).filter((t) => !erlaubt.some((a) => t.includes(a))).length
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

const KOPF = `# ON-0b — eingefrorener Bestand fester Farb-/Schriftwerte im Frontend.
#
# Geprueft: ALLE frontend/src/** (.vue/.css/.js/.mjs) AUSSER
#           frontend/src/diakonos/tokens.css (die Quelle selbst).
# Format:   relativer/pfad\tnzahl_fundstellen
# Fundstelle = #rgb/#rrggbb/#rrggbbaa | rgb()/rgba() | hsl()/hsla() |
#              \`font-family:\` mit konkretem Wert (nicht inherit/var(--…)) |
#              \`font:\`-Kurzschreibweise mit Schriftnamen. Inline-Stile zaehlen mit.
#
# REGEL (Karte ON-0b, F2): Diese Liste darf NUR SCHRUMPFEN.
#   * hoehere Zahl oder neuer Eintrag       -> rot
#     (frontend/tests/on0b-css-ssot.test.mjs)
#   * behobene Fundstelle nicht nachgezogen -> rot
# Erzeugt mit (aus frontend/ heraus): node tools/css-ssot-bestand.mjs --schreiben
#
# Dokumentierte Ausnahmen (Datendaten, keine Gestaltung — zaehlen nicht):
`

export function alsText() {
  const jetzt = bestand()
  const ausnahmen = Object.entries(AUSNAHMEN)
    .map(([datei, werte]) => `#   ${datei}: ${werte.join(', ')}`)
    .join('\n')
  const zeilen = [...jetzt].map(([pfad, zahl]) => `${pfad}\t${zahl}`).join('\n')
  const summe = [...jetzt.values()].reduce((a, b) => a + b, 0)
  return `${KOPF}${ausnahmen}\n#\n# Stand (ON-0b, eingefroren): ${summe} Fundstellen in ${jetzt.size} Dateien.\n${zeilen}\n`
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const text = alsText()
  if (process.argv.includes('--schreiben')) writeFileSync(LISTE, text)
  process.stdout.write(text)
}
