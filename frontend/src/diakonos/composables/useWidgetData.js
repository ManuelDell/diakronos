import { ref, onMounted, onUnmounted } from 'vue'

const API_BASE = '/api/method/diakronos.diakonos.api.dashboard.get_widget_data'

export function useWidgetData(widgetId, refreshInterval = 0) {
  const data = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const lastUpdated = ref(null)
  let timer = null

  async function refresh() {
    if (!widgetId) return
    loading.value = true
    error.value = null
    try {
      const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
      const res = await fetch(API_BASE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
        body: JSON.stringify({ widget_id: widgetId }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      const msg = json.message
      data.value = msg?.data ?? null
      if (msg?.error) error.value = msg.error
      lastUpdated.value = Date.now()
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  onMounted(() => {
    refresh()
    if (refreshInterval > 0) {
      timer = setInterval(refresh, refreshInterval * 1000)
    }
  })

  onUnmounted(() => {
    if (timer) clearInterval(timer)
  })

  return { data, loading, error, lastUpdated, refresh }
}
