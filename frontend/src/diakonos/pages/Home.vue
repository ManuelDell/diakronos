<template>
  <div class="dk-screen dk-screen-enter">

    <!-- Edit-Bar -->
    <div v-if="isEditing" class="dk-widget-edit-bar">
      <span class="dk-widget-edit-label">Dashboard bearbeiten</span>
      <div style="display:flex;gap:8px">
        <button class="dk-btn dk-btn-ghost dk-btn-sm" @click="resetLayout">
          Zurücksetzen
        </button>
        <button class="dk-btn dk-btn-primary dk-btn-sm" @click="store.isEditing = false">
          Fertig
        </button>
      </div>
    </div>

    <!-- Widget-Raster -->
    <WidgetGrid
      v-if="!store.loading"
      :widgets="store.visibleWidgets"
      :is-editing="isEditing"
      :badge-counts="badgeCounts"
      @hide-widget="store.toggleWidget"
      @reorder="onReorder"
      @collapse-widget="onCollapseChange"
    />

    <!-- Lade-Skeleton -->
    <div v-else class="dk-widget-grid-wrapper">
      <div v-for="i in 4" :key="i" class="dk-widget-card dk-widget-medium dk-widget-skeleton-card">
        <div class="dk-skeleton-line" style="width:40%;height:16px;margin-bottom:12px"></div>
        <div class="dk-skeleton-line" style="width:80%"></div>
        <div class="dk-skeleton-line" style="width:60%"></div>
      </div>
    </div>

    <!-- Ausgeblendete Widgets in Bearbeiten-Modus -->
    <div v-if="isEditing && hiddenWidgets.length" class="dk-widget-hidden-section">
      <p class="dk-widget-hidden-label">Ausgeblendete Karten</p>
      <div class="dk-widget-hidden-list">
        <div
          v-for="widget in hiddenWidgets"
          :key="widget.widget_id"
          class="dk-widget-hidden-item"
          @click="store.toggleWidget(widget.widget_id)"
        >
          <span>{{ widget.label }}</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </div>
      </div>
    </div>

    <!-- Bearbeiten-FAB -->
    <button
      v-if="!isEditing"
      class="dk-widget-edit-fab"
      title="Dashboard bearbeiten"
      @click="store.isEditing = true"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
    </button>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { useDashboardConfig } from '../stores/dashboardConfig'
import WidgetGrid from '../components/widgets/WidgetGrid.vue'

const pinia = createPinia()
setActivePinia(pinia)

const store = useDashboardConfig()
const isEditing = computed(() => store.isEditing)
const hiddenWidgets = computed(() => store.allWidgets.filter(w => !w.visible))
const badgeCounts = ref({})
let badgeTimer = null

onMounted(async () => {
  await store.loadConfig()
  loadBadgeCounts()
  badgeTimer = setInterval(loadBadgeCounts, 60_000)
})

onUnmounted(() => clearInterval(badgeTimer))

async function loadBadgeCounts() {
  try {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
    const res = await fetch('/api/method/diakronos.diakonos.api.dashboard.get_widget_badge_counts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
      body: JSON.stringify({}),
    })
    const json = await res.json()
    badgeCounts.value = json.message || {}
  } catch {}
}

function onReorder(reordered) {
  reordered.forEach(w => {
    const item = store.layout.find(l => l.widget_id === w.widget_id)
    if (item) item.position = w.position
  })
  store.scheduleSave()
}

function onCollapseChange(widgetId, collapsed) {
  const w = store.layout.find(l => l.widget_id === widgetId)
  if (w) {
    w.collapsed = collapsed
    store.scheduleSave()
  }
}

async function resetLayout() {
  await store.resetToDefaults()
}
</script>
