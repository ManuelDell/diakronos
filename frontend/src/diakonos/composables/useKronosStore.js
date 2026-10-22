import { apiAntwortPruefen } from './useApi.js'
import { ref, computed } from "vue"
import { useImpersonation } from './useImpersonation.js'

const viewMode = ref("view")
const userRoles = ref([])
const availableCalendars = ref([])
const currentMonth = ref(new Date())
const loading = ref(false)

// Init selectedCalendars from localStorage (only when not impersonating)
const _stored = localStorage.getItem('selected_calendars')
const selectedCalendars = ref(_stored ? JSON.parse(_stored) : [])

export function useKronosStore() {
  const imp = useImpersonation()
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
    if (!imp.isActive.value) {
      localStorage.setItem('selected_calendars', JSON.stringify(selectedCalendars.value))
    }
  }

  function getSelectedCalendars() {
    return selectedCalendars.value
  }

  function setCurrentMonth(date) {
    currentMonth.value = date
  }

  async function fetchAccessibleCalendars() {
    loading.value = true
    try {
      const body = imp.isActive.value ? { __impersonated_as: imp.mitglied.value } : {}
      const csrf_token = window.__DIakonosBOOT?.csrf_token || ''
      const response = await fetch("/api/method/diakronos.kronos.api.permissions.get_accessible_calendars", {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Frappe-CSRF-Token': csrf_token,
          'Accept': 'application/json',
        },
        body: JSON.stringify(body),
      })
      const data = await apiAntwortPruefen(response)
      const calendars = data.message
      if (Array.isArray(calendars)) {
        availableCalendars.value = calendars
        if (selectedCalendars.value.length === 0 || imp.isActive.value) {
          setSelectedCalendars(calendars.map(c => c.name))
        }
        return calendars
      }
      return []
    } catch (err) {
      console.error("useKronosStore: fetchAccessibleCalendars Fehler", err)
      return []
    } finally {
      loading.value = false
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
    loading,
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
