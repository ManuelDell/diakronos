/**
 * Zentrale API-Utility für Diakonos SPA.
 * Nutzt fetch() statt frappe.call() – www-space kompatibel.
 */

import { useImpersonation } from './useImpersonation.js'
import { sitzungBeendet } from './useSitzungsablauf.js'
// WEB-8c (R4): Der Fehler wird ZWISCHENGELEGT (eigene Datei ohne Importe —
// sonst entstuende ein Ring usePlanrahmenCache -> usePlanrahmen -> useApi).
import { sitzungsFehlerMerken } from './sitzungsstand.js'
import { istSitzungsAbbruch } from '../../shared/sitzung-pruefen.js'
// WEB-5b: EINE Quelle fuer den Betriebs-Praefix (DIAKRONOS_BASE_PATH).
import { apiUrl } from '../../shared/basis.js'
// WEB-8b: CSRF-Ablehnung automatisch heilen (Token neu -> 1 Wiederholung ->
// Force-Refresh, 60-s-Schleifenschutz). EINE Wahrheit für alle Aufrufer.
import { istCsrfAblehnung, heileOderMelde, datenVon, SITZUNG_HINWEIS } from '../../shared/csrf-heilung.js'

export class AuditConfirmationRequired extends Error {
    constructor(policy) {
        super('Audit confirmation required')
        this.name = 'AuditConfirmationRequired'
        this.policy = policy
    }
}

/**
 * WEB-8c (R4): Ein Sitzungsende im Hauptbereich wird im VORHANDENEN Dialog
 * gezeigt (`SitzungsHinweis.vue` über `sitzungBeendet`) — die SPA navigiert
 * NICHT weg. Grund: `location.assign(login)` würde ein gerade ausgelöstes
 * `location.reload()` der Heilung überschreiben.
 *
 * Erkennung: die Heilung meldet sich mit `sitzung` (und `imBereich`, WEB-8e
 * E1) ODER die Antwort ist ein echter 401/419-Abbruch. `mitSitzungsdialog`
 * leitet JEDEN Sitzungsfehler ohne laufende Navigation hierher — und NUR
 * einen Sitzungsfehler (WEB-8f B1: Fachfehler bleiben beim Aufrufer).
 */
function sitzungImBereich(fehler) {
    sitzungsFehlerMerken(fehler)
    fehler.sitzung = true
    fehler.imBereich = true
    fehler.hinweis = fehler.hinweis || SITZUNG_HINWEIS
    return fehler
}

/**
 * WEB-8d (N3) / WEB-8e (E1): Wird bei diesem Fehler bereits navigiert? Dann
 * ist der Seitenwechsel schon ausgelöst (`neuLaden` = Force-Refresh,
 * `weitergeleitet` = Anmeldemaske) und es darf KEIN Dialog mehr aufblitzen —
 * er wäre nur ein kurzes Flackern vor dem Verschwinden der Seite.
 *
 * `imBereich` schlägt beide Merker: Ein solcher Fehler ist ausdrücklich
 * „Sitzung weg, aber hier bleiben" (Heilung mit `ohneNavigation`). Die
 * Bedingung ist bewusst so geschrieben, dass ein Merker-Doppel den Dialog
 * nie wieder verschluckt (WEB-8e E1: genau das war der Befund).
 */
function navigiertBereits(fehler) {
    return Boolean((fehler?.neuLaden || fehler?.weitergeleitet) && !fehler?.imBereich)
}

/**
 * Fuehrt `arbeiten` aus und uebersetzt ein Sitzungsende in den SPA-Dialog.
 * Alle drei API-Wege (apiCall, apiGet, apiAntwortPruefen) laufen hierdurch —
 * EINE Stelle, damit kein Weg still weg navigiert.
 */
