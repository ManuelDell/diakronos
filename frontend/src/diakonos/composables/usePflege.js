/**
 * P1-8 — API-Zugriff fuer „Verantwortliche" und „Zugang".
 *
 * Bündelt die Endpunkte, damit die Oberflaeche sie nicht ueber verstreute
 * apiCall-Aufrufe anspricht (Konvention: eine Datei je Bereich). Rechte kommen
 * vom Server; diese Datei blendet nichts aus — sie fragt nur.
 *
 *   verantwortliche:  get_verantwortliche / set_verantwortliche
 *   zugang:           get_zugang / konto_anlegen / setze_rollen /
 *                     konto_sperren / setze_passwort / get_wartende_konten
 *
 * Die API-Module liegen unter `diakronos.diakonos.api.*` (dieselben
 * dotted paths wie im Altcode).
 */
import { apiCall } from './useApi.js'

const VERANTWORTLICHE = 'diakronos.diakonos.api.verantwortliche'
const ZUGANG = 'diakronos.diakonos.api.zugang'

/** Verantwortliche eines Dienstbereichs/einer Gruppe/Untergruppe lesen. */
export function verantwortlicheLesen(doctype, name) {
    return apiCall(`${VERANTWORTLICHE}.get_verantwortliche`, { doctype, name })
}

/**
 * Verantwortliche vollstaendig setzen (Liste von Konten).
 * `user` ist die Liste der Kontonamen (E-Mail); die Liste ERSETZT den Bestand.
 */
export function verantwortlicheSetzen(doctype, name, user) {
    return apiCall(`${VERANTWORTLICHE}.set_verantwortliche`, { doctype, name, user })
}

/** Auswahl der Personen MIT Konto fuer „Verantwortliche hinzufügen". */
export function verantwortlicheAuswahl(doctype, name, suche = '') {
    return apiCall(`${VERANTWORTLICHE}.get_verantwortliche_auswahl`, { doctype, name, suche })
}

/** Die in der Oberflaeche waehlbaren Zugangs-Rollen (feste Diakronos-Liste). */
export function zugangsRollen() {
    return apiCall(`${VERANTWORTLICHE}.get_zugangs_rollen`, {})
}

/** Zugang (Konto + Rollen) eines Mitglieds lesen. */
export function zugangLesen(mitgliedId) {
    return apiCall(`${ZUGANG}.get_zugang`, { mitglied_id: mitgliedId })
}

/** Konto fuer ein Mitglied anlegen (ohne Authentik). */
export function kontoAnlegen(mitgliedId) {
    return apiCall(`${ZUGANG}.konto_anlegen`, { mitglied_id: mitgliedId })
}

/** Rollen eines Kontos setzen (nur aus der festen Liste). */
export function rollenSetzen(mitgliedId, rollen) {
    return apiCall(`${ZUGANG}.setze_rollen`, { mitglied_id: mitgliedId, rollen })
}

/** Konto sperren (`gesperrt=true`) oder freischalten (`false`). */
export function kontoSperren(mitgliedId, gesperrt) {
    return apiCall(`${ZUGANG}.konto_sperren`, { mitglied_id: mitgliedId, gesperrt })
}

/** Startpasswort eines Kontos setzen. */
export function passwortSetzen(mitgliedId, passwort) {
    return apiCall(`${ZUGANG}.setze_passwort`, { mitglied_id: mitgliedId, passwort })
}

/** Einmaligen persönlichen Passwort-Link erzeugen (vorheriger verfällt). */
export function passwortLinkErzeugen(mitgliedId) {
    return apiCall(`${ZUGANG}.einladungslink`, { mitglied_id: mitgliedId })
}

export function zugangsmodusLesen() {
    return apiCall(`${ZUGANG}.get_zugangsmodus`, {})
}

/** Konten ohne Freischaltung (Authentik „Als Gast anlegen"). */
export function wartendeKonten() {
    return apiCall(`${ZUGANG}.get_wartende_konten`, {})
}

/**
 * Konto direkt ueber seinen Kontonamen sperren bzw. freischalten (W1).
 * Gastkonten ohne Mitglied haben kein `mitglied_id` — `konto_sperren` waere
 * fuer sie nicht erreichbar; dieser Weg schaltet ueber den `User.name`.
 */
export function kontoFreischalten(user, freischalten = true) {
    return apiCall(`${ZUGANG}.konto_freischalten`, { user, freischalten })
}
