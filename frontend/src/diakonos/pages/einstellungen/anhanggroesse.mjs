/**
 * anhanggroesse.mjs — Höchstgröße je Anhang im Chat, Admin-Einstellung
 * (Karte CHAT-12c-UI).
 *
 * Server (`backend/src/diakronos_app/api/chat.py`,
 * `chat_anhanggrenze.holen_einstellungen`/`setze_einstellungen`):
 *
 *   GET  chat.chat_einstellungen_lesen
 *        → {anhang_max_mb, standard: 10, minimum: 1, maximum: 50}
 *   POST chat.chat_einstellungen_speichern(anhang_max_mb)   — NUR Administrator
 *        → {anhang_max_mb, gespeichert: true, standard, minimum, maximum}
 *        Fehler (422): „Anhanggröße muss zwischen 1 und 50 MB liegen.“ bzw.
 *        „Anhanggröße muss eine ganze Zahl in MB sein.“
 *
 * Diese Datei rechnet damit — ohne Vue und ohne DOM, damit die Regeln im
 * Node-Test prüfbar sind (`frontend/tests/chat12c-anhang-groesse.test.mjs`).
 *
 * GRUNDSATZ (wie `fristen.mjs`): Keine Zahl wird erfunden. Was der Server
 * nicht schickt, wird nicht behauptet — nur die GRENZEN haben eine Vorgabe,
 * damit die Eingabe auch ohne Serverantwort prüfen kann.
 */

/** Feldkennung in der Oberfläche (Sprungmarke `dk-sprung-<id>`). */
export const FELD_ID = 'anhang'

/** Vorgaben, wenn der Server keine Grenzen mitschickt (Kartentext: 1–50, Standard 10). */
export const GRENZEN_VORGABE = { minimum: 1, maximum: 50, standard: 10 }

/** Der Hinweis unter dem Feld — er sagt, wofür der Wert gilt. */
export const HINWEIS = 'gilt für Anhänge im Chat'

/**
 * Die Zahl aus der Serverantwort — nur ganze Zahlen, sonst `null`.
 * Ein fehlender oder unbrauchbarer Wert wird NICHT durch eine geratene Zahl
 * ersetzt.
 */
export function zahl(wert) {
  if (wert === null || wert === undefined || wert === '') return null
  const n = Number(wert)
  return Number.isInteger(n) ? n : null
}

/**
 * Der Anzeigestand aus der Antwort: gespeicherter Wert, Standard und Grenzen —
 * jeweils nur, wenn der Server sie liefert (Grenzen mit Vorgabe, damit die
 * Eingabe prüfen kann).
 */
export function standLesen(antwort) {
  const a = antwort || {}
  const min = zahl(a.minimum)
  const max = zahl(a.maximum)
  const std = zahl(a.standard)
  return {
    gespeichert: zahl(a.anhang_max_mb),
    standard: std === null ? GRENZEN_VORGABE.standard : std,
    minimum: min === null ? GRENZEN_VORGABE.minimum : min,
    maximum: max === null ? GRENZEN_VORGABE.maximum : max,
  }
}

/**
 * Eingabe prüfen — dieselben Grenzen wie der Server (`_pruefe_mb`).
 * `wert` ist der Text aus `input type="number"`; leer ist keine Zahl.
 * Ergebnis: `{ ok, fehler: Satz, wert: Zahl|null }`.
 */
export function eingabePruefen(wert, stand) {
  const min = stand?.minimum ?? GRENZEN_VORGABE.minimum
  const max = stand?.maximum ?? GRENZEN_VORGABE.maximum
  // Text zuerst BESCHNEIDEN: `Number(' ')` wäre 0 — eine Eingabe aus lauter
  // Leerzeichen ist aber leer.
  const text = wert === null || wert === undefined ? '' : String(wert).trim()
  const n = text === '' ? NaN : Number(text)
  if (text === '' || !Number.isInteger(n)) {
    return { ok: false, fehler: 'Bitte eine ganze Zahl in MB eingeben.', wert: null }
  }
  if (n < min || n > max) {
    return { ok: false, fehler: `Bitte eine Zahl zwischen ${min} und ${max} eingeben.`, wert: null }
  }
  return { ok: true, fehler: '', wert: n }
}

/** Feldwert als Text für das Eingabefeld (leer, wenn der Wert fehlt). */
export function feldText(stand) {
  const n = zahl(stand?.gespeichert)
  return n === null ? '' : String(n)
}

/** Der Text „Auf Standard zurücksetzen“ — die Zahl aus der Antwort. */
export function standardText(stand) {
  const n = zahl(stand?.standard)
  return n === null ? '' : String(n)
}

/** Der Hinweis unter dem Feld: „Standard: 10 MB · gilt für Anhänge im Chat“. */
export function standardHinweis(stand) {
  const n = zahl(stand?.standard)
  return n === null ? HINWEIS : `Standard: ${n} MB · ${HINWEIS}`
}

/** Die Nutzlast für `chat.chat_einstellungen_speichern` — ganze MB. */
export function speicherNutzlast(wert) {
  return { anhang_max_mb: zahl(wert) }
}

/** Ist etwas geändert? (Speichern-Knopf nur, wenn ja — wie bei den Fristen.) */
export function geaendert(wert, stand) {
  return zahl(wert) !== zahl(stand?.gespeichert)
}

/**
 * Der Satz zu einem misslungenen Speichern.
 *
 * 403 ist keine Panne: die Administration fehlt dieser Sitzung (der Server
 * prüft `rechte.ist_admin`). Alles andere ist die Server-Meldung — sie ist für
 * Menschen geschrieben („Anhanggröße muss zwischen 1 und 50 MB liegen.“).
 */
export function speicherFehlerText(fehler, { ersatz = 'Die Anhangsgröße konnte nicht gespeichert werden.' } = {}) {
  if (Number(fehler?.status) === 403) return 'Nur die Administration darf die Anhangsgröße ändern.'
  const roh = String(fehler?.message || '').trim()
  return roh || ersatz
}
