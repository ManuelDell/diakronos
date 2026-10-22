// LN1 — Anzeige eines Liedes ohne "Nr." wenn es keine Nummer gibt.
//
// EINE Wahrheit fuer die Anzeige (Spiegel der Server-Logik in
// backend/src/diakronos_app/planrahmen/lieder_pflege.py:anzeige_text):
//   quelle 'buch'  + Nummer -> "JN 1297"
//   quelle 'buch'  + Seite  -> "WH S. 150"
//   quelle 'buch'  + beides -> "JN 1297"  (Nummer hat Vorrang)
//   quelle 'kopie'          -> "Kopie"
//   quelle 'ohne' / leer    -> "" (Aufrufer zeigt den Titel)
//
// Nur Text — nie v-html. Quelle ist der Server (Feld `quelle`).

export const QUELLEN = [
  { wert: 'buch', label: 'Liederbuch (mit Nummer/Seite)' },
  { wert: 'kopie', label: 'Kopie / Einzelblatt (ohne Nummer)' },
  { wert: 'ohne', label: 'Ohne Angabe' },
]

const SAUBER = (v) => (v == null ? '' : String(v)).trim()

/**
 * Kurze Kennung eines Liedes. Nie "Nr." ohne Nummer.
 * @param {{quelle?:string,buch?:string,nummer?:string,gesangbuch_nummer?:string,seite?:string}} l
 * @returns {string} 'Kopie' | 'JN 1297' | 'WH S. 150' | ''
 */
export function liedAnzeige(l = {}) {
  const quelle = SAUBER(l.quelle)
  const buch = SAUBER(l.buch)
  const nummer = SAUBER(l.nummer != null && l.nummer !== '' ? l.nummer : l.gesangbuch_nummer)
  const seite = SAUBER(l.seite)
  if (quelle === 'kopie') return 'Kopie'
  if (quelle !== 'buch') return ''
  const teile = []
  if (buch) teile.push(buch)
  if (nummer) teile.push(nummer)
  else if (seite) teile.push(`S. ${seite}`)
  return teile.join(' ')
}

/**
 * Ist das Lied als "Kopie / Einzelblatt" markiert? (fuer dezentes Badge)
 */
export function istKopie(l = {}) {
  return SAUBER(l.quelle) === 'kopie'
}

/**
 * Kurzes Badge-Label fuer Listen ('' wenn nichts anzuzeigen ist).
 * Kopie -> 'Kopie', Buch -> 'JN 1297'/'WH S. 150', ohne Angabe -> ''.
 */
export function liedBadge(l = {}) {
  return liedAnzeige(l)
}
