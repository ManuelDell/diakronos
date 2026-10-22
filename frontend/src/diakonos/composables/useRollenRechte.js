/**
 * N10 — API-Zugriff fuer den Einstellungs-Abschnitt „Rollen & Rechte“.
 *
 * Buendelt die Endpunkte, damit die Oberflaeche sie nicht verstreut anspricht
 * (Konvention: eine Datei je Bereich). Rechte kommen vom Server; diese Datei
 * blendet nichts aus — sie fragt nur.
 *
 *   Rollenuebersicht:  get_rollen_uebersicht   (wer hat welche Rolle)
 *   Rollen setzen:     setze_rollen            (mitglied_id, rollen)
 *   Rollenliste:       get_zugangs_rollen      (feste Diakronos-Liste)
 *   Verantwortliche:   get_/set_verantwortliche + Auswahl (Bereiche/Gruppen)
 *   Dev-Modus:         devmodus.api.uebersicht / sitzung_starten / sitzung_beenden
 */
import { apiCall } from './useApi.js'

const ZUGANG = 'diakronos.diakonos.api.zugang'
const VERANTWORTLICHE = 'diakronos.diakonos.api.verantwortliche'
const DEVMODUS = 'diakronos.devmodus.api'

/** Wer hat welche Rolle — Lese-Tabelle des Abschnitts. */
export function rollenUebersicht() {
    return apiCall(`${ZUGANG}.get_rollen_uebersicht`, {})
}

/**
 * Rollen eines Kontos setzen — vollstaendig, nur aus der festen Diakronos-Liste.
 * `mitgliedId` ist die Mitglied-Kennung (das Konto haengt am Mitglied).
 */
export function rollenSetzen(mitgliedId, rollen) {
    return apiCall(`${ZUGANG}.setze_rollen`, { mitglied_id: mitgliedId, rollen })
}

/** Die waehlbare Rollenliste (feste Diakronos-Liste). */
export function zugangsRollen() {
    return apiCall(`${VERANTWORTLICHE}.get_zugangs_rollen`, {})
}

/** Verantwortliche eines Dienstbereichs/einer Gruppe/einer Untergruppe lesen. */
export function verantwortlicheLesen(doctype, name) {
    return apiCall(`${VERANTWORTLICHE}.get_verantwortliche`, { doctype, name })
}

/** Verantwortliche vollstaendig setzen (Liste von Konten). */
export function verantwortlicheSetzen(doctype, name, user) {
    return apiCall(`${VERANTWORTLICHE}.set_verantwortliche`, { doctype, name, user })
}

/** Auswahl der Personen MIT Konto fuer „Verantwortliche“. */
export function verantwortlicheAuswahl(doctype, name, suche = '') {
    return apiCall(`${VERANTWORTLICHE}.get_verantwortliche_auswahl`, { doctype, name, suche })
}

/** Dienstbereiche/Gruppen/Untergruppen fuer die Verantwortlichen-Auswahl. */
export function bereicheLesen() {
    return apiCall('diakronos.diakonos.api.gruppen.get_gruppen_for_orgchart', {})
}

/** Dev-Modus: Zustand (Kennzahlen, Schluesselkuerzel, laufende Sitzung). */
export function devmodusUebersicht() {
    return apiCall(`${DEVMODUS}.uebersicht`, {})
}

/** Dev-Modus fuer diesen Nutzer einschalten. */
export function devmodusStarten() {
    return apiCall(`${DEVMODUS}.sitzung_starten`, {})
}

/** Dev-Modus fuer diesen Nutzer beenden. */
export function devmodusBeenden() {
    return apiCall(`${DEVMODUS}.sitzung_beenden`, {})
}

/**
 * Fehlerzeilen der API verstaendlich machen (pfad/code/meldung/hinweis).
 * Der Server liefert strukturierte Meldungen; wir setzen sie zu einer
 * lesbaren Zeile je Meldung zusammen — wie `useDevmodus.fehlerZeilen`.
 */
export function fehlerZeilen(fehler) {
    const meldungen = fehler?.meldungen
    if (Array.isArray(meldungen) && meldungen.length) {
        return meldungen.map(m =>
            [m.pfad, m.meldung, m.hinweis].filter(Boolean).join(' — '))
    }
    return [fehler?.message || 'Unbekannter Fehler']
}
