<template>
  <div class="kronos-page-content">
    <KronosTopbar
      :dateTitle="dateTitle"
      :currentView="currentView"
      :viewMode="store.viewMode.value"
      :canWrite="hasWriteRight"
      @prev="calendarRef?.prev()"
      @next="calendarRef?.next()"
      @today="calendarRef?.today()"
      @viewChange="onViewChange"
      @resourceToggle="onResourceToggle"
      @viewModeChange="onViewModeChange"
      @sidebarToggle="kronosSidebar.umschalten()"
    />
    <div class="kronos-calendar-wrap">
      <!-- OP-UI-11: Die Kalenderliste ist ein einklappbares Feld IN der Seite.
           Das Hauptmenü links bleibt dadurch stehen; vorher ersetzte sie die
           ganze Navigation und „Zur Hauptnavigation“ verließ den Kalender. -->
      <KronosSidebar
        class="kronos-sidebar-inpage"
        :open="kronosSidebar.offen.value"
        @close="kronosSidebar.zu()"
        @ablehnungClick="$emit('ablehnungClick', $event)"
        @calendarsChange="onCalendarsChange"
      />
      <KronosCalendar
        ref="calendarRef"
        :selectedCalendars="store.selectedCalendars.value"
        :viewMode="store.viewMode.value"
        @eventClick="onEventClick"
        @dateClick="onDateClick"
        @select="onSelect"
        @datesSet="onDatesSet"
        @viewChange="onCalendarViewChange"
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
      :viewMode="store.viewMode.value"
      @eventClick="onDayEventClick"
    />
    <KronosSeriesDialog ref="seriesDialogRef" />

    <!-- K-A (R-P1-8): Detailansicht des EIGENEN abgelehnten Termins aus der
         Kalenderliste. Vorher hing sie in App.vue an der dort gerenderten
         Kalender-Seitenleiste; seit OP-UI-11 liegt die Liste in dieser Seite,
         also auch ihre Detailansicht. -->
    <KronosEventView
      v-model:show="showAbgelehntView"
      :event="abgelehnterTermin"
    />

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useKronosStore } from '../composables/useKronosStore.js'
import { useKronosSidebar } from '../composables/useKronosSidebar.js'
import { getMeinTermin } from '../composables/useEventsApi.js'
import { showToast } from '../composables/useToast.js'
import { vorschlagBeginn } from '../composables/datumZeit.mjs'
import KronosTopbar from '../components/kronos/KronosTopbar.vue'
import KronosSidebar from '../components/kronos/KronosSidebar.vue'
import KronosCalendar from '../components/kronos/KronosCalendar.vue'
import KronosEventCreate from '../components/kronos/KronosEventCreate.vue'
import KronosEventEdit from '../components/kronos/KronosEventEdit.vue'
import KronosEventView from '../components/kronos/KronosEventView.vue'
import KronosDayEventsDialog from '../components/kronos/KronosDayEventsDialog.vue'
import KronosSeriesDialog from '../components/kronos/KronosSeriesDialog.vue'

const store = useKronosStore()
const kronosSidebar = useKronosSidebar()
const calendarRef = ref(null)
const seriesDialogRef = ref(null)

// State
const dateTitle = ref('')
const currentView = ref('dayGridMonth')

// Modal states
const showCreate = ref(false)
const createInitialData = ref({})
const showEdit = ref(false)
const editEvent = ref(null)
const showView = ref(false)
const viewEvent = ref(null)
const showDayEvents = ref(false)
const dayEventsDate = ref('')

// UXK-R10: Der Bearbeitungs-Umschalter und „Termin anlegen“ werden nur
// angeboten, wenn der Nutzer auf MINDESTENS einen Kalender schreiben darf.
// Die Rechte kommen vom Server (`get_accessible_calendars` -> `write`).
const hasWriteRight = computed(() =>
  (store.availableCalendars.value || []).some(c => c.write)
)

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
        } else if (action === 'deleted') {
          // UXK-R3: Nach dem Serien-Loeschen blieben die geloeschten Termine
          // sichtbar, bis die Seite neu geladen wurde — der Kalender muss
          // seine Termine neu holen.
          calendarRef.value?.refetchEvents()
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
    // UXK-R1: `info.dateStr` der Kalender-Bibliothek enthaelt BEREITS die
    // Uhrzeit (Monat: `YYYY-MM-DDT00:00:00`, Woche/Tag: die geklickte Zeit).
    // Frueher wurde daran noch einmal `T{HH}:{MM}` gehaengt — daraus wurde
    // `2026-10-21T00:00:00T19:00`, der Server antwortete 417 „Ungueltiges
    // Datum“, und weil der Dialog trotzdem schloss, sah es nach Erfolg aus.
    // Jetzt: nur das reine Datum nehmen und die Uhrzeit sinnvoll vorbelegen.
    const tag = String(info.dateStr || '').slice(0, 10)
    const beginn = defaultStartZeit(info)
    const ende = defaultEndZeit(beginn)
    createInitialData.value = {
      element_start: `${tag}T${beginn}`,
      // DEV-5: 23:00 + 1 h ist der Folgetag, nicht 00:00 desselben Tages.
      element_end: `${endeTagAusZeit(tag, beginn, ende)}T${ende}`
    }
    showCreate.value = true
  }
}

/**
 * Standard-Beginnzeit fuer einen Klick (DEV-5): Woche/Tag uebernehmen die
 * angeklickte Slot-Zeit unveraendert. Das Monatsraster liefert nur 00:00 —
 * dort (und bei einem reinen Tagesklick) gilt die NAECHSTE volle Stunde der
 * Browserzeit; vorher war es fest 19:00.
 */
