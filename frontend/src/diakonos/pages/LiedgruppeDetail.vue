<template>
  <div class="dk-screen dk-screen-enter">
    <!-- Seitenkopf -->
    <DkPageHeader
      :title="info.gruppenname || info.name || 'Liedgruppe'"
      :krumen="[{ text: 'Liedgruppen', href: '#/liedgruppen' }, { text: info.gruppenname || info.name || 'Liedgruppe' }]"
      :badges="kopfBadges"
    >
      <template v-if="darfSchreiben" #actions>
        <DkButton variant="secondary" @click="bearbeitenOeffnen">
          <svg slot="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
          Bearbeiten
        </DkButton>
        <DkButton variant="ghost" @click="loeschenFragen">Löschen</DkButton>
      </template>
    </DkPageHeader>

    <!-- UXM-R9: Anlegen/Bearbeiten-Dialog -->
    <LiedgruppeBearbeiten
      v-model="editorOffen"
      :detail="editorDetail"
      @gespeichert="nachSpeichern"
    />

    <!-- Löschen bestätigen (kein window.confirm) -->
    <DkDialog v-model="loeschDialog" title="Liedgruppe löschen?" size="sm" @close="loeschDialog = false">
      <p class="ldg-dialog-text">
        „{{ info.gruppenname || info.name }}“ wird mit ihren Liedzuordnungen gelöscht.
        Die Lieder selbst bleiben erhalten.
      </p>
      <template #footer>
        <DkButton variant="secondary" @click="loeschDialog = false">Abbrechen</DkButton>
        <DkButton variant="danger" :loading="loescht" @click="loeschenBestaetigt">Löschen</DkButton>
      </template>
    </DkDialog>

    <!-- Laden -->
    <div v-if="loading" class="ldg-zustand">Lade Liedgruppe…</div>

    <!-- Fehler -->
    <div v-else-if="error" class="ldg-fehler">
      {{ error }}
      <DkButton variant="secondary" size="sm" @click="loadDetail">Nochmal</DkButton>
    </div>

    <template v-else>
      <!-- Kopf -->
      <DkCard class="ldg-head">
        <div class="ldg-head-inhalt">
          <div class="ldg-head-haupt">
            <div class="ldg-meta-row">
              <DkBadge v-if="info.komponist" variant="neutral">🎼 {{ info.komponist }}</DkBadge>
              <DkBadge v-if="info.textautor" variant="neutral">✍️ {{ info.textautor }}</DkBadge>
              <DkBadge v-if="info.verlag" variant="neutral">🏷 {{ info.verlag }}</DkBadge>
              <DkBadge v-if="info.dauer_minuten" variant="neutral">⏱ {{ info.dauer_minuten }} Min.</DkBadge>
              <DkBadge v-if="info.gruppe" variant="neutral">{{ info.gruppe }}</DkBadge>
            </div>
            <p v-if="info.beschreibung" class="ldg-desc">{{ info.beschreibung }}</p>
            <p v-if="info.lizenzhinweis" class="ldg-lizenz">{{ info.lizenzhinweis }}</p>
          </div>
          <div class="ldg-counts">
            <span class="ldg-count">{{ lieder.length }} {{ wortImNumerus(lieder.length, 'Lied', 'Lieder') }}</span>
            <span v-if="rollen.length" class="ldg-count">{{ rollen.length }} {{ wortImNumerus(rollen.length, 'Rolle', 'Rollen') }}</span>
          </div>
        </div>
      </DkCard>

      <!-- Reiter -->
      <div class="ldg-tabs">
        <button class="ldg-tab" :class="{ 'is-active': tab === 'lieder' }" @click="tab = 'lieder'">
          Lieder <span class="ldg-tab-count">{{ lieder.length }}</span>
        </button>
        <button
          v-if="hasRollen"
          class="ldg-tab"
          :class="{ 'is-active': tab === 'rollen' }"
          @click="tab = 'rollen'"
        >
          Rollen <span class="ldg-tab-count">{{ rollen.length }}</span>
        </button>
      </div>

      <!-- Lieder -->
      <DkCard v-if="tab === 'lieder'" class="ldg-block" flach>
        <DkEmpty v-if="lieder.length === 0" title="Keine Lieder" text="Diese Liedgruppe enthält noch keine Lieder." icon="🎵" />
        <DkTable v-else :spalten="liederSpalten">
          <tr v-for="row in sortedLieder" :key="row.lied + '-' + row.reihenfolge" @click="gotoLied(row)">
            <td class="dk-cell-text ldg-nr">{{ row.nummer || row.reihenfolge || '–' }}</td>
            <td>
              <!-- UXM-R10: Titel statt interner Kennung; Kennung nur als Ersatz. -->
              <a :href="'#/lieder/' + encodeURIComponent(row.lied)" class="ldg-lied-link" @click.stop>
                {{ row.titel || row.lied }}
              </a>
              <div v-if="row.alternativtitel" class="ldg-lied-alt">{{ row.alternativtitel }}</div>
            </td>
            <td class="dk-cell-text">
              <span v-if="row.anzeige" :class="{ 'ldg-kopie': true }">{{ row.anzeige }}</span>
              <span v-else class="dk-text-subtle">–</span>
            </td>
            <td class="dk-cell-text">{{ row.fassung || 'Standard' }}</td>
            <td class="dk-cell-text">{{ row.szene || '–' }}</td>
            <td class="dk-cell-text ldg-notiz">{{ row.notiz || '–' }}</td>
          </tr>
        </DkTable>
      </DkCard>

      <!-- Rollen -->
      <DkCard v-else-if="tab === 'rollen'" class="ldg-block" flach>
        <DkEmpty v-if="rollen.length === 0" title="Keine Rollen hinterlegt" icon="🎭" />
        <div v-else class="ldg-rollen">
          <div v-for="r in rollen" :key="r.rollenname + '-' + r.stimmlage" class="ldg-rolle">
            <div class="ldg-rolle-head">
              <span class="ldg-rolle-name">{{ r.rollenname || '–' }}</span>
              <DkBadge v-if="r.rollentyp" variant="neutral">{{ r.rollentyp }}</DkBadge>
            </div>
            <div class="ldg-rolle-meta">
              <DkBadge v-if="r.stimmlage" variant="neutral">Stimmlage: {{ r.stimmlage }}</DkBadge>
              <DkBadge v-if="r.umfang" variant="neutral">Umfang: {{ r.umfang }}</DkBadge>
              <DkBadge v-if="r.anzahl_besetzungen" variant="neutral">{{ r.anzahl_besetzungen }}× besetzt</DkBadge>
              <DkBadge v-if="r.min_alter || r.max_alter" variant="neutral">Alter: {{ r.min_alter || '0' }}–{{ r.max_alter || '∞' }}</DkBadge>
            </div>
            <p v-if="r.beschreibung" class="ldg-rolle-desc">{{ r.beschreibung }}</p>
          </div>
        </div>
      </DkCard>
    </template>
  </div>
