/**
 * ZEIT-2 — EINE Stelle für die Anzeige von SERVER-Zeitstempeln.
 *
 * DAS PROBLEM
 * -----------
 * Das Backend schreibt technische Zeitstempel (`creation`, `modified`,
 * `zeitstempel`, Veroeffentlichungsstand …) als UTC, aber OHNE Zeitzone:
 *   `"2026-11-09 16:09:12.123456"`   (Python `str(datetime)` / ISO ohne Suffix)
 * Termin-Zeiten (`element_start`, `datum_von` …) sind dagegen LOKALE
 * WANDZEITEN ohne Zeitzone — sie beschreiben die Uhr an der Wand der Gemeinde
 * (`CALENDAR_TIMEZONE`, Vorgabe Europe/Berlin, siehe BETRIEBSANLEITUNG,
 * Abschnitt „Kalenderimport“). Beide sehen im JSON gleich aus.
 *
 * Das Frontend las bisher alles mit `new Date(x.replace(' ', 'T'))`. Ein
 * solcher String OHNE Offset gilt in JavaScript als ORTSZEIT des Browsers —
 * ein UTC-Zeitstempel wurde also als deutsche Uhrzeit gelesen und lag im
 * Sommer 2 h, im Winter 1 h daneben („gesetzt am …, 17:09“ statt 16:09).
 *
 * DIE LOESUNG (und warum sie so gewaehlt ist)
 * -------------------------------------------
 * Nur die WENIGEN technischen Zeitstempel bekommen eine eigene Deutung
 * (`serverZeit`), Termin-Wandzeiten bleiben unveraendert (`wandZeit`) —
 * sonst wuerde JEDER Termin um 1–2 h verrutschen.
 *
 * Die Umstellung liegt im FRONTEND, nicht im Backend. Grund: eine Aenderung
 * der Server-Ausgabe (z. B. `…Z` an jedes `creation`/`modified`) aendert den
 * Vertrag fuer ALLE Abnehmer (CalDAV, Primo-Bausteine unter `deploy/primo`,
 * externe Auswertungen) und fuer den Bestand. Ausserdem liegen in den
 * Tabellen beide Sorten ohne Zone: der Bestand wurde mit `datetime.now()`
 * (Ortszeit) geschrieben, neuere Zeilen mit `_now()` (UTC). Ein pauschales
 * Suffix am Backend waere fuer aeltere Zeilen schlicht falsch. Das Frontend
 * dagegen kennt genau die Felder, die technisch sind, und laesst die
 * Termin-Zeiten unangetastet — die kleinste Aenderung mit dem kleinsten
 * Risiko.
 *
 * Anzeige: Europe/Berlin (die Zone der Gemeinde) — unabhängig davon, in
 * welcher Zeitzone der Browser laeuft. Tageszeiten werden so angezeigt, wie
 * sie in der Gemeinde gelten.
 */

/** Zone der Gemeinde (Vorgabe der Installation, siehe ON-2-Vertrag). */
export const GEMEINDE_ZONE = 'Europe/Berlin'

/*
 * Ein Zeitstempel OHNE Zeitzone:
 *   "2026-11-09 16:09:12.123456" / "2026-11-09T16:09" / "2026-11-09"
 * Nicht erfasst (und damit als „schon eindeutig“ durchgelassen) werden
 * Werte mit `Z` oder Offset — sie tragen ihre Zone selbst.
 */
const NAIV = /^\s*(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?)?\s*$/
const MIT_ZONE = /(?:Z|z|[+-]\d{2}:?\d{2})\s*$/

/** Zerlegung eines naiven Zeitstempels — `null`, wenn das Format nicht passt. */
function zerlege(wert) {
  if (typeof wert !== 'string') return null
  const m = wert.match(NAIV)
  if (!m) return null
  return {
    jahr: Number(m[1]),
    monat: Number(m[2]),
    tag: Number(m[3]),
    stunde: Number(m[4] || 0),
    minute: Number(m[5] || 0),
    sekunde: Number(m[6] || 0),
    millis: Number(String(m[7] || '0').slice(0, 3).padEnd(3, '0')),
  }
}

/**
 * Rohes Datum aus einem SERVER-Zeitstempel (UTC ohne Zone).
 *
 * @param {string|number|Date|null|undefined} wert
 * @returns {Date|null} `null`, wenn der Wert fehlt oder unlesbar ist.
 *
 * Regeln:
 *  * fehlt/leer        -> `null` (Aufrufer entscheidet über den Platzhalter)
 *  * `Date`            -> unveraendert (schon ein Zeitpunkt)
 *  * Zahl              -> Milliseconds seit 1970 (Unix-Zeit ist UTC)
 *  * `…Z` / Offset     -> so gelesen, wie es dasteht (Zone ist eindeutig)
 *  * ohne Zone         -> als UTC gelesen
 */
export function serverZeit(wert) {
  if (wert === null || wert === undefined || wert === '') return null
  if (wert instanceof Date) return Number.isNaN(wert.getTime()) ? null : wert
  if (typeof wert === 'number') {
    const d = new Date(wert)
    return Number.isNaN(d.getTime()) ? null : d
  }
  const text = String(wert).trim()
  if (!text) return null
  if (MIT_ZONE.test(text)) {
    // „2026-11-09 16:09:12+00:00“ (Python `str()`): Safari liest die Form mit
    // Leerzeichen nicht — erst in ISO-Form bringen.
    const d = new Date(text.replace(/^(\d{4}-\d{2}-\d{2}) /, '$1T'))
    return Number.isNaN(d.getTime()) ? null : d
  }
  const z = zerlege(text)
  if (!z) return null
  // Date.UTC: der Wert IST UTC. (new Date(...) wuerde Ortszeit annehmen.)
  const d = new Date(Date.UTC(
    z.jahr, z.monat - 1, z.tag, z.stunde, z.minute, z.sekunde, z.millis,
  ))
  if (Number.isNaN(d.getTime())) return null
  // Rueckwaertspruefung gegen „31.02.“ & Co.: Date.UTC rollt still weiter.
  if (d.getUTCFullYear() !== z.jahr || d.getUTCMonth() !== z.monat - 1
    || d.getUTCDate() !== z.tag) return null
  return d
}

