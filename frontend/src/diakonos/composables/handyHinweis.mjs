/**
 * PLAN-M1 — Hinweis am Handy: „Pläne bearbeitest du am besten am Desktop“
 * (Manuel 2026-10-23).
 *
 * Befund: Auf einem Handy ist der Plan-Rahmen zwar bedienbar, aber das
 * Bearbeiten (Tabellen, Felder, Ziehen von Personen) ist dort mühsam. Der
 * Hinweis soll deshalb nur dort erscheinen, wo er einen Sinn hat:
 *
 *   1. auf schmalen Bildschirmen (dieselbe Grenze wie die Mobil-Umschaltung
 *      der App: `MOBIL_GRENZE_PX`, siehe index.css «Responsive»),
 *   2. nur für Benutzer MIT Bearbeitungsrecht (`darf_bearbeiten` vom Server),
 *   3. und nur solange der Benutzer ihn nicht geschlossen hat.
 *
 * Nichts wird gesperrt: Ansehen bleibt vollständig möglich. Reine Betrachter
 * sehen den Hinweis nie — sie haben nichts zu wechseln.
 *
 * Regeln dieses Kerns (ohne `window`, damit in Node prüfbar):
 *   * Der geschlossene Zustand hängt am BENUTZER (nicht am Gerät) und läuft
 *     nach 30 Tagen ab — danach erscheint der Hinweis wieder.
 *   * Der Speicher ist best-effort: ein gesperrter/voller localStorage darf
 *     die Bedienung nie unterbrechen.
 *   * Kein Plan-Bezug: einmal geschlossen gilt für alle Plan-Rahmen-Seiten
 *     (Plan, Planvorlage, Stammdaten) — der Hinweis ist eine reine
 *     Bildschirm-Warnung, keine Aussage über den Plan.
 *   * Ein verstümmelter Eintrag gilt als „nicht geschlossen“ (lieber einmal
 *     zu viel erinnern als die Erinnerung stillschweigend verlieren).
 */

import { MOBIL_GRENZE_PX } from './eingabeart.mjs'

/** Präfix aller Hinweis-Schlüssel dieser Karte. */
export const HANDY_HINWEIS_PRAEFIX = 'pr-handy-hinweis:'

/**
 * Grenze in Pixeln, von der an der Hinweis erscheint.
 *
 * FIX-6c: KEINE eigene Zahl mehr — abgeleitet aus der EINEN Mobilgrenze der
 * App (`composables/eingabeart.mjs`, `MOBIL_GRENZE_PX` = 720 px, deckungsgleich
 * mit `@media (max-width: 720px)` in index.css). Zwei Literale 720 hätten
 * auseinanderlaufen können; so kann der Hinweis nicht an einer anderen Grenze
 * hängen als das Mobil-Layout, in dem er erscheint.
 */
export const HANDY_HINWEIS_PX = MOBIL_GRENZE_PX

/** Gültigkeit des geschlossenen Zustands in Tagen (Kartenvorgabe: z. B. 30). */
export const HANDY_HINWEIS_TAGE = 30

/** Text des Hinweises — wortgleich mit der Kartenvorgabe. */
export const HANDY_HINWEIS_TEXT =
    'Pläne bearbeitest du am besten an einem Desktop oder Tablet im Querformat. Ansehen geht auch hier.'

const TAG_MS = 24 * 60 * 60 * 1000

/**
 * Speicherschlüssel eines Benutzers. Leere Kennung -> `anon`
 * (dann greift die Regel „je Benutzer“ auf den Notfallschlüssel).
 */
export function handyHinweisSchluessel(benutzer) {
    const kennung = String(benutzer || '').trim() || 'anon'
    return `${HANDY_HINWEIS_PRAEFIX}${kennung}`
}

/**
 * Ist die Breite schmal? (Grenze inklusive: 720 px gehört noch dazu.)
 * @param {number} breite Fensterbreite in CSS-Pixeln
 */