</template>

<script setup>
/**
 * LiedgruppeDetail — Werk/Musical/Kantate, Design-System „A · Ruhig & Klar“.
 * Reiner Darstellungsumbau: Kopf, Karten, Kennzeichen, Tabelle und
 * Leerzustaende kommen aus components/ui; Farben nur aus tokens.css.
 */
import { ref, computed, onMounted } from 'vue'
import { apiCall } from '../composables/useApi.js'
import { getRouteParam, navigate } from '../router.js'
import { usePlanrahmen, fehlerMeldungen } from '../composables/usePlanrahmen.js'
import { showToast } from '../composables/useToast.js'
import { wortImNumerus } from '../components/ui/begriffe.mjs'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkBadge from '../components/ui/DkBadge.vue'
import DkCard from '../components/ui/DkCard.vue'
import DkTable from '../components/ui/DkTable.vue'
import DkEmpty from '../components/ui/DkEmpty.vue'
import DkDialog from '../components/ui/DkDialog.vue'
import LiedgruppeBearbeiten from '../components/lieder/LiedgruppeBearbeiten.vue'

const { liedgruppeLoeschen } = usePlanrahmen()

const info = ref({})
const lieder = ref([])
const rollen = ref([])
const loading = ref(true)
const error = ref(null)
const tab = ref('lieder')

/* UXM-R9: Schreibrecht + Bearbeiten/Löschen. */
const darfSchreiben = ref(false)
const editorOffen = ref(false)
const editorDetail = ref(null)
const loeschDialog = ref(false)
const loescht = ref(false)

async function rechteLaden() {
  try {
    const erg = await apiCall('diakronos.planrahmen.api.lied_rechte', {})
    darfSchreiben.value = !!erg?.darf_schreiben
  } catch (e) {
    darfSchreiben.value = false
  }
}

function bearbeitenOeffnen() {
  editorDetail.value = { liedgruppe: { ...info.value }, lieder: lieder.value, rollen: rollen.value }
  editorOffen.value = true
}

async function nachSpeichern() {
  await loadDetail()
}

function loeschenFragen() {
  loeschDialog.value = true
}

async function loeschenBestaetigt() {
  loescht.value = true
  try {
    await liedgruppeLoeschen(info.value.name)
    showToast('Liedgruppe gelöscht.')
    navigate('#/liedgruppen')
  } catch (e) {
    error.value = fehlerMeldungen(e)?.[0]?.meldung || 'Löschen fehlgeschlagen.'
    loeschDialog.value = false
  } finally {
    loescht.value = false
  }
}

const gruppenName = getRouteParam('id') || ''

const hasRollen = computed(() => info.value.typ === 'Musical' || info.value.typ === 'Kantate')

/* Bausteine beschicken */
const liederSpalten = [
  { key: 'nr', label: 'Nr.', width: '48px' },
  { key: 'lied', label: 'Lied' },
  { key: 'anzeige', label: 'Kennung' },
  { key: 'fassung', label: 'Fassung' },
  { key: 'szene', label: 'Szene' },
  { key: 'notiz', label: 'Notiz' },
]
const kopfBadges = computed(() => {
  const badges = []
  if (info.value.typ) badges.push({ text: info.value.typ, variant: typVariante(info.value.typ) })
  if (info.value.status === 'Archiviert') badges.push({ text: 'Archiviert', variant: 'warn' })
  return badges
})

