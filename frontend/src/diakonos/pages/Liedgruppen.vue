<template>
  <div class="dk-screen dk-screen-enter">
    <!-- Header -->
    <div class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">Liedgruppen</h1>
        <p class="dk-screen-sub">{{ filtered.length }} von {{ gruppen.length }} Gruppen</p>
      </div>
      <!-- UXM-R9: Liedgruppen anlegen (nur mit Schreibrecht; der Server entscheidet). -->
      <DkButton v-if="darfSchreiben" variant="primary" @click="neueGruppe">
        <svg slot="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        Neue Liedgruppe
      </DkButton>
    </div>

    <!-- Typ-Filterchips (DES-01: gemeinsamer Baustein, abwählbar) -->
    <div class="dk-toolbar">
      <DkFilterChips
        :chips="typChips"
        :model-value="activeTyp"
        aria-label="Liedgruppen nach Art filtern"
        @waehlen="activeTyp = $event"
      />
    </div>

    <!-- UXM-R9: Dialog zum Anlegen/Bearbeiten -->
    <LiedgruppeBearbeiten v-model="editorOffen" :detail="editorDetail" @gespeichert="nachSpeichern" />

    <!-- Loading -->
    <div v-if="loading && gruppen.length === 0" class="ld-state">
      <div class="ld-spinner"></div>
      <span>Lade Liedgruppen…</span>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="ld-error">
      {{ error }}
      <button class="dk-btn dk-btn-secondary dk-btn-sm" @click="load">Nochmal</button>
    </div>

    <!-- Grid -->
    <template v-else>
      <div v-if="filtered.length === 0" class="ld-empty">
        <p class="lg-leer-titel">{{ istAlle(activeTyp) ? 'Noch keine Liedgruppe' : 'Keine Liedgruppe dieser Art' }}</p>
        <p class="lg-leer-text">
          {{ istAlle(activeTyp)
            ? 'Sobald eine Liedgruppe angelegt ist, erscheint sie hier.'
            : 'Wähle „Alle“, um alle Liedgruppen zu sehen.' }}
        </p>
      </div>
      <div v-else class="lg-grid">
        <a
          v-for="g in filtered"
          :key="g.name"
          class="lg-card"
          :href="'#/liedgruppen/' + encodeURIComponent(g.name)"
        >
          <div class="lg-card-head">
            <span class="dk-badge" :class="typPill(g.typ)">{{ g.typ || 'Sonstiges' }}</span>
            <span v-if="g.status === 'Archiviert'" class="dk-badge dk-badge-warning">Archiviert</span>
          </div>
          <div class="lg-card-name">{{ g.gruppenname || g.name }}</div>
          <div class="lg-card-meta">
            <template v-if="g.komponist"><div>🎼 {{ g.komponist }}</div></template>
            <template v-if="g.textautor"><div>✍️ {{ g.textautor }}</div></template>
            <template v-if="g.dauer_minuten"><div>⏱ {{ g.dauer_minuten }} Min.</div></template>
            <template v-if="g.gruppe"><div class="lg-card-gruppe">{{ g.gruppe }}</div></template>
          </div>
        </a>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiCall } from '../composables/useApi.js'
import { navigate } from '../router.js'
import DkButton from '../components/ui/DkButton.vue'
import DkFilterChips from '../components/ui/DkFilterChips.vue'
import { chipsAus, filtereNachChip, istAlle } from '../composables/filterChips.mjs'
import LiedgruppeBearbeiten from '../components/lieder/LiedgruppeBearbeiten.vue'

const gruppen = ref([])
const loading = ref(true)
const error = ref(null)
// Ruhezustand ist der „Alle“-Wert des Bausteins.
const activeTyp = ref('alle')

/* UXM-R9: Schreibrecht kommt vom Server (dieselbe Regel wie save_liedgruppe). */
const darfSchreiben = ref(false)
const editorOffen = ref(false)
const editorDetail = ref(null)

