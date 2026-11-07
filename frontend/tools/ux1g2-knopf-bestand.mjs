/**
 * UX1g2 — Bestandsrechner fuer rohe `<button>` MIT EIGENKLASSE.
 *
 * SCHLUPFLOCH AUS UX1g (Review 07.11.)
 * `fundstellenOhneBausteine()` in `tools/ux1g-knopf-bestand.mjs` pruefte die
 * Bausteinregel (`dk-ui-chip`, `dk-ui-aktionen-*`) gegen die GANZE Datei:
 * stand irgendwo ein Chip, fielen ALLE klassenlosen `<button>` derselben Datei
 * aus dem Bestand. Beispiel `pages/planrahmen/Plan.vue` — der Reiter-Knopf
 * `class="dk-tab"` wurde nie gezaehlt.
 *
 * Diese Karte zieht die Grenze auf das EINZELNE Element. Die Regel selbst
 * liegt in `tools/knopf-elemente.mjs` (dort, damit UX1g und UX1g2 sie teilen
 * koennen, ohne sich gegenseitig zu importieren):
 *
 *   fundstellenJeElement()   Alt-Knopf-Bestand — auf 0 (UX1g, F1).
 *   roheMitEigenklasse()     rohe `<button class="eigen">` OHNE Alt-Klasse und
 *                            OHNE Baustein. Kein Alt-Knopf, aber auch kein
 *                            Baustein: als BESTAND eingefroren, nur schrumpfen.
 *
 * DIE EINGEFRORENE LISTE
 * `tools/ux1g2-knopf-eigenklasse.txt` haelt fest, welche Datei wie viele rohe
 * Knoepfe mit Eigenklasse traegt (Stand: 49 in 36 Dateien). Mehr als die 10
 * Dateien, ab denen die Karte „einfrieren statt umstellen" vorsieht — die
 * Liste ist damit der Beleg und die Bremse: neue kommen nicht dazu, behobene
 * muessen nachgezogen werden. Der Waechter ist
 * `tests/ux1g2-knopf-element.test.mjs`.
 *
 * WARUM DIE DATEI HIER LIEGT
 * Der Image-Build fuehrt die Tests in `frontend/` aus (backend/Dockerfile,
 * Stage `frontend`, node --test); alles, was der Rechner braucht, liegt IN
 * `frontend/`.
 */
import { mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  FRONTEND,
  SRC,
  liesBestand as liesListe,
  relativ,
  verstoesse as verstoesseAllgemein,
} from './ux1e-knopf-bestand.mjs'
import { imBereich, imFremdenBereich } from './ux1g-knopf-bestand.mjs'
import {
  BAUSTEIN_KLASSEN,
  fundstellenJeElement,
  roheMitEigenklasse,
} from './knopf-elemente.mjs'

export {
  BAUSTEIN_KLASSEN,
  fundstellenJeElement,
  istBaustein,
  klassenNamen,
  knopfElemente,
  roheMitEigenklasse,
  bausteinElemente,
} from './knopf-elemente.mjs'
export { FRONTEND, SRC, imBereich, imFremdenBereich }

/** Eingefrorener Bestand der rohen Knoepfe MIT Eigenklasse. */
export const LISTE = path.join(FRONTEND, 'tools', 'ux1g2-knopf-eigenklasse.txt')

// ── Dateien des Bereichs (alle, nicht nur die mit Alt-Knopf-Fund) ─────────

/**
 * Alle Quelldateien unter `frontend/src`, die zum Bereich dieser Karte gehoeren.
 *
 * `dateienImBereich()` aus dem UX1e-Kern liefert nur Dateien MIT
 * Alt-Knopf-Fund — fuer die Eigenklasse-Zaehlung braucht es die Liste ALLER
 * Dateien (ein `<button class="dk-tab">` ist kein Alt-Knopf und kaeme dort
 * nie vor).
 *
 * @returns {string[]} Pfade in Listen-Schreibweise (`frontend/src/…`), sortiert
 */
