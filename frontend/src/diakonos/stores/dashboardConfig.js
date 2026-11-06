import { apiAntwortPruefen } from '../composables/useApi.js'
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { mitBasis } from '../../shared/basis.js'
// UX2g/UX2d3c: EINE Quelle fuer angezeigte Fehlertexte (kein „HTTP 500").
import { aktionsfehler } from '../../shared/fehlertexte.js'

// WEB-5b: der Praefix kommt vom Server (DIAKRONOS_BASE_PATH), nicht aus dem Build.
const API = mitBasis('/api/method/diakronos.diakonos.api.dashboard')

async function apiFetch(method, body = {}) {
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
  const res = await fetch(`${API}.${method}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
    body: JSON.stringify(body),
  })
  const json = await apiAntwortPruefen(res)
  return json.message
}

export const useDashboardConfig = defineStore('dashboardConfig', () => {
  const layout = ref([])         // Array<{ widget_id, label, category, widget_type, api_method, grid_size, position, visible, collapsed, ... }>
  const isEditing = ref(false)
  const loading = ref(false)
  // UX2d3c: Ein gescheitertes Laden blieb vorher nur in der Konsole
  // (`console.warn`) — die Startseite zeigte dann einen LEEREN Bildschirm, als
  // gäbe es keine Kacheln. `fehler` ist `null` oder der Klartext aus dem
  // Katalog (`aktionsfehler('laden', e)`).
  const fehler = ref(null)
  const lastSyncedAt = ref(null)
  let saveTimer = null

  const visibleWidgets = computed(() =>
    layout.value
      .filter(w => w.visible)
      .slice()
      .sort((a, b) => a.position - b.position)
  )

  const allWidgets = computed(() =>
    layout.value.slice().sort((a, b) => a.position - b.position)
  )

  async function loadConfig() {
    loading.value = true
    fehler.value = null
    try {
      const data = await apiFetch('get_user_config')
      layout.value = Array.isArray(data) ? data : []
      lastSyncedAt.value = Date.now()
    } catch (e) {
      console.warn('[DashboardConfig] Laden fehlgeschlagen:', e)
      fehler.value = aktionsfehler('laden', e)
    } finally {
      loading.value = false
    }
  }

  function scheduleSave() {
    clearTimeout(saveTimer)
    saveTimer = setTimeout(() => saveConfig(), 2000)
  }

  async function saveConfig() {
    try {
      await apiFetch('set_user_config', {
        layout_json: layout.value.map(w => ({
          widget_id: w.widget_id,
          position:  w.position,
          visible:   w.visible,
          size:      w.grid_size,
          collapsed: w.collapsed || false,
        }))
      })
      lastSyncedAt.value = Date.now()
    } catch (e) {
      console.warn('[DashboardConfig] Speichern fehlgeschlagen:', e)
    }
  }

  function moveWidget(fromIndex, toIndex) {
    const sorted = visibleWidgets.value
    const [moved] = sorted.splice(fromIndex, 1)
    sorted.splice(toIndex, 0, moved)
    sorted.forEach((w, i) => {
      const target = layout.value.find(l => l.widget_id === w.widget_id)
      if (target) target.position = i
    })
    scheduleSave()
  }

  function toggleWidget(widgetId) {
    const widget = layout.value.find(w => w.widget_id === widgetId)
    if (widget) {
      widget.visible = !widget.visible
      scheduleSave()
    }
  }

  async function resetToDefaults() {
    try {
      await apiFetch('reset_user_config')
      await loadConfig()
    } catch (e) {
      console.warn('[DashboardConfig] Reset fehlgeschlagen:', e)
    }
  }

  return {
    layout, isEditing, loading, fehler, lastSyncedAt,
    visibleWidgets, allWidgets,
    loadConfig, saveConfig, scheduleSave, moveWidget, toggleWidget, resetToDefaults,
  }
})
