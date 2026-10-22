/**
 * P1-5c (9): Antwort des Serien-Updates in eine Anzeige uebersetzen.
 *
 * Der Server verwirft bei einem Nicht-Moderator den Serien-Status und meldet
 * das in `verworfen`/`meldung` (`api/kronos/series.py`). Diese Antwort wurde in
 * der Oberflaeche nicht ausgewertet — der Nutzer glaubte an eine wirksame
 * Aenderung. Hier steht die (reine, testbare) Entscheidung, WAS gezeigt wird;
 * der Aufrufer kümmert sich nur um den Toast.
 *
 * Rueckgabe: `null`, wenn es nichts zu melden gibt, sonst `{text, type}`.
 * `type` ist ein Toast-Typ (`warning` bei verworfenen Feldern, sonst `info`).
 */

/** Deutsche Bezeichnung eines verworfenen Felds (Klartext statt Feldname). */
const FELD_TEXTE = {
  status: 'Freigabe (Status)',
}

export function serienMeldung(antwort) {
  if (!antwort || typeof antwort !== 'object') return null
  const meldung = antwort.meldung
  if (typeof meldung !== 'string' || !meldung.trim()) return null

  const verworfen = Array.isArray(antwort.verworfen) ? antwort.verworfen : []
  if (verworfen.length) {
    const felder = verworfen.map((f) => FELD_TEXTE[f] || String(f)).join(', ')
    return { text: `${meldung} Betroffen: ${felder}.`, type: 'warning' }
  }
  // Reiner Hinweis (z. B. „N Termine warten auf Freigabe“) — kein Fehler.
  return { text: meldung, type: 'info' }
}
