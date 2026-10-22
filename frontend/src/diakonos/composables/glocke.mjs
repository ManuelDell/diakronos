/**
 * REST-1 (4) — Glocke: „gelesen“ nur für eine Liste, die WIRKLICH zu sehen ist.
 *
 * Befund der Boardpruefung: `toggleListe` markierte nach dem Laden als
 * gelesen, auch wenn das Panel inzwischen wieder geschlossen war — die
 * Nachrichten verschwanden dann ungesehen. Die Bedingung steht hier als reine
 * Funktion, damit der Wettlauf (Öffnen → Schließen → Antwort trifft ein) ohne
 * Browser prüfbar ist.
 */

/**
 * Darf die geladene Liste als gelesen markiert werden?
 *
 * @param {object} lage
 * @param {boolean} lage.offen        Panel ist JETZT offen (nicht beim Klick!)
 * @param {number}  lage.anfrage      Nummer der Antwort
 * @param {number}  lage.oeffnung     Nummer der aktuellen Öffnung
 * @param {Array}   lage.eintraege    geladene Einträge (null = Fehlschlag)
 * @param {string}  lage.fehler       Fehlertext ('' = kein Fehler)
 * @returns {boolean}
 */
export function darfAlsGelesenMarkieren({ offen, anfrage, oeffnung, eintraege, fehler }) {
    if (!offen) return false
    if (anfrage !== oeffnung) return false
    if (!eintraege || fehler) return false
    return true
}

export default darfAlsGelesenMarkieren
