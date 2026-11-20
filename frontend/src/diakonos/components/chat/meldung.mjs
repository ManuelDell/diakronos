/**
 * CHAT-6-UI — Melden und Moderationsreiter „Chat“: die EINE Stelle für Texte,
 * Grenzen und Auslegung der Server-Antworten (ohne DOM prüfbar).
 *
 * Grundlagen
 * ----------
 * Konzept `docs/konzepte/CHAT-KONZEPT.md` 2.5: Jede Nachricht hat „Melden“
 * (Grundauswahl Beleidigung, Spam, persönliche Daten, falsche Person,
 * Sonstiges + Freitext bis 500 Zeichen). Der Hinweis „Wer Meldungen prüft,
 * sieht diese Nachricht und die fünf davor.“ steht VOR dem Absenden im
 * Klartext.
 * Gruppe → HV/MV/GL unter „Moderation“, Reiter „Chat“; Direktnachricht/Runde
 * → Meldestelle. Ein neuer Ort in der Oberfläche entsteht NICHT: die Meldungen
 * stehen im Kalender-Kopf unter „Zu prüfen“.
 *
 * Server (`backend/src/diakronos_app/api/chat.py`):
 *   POST chat.meldung_senden(nachricht, grund, freitext)
 *        → {name, nachricht, gespraech, grund, stand, erstellt_am, meldung_offen}
 *        Fehler: „Die eigene Nachricht lässt sich nicht melden.“ /
 *                „Diese Nachricht wurde von dir bereits gemeldet.“ /
 *                „Eine gelöschte Nachricht lässt sich nicht melden.“
 *   GET  chat.meldungen_liste(stand?, gespraech?)
 *        → {meldungen: [...], offen: <Zahl>};  403 = keine Moderationsrechte
 *   POST chat.meldung_entscheiden(meldung, entscheidung, grund?)
 *        entscheidung: 'entfernen' (Grund PFLICHT) | 'verwerfen'
 *
 * Was hier NICHT steht: Rechtelogik. Wer melden/moderieren darf, entscheidet
 * der Server (400/403, gelieferte Felder). Hier wird nur gelesen und in
 * Klartext übersetzt.
 */

// Die Sätze des Fehlerkatalogs — dieselbe Quelle wie alle Seiten, keine
// eigene Formulierung („Bitte versuche es später noch einmal.“).
import { katalogText, servertextBrauchbar } from '../../../shared/fehlertexte.js'

// ── Grenzen und Schlüssel (wie im Server) ───────────────────────────────────

/** Höchstlänge des Freitexts einer Meldung (`MELDUNG_FREITEXT_MAX`). */
export const FREITEXT_MAX = 500

/** Wie viele Nachrichten VOR der gemeldeten die Moderation sieht (2.5). */
export const KONTEXT_ANZAHL = 5

/**
 * Die fünf Gründe in der Reihenfolge des Konzepts. `schluessel` geht an den
 * Server (`MELDEGRUENDE`), `label` ist der Anzeigetext — der kommt aus der
 * Oberfläche, nicht vom Server.
 */
export const GRUENDE = [
  { schluessel: 'beleidigung', label: 'Beleidigung' },
  { schluessel: 'spam', label: 'Spam' },
  { schluessel: 'persoenliche_daten', label: 'Persönliche Daten' },
  { schluessel: 'falsche_person', label: 'Falsche Person' },
  { schluessel: 'sonstiges', label: 'Sonstiges' },
]

/** Der Grund zu einem Serverschlüssel (null = unbekannt, nicht raten). */
export function grundLabel(schluessel) {
  const treffer = GRUENDE.find((g) => g.schluessel === String(schluessel || ''))
  return treffer ? treffer.label : ''
}

// ── Texte der Oberfläche (EINE Formulierung je Aussage) ─────────────────────

