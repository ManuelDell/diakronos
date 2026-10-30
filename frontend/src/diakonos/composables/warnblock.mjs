/**
 * PLAN-W1 — Warnblock-Zustand je Benutzer merken (Befund DMB-7d8e3068c388).
 *
 * Manuel 2026-10-23: „Nur für Planer“ — die Prüf-Warnungen erscheinen
 * ausschließlich für Bearbeiter (das entscheidet der Server über
 * `darf_bearbeiten`). Zusätzlich darf der Planer den Warnblock einklappen,
 * und dieser Zustand gilt je Benutzer weiter (localStorage).
 *
 * Regeln dieses Kerns (ohne `window`, damit in Node testbar):
 *   * Der Speicher ist best-effort: ein gesperrter/voller localStorage darf
 *     die Bedienung nie unterbrechen.
 *   * Der Schlüssel hängt am BENUTZER, nicht am Gerät — zwei Menschen am
 *     selben Browser sehen nicht denselben Zustand.
 *   * Nur ausdrückliche Werte zählen: alles außer `'1'` ist „offen“. Ein
 *     unbekannter/verstümmelter Eintrag öffnet den Block, statt ihn
 *     stillschweigend zu verstecken (Warnungen sollen sichtbar sein, wenn
 *     niemand sie bewusst eingeklappt hat).
 *   * Kein Plan-Bezug: der Planer stellt „Warnungen eingeklappt“ einmal ein
 *     und behält es für alle Pläne — genau das war der Befund („die Warnung
 *     muss man einstellen oder deaktivieren können“).
 */

/** Präfix aller Warnblock-Schlüssel; wird beim Abmelden mitgeleert. */
export const WARNBLOCK_PRAEFIX = 'pr-warnblock:'

/** Zweck im Schlüssel: nur der Warnblock des Plans, nicht jede Meldung. */
const ZWECK = 'plan'

/**
 * Speicherschlüssel eines Benutzers. Leere Kennung -> `anon`
 * (localStorage ohne Anmeldung, z. B. Anmeldeseite).
 */
export function warnblockSchluessel(benutzer) {
    const kennung = String(benutzer || '').trim() || 'anon'
    return `${WARNBLOCK_PRAEFIX}${kennung}:${ZWECK}`
}

/**
 * Reiner Kern über einem Storage-ähnlichen Objekt (getItem/setItem/removeItem).
 *
 * @param {{speicher?: object, benutzer?: () => string}} abh
 */
export function warnblockKern({ speicher = null, benutzer = () => '' } = {}) {
    function schluessel() {
        return warnblockSchluessel(benutzer())
    }

    /** Ist der Warnblock eingeklappt? (Vorgabe: nein — Warnungen sind sichtbar.) */
    function eingeklappt() {
        if (!speicher) return false
        try {
            return speicher.getItem(schluessel()) === '1'
        } catch {
            return false
        }
    }

    /** Zustand setzen; ein Fehler beim Schreiben bleibt folgenlos. */
    function setzen(an) {
        if (!speicher) return false
        try {
            if (an) speicher.setItem(schluessel(), '1')
            else speicher.removeItem(schluessel())
            return true
        } catch {
            return false
        }
    }

    /** Umschalten und den neuen Zustand zurückgeben. */
    function umschalten() {
        const neu = !eingeklappt()
        setzen(neu)
        return neu
    }

    return { schluessel, eingeklappt, setzen, umschalten }
}

/** Stabiler Benutzer-Schlüssel aus den Boot-Daten (E-Mail/Kennung). */
export function warnblockBenutzer() {
    try {
        const boot = (typeof window !== 'undefined' && window.__DIakonosBOOT) || {}
        return String(boot.usermail || boot.user_email || boot.usr || boot.mitglied?.id || 'anon')
    } catch {
        return 'anon'
    }
}

/** Speicher wählen: ohne localStorage (privater Modus) still weiterarbeiten. */
function speicherWaehlen() {
    try {
        if (typeof window !== 'undefined' && window.localStorage) return window.localStorage
    } catch { /* Zugriff gesperrt */ }
    return null
}

/** Vue-Hülle: ein an den aktuellen Benutzer gebundener Warnblock-Zustand. */
export function useWarnblock(optionen = {}) {
    const kern = warnblockKern({
        speicher: speicherWaehlen(),
        benutzer: optionen.benutzer || warnblockBenutzer,
    })
    return {
        schluessel: kern.schluessel,
        eingeklappt: kern.eingeklappt,
        setzen: kern.setzen,
        umschalten: kern.umschalten,
    }
}