async function mitSitzungsdialog(arbeiten) {
    try {
        return await arbeiten()
    } catch (fehler) {
        // WEB-8d (N3): Navigation laeuft schon -> durchreichen, nicht zeigen.
        if (navigiertBereits(fehler)) throw fehler
        // WEB-8e (E1) + WEB-8f (B1): NUR ein Sitzungsfehler geht in den
        // Dialog. Vorher lief JEDER Fehler durch `sitzungImBereich` — ein
        // 417 `ValidationError`, ein 403 `PermissionError`, ein 500 oder ein
        // Netzwerkfehler zeigten „Sitzung abgelaufen" (Opus-Review WEB-8e,
        // Blocker B1). Alles ohne `sitzung` bleibt unveraendert beim Aufrufer
        // (Feldfehler, Rechtehinweis, Verbindungstext).
        if (fehler?.sitzung) throw sitzungImBereich(fehler)
        throw fehler
    }
}

// WEB-8d (N9): Dieselbe Stelle als benannter Weg fuer den Verhaltenstest.
export { mitSitzungsdialog as __mitSitzungsdialog }

/**
 * Antwort einer API-Anfrage robust lesen (UXD-R8).
 * Erfolgreiche Antworten sind JSON. Bei Nicht-JSON (500/502/„Internal Server
 * Error" aus einem Proxy) liefern wir eine neutrale Struktur, damit der
 * Aufrufer eine verstaendliche Meldung zeigen kann statt eines JSON-Parse-
 * Fehlers.
 */
async function _liesAntwort(res) {
    const text = await res.text()
    if (!text) return { message: `Serverfehler (HTTP ${res.status})` }
    try {
        return JSON.parse(text)
    } catch {
        return { message: `Serverfehler (HTTP ${res.status})` }
    }
}

// Auch ältere direkte fetch-Aufrufer (Kalender) verwenden dieselbe Prüfung.
// Die Regeln stehen in `shared/sitzung-pruefen.js`, damit die eigenständigen
// Bundles (organigramm/registrierung/gast) nicht auseinanderlaufen.
export function pruefeSitzungsAntwort(res, data) {
    if (!istSitzungsAbbruch(res.status, data)) return false
    // WEB-8c (R4/R9): hier kommt NUR noch ein echter Sitzungsabbruch (401/419)
    // an. Eine CSRF-Ablehnung ist an dieser Stelle bereits geheilt oder hat in
    // `neuLadenOderAnmelden()` geendet (Fehler mit `neuLaden`/
    // `weitergeleitet`) — der frühere CSRF-Zweig war toter Code.
    // Damit die Person den Grund sieht (C2), öffnet der vorhandene Dialog
    // (`SitzungsHinweis.vue`, `sitzungBeendet`) hier den FESTEN Hinweis (R4) —
    // nie einen Freitext aus der Adresse. Der Hauptbereich navigiert NICHT weg:
    // ein `location.assign(login)` würde das `reload()` der Heilung
    // überschreiben.
    //
    // WEB-8f (B1): Der Rückgabewert ist der GEWORFENE Fehler (`sitzung`,
    // `hinweis`) — vorher war es `true`, und `apiCall`/`apiGet` haben ihn
    // verworfen. Folge: der Aufrufer bekam einen nackten `Error` ohne
    // `sitzung`, und die Einschränkung „nur Sitzungsfehler in den Dialog"
    // hätte einen echten 401 still gemacht. `true` bleibt trotzdem wahr, ist
    // aber jetzt an ein Objekt gebunden (Wahrheitswert unverändert).
    sitzungBeendet(SITZUNG_HINWEIS)
    const fehler = new Error(SITZUNG_HINWEIS)
    fehler.name = 'SitzungAbgelaufen'
    fehler.sitzung = true
    fehler.imBereich = true
    fehler.hinweis = SITZUNG_HINWEIS
    return fehler
}

