import { ref } from 'vue'
import { cacheLeeren } from './usePlanrahmenCache.js'
import { anmeldeUrl, apiUrl } from '../../shared/basis.js'
// WEB-8c (R4): Der im Hauptbereich aufgedeckte Sitzungsfehler liegt hier ab
// (eigene Datei ohne Importe -> kein Ring), damit dieser Dialog ihn zeigt.
import { sitzungsFehlerLesen, sitzungsFehlerVergessen, sitzungsFehlerBeobachten } from './sitzungsstand.js'

// Eingaben bleiben im geöffneten Tab. Kein automatischer Neuversuch einer
// Schreibaktion, kein Entwurf mit personenbezogenen Daten im Browserspeicher.
export const sitzungAbgelaufen = ref(false)
export const sitzungsHinweis = ref('')

export function sitzungBeendet(hinweis = '') {
    cacheLeeren()
    // WEB-8b (C2): kam der Abbruch aus der CSRF-Heilung (kein zweites
    // Neuladen erlaubt), wird der Grund im Dialog gezeigt.
    if (hinweis) sitzungsHinweis.value = hinweis
    sitzungAbgelaufen.value = true
}

/**
 * WEB-8c (R4): Ein mitten im Hauptbereich aufgedecktes Sitzungsende — OHNE
 * den Seitenwechsel der Heilung. Derselbe Dialog wie bei 401/419
 * (`SitzungsHinweis.vue`), aber ein fest zu setzender Hinweis.
 *
 * Der Weg dorthin: `zurAnmeldung()`/`neuLadenOderAnmelden()` können mit
 * `ohneNavigation: true` aufgerufen werden (Hauptbereich) — dann passiert
 * keine `location.assign`/`reload`, sondern der Aufrufer entscheidet. Hier
 * wird nur der (ggf. schon gesetzte) Navigationsmerker zurückgenommen, damit
 * die nächste echte Prüfung wieder normal laufen kann.
 */
export function sitzungImBereichBeenden(hinweis = '') {
    sitzungsHinweis.value = ''
    sitzungBeendet(hinweis)
}

/**
 * WEB-8c (R4): Ist im Hauptbereich ein Sitzungsende aufgedeckt worden, zeigt
 * dieser Dialog es (fester Hinweis). Die Statusanzeige ruft die Funktion an
 * (und den Wert direkt im Markup — dann ist der Dialog GERENDERT, bevor der
 * Vorgang als ausgeliefert gilt). Der Fehler wird NICHT beim Lesen verbraucht,
 * sondern erst, wenn „Weiterarbeiten" wieder angemeldet hat.
 */
export function sitzungsEndeUebernehmen() {
    const fehler = sitzungsFehlerLesen()
    if (!fehler) return ''
    sitzungImBereichBeenden(fehler.hinweis || '')
    return fehler.hinweis || ''
}

/** Nach erfolgreichem Weiterarbeiten ist der abgelegte Fehler verbraucht. */
export function sitzungsEndeVergessen() {
    sitzungsFehlerVergessen()
}

/**
 * WEB-8d (M2): Auf ein neu aufgedecktes Sitzungsende HÖREN statt es 4x je
 * Sekunde abzufragen. Der Stand ist ein `shallowRef`; die Rückmeldung kommt
 * sofort bei jeder Änderung. `SitzungsHinweis.vue` beobachtet damit ohne
 * Takt und meldet sich in `onUnmounted` wieder ab.
 *
 * @param {() => void} rueckmeldung wird gerufen, sobald ein Fehler abgelegt ist
 * @returns {() => void} Abmeldefunktion
 */
export function sitzungsEndeBeobachten(rueckmeldung) {
    // `sofort: true` — beim Aufbau der Anzeige kann schon ein Fehler vorliegen.
    return sitzungsFehlerBeobachten(
        (fehler) => { if (fehler) rueckmeldung() },
        { sofort: true },
    )
}

export function anmeldeAdresse() {
    const ziel = window.location.pathname + window.location.search + window.location.hash
    return anmeldeUrl(ziel)
}

export async function sitzungFortsetzen() {
    sitzungsHinweis.value = ''
    try {
        const res = await fetch(apiUrl('diakronos.diakonos.api.session.sitzung_status'), {
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
        sitzungsEndeVergessen()
        return true
    } catch (e) {
        sitzungsHinweis.value = e.message || 'Keine Verbindung zum Server. Bitte erneut versuchen.'
        return false
    }
}
