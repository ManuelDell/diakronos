<script setup>
import { apiAntwortPruefen } from '../../composables/useApi.js'
// WEB-5b: Adressen unter dem Betriebs-Praefix (DIAKRONOS_BASE_PATH) bauen.
import { apiUrl } from '../../../shared/basis.js'
import { ref, onMounted, onBeforeUnmount, watch, nextTick, createApp, h } from 'vue'
import * as _EC from '@event-calendar/build'
import '@event-calendar/build/dist/event-calendar.min.css'
import { useEventsApi } from '../../composables/useEventsApi.js'
// ICAL-1: ganztägiges Ende für die Anzeige ausschließend machen (+1 Tag).
import { endeFuerKalender } from '../../composables/datumZeit.mjs'
import { useImpersonation } from '../../composables/useImpersonation.js'
import { showToast } from '../../composables/useToast.js'
import KronosSeriesDialog from './KronosSeriesDialog.vue'
import DkAktionen from '../ui/DkAktionen.vue'
import { MENUE_EINTRAEGE } from './terminAktionenMenue.mjs'
import { erstelleTerminDaten } from './terminAktionenDaten.mjs'
// UX2e5: „⋯" je Termin — der Knopf ist ein Geschwister der Bibliotheks-Zeile
// und wird per Kennung zugeordnet (siehe ./terminAktionen.mjs).
import { zuordnen } from './terminAktionen.mjs'
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
  // UX2e5: Eintrag aus dem „⋯"-Menü eines Termins (siehe MENUE_EINTRAEGE).
  'terminAktion',
])

const calendarEl = ref(null)
const seriesDialog = ref(null)
const calendar = ref(null)

/* ── UX2e5 · „⋯" je Termin in der Terminliste ──────────────────────────
 * Die Knöpfe stehen als GESCHWISTER direkt hinter ihrer Bibliotheks-Zeile
 * (siehe ./terminAktionen.mjs). Jeder Knopf ist ein eigener Vue-Knoten mit
 * seinem DkAktionen-Menü; der Halter wird im Abgleich gebaut und dort auch
 * wieder abgebaut (Rahmen + Knoten) — sonst bliebe je Neuladen ein Rahmen
 * samt offenem Menü im Speicher.
 */
const menueOffen = ref(false)
let abgleichGeplant = false
/** Kennung -> Halter-Element. NUR lebende Halter: was nicht mehr am Dokument
 *  hängt (Ansichtswechsel, Neubau der Bibliothek), wird sofort abgebaut. */
const KNOEPFE = new Map()

function istListenAnsicht() {
  const ansicht = calendar.value?.getOption('view') || ''
  return String(ansicht).startsWith('list')
}

/** Der Rahmen (Vue-App) eines Halters — er hängt am Inhalt darunter. */
function rahmenVon(el) {
  return el?.querySelector?.('.kronos-liste-aktionen-halter-inhalt')?.__kronosRahmen || null
}

/**
 * Ein Abgleich je Umlauf — `eventDidMount`/`eventWillUnmount` melden je Zeile;
 * abgeglichen wird danach EINMAL, nicht je Termin.
 */