/** Für Datei-Uploads: gleiche Sitzungs- und Fehlerprüfung ohne JSON-Schreibwiederholung. */
export async function apiAntwortPruefen(res, { fehlerWerfen = true, anfrage = null } = {}) {
    let daten = res?.dkDaten !== undefined ? res.dkDaten : await datenVon(res)
    // WEB-8b: CSRF-Ablauf auch bei Uploads/rohen fetch-Aufrufern heilen —
    // `anfrage` führt die (z. B. Multipart-)Anfrage erneut aus.
    // WEB-8c (R2): die ERSTE Antwort wird mitgegeben, damit `anfrage()` nicht
    // ein zweites Mal vor dem Token-Abruf läuft (Upload war 3x).
    if (anfrage && istCsrfAblehnung(res, daten)) {
        const ergebnis = await heileOderMelde({ anfrage, res, data: daten, ohneNavigation: true })
        res = ergebnis.res
        daten = ergebnis.data
    }
    if (!res.ok) {
        pruefeSitzungsAntwort(res, daten)
        // Ältere Kalenderfenster besitzen eigene fachliche Fehleranzeigen.
        // Sie bekommen den vollständigen Body, aber nie eine ungeprüfte Sitzung.
        if (!fehlerWerfen) return daten
        const error = new Error(daten?.message || 'Das hat nicht geklappt. Bitte später noch einmal versuchen.')
        error.status = res.status
        error.meldungen = Array.isArray(daten?.meldungen) ? daten.meldungen : []
        throw error
    }
    // Rückgabe bleibt (wie bisher) der gelesene Body — alle übrigen Aufrufer
    // lesen `data.message`. WEB-8c (R1): die zuletzt gültige Antwort hängt
    // zusätzlich als `dkAntwort` daran; `uploadDatei` prüft damit gegen die
    // WIEDERHOLTE Antwort statt gegen die alte 417.
    if (daten && typeof daten === 'object' && !daten.dkAntwort) {
        try {
            Object.defineProperty(daten, 'dkAntwort', { value: res, enumerable: false, configurable: true })
        } catch { /* eingefrorener Body: Aufrufer prüft selbst */ }
    }
    return daten
}

export async function apiCall(method, args = {}, options = {}) {
    return mitSitzungsdialog(() => apiCallRoh(method, args, options))
}

async function apiCallRoh(method, args = {}, options = {}) {
    const url = apiUrl(method)
    const imp = useImpersonation()
    const body = imp.isActive.value
        ? { ...args, __impersonated_as: imp.mitglied.value }
        : args

    // WEB-8b: Der Token wird bei JEDEM Versuch frisch gelesen — nach einer
    // Token-Erneuerung trägt die Wiederholung sonst wieder den alten.
    const anfrage = () => fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Frappe-CSRF-Token': window.__DIakonosBOOT?.csrf_token || '',
            ...(options.headers || {}),
        },
        body: JSON.stringify(body),
    })

    let res = await anfrage()
    // UXD-R8: Bei Serverfehlern (z. B. 500 "Internal Server Error") ist die
    // Antwort KEIN JSON. Ein blindes `res.json()` warf dann "Unexpected token
    // 'I', \"Internal S\"... is not valid JSON" — unlesbar fuer Ehrenamtliche.
    let data = await datenVon(res)

    // WEB-8b: CSRF-Ablauf heilen statt melden — still ein frisches Token holen,
    // die Anfrage GENAU EINMAL wiederholen; scheitert das erneut, lädt die
    // Seite einmal neu (C1/C2). Die CSRF-Prüfung des Servers liegt VOR der
    // Ausführung, deshalb ist die Wiederholung auch für schreibende Aufrufe
    // unbedenklich (C3).
    if (istCsrfAblehnung(res, data)) {
        // WEB-8c (R2): die schon gelesene Antwort mitgeben — `anfrage()` lief
        // gerade, es gibt keinen zweiten „Aufwärm“-Aufruf.
        const ergebnis = await heileOderMelde({ anfrage, res, data, ohneNavigation: true })
        res = ergebnis.res
        data = ergebnis.data
    }

    if (!res.ok) {
        const msg = data?.message || data?.exception || `HTTP ${res.status}`
        const error = new Error(msg)
        error.status = res.status
        error.meldungen = Array.isArray(data?.meldungen) ? data.meldungen : []
        // PF1: Sitzung abgelaufen/abgemeldet -> der nutzerbezogene Browser-Cache
        // darf keinen alten Stand mehr zeigen. Vollstaendig leeren.
        // WEB-8f (B1): pruefeSitzungsAntwort` ERSETZT den Fehler durch einen
        // SitzungsFehler, wenn die Antwort ein Sitzungsabbruch ist (401/419).
        // Vorher wurde der Rueckgabewert verworfen — der Aufrufer bekam einen
        // nackten `Error` ohne `sitzung`, und WEB-8f haette diesen Fehler dann
        // (richtig) NICHT mehr in den Dialog gegeben: der Weg „Sitzung
        // abgelaufen (401) aus dem Server" waere still geworden. Dieselbe
        // Stelle gibt es in `apiGetRoh`.
        const sitzungsFehler = pruefeSitzungsAntwort(res, data)
        if (sitzungsFehler) throw sitzungsFehler
        throw error
    }

    if (data.exc) {
        const excStr = String(data.exc)
        if (excStr.includes('AuditConfirmationRequired') || excStr.includes('CONFIRM_REQUIRED:')) {
            const prefix = 'CONFIRM_REQUIRED:'
            const idx = excStr.indexOf(prefix)
            let policy = null
            if (idx !== -1) {
                try {
                    policy = JSON.parse(excStr.slice(idx + prefix.length))
                } catch {
                    policy = { policy_name: 'unknown', confirm_prompt: excStr, confirm_field_label: 'Begründung' }
                }
            }
            if (!policy || !policy.policy_name) {
                policy = { policy_name: 'unknown', confirm_prompt: excStr, confirm_field_label: 'Begründung' }
            }
            throw new AuditConfirmationRequired(policy)
        }
        throw new Error(data.exc)
    }

    const message = data.message

    if (message && message.requires_confirmation === true) {
        if (!message.policy || !message.policy.policy_name) {
            throw new Error('Server hat unvollständige Audit-Policy zurückgegeben')
        }
        throw new AuditConfirmationRequired(message.policy)
    }

    // P3: AuditConfirmationRequired aus Python-Controller parsen
    const exc = data?.exception || ''
    const msg = (typeof message === 'string') ? message : (data?.exception || '')
    if (exc.includes('AuditConfirmationRequired') || (typeof msg === 'string' && msg.startsWith('CONFIRM_REQUIRED:'))) {
        let policy = null
        const prefix = 'CONFIRM_REQUIRED:'
        const idx = msg.indexOf(prefix)
        if (idx !== -1) {
            try {
                policy = JSON.parse(msg.slice(idx + prefix.length))
            } catch {
                policy = { policy_name: 'unknown', confirm_prompt: msg, confirm_field_label: 'Begründung' }
            }
        }
        if (!policy || !policy.policy_name) {
            policy = { policy_name: 'unknown', confirm_prompt: msg, confirm_field_label: 'Begründung' }
        }
        throw new AuditConfirmationRequired(policy)
    }

    return message
}

