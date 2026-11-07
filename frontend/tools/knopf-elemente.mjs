/**
 * Knopf-Elemente lesen — die gemeinsame Grundlage fuer UX1g und UX1g2.
 *
 * WARUM EIGENE DATEI (import-Zyklus)
 * Die Regel „Baustein-Ausnahme JE ELEMENT“ brauchen BEIDE Rechner: UX1g
 * (`tools/ux1g-knopf-bestand.mjs`, Bestand der Alt-Knoepfe) und UX1g2
 * (`tools/ux1g2-knopf-bestand.mjs`, Eigenklasse-Bestand). Laege sie in einem
 * der beiden, importierten sich die Dateien gegenseitig und die Auswertung
 * braeche mit einem Temporal-Dead-Zone-Fehler ab. Die Primitive wohnen
 * deshalb hier — sie haengen nur an `ux1e-knopf-bestand.mjs` (ohneKommentare,
 * fundstellen), nicht an UX1g.
 *
 * WAS EIN „ELEMENT“ IST
 * Ein oeffnendes `<button …>` und sein EIGENES `class`-Attribut. Vorher las
 * `fundstellenOhneBausteine()` das `class` aus der GANZEN Datei — ein Chip
 * irgendwo stellte alle klassenlosen Knoepfe derselben Datei frei. Genau das
 * war das Schlupfloch aus dem Review zu UX1g.
 */
import { fundstellen as fundstellenKern, ohneKommentare } from './ux1e-knopf-bestand.mjs'

/**
 * Bausteine, die ABSICHTLICH ein knopfartiges Element mit dokumentierter
 * Klasse tragen (Bibliothek, `components/ui/`):
 *
 *   `.dk-ui-chip`                Auswahl-Chip (Druckschalter)
 *   `.dk-ui-aktionen-ausloeser`  Ausloeser des Aktionsmenues „⋯“
 *   `.dk-ui-aktionen-eintrag`    Eintrag darin
 *
 * Die Ausnahme gilt fuer das EINE Element, das die Klasse traegt — nicht fuer
 * seine Datei.
 */
export const BAUSTEIN_KLASSEN = new Set([
  'dk-ui-chip',
  'dk-ui-aktionen-ausloeser',
  'dk-ui-aktionen-eintrag',
])

/**
 * Oeffnende Knopf-Tags einer Quelle, je mit seinem EIGENEN `class`-Attribut.
 *
 * Der Tag wird ZEICHENWEISE bis zum schliessenden `>` gelesen, das AUSSERHALB
 * einer Attribut-Zeichenkette steht. Ein `[^>]*` bricht an `>` INNERHALB von
 * Attributwerten ab (Pfeilfunktion `:ref="el => (…)"`, Vergleich
 * `:disabled="a > b"`) und liesse das `class`-Attribut unbemerkt weg.
 *
 * @param {string} text
 * @returns {{tag: string, klassen: string}[]} je oeffnendes Element
 */
export function knopfElemente(text) {
  const quelle = ohneKommentare(text)
  const elemente = []
  for (const start of quelle.matchAll(/<button\b/g)) {
    const anfang = start.index
    let i = anfang + '<button'.length
    let zitat = null
    for (; i < quelle.length; i += 1) {
      const c = quelle[i]
      if (zitat) {
        if (c === zitat) zitat = null
      } else if (c === '"' || c === "'") {
        zitat = c
      } else if (c === '>') {
        break
      }
    }
    const tag = quelle.slice(anfang, i + 1)
    const attr = tag.slice('<button'.length, -1)
    // Statisch (`class="a b"`), einfach (`class='a'`), gebunden (`:class="…"`,
    // `v-bind:class="…"`) oder als Objekt (`:class="{ … }"`).
    const klassen = /(?:^|\s)(?::|v-bind:)?class\s*=\s*(?:"([^"]*)"|'([^']*)'|\{([^}]*)\})/
      .exec(attr)
    const wert = klassen ? (klassen[1] ?? klassen[2] ?? klassen[3] ?? '') : ''
    elemente.push({ tag, klassen: wert })
  }
  return elemente
}

/** Klassenliste eines Attributwerts in Einzelnamen zerlegen. */
export function klassenNamen(wert) {
  return String(wert)
    .split(/[\s"'`+,:{}(),[\]]+/)
    .map((n) => n.trim())
    .filter(Boolean)
}

/**
 * Traegt das EIGENE `class` dieses Elements eine Baustein-Klasse?
 * @param {string} klassenwert
 * @returns {boolean}
 */
export function istBaustein(klassenwert) {
  return klassenNamen(klassenwert).some((n) => BAUSTEIN_KLASSEN.has(n))
}

/**
 * Fundstellen einer Quelldatei — Baustein-Ausnahme JE ELEMENT.
 *
 * Gezaehlt wird wie im UX1e-Kern: Klassen der Alt-Reihe (`dk-btn*`, `btn*`,
 * `*-btn`/`*-button`) plus `<button>` fuer jedes rohe Element OHNE Klasse.
 * Der Unterschied zur alten UX1g-Fassung: ein klassenloses `<button>` faellt
 * nur dann aus dem Bestand, wenn SEIN eigenes `class` eine Baustein-Klasse
 * traegt. Baustein-Elemente tragen immer eine Klasse und tauchen in der
 * `<button>`-Zahl ohnehin nicht auf — die Zahl ist damit 1:1 die der rohen
 * Knoepfe ohne Klasse.
 *
 * @param {string} text
 * @returns {string[]}
 */
export function fundstellenJeElement(text) {
  const klassen = fundstellenKern(text).filter((n) => n !== '<button>')
  const rohOhne = knopfElemente(text).filter((e) => !e.klassen.trim()).length
  return [...klassen, ...Array(rohOhne).fill('<button>')]
}

/**
 * Baustein-Knoepfe JE ELEMENT: die Dokumentation der Ausnahmen.
 * @param {string} text
 * @returns {string[]} je Element die tragende Baustein-Klasse
 */
export function bausteinElemente(text) {
  return knopfElemente(text)
    .filter((e) => istBaustein(e.klassen))
    .map((e) => klassenNamen(e.klassen).find((n) => BAUSTEIN_KLASSEN.has(n)))
}

/**
 * Rohe `<button>` mit EIGENER Klasse (kein Alt-Knopf, kein Baustein).
 *
 * Alt-Knoepfe zaehlt `fundstellenJeElement()`; hier bleibt, was eine
 * Eigenklasse traegt (`dk-tab`, `dk-ui-datumzeit-link`, `close-btn`).
 *
 * @param {string} text
 * @returns {string[]} je Element die erste Eigenklasse (oder `<button>`)
 */
export function roheMitEigenklasse(text) {
  const treffer = []
  for (const { tag, klassen } of knopfElemente(text)) {
    if (istBaustein(klassen)) continue
    // Ein Element, das schon als Alt-Knopf-KLASSE zaehlt (`class="dk-btn …"`),
    // ist kein Eigenklasse-Fall. Das `<button>` des Kerns meint dagegen genau
    // den klassenlosen Fall — der gehoert hierher.
    if (fundstellenKern(tag).some((n) => n !== '<button>')) continue
    // Auch ganz ohne Klasse ist es ein roher Knopf — der UX1g-Bestand fuehrt
    // ihn als `<button>` (Ziel 0), hier bleibt er als Bestand stehen.
    treffer.push(klassenNamen(klassen)[0] ?? '<button>')
  }
  return treffer
}