function abgleichPlanen() {
  if (abgleichGeplant || !calendarEl.value) return
  abgleichGeplant = true
  nextTick(() => {
    abgleichGeplant = false
    if (!calendarEl.value || !istListenAnsicht()) {
      // Ansichtswechsel (oder Kalender schon weg): es bleibt KEIN Knopf und
      // kein Rahmen zurück — überall unter dem Kalender, nicht nur die
      // selbst gemerkten.
      alleKnoepfeAbbauen()
      return
    }
    // Halter, die nicht mehr am Dokument hängen (die Bibliothek hat sie beim
    // Neubau fortgeworfen), gehören keinem Termin mehr: erst abbauen, dann
    // neu zuordnen. Sonst bliebe für jede weggeworfene Zeile ein Rahmen.
    for (const [kennung, el] of Array.from(KNOEPFE)) {
      if (el?.isConnected) continue
      rahmenAbbauen(el)
      KNOEPFE.delete(kennung)
    }
    // Der Abgleich hat die Zuordnung gerade festgelegt: alle übrigen
    // Halter im Kalender (doppelte/Waisen) werden abgebaut. Erst bauen, dann
    // weg — sonst stünde ein Knopf ohne Rahmen im Baum.
    const behalten = new Set(zuordnen(calendarEl.value, knopfSicherstellen, entfernenErlaubt, vergessen))
    for (const el of Array.from(calendarEl.value.querySelectorAll('.kronos-liste-aktionen-halter'))) {
      if (behalten.has(el)) continue
      rahmenAbbauen(el)
    }
    for (const [kennung, el] of Array.from(KNOEPFE)) {
      if (behalten.has(el)) continue
      rahmenAbbauen(el)
      KNOEPFE.delete(kennung)
    }
  })
}

/** Meldung des Abgleichs: dieser Halter wird nicht behalten — Rahmen weg. */
function vergessen(el) {
  rahmenAbbauen(el)
  for (const [kennung, bekannt] of Array.from(KNOEPFE)) {
    if (bekannt === el) KNOEPFE.delete(kennung)
  }
}

/** Baut ALLE „⋯" samt Rahmen ab (Ansichtswechsel, Verlassen der Seite). */
function alleKnoepfeAbbauen() {
  const gesehen = new Set()
  for (const el of Array.from(calendarEl.value?.querySelectorAll?.('.kronos-liste-aktionen-halter') || [])) {
    gesehen.add(el)
    rahmenAbbauen(el)
  }
  for (const [kennung, el] of Array.from(KNOEPFE)) {
    if (!gesehen.has(el)) rahmenAbbauen(el)
    KNOEPFE.delete(kennung)
  }
  menueOffen.value = false
}

/**
 * Darf der Abgleich DIESEN Knoten entfernen? Nur Knöpfe, die diese Ansicht
 * gebaut hat — ein fremder Kalender ausserhalb dieser Wurzel bleibt unberührt
 * (Karten über React/Vue mit mehreren Kalendern).
 */
function entfernenErlaubt(el) {
  if (!el) return false
  for (const knoten of KNOEPFE.values()) if (knoten === el) return true
  return false
}

/** Baut den Vue-Rahmen eines „⋯"-Halters ab. */
function rahmenAbbauen(el) {
  const rahmen = rahmenVon(el)
  if (rahmen) {
    try { rahmen.unmount() } catch { /* schon abgebaut */ }
    const inhalt = el?.querySelector?.('.kronos-liste-aktionen-halter-inhalt')
    if (inhalt) inhalt.__kronosRahmen = null
  }
  // Der Halter selbst wird IMMER aus dem Baum genommen (die Bibliothek hat ihn
  // nach einem Neubau schon herausgenommen — dann ist das folgenlos).
  if (el?.remove) el.remove()
}

/**
 * WARUM HIER GESTOPPT WIRD (Befund der Browser-Abnahme 07.11.):
 * Der Halter steht als GESCHWISTER der Terminzeile im `.ec-day`-Container.
 * Dieser Container ist in der Liste das Datumsfeld der Bibliothek — ein Klick
 * darin zählt als Klick auf den Tag bzw. als Auswahl (Ziehen), und die
 * Bibliothek meldet dafür `dateClick`/`select`. Folge: „Neuer Termin" ging auf,
 * sobald man das „⋯" (oder die Halter-Fläche) anklickte.
 * Ein Bedienelement IN der Zeile hätte dasselbe Problem gehabt — deshalb
 * beendet sich hier jeder Zeiger-Klick am Halter: er gehört dem Menü, nicht
 * dem Tag. (Die Zeile selbst bleibt unberührt; ihr Klick ist ein eigenes
 * Element mit eigenem `article`-Verhalten.)
 */
