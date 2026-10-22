/**
 * AUSTRITT — API-Zugriff fuer „Austritt / Deaktivieren“ und „Reaktivieren“.
 *
 * Eine Datei je Bereich (Konvention aus `usePflege.js`): die Oberflaeche ruft
 * die Endpunkte nur hier. Rechte kommen vom Server — diese Datei blendet
 * nichts aus und prueft nichts nach, sie fragt nur.
 *
 *   mitglied_austritt      (mitglied_id, begruendung, datum)
 *       -> { status:'Ausgetreten', austritt_seit, konto_deaktiviert, konten }
 *   mitglied_reaktivieren  (mitglied_id)
 *       -> { status:'Mitglied', konto_aktiv, konten }
 *
 * Die API-Module liegen unter `diakronos.diakonos.api.*` (dieselben dotted
 * paths wie im Altcode).
 */
import { apiCall } from './useApi.js'

const API = 'diakronos.diakonos.api.austritt'

/** Heutiges Datum als JJJJ-MM-TT (Vorgabe im Austritts-Dialog). */
export function heute() {
    const jetzt = new Date()
    const zwei = (n) => String(n).padStart(2, '0')
    return `${jetzt.getFullYear()}-${zwei(jetzt.getMonth() + 1)}-${zwei(jetzt.getDate())}`
}

/** ISO-Datum (JJJJ-MM-TT) als deutsches Datum; sonst der Text unveraendert. */
export function datumDeutsch(wert) {
    const text = String(wert || '').slice(0, 10)
    if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return text
    const [jahr, monat, tag] = text.split('-')
    return `${tag}.${monat}.${jahr}`
}

/**
 * Austritt erfassen. `begruendung` ist OPTIONAL (AUSTRITT-b/N1: der Server
 * akzeptiert sie leer), `datum` optional im Format JJJJ-MM-TT (Vorgabe: heute
 * auf dem Server).
 */
export function austrittErfassen(mitgliedId, begruendung, datum = '') {
    return apiCall(`${API}.mitglied_austritt`, {
        mitglied_id: mitgliedId,
        begruendung,
        datum: datum || '',
    })
}

/** Austritt zuruecknehmen (Konto wieder aktiv, Anzeige wieder vollstaendig). */
export function reaktivieren(mitgliedId) {
    return apiCall(`${API}.mitglied_reaktivieren`, { mitglied_id: mitgliedId })
}

/**
 * Lage einer Person aus der Detail-Antwort (`get_mitglied_detail.daten.austritt`).
 *
 * `art` kommt vom SERVER (AUSTRITT-d/NB3): `'austritt'`, `'ausschluss'` oder
 * `''` (nichts gesetzt). Die Oberflaeche leitet sie NICHT aus der Begruendung
 * ab — die ist seit N1 optional, ein Austritt ohne Begruendung erschien damit
 * als „Ausschluss“ (kein Knopf „Reaktivieren“, Nicht-Admins lasen
 * „Ausgeschlossen seit …“). Die Unterscheidung entscheidet, ob die
 * Oberflaeche „Reaktivieren“ oder den Statusweg anbietet — zwei Wege, die halb
 * dasselbe taeten, gibt es nicht.
 *
 * Fehlt `art` (aeltere Antwort), gilt: `ausgetreten` heisst Austritt. Der
 * frueher uebliche Rueckschluss aus `grund` ist bewusst weg.
 */
export function lage(austritt) {
    const a = austritt || {}
    const art = a.art ?? (a.ausgetreten ? 'austritt' : '')
    if (art !== 'austritt' && art !== 'ausschluss') {
        return { art: '', seit: null, grund: '', vorherigerStatus: '' }
    }
    return {
        art,
        seit: a.seit || null,
        grund: a.grund || '',
        vorherigerStatus: a.vorheriger_status || '',
    }
}
