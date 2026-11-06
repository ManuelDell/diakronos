/**
 * UX1f — Bestandsrechner fuer den Alt-Knopf in den Bereichen der zweiten
 * Knopf-Karte („Ein Knopf-System, Teil 2“).
 *
 * Zaehlt je Datei die Fundstellen der ALTEN Knopf-Klassen und der rohen
 * Knopfelemente in:
 *
 *   Personen          pages/mitglieder/**, pages/Mitglieder.vue,
 *                     pages/MitgliedDetail.vue, components/mitglieder/**,
 *                     pages/Registrierung.vue, components/registrierung/**,
 *                     pages/Personen.vue, components/personen/** (UX3b)
 *   Gruppen           pages/Gruppe*.vue, pages/Gruppen.vue, pages/gruppen/**,
 *                     components/gruppen/**
 *   Öffentlich        gast/**, registrierung/**, organigramm/**
 *
 * Gezaehlt wird mit DEMSELBEN Kern wie UX1e (`tools/ux1e-knopf-bestand.mjs`):
 * eine Fundstelle ist
 *   * eine Klasse der Reihen `btn*`, `dk-btn*` oder `*-btn`/`*-button` in einem
 *     `class`-Attribut (ausser den Behaelter-Ausnahmen) oder
 *   * ein rohes `<button>`-Element ohne Klasse (das kennt nur das System).
 *
 * EIGENE LISTE, EIGENER RAHMEN
 * Die Bereiche dieser Karte sind andere als die von UX1e; sie bekommen eine
 * eigene eingefrorene Liste, damit die Kalenderliste unveraendert bleibt. Der
 * Zaehler selbst ist derselbe — zwei Rechner wuerden auseinanderlaufen.
 *
 * REGEL: Die Liste darf NUR SCHRUMPFEN. Eine hoehere Zahl oder ein neuer
 * Eintrag macht `frontend/tests/ux1f-knopf-system.test.mjs` rot; eine behobene
 * Stelle, die nicht nachgezogen wurde, ebenso.
 *
 * WARUM DIE DATEI HIER LIEGT (frontend/tools/)
 * Der Image-Build fuehrt die Tests in `frontend/` aus (backend/Dockerfile,
 * Stage `frontend`, node --test). Alles, was der Rechner braucht liegt IN
 * `frontend/`; er rechnet relativ zu SEINER eigenen Datei.
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  FRONTEND,
  SRC,
  fundstellen,
  liesBestand as liesListe,
  ohneKommentare,
  relativ,
  verstoesse as verstoesseAllgemein,
  dateienImBereich,
} from './ux1e-knopf-bestand.mjs'

export { FRONTEND, SRC, fundstellen, ohneKommentare, relativ }

/** Das Verzeichnis `frontend/` — Wurzel aller Pfade in der Liste. */
export const LISTE = path.join(FRONTEND, 'tools', 'ux1f-knopf-bestand.txt')

/**
 * Die Bereiche der Karte UX1f. Punkte mit `/` am Ende sind Verzeichnisse,
 * alle anderen sind einzelne Seiten.
 */
export const BEREICH = [
  'frontend/src/diakonos/pages/mitglieder/',
  'frontend/src/diakonos/pages/Mitglieder.vue',
  'frontend/src/diakonos/pages/MitgliedDetail.vue',
  'frontend/src/diakonos/pages/Registrierung.vue',
  'frontend/src/diakonos/pages/Personen.vue',
  'frontend/src/diakonos/components/personen/',
  'frontend/src/diakonos/components/mitglieder/',
  'frontend/src/diakonos/components/registrierung/',
  'frontend/src/diakonos/pages/GruppeDetail.vue',
  'frontend/src/diakonos/pages/Gruppen.vue',
  'frontend/src/diakonos/pages/gruppen/',
  'frontend/src/diakonos/components/gruppen/',
  'frontend/src/gast/',
  'frontend/src/registrierung/',
  'frontend/src/organigramm/',
]

/** Liegt dieser Pfad (`frontend/…`) im Bereich der Karte? */
export function imBereich(rel) {
  return BEREICH.some((b) => (b.endsWith('/') ? rel.startsWith(b) : rel === b))
}

/** Gezaehlte Fundstellen je Datei (nur der Bereich, nur > 0). */
export function bestand() {
  return dateienImBereich(SRC, imBereich)
}

/** Die eingefrorene Liste lesen (Datei darf fehlen -> leer). */
export function liesBestand(datei = LISTE) {
  return liesListe(datei)
}

/** Prueft „nur schrumpfen“ und liefert die Verstoesse als Textzeilen. */
export function verstoesse(jetzt = bestand(), frueher = liesBestand()) {
  return verstoesseAllgemein(jetzt, frueher)
}

const KOPF = `# UX1f — eingefrorener Bestand der ALTEN Knopfklassen (Teil 2).
#
# Geprueft: pages/mitglieder/**, pages/Mitglieder*.vue, pages/Registrierung.vue,
#           components/mitglieder/**, components/registrierung/**,
#           pages/Gruppe*.vue, pages/gruppen/**, components/gruppen/**,
#           gast/**, registrierung/**, organigramm/**  (.vue/.css/.js/.mjs),
#           ausser Kommentaren.
# Format:   relativer/pfad<TAB>anzahl_fundstellen / rohe Knopfelemente
# Fundstelle = \`dk-btn\`/\`dk-btn-*\` | \`btn\`/\`btn-*\` | rohe Knopfelemente im Bereich.
#
# REGEL: Diese Liste darf NUR SCHRUMPFEN. Neue Alt-Knoepfe sind nicht
# zulaessig — neue Knoepfe kommen aus DkButton (components/ui/DkButton.vue).
# Erzeugt mit (aus frontend/ heraus): node tools/ux1f-knopf-bestand.mjs --schreiben
# Geprueft von frontend/tests/ux1f-knopf-system.test.mjs.
`

/** Der Bestand als Text der Liste. */
export function alsText() {
  const jetzt = bestand()
  const zeilen = [...jetzt].map(([pfad, zahl]) => `${pfad}\t${zahl}`).join('\n')
  const summe = [...jetzt.values()].reduce((a, b) => a + b, 0)
  return `${KOPF}#\n# Stand (UX1f): ${summe} Fundstellen in ${jetzt.size} Dateien.\n${zeilen}\n`
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const text = alsText()
  if (process.argv.includes('--schreiben')) {
    mkdirSync(path.dirname(LISTE), { recursive: true })
    writeFileSync(LISTE, text)
  }
  process.stdout.write(text)
}