function zeigerAmHalterBleibt(halter) {
  for (const art of ['pointerdown', 'pointerup', 'mousedown', 'mouseup', 'click', 'dblclick']) {
    halter.addEventListener(art, (ereignis) => {
      ereignis.stopPropagation()
      // Tastaturbedienung des Auslösers bleibt unberührt (kein preventDefault).
    })
  }
}

/** Baut den „⋯" samt Menü und merkt ihn sich zur Kennung. */
function knopfAnlegen(kennung, zeile) {
  const halter = document.createElement('span')
  halter.className = 'kronos-liste-aktionen-halter'
  halter.setAttribute('data-termin', kennung)
  const unterbau = document.createElement('span')
  unterbau.className = 'kronos-liste-aktionen-halter-inhalt'
  halter.appendChild(unterbau)
  const rahmen = knopfRahmenFuer(kennung, unterbau)
  unterbau.__kronosRahmen = rahmen
  zeigerAmHalterBleibt(halter)
  KNOEPFE.set(kennung, halter)
  return halter
}

/** Der Termin (Bibliotheks-Objekt) zu einem „⋯"-Knopf. */
function terminZumKnopf(kennung, el) {
  let zeile = el?.previousElementSibling?.matches?.('article.ec-event')
    ? el.previousElementSibling
    : null
  // Der Knopf hängt evtl. schon nicht mehr an seiner Zeile (Neuordnung in
  // Arbeit): dann die Zeile über ihre Kennung suchen.
  if (!zeile && calendarEl.value) {
    zeile = calendarEl.value.querySelector(`article.ec-event[data-event-id="${kennung}"]`)
  }
  const daten = erstelleTerminDaten(zeile)
  if (daten) {
    daten.id = kennung
    return daten
  }
  return { id: kennung, title: '', extendedProps: {} }
}

/**
 * Vue-App für EINEN „⋯"-Knopf samt seinem Menü.
 *
 * Der eigene Rahmen ist nötig, weil der Knopf kein Kind einer Seite, sondern
 * ein Anhängsel der Bibliothek ist. Sein `render` liefert den Knopf als
 * BAUTEIL-Knoten (nicht als gezeichnetes Element): `render: () => h(...)`.
 * Damit gehören `eintraege`, `label` und die Zuhörer zur Komponente
 * DkAktionen — so kommen `aktion` (Menüeintrag) und `offenGeaendert` an.
 *
 * REVIEW UX2e5/3: Im ANSEHEN-Modus bietet das Menü nur „Ansehen" an (das ist
 * dort die einzige erlaubte Handlung — wie beim Klick auf die Zeile,
 * `onEventClick` in Kalender.vue). Die Entscheidung fällt beim Öffnen des
 * Rahmens: `viewMode` steht beim Bauen fest (Kalender wird beim Wechsel des
 * Modus neu geholt).
 */
function knopfRahmenFuer(kennung, el) {
  const nurAnsehen = props.viewMode === 'view'
  const rahmen = createApp({
    render: () => h(DkAktionen, {
      label: 'Aktionen für diesen Termin',
      menueLabel: 'Aktionen für diesen Termin',
      kennung: `termin-${kennung}`,
      // Gemeldet wird von der EIGENEN Uhr-Komponente, nicht vom Unterbau:
      // `emit` von DkAktionen erreicht in einer eigenen App keinen Zuhörer
      // — der Eintrag kommt dort mit `aktion` an, es gibt aber keinen
      // Empfänger (im Browser und in jsdom gemessen).
      eintraege: MENUE_EINTRAEGE
        .filter((eintrag) => !nurAnsehen || eintrag.key === 'ansehen')
        .map((eintrag) => ({
          ...eintrag,
          aktion: () => emit('terminAktion', {
            key: eintrag.key,
            terminId: kennung,
            // Der Termin wird JETZT gelesen, nicht beim Bauen: nach einem
            // Neubau der Bibliothek ist der Inhalt (mit seinen Daten) ein
            // anderer Knoten.
            termin: terminZumKnopf(kennung, el),
          }),
        })),
      onOffenGeaendert: (offen) => { menueOffen.value = offen },
    }),
  })
  rahmen.mount(el)
  return rahmen
}

