/**
 * UX3i — Zeilen der rechten Spalte „Zu prüfen“ (Entwurf A4).
 *
 * Die Daten kommen aus `getBoardData()` (`api/kanbanApi.js`) — demselben
 * Aufruf, den die Tafel „Zu prüfen“ macht. Kein neuer Endpunkt (Auflage der
 * Karte). Hier steht nur die Aufbereitung, damit sie ausführbar geprüft
 * werden kann (`tests/ux3i-kalender-a4.test.mjs`).
 */

import { serverZeit, wandZeit } from '../../../shared/zeit.mjs'
import { wartetAufText } from './freigabeStufen.mjs'

/** Wie viele Zeilen das Panel zeigt; der Rest steht als „+n weitere“ darunter. */
export const PRUEF_ANZEIGE = 4

/**
 * Datum aus einem Server-/Kalenderwert.
 *
 * Die Kalender-Bibliothek liefert `start` NICHT als String, sondern als
 * Objekt (`{ year, month, day }`, Monat 0-basiert). Ein `new Date(obj)`
 * scheitert dort mit „getTime is not a function“ — im Wegwerf-Stack gemessen:
 * die Spalte „Zu prüfen“ blieb deshalb leer, obwohl der Server zwei
 * Vorschläge lieferte. Beide Formen werden hier gelesen.
 */
function datumWert(wert) {
  if (!wert) return null
  if (wert instanceof Date) return Number.isNaN(wert.getTime()) ? null : wert
  if (typeof wert === 'object') {
    const { year, month, day, hour, minute } = wert
    if (Number.isFinite(year) && Number.isFinite(month) && Number.isFinite(day)) {
      const d = new Date(year, month, day, Number(hour) || 0, Number(minute) || 0)
      return Number.isNaN(d.getTime()) ? null : d
    }
    return null
  }
  return wandZeit(String(wert).trim())
}

/** Fällt jemand aus (leerer Name), bleibt der Satz trotzdem lesbar. */
function herkunftText(wer) {
  const name = String(wer || '').trim()
  return name ? `von ${name}` : ''
}

/**
 * „vor 3 Tagen“, „vor 2 Stunden“, „gerade eben“ — deutsche Kurzform.
 * `null`, wenn der Zeitpunkt fehlt oder unbrauchbar ist (dann steht nichts).
 */
export function vorText(wert, jetzt = new Date()) {
  // ZEIT-2: `creation`/`modified` sind SERVER-Zeitstempel (UTC ohne Zone) —
  // als Wandzeit gelesen war die Wartezeit 1–2 h zu kurz.
  const d = typeof wert === 'string' ? serverZeit(wert) : datumWert(wert)
  if (!d) return null
  const bezug = datumWert(jetzt)
  if (!bezug) return null
  const ms = bezug.getTime() - d.getTime()
  if (ms < 0) return 'gerade eben'
  const minuten = Math.floor(ms / 60000)
  if (minuten < 1) return 'gerade eben'
  if (minuten < 60) return `vor ${minuten} ${minuten === 1 ? 'Minute' : 'Minuten'}`
  const stunden = Math.floor(minuten / 60)
  if (stunden < 24) return `vor ${stunden} ${stunden === 1 ? 'Stunde' : 'Stunden'}`
  const tage = Math.floor(stunden / 24)
  if (tage < 30) return `vor ${tage} ${tage === 1 ? 'Tag' : 'Tagen'}`
  const monate = Math.floor(tage / 30)
  if (monate < 12) return `vor ${monate} ${monate === 1 ? 'Monat' : 'Monaten'}`
  const jahre = Math.floor(monate / 12)
  return `vor ${jahre} ${jahre === 1 ? 'Jahr' : 'Jahren'}`
}

/** Datum eines Vorschlags kurz und deutsch („Do., 06.11.“). */
export function kurzDatum(wert) {
  if (!wert) return ''
  const d = datumWert(wert)
  if (!d) return typeof wert === 'string' ? wert : ''
  return d.toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit' })
}

/**
 * Ein Vorschlag -> eine Zeile des Panels.
 *
 * A4 zeigt: Datum · Titel, darunter „von … · vor …“ und den Link „Prüfen ›“.
 * Fehlt die Herkunft (alte Vorschläge ohne Antragsteller), steht nur die
 * Zeit — nie ein leerer Punkt.
 *
 * UI-R4: `wartet` nennt die Stufe, die dran ist („wartet auf Freigabe für: …“), sofern
 * der Server eine nennt (`stufe`). Ohne Stufe bleibt die Zeile weg.
 *
 * @returns {{ id: string, titel: string, datum: string, herkunft: string,
 *            wartet: string|null }|null}
 */
export function pruefZeile(eintrag, jetzt = new Date()) {
  if (!eintrag || typeof eintrag !== 'object') return null
  const id = String(eintrag.id ?? eintrag.name ?? '').trim()
  if (!id) return null
  const titel = String(eintrag.title || eintrag.titel || '').trim() || 'Termin ohne Titel'
  // `start` ist je nach Quelle Text ODER Objekt `{ year, month, day }`
  // (Kalender-Bibliothek). Beides geht durch `kurzDatum`/`datumWert`.
  const start = eintrag.start || eintrag.first_start || ''
  // Der Server liefert die Herkunft als `antragsteller` (aus `owner`), die
  // Zeit als `creation`. `modified` ist die letzte Änderung — die sagt nicht,
  // wie lange der Vorschlag schon wartet, deshalb erst `creation`.
  const wer = eintrag.antragsteller || eintrag.owner || eintrag.created_by || ''
  const vor = vorText(eintrag.creation || eintrag.erstellt_am || eintrag.created_at
    || eintrag.modified || null, jetzt)
  const herkunft = [herkunftText(wer), vor].filter(Boolean).join(' · ')
  return { id, titel, datum: kurzDatum(start), herkunft, wartet: wartetAufText(eintrag) }
}