export const TEXTE = {
  /** Knopf/Beschriftung der Handlung (Menü, Dialog, Knopf). */
  melden: 'Melden',
  /** Titel des Dialogs. */
  dialogTitel: 'Nachricht melden',
  /**
   * Der Hinweis, der VOR dem Absenden sichtbar sein MUSS (Konzept 2.5).
   *
   * Wortlaut: Entscheidung des Operators — „Wer Meldungen prüft, sieht diese
   * Nachricht und die fünf davor.“ Er benennt den Personenkreis statt des
   * Ortes; „Moderation“ bleibt in der Anzeige gesperrt (UX2h, Glossar).
   */
  hinweis: 'Wer Meldungen prüft, sieht diese Nachricht und die fünf davor.',
  /** Ruhige Bestätigung nach dem Absenden. */
  danke: 'Danke, die Meldung ist eingegangen.',
  /** Absenden-Knopf. */
  absenden: 'Meldung absenden',
  /** Erklärung über den Gründen. */
  grundFrage: 'Warum meldest du diese Nachricht?',
  /** Freitextfeld. */
  freitextLabel: 'Noch etwas dazu sagen (freiwillig)',
  /** Reiter im Kalender-Kopf. */
  reiterLabel: 'Chat',
  /** Leerzustand der offenen Liste. */
  leerOffenTitel: 'Keine offenen Meldungen',
  leerOffenText: 'Wenn jemand eine Nachricht meldet, erscheint sie hier.',
  /** Überschrift des zweiten Abschnitts. */
  erledigtTitel: 'Erledigte Meldungen',
  /** Zähler am Reiter, wenn nichts offen ist. */
  keineOffenen: 'Nichts zu prüfen.',
}

/** Ablehnung des Servers beim Melden (403): die Nachricht ist nicht lesbar. */
export const KEIN_ZUGRIFF = 'Du kannst diese Nachricht gerade nicht melden. '
  + 'Vielleicht ist sie nicht mehr vorhanden — lade den Verlauf neu.'

/**
 * Die Erklärung, die der Grundauswahl vorangeht.
 *
 * Neutral: sie nennt den Personenkreis („wer Meldungen prüft“) und sagt, dass
 * die Gemeldete nichts über die meldende Person erfährt — ohne „Moderation“
 * (gesperrt in der Anzeige) und ohne eine Zuständigkeit zu behaupten, die im
 * 1:1 anders ist als in der Gruppe (Entscheidung des Operators).
 */
export const AUSWAHL_HILFE = 'Die Meldung sehen nur die Personen, die Meldungen prüfen. '
  + 'Wer gemeldet hat, erfährt die gemeldete Person nicht.'

// ── Bedienprüfung des Meldeformulars ────────────────────────────────────────

/**
 * Prüft die Eingaben des Meldedialogs vor dem Absenden.
 *
 * @param {{grund?: string, freitext?: string}} eingabe
 * @returns {{ok: true, grund: string, freitext: string|null} | {ok: false, fehler: string}}
 */
export function meldungPruefen({ grund = '', freitext = '' } = {}) {
  const schluessel = String(grund || '')
  if (!grundLabel(schluessel)) {
    return { ok: false, fehler: 'Bitte einen Grund auswählen.' }
  }
  const text = String(freitext ?? '')
  if (text.length > FREITEXT_MAX) {
    return { ok: false, fehler: `Der Freitext darf höchstens ${FREITEXT_MAX} Zeichen lang sein.` }
  }
  // Leerer Freitext geht als „nichts dazu gesagt“ an den Server (null) —
  // der Server nimmt auch Leerraum als „kein Text“.
  const sauber = text.trim()
  return { ok: true, grund: schluessel, freitext: sauber || null }
}

/**
 * Darf diese Nachricht gemeldet werden?
 *
 * Am Server ebenso: die EIGENE Nachricht nicht und eine GELÖSCHTE nicht. Der
 * Server ist die Wahrheit (er prüft es beim Senden erneut) — hier steht nur,
 * ob der Knopf/Eintrag überhaupt angeboten wird.
 */
export function meldbar(nachricht) {
  if (!nachricht || typeof nachricht !== 'object') return false
  if (nachricht.eigene === true) return false
  if (nachricht.geloescht === true) return false
  return Boolean(String(nachricht.ident || nachricht.name || nachricht.id || '').trim())
}

/** Freitext-Zähler „123 / 500“ — Zeichen, nicht Bytes (wie der Server). */
export function zeichenZaehler(freitext) {
  return `${String(freitext ?? '').length} / ${FREITEXT_MAX}`
}

