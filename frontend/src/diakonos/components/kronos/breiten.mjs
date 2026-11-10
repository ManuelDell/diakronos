/**
 * A4 (Review 07.11. Punkt 10) — EINE Grenze für „Handy" in der Kalender-Ansicht.
 *
 * Die App hat ihre Mobile-Grenze in `composables/eingabeart.mjs`
 * (`MOBIL_GRENZE_PX` = 720 px, deckungsgleich mit `index.css`). Im Kalender
 * standen daneben 768 px (CSS und Skript) und 430 px (Chip-Form) — drei
 * Grenzen für dieselbe Frage („ist das ein Handy?"), also drei Stellen, die
 * auseinanderlaufen können.
 *
 * Diese Datei hält die Kalender-Grenzen an EINER Stelle:
 *   * `KALENDER_HANDY_PX` — Layout-Umschaltung des Kalenders (Karte, rechte
 *     Spalte, Seitenleiste-Overlay): dieselbe Zahl wie die App.
 *   * `KALENDER_ENGE_PX` — die schmale Handy-Lage (kleine Chips, Punkte statt
 *     Text). Sie ist eine INHALTS-Grenze unterhalb der Layout-Grenze und
 *     deshalb eine eigene, benannte Zahl (430 px, wie in A10 vorgesehen).
 *
 * Der Node-Test `tests/ux3i-kalender-a4.test.mjs` prüft, dass die
 * Kalender-Dateien keine eigene Layout-Zahl mehr enthalten.
 */
import { MOBIL_GRENZE_PX } from '../../composables/eingabeart.mjs'

/** Layout-Grenze der Kalender-Ansicht (Handy ≤ dieser Breite). */
export const KALENDER_HANDY_PX = MOBIL_GRENZE_PX

/** Enge Handy-Lage: Chips ohne Text, Punkte (A10). */
export const KALENDER_ENGE_PX = 430

/** Ist die Breite die Handy-Lage des Kalenders? */
export function istHandyBreite(breite) {
  const b = Number(breite)
  return Number.isFinite(b) && b > 0 && b <= KALENDER_HANDY_PX
}

/**
 * DEV-B6 (Manuel 09.11.): Ist die Handy-Lage des KALENDERS aktiv?
 *
 * Bis hierher entschied nur die Breite (`istHandyBreite`) — damit bekam ein
 * Laptop mit 702 px das Handy-Gerüst samt unterer Leiste (Befund
 * DMB-3a7d335074cc). Seit DEV-B6 gilt für das GERÜST dieselbe Bedingung wie
 * im CSS (`--layout-mobil`, tokens.css): grober Zeiger UND Breite, oder
 * flaches Querformat. Dazu kommen die sehr schmalen Fenster (<= 430 px,
 * `KALENDER_ENGE_PX`): dort ist die rechte Spalte nicht darstellbar, auch mit
 * Maus — ohne untere Leiste, ohne reservierte Abstänge.
 *
 * Die Zeiger-Abfrage wird hereingereicht (`grob`), damit diese Funktion ohne
 * Browser prüfbar bleibt (kein `matchMedia` hier).
 *
 * @param {number} breite Fensterbreite in CSS-Pixeln
 * @param {{grob?: boolean, hoehe?: number}} lage primärer Zeiger grob?, Fensterhöhe
 */
export function istKalenderHandyLage(breite, { grob = false, hoehe = 0 } = {}) {
  const b = Number(breite)
  if (!Number.isFinite(b) || b <= 0) return false
  const h = Number(hoehe)
  const flachQuer = Number.isFinite(h) && h > 0 && h <= 480
  if (grob && b <= KALENDER_HANDY_PX) return true
  if (flachQuer) return true
  return b <= KALENDER_ENGE_PX
}

/** Ist die Breite die enge Handy-Lage (sehr schmale Spalten)? */
export function istEngeBreite(breite) {
  const b = Number(breite)
  return Number.isFinite(b) && b > 0 && b <= KALENDER_ENGE_PX
}
