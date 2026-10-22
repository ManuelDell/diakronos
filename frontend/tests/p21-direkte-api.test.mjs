import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const pfade = [
  'stores/dashboardConfig.js', 'pages/Home.vue', 'components/widgets/MiniCalendarWidget.vue',
  'composables/useEventsApi.js', 'composables/useKronosStore.js', 'composables/useWidgetData.js',
  'components/kronos/KronosSeriesDialog.vue', 'components/kronos/KronosTopbar.vue',
  'components/kronos/KronosCalendar.vue', 'components/kronos/KronosDayEventsDialog.vue',
  'components/kronos/KronosEventCreate.vue', 'components/kronos/KronosEventEdit.vue',
  'composables/usePlanrahmen.js',
]
for (const pfad of pfade) test(`${pfad}: direkte API-Antworten prüfen den Sitzungsablauf`, () => {
  const text = readFileSync(new URL('../src/diakonos/' + pfad, import.meta.url), 'utf8')
  assert.match(text, /apiAntwortPruefen/)
  assert.doesNotMatch(text, /(?:res|response|r)\.json\(/)
})
