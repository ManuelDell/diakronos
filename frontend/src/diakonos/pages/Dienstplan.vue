<template>
  <div class="dk-screen dk-screen-enter">
    <div class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">Dienstplan</h1>
      </div>
    </div>

    <div v-if="loading" class="text-[var(--dk-text-muted)]">Lade Dienstplan …</div>

    <div v-else-if="error" class="text-[var(--dk-danger)] bg-[color-mix(in_oklch,var(--dk-danger)_8%,var(--dk-surface))] p-4 rounded-lg mb-4">
      {{ error }}
    </div>

    <div v-else-if="dienste.length === 0" class="text-[var(--dk-text-muted)]">
      Keine Dienste gefunden.
    </div>

    <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <div
        v-for="dienst in dienste"
        :key="dienst.name"
        class="dk-card p-4"
      >
        <div class="text-sm text-[var(--dk-text-muted)] mb-1">{{ formatDate(dienst.anmeldedatum) }}</div>
        <div class="font-semibold text-[var(--dk-text)]">{{ dienst.anmeldungstyp || dienst.element || '–' }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { apiCall } from '../composables/useApi.js'

const loading = ref(true)
const dienste = ref([])
const error = ref(null)

function getWeekRange() {
  const now = new Date()
  const day = now.getDay() // 0 = Sonntag, 1 = Montag, ...
  const diffToMonday = (day + 6) % 7 // Montag = 0 Tage zurück
  const monday = new Date(now)
  monday.setDate(now.getDate() - diffToMonday)
  monday.setHours(0, 0, 0, 0)

  const sunday = new Date(monday)
  sunday.setDate(monday.getDate() + 6)
  sunday.setHours(0, 0, 0, 0)

  const fmt = (d) => d.toISOString().split('T')[0]
  return { start_date: fmt(monday), end_date: fmt(sunday) }
}

async function fetchDienstplan() {
  loading.value = true
  error.value = null
  try {
    const { start_date, end_date } = getWeekRange()
    const result = await apiCall('diakronos.diakonos.api.dienstplan.get_dienstplan', {
      start_date,
      end_date,
    })
    dienste.value = result?.eintraege || []
  } catch (err) {
    error.value = err?.message || 'Fehler beim Laden des Dienstplans'
    console.error('Fehler beim Laden des Dienstplans:', err)
  } finally {
    loading.value = false
  }
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('de-DE', {
    weekday: 'short',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  })
}

onMounted(fetchDienstplan)
</script>
