/**
 * R6 — „Neuer Beitrag“/„Neuer Artikel“ nur zeigen, wenn es etwas anzulegen gibt.
 *
 * Befund (Review 12.11., Punkt 4): Der Kopfknopf stand für JEDE Person da. Ein
 * Mitglied löste beim Klick eine Kette von POSTs aus (je Gruppe einer) und
 * landete bei „darfst nicht“ — Lärm ohne Ergebnis.
 *
 * UI-R6b: Gefragt wird EINMAL beim Seitenladen und mit EINEM Aufruf
 * (`rechte.get_anlegeorte(typ)`); der Server antwortet mit der fertigen Liste
 * der erlaubten Einheiten (`anlegeorteAusAntwort` in `r6Gastzugang.mjs`). Der
 * Knopf erscheint nur, wenn mindestens eine Einheit erlaubt ist. Die Antwort
 * des Servers bleibt die Wahrheit; diese Datei entscheidet nichts selbst.
 */

/**
 * Gruppe aus der Adresse (`#/wiki?gruppe=…&untergruppe=…`).
 *
 * R6 (Review 12.11., Punkt 2): Die Gruppenseite springt mit ihrer Gruppe
 * hierher; erst damit ist „auf der Gruppenseite vorbelegt“ keine leere Zusage.
 * Liefert `{gruppe, untergruppe}` oder `null` (kein Abfrageteil in der Adresse).
 */
export function gruppeAusAdresse(hash) {
    const roh = String(hash ?? '')
    const frage = roh.includes('?') ? roh.slice(roh.indexOf('?') + 1) : ''
    if (!frage) return null
    const werte = new URLSearchParams(frage)
    const gruppe = (werte.get('gruppe') || '').trim()
    const untergruppe = (werte.get('untergruppe') || '').trim()
    if (!gruppe && !untergruppe) return null
    return { gruppe: gruppe || null, untergruppe: untergruppe || null }
}

/**
 * Darf die Person überhaupt irgendwo anlegen?
 *
 * @param {Array} optionen  Orte vom Server (`anlegeorteAusAntwort`)
 * @returns {boolean} true, sobald mindestens eine dasteht
 */
export function darfIrgendwoAnlegen(optionen) {
    return Array.isArray(optionen) && optionen.length > 0
}

/**
 * Der EINE Sprung von der Gruppenseite: welche Einheit öffnet den Editor?
 *
 * UI-R6b (Vorauswahl ohne zweiten Klick): Die Gruppenseite schickt ihre Gruppe
 * in der Adresse mit (`#/wiki?gruppe=…&untergruppe=…`). Steht sie unter den
 * Orten, öffnet die Seite den Editor EINMAL damit — kein zweiter Klick, keine
 * Rückfrage. Danach gehört die Adresse wieder „#/wiki“ (`vorauswahlVerbrauchen`
 * im Aufrufer), sonst käme derselbe Sprung beim nächsten Aufbau erneut.
 *
 * „Nur für diesen einen Sprung“ ist damit wahr: die Einheit wird nicht
 * gespeichert, sondern einmal gelesen und sofort verbraucht.
 *
 * @param {object|null} fest  `{gruppe, untergruppe}` aus der Adresse
 * @param {Array} optionen    Orte vom Server
 * @param {(eintrag:object)=>string} wert  Optionswert (`einheitWert`)
 * @returns {object|null} der Ort, mit dem geöffnet wird — oder null
 */
export function vorauswahlOrt(fest, optionen, wert) {
    const liste = Array.isArray(optionen) ? optionen : []
    if (!fest || !(fest.gruppe || fest.untergruppe)) return null
    const gesucht = fest.untergruppe ? `${fest.gruppe}|${fest.untergruppe}` : String(fest.gruppe || '')
    return liste.find(o => wert(o) === gesucht) || null
}
