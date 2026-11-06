/**
 * UX1e — Bestandsrechner fuer den Alt-Knopf im Kalender-/Moderationsbereich.
 *
 * Zaehlt je Datei die Fundstellen der ALTEN Knopfklassen, die Karte UX1e auf
 * `<DkButton>` umstellt:
 *
 *   .dk-btn*         Klassen der Alt-Knopfreihe aus index.css
 *   .btn-*           Modal-Knopfreihe aus kronos.css (`btn btn-secondary` …)
 *   <button ...>     rohe Knopfelemente mit eigener Klasse im Bereich
 *
 * EIN Rechner fuer Test und Liste: `--schreiben` schreibt die Liste, ohne
 * Schalter gibt er den Bestand als Text aus. Test und Liste koennen so nicht
 * auseinanderlaufen.
 *
 * WARUM DIE DATEI HIER LIEGT (frontend/tools/, nicht ../tools/)
 * Der Image-Build fuehrt die Tests in `frontend/` aus (backend/Dockerfile,
 * Stage `frontend`, node --test). Alles, was der Rechner braucht
 * (frontend/src, frontend/tools), liegt IN `frontend/`; er rechnet deshalb
 * relativ zu SEINER eigenen Datei.
 *
 * REGEL: Die Liste darf NUR SCHRUMPFEN. Eine hoehere Zahl oder ein neuer
 * Eintrag macht `frontend/tests/ux1e-knopf-system.test.mjs` rot; eine
 * behobene Stelle, die nicht nachgezogen wurde, ebenso.
 */
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

/** `frontend/` — die Wurzel, auf die sich alle Pfade in der Liste beziehen. */
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
export const LISTE = path.join(FRONTEND, 'tools', 'ux1e-knopf-bestand.txt')

/**
 * Der Bereich, den Karte UX1e umstellt: Kalender- und Moderationsbausteine,
 * die Kalender-Seiten. Die Plan-Rahmen-Seiten und der Rest folgen in
 * spaeteren Karten (UX1e ist Teil 1).
 */
export const BEREICH = [
  'frontend/src/diakonos/components/kronos/',
  'frontend/src/diakonos/pages/Kalender.vue',
  'frontend/src/diakonos/pages/KalenderImport.vue',
  'frontend/src/diakonos/pages/KalenderVerwaltung.vue',
  'frontend/src/diakonos/pages/Moderation.vue',
]

// Kommentar im JS/CSS/Vue: `/* … */`, `// …` und `<!-- … -->`. Eine
// Klassenliste in einem Kommentar ist keine Fundstelle — sie wird nie
// gerendert, und der Bestand soll nur die Stellen zaehlen, die man auch
// beheben kann.
//
// HTML-Kommentare MUESSEN mit: in den Bausteinen stehen auskommentierte
// Knopfzeilen (`<!-- <button class="btn btn-secondary">…`), die sonst als
// Alt-Knopf mitgezaehlt wuerden, obwohl sie niemand sieht.
const KOMMENTAR = /\/\*[\s\S]*?\*\/|<!--[\s\S]*?-->|(?:^|\s)\/\/[^\n]*/g

/** Fundstelle = eine dieser Klassen in einem `class`-Attribut oder Ausdruck. */
const DK_BTN = /\bdk-btn(?:-[\w-]+)?\b/g
// `(?<![\w-])` haelt `dk-btn` und `sidebar-import-btn` aussen vor: die
// gehoeren zur Familie `dk-btn*` bzw. sind Eigenklassen ohne Alt-Knopfreihe.
// Sie werden unten als eigene Familien gezaehlt.
const BTN = /(?<![\w-])btn(?!-\w*btn)(?:-[\w-]+)?\b/g
// Eigene Knopfklassen der Bausteine, die in UX1e ebenfalls auf DkButton
// gehen (`.dk-mcard-resolve-btn`, `.sidebar-import-btn`, `.add-row-btn`).
const EIGEN = /(?<![\w-])[\w-]*-(?:btn|button)\b/g
// Ausnahmen: reine Behaelter-/Strukturklassen, keine Knoepfe.
const KEINE_KNOEPFE = new Set(['diakronos-close-btn', 'close-btn'])
// UX1f: KNOPF-SYSTEM-Klassen zaehlen nicht als Alt-Knopf: `DkButton` rendert
// selbst `class="dk-ui-btn dk-ui-btn--primary …"`. Stuende so ein Element in
// einer Vorlage, waere es eine FALSCHE Fundstelle — das Gegenteil dessen, was
// die Liste misst. Die Umstellung selbst prueft der Test ueber `<button>`
// ohne Baustein.
const SYSTEM = /^dk-ui-btn[\w-]*$/

