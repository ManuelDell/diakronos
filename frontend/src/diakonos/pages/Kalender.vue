<template>
  <div class="kronos-page-content">
    <KronosTopbar
      :dateTitle="dateTitle"
      :currentView="currentView"
      :viewMode="store.viewMode.value"
      @prev="calendarRef?.prev()"
      @next="calendarRef?.next()"
      @today="calendarRef?.today()"
      @viewChange="onViewChange"
      @resourceToggle="onResourceToggle"
      @viewModeChange="onViewModeChange"
      @sidebarToggle="sidebarVisible = !sidebarVisible"
      @searchOpen="searchOpen = true"
    />
    <div class="kronos-calendar-wrap">
      <KronosCalendar
        ref="calendarRef"
        :selectedCalendars="store.selectedCalendars.value"
        :viewMode="store.viewMode.value"
        @eventClick="onEventClick"
        @dateClick="onDateClick"
        @select="onSelect"
        @datesSet="onDatesSet"
      />
    </div>

    <!-- Alle Modals -->
    <KronosEventCreate
      v-model:show="showCreate"
      :initialData="createInitialData"
      @created="onEventCreated"
    />
    <KronosEventEdit
      v-model:show="showEdit"
      :event="editEvent"
      @updated="onEventUpdated"
      @deleted="onEventDeleted"
    />
    <KronosEventView
      v-model:show="showView"
      :event="viewEvent"
    />
    <KronosDayEventsDialog
      v-model:show="showDayEvents"
      :dateStr="dayEventsDate"
      :calendarRef="calendarRef"
      :selectedCalendars="store.selectedCalendars.value"
      @eventClick="onDayEventClick"
    />
    <KronosSeriesDialog ref="seriesDialogRef" />

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useKronosStore } from '../composables/useKronosStore.js'
import KronosTopbar from '../components/kronos/KronosTopbar.vue'
import KronosCalendar from '../components/kronos/KronosCalendar.vue'
import KronosEventCreate from '../components/kronos/KronosEventCreate.vue'
import KronosEventEdit from '../components/kronos/KronosEventEdit.vue'
import KronosEventView from '../components/kronos/KronosEventView.vue'
import KronosDayEventsDialog from '../components/kronos/KronosDayEventsDialog.vue'
import KronosSeriesDialog from '../components/kronos/KronosSeriesDialog.vue'

const store = useKronosStore()
const calendarRef = ref(null)
const seriesDialogRef = ref(null)

// State
const dateTitle = ref('')
const currentView = ref('dayGridMonth')
const sidebarVisible = ref(true)
const searchOpen = ref(false)

// Modal states
const showCreate = ref(false)
const createInitialData = ref({})
const showEdit = ref(false)
const editEvent = ref(null)
const showView = ref(false)
const viewEvent = ref(null)
const showDayEvents = ref(false)
const dayEventsDate = ref('')

// Calendar events
function onDatesSet(info) {
  dateTitle.value = info.view?.title || ''
  const start = info.start
  if (start) {
    store.setCurrentMonth(start)
  }
}

function onEventClick(event) {
  const props = event.extendedProps || {}
  if (store.isViewMode.value) {
    viewEvent.value = props
    showView.value = true
  } else {
    if (props.series_id) {
      seriesDialogRef.value?.showEditOptions(props).then(action => {
        if (action === 'edit') {
          editEvent.value = { ...props, series_id: '' }
          showEdit.value = true
        }
      })
    } else {
      editEvent.value = props
      showEdit.value = true
    }
  }
}

function onDateClick(info) {
  if (store.isViewMode.value) {
    dayEventsDate.value = info.dateStr
    showDayEvents.value = true
  } else {
    const now = new Date()
    const h = String(now.getHours()).padStart(2,'0')
    const m = String(Math.round(now.getMinutes()/5)*5 % 60).padStart(2,'0')
    createInitialData.value = {
      element_start: `${info.dateStr}T${h}:${m}`,
      element_end: `${info.dateStr}T${String((now.getHours()+1)%24).padStart(2,'0')}:${m}`
    }
    showCreate.value = true
  }
}

function onSelect(info) {
  createInitialData.value = {
    element_start: info.startStr,
    element_end: info.endStr
  }
  showCreate.value = true
}

function onCalendarsChange(calendars) {
  store.setSelectedCalendars(calendars)
}

function onViewChange(viewName) {
  currentView.value = viewName
  calendarRef.value?.changeView(viewName)
}

function onResourceToggle() {
  const RESOURCE_VIEW_MAP = {
    'dayGridMonth': 'resourceTimelineMonth',
    'timeGridWeek': 'resourceTimelineWeek',
    'timeGridDay':  'resourceTimelineDay',
    'listMonth':    'resourceTimelineWeek',
  }
  const RESOURCE_VIEWS = new Set(Object.values(RESOURCE_VIEW_MAP))
  const cur = currentView.value
  if (RESOURCE_VIEWS.has(cur)) {
    calendarRef.value?.changeView('dayGridMonth')
  } else {
    calendarRef.value?.changeView(RESOURCE_VIEW_MAP[cur] || 'resourceTimelineWeek')
  }
}

function onViewModeChange(mode) {
  store.setViewMode(mode === 'view')
  calendarRef.value?.refetchEvents()  // view_mode affects which statuses are shown
}

function onEventCreated() {
  showCreate.value = false
  calendarRef.value?.refetchEvents()
}

function onEventUpdated() {
  showEdit.value = false
  calendarRef.value?.refetchEvents()
}

function onEventDeleted() {
  showEdit.value = false
  calendarRef.value?.refetchEvents()
}

function onDayEventClick(eventData) {
  showDayEvents.value = false
  viewEvent.value = eventData
  showView.value = true
}
onMounted(() => {
  store.fetchAccessibleCalendars()
})

</script>

<style scoped>
.kronos-page-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}
@media (hover: none) and (pointer: coarse) {
  .kronos-page-content {
    padding-bottom: 80px;
  }
}
</style>
