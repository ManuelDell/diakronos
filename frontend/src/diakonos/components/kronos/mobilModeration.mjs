/**
 * A10 — goldene Statuszeile „Zu prüfen“ auf dem Handy, NUR für Moderatoren.
 *
 * Warum hier und nicht in der Seite: dieselbe Zeile braucht drei Regeln, die
 * man prüfen können muss, ohne einen Browser zu starten —
 *
 *   * SICHTBARKEIT: nur mit `can_moderate` (dieselbe Quelle wie das
 *     Desktop-Panel „Zu prüfen“, UX3d/UX3i). Der Server liefert die Daten
 *     ohnehin nur Moderatoren; ohne Recht gibt es die Zeile nicht — keinen
 *     leeren Platz und kein Abzeichen (Karte A10).
 *   * TEXT: „Zu prüfen (3) · Von Gruppen eingetragen“ (Entwurf A10). Die
 *     Zahl bleibt weg, solange sie unbekannt ist (`null`) — nie eine
 *     erfundene 0 (dieselbe Regel wie `kalenderKopf.eingeblendeteZahl`).
 *   * ZIEL: die vorhandene Tafel `#/kalender/pruefen` (UX3d). Kein vierter
 *     Reiter, kein neuer Endpunkt.
 */
import { pruefZeilenText } from './mobilAnsicht.mjs'

/**
 * Zeile der Moderation für die Mobil-Ansicht.
 *
 * A10-N2 (Review 09.11., Punkt 4): Bei 0 offenen Vorschlägen erscheint die
 * Zeile NICHT — sie führte zu einer leeren Tafel und nahm dem ersten
 * Bildschirm die Höhe der Tagesliste weg. `null` heißt unbekannt und bleibt
 * sichtbar (ohne Zahl): dann ist es ehrlich zu sagen „da ist etwas zu
 * prüfen, die Zahl kenne ich noch nicht“.
 *
 * @param {{ darfPruefen?: boolean, zahl?: number|null }} lage
 * @returns {{ sichtbar: boolean, text: string, zahl: number|null, ziel: string }|null}
 *   `null`, wenn die Zeile nicht erscheinen darf.
 */
export function moderationsZeile({ darfPruefen = false, zahl = null } = {}) {
  if (darfPruefen !== true) return null
  const n = (zahl === null || zahl === undefined || zahl === '')
    ? null
    : (Number.isFinite(Number(zahl)) ? Number(zahl) : null)
  // Bekannte 0: nichts zu tun, also keine Zeile und kein leerer Platz.
  if (n === 0) return null
  return {
    sichtbar: true,
    text: pruefZeilenText(n),
    zahl: n,
    ziel: '#/kalender/pruefen',
  }
}

/** Nur die Kennzahl, wie sie das Desktop-Panel zeigt (`null` = unbekannt). */
export function zeilenZahl(zahl) {
  return moderationsZeile({ darfPruefen: true, zahl })?.zahl ?? null
}

export default { moderationsZeile, zeilenZahl }