// Lieder sortiert nach reihenfolge (bzw. nummer als Fallback)
const sortedLieder = computed(() => {
  const arr = [...lieder.value]
  const key = row => (row.reihenfolge !== null && row.reihenfolge !== undefined)
    ? row.reihenfolge
    : (row.nummer !== null && row.nummer !== undefined ? row.nummer : Number.MAX_SAFE_INTEGER)
  arr.sort((a, b) => key(a) - key(b))
  return arr
})

/** Liedgruppen-Typ → Kennzeichen-Variante. */
function typVariante(t) {
  if (t === 'Musical' || t === 'Kantate') return 'info'
  if (t === 'Sammlung') return 'ok'
  if (t === 'Werk') return 'warn'
  return 'neutral'
}

function gotoLied(row) {
  window.location.hash = '#/lieder/' + encodeURIComponent(row.lied)
}

async function loadDetail() {
  if (!gruppenName) {
    error.value = 'Keine Liedgruppen-ID angegeben.'
    loading.value = false
    return
  }
  loading.value = true
  error.value = null
  try {
    const data = await apiCall('diakronos.psalmos.api.musik.get_liedgruppe_detail', { liedgruppe: gruppenName })
    info.value = data?.liedgruppe || {}
    lieder.value = data?.lieder || []
    rollen.value = data?.rollen || []
    tab.value = 'lieder'
  } catch (err) {
    error.value = err?.message || 'Fehler beim Laden der Liedgruppe'
    console.error('LiedgruppeDetail — Fehler:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadDetail()
  rechteLaden()
})
</script>

<style scoped>
.ldg-zustand { padding: var(--sp-8); text-align: center; color: var(--muted); }

.ldg-head-inhalt {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-4);
  flex-wrap: wrap;
}
.ldg-head-haupt { min-width: 0; }
.ldg-meta-row { display: flex; flex-wrap: wrap; gap: var(--sp-2); }
.ldg-desc { margin: var(--sp-3) 0 0; font-size: var(--fs-sm); color: var(--muted); }
.ldg-lizenz { margin: var(--sp-2) 0 0; font-size: var(--fs-sm); color: var(--subtle); font-style: italic; }
.ldg-counts { display: flex; flex-direction: column; gap: var(--sp-1); text-align: right; }
.ldg-count { font-size: var(--fs-sm); color: var(--muted); }

.ldg-tabs {
  display: flex; gap: 6px; border-bottom: 1px solid var(--line);
  padding-bottom: var(--sp-3);
  margin-bottom: var(--sp-4);
}
.ldg-tab {
  font-size: var(--fs-sm); padding: 6px var(--sp-3); border-radius: var(--radius);
  border: 1px solid var(--line); background: var(--surface-2);
  color: var(--muted); cursor: pointer;
  transition: background var(--fast) var(--ease), color var(--fast) var(--ease), border-color var(--fast) var(--ease);
}
.ldg-tab:hover { border-color: var(--primary); color: var(--text); }
.ldg-tab.is-active { background: var(--primary); border-color: var(--primary); color: var(--primary-ink); }
.ldg-tab-count { font-size: var(--fs-xs); opacity: 0.7; margin-left: 3px; }

.ldg-nr { font-weight: 600; color: var(--muted); }
.ldg-lied-link { color: var(--text); font-weight: 500; font-size: var(--fs-sm); text-decoration: none; }
.ldg-lied-link:hover { color: var(--primary); text-decoration: underline; }
.ldg-lied-alt { font-size: var(--fs-xs); color: var(--subtle); }
.ldg-kopie { font-style: italic; color: var(--muted); }
.ldg-notiz { color: var(--muted); }

.ldg-rollen { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: var(--sp-3); }
.ldg-rolle {
  border: 1px solid var(--line); border-radius: var(--radius);
  background: var(--surface-2); padding: var(--pad);
}
.ldg-rolle-head { display: flex; align-items: center; justify-content: space-between; gap: var(--sp-2); margin-bottom: var(--sp-2); }
.ldg-rolle-name { font-size: var(--fs); font-weight: 600; color: var(--text); }
.ldg-rolle-meta { display: flex; flex-wrap: wrap; gap: 6px; }
.ldg-rolle-desc { margin: var(--sp-3) 0 0; font-size: var(--fs-sm); color: var(--muted); }

.ldg-fehler {
  padding: var(--sp-5);
  background: var(--err-soft);
  border: 1px solid color-mix(in oklch, var(--err) 25%, var(--line));
  border-radius: var(--radius-lg);
  color: var(--err);
  font-size: var(--fs-sm);
  display: flex; align-items: center; justify-content: space-between;
  gap: var(--sp-3);
}
.ldg-dialog-text { margin: 0; font-size: var(--fs); color: var(--text); line-height: 1.55; }
</style>
