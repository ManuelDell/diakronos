<template>
  <div class="dk-screen dk-screen-enter" style="display:flex;flex-direction:column;gap:0;">
    <div class="dk-screen-header" style="flex-shrink:0;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:20px;">
      <div>
        <h1 class="dk-screen-title">Gruppen</h1>
        <p class="dk-screen-sub">Übersicht aller Dienstbereiche, Gruppen und Untergruppen.</p>
      </div>
    </div>

    <div v-if="loading" style="display:flex;align-items:center;justify-content:center;padding:60px 0;color:var(--dk-text-muted);">Lade…</div>

    <template v-else>

      <!-- ═══ Meine Gruppen ═══ -->
      <section v-if="meineGruppen.length > 0" style="margin-bottom:32px;">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
          <span style="font-size:1.05rem;font-weight:700;color:var(--dk-text);">Meine Gruppen</span>
          <span style="font-size:0.78rem;color:var(--dk-text-muted);background:var(--dk-surface-2);padding:2px 9px;border-radius:20px;border:1px solid var(--dk-border);">{{ gefilterteMeineGruppen.length }}</span>
        </div>

        <!-- Pill-Filter-Chips -->
        <div class="dk-filters" style="margin-bottom:14px;">
          <div class="dk-filter-group">
            <button
              v-for="chip in meineDienstbereichChips"
              :key="chip.id"
              class="dk-filter-chip"
              :class="{ 'is-active': aktiverMeineChip === chip.id }"
              @click="aktiverMeineChip = chip.id"
            >
              {{ chip.label }} {{ chip.count }}
            </button>
          </div>
        </div>

        <!-- Horizontales 2-Zeilen-Grid -->
        <div v-if="gefilterteMeineGruppen.length === 0" style="color:var(--dk-text-muted);font-size:0.88rem;padding:12px 0;">
          Keine Gruppen in diesem Dienstbereich.
        </div>
        <div v-else class="gr-grid-scroll">
          <div
            v-for="g in gefilterteMeineGruppen"
            :key="g.name"
            class="gr-kachel"
            @click="() => { location.hash = '#/gruppe/' + g.name }"
            @mouseenter="e=>{e.currentTarget.style.boxShadow='0 4px 18px rgba(0,0,0,0.13)';e.currentTarget.style.transform='translateY(-2px)'}"
            @mouseleave="e=>{e.currentTarget.style.boxShadow='none';e.currentTarget.style.transform='none'}"
          >
            <div class="gr-kachel-img">
              <img v-if="g.bild" :src="g.bild" style="width:100%;height:100%;object-fit:cover;" />
              <div v-else :style="`width:100%;height:100%;background:${g.dienstbereich_farbe};opacity:0.85;`"></div>
              <span v-if="g.ist_verantwortlich" class="gr-badge">Verantwortlich</span>
            </div>
            <div class="gr-kachel-body">
              <div class="gr-kachel-name">{{ g.gruppenname }}</div>
              <div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap;margin-bottom:5px;">
                <span v-if="g.gruppentyp_name" class="gr-typ-tag">{{ g.gruppentyp_name }}</span>
              </div>
              <div class="gr-kachel-meta">👤 {{ g.mitglieder_count }} Mitglieder</div>
            </div>
          </div>
        </div>
      </section>

      <!-- ═══ Alle Gruppen (nur Admins) ═══ -->
      <section v-if="isAdmin && alleGruppenFlach.length > 0" style="margin-top:4px;">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
          <span style="font-size:1.05rem;font-weight:700;color:var(--dk-text);">Alle Gruppen</span>
          <span style="font-size:0.78rem;color:var(--dk-text-muted);background:var(--dk-surface-2);padding:2px 9px;border-radius:20px;border:1px solid var(--dk-border);">{{ gefilterteAlleGruppen.length }}</span>
        </div>

        <!-- Pill-Filter-Chips -->
        <div class="dk-filters" style="margin-bottom:14px;">
          <div class="dk-filter-group">
            <button
              v-for="chip in alleDienstbereichChips"
              :key="chip.id"
              class="dk-filter-chip"
              :class="{ 'is-active': aktiverAlleChip === chip.id }"
              @click="aktiverAlleChip = chip.id"
            >
              {{ chip.label }} {{ chip.count }}
            </button>
          </div>
        </div>

        <!-- Horizontales 2-Zeilen-Grid -->
        <div v-if="gefilterteAlleGruppen.length === 0" style="color:var(--dk-text-muted);font-size:0.88rem;padding:12px 0;">
          Keine Gruppen in diesem Dienstbereich.
        </div>
        <div v-else class="gr-grid-scroll">
          <div
            v-for="g in gefilterteAlleGruppen"
            :key="g.name"
            class="gr-kachel"
            @click="() => { location.hash = '#/gruppe/' + g.name }"
            @mouseenter="e=>{e.currentTarget.style.boxShadow='0 4px 18px rgba(0,0,0,0.13)';e.currentTarget.style.transform='translateY(-2px)'}"
            @mouseleave="e=>{e.currentTarget.style.boxShadow='none';e.currentTarget.style.transform='none'}"
          >
            <div class="gr-kachel-img">
              <img v-if="g.bild" :src="g.bild" style="width:100%;height:100%;object-fit:cover;" />
              <div v-else :style="`width:100%;height:100%;background:${g.dienstbereich_farbe};opacity:0.85;`"></div>
            </div>
            <div class="gr-kachel-body">
              <div class="gr-kachel-name">{{ g.gruppenname }}</div>
              <div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap;margin-bottom:5px;">
                <span v-if="g.gruppentyp_name" class="gr-typ-tag">{{ g.gruppentyp_name }}</span>
              </div>
              <div class="gr-kachel-meta">👤 {{ g.mitglieder_count }} Mitglieder</div>
            </div>
          </div>
        </div>
      </section>

    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiCall } from '../composables/useApi.js'

