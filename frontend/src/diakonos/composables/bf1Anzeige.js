/**
 * BF1 — kleine, reine Anzeige-Helfer (testbar ohne Vue/DOM).
 *
 * Sie liegen extra hier, damit die Logik aus MitgliedAuswahl.vue und dem
 * Dashboard-Widget „Zu moderierende Termine“ per node:test geprueft werden
 * kann, ohne einen Browser zu brauchen.
 */

/**
 * Normalisiert Text fuer einen Suchevergleich: Gross-/Kleinschreibung egal,
 * Umlaute und ß aufgeloest (BF1-J). „Müller“ == „mueller“ == „MÜLLER“.
 */
export function suchNormal(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/ß/g, 'ss')
    .replace(/ä/g, 'ae')
    .replace(/ö/g, 'oe')
    .replace(/ü/g, 'ue')
    .trim()
}

/** Passt `name`/`email` eines Mitglieds auf den Suchbegriff (BF1-E/J). */
export function passtZurSuche(mitglied, suche) {
  const t = suchNormal(suche)
  if (!t) return true
  return suchNormal(mitglied?.name).includes(t) || suchNormal(mitglied?.email).includes(t)
}

/**
 * Formatiert den Zeit-Bereich eines Termins fuer die Dashboard-Kachel (BF1-G):
 * ganztägig wird als solches benannt, sonst „Wochentag TT.MM. · HH:MM Uhr“.
 * Mehrtägige Termine nennen den Tagesbereich (K10).
 */
export function terminZeitText(start, ende, allDay = false) {
  if (!start) return 'Zeit unbekannt'
  const s = new Date(String(start).replace(' ', 'T'))
  if (isNaN(s.getTime())) return String(start)
  const tag = (d) => d.toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit' })
  const e = ende ? new Date(String(ende).replace(' ', 'T')) : null
  const eGueltig = e && !isNaN(e.getTime())
  // K10: Das „ganztägig“-Kennzeichen kommt vom Server (`all_day`), nicht aus
  // einer Uhrzeit-Vermutung. Frueher galt jeder Termin um 00:00 als ganztägig
  // (auch ein echter Mitternachtstermin) und umgekehrt galt ein echtes
  // Ganztages-Element mit abweichender Endzeit als Uhrzeit-Termin.
  const ganztaegig = allDay === true
    || (s.getHours() === 0 && s.getMinutes() === 0
      && (!eGueltig || (e.getHours() === 0 && e.getMinutes() === 0)))
  // K10: Mehrtägig (Ende an einem anderen Kalendertag) -> Datumsbereich nennen.
  const mehrtagig = eGueltig
    && (e.getFullYear() !== s.getFullYear() || e.getMonth() !== s.getMonth() || e.getDate() !== s.getDate())
  if (ganztaegig) {
    return mehrtagig ? `${tag(s)} – ${tag(e)} · ganztägig` : `${tag(s)} · ganztägig`
  }
  const zeit = s.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })
  if (mehrtagig) return `${tag(s)} ${zeit} – ${tag(e)} · ${e.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })} Uhr`
  return `${tag(s)} · ${zeit} Uhr`
}

/**
 * Baut aus einem Roh-Termin der Moderation ein anzeigbares Element — ohne
 * interne ID (`name`). Titel, Zeit, Ort/Kalender (BF1-G).
 */
export function terminAnzeige(roh) {
  return {
    schluessel: roh?.name || `${roh?.element_name || ''}|${roh?.element_start || ''}`,
    titel: roh?.element_name || roh?.titel || 'Termin',
    zeit: terminZeitText(roh?.element_start, roh?.element_end, roh?.all_day === true),
    ort: roh?.ressource || roh?.element_calendar || '',
    calendar: roh?.element_calendar || '',
  }
}
