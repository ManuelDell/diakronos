/**
 * datumZeit — deutsche Datum-/Uhrzeit-Bausteine (OP-UI-20, Standard S8).
 *
 * Befund: Datum und Uhrzeit wurden auf vier Arten eingegeben — flatpickr mit
 * sichtbarem ISO-Wert („2026-12-30 00:00“), `datetime-local` („30.12.2026,
 * 00:00“ je nach Browser), zwei getrennte native Felder und ein Freitextfeld.
 * Dazu kam: Ein neuer Termin begann immer um 00:00, ein Serienende war ein
 * nacktes Textfeld.
 *
 * Festlegungen (S8):
 *  - Sichtbar ist IMMER Deutsch: „Mi., 30.12.2026, 19:00“.
 *  - Der Wert im Modell bleibt das, was der Server erwartet: „2026-12-30 19:00“.
 *  - Vorschlag für neue Termine: 19:00–20:00 bzw. die angeklickte Stunde.
 *  - Wochenbeginn ist Montag.
 *
 * Reine Funktionen ohne Vue/DOM — im Node-Test prüfbar.
 */

const WOCHENTAGE = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag']
const WOCHENTAGE_KURZ = ['So.', 'Mo.', 'Di.', 'Mi.', 'Do.', 'Fr.', 'Sa.']
const MONATE = [
  'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
  'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember',
]

/** Vorschlagszeiten (S8): Beginn 19:00, Dauer eine Stunde. */
export const VORSCHLAG_BEGINN = '19:00'
export const VORSCHLAG_DAUER_MINUTEN = 60

/** Zwei Zeichen mit führender Null. */
function zwei(n) {
  return String(n).padStart(2, '0')
}

/**
 * Beliebige Server-/ISO-Schreibweise → { datum: 'YYYY-MM-DD', zeit: 'HH:MM' }.
 * Versteht „2026-12-30 19:00“, „2026-12-30T19:00:00“, „2026-12-30“ und
 * bereits getrennte Werte. Unlesbares ergibt leere Felder (kein „NaN“).
 */
export function zerlegeDatumZeit(wert) {
  const leer = { datum: '', zeit: '' }
  if (wert === null || wert === undefined) return leer
  const roh = String(wert).trim()
  if (!roh) return leer
  const m = roh.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{1,2}):(\d{2}))?/)
  if (!m) return leer
  const [, jahr, monat, tag, stunde, minute] = m
  const datum = `${jahr}-${monat}-${tag}`
  // Ein reines Datum hat keine Uhrzeit — dann bleibt die Zeit leer, statt
  // heimlich „00:00“ zu behaupten (genau das zeigte der Befund).
  const zeit = stunde === undefined ? '' : `${zwei(Number(stunde))}:${minute}`
  return { datum, zeit }
}

/** { datum, zeit } → „YYYY-MM-DD HH:MM“ (Serverformat) bzw. „YYYY-MM-DD“. */
export function baueDatumZeit(datum, zeit) {
  const d = String(datum || '').trim()
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) return ''
  const z = String(zeit || '').trim()
  if (!z) return d
  const m = z.match(/^(\d{1,2}):(\d{1,2})$/)
  if (!m) return d
  return `${d} ${zwei(Number(m[1]))}:${zwei(Number(m[2]))}`
}

/** „YYYY-MM-DD“ → „30.12.2026“ (unlesbares bleibt leer). */
export function datumDeutsch(datum) {
  const m = String(datum || '').match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!m) return ''
  return `${m[3]}.${m[2]}.${m[1]}`
}

/** „HH:MM“ → „19:00 Uhr“. */
export function zeitDeutsch(zeit) {
  const m = String(zeit || '').match(/^(\d{1,2}):(\d{2})/)
  if (!m) return ''
  return `${zwei(Number(m[1]))}:${m[2]} Uhr`
}

/** Wochentag eines „YYYY-MM-DD“ (deutsch, lang und kurz). */
export function wochentag(datum) {
  const m = String(datum || '').match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!m) return { lang: '', kurz: '' }
  // Mittagszeit, damit die Zeitzone den Tag nicht verschiebt.
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 12))
  if (Number.isNaN(d.getTime())) return { lang: '', kurz: '' }
  return { lang: WOCHENTAGE[d.getUTCDay()], kurz: WOCHENTAGE_KURZ[d.getUTCDay()] }
}

