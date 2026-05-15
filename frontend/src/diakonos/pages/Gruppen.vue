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
      <!-- Meine Gruppen -->
      <section v-if="meineGruppen.length > 0" style="margin-bottom:28px;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
          <div style="display:flex;align-items:center;gap:10px;">
            <span style="font-size:1.05rem;font-weight:700;color:var(--dk-text);">Meine Gruppen</span>
            <span style="font-size:0.78rem;color:var(--dk-text-muted);background:var(--dk-surface-2);padding:2px 9px;border-radius:20px;border:1px solid var(--dk-border);">{{ gefilterteGruppen.length }}</span>
          </div>
          <div style="display:flex;gap:6px;">
            <button class="dk-btn dk-btn-ghost" style="padding:4px 12px;font-size:0.85rem;" @click="scrollCarousel(meineScroll,-1)">←</button>
            <button class="dk-btn dk-btn-ghost" style="padding:4px 12px;font-size:0.85rem;" @click="scrollCarousel(meineScroll,1)">→</button>
          </div>
        </div>

        <!-- Filter -->
        <div v-if="meineGruppen.length > 1" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">
          <select v-model="filterDienstbereich" class="dk-form-input" style="padding:4px 8px;font-size:0.82rem;height:auto;width:auto;min-width:140px;">
            <option value="">Alle Dienstbereiche</option>
            <option v-for="db in dienstbereichOptionen" :key="db" :value="db">{{ db }}</option>
          </select>
          <select v-model="filterTyp" class="dk-form-input" style="padding:4px 8px;font-size:0.82rem;height:auto;width:auto;min-width:130px;">
            <option value="">Alle Typen</option>
            <option v-for="t in typOptionen" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>

        <div v-if="gefilterteGruppen.length === 0" style="color:var(--dk-text-muted);font-size:0.88rem;padding:12px 0;">
          Keine Gruppen für diese Auswahl.
        </div>
        <div v-else ref="meineScroll" style="display:flex;gap:14px;overflow-x:auto;scroll-snap-type:x mandatory;scroll-behavior:smooth;padding-bottom:6px;scrollbar-width:none;-ms-overflow-style:none;">
          <div v-for="g in gefilterteGruppen" :key="g.name"
               style="flex:0 0 190px;border-radius:12px;overflow:hidden;background:var(--dk-surface);border:1px solid var(--dk-border);scroll-snap-align:start;cursor:pointer;transition:box-shadow 0.15s,transform 0.15s;"
               @click="() => { window.location.hash = '#/gruppe/' + g.name }"
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
                <span v-if="g.dienstbereich_abbr" style="font-size:0.67rem;padding:1px 6px;border-radius:4px;background:var(--dk-surface-2);color:var(--dk-text-muted);border:1px solid var(--dk-border);">{{ g.dienstbereich_abbr }}</span>
              </div>
              <div style="font-size:0.75rem;color:var(--dk-text-muted);">👤 {{ g.mitglieder_count }} Mitglieder</div>
            </div>
          </div>
        </div>
      </section>

      <!-- Alle Gruppen (nur für Admins — Gruppen ohne eigene Mitgliedschaft) -->
      <section v-if="isAdmin && andereGruppen.length > 0" style="margin-top:4px;">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">
          <span style="font-size:1.05rem;font-weight:700;color:var(--dk-text);">Alle Gruppen</span>
          <span style="font-size:0.78rem;color:var(--dk-text-muted);background:var(--dk-surface-2);padding:2px 9px;border-radius:20px;border:1px solid var(--dk-border);">{{ totalAndereGruppen }}</span>
        </div>
        <div v-for="dbSection in andereGruppen" :key="dbSection.dienstbereich" style="margin-bottom:20px;">
          <div style="font-size:0.8rem;color:var(--dk-text-muted);font-weight:600;margin-bottom:8px;display:flex;align-items:center;gap:6px;">
            <span :style="`display:inline-block;width:8px;height:8px;border-radius:50%;background:${dbSection.dienstbereich_farbe};`"></span>
            {{ dbSection.dienstbereich_name }}
          </div>
          <div style="display:flex;gap:14px;flex-wrap:wrap;">
            <div v-for="g in dbSection.gruppen" :key="g.name"
                 style="flex:0 0 190px;border-radius:12px;overflow:hidden;background:var(--dk-surface);border:1px solid var(--dk-border);cursor:pointer;transition:box-shadow 0.15s,transform 0.15s;"
                 @click="() => { window.location.hash = '#/gruppe/' + g.name }"
                 @mouseenter="e=>{e.currentTarget.style.boxShadow='0 4px 18px rgba(0,0,0,0.13)';e.currentTarget.style.transform='translateY(-2px)'}"
                 @mouseleave="e=>{e.currentTarget.style.boxShadow='none';e.currentTarget.style.transform='none'}">
              <div style="height:96px;position:relative;overflow:hidden;">
                <img v-if="g.bild" :src="g.bild" style="width:100%;height:100%;object-fit:cover;" />
                <div v-else :style="`width:100%;height:100%;background:${g.dienstbereich_farbe};opacity:0.85;`"></div>
              </div>
              <div style="padding:10px 12px;">
                <div style="font-weight:600;font-size:0.87rem;color:var(--dk-text);margin-bottom:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{{ g.gruppenname }}</div>
                <div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap;margin-bottom:5px;">
                  <span v-if="g.dienstbereich_abbr" style="font-size:0.67rem;padding:1px 6px;border-radius:4px;background:var(--dk-surface-2);color:var(--dk-text-muted);border:1px solid var(--dk-border);">{{ g.dienstbereich_abbr }}</span>
                  <span v-if="g.gruppentyp_name" style="font-size:0.67rem;padding:1px 6px;border-radius:4px;background:var(--dk-surface-2);color:var(--dk-text-muted);border:1px solid var(--dk-border);">{{ g.gruppentyp_name }}</span>
                </div>
                <div style="font-size:0.75rem;color:var(--dk-text-muted);">👤 {{ g.mitglieder_count }} Mitglieder</div>
              </div>
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
const meineScroll = ref(null)

const filterDienstbereich = ref('')
const filterTyp = ref('')

const totalAndereGruppen = computed(() => andereGruppen.value.reduce((s, db) => s + db.gruppen.length, 0))

const dienstbereichOptionen = computed(() => {
  const set = new Set()
  meineGruppen.value.forEach(g => { if (g.dienstbereich_name) set.add(g.dienstbereich_name) })
  return [...set].sort()
})

const typOptionen = computed(() => {
  const set = new Set()
  meineGruppen.value.forEach(g => { if (g.gruppentyp_name) set.add(g.gruppentyp_name) })
  return [...set].sort()
})

const gefilterteGruppen = computed(() => {
  let list = meineGruppen.value
  if (filterDienstbereich.value) list = list.filter(g => g.dienstbereich_name === filterDienstbereich.value)
  if (filterTyp.value) list = list.filter(g => g.gruppentyp_name === filterTyp.value)
  return list
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
