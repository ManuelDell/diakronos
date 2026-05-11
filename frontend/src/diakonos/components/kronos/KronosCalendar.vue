<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as _EC from '@event-calendar/build'
import '@event-calendar/build/dist/event-calendar.min.css'
import { useEventsApi } from '../../composables/useEventsApi.js'
import KronosSeriesDialog from './KronosSeriesDialog.vue'

const EventCalendar = _EC.default?.create ? _EC.default : (_EC.create ? _EC : null)


const props = defineProps({
  selectedCalendars: { type: Array, default: () => [] },
  viewMode: { type: String, default: 'view' }
})

const emit = defineEmits([
  'eventClick',
  'dateClick',
  'select',
  'datesSet',
  'resourceViewChange'
])

const calendarEl = ref(null)
const seriesDialog = ref(null)
const calendar = ref(null)
const _resourcesLoaded = ref(false)
const _highlightEventId = ref(null)
const sessionAutoConvertSeries = ref(false)

const eventsApi = useEventsApi()

onMounted(() => {
  if (!calendarEl.value) {
    console.error('Calendar Element nicht gefunden')
    return
  }

  try {
    const isEditMode = props.viewMode === 'edit'

    calendar.value = EventCalendar.create(calendarEl.value, {
      view: 'dayGridMonth',
      locale: 'de',
      eventTimeFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
      headerToolbar: false,
      weekNumbers: true,
      dayMaxEvents: true,
      height: '100%',
      resourceAreaWidth: 200,
      editable: isEditMode,
      selectable: isEditMode,

      resources: [],
      resourceLabelContent: (info) => {
        if (info.resource.extendedProps?.isGroupHeader) {
          return { html: '<span class="ec-res-group-label">' + info.resource.title + '</span>' }
        }
        return { html: '<span class="ec-res-normal-label">' + info.resource.title + '</span>' }
      },
      resourceLabelDidMount: (info) => {
        if (info.resource.extendedProps?.isGroupHeader) {
          info.el.style.marginLeft = '6px'
        }
      },
      events: [],
      eventSources: [
        {
          events: function(fetchInfo, successCallback, failureCallback) {
            const startDate = fetchInfo.startStr ? fetchInfo.startStr.split('T')[0] : ''
            const endDate   = fetchInfo.endStr   ? fetchInfo.endStr.split('T')[0]   : ''
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || ''
            const activeCalendars = props.selectedCalendars

            fetch('/api/method/diakronos.kronos.api.calendar_get.get_calendar_events', {
              method: 'POST',
              headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Frappe-CSRF-Token': csrfToken
              },
              body: JSON.stringify({
                start_date: startDate,
                end_date: endDate,
                calendar_filter: JSON.stringify(activeCalendars),
                view_mode: props.viewMode
              })
            })
            .then(response => {
              if (!response.ok) return response.text().then(t => { throw new Error(t) })
              return response.json()
            })
            .then(result => {
              const events = result.message || []
              const processedEvents = events.map(ev => {
                if (ev.start && typeof ev.start === 'string' && ev.start.includes('T')) {
                  ev.allDay = false
                }
                if (ev.end && typeof ev.end === 'string' && ev.end.includes('T')) {
                  ev.allDay = false
                }
                return ev
              })
              successCallback(processedEvents)
            })
            .catch(err => {
              console.error('Events Fetch Fehler:', err)
              failureCallback(err)
            })
          }
        }
      ],

      dateClick: (info) => {
        emit('dateClick', info)
      },

      eventClick: (info) => {
        const isMobile = window.innerWidth <= 768
        const currentView = info.view.type

        if (isMobile && currentView === 'dayGridMonth') {
          calendar.value.setOption('view', 'timeGridDay')
          calendar.value.setOption('date', info.event.start)
          info.jsEvent.preventDefault()
          return
        }

        emit('eventClick', info.event)
        info.jsEvent.preventDefault()
      },

      eventDrop: async (info) => {
        const _dropRes = (info.event.getResources?.() || [])[0]
        if (_dropRes?.id?.startsWith('__grp_') || _dropRes?.extendedProps?.isGroupHeader) { info.revert(); return }
        const props_ev = info.event.extendedProps || {}
        if (props_ev.series_id) {
          if (!sessionAutoConvertSeries.value) {
            const result = await seriesDialog.value?.showDragConfirmation(info.event)
            if (!result?.confirmed) { info.revert(); return }
            if (result.rememberSession) sessionAutoConvertSeries.value = true
          }
          eventsApi.updateEvent(info.event, () => refetchEvents(), true)
        } else {
          eventsApi.updateEvent(info.event, () => refetchEvents(), false)
        }
      },

      eventResize: async (info) => {
        const props_ev = info.event.extendedProps || {}
        if (props_ev.series_id) {
          if (!sessionAutoConvertSeries.value) {
            const result = await seriesDialog.value?.showDragConfirmation(info.event)
            if (!result?.confirmed) { info.revert(); return }
            if (result.rememberSession) sessionAutoConvertSeries.value = true
          }
          eventsApi.updateEvent(info.event, () => refetchEvents(), true)
        } else {
          eventsApi.updateEvent(info.event, () => refetchEvents(), false)
        }
      },

      select: (info) => {
        if (info.resource?.id?.startsWith('__grp_') || info.resource?.extendedProps?.isGroupHeader) return
        emit('select', info)
      },

      datesSet: (info) => {
        emit('datesSet', info)
        const vt = info.view.type
        const isResourceView = vt === 'resourceTimelineDay'
          || vt === 'resourceTimelineWeek'
          || vt === 'resourceTimelineMonth'

        emit('resourceViewChange', isResourceView)

        if (isResourceView && !_resourcesLoaded.value) {
          _loadResources()
        }
      },

      eventClassNames: (info) => {
        const isMonthView = calendar.value?.getOption('view') === 'dayGridMonth'
        const isMobile   = window.innerWidth <= 430
        const isMultiDay = !info.event.allDay && info.event.end &&
          new Date(info.event.start).toDateString() !== new Date(info.event.end).toDateString()
        const useDot = !info.event.allDay && isMonthView && !isMobile && !isMultiDay
        const classes = useDot ? ['ec-event-dot-style'] : []
        if (_highlightEventId.value && info.event.id === _highlightEventId.value)
          classes.push('kronos-event-highlight')
        return classes
      },

      eventContent: (info) => {
        const event = info.event
        const isMonthView = calendar.value?.getOption('view') === 'dayGridMonth'
        const isMobile   = window.innerWidth <= 430
        const isMultiDay = !event.allDay && event.end &&
          new Date(event.start).toDateString() !== new Date(event.end).toDateString()
        const safe = s => (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

        if (!event.allDay && isMonthView && !isMobile && !isMultiDay) {
          const color = event.backgroundColor || 'var(--primary)'
          return { html:
            '<div class="ec-event-body ec-dot-body">' +
            '<span class="ec-dot" style="background:' + safe(color) + '"></span>' +
            '<h4 class="ec-event-title">' + safe(event.title) + '</h4>' +
            '</div>'
          }
        }

        const showTime = !event.allDay && !isMultiDay
        const timeHtml = showTime && info.timeText
          ? '<span class="ec-event-time">' + safe(info.timeText) + '</span>' : ''
        return { html:
          '<div class="ec-event-body">' + timeHtml + '<h4 class="ec-event-title">' + safe(event.title) + '</h4></div>'
        }
      }
    })

    // Mobile: Swipe-Navigation
    let _swipeStartX = 0
    calendarEl.value.addEventListener('touchstart', (e) => {
      _swipeStartX = e.touches[0].clientX
    }, { passive: true })
    calendarEl.value.addEventListener('touchend', (e) => {
      const delta = e.changedTouches[0].clientX - _swipeStartX
      const viewType = calendar.value.getOption('view')
      if (viewType === 'timeGridDay') {
        if (delta > 80) calendar.value.setOption('view', 'dayGridMonth')
      } else if (viewType === 'dayGridMonth') {
        if (delta < -80) calendar.value.next()
        else if (delta > 80) calendar.value.prev()
      }
    }, { passive: true })

  } catch (error) {
    console.error('Fehler beim Initialisieren:', error)
    console.error(' Stack:', error.stack)
  }
})