// ── Auslegung der Server-Antworten ──────────────────────────────────────────

/** Antwort von `meldung_senden` einordnen: eingegangen? Text für die Anzeige? */
export function sendeAntwort(antwort) {
  if (antwort && (antwort.meldung_offen === true || antwort.name || antwort.stand)) {
    return { ok: true, meldung: antwort, text: TEXTE.danke }
  }
  // Antwort ohne die erwarteten Felder: nichts behaupten, was nicht belegt ist.
  return { ok: false, text: 'Die Meldung ist nicht angekommen. Bitte versuche es später erneut.' }
}

/**
 * Was zeigt der Meldedialog nach einem Fehlschlag? (Review-Punkt: „doppelte
 * Meldung → Text vom Server ruhig zeigen“.)
 *
 * Der Satz des Servers wird gezeigt, wenn er eine Auskunft ist („Diese
 * Nachricht wurde von dir bereits gemeldet.“). Eine technische oder nichtssagende
 * Meldung („HTTP 403“, „Failed to fetch“) ersetzt der Katalogtext über
 * `fehlertext` — der Aufrufer übergibt ihn als `ersatz`.
 *
 * @param {{message?: string, status?: number, exc_type?: string}|null} fehler
 * @param {{ersatz?: string, zustand?: string}} [lage]
 * @returns {string}
 */
export function meldeFehlerText(fehler, lage = {}) {
  const satz = String(fehler?.message || '').trim()
  if (satz && servertextBrauchbar(satz)) return satz
  return String(lage.ersatz || '').trim() || katalogText(lage.zustand || 'spaeter')
}

/**
 * Meldungen aus `meldungen_liste` in Anzeigezeilen übersetzen.
 *
 * `gespraech_titel` kommt vom Server: im 1:1 steht dort NEUTRAL
 * „Direktnachricht“ (nie der Name des Gegenübers) — hier wird nichts
 * neu bestimmt und nichts ersetzt. Die Zeitpunkte bleiben ROH (der Server
 * liefert UTC-naive Zeitstempel); formatiert wird erst in der Anzeige über die
 * gemeinsame Zeit-Hilfe (`shared/zeit.mjs`).
 */
export function meldungZeilen(daten) {
  const roh = Array.isArray(daten?.meldungen) ? daten.meldungen : []
  return roh
    .filter((m) => m && typeof m === 'object')
    .map((m) => ({
      ...m,
      name: String(m.name || ''),
      gespraechTitel: String(m.gespraech_titel || '').trim() || 'Direktnachricht',
      grundText: grundLabel(m.grund) || 'Sonstiges',
      freitextText: String(m.freitext || '').trim(),
      standText: standText(m.stand),
      nachrichtText: String(m.nachricht?.text ?? ''),
      nachrichtAutor: String(m.nachricht?.autor || '').trim(),
      // Der Kontext kommt aus der Antwort (Server: die fünf davor). KEINE
      // eigene Abfrage: was nicht mitkommt, ist nicht da.
      vorgeschichte: Array.isArray(m.vorgeschichte) ? m.vorgeschichte : [],
      offen: String(m.stand || '') === 'offen',
    }))
}

/** Stand einer Meldung in Klartext (Oberfläche, nicht Serverjargon). */
export function standText(stand) {
  const wert = String(stand || '')
  if (wert === 'offen') return 'offen'
  if (wert === 'erledigt') return 'erledigt'
  if (wert === 'verworfen') return 'zurückgewiesen'
  return ''
}

/** Zähler der offenen Meldungen aus der Antwort (keine erfundene 0). */
export function offenZahl(daten) {
  const n = Number(daten?.offen)
  return Number.isFinite(n) && n > 0 ? n : 0
}

// ── Entscheidungen ──────────────────────────────────────────────────────────

/**
 * Welche Entscheidungen bietet die Oberfläche an? Die Schlüssel sind die des
 * Servers (`MELDUNG_ENTSCHEIDUNGEN`), der Text ist Klartext. Beschriftung
 * nach Glossar: „Löschen“ nur für dauerhaft Entferntes — hier wird eine
 * Nachricht aus dem Verlauf genommen, dafür steht „Entfernen“. Die Meldung
 * ohne Folge heißt „Zurückweisen“ (nicht „Ablehnen“, das ist ein anderer
 * Vorgang).
 */
