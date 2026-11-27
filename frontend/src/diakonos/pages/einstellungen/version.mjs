/**
 * ABN-3 — die laufende Version fuer die Oberflaeche, an EINER Stelle.
 *
 * Quelle ist das Boot-Objekt `window.__DIakonosBOOT`. Server-seitig fuellt es
 * `diakronos_app.spa.boot_fuer_request()` aus `diakronos_app.version_auskunft()`
 * — derselbe Aufruf, den `/healthz` benutzt. Damit kann die Anzeige nie eine
 * andere Nummer nennen als der Zustandspruefer, und es gibt keinen zweiten
 * Abruf (kein Extra-Netzverkehr je Seite).
 *
 * Absichtlich ohne Vue: die Regeln sind so in `node --test` pruefbar, ohne
 * dass eine Komponente gebaut werden muss.
 */

/** Platzhalter, wenn das Boot-Objekt den Wert nicht hat (alter Server). */
export const VERSION_UNBEKANNT = 'unbekannt'

/**
 * Version und Build-Kennung aus einem Boot-Objekt lesen.
 *
 * `boot` ist injizierbar (Tests); ohne Angabe wird
 * `window.__DIakonosBOOT` gelesen. Beide Rueckgabewerte sind Zeichenketten:
 *
 *   version — die Versionsnummer, z.B. "2.0.0"; fehlt sie, "unbekannt".
 *             NICHT leer: ein leeres Feld neben "Version" saehe wie ein
 *             Fehler der Anwendung aus.
 *   git     — der Kurz-Hash des Builds; LEER, wenn er beim Bauen nicht
 *             gesetzt war. Die Oberflaeche blendet die Zeile dann aus bzw.
 *             schreibt "nicht im Build vermerkt" — geraten wird nichts.
 */
export function versionAusBoot(boot) {
  const quelle = (boot && typeof boot === 'object')
    ? boot
    : (typeof window !== 'undefined' && window.__DIakonosBOOT) || {}

  const version = typeof quelle.version === 'string' ? quelle.version.trim() : ''
  const git = typeof quelle.git === 'string' ? quelle.git.trim() : ''

  return {
    version: version || VERSION_UNBEKANNT,
    git,
  }
}

/**
 * Kurztext fuer die Fusszeile: nur "Version 2.0.0".
 *
 * ABN-3b/N9: Die Fusszeile steht auf JEDER Seite und fuer JEDE Sitzung — der
 * Git-Hash gehoert nicht dorthin (er nennt den genauen Quellstand). Er steht
 * weiterhin in "Einstellungen -> Ueber Diakronos", wo man ihn zum Melden eines
 * Fehlers braucht; der Server reicht ihn ohnehin nur an Administratoren.
 *
 * Steht gar keine Version im Boot (alter Server), ist der Text leer und die
 * Fusszeile bleibt weg — eine Zeile "Version unbekannt" in jeder Ansicht
 * waere ein Stoerfeuer, kein Hinweis.
 */
export function fusszeilenText(boot) {
  const { version } = versionAusBoot(boot)
  if (version === VERSION_UNBEKANNT) return ''
  return `Version ${version}`
}
