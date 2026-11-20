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
 * CHAT-9b (Konzept S4): Die Glocke „Du wurdest erwähnt“ (`document_type =
 * 'chat_erwaehnung'`, `api/chat.py:_erwaehnung_glocke_setzen`) ist der ZWEITE
 * Chat-Weg. Ihr `document_name` ist die Kennung der NACHRICHT, nicht die des
 * Gesprächs. Welches Gespräch dazu gehört, sagt der Server über
 * `chat.nachricht_kontext(nachricht)` (Backend-Karte CHAT-9c); `erwaehnungZiel`
 * fragt ihn und führt ins Gespräch. Antwortet er neutral (unbekannt/kein
 * Recht) oder scheitert der Aufruf, bleibt es beim Bereich „Nachrichten“ —
 * eine Kennung wird nie geraten.
 * Fehlt die Glocke ganz (z. B. bei Kontaktsperre), ist das KEIN Umstand der
 * Oberfläche — hier wird daraus nichts abgeleitet.
 *
 * R-9 („Datenanfrage“) ist der dritte solche Weg und steht in
 * `datenAnfrage.mjs` — hier liegen NUR die Chat-Wege, damit die Zuordnung an
 * EINER Stelle steht und ohne Browser prüfbar ist.
 */

import { MELDUNGEN_ADRESSE } from '../components/chat/meldung.mjs'

/** Der Betreff, den der Server schreibt (`_glocke_neue_meldung`). */
export const MELDUNG_BETREFF = 'Neue Meldung im Chat'

/** `document_type` der Glocke (derselbe Wert wie im Server). */
export const MELDUNG_ART = 'chat_meldung'

/** CHAT-9b: `document_type` der Erwähnungs-Glocke (wie im Server). */
export const ERWAEHNUNG_ART = 'chat_erwaehnung'

/**
 * Der Betreff BEGINNT immer mit dem Gesprächstitel und endet mit diesem Satz
 * (`f"{titel}: Du wurdest erwähnt"`). Verglichen wird nur die ENDUNG — der
 * Titel davor ist frei (Gruppenname, Rundenname, „Direktnachricht“).
 */
export const ERWAEHNUNG_BETREFF_ENDE = ': Du wurdest erwähnt'

/** Ziel der Erwähnungs-Glocke, wenn die Zuordnung (noch) fehlt: der Bereich. */
export const NACHRICHTEN_ADRESSE = '#/nachrichten'

/** Die Gesprächsadresse — dieselbe Form, die die Seite liest. */
export function nachrichtenAdresse(gespraech) {
  const kennung = String(gespraech || '').trim()
  return kennung ? `${NACHRICHTEN_ADRESSE}/${encodeURIComponent(kennung)}` : NACHRICHTEN_ADRESSE
}

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

/**
 * Ist dieser Glocken-Eintrag eine Erwähnung im Chat? (CHAT-9b)
 *
 * Wie oben: `document_type` ist maßgeblich, der Betreff-Rückfall greift bei
 * Zeilen ohne das Feld. Eine MELDUNG ist nie eine Erwähnung — die Reihenfolge
 * der Prüfungen in der Kopfzeile entscheidet, hier wird nichts doppelt
 * zugeordnet.
 */
export function istChatErwaehnung(eintrag) {
  if (!eintrag || typeof eintrag !== 'object') return false
  if (istChatMeldung(eintrag)) return false
  if (String(eintrag.document_type || '') === ERWAEHNUNG_ART) return true
  return String(eintrag.subject || '').trim().endsWith(ERWAEHNUNG_BETREFF_ENDE)
}

/** Ziel des Klicks auf eine Meldung: der Reiter „Chat“ im BESTEHENDEN „Zu prüfen“. */
export function meldungZiel() {
  return MELDUNGEN_ADRESSE
}

/**
 * Ziel des Klicks auf eine Erwähnung: das GESPRÄCH, in dem die Nachricht steht.
 *
 * `document_name` der Glocke ist die NACHRICHT. Welches Gespräch das ist, sagt
 * der Server: `chat.nachricht_kontext(nachricht)` (GET, Backend-Karte CHAT-9c)
 * → `{gespraech, art, titel}`; bei fehlendem Recht/unbekannter Kennung kommt
 * eine neutrale „nicht gefunden“-Antwort (kein `gespraech`).
 *
 * OHNE diese Auskunft wird NICHTS behauptet: dann führt die Glocke in den
 * Bereich „Nachrichten“, wo der Eintrag des Gesprächs steht — geraten wird
 * keine Kennung. Fehlt die Glocke ganz (Kontaktsperre), ist das KEIN Umstand
 * der Oberfläche; hier wird daraus nichts abgeleitet.
 */
export async function erwaehnungZiel(eintrag, hole = null) {
  const nachricht = String(eintrag?.document_name || '').trim()
  if (!nachricht || typeof hole !== 'function') return NACHRICHTEN_ADRESSE
  try {
    const antwort = await hole('chat.nachricht_kontext', { nachricht })
    return nachrichtenAdresse(antwort?.gespraech)
  } catch {
    // Fehler oder neutrale Antwort: der Bereich bleibt das ehrliche Ziel.
    return NACHRICHTEN_ADRESSE
  }
}

export default istChatMeldung
