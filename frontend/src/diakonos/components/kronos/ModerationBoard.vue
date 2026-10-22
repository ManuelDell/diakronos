<template>
  <div class="dk-mboard">
    <!-- Konflikte Column -->
    <div class="dk-mboard-col">
      <div class="dk-mboard-col-header dk-mboard-col-header--konflikte">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        <span class="dk-mboard-col-title">Konflikte</span>
        <span class="dk-mboard-count">{{ konflikte.length }}</span>
      </div>
      <div ref="sortKonflikte" class="dk-mboard-col-body">
        <div v-if="loading" class="dk-mboard-empty">Lade Termine …</div>
        <DkEmpty
          v-else-if="groupedKonflikte.length === 0"
          icon="✓"
          title="Keine Konflikte"
          text="Alle Terminvorschläge passen ohne Überschneidung."
        />
        <ModerationCard
          v-for="item in groupedKonflikte"
          :key="item.id"
          :item="item"
          column="konflikte"
          :notification="boardData.notifications?.[item.id]"
          @click="onCardClick(item, 'konflikte')"
          @resolve-conflict="onResolveConflict"
        />
      </div>
    </div>

    <!-- Vorschläge Column -->
    <div class="dk-mboard-col">
      <div class="dk-mboard-col-header dk-mboard-col-header--vorschlaege">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        <span class="dk-mboard-col-title">Vorschläge</span>
        <span class="dk-mboard-count">{{ vorschlaege.length }}</span>
      </div>
      <div ref="sortVorschlaege" class="dk-mboard-col-body">
        <div v-if="loading" class="dk-mboard-empty">Lade Termine …</div>
        <DkEmpty
          v-else-if="groupedVorschlaege.length === 0"
          icon="🕒"
          title="Keine Vorschläge"
          text="Es warten gerade keine neuen Terminvorschläge auf Freigabe."
        />
        <ModerationCard
          v-for="item in groupedVorschlaege"
          :key="item.id"
          :item="item"
          column="vorschlaege"
          :notification="boardData.notifications?.[item.id]"
          @click="onCardClick(item, 'vorschlaege')"
        />
      </div>
    </div>

    <!-- Freigeben Column -->
    <div class="dk-mboard-col">
      <div class="dk-mboard-col-header dk-mboard-col-header--festlegen">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5l10-10"/></svg>
        <span class="dk-mboard-col-title">Freigeben</span>
        <span class="dk-mboard-count">{{ stagingIds.length }}</span>
      </div>
      <div v-if="stagingGroups.length === 0" class="dk-mboard-drop-hint">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/></svg>
        Termine hierher ziehen
      </div>
      <div ref="sortFestlegen" class="dk-mboard-col-body">
        <ModerationCard
          v-for="item in stagingGroups"
          :key="item.id"
          :item="item"
          column="festlegen"
          :notification="boardData.notifications?.[item.id]"
          @click="onCardClick(item, 'festlegen')"
          @remove="onRemoveFromStaging"
        />
      </div>
    </div>

    <!-- Abgelehnt (Moderations-Historie, P1-5b W-1) -->
    <div v-if="abgelehnt.length" class="dk-mboard-col">
      <div class="dk-mboard-col-header dk-mboard-col-header--abgelehnt">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
        <span class="dk-mboard-col-title">Abgelehnt</span>
        <span class="dk-mboard-count">{{ abgelehnt.length }}</span>
      </div>
      <div class="dk-mboard-col-body">
        <ModerationCard
          v-for="item in abgelehnt"
          :key="item.id"
          :item="item"
          column="abgelehnt"
          @click="onCardClick(item, 'abgelehnt')"
        />
      </div>
    </div>

    <!-- Modals (delegated) -->
    <ModerationModals
      ref="modals"
      :ressources="ressources"
      @resolved="reloadBoard"
      @series-updated="reloadBoard"
      @series-deleted="reloadBoard"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import Sortable from 'sortablejs'
import ModerationCard from './ModerationCard.vue'
import ModerationModals from './ModerationModals.vue'
import DkEmpty from '../ui/DkEmpty.vue'
import {
  getBoardData,
  saveStagingState,
  getRessources,
} from '../../api/kanbanApi.js'

