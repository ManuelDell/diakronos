import { ref, onMounted, onUnmounted } from 'vue'
import { apiGet, apiCall } from './useApi.js'

const unreadCount = ref(0)
let intervalId = null
let initialized = false

export function useNotifications() {
  async function fetchUnread() {
    try {
      const res = await apiGet('diakronos.diakonos.api.audit.get_unread_notifications')
      unreadCount.value = res?.count ?? 0
    } catch (e) {
      console.error('[Notifications] fetch error:', e)
    }
  }

  async function markAsRead() {
    try {
      await apiCall('diakronos.diakonos.api.audit.mark_notifications_read')
      unreadCount.value = 0
    } catch (e) {
      console.error('[Notifications] mark read error:', e)
    }
  }

  function startPolling() {
    if (initialized) return
    initialized = true
    fetchUnread()
    intervalId = setInterval(fetchUnread, 60000)
  }

  function stopPolling() {
    if (intervalId) {
      clearInterval(intervalId)
      intervalId = null
    }
    initialized = false
  }

  onMounted(startPolling)
  onUnmounted(stopPolling)

  return { unreadCount, fetchUnread, markAsRead }
}