const loading = ref(true)
const meineGruppen = ref([])
const andereGruppen = ref([])
const isAdmin = ref(false)

const aktiverMeineChip = ref('alle')
const aktiverAlleChip = ref('alle')

// ─── Chips für Meine Gruppen ───
const meineDienstbereichChips = computed(() => {
  const map = new Map()
  for (const g of meineGruppen.value) {
    const name = g.dienstbereich_name || g.dienstbereich_abbr || 'Unbekannt'
    map.set(name, (map.get(name) || 0) + 1)
  }
  const chips = [{ id: 'alle', label: 'Alle', count: meineGruppen.value.length }]
  for (const [label, count] of [...map.entries()].sort((a, b) => a[0].localeCompare(b[0], 'de'))) {
    chips.push({ id: label, label, count })
  }
  return chips
})

// ─── Gefilterte Meine Gruppen ───
const gefilterteMeineGruppen = computed(() => {
  if (aktiverMeineChip.value === 'alle') return meineGruppen.value
  const name = aktiverMeineChip.value
  return meineGruppen.value.filter(g => (g.dienstbereich_name || g.dienstbereich_abbr || 'Unbekannt') === name)
})

// ─── Alle Gruppen: flaches Array aus andereGruppen ───
const alleGruppenFlach = computed(() => {
  const flat = []
  for (const db of andereGruppen.value) {
    for (const g of db.gruppen) {
      flat.push({
        ...g,
        dienstbereich_name: g.dienstbereich_name || db.dienstbereich_name || g.dienstbereich_abbr || 'Unbekannt',
        dienstbereich_farbe: g.dienstbereich_farbe || db.dienstbereich_farbe || null,
      })
    }
  }
  return flat
})

// ─── Chips für Alle Gruppen ───
const alleDienstbereichChips = computed(() => {
  const map = new Map()
  for (const g of alleGruppenFlach.value) {
    const name = g.dienstbereich_name || 'Unbekannt'
    map.set(name, (map.get(name) || 0) + 1)
  }
  const chips = [{ id: 'alle', label: 'Alle', count: alleGruppenFlach.value.length }]
  for (const [label, count] of [...map.entries()].sort((a, b) => a[0].localeCompare(b[0], 'de'))) {
    chips.push({ id: label, label, count })
  }
  return chips
})

// ─── Gefilterte Alle Gruppen ───
const gefilterteAlleGruppen = computed(() => {
  if (aktiverAlleChip.value === 'alle') return alleGruppenFlach.value
  const name = aktiverAlleChip.value
  return alleGruppenFlach.value.filter(g => (g.dienstbereich_name || 'Unbekannt') === name)
})

async function loadData() {
  loading.value = true
  try {
    const data = await apiCall('diakronos.diakonos.api.gruppen.get_gruppen_page_data')
    meineGruppen.value = data?.meine_gruppen || []
    andereGruppen.value = data?.andere_gruppen || []
    isAdmin.value = data?.is_admin || false
  } catch (err) {
    console.error('Fehler beim Laden:', err)
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
/* ── Horizontales 2-Zeilen-Grid mit Scroll ── */
.gr-grid-scroll {
  display: grid;
  grid-auto-flow: column;
  grid-template-rows: repeat(2, auto);
  gap: 14px;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  scroll-behavior: smooth;
  padding-bottom: 8px;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.gr-grid-scroll::-webkit-scrollbar { display: none; }

/* ── Kachel ── */
.gr-kachel {
  width: 190px;
  border-radius: 12px;
  overflow: hidden;
  background: var(--dk-surface);
  border: 1px solid var(--dk-border);
  scroll-snap-align: start;
  cursor: pointer;
  transition: box-shadow 0.15s, transform 0.15s;
  flex-shrink: 0;
}

.gr-kachel-img {
  height: 96px;
  position: relative;
  overflow: hidden;
}

.gr-badge {
  position: absolute;
  top: 7px;
  right: 7px;
  background: rgba(0,0,0,0.55);
  color: white;
  font-size: 0.62rem;
  padding: 2px 7px;
  border-radius: 20px;
  backdrop-filter: blur(4px);
}

.gr-kachel-body {
  padding: 10px 12px;
}

.gr-kachel-name {
  font-weight: 600;
  font-size: 0.87rem;
  color: var(--dk-text);
  margin-bottom: 5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.gr-typ-tag {
  font-size: 0.67rem;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--dk-surface-2);
  color: var(--dk-text-muted);
  border: 1px solid var(--dk-border);
}

.gr-kachel-meta {
  font-size: 0.75rem;
  color: var(--dk-text-muted);
}
</style>
