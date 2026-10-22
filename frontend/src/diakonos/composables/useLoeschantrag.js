/**
 * DSGVO-2b — API-Zugriff für „Meine Daten löschen lassen“ im eigenen Profil.
 *
 * Eine Datei je Bereich (Konvention aus `useAustritt.js`): die Oberfläche
 * spricht die Endpunkte NUR hier an. Ziel der Aufrufe ist immer die eigene
 * Person — es gibt kein `mitglied_id`, der Server nimmt sie aus der Sitzung.
 *
 *   datenschutz.mein_loeschantrag()              -> Stand oder null
 *   datenschutz.loeschung_beantragen(bestaetigt) -> Stand (offen)
 *   datenschutz.loeschantrag_zurueckziehen(bestaetigt) -> Stand (zurueckgezogen)
 *
 * Bestätigen (`loeschung_bestaetigen`) und Ablehnen (`loeschantrag_ablehnen`)
 * sind Verwaltungssachen und stehen deshalb NICHT hier.
 */
import { apiCall } from './useApi.js'
import { serverFehlerText } from './useVerwaltung.js'

const API = 'diakronos.diakonos.api.datenschutz'

/** Stand des eigenen Antrags holen (null, solange keiner gestellt wurde). */
export function antragsstandLaden() {
    return apiCall(`${API}.mein_loeschantrag`)
}

/** Eigenen Löschantrag stellen. `bestaetigt` ist Pflicht (Server prüft). */
export function loeschungBeantragen() {
    return apiCall(`${API}.loeschung_beantragen`, { bestaetigt: true })
}

/** Eigenen Löschantrag zurückziehen, solange er offen ist. */
export function antragZurueckziehen() {
    return apiCall(`${API}.loeschantrag_zurueckziehen`, { bestaetigt: true })
}

/**
 * Fehler aus diesen Aufrufen als EINEN lesbaren Satz.
 *
 * `serverFehlerText` kennt die strukturierten Meldungen (pfad/meldung/hinweis)
 * und macht aus „HTTP 417“ einen Satz. 403 heißt hier: kein Konto/keine Person
 * zur Sitzung — das ist die einzige Stelle, an der die Person etwas tun kann
 * (an die Gemeindeverwaltung wenden).
 */
export function antragFehlerText(err, fallback = 'Das hat nicht geklappt. Bitte noch einmal versuchen.') {
    if (err?.status === 403) {
        return 'Zu deinem Zugang ist keine Person hinterlegt. Bitte wende dich an die Gemeindeverwaltung.'
    }
    return serverFehlerText(err, fallback)
}
