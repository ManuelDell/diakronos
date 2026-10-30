/**
 * mehrBlatt.mjs — Beschriftung des Kopfes im „Mehr“-Blatt der Handy-Navigation.
 *
 * Befund DMB-a2d846875201 (FIX-1): Am Handy ließ sich das Blatt (Klasse
 * `dk-bn-sheet`, darin die Theme-Zeile `dk-bn-sheet-theme`) nicht einklappen —
 * es ging nur zu, indem man einen Eintrag im Raster wählte. Der Kopf (Griff +
 * „Navigation“) war reine Anzeige ohne Klickziel.
 *
 * Was die Karte behebt: Der Kopf ist jetzt ein Knopf und schließt das Blatt
 * (Markup und Verdrahtung in AppBottomNav.vue). Tippen außerhalb, Escape und
 * die Zurück-Geste schlossen schon vorher — sie sind im Node-Test nur
 * abgesichert, damit der festgestellte Zustand nicht still zurückfällt.
 *
 * Diese Datei hält die Kopf-Texte ohne Vue/DOM, damit sie ohne Browser prüfbar
 * sind. Verhaltensregeln liegen hier bewusst nicht: sie wären ungenutzte
 * Zweitimplementierung neben AppBottomNav.vue.
 */

/** Sichtbare Beschriftung des Blattkopfes. */
export const KOPF_TEXT = 'Navigation'

/**
 * Vorlesetext des Kopfknopfes: er nennt das Ziel und sagt, dass der Tipp
 * schließt (der sichtbare Text bleibt kurz).
 */
export const KOPF_ARIA = 'Navigation — schließen'
