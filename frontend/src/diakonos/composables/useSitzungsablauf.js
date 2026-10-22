import { ref } from 'vue'
import { cacheLeeren } from './usePlanrahmenCache.js'

// Eingaben bleiben im geöffneten Tab. Kein automatischer Neuversuch einer
// Schreibaktion, kein Entwurf mit personenbezogenen Daten im Browserspeicher.
export const sitzungAbgelaufen = ref(false)
export const sitzungsHinweis = ref('')

export function sitzungBeendet() {
    cacheLeeren()
    sitzungAbgelaufen.value = true
}

export function anmeldeAdresse() {
    const ziel = window.location.pathname + window.location.search + window.location.hash
    return '/login?redirect-to=' + encodeURIComponent(ziel)
}

export async function sitzungFortsetzen() {
    sitzungsHinweis.value = ''
    try {
        const res = await fetch('/api/method/diakronos.diakonos.api.session.sitzung_status', {
            credentials: 'same-origin', headers: { Accept: 'application/json' },
        })
        if (!res.ok) throw new Error('Bitte melde dich zuerst im neuen Tab an.')
        const { message } = await res.json()
        const user = window.__DIakonosBOOT?.user
        // Andere Identität: alte Eingaben und Rechte niemals weiterverwenden.
        const kennung = typeof user === 'object' ? user.name : user
        if (!kennung || message?.user !== kennung) {
            throw new Error('Du bist mit einem anderen Konto angemeldet. Schließe diesen Tab und arbeite im neuen Tab weiter.')
        }
        if (!message.csrf_token) throw new Error('Die Anmeldung konnte nicht geprüft werden. Bitte erneut versuchen.')
        window.__DIakonosBOOT.csrf_token = message.csrf_token
        // Bestehende Kalender-/Upload-Aufrufer lesen noch das Meta-Element.
        globalThis.document?.querySelector('meta[name="csrf-token"]')?.setAttribute('content', message.csrf_token)
        sitzungAbgelaufen.value = false
        return true
    } catch (e) {
        sitzungsHinweis.value = e.message || 'Keine Verbindung zum Server. Bitte erneut versuchen.'
        return false
    }
}