// ── State ────────────────────────────────────────────────────────────────────
const boardData = ref({ vorschlaege: [], konflikte: [], staging: [], notifications: {}, abgelehnt: [] })
const stagingIds = ref([])
const ressources = ref([])
const loading = ref(true)

// ── Template refs ────────────────────────────────────────────────────────────
const sortVorschlaege = ref(null)
const sortKonflikte = ref(null)
const sortFestlegen = ref(null)
const modals = ref(null)

// ── Sortable instances ──────────────────────────────────────────────────────
let sortableV = null
let sortableF = null

// ── Serie Grouping (matches kanban.bundle.js groupItems) ─────────────────────
function groupItems(events) {
  const seriesMap = {}
  const result = []

  events.forEach(ev => {
    if (ev.series_id) {
      if (!seriesMap[ev.series_id]) seriesMap[ev.series_id] = []
      seriesMap[ev.series_id].push(ev)
    } else {
      result.push(ev)
    }
  })

  Object.entries(seriesMap).forEach(([sid, evts]) => {
    const sorted = [...evts].sort((a, b) => (a.start || '').localeCompare(b.start || ''))
    const first = sorted[0]
    const last = sorted[sorted.length - 1]
    const hasKonflikt = evts.some(e => e.status === 'Konflikt')
    result.push({
      type: 'serie',
      id: sid,
      series_id: sid,
      title: first.title,
      count: evts.length,
      event_ids: evts.map(e => e.id),
      events: evts,
      first_start: first.start,
      last_start: last.start,
      all_day: first.all_day,
      calendar: first.calendar,
      calendar_title: first.calendar_title,
      calendar_color: first.calendar_color,
      has_konflikt: hasKonflikt,
      konflikt_events: evts.filter(e => e.status === 'Konflikt'),
      status: hasKonflikt ? 'Konflikt' : 'Vorschlag',
    })
  })

  return result
}

// ── Staging groups (matches kanban.bundle.js buildStagingGroups) ─────────────
const stagingGroups = computed(() => {
  const seriesMap = {}
  boardData.value.staging.forEach(ev => {
    if (ev.series_id) {
      if (!seriesMap[ev.series_id]) seriesMap[ev.series_id] = []
      seriesMap[ev.series_id].push(ev)
    }
  })

  const groups = []
  const processed = new Set()

  for (const id of stagingIds.value) {
    const ev = boardData.value.staging.find(e => e.id === id)
    if (!ev) continue

    if (ev.series_id) {
      if (processed.has(ev.series_id)) continue
      processed.add(ev.series_id)
      const evts = seriesMap[ev.series_id] || []
      const sorted = [...evts].sort((a, b) => (a.start || '').localeCompare(b.start || ''))
      groups.push({
        type: 'serie',
        id: ev.series_id,
        series_id: ev.series_id,
        title: ev.title,
        count: evts.length,
        event_ids: evts.map(e => e.id),
        first_start: sorted[0]?.start,
        last_start: sorted[sorted.length - 1]?.start,
        all_day: ev.all_day,
        calendar_title: ev.calendar_title,
        calendar_color: ev.calendar_color,
        _origin: ev._origin || 'vorschlaege',
      })
    } else {
      if (processed.has(ev.id)) continue
      processed.add(ev.id)
      groups.push(ev)
    }
  }
  return groups
})

// ── Grouped columns ──────────────────────────────────────────────────────────
const groupedVorschlaege = computed(() => groupItems(boardData.value.vorschlaege))
const groupedKonflikte = computed(() => groupItems(boardData.value.konflikte))
const vorschlaege = computed(() => boardData.value.vorschlaege)
const konflikte = computed(() => boardData.value.konflikte)
// P1-5b (W-1): Moderations-Historie der abgelehnten Termine.
const abgelehnt = computed(() => boardData.value.abgelehnt || [])

