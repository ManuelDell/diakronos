import { ref, computed, watch } from 'vue'
import { apiCall } from './useApi.js'

const mitglieder = ref([])
const loading = ref(false)
const error = ref(null)
const hasMore = ref(true)

const searchQuery = ref('')
const statusFilter = ref('')
const sortBy = ref('full_name')
const sortOrder = ref('asc')

const limit = 30
let currentStart = 0

async function loadMitglieder({ start = 0, append = false } = {}) {
    if (loading.value) return

    loading.value = true
    error.value = null

    try {
        const data = await apiCall('diakronos.diakonos.api.mitglieder.get_mitglieder_liste', {
            start,
            limit,
            suche: searchQuery.value || undefined,
            status: statusFilter.value || undefined,
            sort_by: sortBy.value,
            sort_order: sortOrder.value,
        })

        const payload = data || {}
        const rows = payload.data || []

        if (append) {
            mitglieder.value.push(...rows)
        } else {
            mitglieder.value = rows
        }

        currentStart = start + rows.length
        hasMore.value = rows.length === limit
    } catch (err) {
        error.value = err?.message || 'Fehler beim Laden der Mitglieder'
        console.error('loadMitglieder error:', err)
    } finally {
        loading.value = false
    }
}

function reload() {
    currentStart = 0
    hasMore.value = true
    return loadMitglieder({ start: 0, append: false })
}

function loadMore() {
    if (!hasMore.value || loading.value) return
    return loadMitglieder({ start: currentStart, append: true })
}

// Auto-reload when filters or sorting change
watch([searchQuery, statusFilter, sortBy, sortOrder], () => {
    reload()
}, { flush: 'post' })

export function useMitglieder() {
    return {
        mitglieder: computed(() => mitglieder.value),
        loading: computed(() => loading.value),
        error: computed(() => error.value),
        hasMore: computed(() => hasMore.value),
        searchQuery,
        statusFilter,
        sortBy,
        sortOrder,
        reload,
        loadMore,
    }
}
