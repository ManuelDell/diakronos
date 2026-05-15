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
      <!-- Filter-/Sortierleiste (nur wenn Meine Gruppen vorhanden) -->
      <div v-if="meineGruppen.length > 0" style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:20px;">
        <div style="display:flex;align-items:center;gap:6px;">
          <label style="font-size:0.82rem;color:var(--dk-text-muted);white-space:nowrap;">Gruppieren nach:</label>
          <select v-model="gruppiereNach" class="dk-form-input" style="padding:4px 8px;font-size:0.82rem;height:auto;width:auto;min-width:140px;">
            <option value="dienstbereich">Dienstbereich</option>
            <option value="typ">Gruppentyp</option>
          </select>
        </div>
        <input
          v-model="suchtext"
          type="text"
          placeholder="Gruppe suchen…"
          class="dk-form-input"
          style="padding:4px 10px;font-size:0.82rem;height:auto;width:auto;min-width:180px;"
        />
      </div>

      <!-- Meine Gruppen -->
      <section v-if="meineGruppen.length > 0" style="margin-bottom:28px;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
          <div style="display:flex;align-items:center;gap:10px;">
            <span style="font-size:1.05rem;font-weight:700;color:var(--dk-text);">Meine Gruppen</span>
            <span style="font-size:0.78rem;color:var(--dk-text-muted);background:var(--dk-surface-2);padding:2px 9px;border-radius:20px;border:1px solid var(--dk-border);">{{ gefilterteMeineGruppen.length }}</span>
          </div>
          <div style="display:flex;gap:6px;">
            <button class="dk-btn dk-btn-ghost" style="padding:4px 12px;font-size:0.85rem;" @click="scrollCarousel(meineScroll,-1)">←</button>
            <button class="dk-btn dk-btn-ghost" style="padding:4px 12px;font-size:0.85rem;" @click="scrollCarousel(meineScroll,1)">→</button>
          </div>
        </div>

        <div v-if="gefilterteMeineGruppen.length === 0" style="color:var(--dk-text-muted);font-size:0.88rem;padding:12px 0;">
          Keine Gruppen für diese Suche.
        </div>
        <template v-else>
          <template v-for="grp in gruppiertMeineGruppen" :key="grp.label">
            <div v-if="gruppiertMeineGruppen.length > 1" style="font-size:0.8rem;color:var(--dk-text-muted);font-weight:600;margin-bottom:8px;margin-top:12px;display:flex;align-items:center;gap:6px;">
              <span v-if="grp.farbe" :style="`display:inline-block;width:8px;height:8px;border-radius:50%;background:${grp.farbe};`"></span>
              {{ grp.label }}
            </div>
            <div ref="meineScroll" style="display:flex;gap:14px;overflow-x:auto;scroll-snap-type:x mandatory;scroll-behavior:smooth;padding-bottom:6px;scrollbar-width:none;-ms-overflow-style:none;margin-bottom:8px;">
              <div v-for="g in grp.gruppen" :key="g.name"
                   style="flex:0 0 190px;border-radius:12px;overflow:hidden;background:var(--dk-surface);border:1px solid var(--dk-border);scroll-snap-align:start;cursor:pointer;transition:box-shadow 0.15s,transform 0.15s;"
                   @click="() => { location.hash = '#/gruppe/' + g.name }"
                   @mouseenter="e=>{e.currentTarget.style.boxShadow='0 4px 18px rgba(0,0,0,0.13)';e.currentTarget.style.transform='translateY(-2px)'}"
                   @mouseleave="e=>{e.currentTarget.style.boxShadow='none';e.currentTarget.style.transform='none'}">
                <div style="height:96px;position:relative;overflow:hidden;">
                  <img v-if="g.bild" :src="g.bild" style="width:100%;height:100%;object-fit:cover;" />
                  <div v-else :style="`width:100%;height:100%;background:${g.dienstbereich_farbe};opacity:0.85;`"></div>
                  <span v-if="g.ist_verantwortlich"
                        style="position:absolute;top:7px;right:7px;background:rgba(0,0,0,0.55);color:white;font-size:0.62rem;padding:2px 7px;border-radius:20px;backdrop-filter:blur(4px);">
                    Verantwortlich
                  </span>
                </div>
                <div style="padding:10px 12px;">
                  <div style="font-weight:600;font-size:0.87rem;color:var(--dk-text);margin-bottom:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{{ g.gruppenname }}</div>
                  <div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap;margin-bottom:5px;">
                    <span v-if="g.gruppentyp_name" style="font-size:0.67rem;padding:1px 6px;border-radius:4px;background:var(--dk-surface-2);color:var(--dk-text-muted);border:1px solid var(--dk-border);">{{ g.gruppentyp_name }}</span>
                  </div>
                  <div style="font-size:0.75rem;color:var(--dk-text-muted);">👤 {{ g.mitglieder_count }} Mitglieder</div>
                </div>
              </div>
            </div>
          </template>
        </template>
      </section>

      <!-- Alle Gruppen (nur für Admins) -->
      <section v-if="isAdmin && andereGruppen.length > 0" style="margin-top:4px;">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">
          <span style="font-size:1.05rem;font-weight:700;color:var(--dk-text);">Alle Gruppen</span>
          <span style="font-size:0.78rem;color:var(--dk-text-muted);background:var(--dk-surface-2);padding:2px 9px;border-radius:20px;border:1px solid var(--dk-border);">{{ gefilterteAndereGruppenTotal }}</span>
        </div>
        <template v-for="grp in gruppiertAndereGruppen" :key="grp.label">
          <div style="font-size:0.8rem;color:var(--dk-text-muted);font-weight:600;margin-bottom:8px;margin-top:4px;display:flex;align-items:center;gap:6px;">
            <span v-if="grp.farbe" :style="`display:inline-block;width:8px;height:8px;border-radius:50%;background:${grp.farbe};`"></span>
            {{ grp.label }}
          </div>
          <div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:16px;">
            <div v-for="g in grp.gruppen" :key="g.name"
                 style="flex:0 0 190px;border-radius:12px;overflow:hidden;background:var(--dk-surface);border:1px solid var(--dk-border);cursor:pointer;transition:box-shadow 0.15s,transform 0.15s;"
                 @click="() => { location.hash = '#/gruppe/' + g.name }"
                 @mouseenter="e=>{e.currentTarget.style.boxShadow='0 4px 18px rgba(0,0,0,0.13)';e.currentTarget.style.transform='translateY(-2px)'}"
                 @mouseleave="e=>{e.currentTarget.style.boxShadow='none';e.currentTarget.style.transform='none'}">
              <div style="height:96px;position:relative;overflow:hidden;">
                <img v-if="g.bild" :src="g.bild" style="width:100%;height:100%;object-fit:cover;" />
                <div v-else :style="`width:100%;height:100%;background:${g.dienstbereich_farbe};opacity:0.85;`"></div>
              </div>
              <div style="padding:10px 12px;">
                <div style="font-weight:600;font-size:0.87rem;color:var(--dk-text);margin-bottom:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{{ g.gruppenname }}</div>
                <div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap;margin-bottom:5px;">
                  <span v-if="g.gruppentyp_name" style="font-size:0.67rem;padding:1px 6px;border-radius:4px;background:var(--dk-surface-2);color:var(--dk-text-muted);border:1px solid var(--dk-border);">{{ g.gruppentyp_name }}</span>
                </div>
                <div style="font-size:0.75rem;color:var(--dk-text-muted);">👤 {{ g.mitglieder_count }} Mitglieder</div>
              </div>
            </div>
          </div>
        </template>
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
const meineScroll = ref(null)

