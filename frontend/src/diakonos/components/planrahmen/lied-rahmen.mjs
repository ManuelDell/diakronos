// DEV-6 — Kennzeichnet eine Plan-Zelle als Lied-Zelle (Befund DMB-45e5dfcda737).
//
// In einer Zelle der Plan-Tabelle koennen mehrere Lieder stehen (mehrere
// Instanzen desselben Feldes, z. B. `lieder[0]`, `lieder[1]`, `lieder[2]`).
// Bisher waren sie nur durch 3 px Abstand getrennt — ohne Rahmen fielen sie
// zu einem Textblock zusammen. Gewuenscht (Manuel): JEDES Lied bekommt einen
// kleinen Rahmen.
//
// Die Zelle weiss nicht, welches Lied sie zeigt: die Linien der Tabelle
// nennen nur den Feldnamen ("Lieder"). Deshalb wird ueber die DEKLARATION
// entschieden (Spalte → Feld → art/sammlung) und die Formatvorlage der
// Ansicht beruecksichtigt, die ein Textfeld als Lied ausgeben kann
// (z. B. `{lied.anzeige}{lied.titel: {lied.titel}}`).

/** Eingebaute Liedsammlung des Plan-Rahmens (plantyp-1.json, `sammlungen`). */
export const LIEDER_SAMMLUNG = 'lieder'

/** Arten, deren Werte aus einer Sammlung stammen koennen. */
const SAMMLUNGSARTEN = new Set(['eintrag'])

/**
 * Setzt die Formatvorlage ein Lied voraus? Nur dann gilt ein Textfeld als
 * Lied-Spalte, wenn seine Vorlage den Eintrag in Lied-Rollen ausgibt
 * (`{lied.…}`, `{nr}`) oder ausdruecklich die Sammlung `lieder` nennt.
 */
function vorlageIstLied(format) {
  if (typeof format !== 'string' || !format) return false
  // {lied.anzeige}, {lied.titel}, {nr} (Liednummer im Programmkopf)
  if (/\{\s*lied\s*[.:}]/.test(format)) return true
  if (/\{\s*nr\s*[.:}]/.test(format)) return true
  return /sammlung\s*[:=]\s*['"]?lieder/.test(format)
}

/**
 * Ist die Tabellenspalte eine Lied-Spalte?
 *
 * @param {{feld?: object|null, format?: string}} spalte Spalte aus PrTabelle
 *   (`feld` = Deklaration, `format` = Formatvorlage der Ansicht)
 * @param {{liederSammlungen?: Iterable<string>}} [optionen] zusaetzliche
 *   Sammlungsschluessel, die als Liedsammlung gelten (Vorgabe: 'lieder')
 * @returns {boolean}
 */
export function istLiedSpalte(spalte, optionen = {}) {
  const feld = spalte?.feld
  if (!feld || typeof feld !== 'object') return false
  if (feld.art === 'gruppe') return false
  const sammlungen = new Set(optionen.liederSammlungen || [LIEDER_SAMMLUNG])
  sammlungen.add(LIEDER_SAMMLUNG)
  if (SAMMLUNGSARTEN.has(feld.art) && sammlungen.has(String(feld.sammlung || ''))) return true
  // Textfeld, dessen Formatvorlage Lied-Rollen ausgibt (die Deklaration nennt
  // dann keine Sammlung, die Vorlage aber `{lied.…}`/`{nr}`).
  if (feld.art === 'text' && vorlageIstLied(spalte?.format)) return true
  return false
}

/**
 * Zeilen einer Lied-Zelle mit Rahmen: je Instanz eine Zeile, leere Werte
 * ('–', '') bekommen keinen Rahmen (ein Rahmen um einen Gedankenstrich waere
 * eine Behauptung). Die Reihenfolge bleibt die der Zelle.
 *
 * @param {Array<{text?: string}>} instanzen Zeilen aus `zellenInhalt`
 * @param {boolean} liedZelle Ergebnis von `istLiedSpalte`
 * @returns {Array<{text: string, gerahmt: boolean}>}
 */
export function zellZeilen(instanzen, liedZelle) {
  const liste = Array.isArray(instanzen) ? instanzen : []
  return liste.map((z) => {
    const text = z?.text === null || z?.text === undefined ? '' : String(z.text)
    const leer = text.trim() === '' || text.trim() === '\u2013'
    return { ...z, text, gerahmt: !!liedZelle && !leer }
  })
}