async function rechteLaden() {
  try {
    const erg = await apiCall('diakronos.planrahmen.api.lied_rechte', {})
    darfSchreiben.value = !!erg?.darf_schreiben
  } catch (e) {
    darfSchreiben.value = false
  }
}

function neueGruppe() {
  // Anlegen = leeres Detail; der Dialog startet im Neu-Modus.
  editorDetail.value = { liedgruppe: {}, lieder: [], rollen: [] }
  editorOffen.value = true
}

async function nachSpeichern(name) {
  await load()
  if (name) navigate('#/liedgruppen/' + encodeURIComponent(name))
}

const TYPEN = ['Werk', 'Musical', 'Kantate', 'Sammlung', 'Gesangbuch', 'Buch', 'Projekt', 'Reihe', 'Mappe', 'Sonstiges']

// DES-01: Chips aus dem Baustein. Arten ohne Gruppe erscheinen nicht (sonst
// standen dort Chips mit 0, die nichts anzeigen konnten).
const typChips = computed(() => chipsAus(
  gruppen.value.filter(g => TYPEN.includes(g.typ) || g.typ),
  (g) => g.typ,
).filter(c => c.anzahl > 0 || istAlle(c.id)))

const filtered = computed(() => filtereNachChip(gruppen.value, activeTyp.value, (g) => g.typ))

function typPill(t) {
  if (t === 'Musical' || t === 'Kantate') return 'dk-badge-info'
  if (t === 'Sammlung') return 'dk-badge-success'
  if (t === 'Werk') return 'dk-badge-warning'
  return ''
}

async function load() {
  loading.value = true
  error.value = null
  try {
    // Große Stichprobe laden und client-seitig nach Typ filtern
    const data = await apiCall('diakronos.psalmos.api.musik.get_liedgruppen', { limit: 500 })
    gruppen.value = data || []
  } catch (err) {
    error.value = err?.message || 'Fehler beim Laden der Liedgruppen'
    console.error('Liedgruppen — Fehler:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  rechteLaden()
})
</script>

<style scoped>
/* DES-02/OP-UI-19: Leertext als Klasse, zwei getrennte Fälle. */
.lg-leer-titel { margin: 0; font-size: var(--fs); font-weight: 600; color: var(--text); }
.lg-leer-text { margin: var(--sp-1) 0 0; font-size: var(--fs-sm); color: var(--subtle); }

.ld-state { display: flex; align-items: center; gap: 10px; color: var(--dk-text-muted); padding: 30px 0; }
.ld-spinner {
  width: 18px; height: 18px; border-radius: 50%;
  border: 2px solid var(--dk-border); border-top-color: var(--dk-brand-400);
  animation: ld-spin 0.7s linear infinite;
}
@keyframes ld-spin { to { transform: rotate(360deg); } }

.ld-error {
  padding: 20px;
  background: color-mix(in oklch, var(--dk-danger) 8%, var(--dk-surface));
  border: 1px solid color-mix(in oklch, var(--dk-danger) 25%, var(--dk-surface));
  border-radius: 12px;
  color: var(--dk-danger);
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.ld-empty { text-align: center; padding: 40px 0; }

.lg-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 14px;
}
.lg-card {
  background: var(--dk-surface);
  border: 1px solid var(--dk-border);
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: box-shadow 0.15s, border-color 0.15s, transform 0.15s;
}
.lg-card:hover {
  border-color: var(--dk-brand-400);
  box-shadow: 0 4px 16px rgba(0,0,0,0.08);
  transform: translateY(-2px);
}
.lg-card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.lg-card-name { font-size: 15px; font-weight: 600; color: var(--dk-text); margin-bottom: 8px; }
.lg-card-meta { display: flex; flex-direction: column; gap: 3px; font-size: 12px; color: var(--dk-text-muted); }
.lg-card-gruppe { color: var(--dk-text-subtle); }
</style>
