<template>
  <div class="dk-screen dk-screen-enter">
    <div class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">Anmeldungen</h1>
      </div>
    </div>

    <div v-if="loading" class="text-[var(--dk-text-muted)]">Lade Anmeldungen …</div>

    <div v-else-if="error" class="text-[var(--dk-danger)] bg-[color-mix(in_oklch,var(--dk-danger)_8%,var(--dk-surface))] p-4 rounded-lg mb-4">
      {{ error }}
    </div>

    <div v-else-if="anmeldungen.length === 0" class="text-[var(--dk-text-muted)]">
      Keine Anmeldungen gefunden.
    </div>

    <div v-else class="overflow-x-auto dk-card">
      <table class="dk-table">
        <thead>
          <tr>
            <th>Datum</th>
            <th>Bereich</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="a in anmeldungen"
            :key="a.name"
          >
            <td class="whitespace-nowrap">{{ formatDate(a.anmeldedatum) }}</td>
            <td>{{ a.anmeldungstyp || a.element || '–' }}</td>
            <td>
              <span :class="statusBadgeClass(a.status)">
                {{ a.status }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { apiCall } from '../composables/useApi.js'

const loading = ref(true)
const anmeldungen = ref([])
const error = ref(null)

async function fetchAnmeldungen() {
  loading.value = true
  error.value = null
  try {
    const result = await apiCall('diakronos.diakonos.api.dienstplan.get_meine_dienste') || {}
    anmeldungen.value = result.eintraege || []
  } catch (err) {
    error.value = err?.message || 'Fehler beim Laden der Anmeldungen'
    console.error('Fehler beim Laden der Anmeldungen:', err)
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

function statusBadgeClass(status) {
  const map = {
    'Bestätigt': 'dk-badge dk-badge-success',
    'Ausstehend': 'dk-badge dk-badge-warning',
    'Abgelehnt': 'dk-badge dk-badge-danger'
  }
  return map[status] || 'dk-badge'
}

onMounted(fetchAnmeldungen)
</script>
