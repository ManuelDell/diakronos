<template>
  <div class="dk-screen dk-screen-enter">
    <div class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">Dienstplan</h1>
        <p class="dk-screen-sub">Deine nächsten Vorbereitungen und Einsätze</p>
      </div>
    </div>

    <div v-if="loading" class="dp-state text-[var(--dk-text-muted)]">Lade Dienstplan …</div>
    <div v-else-if="error" class="dp-state dp-error">
      {{ error }}
      <button class="dk-btn dk-btn-secondary dk-btn-sm" @click="fetchData">Nochmal</button>
    </div>

    <template v-else>
      <div class="dp-grid">
        <!-- Nächste Vorbereitung -->
        <section class="dk-card dp-col">
          <h2 class="dp-col-title">Nächste Vorbereitung</h2>
          <template v-if="nextVorbereitung">
            <div class="dp-entry-head">
              <div>
                <div class="dp-entry-name">{{ nextVorbereitung.element_name || '–' }}</div>
                <div class="dp-entry-meta">{{ formatDateTime(nextVorbereitung.element_start) }}</div>
              </div>
              <div class="dp-entry-side">
                <span v-if="nextVorbereitung.dienstrolle_name" class="dp-rolle">{{ nextVorbereitung.dienstrolle_name }}</span>
                <span class="dk-badge dk-badge-warning">Vorbereitung</span>
              </div>
            </div>
            <div v-if="nextVorbereitung.ablaufplan?.positionen?.length" class="dp-ablauf">
              <div class="dp-ablauf-title">Ablauf</div>
              <ol class="dp-positions">
                <li
                  v-for="pos in nextVorbereitung.ablaufplan.positionen"
                  :key="pos.reihenfolge + '-' + pos.bezeichnung"
                  class="dp-pos"
                  :class="{ 'dp-own': pos.verantwortet }"
                >
                  <span class="dp-pos-idx">{{ pos.reihenfolge }}</span>
                  <span class="dp-pos-body">
                    <span class="dp-pos-name">{{ pos.bezeichnung || '–' }}</span>
                    <span v-if="pos.funktion || pos.gruppe || pos.detail || pos.dauer_minuten" class="dp-pos-detail">
                      <template v-if="pos.funktion">{{ pos.funktion }}</template>
                      <template v-if="pos.gruppe"> · {{ pos.gruppe }}</template>
                      <template v-if="pos.detail"> · {{ pos.detail }}</template>
                      <template v-if="pos.dauer_minuten"> · {{ pos.dauer_minuten }} Min.</template>
                    </span>
                  </span>
                  <span v-if="pos.verantwortet" class="dp-own-badge">Du</span>
                </li>
              </ol>
            </div>
            <div v-else class="dp-no-ablauf">Kein Ablaufplan hinterlegt.</div>
          </template>
          <div v-else class="dp-empty-inline">Keine anstehende Vorbereitung.</div>
        </section>

        <!-- Nächster Einsatz -->
        <section class="dk-card dp-col">
          <h2 class="dp-col-title">Nächster Einsatz</h2>
          <template v-if="nextEinsatz">
            <div class="dp-entry-head">
              <div>
                <div class="dp-entry-name">{{ nextEinsatz.element_name || '–' }}</div>
                <div class="dp-entry-meta">{{ formatDateTime(nextEinsatz.element_start) }}</div>
              </div>
              <div class="dp-entry-side">
                <span v-if="nextEinsatz.dienstrolle_name" class="dp-rolle">{{ nextEinsatz.dienstrolle_name }}</span>
                <span class="dk-badge dk-badge-info">Einsatz</span>
              </div>
            </div>
            <div v-if="nextEinsatz.ablaufplan?.positionen?.length" class="dp-ablauf">
              <div class="dp-ablauf-title">Ablauf</div>
              <ol class="dp-positions">
                <li
                  v-for="pos in nextEinsatz.ablaufplan.positionen"
                  :key="pos.reihenfolge + '-' + pos.bezeichnung"
                  class="dp-pos"
                  :class="{ 'dp-own': pos.verantwortet }"
                >
                  <span class="dp-pos-idx">{{ pos.reihenfolge }}</span>
                  <span class="dp-pos-body">
                    <span class="dp-pos-name">{{ pos.bezeichnung || '–' }}</span>
                    <span v-if="pos.funktion || pos.gruppe || pos.detail || pos.dauer_minuten" class="dp-pos-detail">
                      <template v-if="pos.funktion">{{ pos.funktion }}</template>
                      <template v-if="pos.gruppe"> · {{ pos.gruppe }}</template>
                      <template v-if="pos.detail"> · {{ pos.detail }}</template>
                      <template v-if="pos.dauer_minuten"> · {{ pos.dauer_minuten }} Min.</template>
                    </span>
                  </span>
                  <span v-if="pos.verantwortet" class="dp-own-badge">Du</span>
                </li>
              </ol>
            </div>
            <div v-else class="dp-no-ablauf">Kein Ablaufplan hinterlegt.</div>
          </template>
          <div v-else class="dp-empty-inline">Kein anstehender Einsatz.</div>
        </section>
      </div>

      <!-- Weitere Termine -->
      <section v-if="weitereTermine.length" class="dk-card dp-further">
        <h2 class="dp-col-title">Weitere Termine</h2>
        <ul class="dp-further-list">
          <li v-for="(t, i) in weitereTermine" :key="t.element + '-' + (t.mitglied || '') + '-' + i" class="dp-further-row">
            <div class="dp-further-main">
              <div class="dp-entry-name">{{ t.element_name || '–' }}</div>
              <div class="dp-entry-meta">{{ formatDateTime(t.element_start) }}</div>
            </div>
            <div class="dp-entry-side">
              <span v-if="t.dienstrolle_name" class="dp-rolle">{{ t.dienstrolle_name }}</span>
              <span class="dk-badge" :class="pillClass(t.terminart)">
                {{ t.terminart === 'Vorbereitung' ? 'Vorbereitung' : 'Einsatz' }}
              </span>
            </div>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiCall } from '../composables/useApi.js'

