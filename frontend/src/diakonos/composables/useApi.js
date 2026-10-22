/**
 * Zentrale API-Utility für Diakonos SPA.
 * Nutzt fetch() statt frappe.call() – www-space kompatibel.
 */

import { useImpersonation } from './useImpersonation.js'
import { sitzungBeendet } from './useSitzungsablauf.js'
import { istSitzungsAbbruch } from '../../shared/sitzung-pruefen.js'

export class AuditConfirmationRequired extends Error {
    constructor(policy) {
        super('Audit confirmation required')
        this.name = 'AuditConfirmationRequired'
        this.policy = policy
    }
}

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
    if (istSitzungsAbbruch(res.status, data)) {
        sitzungBeendet()
        return true
    }
    return false
}

/** Für Datei-Uploads: gleiche Sitzungs- und Fehlerprüfung ohne JSON-Schreibwiederholung. */
export async function apiAntwortPruefen(res, { fehlerWerfen = true } = {}) {
    const data = await _liesAntwort(res)
    if (!res.ok) {
        pruefeSitzungsAntwort(res, data)
        // Ältere Kalenderfenster besitzen eigene fachliche Fehleranzeigen.
        // Sie bekommen den vollständigen Body, aber nie eine ungeprüfte Sitzung.
        if (!fehlerWerfen) return data
        const error = new Error(data?.message || 'Das hat nicht geklappt. Bitte später noch einmal versuchen.')
        error.status = res.status
        error.meldungen = Array.isArray(data?.meldungen) ? data.meldungen : []
        throw error
    }
    return data
}

export async function apiCall(method, args = {}, options = {}) {
    const url = '/api/method/' + method
    const csrf_token = window.__DIakonosBOOT?.csrf_token || ''
    const imp = useImpersonation()
    const body = imp.isActive.value
        ? { ...args, __impersonated_as: imp.mitglied.value }
        : args

    const fetchOptions = {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Frappe-CSRF-Token': csrf_token,
            ...(options.headers || {}),
        },
        body: JSON.stringify(body),
    }

    const res = await fetch(url, fetchOptions)
    // UXD-R8: Bei Serverfehlern (z. B. 500 "Internal Server Error") ist die
    // Antwort KEIN JSON. Ein blindes `res.json()` warf dann "Unexpected token
    // 'I', \"Internal S\"... is not valid JSON" — unlesbar fuer Ehrenamtliche.
    const data = await _liesAntwort(res)

    if (!res.ok) {
        const msg = data?.message || data?.exception || `HTTP ${res.status}`
        const error = new Error(msg)
        error.status = res.status
        error.meldungen = Array.isArray(data?.meldungen) ? data.meldungen : []
        // PF1: Sitzung abgelaufen/abgemeldet -> der nutzerbezogene Browser-Cache
        // darf keinen alten Stand mehr zeigen. Vollstaendig leeren.
        pruefeSitzungsAntwort(res, data)
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
    const imp = useImpersonation()
    const allArgs = imp.isActive.value
        ? { ...args, __impersonated_as: imp.mitglied.value }
        : args
    const params = new URLSearchParams()
    Object.entries(allArgs).forEach(([k, v]) => {
        if (v !== undefined && v !== null) params.append(k, v)
    })
    const url = '/api/method/' + method + '?' + params.toString()
    const csrf_token = window.__DIakonosBOOT?.csrf_token || ''
    const res = await fetch(url, {
        headers: {
            'X-Frappe-CSRF-Token': csrf_token,
        },
    })
    const data = await _liesAntwort(res)
    if (!res.ok) {
        pruefeSitzungsAntwort(res, data)
        const error = new Error(data?.message || data?.exception || `HTTP ${res.status}`)
        error.status = res.status
        error.meldungen = Array.isArray(data?.meldungen) ? data.meldungen : []
        throw error
    }
    if (data.exc) throw new Error(data.exc)
    return data.message
}