export function dateienDesBereichs() {
  const treffer = []
  const lauf = (dir) => {
    for (const name of readdirSync(dir)) {
      const p = path.join(dir, name)
      const st = statSync(p)
      if (st.isDirectory()) {
        if (name === 'node_modules' || name === 'dist') continue
        lauf(p)
      } else if (/\.(vue|css|js|mjs)$/.test(name)) {
        const rel = relativ(p)
        if (rel.endsWith('.test.mjs')) continue
        if (!imBereich(rel)) continue
        treffer.push(rel)
      }
    }
  }
  lauf(SRC)
  return treffer.sort()
}

/** Quelle einer Datei der Liste lesen. */
function quelle(rel) {
  return readFileSync(path.join(FRONTEND, rel.replace(/^frontend\//, '')), 'utf8')
}

/** Gezaehlte Fundstellen je Datei im Bereich dieser Karte (nur > 0). */
export function bestand() {
  const werte = new Map()
  for (const pfad of dateienDesBereichs()) {
    const zahl = fundstellenJeElement(quelle(pfad)).length
    if (zahl > 0) werte.set(pfad, zahl)
  }
  return new Map([...werte].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)))
}

/** Gezaehlte rohe Knoepfe mit Eigenklasse je Datei (nur > 0). */
export function bestandEigenklasse() {
  const werte = new Map()
  for (const pfad of dateienDesBereichs()) {
    const zahl = roheMitEigenklasse(quelle(pfad)).length
    if (zahl > 0) werte.set(pfad, zahl)
  }
  return new Map([...werte].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)))
}

/** Eingefrorene Liste der Eigenklasse-Knoepfe lesen (darf fehlen -> leer). */
export function liesBestandEigenklasse(datei = LISTE) {
  return liesListe(datei)
}

/** Prueft „nur schrumpfen“ fuer die Eigenklasse-Liste. */
export function verstoesseEigenklasse(jetzt = bestandEigenklasse(),
  frueher = liesBestandEigenklasse()) {
  return verstoesseAllgemein(jetzt, frueher)
}

// ── Bericht ───────────────────────────────────────────────────────────────

const KOPF = `# UX1g2 — eingefrorener Bestand: rohe <button> MIT Eigenklasse.
#
# Geprueft: alles unter frontend/src (ausser den Bereichen von UX1e/UX1f),
#           ausser Kommentaren — Regel JE ELEMENT.
# Format:   relativer/pfad<TAB>anzahl
# Fundstelle = rohes <button class="eigen"> ohne Alt-Knopfklasse und ohne
#              Baustein-Klasse (dk-ui-chip, dk-ui-aktionen-*).
#
# REGEL: Diese Liste darf NUR SCHRUMPFEN. Neue rohe Knoepfe mit Eigenklasse
# sind nicht zulaessig — neue Knoepfe kommen aus DkButton
# (components/ui/DkButton.vue). Beheben: node tools/ux1g2-knopf-bestand.mjs --schreiben
# Geprueft von frontend/tests/ux1g2-knopf-element.test.mjs.
`

/** Der Bestand als Text der Liste. */
export function alsText() {
  const jetzt = bestandEigenklasse()
  const zeilen = [...jetzt].map(([pfad, zahl]) => `${pfad}\t${zahl}`).join('\n')
  const summe = [...jetzt.values()].reduce((a, b) => a + b, 0)
  return `${KOPF}#\n# Stand (UX1g2): ${summe} rohe Knoepfe mit Eigenklasse in ${jetzt.size} Dateien.\n${zeilen}\n`
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const text = alsText()
  if (process.argv.includes('--schreiben')) {
    mkdirSync(path.dirname(LISTE), { recursive: true })
    writeFileSync(LISTE, text)
  }
  process.stdout.write(text)
}
