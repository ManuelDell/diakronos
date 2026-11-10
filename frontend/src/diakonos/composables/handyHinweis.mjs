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
import { HANDY_LAGE_ABFRAGE } from './handyLageAbfrage.mjs'

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
 * Sehr schmale Fenster: dort ist das Planraster auch mit Maus nicht sinnvoll
 * bearbeitbar — dieselbe Zahl wie die enge Kalender-Lage (`KALENDER_ENGE_PX`,
 * A10/`components/kronos/breiten.mjs`). DW: kein zweiter Literal-Ort, sondern
 * dieselbe benannte Grenze (`KALENDER_ENGE_PX` = 430 px).
 */
export const SEHR_SCHMAL_PX = 430

/**
 * DEV-B6 (Manuel 09.11.): Ist die HANDY-Lage aktiv (Hinweis „am besten am
 * Desktop bearbeiten“ sinnvoll)?
 *
 * Bis hierher entschied nur die Breite — ein Laptop mit 702 px bekam den
 * Hinweis, obwohl er gar kein Handy ist (Befund DMB-3a7d335074cc). Jetzt
 * dieselbe Bedingung wie das Handy-Gerüst (`--layout-mobil`, tokens.css):
 * grober Zeiger UND schmal, oder flaches Querformat. Dazu die sehr schmalen
 * Fenster (<= 430 px, `KALENDER_ENGE_PX` — dort ist das Planraster auch mit
 * Maus nicht sinnvoll bedienbar).
 *
 * Der Zeiger wird hereingereicht (`grob`), damit diese Funktion ohne Browser
 * prüfbar bleibt (kein `matchMedia` hier).
 *
 * @param {number} breite Fensterbreite in CSS-Pixeln
 * @param {{grob?: boolean, hoehe?: number}} lage primärer Zeiger grob?, Fensterhöhe
 */
export function istHandyHinweisLage(breite, { grob = false, hoehe = 0, handyLage = null } = {}) {
    const n = Number(breite)
    if (!Number.isFinite(n) || n <= 0) return false
    // DEV-B6 (Review-Nacharbeit 10.11.): Liegt die Handy-Lage bereits vor
    // (aus `HANDY_LAGE_ABFRAGE`, EINE Quelle), entscheidet SIE — ein flaches
    // Maus-Fenster (1280×450) bekommt den Hinweis dann nicht mehr.
    if (typeof handyLage === 'boolean') {
        if (handyLage) return true
        return n <= SEHR_SCHMAL_PX
    }
    const h = Number(hoehe)
    if (grob && istSchmal(n)) return true
    if (grob && Number.isFinite(h) && h > 0 && h <= 480) return true
    return n <= SEHR_SCHMAL_PX
}

/**
 * Liest die Lage im Browser (matchMedia prüft den PRIMÄREN Zeiger).
 * Ohne Browser/matchMedia (Node, jsdom) gilt die reine Breite — best effort,
 * damit der Hinweis in Tests und ohne Zeigerauskunft nicht verschwindet.
 *
 * @param {{breite?: number, hoehe?: number, matchMedia?: Function}} [umgebung]
 */
export function handyHinweisLage(umgebung = {}) {
    const fenster = umgebung.fenster || (typeof window !== 'undefined' ? window : null)
    const mq = umgebung.matchMedia || (fenster && typeof fenster.matchMedia === 'function'
        ? fenster.matchMedia.bind(fenster) : null)
    if (!mq) return { grob: false, breite: Number(fenster?.innerWidth) || 0, hoehe: Number(fenster?.innerHeight) || 0 }
    const lesen = (abfrage) => {
        try {
            const treffer = mq(abfrage)
            return !!(treffer && treffer.matches)
        } catch {
            return false
        }
    }
    return {
        grob: lesen('(pointer: coarse)'),
        breite: Number(fenster?.innerWidth) || 0,
        hoehe: Number(fenster?.innerHeight) || 0,
        // DEV-B6 (Review-Nacharbeit 10.11.): DIESELBE Abfrage wie App/CSS
        // (`HANDY_LAGE_ABFRAGE`, composables/handyLage.mjs) — die Seiten
        // lesen sie über `istHandyLage` in `handyHinweisLage` mit.
        handyLage: lesen(HANDY_LAGE_ABFRAGE),
    }
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
