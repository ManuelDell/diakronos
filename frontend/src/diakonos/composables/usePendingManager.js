import { ref, computed } from "vue"

const _pending = ref([])

export function usePendingManager() {
  const count = computed(() => _pending.value.length)

  function add(id, calendarName, title) {
    if (!_pending.value.find(e => e.id === id)) {
      _pending.value = [..._pending.value, { id, calendarName, title: title || "Termin" }]
    }
  }

  function remove(id) {
    _pending.value = _pending.value.filter(e => e.id !== id)
  }

  function clear() {
    _pending.value = []
  }

  function getAll() {
    return [..._pending.value]
  }

  function grouped() {
    const map = {}
    for (const e of _pending.value) {
      if (!map[e.calendarName]) map[e.calendarName] = []
      map[e.calendarName].push({ id: e.id, title: e.title })
    }
    return map
  }

  return { pending: _pending, count, add, remove, clear, getAll, grouped }
}
