<script setup>
import { apiAntwortPruefen } from '../../composables/useApi.js'
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as _EC from '@event-calendar/build'
import '@event-calendar/build/dist/event-calendar.min.css'
import { useEventsApi } from '../../composables/useEventsApi.js'
import { useImpersonation } from '../../composables/useImpersonation.js'
import { showToast } from '../../composables/useToast.js'
import KronosSeriesDialog from './KronosSeriesDialog.vue'
// P3-4b/Restpunkt 1: Schriftfarbe je Terminkachel nach Helligkeit (AA).
import { kachelSchrift } from '../../../shared/kachelfarbe.mjs'
import { sichereFarbe } from '../../../shared/sichere-ausgabe.js'

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
  'resourceViewChange',
  'viewChange',
])

const calendarEl = ref(null)
const seriesDialog = ref(null)
const calendar = ref(null)

const _resourcesLoaded = ref(false)
const _highlightEventId = ref(null)
const sessionAutoConvertSeries = ref(false)
let _suppressClick = false  // true nach Swipe/Drag -> unterdrueckt eventClick/dateClick (Tap vs Swipe)
let _dayPushed = false   // History-Eintrag fuer Tagesansicht aktiv
let _popHandling = false
function _onPopState() {
  if (!_dayPushed) return
  _popHandling = true
  _dayPushed = false
  if (calendar.value && calendar.value.getOption('view') === 'timeGridDay') {
    calendar.value.setOption('view', 'dayGridMonth')   // Edge-/Browser-Back -> Monatsansicht
  }
  _popHandling = false
}

const eventsApi = useEventsApi()
const _imp = useImpersonation()

/**
 * P1-1b: Verschieben/Groessenaenderung an einem FESTGELEGTEN Termin wirkt fuer
 * Nicht-Moderatoren nicht sofort — die Aenderung wartet als offener Vorschlag.
 * Ohne diese Meldung sah es so aus, als sei der Termin "zurueckgesprungen".
 */
