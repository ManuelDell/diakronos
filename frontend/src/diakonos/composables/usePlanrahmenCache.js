/**
 * PF1: Nutzerbezogener Browser-Cache (stale-while-revalidate) fuer die
 * Lese-Antworten der Arbeitsseiten des Plan-Rahmens.
 *
 * Zweck: Die Seite zeigt den zuletzt gesehenen Stand SOFORT aus dem Browser
 * und tauscht ihn still gegen den Serverstand aus, sobald die Antwort da ist.
 * Nur wenn sich etwas unterscheidet, wird getauscht.
 *
 * Sicherheit (verbindlich):
 *  - Der Schluessel enthaelt IMMER die Nutzerkennung (`userId`), die Version
 *    des Caches und den Endpunkt samt Parametern. Zwei Nutzer teilen sich nie
 *    einen Eintrag; ein Nutzerwechsel leert den Cache vollstaendig.
 *  - Der Cache traegt keine Rechte-Entscheidung: der Server bleibt die eine
 *    Wahrheit. Aendern sich Rollen/Rechte, liefert der Server einen anderen
 *    Stand, der den Cache ersetzt (der Stand-Vergleich greift).
 *  - Generator- und Trockenlauf-Ergebnisse werden NICHT gecacht.
 *  - Beim Abmelden (Nutzerkennung wechselt auf leer) wird der Cache geleert.
 *  - Ist der Speicher nicht verfuegbar oder voll, faellt alles auf normales
 *    Laden zurueck (kein Fehler).
 *
 * Das ist ausdruecklich KEIN Server-Cache: es gibt keinen geteilten Zustand
 * zwischen Nutzern und keinen Zwischenspeicher im Backend.
 */

// Wird bei JEDER inhaltlichen Aenderung an der Cache-Form erhoeht; aeltere
// Staende im Browser eines Nutzers werden damit verworfen (neue App-Version).
const CACHE_VERSION = 'pf1-v1'
const PRAEFIX = 'dk-pr-swr:'

// Schluessel, die NIE gecacht werden (Ergebnisse, die sich je Aufruf aendern
// koennen oder Rechenarbeit des Servers ohne Version sind).
const NIE_CACHEN = new Set([
    'plan_generieren',
    'trockenlauf',
    'schema_holen',
    'doku_holen',
    'kochbuch_holen',
])

function speicher() {
    // Speicher darf nie die Seite kippen: jeder Fehler -> null (kein Cache).
    try {
        const s = window.localStorage
        if (!s) return null
        const probe = PRAEFIX + '__probe'
        s.setItem(probe, '1')
        s.removeItem(probe)
        return s
    } catch {
        return null
    }
}

/** Aktuelle Nutzerkennung (Anmeldung + Impersonation) — Teil JEDES Schluessels. */
let nutzerKennung = ''
export function cacheNutzerSetzen(kennung) {
    const neu = String(kennung || '')
    if (neu !== nutzerKennung) {
        if (nutzerKennung) cacheLeeren()   // Nutzerwechsel/Abmelden: alles weg
        nutzerKennung = neu
    }
}

export function cacheNutzer() {
    return nutzerKennung
}

function schluessel(name, args) {
    return PRAEFIX + CACHE_VERSION + ':' + nutzerKennung + ':' + name + ':' +
        JSON.stringify(args || {}, Object.keys(args || {}).sort())
}

/**
 * Gespeicherten Stand lesen. Liefert `null`, wenn kein gueltiger Eintrag
 * existiert (falscher Nutzer, andere Cache-Version, Speicher nicht lesbar).
 */
export function standLesen(name, args) {
    if (!nutzerKennung || NIE_CACHEN.has(name)) return null
    const s = speicher()
    if (!s) return null
    try {
        const roh = s.getItem(schluessel(name, args))
        if (!roh) return null
        const eintrag = JSON.parse(roh)
        if (eintrag?.v !== CACHE_VERSION || eintrag?.nutzer !== nutzerKennung) return null
        return eintrag.daten
    } catch {
        return null
    }
}

/** Stand speichern. Fehler (voller Speicher) werden ignoriert. */
export function standSchreiben(name, args, daten) {
    if (!nutzerKennung || NIE_CACHEN.has(name) || daten === undefined) return
    const s = speicher()
    if (!s) return
    try {
        s.setItem(schluessel(name, args), JSON.stringify({
            v: CACHE_VERSION, nutzer: nutzerKennung, zeit: Date.now(), daten,
        }))
    } catch {
        // Speicher voll/nicht schreibbar -> normales Laden, kein Fehler.
        cacheLeeren()
    }
}

/** Billiger Vergleich zweier Staende: nur bei Unterschied tauschen. */
export function gleich(a, b) {
    try {
        return JSON.stringify(a) === JSON.stringify(b)
    } catch {
        return false
    }
}

/** Einen einzelnen Eintrag verwerfen (nach Schreibaktion). */
export function eintragVerwerfen(name, args) {
    const s = speicher()
    if (!s) return
    try {
        s.removeItem(schluessel(name, args))
    } catch {
        /* egal */
    }
}

/** Gesamten Planrahmen-Cache dieses Browsers leeren (Abmelden/Nutzerwechsel). */
export function cacheLeeren() {
    const s = speicher()
    if (!s) return
    try {
        const weg = []
        for (let i = 0; i < s.length; i += 1) {
            const k = s.key(i)
            if (k && k.startsWith(PRAEFIX)) weg.push(k)
        }
        for (const k of weg) s.removeItem(k)
    } catch {
        /* egal */
    }
}
