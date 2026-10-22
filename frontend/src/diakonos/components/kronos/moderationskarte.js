/**
 * UXK-R11 — Datums-/Zeitdarstellung der Moderationskarte.
 *
 * Ausgelagert aus `ModerationCard.vue`, damit die Formatierung als reine
 * Funktion geprueft werden kann (Verhaltenstest statt Quelltext-Waechter).
 *
 * Erwartete Darstellung:
 *   - Termin am selben Tag:  „Do., 15.10. · 14:00 – 15:00“
 *   - Termin ueber Mitternacht: „Do., 15.10. · 22:00 – Fr., 16.10. · 01:00“
 *   - Ganztags:              „Do., 15.10.“
 */

function datumUhrzeit(str, ganztags) {
  if (!str) return ''
  const d = new Date(str)
  if (isNaN(d)) return str
  const opts = { weekday: 'short', day: '2-digit', month: '2-digit' }
  if (ganztags) return d.toLocaleDateString('de-DE', opts)
  return d.toLocaleDateString('de-DE', opts) + ' · ' +
         d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })
}

/** Nur die Uhrzeit (`14:00`). */
function uhrzeit(str) {
  const d = new Date(str)
  if (isNaN(d)) return ''
  return d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })
}

/**
 * Textzeile der Karte. `item` folgt der Form der Moderationsdaten
 * (`start`, `end`, `all_day`, `type: 'serie'`, `first_start`, `last_start`).
 */
export function terminZeitText(item) {
  if (!item) return ''
  if (item.type === 'serie') {
    const gleicherTag = item.first_start === item.last_start
    if (gleicherTag) return datumUhrzeit(item.first_start, item.all_day)
    return `${datumUhrzeit(item.first_start, item.all_day)} – ${datumUhrzeit(item.last_start, item.all_day)}`
  }
  // UXK-R11: Das Ende war als DATUM formatiert („14:00 – 15.10.“). Erwartet ist
  // die Endzeit als Uhrzeit; das Datum nur an einem anderen Tag.
  let endTeil = ''
  if (item.end && !item.all_day) {
    const gleicherTag = new Date(item.end).toDateString() === new Date(item.start).toDateString()
    endTeil = gleicherTag
      ? ' – ' + uhrzeit(item.end)
      : ' – ' + datumUhrzeit(item.end, false)
  }
  return datumUhrzeit(item.start, item.all_day) + endTeil
}
