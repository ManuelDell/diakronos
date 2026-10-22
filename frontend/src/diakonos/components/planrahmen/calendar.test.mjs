import assert from 'node:assert/strict'
import { calendarMonths, isoWeek, weekdayLabel, calendarTime } from './calendar.mjs'
const q4 = calendarMonths('2026-10-01', '2026-12-31')
assert.deepEqual(q4.map(m => m.id), ['2026-10', '2026-11', '2026-12'])
assert.deepEqual(q4.map(m => m.days.length), [31, 30, 31])
assert.equal(q4[0].name, 'Oktober 2026')
assert.equal(q4[0].days[0].date, '2026-10-01')
assert.equal(q4[0].days[0].weekday, 4)
assert.equal(weekdayLabel(q4[0].days[3].weekday), 'So')
assert.equal(weekdayLabel(q4[1].days[0].weekday), 'So')
assert.equal(weekdayLabel(1), 'Mo')
const derived = { terminreihen: [{ id: 'probe', termine: { abgeleitet: { von: 'gottesdienst' } } }] }
assert.equal(calendarTime({ reihe: 'probe', uhrzeit: '10:00' }, derived), '')
assert.equal(calendarTime({ reihe: 'gottesdienst', uhrzeit: '10:00' }, derived), '10:00')
derived.terminreihen[0].termine.uhrzeit = '19:30'
assert.equal(calendarTime({ reihe: 'probe', uhrzeit: '19:30' }, derived), '19:30')
assert.equal(q4[0].days[0].kw, null)
assert.equal(q4[0].days[4].kw, 41)
assert.equal(isoWeek('2021-01-01'), 53)
assert.equal(isoWeek('2024-12-30'), 1)
assert.equal(calendarMonths('2024-02-01', '2024-02-29')[0].days.length, 29)
const partial = calendarMonths('2026-10-05', '2026-10-06')[0].days
assert.equal(partial.length, 31)
assert.deepEqual(partial.filter(d => d.inside).map(d => d.date), ['2026-10-05', '2026-10-06'])
assert.deepEqual(calendarMonths('2026-12-31', '2026-10-01'), [])
assert.deepEqual(calendarMonths('', '2026-10-01'), [])
assert.deepEqual(calendarMonths('2026-02-30', '2026-03-01'), [])
assert.equal(isoWeek('ungueltig'), null)
console.log('Kalender: Prüfungen inklusive Sonntagen und abgeleiteter Uhrzeit bestanden')
