/**
 * Benachrichtigungen (OP-HANDY-6).
 *
 * Der Zaehler kam NIE an: `get_unread_notifications` liefert `unread_count`,
 * gelesen wurde `count` — die Glocke zeigte deshalb immer nichts an. Ausserdem
 * markierte ein Klick auf die Glocke ALLES als gelesen, ohne dass eine Liste
 * zu sehen war: die Benachrichtigungen verschwanden ungesehen.
 *
 * Jetzt: der Klick oeffnet die Liste (`get_my_notifications`); erst danach
 * werden die Eintraege als gelesen markiert. Der Zaehler liest `unread_count`.
 */

import { ref, onMounted, onUnmounted } from 'vue'
import { apiGet, apiCall } from './useApi.js'

const unreadCount = ref(0)
// Liste der zuletzt geladenen Benachrichtigungen (rohe API-Zeilen).
const notifications = ref([])
const laden = ref(false)
const fehler = ref('')
let intervalId = null
let initialized = false
let listenAnfrage = 0

const GET_UNREAD = 'diakronos.diakonos.api.audit.get_unread_notifications'
const GET_LIST = 'diakronos.diakonos.api.audit.get_my_notifications'
const MARK_READ = 'diakronos.diakonos.api.audit.mark_notifications_read'

export function useNotifications() {
  async function fetchUnread() {
    try {
      const res = await apiGet(GET_UNREAD)
      // Vertrag der API: { success, unread_count }. Vorher stand hier `count`
      // und die Glocke blieb dauerhaft leer.
      unreadCount.value = res?.unread_count ?? 0
    } catch (e) {
      console.error('[Notifications] fetch error:', e)
    }
  }

  /** Liste laden. `still` = Hintergrund-Aktualisierung ohne Ladeanzeige. */
  async function ladeListe({ still = false } = {}) {
    const anfrage = ++listenAnfrage
    laden.value = !still
    fehler.value = ''
    try {
      const res = await apiGet(GET_LIST, { limit: 30 })
      if (anfrage !== listenAnfrage) return null
      notifications.value = Array.isArray(res?.data) ? res.data : []
      return notifications.value
    } catch (e) {
      if (anfrage !== listenAnfrage) return null
      fehler.value = 'Benachrichtigungen konnten nicht geladen werden.'
      console.error('[Notifications] list error:', e)
      return null
    } finally {
      if (anfrage === listenAnfrage) laden.value = false
    }
  }

  /** Erst nach dem Anzeigen der Liste aufrufen — nie ungesehen alles loeschen. */
  async function markAsRead(eintraege = notifications.value) {
    try {
      const angezeigt = eintraege.filter(n => !n.read).map(n => n.name)
      if (!angezeigt.length) return
      await apiCall(MARK_READ, { names: angezeigt })
      const gelesen = new Set(angezeigt)
      notifications.value = notifications.value.map(n => gelesen.has(n.name) ? { ...n, read: 1 } : n)
      await fetchUnread()
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

  return {
    unreadCount, notifications, laden, fehler,
    fetchUnread, ladeListe, markAsRead,
  }
}
