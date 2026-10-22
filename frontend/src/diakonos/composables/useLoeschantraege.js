/**
 * DSGVO-2c — API-Zugriff der Verwaltung für Löschanträge.
 *
 * Eine Datei je Bereich (Konvention aus `useAustritt.js` / `useLoeschantrag.js`):
 * die Oberfläche spricht die Endpunkte NUR hier an. Das Gegenstück für die
 * Person selbst ist `useLoeschantrag.js` (Profil, ohne Ziel-ID) — hier ist die
 * Ziel-ID Pflicht, denn die Verwaltung entscheidet über FREMDES Löschen.
 *
 *   datenschutz.get_loeschantraege(status)                       -> Liste
 *   datenschutz.loeschung_bestaetigen(mitglied_id, bestaetigt)   -> Zähler
 *   datenschutz.loeschantrag_ablehnen(mitglied_id, begruendung, bestaetigt)
 *
 * Dazu die zwei Auskünfte, die die Seite für verständliche Meldungen braucht:
 * ob der Mailversand eingerichtet ist (`mailversand_status`, nur „ja/nein“)
 * und die Zahl offener Anträge für die Seitenleiste (`get_navigation_zaehler`).
 *
 * Freigeben und Ablehnen sind NICHT umkehrbar bzw. eine Entscheidung: beide
 * gehen nur mit `bestaetigt: true`, das der Dialog nach Rückfrage setzt.
 */
import { apiCall } from './useApi.js'

const API = 'diakronos.diakonos.api.datenschutz'

/**
 * Anträge einer Auswahl holen. Ohne Argument die Arbeitsliste („offen“) —
 * das ist der Standard des Servers, hier nicht doppelt festgelegt.
 */
export function antraegeLaden(status = '') {
  return apiCall(`${API}.get_loeschantraege`, status ? { status } : {})
}

/**
 * Löschung freigeben (endgültig). Der Server anonymisiert vollständig und
 * schickt VORHER die Mail; scheitert der Versand, wird nichts gelöscht.
 */
export function loeschungFreigeben(mitglied_id) {
  if (!mitglied_id) throw new Error('Ohne Person kann keine Löschung freigegeben werden.')
  return apiCall(`${API}.loeschung_bestaetigen`, { mitglied_id, bestaetigt: true })
}

/** Löschantrag mit Begründung ablehnen. Die Begründung geht an die Person. */
export function antragAblehnen(mitglied_id, begruendung) {
  if (!mitglied_id) throw new Error('Ohne Person kann kein Löschantrag abgelehnt werden.')
  return apiCall(`${API}.loeschantrag_ablehnen`, {
    mitglied_id,
    begruendung: String(begruendung ?? ''),
    bestaetigt: true,
  })
}

/**
 * Ist der Mailversand eingerichtet? Der Server gibt Mitgliederadministratoren
 * nur „ja/nein“ (`eingerichtet`, `darf_aendern`), keinen Server und keinen
 * Absender. Ein Fehler hier darf die Seite nicht kippen — dann bleibt der
 * Hinweis aus (kein falsches „nicht eingerichtet“).
 */
export async function mailversandStand() {
  try {
    const antwort = await apiCall('diakronos.diakonos.api.mailversand.mailversand_status')
    return { eingerichtet: antwort?.eingerichtet !== false, darf_aendern: antwort?.darf_aendern === true }
  } catch {
    return null
  }
}

/**
 * Zahl der offenen Löschanträge für Seitenleiste und Reiter.
 *
 * Der Endpunkt liefert die Zahl offener ANMELDUNGEN; Löschanträge zählt er
 * (noch) nicht mit. Deshalb: `null` heißt „keine Auskunft“ — die Oberfläche
 * blendet dann nichts ein, statt eine erfundene Null zu zeigen.
 */
export async function offeneAntraegeZaehlen() {
  try {
    const antraege = await antraegeLaden('offen')
    return Array.isArray(antraege) ? antraege.length : null
  } catch {
    return null
  }
}
