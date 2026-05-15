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
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
          <div style="display:flex;align-items:center;gap:10px;">
            <span style="font-size:1.05rem;font-weight:700;color:var(--dk-text);">Meine Gruppen</span>
            <span style="font-size:0.78rem;color:var(--dk-text-muted);background:var(--dk-surface-2);padding:2px 9px;border-radius:20px;border:1px solid var(--dk-border);">{{ meineGruppen.length }}</span>
          </div>
          <div style="display:flex;gap:6px;">
            <button class="dk-btn dk-btn-ghost" style="padding:4px 12px;font-size:0.85rem;" @click="scrollCarousel(meineScroll,-1)">←</button>
            <button class="dk-btn dk-btn-ghost" style="padding:4px 12px;font-size:0.85rem;" @click="scrollCarousel(meineScroll,1)">→</button>
          </div>
        </div>
        <div ref="meineScroll" style="display:flex;gap:14px;overflow-x:auto;scroll-snap-type:x mandatory;scroll-behavior:smooth;padding-bottom:6px;scrollbar-width:none;-ms-overflow-style:none;">
          <div v-for="g in meineGruppen" :key="g.name"
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
                <span v-if="g.gruppentyp_name" style="font-size:0.67rem;padding:1px 6px;border-radius:4px;background:var(--dk-surface-2);color:var(--dk-text-muted);border:1px solid var(--dk-border);">{{ g.gruppentyp_name }}</span>
              </div>
              <div style="font-size:0.75rem;color:var(--dk-text-muted);">👤 {{ g.mitglieder_count }} Mitglieder</div>
            </div>
          </div>
        </div>
      </section>

      <!-- Gruppentypen -->
      <section>
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">
          <span style="font-size:1.05rem;font-weight:700;color:var(--dk-text);">Gruppentypen</span>
          <span style="font-size:0.78rem;color:var(--dk-text-muted);background:var(--dk-surface-2);padding:2px 9px;border-radius:20px;border:1px solid var(--dk-border);">{{ totalGruppen }} Gruppen</span>
        </div>

        <div v-if="gruppentypen.length === 0" style="color:var(--dk-text-muted);font-size:0.9rem;padding:20px 0;text-align:center;">
          Noch keine Gruppentypen vorhanden.
        </div>

        <div v-else style="display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:14px;">
          <div v-for="typ in gruppentypen" :key="typ.name"
               style="border-radius:12px;overflow:hidden;background:var(--dk-surface);border:1px solid var(--dk-border);cursor:pointer;transition:box-shadow 0.15s,transform 0.15s;"
               :style="selectedTyp?.name === typ.name ? 'box-shadow:0 0 0 2px var(--dk-btn-primary);transform:none;' : ''"
               @click="selectTyp(typ)"
               @mouseenter="e=>{if(selectedTyp?.name!==typ.name){e.currentTarget.style.boxShadow='0 4px 18px rgba(0,0,0,0.10)';e.currentTarget.style.transform='translateY(-2px)'}}"
               @mouseleave="e=>{if(selectedTyp?.name!==typ.name){e.currentTarget.style.boxShadow='';e.currentTarget.style.transform=''}}">
            <!-- 2x2 image mosaic or solid color -->
            <div style="height:108px;overflow:hidden;">
              <template v-if="typ.gruppen.filter(g=>g.bild).length >= 1">
                <div style="display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;height:108px;gap:1px;background:var(--dk-border);">
                  <div v-for="i in 4" :key="i" :style="`overflow:hidden;background:${typ.farbe}33;`">
                    <img v-if="typ.gruppen.filter(g=>g.bild)[i-1]" :src="typ.gruppen.filter(g=>g.bild)[i-1].bild" style="width:100%;height:100%;object-fit:cover;" />
                    <div v-else :style="`width:100%;height:100%;background:${typ.farbe}44;`"></div>
                  </div>
                </div>
              </template>
              <div v-else :style="`width:100%;height:100%;background:${typ.farbe};display:flex;align-items:center;justify-content:center;font-size:2.2rem;opacity:0.5;`">👥</div>
            </div>
            <div style="padding:10px 12px;">
              <div style="font-weight:700;font-size:0.9rem;color:var(--dk-text);">{{ typ.typname }}</div>
              <div style="font-size:0.78rem;color:var(--dk-text-muted);margin-top:2px;">{{ typ.gruppen_count }} Gruppen</div>
            </div>
          </div>
        </div>

        <!-- Selected type drill-down -->
        <div v-if="selectedTyp" style="margin-top:18px;padding:16px 18px;background:var(--dk-surface);border-radius:12px;border:1px solid var(--dk-border);">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
            <div style="display:flex;align-items:center;gap:10px;">
              <span style="font-weight:700;font-size:0.95rem;color:var(--dk-text);">{{ selectedTyp.typname }}</span>
              <span style="font-size:0.75rem;color:var(--dk-text-muted);">{{ selectedTyp.gruppen.length }} Gruppen</span>
            </div>
            <button class="dk-btn dk-btn-ghost" style="padding:2px 9px;font-size:0.8rem;" @click="selectedTyp=null">✕</button>
          </div>
          <div v-if="selectedTyp.gruppen.length === 0" style="color:var(--dk-text-muted);font-size:0.85rem;">Keine Gruppen in diesem Typ.</div>
          <div v-else style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:11px;">
            <div v-for="g in selectedTyp.gruppen" :key="g.name"
                 style="border-radius:10px;overflow:hidden;background:var(--dk-surface-2);border:1px solid var(--dk-border);cursor:pointer;transition:box-shadow 0.12s;"
                 @click="() => { window.location.hash = '#/gruppe/' + g.name }"
                 @mouseenter="e=>e.currentTarget.style.boxShadow='0 2px 10px rgba(0,0,0,0.09)'"
                 @mouseleave="e=>e.currentTarget.style.boxShadow='none'">
              <div style="height:72px;overflow:hidden;position:relative;">
                <img v-if="g.bild" :src="g.bild" style="width:100%;height:100%;object-fit:cover;" />
                <div v-else :style="`width:100%;height:100%;background:${selectedTyp.farbe};opacity:0.6;`"></div>
                <span v-if="g.ist_meins" style="position:absolute;top:5px;right:5px;background:#166534;color:white;font-size:0.6rem;padding:1px 6px;border-radius:20px;">Meine</span>
              </div>
              <div style="padding:8px 10px;">
                <div style="font-weight:600;font-size:0.82rem;color:var(--dk-text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{{ g.gruppenname }}</div>
                <div style="display:flex;align-items:center;gap:4px;margin-top:4px;">
                  <span v-if="g.dienstbereich_abbr" style="font-size:0.63rem;padding:1px 5px;border-radius:4px;background:var(--dk-surface);color:var(--dk-text-muted);border:1px solid var(--dk-border);">{{ g.dienstbereich_abbr }}</span>
                </div>
                <div style="font-size:0.72rem;color:var(--dk-text-muted);margin-top:3px;">👤 {{ g.mitglieder_count }}</div>
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
const gruppentypen = ref([])
const selectedTyp = ref(null)
const meineScroll = ref(null)

const totalGruppen = computed(() => gruppentypen.value.reduce((s, t) => s + t.gruppen_count, 0))

function scrollCarousel(el, dir) {
  if (el) el.scrollBy({ left: dir * 210, behavior: 'smooth' })
}

function selectTyp(typ) {
  selectedTyp.value = selectedTyp.value?.name === typ.name ? null : typ
}

async function loadData() {
  loading.value = true
  try {
    const data = await apiCall('diakronos.diakonos.api.gruppen.get_gruppen_page_data')
    meineGruppen.value = data?.meine_gruppen || []
    gruppentypen.value = data?.gruppentypen || []
  } catch (err) {
    console.error('Fehler beim Laden:', err)
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>
