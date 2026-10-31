/**
 * WEB-7 — Wann führt ein ungültiger Link OHNE Rückmeldung auf die Hauptseite?
 *
 * Ziel (Manuel 2026-10-30): „Überall wo man keine Rückmeldung braucht, die
 * Umleitung (auf die Hauptseite).“ Hauptseite ist die Wurzel der DOMAIN
 * (`/`) — NICHT das Diakronos-Präfix: unter `dev.ecg-hn.de` liegt dort die
 * Gemeinde-Website, ohne Präfix landet `/` in Diakronos (Login).
 *
 * Diese Datei ist die EINE Entscheidungsstelle. Alle drei öffentlichen Seiten
 * (Registrierung, Gast, Organigramm) und der Server (`spa.py`) lesen hier bzw.
 * spiegeln die Regeln wörtlich — damit Anzeige und Weiterleitung nicht
 * auseinanderlaufen können.
 *
 * Regeln der Karte (U1–U4), nicht erweitern:
 *
 *   U1/U2  unwiderruflich toter Link — Token unbekannt ODER deaktiviert
 *          („Ungültiger oder deaktivierter Registrierungslink“) ODER die
 *          Seite wurde ohne `?token=` aufgerufen
 *             → sofort `location.replace('/')`, ohne Meldung.
 *   U3     UMKEHRBAR / Rückmeldung nötig — Meldung BLEIBT stehen:
 *            - 429 „zu viele Versuche“ (Rate-Limit),
 *            - 5xx / Netzwerk / Diakronos nicht erreichbar,
 *            - zeitliche Grenzen des Links („Anmeldung ab … möglich“,
 *              „abgelaufen“, „maximale Anzahl erreicht“): die Person bekommt
 *              einen neuen Link; Blind-Weiterleiten sähe wie ein kaputter Link
 *              aus, obwohl der Link nur noch nicht/ nicht mehr gilt.
 *   U4     geschützte Seiten → Login wie bisher (hier nicht behandelt).
 *
 * Zusätzlich gilt für den Absendeweg: ein 403 NACH gültiger Anzeige ist der
 * Kampf zweier gleichzeitiger Absender um den letzten Platz — der Link war
 * gültig, die Meldung sagt warum. Also Meldung (U3), nicht Umleitung.
 *
 * SICHERHEIT (U6): Beim Weiterleiten wird KEIN Token in Log/Konsole
 * geschrieben; die Weiterleitung ersetzt den Verlaufseintrag (`replace`),
 * damit „Zurück“ nicht wieder auf die tote Seite führt.
 */

/** Was der Server als Grund mitschickt (`window.__diakronos.linkGrund`). */
export const GRUND_UNBEKANNT = 'unbekannt'

/** Wurzel der Domain — das Ziel jeder Weiterleitung (NICHT `basisPfad()`). */
export const HAUPTSEITE = '/'

/**
 * Ist der Linkgrund ein „der Link ist tot“-Grund (U1/U2)?
 *
 * `unbekannt` ist der Standard aus `_validate_token` (Token nicht in der
 * Datenbank, Link deaktiviert, leer). Die übrigen Gründe sind zeitlich oder
 * mengenmäßig begrenzt und tragen eine Erklärung für die Person (U3).
 */
export function istToterLink(grund) {
    return String(grund ?? '').trim() === GRUND_UNBEKANNT
}

/**
 * Soll die Seite ohne Rückmeldung auf die Hauptseite führen?
 *
 * @param {object} lage
 * @param {string} lage.grund       `linkGrund` vom Server ('' = Link gültig)
 * @param {boolean} lage.tokenFehlt Seite wurde ohne `?token=` aufgerufen
 * @returns {boolean}
 */
export function brauchtWeiterleitung({ grund = '', tokenFehlt = false } = {}) {
    // Ohne Token gibt es nichts anzuzeigen und keine Erklärung (U1).
    if (tokenFehlt) return true
    if (!grund) return false
    return istToterLink(grund)
}

/**
 * `location.replace` auf die Hauptseite — ersetzt den Eintrag, damit „Zurück“
 * nicht auf die tote Seite zurückfällt (U6).
 *
 * @param {boolean} weiter        Ergebnis von `brauchtWeiterleitung`
 * @param {object}  [fenster]     `window` (Test-Attrappe)
 * @returns {boolean} ob umgeleitet wurde
 */
export function weiterleitenZurHauptseite(weiter, fenster = globalThis.window) {
    if (!weiter) return false
    try {
        fenster.location.replace(HAUPTSEITE)
    } catch {
        // Kein `location` (Test/Sandbox) — nichts zu tun, nie werfen.
        return false
    }
    return true
}
