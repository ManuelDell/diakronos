/**
 * UX1g — Bestandsrechner fuer den ALT-Knopf im REST der Anwendung.
 *
 * Die Karten UX1e (Kalender/Moderation) und UX1f (Personen/Gruppen/
 * Registrierung/Gast) haben das Knopf-System `DkButton` in ihren Bereichen
 * durchgesetzt. Teil 3 (UX1g) nimmt den Rest: alles, was nach Abzug dieser
 * beiden Bereiche noch alte Knopfklassen traegt — App-Rahmen, Plan-Rahmen,
 * Lieder, Startseite, Ressourcen, Widgets, Bausteine.
 *
 * Gezaehlt wird mit DEMSELBEN Kern wie UX1e/UX1f
 * (`tools/ux1e-knopf-bestand.mjs`): eine Fundstelle ist
 *   * eine Klasse der Reihen `btn*`, `dk-btn*` oder `*-btn`/`*-button` in einem
 *     `class`-Attribut (ausser den Behaelter-Ausnahmen), oder
 *   * ein rohes `<button>`-Element ohne Klasse.
 *
 * ZIEL: NULL. Anders als in UX1e/UX1f gibt es hier KEINE eingefrorene Liste,
 * die schrumpfen darf — die Karte sagt „Rest, Waechter auf 0". Der Waechter
 * `tests/ux1g-knopf-system.test.mjs` verlangt deshalb 0 Fundstellen in
 * `frontend/src` und 0 Fundstellen der CSS-Regeln `.dk-btn*`.
 *
 * DIE BEIDEN BEREICHE VON UX1e/UX1f SIND AUSGENOMMEN
 * Ihre Bestandslisten (`tools/ux1e-knopf-bestand.txt`,
 * `tools/ux1f-knopf-bestand.txt`) halten eigene Alt-Bestaende fest, die
 * spaetere Karten abarbeiten. Sie wuerden die 0 dieser Karte sofort
 * unmoeglich machen; der Waechter prueft sie weiterhin ueber ihre eigenen
 * Tests.
 *
 * WARUM DIE DATEI IN frontend/tools/ LIEGT
 * Der Image-Build fuehrt die Tests in `frontend/` aus (backend/Dockerfile,
 * Stage `frontend`, node --test); alles, was der Rechner braucht, liegt IN
 * `frontend/`.
 */
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  FRONTEND,
  SRC,
  fundstellen,
  imBereich as imBereichUx1e,
  ohneKommentare,
  relativ,
  dateienImBereich,
} from './ux1e-knopf-bestand.mjs'
import { imBereich as imBereichUx1f } from './ux1f-knopf-bestand.mjs'

export { FRONTEND, SRC, fundstellen, ohneKommentare, relativ }

/** Bericht der letzten Auszaehlung (Karte, Stand). */
export const LISTE = path.join(FRONTEND, 'tools', 'ux1g-knopf-bestand.txt')

/**
 * Bereiche, die NICHT zu dieser Karte gehoeren: UX1e (Kalender/Moderation)
 * und UX1f (Personen/Gruppen/Registrierung/Gast). Sie fuehren ihre eigenen
 * eingefrorenen Listen.
 */
export function imFremdenBereich(rel) {
  return imBereichUx1e(rel) || imBereichUx1f(rel)
}

/**
 * Bausteine, die ABSICHTLICH ein Knopfartiges Element mit dokumentierter
 * Klasse tragen und deshalb nicht gezaehlt werden:
 *
 *   `.dk-ui-chip`   Auswahl-Chip (Druckschalter), gebaut in `components/ui/`
 *                   und in den Seiten als Bedienelement benutzt — Teil der
 *                   Baustein-Bibliothek, nicht der Alt-Knopfreihe.
 *   `.dk-ui-aktionen-ausloeser` / `-eintrag`
 *                   Ausloeser und Eintraege des Aktionsmenues „⋯" (UX2e) —
 *                   ein Menue-Bedienelement mit eigener Tastaturbedienung,
 *                   kein Knopf der Reihe primary/secondary/ghost/danger.
 *
 * Beides sind KEINE Alt-Knoepfe (`dk-btn*`, `btn*`, `*-btn`); der Zaehler
 * ueberspringt sie, damit „0" die Alt-Knopfreihe misst und nicht die
 * Bausteine mitzaehlt.
 */
export const BAUSTEIN_KLASSEN = new Set(['dk-ui-chip', 'dk-ui-aktionen-ausloeser',
  'dk-ui-aktionen-eintrag'])