const loading = ref(true)
const error = ref(null)
const data = ref(null)

const nextVorbereitung = computed(() => (data.value?.vorbereitung || [])[0] || null)
const nextEinsatz = computed(() => (data.value?.einsatz || [])[0] || null)
const weitereTermine = computed(() => {
  const vor = data.value?.vorbereitung || []
  const ein = data.value?.einsatz || []
  const rest = [...vor.slice(1), ...ein.slice(1)]
  return rest.sort((a, b) => (a.element_start || '').localeCompare(b.element_start || ''))
})

function pillClass(t) {
  return t === 'Vorbereitung' ? 'dk-badge-warning' : 'dk-badge-info'
}

function formatDateTime(s) {
  if (!s) return ''
  const d = new Date(String(s).replace(' ', 'T'))
  if (isNaN(d)) return s
  return (
    d.toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' }) +
    ', ' + d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })
  )
}

async function fetchData() {
  loading.value = true
  error.value = null
  try {
    const result = await apiCall('diakronos.diakonos.api.dienstplan.get_meine_dienste', {})
    data.value = result || { vorbereitung: [], einsatz: [] }
  } catch (err) {
    error.value = err?.message || 'Fehler beim Laden der Dienste'
    console.error('Dienstplan — Fehler:', err)
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<style scoped>
.dp-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  align-items: start;
}
@media (max-width: 760px) {
  .dp-grid { grid-template-columns: 1fr; }
}
.dp-col { padding: 18px 20px; }
.dp-col-title { font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--dk-text-muted); margin: 0 0 12px; }
.dp-state { display: flex; align-items: center; gap: 10px; }
.dp-error { color: var(--dk-danger); }

.dp-entry-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.dp-entry-name { font-size: 1rem; font-weight: 600; color: var(--dk-text); line-height: 1.3; }
.dp-entry-meta { font-size: 0.78rem; color: var(--dk-text-muted); margin-top: 3px; }
.dp-entry-side { display: inline-flex; align-items: center; gap: 8px; flex-shrink: 0; }
.dp-rolle { font-size: 0.72rem; color: var(--dk-text-muted); max-width: 110px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.dp-ablauf { border-top: 1px solid var(--dk-divider); margin-top: 10px; padding-top: 12px; }
.dp-ablauf-title { font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dk-text-subtle); margin-bottom: 8px; }
.dp-positions { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.dp-pos {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 10px;
  border-radius: 8px;
  border: 1px solid var(--dk-border);
  background: var(--dk-surface);
}
.dp-pos.dp-own {
  background: color-mix(in oklch, var(--dk-brand-400) 10%, var(--dk-surface));
  border-color: color-mix(in oklch, var(--dk-brand-400) 35%, var(--dk-surface));
}
.dp-pos-idx {
  width: 22px; height: 22px;
  flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 50%;
  background: var(--dk-surface-2);
  color: var(--dk-text-muted);
  font-size: 0.7rem; font-weight: 600;
}
.dp-pos.dp-own .dp-pos-idx { background: var(--dk-navy-400); color: var(--primary-ink); }
.dp-pos-body { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.dp-pos-name { font-size: 0.84rem; font-weight: 500; color: var(--dk-text); }
.dp-pos.dp-own .dp-pos-name { color: var(--dk-brand-700); font-weight: 600; }
.dp-pos-detail { font-size: 0.72rem; color: var(--dk-text-muted); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dp-own-badge {
  flex-shrink: 0;
  font-size: var(--fs-xs); font-weight: 600;
  padding: 2px 8px; border-radius: var(--badge-r);
  background: var(--primary); color: var(--primary-ink);
}
.dp-no-ablauf { font-size: 0.78rem; color: var(--dk-text-subtle); margin-top: 4px; }
.dp-empty-inline { font-size: 0.84rem; color: var(--dk-text-muted); padding: 6px 0; }

.dp-further { padding: 14px 20px; margin-top: 4px; }
.dp-further-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.dp-further-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--dk-divider);
}
.dp-further-row:last-child { border-bottom: none; }
.dp-further-main { flex: 1; min-width: 0; }
</style>
