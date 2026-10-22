/**
 * UXD-R5 — gemeinsame, sichere Ausgabe fuer HTML-Strings.
 *
 * Mehrere Oberflaechen bauen ihre Knoten aus HTML-Text statt aus Vue-
 * Templates (d3-org-chart):
 * `diakonos/components/gruppen/OrganigrammAnsicht.vue` und die
 * eigenstaendige `organigramm/App.vue`. Vues eigenes Escaping greift dort
 * NICHT — jeder Fremdwert (Gruppenname, Leiter, Rolle, Foto-URL …) landet
 * sonst roh im Markup und waere gespeichertes Cross-Site-Scripting.
 *
 * Damit es EINE Regel gibt (statt je einer Kopie pro Renderer, die
 * auseinanderlaufen), stehen die Helfer hier zentral. Beide Renderer
 * importieren sie.
 */

/**
 * Maskiert die fuenf HTML-Sonderzeichen. `&` zuerst, damit die spaeter
 * erzeugten Entities nicht erneut ersetzt werden.
 */
export function escapeHtml(wert) {
  if (wert === null || wert === undefined) return ''
  return String(wert)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/** Nur ein gueltiger Hex-Wert (`#RGB`, `#RRGGBB`, `#RRGGBBAA`) ist CSS. */
const FARB_MUSTER = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/

/**
 * UXD-R28/DES-04: Nur ein gueltiger Hex-Wert darf in einen style-String.
 * Der Server prueft ebenfalls (`_normalisiere_farbe`); hier die zweite
 * Schranke, damit ein Altbestand (`zzz-keine-farbe`, `url(...)`) nie roh
 * in CSS landet. Leerer Rueckgabewert = "keine Farbe setzen".
 */
export function sichereFarbe(wert) {
  if (!wert) return ''
  const s = String(wert).trim()
  return FARB_MUSTER.test(s) ? s : ''
}

/**
 * UXD-R5: Foto-URLs duerfen nur `http(s)://` oder ein relativer Pfad sein.
 * `javascript:`/`data:`/`vbscript:` werden verworfen — ein `src`-Attribut
 * waere sonst ein Skript-Einschleuspunkt.
 */
export function sichereBildUrl(wert) {
  if (!wert) return ''
  const s = String(wert).trim()
  if (/^https?:\/\//i.test(s)) return escapeHtml(s)
  // Relativer Pfad: genau ein fuehrendes `/` oder `./`/`../`, kein Protokoll
  // (ein `//host` waere protokoll-relativ und damit wieder extern).
  if (/^\/(?!\/)/.test(s) || /^\.\.?\//.test(s)) return escapeHtml(s)
  return ''
}

/**
 * UXD-R28: Startwert des Farbwaehlers, wenn das Token-System keinen
 * auswertbaren Hex liefert (z. B. `oklch(...)`). `<input type="color">` kennt
 * nur `#RRGGBB`; ohne Wert zeigt der Browser Schwarz, obwohl daneben
 * "Standardfarbe" steht. Derselbe Wert wie der Server-Default in
 * `_normalisiere_farbe`.
 */
export const STANDARD_FARBE = '#667eea'

