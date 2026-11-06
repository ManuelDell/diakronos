import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const pfade = [
  'stores/dashboardConfig.js', 'pages/Home.vue', 'components/widgets/MiniCalendarWidget.vue',
  'composables/useEventsApi.js', 'composables/useKronosStore.js', 'composables/useWidgetData.js',
  // KronosTopbar.vue: seit UX3d ohne eigenen fetch (Moderations-Zähler entfällt),
  // braucht apiAntwortPruefen daher nicht mehr — Wächter unten prüft, dass es so bleibt.
  'components/kronos/KronosSeriesDialog.vue',
  'components/kronos/KronosCalendar.vue', 'components/kronos/KronosDayEventsDialog.vue',
  'components/kronos/KronosEventCreate.vue', 'components/kronos/KronosEventEdit.vue',
  'composables/usePlanrahmen.js',
]
for (const pfad of pfade) test(`${pfad}: direkte API-Antworten prüfen den Sitzungsablauf`, () => {
  const text = readFileSync(new URL('../src/diakonos/' + pfad, import.meta.url), 'utf8')
  assert.match(text, /apiAntwortPruefen/)
  assert.doesNotMatch(text, /(?:res|response|r)\.json\(/)
})

test('components/kronos/KronosTopbar.vue: kein direkter fetch ohne Sitzungsprüfung', () => {
  const text = readFileSync(new URL('../src/diakonos/components/kronos/KronosTopbar.vue', import.meta.url), 'utf8')
  assert.ok(!/\bfetch\(/.test(text) || /apiAntwortPruefen/.test(text),
    'wer wieder selbst fetcht, muss die Antwort mit apiAntwortPruefen prüfen')
  assert.doesNotMatch(text, /(?:res|response|r)\.json\(/)
})
