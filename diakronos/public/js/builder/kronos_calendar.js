// builder/kronos_calendar.js – Haupt-Kalender Klasse

import { DiakronosDayEventsModal } from '../modal/modal_day_events.js';
import { DiakronosCreateModal } from '../modal/modal_create.js';
import { DiakronosViewModal } from '../modal/modal_view.js';
import { DiakronosEditModal } from '../modal/modal_edit.js';
import { DiakronosSeriesHandler } from '../modal/modal_series_handler.js';
import { KronosEvents } from '../backend/events_api.js';
import { getViewMode, getSelectedCalendars } from '../backend/data.js';

// Session-Flag: einmal bestätigt → alle Serientermine in dieser Sitzung automatisch trennen
let sessionAutoConvertSeries = false;

class KronosCalendar {
    constructor() {
        this.calendar = null;
    }

    kronos_calendar_init() {
        const calendarEl = document.getElementById('calendar');
        if (!calendarEl) {
            console.error('❌ Calendar Element nicht gefunden');
            return;
        }

        const { Calendar } = window.FullCalendar;
        if (!Calendar) {
            console.error('❌ Kritische Calendar-Klasse fehlt');
            return;
        }

        try {
            // editable und selectable initial anhand des viewMode-State setzen
            const isViewMode = getViewMode();

            this.calendar = new Calendar(calendarEl, {
                initialView: 'dayGridMonth',
                locale: 'de',
                eventTimeFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
                headerToolbar: false,
                weekNumbers: true,
                height: '100%',
                expandRows: true,
                editable: !isViewMode,
                selectable: !isViewMode,
                selectMirror: true,

                events: async function(fetchInfo, successCallback, failureCallback) {
                    const startDate = fetchInfo.startStr.split('T')[0];
                    const endDate   = fetchInfo.endStr.split('T')[0];
                    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
                    const activeCalendars = getSelectedCalendars();

                    console.log('Events-Fetch gestartet – Zeitraum:', startDate, 'bis', endDate);
                    console.log('Ausgewählte Kalender Filter:', activeCalendars.length > 0 ? activeCalendars : 'ALLE');

                    try {
                        const response = await fetch('/api/method/diakronos.kronos.api.calendar_get.get_calendar_events', {
                            method: 'POST',
                            headers: {
                                'Accept': 'application/json',
                                'Content-Type': 'application/json',
                                'X-Frappe-CSRF-Token': csrfToken
                            },
                            body: JSON.stringify({
                                start_date: startDate,
                                end_date: endDate,
                                calendar_filter: JSON.stringify(activeCalendars)
                            })
                        });

                        if (!response.ok) {
                            throw new Error(await response.text());
                        }

                        const result = await response.json();
                        const events = result.message || [];
                        console.log('Gefetchte Events:', events.length);
                        successCallback(events);
                    } catch (err) {
                        console.error('❌ Events Fetch Fehler:', err);
                        failureCallback(err);
                    }
                },

                dateClick: function(info) {
                    console.log('📅 Datum geklickt:', info.dateStr);
                    if (getViewMode()) {
                        if (DiakronosDayEventsModal) {
                            DiakronosDayEventsModal.show(info.dateStr);
                        }
                    } else {
                        if (DiakronosCreateModal) {
                            DiakronosCreateModal.show({
                                start: info.startStr || info.dateStr + 'T00:00',
                                end: info.endStr || info.dateStr + 'T23:59',
                                allDay: info.allDay || !info.endStr
                            });
                        }
                    }
                },

                eventClick: function(info) {
                    const isMobile = window.innerWidth <= 768;
                    const currentView = info.view.type;

                    // Mobile + Monatsansicht: Termin-Klick öffnet Tagesansicht des Tages
                    if (isMobile && currentView === 'dayGridMonth') {
                        info.view.calendar.changeView('timeGridDay', info.event.start);
                        info.jsEvent.preventDefault();
                        return;
                    }

                    // Standard: Modal anzeigen (Desktop oder bereits in Tagesansicht)
                    const eventData = info.event;
                    if (!eventData || !eventData.id) return;

                    const element = eventData.extendedProps || {};
                    if (getViewMode()) {
                        if (element.name && DiakronosViewModal) {
                            DiakronosViewModal.show(element);
                        }
                    } else {
                        if (element.name) {
                            if (element.series_id) {
                                DiakronosSeriesHandler.showEditOptions(element).then(action => {
                                    if (action === 'edit') {
                                        DiakronosEditModal.show({ ...element, series_id: '' });
                                    }
                                });
                            } else if (DiakronosEditModal) {
                                DiakronosEditModal.show(element);
                            }
                        }
                    }
                    info.jsEvent.preventDefault();
                },

                // Arrow-Funktionen → this zeigt auf KronosCalendar-Instanz
                eventDrop: async (info) => {
                    console.log('📦 Event verschoben:', info.event.id);
                    const props = info.event.extendedProps || {};
                    if (props.series_id) {
                        if (!sessionAutoConvertSeries) {
                            const result = await DiakronosSeriesHandler.showDragConfirmation(info.event);
                            if (!result?.confirmed) { info.revert(); return; }
                            if (result.rememberSession) sessionAutoConvertSeries = true;
                        }
                        KronosEvents.updateEvent(info.event, this, true);
                    } else {
                        KronosEvents.updateEvent(info.event, this);
                    }
                },

                eventResize: async (info) => {
                    console.log('📏 Event resized:', info.event.id);
                    const props = info.event.extendedProps || {};
                    if (props.series_id) {
                        if (!sessionAutoConvertSeries) {
                            const result = await DiakronosSeriesHandler.showDragConfirmation(info.event);
                            if (!result?.confirmed) { info.revert(); return; }
                            if (result.rememberSession) sessionAutoConvertSeries = true;
                        }
                        KronosEvents.updateEvent(info.event, this, true);
                    } else {
                        KronosEvents.updateEvent(info.event, this);
                    }
                },

                select: (info) => {
                    console.log('🗓️ Bereich ausgewählt:', info.startStr);
                    if (DiakronosCreateModal) {
                        DiakronosCreateModal.show({
                            start: info.startStr,
                            end: info.endStr,
                            allDay: info.allDay
                        });
                    }
                }
            });

            // Kalender-Resize nach Sidebar-Transition
            const sidebar = document.querySelector('.kronos-sidebar');
            if (sidebar) {
                sidebar.addEventListener('transitionend', (event) => {
                    if (event.propertyName === 'width' && this.calendar) {
                        this.calendar.updateSize();
                    }
                });
            }

            this.calendar.render();
            console.log('✅ Kalender erfolgreich gerendert');

            // Mobile: Swipe nach rechts in der Tagesansicht → zurück zur Monatsansicht
            let _swipeStartX = 0;
            calendarEl.addEventListener('touchstart', (e) => {
                _swipeStartX = e.touches[0].clientX;
            }, { passive: true });
            calendarEl.addEventListener('touchend', (e) => {
                const delta = e.changedTouches[0].clientX - _swipeStartX;
                const viewType = this.calendar.view.type;
                if (viewType === 'timeGridDay') {
                    if (delta > 80) this.calendar.changeView('dayGridMonth');
                } else if (viewType === 'dayGridMonth') {
                    if (delta < -80) this.calendar.next();
                    else if (delta > 80) this.calendar.prev();
                }
            }, { passive: true });

            // Header-Navigation verknüpfen
            const dateDisplay = document.getElementById('current-date-display');
            const prevBtn = document.querySelector('.prev-month');
            const nextBtn = document.querySelector('.next-month');

            const updateDateDisplay = () => {
                if (dateDisplay && this.calendar) {
                    dateDisplay.textContent = this.calendar.view.title;
                }
            };

            this.calendar.on('datesSet', updateDateDisplay);
            updateDateDisplay();

            // Navigation wird in header_build_elements.js verdrahtet (kein Doppel-Listener)

            calendarEl.style.height = '100%';
            this.calendar.updateSize();

        } catch (error) {
            console.error('❌ Fehler beim Initialisieren:', error);
            console.error(' Stack:', error.stack);
        }
    }

    // =========================================================================
    // HELPER METHODEN
    // =========================================================================

    refetchEvents() {
        if (this.calendar) {
            this.calendar.updateSize();
            setTimeout(() => { this.calendar.refetchEvents(); }, 50);
        } else {
            console.warn('⚠️ Calendar nicht initialisiert');
        }
    }

    gotoDate(dateStr) {
        if (this.calendar) this.calendar.gotoDate(dateStr);
    }

    changeView(viewName) {
        if (this.calendar) this.calendar.changeView(viewName);
    }

    getCurrentView() {
        return this.calendar ? this.calendar.view : null;
    }

    today() {
        if (this.calendar) this.calendar.today();
    }
}

export { KronosCalendar };
export const kronosCalendar = new KronosCalendar();
