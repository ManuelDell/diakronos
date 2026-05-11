<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  show: { type: Boolean, required: true },
  dateStr: { type: String, required: true },
  calendarRef: { type: Object, default: null },
  selectedCalendars: { type: Array, default: () => [] }
})

const emit = defineEmits(['update:show', 'eventClick'])

const dayEvents = ref([])
const loading = ref(false)

function safeColor(c) {
  return c && /^#[0-9a-fA-F]{3,8}$|^var\(/.test(c) ? c : 'var(--primary)'
}

function formatTimeRange(ev) {
  if (ev.allDay) return 'Ganztägig'
  const s = new Date((ev.start || '').replace(' ', 'T'))
  const e = new Date((ev.end || '').replace(' ', 'T'))
  const optsT = { hour: '2-digit', minute: '2-digit' }
  return s.toLocaleTimeString('de-DE', optsT) + ' – ' + e.toLocaleTimeString('de-DE', optsT)
}

async function loadDayEvents() {
  if (!props.show || !props.dateStr) return
  loading.value = true
  try {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
    const res = await fetch('/api/method/diakronos.kronos.api.calendar_get.get_calendar_events', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Frappe-CSRF-Token': csrf
      },
      body: JSON.stringify({
        start_date: props.dateStr,
        end_date: props.dateStr,
        calendar_filter: JSON.stringify(props.selectedCalendars)
      })
    })
    const data = await res.json()
    const events = data?.message || []
    dayEvents.value = events.sort((a, b) => {
      const ta = new Date((a.start || '').replace(' ', 'T')).getTime()
      const tb = new Date((b.end || '').replace(' ', 'T')).getTime()
      return ta - tb
    })
  } catch (e) {
    console.error('loadDayEvents failed', e)
    dayEvents.value = []
  } finally {
    loading.value = false
  }
}

watch(() => props.show, (v) => { if (v) loadDayEvents() })
watch(() => props.dateStr, () => { if (props.show) loadDayEvents() })

function onEventClick(ev) {
  emit('eventClick', ev.extendedProps || ev)
}
</script>

<template>
  <Teleport to="body">
    <div v-if="show" class="diakronos-modal show" @click.self="emit('update:show', false)">
      <div class="diakronos-modal-dialog modal-dialog-centered" style="max-width:480px">
        <div class="diakronos-modal-content">
          <div class="diakronos-modal-header">
            <h5 class="modal-title">{{ dateStr ? new Date(dateStr).toLocaleDateString('de-DE', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) : 'Termine' }}</h5>
            <button class="diakronos-close-btn" @click="emit('update:show', false)">&times;</button>
          </div>
          <div class="diakronos-modal-body">
            <div v-if="loading" class="text-muted">Lade Termine...</div>
            <div v-else-if="!dayEvents.length" class="text-muted">Keine Termine an diesem Tag.</div>
            <div v-else class="day-events-list">
              <div
                v-for="ev in dayEvents"
                :key="ev.id || ev.name"
                class="day-event-item"
                :style="{ borderLeft: '4px solid ' + safeColor(ev.backgroundColor || ev.extendedProps?.element_color) }"
                @click="onEventClick(ev)"
              >
                <div class="day-event-time">{{ formatTimeRange(ev) }}</div>
                <div class="day-event-name">{{ ev.title || 'Termin' }}</div>
                <div class="day-event-calendar text-muted">{{ ev.extendedProps?.element_calendar || '' }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
