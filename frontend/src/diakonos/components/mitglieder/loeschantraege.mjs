/**
 * DSGVO-2c — Regeln der Verwaltungsliste „Löschanträge“.
 *
 * Die Liste, die Freigabe und die Ablehnung stehen auf drei Flächen (Reiter
 * „Löschanträge“, Kachel der Übersicht, Seitenleiste). Damit sie nicht drei
 * eigene Wahrheiten erfinden, steht hier EINMAL, was ein Antrag bedeutet:
 *
 *  * `ANTRAG_STATUS` — die vier Stände, die der Server kennt
 *    (`models/datenschutz.STATUS_WERTE`), mit deutschem Text und Ton.
 *  * `antragsStatusText` — Stand + Datum als EINE Zeile für die Liste.
 *  * `nameFuerAntrag` — „Vorname Nachname“, sonst die Kennung. Nach der
 *    Löschung bleiben beide Felder leer; dann heißt die Zeile wie überall
 *    sonst „Gelöschte Person“ (Regel in `composables/geloeschte-person.mjs`).
 *  * `freigabeVollstaendig` — der Freigabedialog verlangt das ABTIPPEN des
 *    vollständigen Namens. Verglichen wird ohne Rücksicht auf Groß-/
 *    Kleinschreibung und Leerzeichen — die Verwaltung soll nicht an einem
 *    doppelten Leerzeichen scheitern, aber auch nicht am Klicken allein.
 *  * `begruendungFehler` — die Ablehnung braucht eine Begründung. Der Server
 *    prüft dasselbe noch einmal (`_pruefe_begruendung`, höchstens `GRUND_MAX`).
 *  * `mailfehlerText` — „Mail nicht eingerichtet“ bekommt den Link zur
 *    Mailversand-Seite, ein gescheiterter Versand den Hinweis, dass NICHTS
 *    gelöscht wurde, ein Rechtfehler den Satz, an wen man sich wendet.
 *
 * Nichts hiervon entscheidet über Rechte: wer freigeben darf, sagt allein der
 * Server (`datenschutz.loeschung_bestaetigen` / `loeschantrag_ablehnen`).
 */
import { GELOESCHT_ANZEIGE, GELOESCHT_PRAEFIX } from '../../composables/geloeschte-person.mjs'
// `serverFehlerText` liegt in `useVerwaltung.js`. Diese Datei wird auch von
// Knoten-Tests geladen (ohne gebaute Oberfläche) — und `useVerwaltung.js`
// zieht `useApi.js` nach, das `vue` braucht. Deshalb hier NICHT importiert:
// die kleine Übersetzung steht unten als `fehlerSatz`, in derselben
// Reihenfolge wie dort (erst strukturierte Meldungen, dann `message`).

/** Fehlertext wie `serverFehlerText` in `useVerwaltung.js` (gleiche Reihenfolge). */
function fehlerSatz(err, fallback) {
  const meldungen = Array.isArray(err?.meldungen) ? err.meldungen : []
  if (meldungen.length) {
    const teile = meldungen
      .map(m => (typeof m === 'string' ? m : (m?.meldung || m?.hinweis || '')))
      .filter(Boolean)
    if (teile.length) return teile.join(' ')
  }
  const text = String(err?.message || '').trim()
  if (!text || /^HTTP \d+$/.test(text)) {
    if (err?.status === 403) return 'Dafür fehlt dir das Recht. Bitte die Gemeindeleitung fragen.'
    return fallback
  }
  return text
}

/** Die Stände aus `models/datenschutz.STATUS_WERTE` — deutsche Beschriftung. */
export const ANTRAG_STATUS = {
  offen: { text: 'offen', ton: 'warn' },
  abgelehnt: { text: 'abgelehnt', ton: 'info' },
  zurueckgezogen: { text: 'zurückgezogen', ton: 'neutral' },
  ausgefuehrt: { text: 'gelöscht', ton: 'ok' },
}

/** Höchstlänge der Begründung — derselbe Wert wie `models/datenschutz.GRUND_MAX`. */
export const BEGRUENDUNG_MAX = 2000

/** Zulässige Auswahl der Liste. „offen“ ist die Arbeitsliste (Server-Standard). */
export const ANTRAG_FILTER = [
  { wert: 'offen', text: 'Offen' },
  { wert: 'abgelehnt', text: 'Abgelehnt' },
  { wert: 'zurueckgezogen', text: 'Zurückgezogen' },
  { wert: 'ausgefuehrt', text: 'Gelöscht' },
  { wert: 'alle', text: 'Alle' },
]

/** Datum wie im übrigen Diakronos: ``22.10.2026``; leer bleibt leer. */
export function datumDeutsch(wert) {
  const text = String(wert ?? '').trim()
  const treffer = text.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!treffer) return ''
  return `${treffer[3]}.${treffer[2]}.${treffer[1]}`
}

/**
 * Stand eines Antrags als ein Satz für die Liste — ohne Fachbegriffe.
 *
 * Der Server liefert `status`; fehlt er (Bestandszeilen aus N6), gilt
 * `erledigt_am`. Unbekannte Werte werden NICHT erfunden, sondern als „offen“
 * gezeigt — der Server entscheidet, was damit passiert.
 */