// ── Data loading ─────────────────────────────────────────────────────────────
async function loadBoard() {
  loading.value = true
  try {
    const data = await getBoardData()
    boardData.value = data || { vorschlaege: [], konflikte: [], staging: [], notifications: {}, abgelehnt: [] }
    // Merge stagingIds with server data
    const serverIds = data.staging?.map(e => e.id) || []
    const validIds = stagingIds.value.filter(id => serverIds.includes(id))
    serverIds.forEach(id => { if (!validIds.includes(id)) validIds.push(id) })
    stagingIds.value = validIds
  } catch (e) {
    console.error('Board-Daten konnten nicht geladen werden', e)
    boardData.value = { vorschlaege: [], konflikte: [], staging: [], notifications: {}, abgelehnt: [] }
  } finally {
    loading.value = false
  }
}

async function loadRessources() {
  try {
    const r = await getRessources()
    // OP-EVENT-12: `get_ressources` liefert `{ resources: [...], types: [...] }`
    // (so liest es auch KronosCalendar). Die frühere Annahme eines flachen
    // Arrays ergab `(r || []).map(...)` auf einem Objekt -> immer leere Liste,
    // deshalb blieb das Feld „Raum“ im Moderationsdialog leer.
    const liste = Array.isArray(r) ? r : (r?.resources || [])
    ressources.value = (liste || []).map(x => ({ id: x.id, title: x.title }))
  } catch {
    ressources.value = []
  }
}

async function reloadBoard() {
  await loadBoard()
}

// ── Debounced save (500ms) ──────────────────────────────────────────────────
let _saveTimer = null
function debouncedSaveState() {
  clearTimeout(_saveTimer)
  _saveTimer = setTimeout(() => {
    saveStagingState(stagingIds.value).catch(e => console.warn('State save failed', e))
  }, 500)
}

// ── Drag & Drop ──────────────────────────────────────────────────────────────
function initSortable() {
  if (sortVorschlaege.value) {
    sortableV = Sortable.create(sortVorschlaege.value, {
      group: { name: 'vorschlaege', pull: true, put: false },
      sort: false,
      animation: 150,
      ghostClass: 'dk-mboard-ghost',
      dragClass: 'dk-mboard-dragging',
    })
  }

  if (sortFestlegen.value) {
    sortableF = Sortable.create(sortFestlegen.value, {
      group: { name: 'festlegen', pull: false, put: ['vorschlaege'] },
      sort: true,
      animation: 150,
      ghostClass: 'dk-mboard-ghost',
      dragClass: 'dk-mboard-dragging',
      onAdd(evt) {
        const id = evt.item.dataset.id
        const type = evt.item.dataset.type || 'event'
        if (!id) return

        if (type === 'serie') {
          const seriesEvents = boardData.value.vorschlaege.filter(e => e.series_id === id)
          if (!seriesEvents.length) return
          boardData.value.vorschlaege = boardData.value.vorschlaege.filter(e => e.series_id !== id)
          seriesEvents.forEach(ev => {
            ev._origin = 'vorschlaege'
            boardData.value.staging.push(ev)
            if (!stagingIds.value.includes(ev.id)) stagingIds.value.push(ev.id)
          })
        } else {
          const ev = boardData.value.vorschlaege.find(e => e.id === id)
          if (!ev) return
          boardData.value.vorschlaege = boardData.value.vorschlaege.filter(e => e.id !== id)
          ev._origin = 'vorschlaege'
          boardData.value.staging.push(ev)
          if (!stagingIds.value.includes(id)) stagingIds.value.push(id)
        }
        debouncedSaveState()
      },
    })
  }
}

function destroySortable() {
  sortableV?.destroy()
  sortableF?.destroy()
  sortableV = null
  sortableF = null
}

// ── Card interactions ────────────────────────────────────────────────────────
function onCardClick(item, column) {
  // P1-5b (W-1): abgelehnte Termine sind erledigt — nur noch ansehen.
  if (column === 'abgelehnt') {
    modals.value?.openAbgelehntModal(item)
    return
  }
  if (item.type === 'serie') {
    if (column === 'konflikte') {
      modals.value?.openSeriesKonfliktModal(item)
    } else {
      modals.value?.openSeriesModal(item)
    }
  } else {
    if (column === 'konflikte') {
      modals.value?.openConflictModal(item)
    } else {
      modals.value?.openEditModal(item)
    }
  }
}

