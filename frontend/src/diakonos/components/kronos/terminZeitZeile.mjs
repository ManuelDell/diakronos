/**
 * FIX-7b — Zeitzeile der Termin-Detailansicht.
 *
 * Befund (Abnahme FIX-7 im Browser, 2026-11-05): `KronosEventView.vue` las
 * `event.element_start` / `event.element_end`. Die Felder heissen im
 * Terminobjekt aber `start` / `end` — die vom Server frisch geladene
 * Detailansicht (`get_mein_termin`) zeigte deshalb „Invalid Date Invalid
 * Date – Invalid Date“. Die Termine AUS DEM KALENDER trugen `element_start`
 * nur zufaellig, weil die Kalender-Bibliothek den ganzen Datensatz als
 * `extendedProps` mitreicht.
 *
 * Diese Funktion nimmt BEIDE Formen (Detailantwort und Kalender-Event) und
 * liefert IMMER deutschen Text.
 */

const OPTS_DATUM = { weekday: 'short', day: 'numeric', month: 'short' }
const OPTS_ZEIT = { hour: '2-digit', minute: '2-digit' }

const de = (options) => new Intl.DateTimeFormat('de-DE', options)

/** Wandelt Server-/Kalenderwerte in ein Datum; `null`, wenn unbrauchbar. */
function alsDatum(wert) {
  if (!wert) return null
  if (wert instanceof Date) return Number.isNaN(wert.getTime()) ? null : wert
  const d = new Date(String(wert).trim().replace(' ', 'T'))
  return Number.isNaN(d.getTime()) ? null : d
}

/**
 * Zeitzeile eines Termins („So., 8. Nov. 10:00 – 11:30“).
 *
 * @param {object|null} event — Termin aus `get_mein_termin` (`start`/`end`)
 *   oder aus dem Kalender (`element_start`/`element_end`).
 * @returns {string} Text; `'—'` wenn kein Datum vorliegt.
 */
export function terminZeitZeile(event) {
  if (!event) return '—'
  const start = alsDatum(event.start ?? event.element_start)
  const ende = alsDatum(event.end ?? event.element_end)
  if (!start) return '—'

  if (event.all_day) {
    return de({ ...OPTS_DATUM, year: 'numeric' }).format(start) + ' (Ganztägig)'
  }
  if (!ende) return de(OPTS_DATUM).format(start) + ' ' + de(OPTS_ZEIT).format(start)
  const gleicherTag = start.toDateString() === ende.toDateString()
  if (gleicherTag) {
    return (
      de(OPTS_DATUM).format(start) +
      ' ' +
      de(OPTS_ZEIT).format(start) +
      ' – ' +
      de(OPTS_ZEIT).format(ende)
    )
  }
  return (
    de({ ...OPTS_DATUM, ...OPTS_ZEIT }).format(start) +
    ' – ' +
    de({ ...OPTS_DATUM, ...OPTS_ZEIT }).format(ende)
  )
}