export function antragsStatusText(antrag) {
  const roh = String(antrag?.status || '').trim().toLowerCase()
  const stand = ANTRAG_STATUS[roh] ? roh : (antrag?.erledigt_am ? 'ausgefuehrt' : 'offen')
  const eintrag = ANTRAG_STATUS[stand]
  const am = datumDeutsch(
    stand === 'abgelehnt' ? antrag?.abgelehnt_am
      : stand === 'zurueckgezogen' ? antrag?.zurueckgezogen_am
        : stand === 'ausgefuehrt' ? (antrag?.anonymisiert_am || antrag?.erledigt_am)
          : antrag?.beantragt_am,
  )
  return { stand, text: eintrag.text, ton: eintrag.ton, am }
}

/** „Beantragt am 22.10.2026“ — das Datum, das in jeder Zeile stehen muss. */
export function beantragtText(antrag) {
  const am = datumDeutsch(antrag?.beantragt_am)
  return am ? `Beantragt am ${am}` : 'Beantragt (Datum fehlt)'
}

/**
 * Anzeigename des Antragstellers.
 *
 * Vor der Löschung stehen Vor- und Nachname in der Antwort der Verwaltung
 * (`get_loeschantraege`); nach der Anonymisierung sind beide leer und die
 * Zeile heißt „Gelöschte Person“ — dieselbe Regel wie in der Mitgliederliste.
 */
export function nameFuerAntrag(antrag) {
  const teile = [antrag?.vorname, antrag?.nachname]
    .map(teil => String(teil ?? '').trim())
    .filter(Boolean)
  if (teile.length) return teile.join(' ')
  // Nach der Anonymisierung ist die Person gelöscht: Vor-/Nachname sind leer
  // und die Kennung beginnt mit `geloescht-`. Dann steht hier derselbe Text
  // wie in der Mitgliederliste — keine Kennung, kein leerer Rest.
  const kennung = String(antrag?.mitglied || antrag?.name || '').trim()
  if (kennung.toLowerCase().startsWith(GELOESCHT_PRAEFIX)) return GELOESCHT_ANZEIGE
  return kennung || GELOESCHT_ANZEIGE
}

/** Vergleicht zwei Namen so, wie Ehrenamtliche tippen: ohne Groß/Klein, ohne doppelte Leerzeichen. */
function gleichGetippt(a, b) {
  const säubern = (wert) => String(wert ?? '').trim().replace(/\s+/g, ' ').toLocaleLowerCase('de-DE')
  return säubern(a) === säubern(b)
}

/**
 * Darf „Löschung freigeben“ gedrückt werden?
 *
 * Nur wenn der VOLLSTÄNDIGE Name abgetippt ist. Ein leerer Name (gelöschte
 * Person) kann nicht bestätigt werden — dann ist der Antrag ohnehin erledigt.
 */
export function freigabeVollstaendig({ name = '', eingabe = '', laeuft = false } = {}) {
  if (laeuft) return false
  const soll = String(name ?? '').trim()
  if (!soll) return false
  const ist = String(eingabe ?? '').trim()
  if (!ist) return false
  return gleichGetippt(ist, soll)
}

/**
 * Fehlertext für die Begründung der Ablehnung — leer heißt „noch keine“.
 * Der Server lehnt dasselbe ab, hier wird es nur früher gesagt.
 */
export function begruendungFehler(wert) {
  const text = String(wert ?? '').replace(/\r\n?/g, '\n').trim()
  if (!text) return 'Bitte eine Begründung angeben — die Person erhält sie per E-Mail.'
  if (text.length > BEGRUENDUNG_MAX) {
    return `Die Begründung ist zu lang (${text.length} Zeichen). Bitte auf höchstens ${BEGRUENDUNG_MAX} Zeichen kürzen.`
  }
  if (/[\u0000-\u0008\u000B-\u001F\u007F]/.test(text)) {
    return 'Die Begründung enthält unerlaubte Zeichen. Bitte nur normalen Text eingeben.'
  }
  return ''
}

/** Ist der Serverfehler „Mailversand ist nicht eingerichtet“? */
export function istMailNichtEingerichtet(err) {
  const texte = [
    err?.message,
    ...(Array.isArray(err?.meldungen) ? err.meldungen.map(m => m?.meldung || m?.hinweis) : []),
  ]
  return texte.some(text => /Mailversand ist nicht eingerichtet/i.test(String(text || '')))
}

/**
 * Fehler aus Freigeben/Ablehnen als verständlicher Satz für Ehrenamtliche.
 *
 * ``teil`` sagt, was NICHT passiert ist („Es wurde nichts gelöscht.“ / „Es
 * wurde nichts abgelehnt.“) — ein Serverfehler darf nie so klingen, als wäre
 * die Löschung trotzdem gelaufen.
 */
export function freigabeFehlerText(err, teil = 'Es wurde nichts geändert.') {
  if (istMailNichtEingerichtet(err)) {
    return 'Mailversand ist nicht eingerichtet — ohne ihn kann ein Löschantrag nicht '
      + 'bearbeitet werden. Bitte zuerst den Mailversand einrichten.'
  }
  const text = fehlerSatz(err, 'Das hat nicht geklappt. Bitte noch einmal versuchen.')
  // Die Meldungen des Servers sagen bereits, dass nichts passiert ist.
  if (/nichts (gelöscht|abgelehnt)|Es wurde NICHTS/i.test(text)) return text
  if (err?.status === 417) return `${text} ${teil}`
  return text
}