/** Monatsname für die Anzeige („Dezember“). */
export function monatName(nummer) {
  const i = Number(nummer) - 1
  return MONATE[i] || ''
}

/**
 * Deutsche Vorschau eines Termins:
 *  - mit Zeit:  „Mi., 30.12.2026, 19:00–20:00 Uhr“
 *  - ohne Zeit: „Mi., 30.12.2026“
 *  - unvollständig: nur der vorhandene Teil, nie ein Platzhalter.
 */
export function vorschau(datum, zeit, endeZeit = '') {
  const d = datumDeutsch(datum)
  if (!d) return ''
  const tag = wochentag(datum).kurz
  const kopf = tag ? `${tag}, ${d}` : d
  const z = zeitDeutsch(zeit)
  if (!z) return kopf
  const e = zeitDeutsch(endeZeit)
  return e ? `${kopf}, ${z.replace(' Uhr', '')}–${e}` : `${kopf}, ${z}`
}

/** Minuten seit Mitternacht; -1 wenn unlesbar. */
function minuten(zeit) {
  const m = String(zeit || '').match(/^(\d{1,2}):(\d{2})/)
  if (!m) return -1
  const h = Number(m[1])
  const mi = Number(m[2])
  if (h > 23 || mi > 59) return -1
  return h * 60 + mi
}

/** Vorschlag für das Ende: eine Stunde nach dem Beginn (über Mitternacht gekappt). */
export function endeAusBeginn(beginn, dauerMinuten = VORSCHLAG_DAUER_MINUTEN) {
  const start = minuten(beginn)
  if (start < 0) return ''
  const ende = Math.min(start + dauerMinuten, 23 * 60 + 59)
  return `${zwei(Math.floor(ende / 60))}:${zwei(ende % 60)}`
}

/**
 * Beginn für einen neuen Termin (S8): 19:00–20:00. Wurde im Kalender eine
 * Stunde angeklickt, gilt diese Stunde und die Dauer bleibt eine Stunde.
 */
export function vorschlagBeginn(geklickteStunde = null) {
  // `Number(null)` waere 0 — ein fehlender Klick darf nicht Mitternacht ergeben.
  if (geklickteStunde === null || geklickteStunde === undefined || geklickteStunde === '') {
    return VORSCHLAG_BEGINN
  }
  const h = Number(geklickteStunde)
  if (Number.isInteger(h) && h >= 0 && h <= 23) return `${zwei(h)}:00`
  return VORSCHLAG_BEGINN
}

/**
 * Ende prüfen: Es darf nicht vor dem Beginn liegen (gleicher Tag).
 * Gibt eine deutsche Meldung zurück oder '' wenn alles passt.
 */
export function pruefeZeitraum(beginn, ende) {
  const a = minuten(beginn)
  const b = minuten(ende)
  if (a < 0 || b < 0) return ''
  if (b < a) return 'Das Ende liegt vor dem Beginn.'
  if (b === a) return 'Beginn und Ende sind gleich — der Termin hätte keine Dauer.'
  return ''
}

// ── B2: mehrtägige Termine ─────────────────────────────────────────────────

/** „YYYY-MM-DD“ → Tage seit Mitternacht (UTC-Mittag, damit keine Zeitzone kippt). */
function tage(datum) {
  const m = String(datum || '').match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!m) return null
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 12))
  if (Number.isNaN(d.getTime())) return null
  // Ungültige Kalendertage (31.02.) abweisen — sonst „rollt“ das Datum weiter.
  if (d.getUTCFullYear() !== Number(m[1]) || d.getUTCMonth() !== Number(m[2]) - 1
    || d.getUTCDate() !== Number(m[3])) return null
  return Math.round(d.getTime() / 86400000)
}

/** Liegt `a` nach `b` (beide „YYYY-MM-DD“)? Unlesbares gilt als „nicht danach“. */
export function datumNach(a, b) {
  const ta = tage(a)
  const tb = tage(b)
  if (ta === null || tb === null) return false
  return ta > tb
}

/** Beginndatum verschieben: das Ende wandert mit, wenn es hinterherhinkt. */
export function endeMitBeginn(beginnDatum, endeDatum) {
  const ende = String(endeDatum || '').trim()
  // Ein neues Beginndatum nach dem Ende setzt das Ende auf den Beginn.
  if (datumNach(beginnDatum, ende)) return String(beginnDatum || '')
  return ende
}

