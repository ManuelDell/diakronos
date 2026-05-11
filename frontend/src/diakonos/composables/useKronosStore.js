import { ref, computed } from "vue"

const viewMode = ref("view")           // "view" | "edit"
const selectedCalendars = ref([])      // Array von Kalender-Namen
const userRoles = ref([])
const availableCalendars = ref([])     // Vollstaendige Kalender-Objekte
const currentMonth = ref(new Date())

export function useKronosStore() {
  const isViewMode = computed(() => viewMode.value === "view")
  const isEditMode = computed(() => viewMode.value === "edit")

  function setViewMode(val) {
    viewMode.value = val ? "view" : "edit"
  }

  function getViewMode() {
    return viewMode.value !== "edit"
  }

  function setSelectedCalendars(arr) {
    selectedCalendars.value = arr || []
  }

  function getSelectedCalendars() {
    return selectedCalendars.value
  }

  function setCurrentMonth(date) {
    currentMonth.value = date
  }

  async function fetchAccessibleCalendars() {
    try {
      const response = await fetch("/api/method/diakronos.kronos.api.calendar_get.get_accessible_calendars", {
        headers: { "Accept": "application/json" }
      })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const data = await response.json()
      const calendars = data.message
      if (Array.isArray(calendars)) {
        availableCalendars.value = calendars
        if (selectedCalendars.value.length === 0) {
          selectedCalendars.value = calendars.map(c => c.name)
        }
        return calendars
      }
      return []
    } catch (err) {
      console.error("useKronosStore: fetchAccessibleCalendars Fehler", err)
      return []
    }
  }

  function initFromDOM() {
    userRoles.value = JSON.parse(document.body.dataset?.userRoles || "[]")
    viewMode.value = document.body.dataset?.viewMode || "view"
  }

  return {
    viewMode,
    selectedCalendars,
    userRoles,
    availableCalendars,
    currentMonth,
    isViewMode,
    isEditMode,
    setViewMode,
    getViewMode,
    setSelectedCalendars,
    getSelectedCalendars,
    setCurrentMonth,
    fetchAccessibleCalendars,
    initFromDOM,
  }
}