/** Zerlegung eines Wandzeit-Textes (Datum, optional mit Uhrzeit). */
const WAND = /^\s*(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?)?\s*$/

/**
 * Rohes Datum aus einer LOKALEN WANDZEIT (Termin, Kalender, Tagesdatum).
 *
 * Bleibt absichtlich so, wie JavaScript naheliegende Werte liest: ein Datum
 * ohne Zone ist die Uhrzeit an der Wand. Der Name macht an der Aufrufstelle
 * sichtbar, dass hier KEINE UTC-Umrechnung gewollt ist.
 *
 * Die Form `YYYY-MM-DD[ HH:MM[:SS]]` wird ZU FUSS gebaut: `new Date('2026-11-08')`
 * waere UTC-Mitternacht und damit in Berlin schon der Vortag 23:00 — der
 * Tageswechsel waere genau der Fehler, den diese Datei verhindern soll.
 *
 * @param {string|number|Date|null|undefined} wert
 * @returns {Date|null}
 */
export function wandZeit(wert) {
  if (wert === null || wert === undefined || wert === '') return null
  if (wert instanceof Date) return Number.isNaN(wert.getTime()) ? null : wert
  if (typeof wert === 'number') {
    const d = new Date(wert)
    return Number.isNaN(d.getTime()) ? null : d
  }
  const text = String(wert).trim()
  if (!text) return null
  const m = text.match(WAND)
  if (m) {
    const jahr = Number(m[1])
    const monat = Number(m[2])
    const tag = Number(m[3])
    const d = new Date(jahr, monat - 1, tag,
      Number(m[4] || 0), Number(m[5] || 0), Number(m[6] || 0),
      Number(String(m[7] || '0').slice(0, 3).padEnd(3, '0')))
    if (Number.isNaN(d.getTime())) return null
    // Rueckwaertspruefung gegen „31.02.“ & Co.
    if (d.getFullYear() !== jahr || d.getMonth() !== monat - 1 || d.getDate() !== tag) return null
    return d
  }
  const d = new Date(text)
  return Number.isNaN(d.getTime()) ? null : d
}

/**
 * Nur das KALENDERDATUM eines Zeitstempels („2026-11-09“) — ohne Rechnung.
 *
 * Fuer Geburtstage, Einwilligungsdaten und „dabei seit“: das Datum steht
 * bereits als Datum in der Antwort und darf durch keine Zeitzonenrechnung
 * auf den Vor-/Folgetag rutschen.
 */
export function serverDatum(wert) {
  const text = String(wert ?? '').trim()
  const m = text.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!m) return null
  const jahr = Number(m[1])
  const monat = Number(m[2])
  const tag = Number(m[3])
  // Mittag als Anker: die Anzeige in Europe/Berlin bleibt derselbe Tag.
  const d = new Date(Date.UTC(jahr, monat - 1, tag, 12))
  if (Number.isNaN(d.getTime())) return null
  if (d.getUTCFullYear() !== jahr || d.getUTCMonth() !== monat - 1 || d.getUTCDate() !== tag) return null
  return d
}

/** Datum + Uhrzeit in der Zone der Gemeinde („09.11.2026, 17:09“). */
export function serverZeitText(wert, optionen = {}) {
  const d = serverZeit(wert)
  if (!d) return ''
  return new Intl.DateTimeFormat('de-DE', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
    timeZone: GEMEINDE_ZONE,
    ...optionen,
  }).format(d)
}

/** Nur die Uhrzeit in der Zone der Gemeinde („17:09“). */
export function serverUhrzeitText(wert) {
  const d = serverZeit(wert)
  if (!d) return ''
  return new Intl.DateTimeFormat('de-DE', {
    hour: '2-digit', minute: '2-digit', timeZone: GEMEINDE_ZONE,
  }).format(d)
}

/**
 * Nur das Datum eines Zeitstempels in der Zone der Gemeinde
 * („09.11.2026“) — gedacht fuer kurze Anzeigen.
 */
export function serverDatumText(wert, optionen = {}) {
  const d = typeof wert === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(wert.trim())
    ? serverDatum(wert)
    : serverZeit(wert)
  if (!d) return ''
  return new Intl.DateTimeFormat('de-DE', {
    day: '2-digit', month: 'short', year: 'numeric',
    timeZone: GEMEINDE_ZONE,
    ...optionen,
  }).format(d)
}

/**
 * Wandelt einen Zeitstempel in die Schreibform des Servers
 * („2026-11-09 16:09:12“) — z. B. fuer Vergleiche in einem Formular.
 */
export function serverZeitIso(wert) {
  const d = serverZeit(wert)
  if (!d) return ''
  const zwei = (n) => String(n).padStart(2, '0')
  return `${d.getUTCFullYear()}-${zwei(d.getUTCMonth() + 1)}-${zwei(d.getUTCDate())} `
    + `${zwei(d.getUTCHours())}:${zwei(d.getUTCMinutes())}:${zwei(d.getUTCSeconds())}`
}