/** Tage zwischen zwei „YYYY-MM-DD“ (positiv = bis nach von); null wenn unlesbar. */
export function tageDazwischen(von, bis) {
  const a = tage(von)
  const b = tage(bis)
  if (a === null || b === null) return null
  return b - a
}

/**
 * Deutsche Dauer eines mehrtägigen Termins: „3 Tage (Mo.)
 * B2 — die Vorschau darf den mehrtägigen Zeitraum nicht verschweigen.
 */
export function zeitraumText(vonDatum, bisDatum) {
  const diff = tageDazwischen(vonDatum, bisDatum)
  if (diff === null || diff <= 0) return ''
  return `${diff + 1} Tage (${wochentag(vonDatum).kurz}–${wochentag(bisDatum).kurz})`
}

/**
 * B2: Zeitraum ganzer Termine prüfen — Datum UND Uhrzeit.
 * Ein mehrtägiger Termin ist gültig, auch wenn die Uhrzeit des Endes vor der
 * des Beginns liegt (23.02. 09:00 – 25.02. 08:00). Nur am GLEICHEN Tag muss
 * das Ende nach dem Beginn liegen.
 */
export function pruefeZeitraumMitDatum(beginnDatum, beginnZeit, endeDatum, endeZeit, ganztags = false) {
  const von = String(beginnDatum || '').trim()
  const bis = String(endeDatum || '').trim() || von
  const diff = tageDazwischen(von, bis)
  // Ende VOR dem Beginn: unabhängig von der Uhrzeit ein Fehler.
  if (diff !== null && diff < 0) return 'Das Ende liegt vor dem Beginn.'
  if (ganztags) return ''                    // ganztägig zählt nur das Datum
  if (diff !== null && diff > 0) return ''   // mehrtägig: immer gültig
  return pruefeZeitraum(beginnZeit, endeZeit) // gleicher Tag: wie bisher
}

/**
 * B2: Endzeit vorschlagen, ohne das Enddatum zu zerstören.
 *  - mehrtägig: das Ende bleibt, wo es ist (nur eine leere Endzeit wird gefüllt)
 *  - eintägig: wie bisher eine Stunde nach dem Beginn
 */
export function endeAusBeginnMitDatum(beginnDatum, beginnZeit, endeDatum, endeZeit, ganztags = false) {
  const von = String(beginnDatum || '').trim()
  const bis = String(endeDatum || '').trim()
  const diff = tageDazwischen(von, bis)
  const mehrtaegig = diff !== null && diff > 0
  if (mehrtaegig) {
    // Das Enddatum bleibt unangetastet; nur ein leeres Feld wird gefüllt,
    // damit beim Speichern eine gültige Zeit entsteht.
    if (!ganztags && !String(endeZeit || '').trim() && minuten(beginnZeit) >= 0) {
      return endeAusBeginn(beginnZeit)
    }
    return String(endeZeit || '')
  }
  // R-DES-REST-b B3: eingetragene/geladene Endzeit hat Vorrang (19:30–21:00
  // bleibt beim Ändern des Beginns 21:00) — der Vorschlag gilt nur bei leerem Ende.
  if (String(endeZeit || '').trim()) return String(endeZeit)
  return endeAusBeginn(beginnZeit)
}

/**
 * B2: Die tatsächlich zu SPEICHERNDE Endzeit zum Vorschlag für die Anzeige.
 * Nur wenn noch keine Endzeit eingetragen ist, wird der Vorschlag benutzt —
 * er darf nicht als gespeicherter Wert erscheinen. Die Anzeige entscheidet
 * darüber im Baustein DkDatumZeit (Kennzeichnung „(Vorschlag)“).
 */
export function wirksameEndeZeit(beginnDatum, beginnZeit, endeDatum, endeZeit, ganztags = false) {
  return endeAusBeginnMitDatum(beginnDatum, beginnZeit, endeDatum, endeZeit, ganztags)
}

/** Ist ein Datum ein gültiger Kalendertag? (31.02. fällt durch.) */
export function istDatum(datum) {
  const m = String(datum || '').match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!m) return false
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 12))
  return d.getUTCFullYear() === Number(m[1])
    && d.getUTCMonth() === Number(m[2]) - 1
    && d.getUTCDate() === Number(m[3])
}