export async function apiGet(method, args = {}) {
    return mitSitzungsdialog(() => apiGetRoh(method, args))
}

async function apiGetRoh(method, args = {}) {
    const imp = useImpersonation()
    const allArgs = imp.isActive.value
        ? { ...args, __impersonated_as: imp.mitglied.value }
        : args
    const params = new URLSearchParams()
    Object.entries(allArgs).forEach(([k, v]) => {
        if (v !== undefined && v !== null) params.append(k, v)
    })
    const url = apiUrl(method) + '?' + params.toString()
    // WEB-8b: Token je Versuch frisch lesen (s. apiCall).
    const anfrage = () => fetch(url, {
        headers: {
            'X-Frappe-CSRF-Token': window.__DIakonosBOOT?.csrf_token || '',
        },
    })
    let res = await anfrage()
    let data = await datenVon(res)
    if (istCsrfAblehnung(res, data)) {
        const ergebnis = await heileOderMelde({ anfrage, res, data, ohneNavigation: true })
        res = ergebnis.res
        data = ergebnis.data
    }
    if (!res.ok) {
        // WEB-8f (B1): ein Sitzungsabbruch (401/419) wird als Sitzungsfehler
        // weitergegeben — sonst ginge er als nackter Fehler am Dialog vorbei.
        const sitzungsFehler = pruefeSitzungsAntwort(res, data)
        if (sitzungsFehler) throw sitzungsFehler
        const error = new Error(data?.message || data?.exception || `HTTP ${res.status}`)
        error.status = res.status
        error.meldungen = Array.isArray(data?.meldungen) ? data.meldungen : []
        throw error
    }
    if (data.exc) throw new Error(data.exc)
    return data.message
}
