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
 *  - Vorschlag für neue Termine: nächste volle Stunde, Dauer eine Stunde
 *    (DEV-5; vorher fest 19:00).
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
 * Beginn für einen neuen Termin (DEV-5): die NÄCHSTE volle Stunde der
 * Browserzeit, aufgerundet (14:20 → 15:00, 14:00 → 14:00, 23:30 → 00:00).
 * Wurde im Kalender eine Stunde oder ein Zeitfenster angeklickt, gilt
 * stattdessen diese Uhrzeit (`geklickteStunde`, z. B. 9 oder „19:30“).
 *
 * `jetzt` ist nur für den Test da; ohne Angabe gilt die aktuelle Zeit.
 */
export function vorschlagBeginn(geklickteStunde = null, jetzt = new Date()) {
  // `Number(null)` waere 0 — ein fehlender Klick darf nicht Mitternacht ergeben.
  const klick = geklickteStunde instanceof Date ? null : geklickteStunde
  // Der Test darf „jetzt“ auch als ersten Wert übergeben.
  const zeitpunkt = geklickteStunde instanceof Date ? geklickteStunde : jetzt
  if (klick !== null && klick !== undefined && klick !== '') {
    const roh = String(klick).trim()
    // „19:30“ (Slot aus Woche/Tag) zählt unverändert.
    const mitMinuten = roh.match(/^(\d{1,2}):(\d{2})$/)
    if (mitMinuten) {
      const h = Number(mitMinuten[1])
      const mi = Number(mitMinuten[2])
      if (h >= 0 && h <= 23 && mi >= 0 && mi <= 59) return `${zwei(h)}:${zwei(mi)}`
    }
    const h = Number(roh)
    // Auch eine unbrauchbare Klickangabe fällt auf die aktuelle Stunde zurück
    // (vorher war es die feste 19:00).
    if (Number.isInteger(h) && h >= 0 && h <= 23) return `${zwei(h)}:00`
  }
  return naechsteVolleStunde(zeitpunkt)
}

/** „Jetzt“ → nächste volle Stunde als „HH:MM“ (aufgerundet, 23:30 → 00:00). */
function naechsteVolleStunde(jetzt) {
  const d = jetzt instanceof Date ? jetzt : new Date(jetzt)
  if (Number.isNaN(d.getTime())) return VORSCHLAG_BEGINN
  const stunde = d.getHours() + (d.getMinutes() > 0 ? 1 : 0)
  return `${zwei(stunde % 24)}:00`
}

/** „YYYY-MM-DD“ um `anzahl` Tage verschieben (unlesbares bleibt leer). */
export function datumPlusTage(datum, anzahl = 1) {
  const m = String(datum || '').match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!m) return ''
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]) + Number(anzahl), 12))
  if (Number.isNaN(d.getTime())) return ''
  return `${d.getUTCFullYear()}-${zwei(d.getUTCMonth() + 1)}-${zwei(d.getUTCDate())}`
}

/**
 * Vollständiger Vorschlag für einen NEUEN Termin (DEV-5):
 *  - `datum`      der angeklickte Tag, sonst der heutige Tag
 *  - `beginn`     die angeklickte Slot-Zeit, sonst die nächste volle Stunde
 *  - `ende`/`endeDatum`  eine Stunde später (über Mitternacht mit Tageswechsel)
 *
 * Damit legt der Dialog den Termin auch dann richtig an, wenn der Vorschlag
 * über Mitternacht geht (23:30 → Tag des Klicks 00:00–01:00 des Folgetags).
 */
