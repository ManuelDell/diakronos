// Datumsmathematik ausschließlich in UTC: kein DST-/Zeitzonenversatz am Aushang.
const dayMs = 86400000
export function weekdayLabel(weekday) {
  return ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'][weekday - 1] || ''
}
export function calendarTime(termin, definition) {
  const reihe = definition?.terminreihen?.find(r => r.id === termin.reihe)
  if (reihe?.termine?.abgeleitet && !reihe.termine.uhrzeit) return ''
  return termin.uhrzeit?.slice(0, 5) || ''
}
function parseDate(iso) {
  if (typeof iso !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(iso)) return null
  const date = new Date(iso + 'T00:00:00Z')
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === iso ? date : null
}
export function isoWeek(iso) {
  const date = parseDate(iso)
  if (!date) return null
  date.setUTCDate(date.getUTCDate() + 4 - (date.getUTCDay() || 7))
  const first = new Date(Date.UTC(date.getUTCFullYear(), 0, 1))
  return Math.ceil(((date - first) / dayMs + 1) / 7)
}
export function calendarMonths(von, bis) {
  const start = parseDate(von), end = parseDate(bis)
  if (!start || !end || start > end) return []
  const months = []
  const cursor = new Date(start)
  cursor.setUTCDate(1)
  while (cursor <= end) {
    const month = cursor.getUTCMonth()
    const days = []
    const id = cursor.toISOString().slice(0, 7)
    const name = cursor.toLocaleDateString('de-DE', { month: 'long', year: 'numeric', timeZone: 'UTC' })
    while (cursor.getUTCMonth() === month) {
      const date = cursor.toISOString().slice(0, 10)
      const weekday = cursor.getUTCDay() || 7
      days.push({ date, day: cursor.getUTCDate(), weekday, kw: weekday === 1 ? isoWeek(date) : null, inside: date >= von && date <= bis })
      cursor.setUTCDate(cursor.getUTCDate() + 1)
    }
    months.push({ id, name, days })
  }
  return months
}