/** Gehoert dieser Pfad (`frontend/…`) zum Rest, den UX1g umstellt? */
export function imBereich(rel) {
  if (!rel.startsWith('frontend/src/')) return false
  if (imFremdenBereich(rel)) return false
  // Die Zuordnungsregel nennt die alten Klassen absichtlich (Regeln und
  // Kommentare) — gezaehlt wird nur, was gerendert wird.
  if (/\/knopfvarianten\.mjs$/.test(rel)) return false
  return true
}

/**
 * Fundstellen einer Quelldatei OHNE die Bausteine der Bibliothek
 * (`BAUSTEIN_KLASSEN`) — die zaehlen nicht als Alt-Knopf.
 * @param {string} text
 * @returns {string[]}
 */
export function fundstellenOhneBausteine(text) {
  const quelle = ohneKommentare(text)
  return fundstellen(text).filter((name) => {
    if (name !== '<button>') return true
    // Ein rohes `<button class="dk-ui-chip">` ist der Auswahl-Chip; steht im
    // selben Element eine erlaubte Klasse, ist es kein Alt-Knopf.
    return ![...BAUSTEIN_KLASSEN].some((k) => quelle.includes(`class="${k}`)
      && new RegExp(`<button[^>]*class="[^"]*\\b${k}\\b[^"]*"[^>]*>`).test(quelle))
  })
}

/** Gezaehlte Fundstellen je Datei (nur der Rest, nur > 0). */
export function bestand() {
  const werte = new Map()
  for (const [pfad, zahl] of dateienImBereich(SRC, imBereich)) {
    const text = readFileSync(path.join(FRONTEND, pfad.replace(/^frontend\//, '')), 'utf8')
    const rest = fundstellenOhneBausteine(text).length
    if (rest > 0) werte.set(pfad, rest)
  }
  return new Map([...werte].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)))
}

/**
 * Fundstellen der ALTEN KNOPF-CSS. Die Regeln `.dk-btn` … lebten in
 * `index.css` (und als Kopie in `pages/Ressourcen.vue`); mit dem Umbau
 * entfallen sie, weil `DkButton` seine Optik in der Komponente traegt.
 *
 * Gezaehlt wird in JEDER Quelle unter `frontend/src` — auch in den
 * Bereichen von UX1e/UX1f: die CSS-Klassen selbst gehoeren niemandem mehr.
 *
 * @returns {{pfad: string, zahl: number}[]}
 */
export function cssFundstellen() {
  const treffer = []
  for (const [pfad] of dateienImBereich(SRC, () => true)) {
    const text = ohneKommentare(
      readFileSync(path.join(FRONTEND, pfad.replace(/^frontend\//, '')), 'utf8'),
    )
    const zahl = (text.match(/\.dk-btn(?![\w-])/g) || []).length
      + (text.match(/\.dk-btn-[\w-]+/g) || []).length
    if (zahl > 0) treffer.push({ pfad, zahl })
  }
  return treffer
}

/** Kopf des Berichts (kein Zustand, nur Lesehilfe — die Karte verlangt 0). */
const KOPF = `# UX1g — Alt-Knopf-Bestand im REST (Teil 3).
#
# Geprueft: alles unter frontend/src (ausser den Bereichen von UX1e/UX1f,
#           die eigene Listen fuehren), ausser Kommentaren.
# Format:   relativer/pfad<TAB>anzahl_fundstellen
# Fundstelle = \`dk-btn\`/\`dk-btn-*\` | \`btn\`/\`btn-*\` | rohe Knopfelemente.
#
# ZIEL: 0. Dies ist KEINE eingefrorene Liste — der Waechter
# (frontend/tests/ux1g-knopf-system.test.mjs) verlangt null Fundstellen in
# frontend/src und null Vorkommen der CSS-Regeln \`.dk-btn*\`.
# Erzeugt mit (aus frontend/ heraus): node tools/ux1g-knopf-bestand.mjs --schreiben
`

/** Der Bestand als Text des Berichts. */
export function alsText() {
  const jetzt = bestand()
  const zeilen = [...jetzt].map(([pfad, zahl]) => `${pfad}\t${zahl}`).join('\n')
  const summe = [...jetzt.values()].reduce((a, b) => a + b, 0)
  return `${KOPF}#\n# Stand (UX1g): ${summe} Fundstellen in ${jetzt.size} Dateien.\n${zeilen}\n`
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const text = alsText()
  if (process.argv.includes('--schreiben')) {
    mkdirSync(path.dirname(LISTE), { recursive: true })
    writeFileSync(LISTE, text)
  }
  process.stdout.write(text)
}