function meldeWartendeAenderung(ergebnis) {
  if (ergebnis?.wartet) {
    showToast(ergebnis.meldung || 'Änderung wartet auf Freigabe (Terminmoderation).', 'success')
  }
}

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
      // OP-ADMIN-17: Die Kalenderwoche beginnt am Montag (wie der Mini-Kalender
      // und wie in Deutschland ueblich). Vorher fing das Raster am Sonntag an.
      firstDay: 1,
      // UXK-R14 (P3-4b/Restpunkt 9): Am Handy ueberlagerte „W40“ die Tageszahl
      // (las sich „W4027“). Die Nummer wird jetzt immer gerendert und per CSS
      // unter 640 px ausgeblendet — ein matchMedia beim Aufbau griff beim
      // Drehen/Fenstergroesse nicht und liess die Ueberlappung stehen.
      weekNumbers: true,
      dayMaxEvents: true,
      // UXK-R13: englische Texte der Bibliothek übersetzen („all-day“, „+2 more“).
      allDayContent: { text: 'ganztägig' },
      moreLinkContent: (info) => `+${info.num} weitere`,
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
                view_mode: props.viewMode,
                ...(_imp.isActive.value ? { __impersonated_as: _imp.mitglied.value } : {})
              })
            })
            .then(apiAntwortPruefen)
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
        if (_suppressClick) return
        emit('dateClick', info)
      },

      eventClick: (info) => {
        if (_suppressClick) return
        const isMobile = window.innerWidth <= 768
        const currentView = info.view.type

        // OP-HANDY-8: Am Handy fuehrte ein Tipp auf einen Monatstermin in die
        // Tagesansicht — und die war scheinbar leer, weil der Termin (z. B.
        // 21:00) hunderte Pixel unter dem sichtbaren Bereich lag. Jetzt oeffnet
        // der Tipp direkt das Termindetail (Titel, Zeit, Ort, Beschreibung);
        // wer die Tagesübersicht will, waehlt sie oben im Ansichtsfeld.
        if (isMobile && currentView === 'dayGridMonth') {
          emit('eventClick', info.event)
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
        let ergebnis
        if (props_ev.series_id) {
          if (!sessionAutoConvertSeries.value) {
            const result = await seriesDialog.value?.showDragConfirmation(info.event)
            if (!result?.confirmed) { info.revert(); return }
            if (result.rememberSession) sessionAutoConvertSeries.value = true
          }
          ergebnis = await eventsApi.updateEvent(info.event, () => refetchEvents(), true)
        } else {
          ergebnis = await eventsApi.updateEvent(info.event, () => refetchEvents(), false)
        }
        meldeWartendeAenderung(ergebnis)
      },

      eventResize: async (info) => {
        const props_ev = info.event.extendedProps || {}
        let ergebnis
        if (props_ev.series_id) {
          if (!sessionAutoConvertSeries.value) {
            const result = await seriesDialog.value?.showDragConfirmation(info.event)
            if (!result?.confirmed) { info.revert(); return }
            if (result.rememberSession) sessionAutoConvertSeries.value = true
          }
          ergebnis = await eventsApi.updateEvent(info.event, () => refetchEvents(), true)
        } else {
          ergebnis = await eventsApi.updateEvent(info.event, () => refetchEvents(), false)
        }
        meldeWartendeAenderung(ergebnis)
      },

      select: (info) => {
        if (info.resource?.id?.startsWith('__grp_') || info.resource?.extendedProps?.isGroupHeader) return
        emit('select', info)
      },

      datesSet: (info) => {
        emit('datesSet', info)
        const vt = info.view.type
        // BF1-D: Die tatsaechliche Ansicht melden. Das Kalender-Widget wechselt
        // die Ansicht auch selbst (z.B. Mobil-Klick im Monat -> Tagesansicht);
        // nur so spiegelt das Ansichts-Dropdown die eine Wahrheit.
        emit('viewChange', vt)
        const isResourceView = vt === 'resourceTimelineDay'
          || vt === 'resourceTimelineWeek'
          || vt === 'resourceTimelineMonth'

        emit('resourceViewChange', isResourceView)

        if (isResourceView && !_resourcesLoaded.value) {
          _loadResources()
        }

        if (vt === 'timeGridDay' && !_dayPushed) {
          history.pushState({ kronosDay: 1 }, '')   // Back-Geste faengt Tag->Monat ab statt Seite verlassen
          _dayPushed = true
        } else if (vt === 'dayGridMonth' && _dayPushed && !_popHandling) {
          _dayPushed = false
          history.back()                              // In-App-Rueckkehr -> History-Eintrag konsumieren
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
        // P3-4b/Restpunkt 1 + P3-4c/W3: Die Schriftfarbe kommt aus dem
        // KONTRAST zur Kachelfarbe — dunkle Kacheln bekommen helle, helle
        // Kacheln dunkle Schrift; reicht keine der beiden Marken-Schriften
        // (Kalenderfarben sind frei waehlbar), wird auf Schwarz/Weiß
        // ausgewichen, damit AA (4,5:1) IMMER erreicht wird.
        // Ohne Farbangabe (CSS-Variable/Altbestand) wird KEIN fester Wert
        // gesetzt, sondern der Theme-Wert `--event-ink` verwendet — im
        // Dunkelmodus und im Druck greift damit das Theme (vorher stand hier
        // fest #12183a, wodurch --event-ink wirkungslos war).
        const schrift = kachelSchrift(sichereFarbe(event.backgroundColor))
        return { html:
          '<div class="ec-event-body" style="color:' + schrift + '">' + timeHtml +
          '<h4 class="ec-event-title">' + safe(event.title) + '</h4></div>'
        }
      }
    })

    // Mobile: Swipe-Navigation
    let _swipeStartX = 0
    let _swipeStartY = 0
    calendarEl.value.addEventListener('touchstart', (e) => {
      _swipeStartX = e.touches[0].clientX
      _swipeStartY = e.touches[0].clientY
      _suppressClick = false
    }, { passive: true })
    calendarEl.value.addEventListener('touchmove', (e) => {
      if (Math.abs(e.touches[0].clientX - _swipeStartX) > 10 || Math.abs(e.touches[0].clientY - _swipeStartY) > 10) _suppressClick = true
    }, { passive: true })
    // Capture-Phase: blockt den lib-eigenen click NACH Drag/Swipe, bevor eventClick feuert
    calendarEl.value.addEventListener('click', (e) => {
      if (_suppressClick) { e.stopImmediatePropagation(); e.preventDefault(); _suppressClick = false }
    }, true)
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

    window.addEventListener('popstate', _onPopState)

  } catch (error) {
    console.error('Fehler beim Initialisieren:', error)
    console.error(' Stack:', error.stack)
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('popstate', _onPopState)
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
    const data = await apiAntwortPruefen(res)
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

function next() {
  if (calendar.value) calendar.value.next()
}

function prev() {
  if (calendar.value) calendar.value.prev()
}

function refetchEvents() {
  if (calendar.value) calendar.value.refetchEvents()
}

defineExpose({ changeView, gotoDate, today, next, prev, refetchEvents })
</script>

<template>
  <div ref=calendarEl style=height:100%></div>
  <KronosSeriesDialog ref=seriesDialog />
</template>