/** Baut (falls nötig) den „⋯" an einer Zeile und liefert ihn. */
function knopfSicherstellen(zeile, kennung) {
  const bekannt = KNOEPFE.get(kennung)
  if (bekannt && bekannt.isConnected) return bekannt
  // Ein Halter zu dieser Kennung, der nicht mehr am Dokument hängt, ist
  // Müll: erst seinen Rahmen abbauen, dann einen frischen bauen. Sonst
  // sammelt jedes Neuladen einen Vue-Rahmen samt Menü-Zuhörern an.
  if (bekannt) {
    rahmenAbbauen(bekannt)
    KNOEPFE.delete(kennung)
  }
  return knopfAnlegen(kennung, zeile)
}

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
    showToast(ergebnis.meldung || 'Änderung wartet auf Freigabe (Zu prüfen).', 'success')
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

            fetch(apiUrl('diakronos.kronos.api.calendar_get.get_calendar_events'), {
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
                // ICAL-1: Die Bibliothek zählt das Ende ganztägiger Termine
                // AUSSCHLIESSEND (RFC 5545), Diakronos speichert es
                // EINSCHLIESSEND. Ohne diesen Tag fehlte der zweite Tag eines
                // mehrtägigen Ganztags-Termins im Monatsraster.
                const endePlus = endeFuerKalender(ev.end, ev.allDay)
                if (endePlus) ev.end = endePlus
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
        // UX2e5: Der Termin-Datensatz für das „⋯"-Menü der LISTE. Die
        // Bibliothek liefert keine Rückreferenz zum Datensatz, deshalb reist
        // er als JSON an der Zeile mit (ausgelesen in ./terminAktionenDaten.mjs).
        const daten = {
          id: String(event.id ?? ''),
          title: event.title || '',
          start: event.start ? new Date(event.start).toISOString() : null,
          end: event.end ? new Date(event.end).toISOString() : null,
          allDay: !!event.allDay,
          backgroundColor: event.backgroundColor || '',
          extendedProps: event.extendedProps || {},
        }
        // Einfache Anführungszeichen: der Inhalt ist JSON mit doppelten —
        // mit doppelten umschlossen endete das Merkmal mitten im JSON.
        const datenAttr = " data-termin-daten='" + safe(JSON.stringify(daten)) + "'"

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
        // Am ÄUSSEREN Inhalt: den hängt die Bibliothek in `.ec-event-body` der
        // Zeile — dort liest ./terminAktionenDaten.mjs ihn, auch nach einem
        // Neubau (deshalb NICHT am inneren Körper duplizieren).
        return { html:
          '<div class="ec-event-inhalt"' + datenAttr + ' style="color:' + schrift + '">' + timeHtml +
          '<h4 class="ec-event-title">' + safe(event.title) + '</h4></div>'
        }
      },

      // UX2e5: Ein-/Ausbau und jeder Neubau der Bibliothek stoßen den
      // Knopf-Abgleich an (idempotent, ein Lauf je Umlauf). KEIN gemessenes
      // Nachführen je Knopf (kein ResizeObserver) — die Zuordnung hängt an
      // der Kennung, nicht an Maßen.
      // Die Kennung setzt KEIN Teil der Bibliothek ans `article` (sie führt
      // sie nur intern); sie kommt hier an der Zeile mit, damit der Abgleich
      // Knopf und Termin ohne Raten zusammenbringt.
      eventDidMount: (info) => {
        const el = info?.el
        if (!el || el.tagName !== 'ARTICLE') return
        const kennung = String(info?.event?.id ?? '')
        if (kennung) el.setAttribute('data-event-id', kennung)
        abgleichPlanen()
      },
      eventWillUnmount: () => { abgleichPlanen() },
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
  // UX2e5: Alle „⋯"- Rahmen der Liste abbauen (kein hängender Knoten, kein
  // offenes Menü nach dem Verlassen der Seite).
  alleKnoepfeAbbauen()
  menueOffen.value = false
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
    const res = await fetch(apiUrl('diakronos.kronos.api.ressource_api.get_ressources'), {
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
  // UX2e5: Nach jedem Neuladen neu zuordnen — auch wenn die Bibliothek die
  // Zeilen in derselben Lage weiterbenutzt (Rückgängig, Serien-Fragen).
  abgleichPlanen()
}

defineExpose({
  changeView, gotoDate, today, next, prev, refetchEvents,
  // REVIEW UX2e5/3: die „⋯"-Menüs neu bauen (nach einem Moduswechsel kennt
  // das alte Menü den neuen Modus nicht).
  neuZuordnen,
  // UX2e5 (Review 07.11.): Anzahl der „⋯"-Rahmen im Kalender. Der Test hält
  // damit fest, dass nach vielen Neuladen/Ansichtswechseln KEIN Rahmen übrig
  // bleibt (jedem sichtbaren Termin genau einer).
  anzahlRahmen,
})

/** Zahl der lebenden „⋯"-Rahmen — nur für Belege (Test), ohne Nebenwirkung. */
function anzahlRahmen() {
  return Array.from(calendarEl.value?.querySelectorAll?.('.kronos-liste-aktionen-halter-inhalt') || [])
    .filter((inhalt) => !!inhalt.__kronosRahmen).length
}

/**
 * REVIEW UX2e5/3: Alle „⋯" samt Menü verwerfen und frisch zuordnen.
 *
 * Das Menü eines Knopfes entsteht beim Zuordnen und kennt den ANSEHEN- bzw.
 * BEARBEITEN-Modus von da. Nach einem Moduswechsel (oder wenn ein Test den
 * Modus umstellt) wird deshalb neu gebaut — kein zweiter Menüpfad, keine
 * Prüfung im Klickpfad.
 */
function neuZuordnen() {
  for (const [kennung, el] of Array.from(KNOEPFE)) {
    rahmenAbbauen(el)
    KNOEPFE.delete(kennung)
  }
  abgleichGeplant = false
  abgleichPlanen()
}

</script>

<template>
  <div ref=calendarEl style=height:100%></div>
  <KronosSeriesDialog ref=seriesDialog />
</template>

<style scoped>
/* UX2e5 — „⋯" je Termin in der Terminliste.
   Die Zeilen der Bibliothek sind Geschwister im Tages-Container (keine
   gemeinsame Hülle); der Halter ist das nächste Geschwister SEINER Zeile,
   also in Zeilenhöhe unter seinem Termin.

   TREFFERFLÄCHE (Befund aus der Browser-Abnahme 07.11.): Der Halter nimmt die
   ganze Zeilenbreite ein — der AUSLÖSER darin aber nur eine quadratische
   Fläche von --control-h (44 px bei pointer: coarse) am rechten Rand, oben
   bündig zur Zeile. Vorher füllte der Auslöser die ganze Breite und lag über
   dem Termin: ein Klick auf den Termin traf das „⋯" statt der Zeile (die
   Bibliothek öffnete stattdessen „Neuer Termin"). Die Leerfläche LINKS bleibt
   klickdurchlässig (Halter und Inhalt ohne Hintergrund). */
:deep(.kronos-liste-aktionen-halter) {
  display: block;
  margin: 0 0 var(--sp-1) 0;
  padding: 0;
}
:deep(.kronos-liste-aktionen-halter-inhalt) {
  display: block;
}
/* Nur in der Liste: das Monatsraster behält seine Punkte-Zeilen. */
:deep(.ec-list .kronos-liste-aktionen-halter .dk-ui-aktionen-ausloeser) {
  display: flex;
  width: var(--control-h);
  height: var(--control-h);
  margin-left: auto;
  justify-content: center;
}
@media (pointer: coarse) {
  :deep(.ec-list .kronos-liste-aktionen-halter .dk-ui-aktionen-ausloeser) {
    width: 44px;
    height: 44px;
  }
}
</style>