/** Pfad in Listen-Schreibweise (`frontend/src/…`). */
export function relativ(absolut) {
  const p = path.relative(FRONTEND, absolut).split(path.sep).join('/')
  return `frontend/${p}`
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

export function imBereich(rel) {
  return BEREICH.some((b) => (b.endsWith('/') ? rel.startsWith(b) : rel === b))
}

/** Ohne Kommentare — was uebrig bleibt, wird gerendert. */
export function ohneKommentare(text) {
  return String(text).replace(KOMMENTAR, ' ')
}

/**
 * Alle Fundstellen einer Quelldatei.
 * @param {string} text
 * @returns {string[]} die gefundenen Klassen (mehrfach, je Vorkommen)
 */
/**
 * Alle Fundstellen einer Quelldatei.
 *
 * Gezaehlt wird nur, was wirklich ein Knopf IST:
 *   * `class`-Attribute, deren Wert eine Klasse der Familien `btn*`,
 *     `dk-btn*` oder `*-btn`/`*-button` enthaelt, und
 *   * rohe `<button>`-Elemente ohne Baustein (der Umbau auf `DkButton`).
 * Reine CSS-Regeln (`.nav-btn { … }`, Media-Queries) und Klassennamen, die
 * nur als `*-btn-label`/`*-btn-icon` auftauchen, sind keine Knoepfe mehr und
 * zaehlen nicht — sonst waere die Zahl an die Gestaltung gekoppelt.
 *
 * @param {string} text
 * @returns {string[]}
 */
export function fundstellen(text) {
  const quelle = ohneKommentare(text)
  const treffer = []
  // 1) class-Attribut (statisch oder gebunden) auslesen.
  for (const m of quelle.matchAll(/\bclass\s*=\s*(?:"([^"]*)"|'([^']*)'|\{([^}]*)\})/g)) {
    const roh = m[1] != null ? m[1] : m[2] != null ? m[2] : m[3]
    for (const name of roh.split(/[\s"'`+,:]+/)) {
      if (!name) continue
      if (KEINE_KNOEPFE.has(name)) continue
      if (SYSTEM.test(name)) continue
      if (DK_BTN.test(name) || BTN.test(name) || EIGEN.test(name)) {
        // `xxx-btn-label` / `xxx-btn-icon` sind Beschriftung und Symbol,
        // nicht der Knopf selbst — der Knopf traegt die Klasse ohne Suffix.
        if (/-(label|icon|text|wrapper|gruppe|group|reihe|row|leiste|bar)$/.test(name)) continue
        DK_BTN.lastIndex = 0
        BTN.lastIndex = 0
        EIGEN.lastIndex = 0
        treffer.push(name)
      }
    }
    DK_BTN.lastIndex = 0
    BTN.lastIndex = 0
    EIGEN.lastIndex = 0
  }
  // 2) rohe Knopfelemente ohne Knopfklasse: das System kennt nur DkButton.
  for (const m of quelle.matchAll(/<button\b([^>]*)>/g)) {
    const attr = m[1]
    const klassen = /class\s*=\s*("([^"]*)"|'([^']*)')/.exec(attr)
    const wert = klassen ? (klassen[2] != null ? klassen[2] : klassen[3]) : ''
    // Eine Klasse des neuen Systems (`dk-ui-btn`) macht aus dem rohen Element
    // zwar kein altes, aber das System ist es auch nicht: ein `<button>` bleibt
    // ein roher Knopf und damit eine Fundstelle.
    if (!wert.trim()) treffer.push('<button>')
  }
  return treffer
}

/**
 * Gezaehlte Fundstellen je Datei unterhalb `wurzel`, gefiltert mit `pruefung`.
 *
 * EIN Rechner fuer alle Knopf-Karten (UX1e: Kalender, UX1f: Personen, Gruppen,
 * Registrierung, Gast): die Bereiche unterscheiden sich, die Zaehlweise nicht.
 * Sortiert, damit zwei Laeufe dieselbe Liste ergeben.
 *
 * @param {string} wurzel             z. B. `frontend/src`
 * @param {(rel: string) => boolean} pruefung  Pfad in Listen-Schreibweise
 * @returns {Map<string, number>}
 */
export function dateienImBereich(wurzel, pruefung) {
  const werte = new Map()
  for (const p of dateien(wurzel)) {
    const rel = relativ(p)
    if (!pruefung(rel)) continue
    if (rel.endsWith('.test.mjs')) continue
    const zahl = fundstellen(readFileSync(p, 'utf8')).length
    if (zahl > 0) werte.set(rel, zahl)
  }
  return new Map([...werte].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)))
}

