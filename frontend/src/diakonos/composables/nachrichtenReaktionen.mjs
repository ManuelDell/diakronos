/**
 * CHAT-3a — Reaktionen an einer Nachricht, ohne DOM.
 *
 * Der Server (`chat.reaktion_setzen`) hält EINE Reaktion je Person und
 * Nachricht; die Antwort ist die neue Summenliste
 * `[{reaktion, anzahl, von_mir}]`. Diese Datei beantwortet die zwei Fragen,
 * die die Oberfläche dazu hat:
 *
 *   1. Welche Zeichen bietet das Menü an, und was zeigen sie? (Set aus dem
 *      Model `REAKTIONEN` — sechs Zeichen, nicht das WhatsApp-Set.)
 *   2. Was passiert beim TIPPEN auf ein Zeichen? Ein Zeichen, das ich selbst
 *      gesetzt habe, wird beim erneuten Tippen ENTFERNT (Server: leerer Wert
 *      löscht). Ein anderes ersetzt meines (der Primärschlüssel ist
 *      `(nachricht, benutzer)` — es entsteht keine zweite Zeile).
 */
import { REAKTIONEN } from './nachrichtenLogik.mjs'

/**
 * Das Menü zum Setzen: alle Zeichen, mit dem Vermerk, ob ES MEINES ist.
 * @param {Array<{reaktion: string, anzahl: number, von_mir?: boolean}>} vorhanden
 * @returns {Array<{reaktion: string, anzahl: number, meines: boolean}>}
 */
export function reaktionsAuswahl(vorhanden = []) {
  const stand = new Map()
  for (const e of Array.isArray(vorhanden) ? vorhanden : []) {
    const zeichen = String(e?.reaktion || '')
    if (!zeichen) continue
    stand.set(zeichen, { anzahl: Math.max(0, Number(e.anzahl) || 0), meines: e.von_mir === true })
  }
  return REAKTIONEN.map((zeichen) => ({
    reaktion: zeichen,
    anzahl: stand.get(zeichen)?.anzahl || 0,
    meines: stand.get(zeichen)?.meines === true,
  }))
}

/**
 * Die Zeichen, die am Verlauf unter der Blase stehen: nur gesetzte (Anzahl > 0),
 * in der festen Reihenfolge des Sets — nicht in der Reihenfolge des Servers
 * (der sortiert schon, aber die Oberfläche soll sich darauf nicht verlassen).
 */
export function reaktionsZeile(vorhanden = []) {
  return reaktionsAuswahl(vorhanden).filter((e) => e.anzahl > 0)
}

/**
 * Was ein Tipp auf `zeichen` sendet: das Zeichen (setzen/wechseln) oder `''`
 * (entfernen, weil es MEINES ist). Dieselbe Regel wie der Server, hier nur
 * vorweggenommen, damit die Oberfläche nicht auf ein 417 laufen muss.
 *
 * @param {Array<object>} vorhanden  die Reaktionen der Nachricht
 * @param {string} zeichen
 * @returns {string} `''` = entfernen
 */
export function naechsteReaktion(vorhanden, zeichen) {
  const gewaehlt = String(zeichen || '').trim()
  if (!REAKTIONEN.includes(gewaehlt)) return ''
  const meines = reaktionsAuswahl(vorhanden).some((e) => e.reaktion === gewaehlt && e.meines)
  return meines ? '' : gewaehlt
}

/** Ist mir ein Zeichen überhaupt bekannt? (Der Server lehnt andere mit 417 ab.) */
export function istReaktion(zeichen) {
  return REAKTIONEN.includes(String(zeichen || '').trim())
}