function onResolveConflict(ev) {
  modals.value?.openConflictModal(ev)
}

function onRemoveFromStaging(item) {
  if (item.type === 'serie') {
    const seriesEvents = boardData.value.staging.filter(e => e.series_id === item.series_id)
    const seriesEventIds = new Set(seriesEvents.map(e => e.id))
    stagingIds.value = stagingIds.value.filter(id => !seriesEventIds.has(id))
    boardData.value.staging = boardData.value.staging.filter(e => e.series_id !== item.series_id)
    seriesEvents.forEach(ev => {
      if (ev.status === 'Konflikt') boardData.value.konflikte.push(ev)
      else boardData.value.vorschlaege.push(ev)
    })
  } else {
    stagingIds.value = stagingIds.value.filter(i => i !== item.id)
    const ev = boardData.value.staging.find(e => e.id === item.id)
    if (ev) {
      boardData.value.staging = boardData.value.staging.filter(e => e.id !== item.id)
      if (ev.status === 'Konflikt') boardData.value.konflikte.push(ev)
      else boardData.value.vorschlaege.push(ev)
    }
  }
  debouncedSaveState()
}

// ── Lifecycle ────────────────────────────────────────────────────────────────
onMounted(async () => {
  await Promise.all([loadBoard(), loadRessources()])
  await nextTick()
  initSortable()
})

onUnmounted(() => {
  destroySortable()
  clearTimeout(_saveTimer)
})

// ── Expose for parent (finalize) ─────────────────────────────────────────────
defineExpose({
  getStagingIds: () => stagingIds.value,
  reloadBoard,
})
</script>

<style scoped>
.dk-mboard {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
  /* BF1-I: Der Seitenrahmen (.dk-screen) liefert die Aussenabstaende;
     das Board bringt nur noch den Abstand nach oben/unten mit. */
  padding: 0 0 20px;
}

.dk-mboard-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--dk-surface);
  border: 1px solid var(--dk-border);
  border-radius: 12px;
  overflow: hidden;
}

.dk-mboard-col-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--dk-border);
  font-size: 13px;
  font-weight: 600;
}
.dk-mboard-col-header--konflikte { color: var(--dk-danger); }
.dk-mboard-col-header--vorschlaege { color: var(--dk-warning); }
.dk-mboard-col-header--festlegen { color: var(--dk-success); }
/* P1-5b (W-1): Historie-Spalte — bewusst neutral/gedaempft, sie ist keine
   Arbeitsliste, sondern ein Nachschlage-Ort. */
.dk-mboard-col-header--abgelehnt { color: var(--dk-text-muted); }

.dk-mboard-col-title { flex: 1; }

.dk-mboard-count {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--dk-surface-2);
  color: var(--dk-text-muted);
}

.dk-mboard-col-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 80px;
}

.dk-mboard-empty {
  padding: 24px 12px;
  text-align: center;
  color: var(--dk-text-subtle);
  font-size: 13px;
}

.dk-mboard-drop-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px 16px;
  color: var(--dk-text-subtle);
  font-size: 13px;
  border: 2px dashed var(--dk-border);
  border-radius: 8px;
  margin: 8px;
}

/* Drag & Drop */
.dk-mboard-ghost {
  opacity: 0.4;
}
.dk-mboard-dragging {
  opacity: 0.9;
}

/* Mobile: single column, horizontal scroll */
@media (max-width: 768px) {
  .dk-mboard {
    flex-direction: column;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    -webkit-overflow-scrolling: touch;
    padding: 0 12px 12px;
    /* UXK-006: Nicht auf die Fensterhoehe quetschen — die Seite scrollt,
       die Karten behalten ihre natuerliche Hoehe. */
    flex: none;
    min-height: 0;
  }
  .dk-mboard-col {
    min-width: 85vw;
    scroll-snap-align: start;
    /* Kein dreifaches Fensterdrittel mehr, sondern natuerlicher Inhalt. */
    overflow: visible;
  }
  .dk-mboard-col-body {
    overflow-y: visible;
    flex: none;
  }
}
</style>
