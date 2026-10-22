<template>
  <BaseWidgetCard label="Mini-Kalender" gridSize="medium" :loading="false" :error="null" :isEmpty="false" :isEditing @refresh="loadEvents" @hide="$emit('hide')" @collapse-change="$emit('collapse-change', $event)">
    <KronosMiniCalendar
      :currentMonth="currentMonth"
      :eventDays="eventDays"
      @monthChange="onMonthChange"
      @dateClick="goToCalendar"
    />
  </BaseWidgetCard>
</template>

<script setup>
import { apiAntwortPruefen } from '../../composables/useApi.js'
import { ref, onMounted } from 'vue'
import BaseWidgetCard from './BaseWidgetCard.vue'
import KronosMiniCalendar from '../kronos/KronosMiniCalendar.vue'
import { useImpersonation } from '../../composables/useImpersonation.js'

const props = defineProps({ isEditing: Boolean, refreshInterval: { type: Number, default: 0 } })
const emit = defineEmits(['hide', 'collapse-change'])

const now = new Date()
const currentMonth = ref(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)
const eventDays = ref([])

async function loadEvents() {
  const [y, m] = currentMonth.value.split('-').map(Number)
  try {
    const imp = useImpersonation()
    const csrf = window.__DIakonosBOOT?.csrf_token || ''
    const body = { year: y, month: m }
    if (imp.isActive.value) body.__impersonated_as = imp.mitglied.value
    const res = await fetch('/api/method/diakronos.diakonos.api.dashboard.get_events_for_month', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
      body: JSON.stringify(body),
    })
    const json = await apiAntwortPruefen(res)
    eventDays.value = json.message?.event_days || []
  } catch { eventDays.value = [] }
}

function onMonthChange(month) {
  currentMonth.value = month
  loadEvents()
}

function goToCalendar(dateStr) {
  window.location.hash = '#/kalender'
}

onMounted(loadEvents)
</script>
