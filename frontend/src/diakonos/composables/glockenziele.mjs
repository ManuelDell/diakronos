/**
 * glockeZiel — Glocken-Einträge, die ein WEG sind (nicht nur Lesetext).
 *
 * CHAT-6-UI (Konzept 2.5): Die Glocke „Neue Meldung im Chat“ führt in den
 * Reiter „Chat“ unter „Zu prüfen“ (`#/kalender/pruefen?reiter=chat`) — dort
 * entscheidet die Moderation. Der Server schreibt diese Glocke mit
 * `subject = 'Neue Meldung im Chat'` und `document_type = 'chat_meldung'`
 * (`api/chat.py:_glocke_neue_meldung`); die Oberfläche liest NUR diese beiden
 * Felder der EIGENEN Meldung (die Liste kommt gefiltert über `for_user`).
 *
 * R-9 („Datenanfrage“) ist der zweite solche Weg und steht in
 * `datenAnfrage.mjs` — hier liegt NUR der Chat-Meldeweg, damit die
 * Zuordnung an EINER Stelle steht und ohne Browser prüfbar ist.
 */

import { MELDUNGEN_ADRESSE } from '../components/chat/meldung.mjs'

/** Der Betreff, den der Server schreibt (`_glocke_neue_meldung`). */
export const MELDUNG_BETREFF = 'Neue Meldung im Chat'

/** `document_type` der Glocke (derselbe Wert wie im Server). */
export const MELDUNG_ART = 'chat_meldung'

/**
 * Ist dieser Glocken-Eintrag eine Meldung aus dem Chat?
 *
 * Maßgeblich ist `document_type` (der Server setzt ihn ausdrücklich); der
 * Betreff gilt als Rückfall für Zeilen aus der Zeit vor dem Feld — beide
 * zusammen, nie ein geratener Text.
 */
export function istChatMeldung(eintrag) {
  if (!eintrag || typeof eintrag !== 'object') return false
  if (String(eintrag.document_type || '') === MELDUNG_ART) return true
  return String(eintrag.subject || '').trim() === MELDUNG_BETREFF
}

/** Ziel des Klicks: der Reiter „Chat“ im BESTEHENDEN Ort „Zu prüfen“. */
export function meldungZiel() {
  return MELDUNGEN_ADRESSE
}

export default istChatMeldung