/** Gezaehlte Fundstellen je Datei (nur der Bereich, nur > 0). */
export function bestand() {
  return dateienImBereich(SRC, imBereich)
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

/**
 * Prueft „nur schrumpfen“ und liefert die Verstoesse als Textzeilen.
 * Ohne Argumente gegen die eigene Liste (Kalenderbereich, UX1e) — andere
 * Karten reichen ihre eigene Karte hinein (`ux1f-knopf-bestand.mjs`).
 */
export function verstoesse(jetzt = bestand(), frueher = liesBestand()) {
  const fehler = []
  for (const [pfad, zahl] of jetzt) {
    if (!frueher.has(pfad)) fehler.push(`${pfad}: neuer Eintrag (${zahl}) — neue Alt-Knoepfe sind nicht zulaessig`)
    else if (zahl > frueher.get(pfad)) fehler.push(`${pfad}: ${frueher.get(pfad)} -> ${zahl} gewachsen`)
  }
  for (const [pfad, zahl] of frueher) {
    if (!jetzt.has(pfad)) fehler.push(`${pfad}: ${zahl} -> 0 behoben, aber nicht in der Liste nachgezogen`)
    else if (jetzt.get(pfad) < zahl) fehler.push(`${pfad}: ${zahl} -> ${jetzt.get(pfad)} behoben, aber nicht nachgezogen`)
  }
  return fehler
}

const KOPF = `# UX1e — eingefrorener Bestand der ALTEN Knopfklassen im Kalender-/Moderationsbereich.
#
# Geprueft: components/kronos/**, pages/Kalender*.vue, pages/Moderation.vue
#           (.vue/.css/.js/.mjs), ausser Kommentaren.
# Format:   relativer/pfad<TAB>anzahl_fundstellen
# Fundstelle = \`dk-btn\`/\`dk-btn-*\` | \`btn\`/\`btn-*\` | rohe Knopfklassen im Bereich.
#
# REGEL: Diese Liste darf NUR SCHRUMPFEN. Neue Alt-Knoepfe sind nicht
# zulaessig — neue Knoepfe kommen aus DkButton (components/ui/DkButton.vue).
# Erzeugt mit (aus frontend/ heraus): node tools/ux1e-knopf-bestand.mjs --schreiben
# Geprueft von frontend/tests/ux1e-knopf-system.test.mjs.
`

export function alsText() {
  const jetzt = bestand()
  const zeilen = [...jetzt].map(([pfad, zahl]) => `${pfad}\t${zahl}`).join('\n')
  const summe = [...jetzt.values()].reduce((a, b) => a + b, 0)
  return `${KOPF}#\n# Stand (UX1e): ${summe} Fundstellen in ${jetzt.size} Dateien.\n${zeilen}\n`
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const text = alsText()
  if (process.argv.includes('--schreiben')) {
    mkdirSync(path.dirname(LISTE), { recursive: true })
    writeFileSync(LISTE, text)
  }
  process.stdout.write(text)
}
