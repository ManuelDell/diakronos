/**
 * DEV-B6 — die Handy-Lage als Zeichenkette, OHNE Vue (Review-Nacharbeit 10.11.).
 *
 * Warum eine eigene Datei: `composables/handyLage.mjs` liefert zusätzlich
 * `useHandyLage()` und importiert dafür `vue`. Module, die ohne Oberfläche in
 * Node laufen müssen (`composables/handyHinweis.mjs`, seine Tests), dürfen
 * diese Abhängigkeit nicht erben — sie lesen die Zeichenkette hier.
 *
 * `handyLage.mjs` importiert DIESE Datei und exportiert `HANDY_LAGE_ABFRAGE`
 * weiter — es gibt also genau EINEN Text, nur zwei Zugänge.
 */
import { MOBIL_GRENZE_PX } from './eingabeart.mjs'

/** Flaches Querformat: bis zu dieser Fensterhöhe (OP-HANDY-10). */
export const FLACH_QUER_PX = 480

/**
 * Die Bedingung — identisch mit `--layout-mobil` (`tokens.css`).
 *
 *   (pointer: coarse) and (max-width: 720px),
 *   (pointer: coarse) and (max-height: 480px) and (orientation: landscape)
 *
 * BEIDE Alternativen prüfen den Zeiger (Review-Punkt 2): ein Maus-Laptop
 * 1280×450 bekommt keine Handy-Leiste.
 */
export const HANDY_LAGE_ABFRAGE =
    `(pointer: coarse) and (max-width: ${MOBIL_GRENZE_PX}px), `
    + `(pointer: coarse) and (max-height: ${FLACH_QUER_PX}px) and (orientation: landscape)`