export const ENTSCHEIDUNGEN = [
  { schluessel: 'entfernen', label: 'Nachricht entfernen', grundPflicht: true },
  { schluessel: 'verwerfen', label: 'Meldung zurückweisen', grundPflicht: false },
]

/** Beschriftung einer Entscheidung ('' = unbekannt). */
export function entscheidungLabel(schluessel) {
  const treffer = ENTSCHEIDUNGEN.find((e) => e.schluessel === String(schluessel || ''))
  return treffer ? treffer.label : ''
}

/** Braucht diese Entscheidung einen Grund? (`entfernen` — Konzept: „Grund ist Pflicht“.) */
export function grundPflicht(schluessel) {
  const treffer = ENTSCHEIDUNGEN.find((e) => e.schluessel === String(schluessel || ''))
  return treffer ? treffer.grundPflicht === true : false
}

/**
 * Prüft eine Entscheidung vor dem Absenden — dieselbe Grenze wie im Server
 * (Grund höchstens `FREITEXT_MAX` Zeichen, beim Entfernen Pflicht).
 */
export function entscheidungPruefen({ entscheidung = '', grund = '' } = {}) {
  const wahl = String(entscheidung || '')
  if (!entscheidungLabel(wahl)) {
    return { ok: false, fehler: 'Bitte eine Entscheidung wählen.' }
  }
  const text = String(grund ?? '').trim()
  if (grundPflicht(wahl) && !text) {
    return { ok: false, fehler: 'Zum Entfernen einer Nachricht gehört ein Grund.' }
  }
  if (text.length > FREITEXT_MAX) {
    return { ok: false, fehler: `Der Grund darf höchstens ${FREITEXT_MAX} Zeichen lang sein.` }
  }
  return { ok: true, entscheidung: wahl, grund: text || null }
}

/** Die Meldung im Ausschnitt: hervorgehoben, danach die fünf davor. */
export function ausschnitt(zeile) {
  const davor = Array.isArray(zeile?.vorgeschichte) ? zeile.vorgeschichte.slice(-KONTEXT_ANZAHL) : []
  return { davor, gemeldet: zeile || null }
}

/**
 * Titel des Ausschnitts: der Gesprächstitel kommt vom Server. Für die
 * Zuordnung in der Liste dient `gespraechTitel` (1:1 neutral).
 */
export function ausschnittTitel(zeile) {
  return String(zeile?.gespraechTitel || '').trim() || 'Direktnachricht'
}

/**
 * Adresse des Reiters: die Meldungen stehen unter „Zu prüfen“ im
 * Kalender-Kopf (`#/kalender/pruefen`), der Reiter heißt „Chat“. Diese eine
 * Konstante ist das Ziel der Glocke („Neue Meldung im Chat“) und der
 * Einstieg aus dem Nachrichtenbereich — kein zweiter Ort.
 */
export const MELDUNGEN_ADRESSE = '#/kalender/pruefen?reiter=chat'

/** Wird dieser Reiter in der Adresse gewählt? Leer/anderes = die Termine. */
export function reiterAusAdresse(hash) {
  const text = String(hash || '')
  const frage = text.includes('?') ? text.slice(text.indexOf('?') + 1) : ''
  if (!frage) return ''
  const parameter = new URLSearchParams(frage)
  const wert = String(parameter.get('reiter') || '').trim()
  return wert === 'chat' ? 'chat' : ''
}

/**
 * Ist eine FEHLERLAGE „keine Moderationsrechte“ (403)?
 *
 * CHAT-6-UI-2 (Review R2, SOLL 5): Nur ein 403 heißt „dieser Weg ist zu“ —
 * ein Netz- oder Serverfehler sagt nichts über Rechte. Die Frage steht
 * deshalb als reine Funktion hier und wird nicht an jeder Stelle neu
 * beantwortet.
 *
 * @param {{status?: number}} lage — Fehler des Aufrufs
 * @returns {boolean}
 */
export function keineRechte(lage) {
  return Number(lage?.status) === 403
}
