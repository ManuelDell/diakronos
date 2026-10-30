/**
 * WEB-3 — Anbindung an die Website-Verwaltung (Primo) aus der Oberfläche.
 *
 * EINE Stelle für alle Aufrufe — die Komponenten kennen keinen Pfad. Zwei
 * Endpunkte (Vertrag WEB-1b):
 *
 *   GET  diakronos.diakronos.api.website.status            -> Zustand
 *   POST diakronos.diakronos.api.website.login_uebergabe   -> {url}
 *
 * Beides läuft über `apiGet`/`apiCall` und damit durch die CSRF-Middleware
 * (POST trägt `X-Frappe-CSRF-Token`). Der Übergabe-Endpunkt nimmt NUR POST an;
 * ein GET endet serverseitig mit 403 — hier wird deshalb nie `apiGet` benutzt.
 *
 * S3 — kein Token im Diakronos-DOM:
 * Die Antwort trägt das Token im FRAGMENT der Adresse
 * (`…/diakronos-sso.html#token=…`). Es wird nie in den Vue-Zustand gelegt,
 * nicht geloggt und nicht angezeigt. Der Aufrufer bekommt es EINMAL als
 * Argument für `window.open` (`oeffnen`), damit es sofort an Primo geht und
 * nicht im Speicher der SPA stehen bleibt.
 */
import { ref } from 'vue'
import { apiCall, apiGet } from './useApi.js'
import {
    sichereUebergabeUrl,
    uebergabeFehlertext,
    verbindungsDetails,
    zustandsText,
} from './website.mjs'

const API_STATUS = 'diakronos.diakronos.api.website.status'
const API_UEBERGABE = 'diakronos.diakronos.api.website.login_uebergabe'

/**
 * Öffnet eine Adresse in einem neuen Tab, ohne dem Ziel Zugriff auf das
 * Diakronos-Fenster zu geben (`noopener`) und ohne die Herkunft zu verraten
 * (`noreferrer`). Der Fragment-Teil (Token) geht dabei NICHT an Server/Proxy,
 * weil Browser Fragmente nie mitsenden.
 *
 * WICHTIG (im Wegwerf-Stack gefunden): Mit `noopener` gibt `window.open`
 * laut Spezifikation IMMER `null` zurück — auch wenn der Tab geöffnet wurde.
 * Der Rückgabewert taugt deshalb NICHT als Beweis für einen Popup-Blocker;
 * ein `!fenster` als Fehler zu werten, hätte jedem Benutzer eine falsche
 * Meldung gezeigt, obwohl Primo im neuen Tab korrekt aufging.
 *
 * Rückgabe: `false` nur, wenn gar nicht geöffnet werden konnte (ungültiges
 * Ziel, kein `window`) und `true` sonst. Ob der Browser blockiert hat, sagt
 * nur ein Aufruf OHNE `noopener` — auf den wird bewusst nicht zurückgefallen.
 *
 * @param {string} url
 * @param {{oeffnen?: ((url: string, ziel: string, merkmale: string) => any)|null}} [optionen]
 * @returns {boolean}
 */
export function oeffneInNeuemTab(url, { oeffnen = null } = {}) {
    const ziel = sichereUebergabeUrl(url)
    if (!ziel) return false
    const auf = oeffnen || (typeof window !== 'undefined' ? window.open.bind(window) : null)
    if (!auf) return false
    auf(ziel, '_blank', 'noopener,noreferrer')
    return true
}

export function useWebsite() {
    /** Serverzustand (`status`, `version`, `site_count`, `url`, `warnung`). */
    const daten = ref(null)
    const laedt = ref(false)
    const geprueft = ref(false)
    const fehler = ref('')

    /**
     * Zustand neu abfragen („Verbindung prüfen“ und beim Öffnen des
     * Abschnitts). Ein Fehler wird als Text gehalten, nicht geworfen: die
     * Einstellungsseite soll auch dann stehen, wenn der Server nicht antwortet.
     */
    async function pruefen() {
        laedt.value = true
        fehler.value = ''
        try {
            const antwort = await apiGet(API_STATUS)
            daten.value = antwort || null
            geprueft.value = true
            return daten.value
        } catch (e) {
            // Ohne Berechtigung gibt es nichts zu zeigen — der Server hat
            // bewusst mit 403 geantwortet.
            daten.value = null
            fehler.value = uebergabeFehlertext(e)
            geprueft.value = true
            return null
        } finally {
            laedt.value = false
        }
    }

    /** Anzeigbare Ableitungen — die Regeln stehen in `website.mjs`. */
    function zustand() {
        return zustandsText(daten.value?.status)
    }

    function details() {
        return verbindungsDetails(daten.value)
    }

    /**
     * Login-Übergabe holen und den Tab öffnen.
     *
     * Rückgabe `{ok, url, fehler}` — `url` ist die gelieferte Adresse (der
     * Aufrufer hat sie selbst angefordert), `fehler` ein Klartext für die
     * Oberfläche. Es wird NICHTS gespeichert.
     */
    async function primoOeffnen({ oeffnen = null, oeffne = oeffneInNeuemTab } = {}) {
        try {
            const antwort = await apiCall(API_UEBERGABE, {})
            const url = sichereUebergabeUrl(antwort?.url)
            if (!url) {
                return {
                    ok: false,
                    url: '',
                    fehler: 'Der Server hat keine gültige Adresse geliefert. '
                        + 'Bitte einen Admin benachrichtigen.',
                }
            }
            // `oeffne` meldet nur, ob der Aufruf moeglich war. Ob der Browser
            // den Tab wirklich gezeigt hat, laesst sich mit `noopener` NICHT
            // feststellen (window.open liefert dort immer null) — deshalb KEINE
            // falsche Erfolgs- oder Blockermeldung, sondern ein neutraler
            // Hinweis mit dem Weg zum Nachholen.
            const gestartet = oeffne(url, { oeffnen })
            if (!gestartet) {
                return {
                    ok: false,
                    url,
                    fehler: 'Der neue Tab ließ sich nicht öffnen. Bitte Pop-ups für '
                        + 'diese Seite erlauben und erneut versuchen.',
                }
            }
            return { ok: true, url, fehler: '' }
        } catch (e) {
            return { ok: false, url: '', fehler: uebergabeFehlertext(e) }
        }
    }

    return {
        daten,
        laedt,
        geprueft,
        fehler,
        pruefen,
        zustand,
        details,
        primoOeffnen,
    }
}
