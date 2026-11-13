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
 *
 * B6-N2 (09.11., Punkt 3): `istKalenderHandyLage` ist hier ENTFALLEN. Die
 * Funktion war tot (kein Aufrufer) und irreführend: sie wertete jedes flache
 * Fenster (`hoehe <= 480`) als Handy-Lage — also auch ein flaches MAUS-Fenster.
 * Die gültige Regel steht seit DEV-B6 allein in `composables/handyLage.mjs`
 * (grob + Breite, oder flach + Querformat + grob) und wird als KLASSE
 * `.dk-app--handy` gesetzt; ein zweiter Ort für dieselbe Frage war die
 * Ursache der Befunde. Siehe Regel 19 im Kartenkommentar: der zugehörige
 * Testblock wurde mit derselben Begründung angepasst.
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

/** Ist die Breite die enge Handy-Lage (sehr schmale Spalten)? */
export function istEngeBreite(breite) {
  const b = Number(breite)
  return Number.isFinite(b) && b > 0 && b <= KALENDER_ENGE_PX
}
