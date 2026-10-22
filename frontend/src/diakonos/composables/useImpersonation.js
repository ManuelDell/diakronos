import { ref, computed } from 'vue'

const STORAGE_KEY = 'dk-impersonation'
const TIMEOUT_MS = 30 * 60 * 1000

function loadState() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY)
        if (!raw) return null
        const data = JSON.parse(raw)
        if (Date.now() > data.expires) {
            localStorage.removeItem(STORAGE_KEY)
            return null
        }
        return data
    } catch { return null }
}

const _state = ref(loadState())

export function useImpersonation() {
    const isActive = computed(() => _state.value !== null)
    const mitglied = computed(() => _state.value?.mitglied || null)
    const fullName = computed(() => _state.value?.fullName || '')
    const expiresAt = computed(() => _state.value?.expires || null)

    function start(mitgliedName, name) {
        const data = { mitglied: mitgliedName, fullName: name, expires: Date.now() + TIMEOUT_MS }
        localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
        _state.value = data
    }

    function stop() {
        localStorage.removeItem(STORAGE_KEY)
        _state.value = null
    }

    function checkExpiry() {
        if (_state.value && Date.now() > _state.value.expires) stop()
    }

    return { isActive, mitglied, fullName, expiresAt, start, stop, checkExpiry }
}