const gruppiereNach = ref('dienstbereich')
const suchtext = ref('')

// Hilfsfunktion: gruppiert ein flaches Array nach Kriterium
// gibt [{label, farbe, gruppen:[]}] zurück
function groupBy(gruppen, kriterium) {
  const map = new Map()
  for (const g of gruppen) {
    let label, farbe
    if (kriterium === 'dienstbereich') {
      label = g.dienstbereich_abbr || 'Unbekannt'
      farbe = g.dienstbereich_farbe || null
    } else if (kriterium === 'typ') {
      label = g.gruppentyp_name || 'Ohne Typ'
      farbe = null
    } else {
      label = 'Alle'
      farbe = null
    }
    if (!map.has(label)) map.set(label, { label, farbe, gruppen: [] })
    map.get(label).gruppen.push(g)
  }
  return [...map.values()].sort((a, b) => a.label.localeCompare(b.label, 'de'))
}

// Gefilterte "Meine Gruppen" (nach Suchtext)
const gefilterteMeineGruppen = computed(() => {
  const q = suchtext.value.trim().toLowerCase()
  if (!q) return meineGruppen.value
  return meineGruppen.value.filter(g => g.gruppenname.toLowerCase().includes(q))
})

const gruppiertMeineGruppen = computed(() => groupBy(gefilterteMeineGruppen.value, gruppiereNach.value))

// "Alle Gruppen": flache Liste aus andereGruppen-Struktur, gefiltert, dann neu gruppiert
const andereGruppenFlach = computed(() => {
  const flat = []
  for (const db of andereGruppen.value) {
    for (const g of db.gruppen) {
      if (!g.ist_meins) {
        flat.push({ ...g, _dienstbereich_name: db.dienstbereich_name, _dienstbereich_farbe: db.dienstbereich_farbe })
      }
    }
  }
  return flat
})

const gefilterteAndereGruppen = computed(() => {
  const q = suchtext.value.trim().toLowerCase()
  if (!q) return andereGruppenFlach.value
  return andereGruppenFlach.value.filter(g => g.gruppenname.toLowerCase().includes(q))
})

const gefilterteAndereGruppenTotal = computed(() => gefilterteAndereGruppen.value.length)

const gruppiertAndereGruppen = computed(() => {
  if (gruppiereNach.value === 'dienstbereich') {
    const map = new Map()
    for (const g of gefilterteAndereGruppen.value) {
      const label = g._dienstbereich_name || g.dienstbereich_abbr || 'Unbekannt'
      const farbe = g._dienstbereich_farbe || g.dienstbereich_farbe || null
      if (!map.has(label)) map.set(label, { label, farbe, gruppen: [] })
      map.get(label).gruppen.push(g)
    }
    return [...map.values()].sort((a, b) => a.label.localeCompare(b.label, 'de'))
  }
  return groupBy(gefilterteAndereGruppen.value, gruppiereNach.value)
})

function scrollCarousel(el, dir) {
  if (el) el.scrollBy({ left: dir * 210, behavior: 'smooth' })
}

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
