/**
 * useEntwurf — wiederverwendbare lokale Entwurfs-Sicherung (ST1).
 *
 * Warum: Manuels Befund 2026-10-09 — „Wenn ich die Stammdaten pflege, während
 * ich einen Plan erstelle, ist der Stand weg. Es gibt keinen Entwurf, keine
 * Zwischenspeicherung." Dieses Composable sichert unfertige Eingaben lokal
 * (localStorage) und stellt sie beim Wiederoeffnen wieder her.
 *
 * Eigenschaften:
 * - pro Benutzer + Zweck (Schlüssel) getrennt,
 * - Speichern in try/catch: ein voller/gesperrter Speicher darf die Bedienung
 *   nie unterbrechen,
 * - Ablauf nach 14 Tagen (abgelaufene Entwürfe gelten als leer),
 * - sensible Felder (Abwesenheitsgründe) werden NICHT persistiert (siehe
 *   SENSIBLE_FELDER unten) — ein Entwurf ist nie vollständiger als nötig,
 * - ein reiner JS-Kern (entwurfKern) ohne Browser-Abhängigkeit, damit er in
 *   Node getestet werden kann; der Vue-Teil ist nur die dünne Hülle darüber.
 */

/** Nach 14 Tagen verfällt ein Entwurf. */
export const ENTWURF_TTL_MS = 14 * 24 * 60 * 60 * 1000

/** Präfix aller Entwurfs-Schlüssel im Speicher. */
export const ENTWURF_PRAEFIX = 'pr-entwurf:'

/**
 * Felder, die NIE in den Entwurf gehen (datensparsam, ST1 Punkt 4):
 * Abwesenheitsgründe und ähnliches sind sensibel.
 */
export const SENSIBLE_FELDER = ['grund', 'abwesenheitsgrund', 'abwesenheit_grund']

/**
 * Reiner Kern ohne `window` — vollständig in Node testbar.
 *
 * @param {{speicher?: object, jetzt?: () => number, benutzer?: () => string}} abh
 *   speicher: Storage-ähnliches Objekt (getItem/setItem/removeItem) oder null.
 *   jetzt:    Zeitquelle (ms). benutzer: liefert einen stabilen Benutzer-Schlüssel.
 */
export function entwurfKern({ speicher = null, jetzt = () => Date.now(), benutzer = () => '' } = {}) {
    const schluessel = (zweck) => `${ENTWURF_PRAEFIX}${benutzer() || 'anon'}:${zweck}`

    function lesenRoh(zweck) {
        if (!speicher) return null
        try {
            const text = speicher.getItem(schluessel(zweck))
            if (!text) return null
            const daten = JSON.parse(text)
            if (!daten || typeof daten !== 'object') return null
            return daten
        } catch {
            return null
        }
    }

    /** Abgelaufene Entwürfe werden als leer betrachtet (und entfernt). */
    function istAbgelaufen(daten) {
        const ts = Number(daten?.zeit)
        if (!Number.isFinite(ts)) return true
        return jetzt() - ts > ENTWURF_TTL_MS
    }

    function lade(zweck) {
        const daten = lesenRoh(zweck)
        if (!daten) return null
        if (istAbgelaufen(daten)) {
            entfernen(zweck)
            return null
        }
        return daten.wert ?? null
    }

    /** Metadaten eines vorhandenen Entwurfs (für „fortsetzen / verwerfen"). */
    function info(zweck) {
        const daten = lesenRoh(zweck)
        if (!daten) return null
        if (istAbgelaufen(daten)) {
            entfernen(zweck)
            return null
        }
        return { zeit: daten.zeit, titel: daten.titel || '' }
    }

    function speichern(zweck, wert, { titel = '' } = {}) {
        if (!speicher) return false
        try {
            speicher.setItem(schluessel(zweck), JSON.stringify({
                zeit: jetzt(), titel: String(titel || ''), wert: bereinigen(wert),
            }))
            return true
        } catch {
            return false
        }
    }

    function entfernen(zweck) {
        if (!speicher) return
        try { speicher.removeItem(schluessel(zweck)) } catch { /* Speicher gesperrt */ }
    }

    /** Ist der Entwurf einer Eingabe leer (nichts zu sichern)? */
    function istLeer(wert) {
        if (wert === null || wert === undefined) return true
        if (typeof wert === 'string') return wert.trim() === ''
        if (Array.isArray(wert)) return wert.length === 0
        if (typeof wert === 'object') return Object.keys(wert).length === 0
        return false
    }

    /**
     * Speichert nur, wenn etwas zu sichern ist — ein leerer Entwurf wird
     * gelöscht (so verschwindet er nach erfolgreichem Speichern von selbst).
     */
    function sichern(zweck, wert, optionen) {
        if (istLeer(wert)) {
            entfernen(zweck)
            return false
        }
        return speichern(zweck, wert, optionen)
    }

    return { schluessel, lade, info, speichern, sichern, entfernen, istLeer }
}

/**
 * Entfernt sensible Felder rekursiv aus einem Entwurfswert.
 * Es entsteht eine Kopie — der Originalzustand bleibt unangetastet.
 */
export function bereinigen(wert) {
    if (Array.isArray(wert)) return wert.map(bereinigen)
    if (wert && typeof wert === 'object') {
        const out = {}
        for (const [k, v] of Object.entries(wert)) {
            if (SENSIBLE_FELDER.includes(k)) continue
            out[k] = bereinigen(v)
        }
        return out
    }
    return wert
}

/**
 * Vue-Composable-Hülle. Liefert einen an einen Zweck gebundenen Entwurf.
 * Ohne localStorage (privater Modus, SSR) funktioniert alles still weiter —
 * nur ohne echte Sicherung.
 */
export function useEntwurf(zweck, optionen = {}) {
    const kern = entwurfKern({
        speicher: speicherWaehlen(),
        benutzer: benutzerSchluessel,
        jetzt: () => Date.now(),
    })
    return {
        laden: () => kern.lade(zweck),
        info: () => kern.info(zweck),
        speichern: (wert, opt) => kern.sichern(zweck, wert, opt),
        entfernen: () => kern.entfernen(zweck),
        istLeer: (wert) => kern.istLeer(wert),
        ...optionen,
    }
}

function speicherWaehlen() {
    try {
        if (typeof window !== 'undefined' && window.localStorage) return window.localStorage
    } catch { /* Zugriff gesperrt */ }
    return null
}

/** Stabiler Benutzer-Schlüssel aus den Boot-Daten (E-Mail/Kennung). */
export function benutzerSchluessel() {
    try {
        const boot = (typeof window !== 'undefined' && window.__DIakonosBOOT) || {}
        return String(boot.usermail || boot.user_email || boot.usr || boot.mitglied?.id || 'anon')
    } catch {
        return 'anon'
    }
}