export function vorschlagZeitraum(jetzt = new Date(), datum = '', slotZeit = '') {
  const d = jetzt instanceof Date ? jetzt : new Date(jetzt)
  const gueltig = !Number.isNaN(d.getTime())
  const tag = istDatum(datum)
    ? String(datum)
    : (gueltig ? `${d.getFullYear()}-${zwei(d.getMonth() + 1)}-${zwei(d.getDate())}` : '')
  const beginn = vorschlagBeginn(slotZeit || null, gueltig ? d : new Date())
  // Rutscht der Beginn über Mitternacht (23:30 → 00:00), ist das der Folgetag.
  const ueberMitternacht = gueltig && !slotZeit && d.getMinutes() > 0 && d.getHours() === 23
  const datumBeginn = ueberMitternacht ? datumPlusTage(tag, 1) : tag
  // Ende = Beginn + 1 h; ab 23:00 auf dem Folgetag.
  const beginnMinuten = minuten(beginn)
  const endeGesamt = beginnMinuten < 0 ? -1 : beginnMinuten + VORSCHLAG_DAUER_MINUTEN
  const endeUeberMitternacht = endeGesamt >= 24 * 60
  const ende = endeGesamt < 0
    ? ''
    : `${zwei(Math.floor((endeGesamt % (24 * 60)) / 60))}:${zwei(endeGesamt % 60)}`
  return {
    datum: datumBeginn,
    beginn,
    ende,
    endeDatum: endeUeberMitternacht ? datumPlusTage(datumBeginn, 1) : datumBeginn,
  }
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

/**
 * ICAL-1: Terminende für den KALENDER (event-calendar/FullCalendar) berechnen.
 *
 * Die Anzeige-Bibliothek zählt bei ganztägigen Terminen das Ende
 * AUSSCHLIESSEND (FullCalendar-Doku: „end of 2018-09-03 → der Termin reicht
 * bis 2018-09-02“; RFC 5545, gleiche Regel wie iCalendar). Diakronos speichert
 * das Ende dagegen EINSCHLIESSLICH — ein als „7.–8.“ eingetragener Termin lag
 * im Monatsraster deshalb NUR am 7., der zweite Tag fehlte.
 *
 * Deshalb hier genau EIN Tag dazu (ganztägig). Termine MIT Uhrzeit bleiben
 * unverändert: dort ist das Ende eine echte Uhrzeit, kein Datumswechsel.
 *
 * Fehlt das Ende, gilt der Beginn (eintägig) → Beginn + 1 Tag.
 * Rückgabe: `null`, wenn sich nichts ändern soll (kein Ende oder mit Uhrzeit).
 */
export function endeFuerKalender(ende, allDay) {
  if (!allDay) return null
  const zerlegt = zerlegeDatumZeit(ende)
  if (!zerlegt.datum) {
    return null   // ohne Ende bleibt „kein Ende“ — die Bibliothek nimmt den Beginn
  }
  const d = new Date(`${zerlegt.datum}T12:00:00Z`)
  if (Number.isNaN(d.getTime())) return null
  d.setUTCDate(d.getUTCDate() + 1)
  const plusEins = d.toISOString().slice(0, 10)
  // Ein vorhandenes Ende behält seine Zeit-Schreibweise (meist „00:00:00“).
  const uhr = String(ende || '').trim().slice(10)
  return uhr ? plusEins + uhr : plusEins
}

/**
 * ICAL-1b: die RÜCK-Richtung von `endeFuerKalender` — das angezeigte
 * Kalender-Ende in das Diakronos-Ende (einschließlich) zurückrechnen.
 *
 * Der Kalender liefert das Ende ganztägiger Termine AUSSCHLIESSEND; würde man
 * es unverändert speichern, wüchse der Termin bei jedem Ziehen oder Ändern um
 * einen Tag (Befund ICAL-1b). Deshalb hier genau EIN Tag zurück — aber nie vor
 * den Beginn: ein eintägiger Termin (angezeigtes Ende = Beginn + 1) landet
 * wieder auf dem Beginn.
 *
 * Rückgabe: derselbe Wert in derselben Schreibweise, wenn nichts umzurechnen
 * ist (Termin mit Uhrzeit, ohne Ende, unlesbares Ende).
 */
export function endeAusKalender(ende, allDay, beginn = null) {
  if (!allDay) return ende
  const zerlegt = zerlegeDatumZeit(ende)
  if (!zerlegt.datum) return ende
  const d = new Date(`${zerlegt.datum}T12:00:00Z`)
  if (Number.isNaN(d.getTime())) return ende
  d.setUTCDate(d.getUTCDate() - 1)
  let minusEins = d.toISOString().slice(0, 10)
  // Nie vor dem Beginn: liegt das gerechnete Ende vor dem Beginn (z. B. weil
  // das Ende schon einschließlich kam), gilt der Beginn (eintägig).
  const beginnDatum = zerlegeDatumZeit(beginn).datum
  if (beginnDatum && datumNach(beginnDatum, minusEins)) minusEins = beginnDatum
  const uhr = String(ende || '').trim().slice(10)
  return uhr ? minusEins + uhr : minusEins
}

/** Date → „YYYY-MM-DD HH:MM:SS“ in BROWSERzeit (Serverformat, wie bisher). */
function alsServerZeit(wert) {
  if (!(wert instanceof Date)) return String(wert ?? '')
  const pad = (n) => String(n).padStart(2, '0')
  return `${wert.getFullYear()}-${pad(wert.getMonth() + 1)}-${pad(wert.getDate())} ` +
         `${pad(wert.getHours())}:${pad(wert.getMinutes())}:${pad(wert.getSeconds())}`
}

/**
 * ICAL-1b: Ein Termin-Objekt des Kalenders (event-calendar/FullCalendar) → die
 * Werte, die der Server erwartet (`save_event`). Das ganztägige Ende wird von
 * der Anzeige-Schreibweise (ausschließend) auf die Speicher-Schreibweise
 * (einschließend) zurückgerechnet; sonst verlängerte jedes Ziehen/Ändern den
 * Termin um einen Tag (Befund ICAL-1b).
 *
 * Liegt hier (und nicht in useEventsApi.js), damit der Speicherweg ohne
 * Vue/DOM im Node-Test prüfbar ist.
 */
export function speicherWerte(event, seriesAbloesen = false) {
  const roh = event || {}
  const beginn = alsServerZeit(roh.start)
  const endeRoh = roh.end === null || roh.end === undefined || roh.end === ''
    ? beginn
    : alsServerZeit(roh.end)
  const allDay = Boolean(roh.allDay)
  const ende = allDay ? endeAusKalender(endeRoh, true, beginn) : endeRoh
  const props = roh.extendedProps || {}
  return {
    beginn,
    ende: ende || beginn,
    allDay,
    props,
    seriesId: seriesAbloesen ? '' : (props.series_id || ''),
  }
}