export function istSchmal(breite) {
    const n = Number(breite)
    if (!Number.isFinite(n) || n <= 0) return false
    return n <= HANDY_HINWEIS_PX
}

/**
 * Soll der Hinweis erscheinen?
 *
 * @param {{schmal: boolean, darfBearbeiten: boolean, geschlossen?: boolean}} lage
 * @returns {boolean}
 */
export function hinweisZeigen({ schmal = false, darfBearbeiten = false, geschlossen = false } = {}) {
    // Reihenfolge ist Absicht: ohne Bearbeitungsrecht gibt es nichts zu
    // wechseln -> nie zeigen, auch nicht auf schmalen Bildschirmen.
    if (!darfBearbeiten) return false
    if (!schmal) return false
    return !geschlossen
}

/**
 * Reiner Kern über einem Storage-ähnlichen Objekt (getItem/setItem).
 *
 * @param {{speicher?: object, benutzer?: () => string, jetzt?: () => number}} abh
 */
export function handyHinweisKern({ speicher = null, benutzer = () => '', jetzt = () => Date.now() } = {}) {
    function schluessel() {
        return handyHinweisSchluessel(benutzer())
    }

    /** Ist der Hinweis für diesen Benutzer (noch) geschlossen? */
    function geschlossen() {
        if (!speicher) return false
        let roh
        try {
            roh = speicher.getItem(schluessel())
        } catch {
            return false
        }
        if (!roh) return false
        let eintrag
        try {
            eintrag = JSON.parse(roh)
        } catch {
            return false
        }
        const bis = Number(eintrag?.bis)
        if (!Number.isFinite(bis)) return false
        // Abgelaufen -> wieder zeigen (und den alten Eintrag entfernen).
        if (jetzt() >= bis) {
            setzen(false)
            return false
        }
        return true
    }

    /** Hinweis schließen (bis = jetzt + 30 Tage) bzw. die Merkung löschen. */
    function setzen(an) {
        if (!speicher) return false
        try {
            if (an) {
                const bis = Number(jetzt()) + HANDY_HINWEIS_TAGE * TAG_MS
                speicher.setItem(schluessel(), JSON.stringify({ bis }))
            } else {
                speicher.removeItem?.(schluessel())
            }
            return true
        } catch {
            return false
        }
    }

    /** Schließen und den neuen Zustand zurückgeben (true = jetzt geschlossen). */
    function schliessen() {
        setzen(true)
        return true
    }

    return { schluessel, geschlossen, setzen, schliessen }
}

/** Stabiler Benutzer-Schlüssel aus den Boot-Daten (E-Mail/Kennung). */
export function handyHinweisBenutzer() {
    try {
        const boot = (typeof window !== 'undefined' && window.__DIakonosBOOT) || {}
        return String(boot.user_email || boot.user_fullname || boot.user || 'anon')
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

/**
 * Vue-Hülle: ein an den aktuellen Benutzer gebundener Hinweis-Zustand.
 *
 * `breite` ist eine Funktion (damit Tests und die Vue-Seite dieselbe Quelle
 * nutzen); sie wird erst beim Lesen ausgewertet, nicht beim Aufbau.
 */
export function useHandyHinweis(optionen = {}) {
    const kern = handyHinweisKern({
        speicher: optionen.speicher !== undefined ? optionen.speicher : speicherWaehlen(),
        benutzer: optionen.benutzer || handyHinweisBenutzer,
    })
    const breite = optionen.breite || (() => (typeof window !== 'undefined' ? window.innerWidth : 0))
    return {
        schluessel: kern.schluessel,
        geschlossen: kern.geschlossen,
        setzen: kern.setzen,
        schliessen: kern.schliessen,
        istSchmal: () => istSchmal(breite()),
        zeige: (darfBearbeiten) => hinweisZeigen({
            schmal: istSchmal(breite()),
            darfBearbeiten: Boolean(darfBearbeiten),
            geschlossen: kern.geschlossen(),
        }),
    }
}