function defaultStartZeit(info) {
  const str = String(info.dateStr || '')
  const treffer = str.match(/T(\d{2}):(\d{2})/)
  if (treffer) {
    const h = treffer[1]
    const m = treffer[2]
    // Klick um 00:00 (Tagesbeginn) kommt aus dem Monatsraster -> Vorschlag.
    if (h === '00' && m === '00' && info.view?.type?.startsWith('dayGrid')) {
      return vorschlagBeginn()
    }
    return `${h}:${m}`
  }
  return vorschlagBeginn()
}

/** Standard-Endzeit: eine Stunde nach dem Beginn (UXK-R1). */
function defaultEndZeit(beginn) {
  const [h, m] = String(beginn).split(':').map(Number)
  const endH = String((h + 1) % 24).padStart(2, '0')
  return `${endH}:${String(m).padStart(2, '0')}`
}

/** Endtag zu einer Endzeit: ab Mitternacht ist es der Folgetag (DEV-5). */
function endeTagAusZeit(startTag, startZeit, endeZeit) {
  const s = String(startZeit || '').match(/^(\d{1,2}):/)?.[1]
  const e = String(endeZeit || '').match(/^(\d{1,2}):/)?.[1]
  if (s === undefined || e === undefined) return startTag
  return Number(e) < Number(s) ? naechsterTag(startTag) : startTag
}

/** „YYYY-MM-DD“ + 1 Tag (Monats-/Jahreswechsel inklusive). */
function naechsterTag(datum) {
  const m = String(datum || '').match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!m) return datum
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]) + 1, 12))
  const zwei = (n) => String(n).padStart(2, '0')
  return `${d.getUTCFullYear()}-${zwei(d.getUTCMonth() + 1)}-${zwei(d.getUTCDate())}`
}

function onSelect(info) {
  // UXK-R1: Auch die Auswahl (Ziehen) liefert je nach Ansicht ein reines Datum
  // (`2026-10-21`) oder einen vollen Zeitstempel. Vereinheitlichen: Tag + Zeit,
  // damit der Dialog immer ein vollstaendiges, gueltiges Datum bekommt.
  const startTag = String(info.startStr || '').slice(0, 10)
  const startZeit = zeitAusStr(info.startStr) || '09:00'
  const endeStr = String(info.endStr || '')
  const endeTag = endeStr.slice(0, 10)
  const endeZeit = zeitAusStr(endeStr) || defaultEndZeit(startZeit)
  const endeEffektivTag = (endeTag && endeTag !== startTag) ? endeTag : startTag
  const endeEffektivZeit = (endeTag && endeTag !== startTag) ? endeZeit : defaultEndZeit(startZeit)
  createInitialData.value = {
    element_start: `${startTag}T${startZeit}`,
    element_end: `${endeEffektivTag}T${endeEffektivZeit}`
  }
  showCreate.value = true
}

/** Uhrzeit aus einem ISO-/DateStr ziehen (`2026-10-21T19:00:00` -> `19:00`). */
function zeitAusStr(wert) {
  const treffer = String(wert || '').match(/T(\d{2}:\d{2})/)
  return treffer ? treffer[1] : ''
}

function onCalendarsChange(calendars) {
  store.setSelectedCalendars(calendars)
}

/* K-A (R-P1-8): eigener abgelehnter Termin aus der Kalenderliste. */
const showAbgelehntView = ref(false)
const abgelehnterTermin = ref(null)

async function zeigeAbgelehntenTermin(elementId) {
  const daten = await getMeinTermin(elementId)
  if (!daten) {
    showToast('Termin konnte nicht geladen werden.', 'error')
    return
  }
  abgelehnterTermin.value = daten
  showAbgelehntView.value = true
}

function onViewChange(viewName) {
  currentView.value = viewName
  calendarRef.value?.changeView(viewName)
}

/** BF1-D: Das Kalender-Widget hat die Ansicht selbst gewechselt (z.B.
 *  Mobil-Klick im Monat -> Tagesansicht). `currentView` nachziehen, damit das
 *  Ansichts-Dropdown dieselbe Ansicht anzeigt (eine Wahrheit). Zurueck zum
 *  Monat geht dann wieder direkt ueber das Dropdown. */
function onCalendarViewChange(viewType) {
  if (viewType && viewType !== currentView.value) {
    currentView.value = viewType
  }
}

/** Resource-Timeline-Ansichten sind eine Untermenge der normalen Ansichten;
 *  das Dropdown fuehrt die Normalansicht. Bei Ressourcenansicht die zuletzt
 *  gewaehlte Normalansicht behalten — das erledigt `onCalendarViewChange`
 *  bereits, indem es Ressourcenansichten nicht uebernimmt. K4: die frueher
 *  hier gebundene, leere `onResourceViewChange`-Funktion ist entfernt.
 */

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
  // UXK-R10: Ohne Schreibrecht gibt es keinen Bearbeitungsmodus.
  if (mode === 'edit' && !hasWriteRight.value) return
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
/* FIX-6: Der Fußabstand für die untere Leiste gilt in der Mobil-Lage —
   LAYOUT, also nur die Breite (index.css «FIX-6 · Layout nur nach Breite»).
   Vorher stand hier `(hover: none) and (pointer: coarse)`: auf einem
   Touch-Notebook mit 1410 px entstand 80 px Leerraum unter dem Inhalt,
   obwohl die untere Leiste dort gar nicht erscheint. */
@media (max-width: 720px) {
  .kronos-page-content {
    padding-bottom: 80px;
  }
}
/* OP-HANDY-9: Im Querformat darf der Inhalt scrollen, damit das Monatsraster
   seine Mindesthoehe behaelt und Termine sichtbar bleiben. */
@media (orientation: landscape) and (max-height: 480px) {
  .kronos-page-content {
    overflow-y: auto;
  }
}
</style>
