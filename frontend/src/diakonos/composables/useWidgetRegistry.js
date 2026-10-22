import { defineAsyncComponent } from 'vue'

const WIDGETS_DIR = '../components/widgets'

const registry = {
  'greeting':              defineAsyncComponent(() => import('../components/widgets/GreetingWidget.vue')),
  'quick-links':           defineAsyncComponent(() => import('../components/widgets/QuickLinksWidget.vue')),
  'upcoming-events':       defineAsyncComponent(() => import('../components/widgets/UpcomingEventsWidget.vue')),
  'my-services':           defineAsyncComponent(() => import('../components/widgets/MyServicesWidget.vue')),
  'announcements':         defineAsyncComponent(() => import('../components/widgets/AnnouncementsWidget.vue')),
  'wiki-recent':           defineAsyncComponent(() => import('../components/widgets/WikiRecentWidget.vue')),
  'mini-calendar':         defineAsyncComponent(() => import('../components/widgets/MiniCalendarWidget.vue')),
  'my-bookings':           defineAsyncComponent(() => import('../components/widgets/MyBookingsWidget.vue')),
  'pending-registrations': defineAsyncComponent(() => import('../components/widgets/PendingRegistrationsWidget.vue')),
  'manage-registrations':  defineAsyncComponent(() => import('../components/widgets/ManageRegistrationsWidget.vue')),
  'dsgvo-compliance':      defineAsyncComponent(() => import('../components/widgets/DsgvoComplianceWidget.vue')),
  'member-stats':          defineAsyncComponent(() => import('../components/widgets/MemberStatsWidget.vue')),
  'open-signups':          defineAsyncComponent(() => import('../components/widgets/OpenSignupsWidget.vue')),
}

export function useWidgetRegistry() {
  function getComponent(widgetId) {
    return registry[widgetId] || null
  }

  function isRegistered(widgetId) {
    return widgetId in registry
  }

  return { getComponent, isRegistered }
}
