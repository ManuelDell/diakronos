/**
 * Zentrale API-Utility für Diakonos SPA.
 * Nutzt fetch() statt frappe.call() – www-space kompatibel.
 */

const csrf_token = window.__DIakonosBOOT?.csrf_token || ''

export class AuditConfirmationRequired extends Error {
    constructor(policy) {
        super('Audit confirmation required')
        this.name = 'AuditConfirmationRequired'
        this.policy = policy
    }
}

export async function apiCall(method, args = {}, options = {}) {
    const url = '/api/method/' + method
    const fetchOptions = {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Frappe-CSRF-Token': csrf_token,
            ...(options.headers || {}),
        },
        body: JSON.stringify(args),
    }

    const res = await fetch(url, fetchOptions)
    const data = await res.json()

    if (!res.ok) {
        const msg = data?.message || data?.exception || `HTTP ${res.status}`
        throw new Error(msg)
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
    const params = new URLSearchParams()
    Object.entries(args).forEach(([k, v]) => {
        if (v !== undefined && v !== null) params.append(k, v)
    })
    const url = '/api/method/' + method + '?' + params.toString()
    const res = await fetch(url, {
        headers: {
            'X-Frappe-CSRF-Token': csrf_token,
        },
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data?.message || data?.exception || `HTTP ${res.status}`)
    if (data.exc) throw new Error(data.exc)
    return data.message
}
