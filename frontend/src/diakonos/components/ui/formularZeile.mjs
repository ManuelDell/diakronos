/**
 * BEF-DESIGN-2 — Kennungen und Texte der gemeinsamen Formular-Zeilen.
 *
 * Zwei Bausteine teilen sich diesen Rechner:
 *
 *   `DkSchalterZeile`  Zeile mit Schalter (Kästchen) links und Beschriftung
 *                      daneben; der Hilfetext steht eingerückt DARUNTER und
 *                      gehört per `aria-describedby` zum Kästchen.
 *   `DkFeldZeile`      Feld mit Hilfetext in voller Spaltenbreite — Label,
 *                      Eingabe und Hilfe teilen sich EINE Breite (BEFUND:
 *                      „Kürzel für Gemeindeleben“ war anders breit als sein
 *                      Hilfetext).
 *
 * Die Kennungen entstehen hier, damit `aria-describedby` und die `id` am
 * Hilfetext NIEMALS auseinanderlaufen (Muster aus `DkField`).
 *
 * Keine Vue-Abhängigkeit: reine Funktionen, damit die Wächter-Tests sie ohne
 * DOM prüfen können (Tests stubben `useApi.js`; hier gibt es nichts zu stubben).
 */

/**
 * EINE Kennung je Zeile — Vue-`useId` gibt es erst ab 3.5, der Rückfall ist
 * ebenfalls seiten-/hydration-sicher (Aufruf nur im Browser/SSR-Kontext).
 *
 * @param {() => string} [useId] `useId` aus Vue (falls vorhanden)
 * @returns {string} Kennung ohne Leerzeichen
 */
export function zeilenKennung(useId) {
  const roh = typeof useId === 'function'
    ? useId()
    : 'dk' + Math.random().toString(36).slice(2, 9) + Date.now().toString(36).slice(-4)
  return sicheresKennzeichen(roh)
}

/**
 * Kennzeichen ohne Zeichen, die in einem CSS-Selektor oder bei Vorlesehilfen
 * stören (Doppelpunkte, Leerzeichen, `:` aus `useId`).
 *
 * @param {unknown} wert
 * @returns {string}
 */
export function sicheresKennzeichen(wert) {
  return String(wert ?? '').replace(/[^A-Za-z0-9_-]/g, '-')
}

/**
 * Die Kennung des Hilfetextes einer Zeile.
 *
 * @param {string} kennung Ergebnis von `zeilenKennung`
 * @returns {string}
 */
export function hilfeKennung(kennung) {
  return `dk-zeile-hilfe-${sicheresKennzeichen(kennung)}`
}

/**
 * Kennung einer Fehlermeldung an derselben Zeile.
 *
 * @param {string} kennung
 * @returns {string}
 */
export function fehlerKennung(kennung) {
  return `dk-zeile-fehler-${sicheresKennzeichen(kennung)}`
}

/**
 * Was die Eingabe bzw. das Kästchen als „Beschreibung“ ansieht: die MELDUNG,
 * wenn eine dasteht — sonst der HILFETEXT, wenn es einen gibt — sonst nichts.
 * Genau die Reihenfolge aus `DkField` (Meldung gewinnt, Server weiß mehr).
 *
 * @param {{ fehler?: string, hilfe?: string, kennung: string }} angaben
 * @returns {string|undefined}
 */
export function beschriebenDurch({ fehler, hilfe, kennung }) {
  if (String(fehler ?? '').trim()) return fehlerKennung(kennung)
  if (String(hilfe ?? '').trim()) return hilfeKennung(kennung)
  return undefined
}

/**
 * Braucht die Zeile überhaupt einen Hilfetext? (Leere Zeichenketten und reine
 * Leerzeichen erzeugen KEINEN leeren Absatz — sonst entstünde ein Abstand
 * ohne Inhalt.)
 *
 * @param {unknown} text
 * @returns {boolean}
 */
export function hatHilfe(text) {
  return String(text ?? '').trim().length > 0
}