onBeforeUnmount(() => {
  if (calendar.value && typeof calendar.value.destroy === 'function') {
    calendar.value.destroy()
  }
})

watch(() => props.selectedCalendars, () => {
  refetchEvents()
}, { deep: true })

watch(() => props.viewMode, (newVal) => {
  const isEditMode = newVal === 'edit'
  if (calendar.value) {
    calendar.value.setOption('editable', isEditMode)
    calendar.value.setOption('selectable', isEditMode)
  }
  refetchEvents()
})

async function _loadResources() {
  _resourcesLoaded.value = true
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
  try {
    const res = await fetch('/api/method/diakronos.kronos.api.ressource_api.get_ressources', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
      body: JSON.stringify({})
    })
    const data = await res.json()
    const msg = data.message
    const resList = Array.isArray(msg) ? msg : (msg?.resources || [])
    const typeOrder = Array.isArray(msg) ? [] : (msg?.types || [])
    const rawList = resList.map(r => ({
      id: r.id,
      title: r.title,
      extendedProps: { typ: r.typ || 'Sonstiges' }
    }))

    const grouped = {}
    for (const r of rawList) {
      const t = r.extendedProps.typ
      if (!grouped[t]) grouped[t] = []
      grouped[t].push(r)
    }

    const allTypes = [
      ...typeOrder,
      ...Object.keys(grouped).filter(t => !typeOrder.includes(t) && t !== 'Sonstiges')
    ]
    if (grouped['Sonstiges']) allTypes.push('Sonstiges')

    const resources = []
    for (const typ of allTypes) {
      if (grouped[typ]?.length) {
        resources.push({
          id: '__grp_' + typ,
          title: typ,
          extendedProps: { isGroupHeader: true },
          children: grouped[typ]
        })
      }
    }
    resources.push({ id: '__unassigned__', title: 'Nicht zugeordnet' })

    if (calendar.value) {
      calendar.value.setOption('resources', resources)
      calendar.value.refetchResources()
    }

  } catch (e) {
    _resourcesLoaded.value = false
    console.warn('Ressourcen konnten nicht geladen werden:', e)
  }
}

function changeView(viewName, date) {
  if (!calendar.value) return
  calendar.value.setOption('view', viewName)
  if (date) calendar.value.setOption('date', date instanceof Date ? date : new Date(date))
}

function gotoDate(date) {
  if (!calendar.value) return
  calendar.value.setOption('date', date instanceof Date ? date : new Date(date))
}

function today() {
  if (!calendar.value) return
  calendar.value.setOption('date', new Date())
}

function refetchEvents() {
  if (calendar.value) calendar.value.refetchEvents()
}

defineExpose({ changeView, gotoDate, today })
</script>

<template>
  <div ref=calendarEl style=height:100%></div>
  <KronosSeriesDialog ref=seriesDialog />
</template>
