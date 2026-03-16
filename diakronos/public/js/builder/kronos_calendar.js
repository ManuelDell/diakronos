// builder/kronos_calendar.js – Haupt-Kalender Klasse (EventCalendar)

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

        const Calendar = window.EventCalendar;
        if (!Calendar) {
            console.error('❌ EventCalendar nicht gefunden (window.EventCalendar)');
            return;
        }

        try {
            const isViewMode = getViewMode();

            this.calendar = new Calendar(calendarEl, {
                view: 'dayGridMonth',
                locale: 'de',
                eventTimeFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
                headerToolbar: false,
                weekNumbers: true,
                height: '100%',
                editable: !isViewMode,
                selectable: !isViewMode,

                events: async function(fetchInfo, successCallback, failureCallback) {
                    const startDate = fetchInfo.startStr.split('T')[0];
                    const endDate   = fetchInfo.endStr.split('T')[0];
                    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
                    const activeCalendars = getSelectedCalendars();

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
                        successCallback(events);
                    } catch (err) {
                        console.error('❌ Events Fetch Fehler:', err);
                        failureCallback(err);
                    }
                },

                dateClick: function(info) {
                    if (getViewMode()) {
                        if (DiakronosDayEventsModal) {
                            DiakronosDayEventsModal.show(info.dateStr);
                        }
                    }
                },

                eventClick: function(info) {
                    const isMobile = window.innerWidth <= 768;
                    const currentView = info.view.type;

                    // Mobile + Monatsansicht: Termin-Klick öffnet Tagesansicht
                    if (isMobile && currentView === 'dayGridMonth') {
                        kronosCalendar.changeView('timeGridDay', info.event.start);
                        info.jsEvent.preventDefault();
                        return;
                    }

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

                eventDrop: async (info) => {
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
                    if (!DiakronosCreateModal) return;

                    const date = info.startStr.slice(0, 10);
                    const now  = new Date();
                    const roundedMin = Math.round(now.getMinutes() / 5) * 5;
                    const carryHour  = Math.floor(roundedMin / 60);
                    const h = (now.getHours() + carryHour) % 24;
                    const m = roundedMin % 60;
                    const pad = n => String(n).padStart(2, '0');

                    const startStr = `${date}T${pad(h)}:${pad(m)}`;
                    const endStr   = `${date}T${pad((h + 1) % 24)}:${pad(m)}`;

                    DiakronosCreateModal.show({
                        element_start: startStr,
                        element_end:   endStr,
                    });
                },

                // datesSet broadcastet an alle Listener via Custom-Event
                datesSet: (info) => {
                    document.dispatchEvent(new CustomEvent('ec:datesSet', { detail: info }));
                }
            });

            // Kalender-Resize nach Sidebar-Transition
            const sidebar = document.querySelector('.kronos-sidebar');
            if (sidebar) {
                sidebar.addEventListener('transitionend', (event) => {
                    if (event.propertyName === 'width') {
                        // EventCalendar resized automatisch
                    }
                });
            }

            // Mobile: Swipe-Navigation
            let _swipeStartX = 0;
            calendarEl.addEventListener('touchstart', (e) => {
                _swipeStartX = e.touches[0].clientX;
            }, { passive: true });
            calendarEl.addEventListener('touchend', (e) => {
                const delta = e.changedTouches[0].clientX - _swipeStartX;
                const viewType = this.calendar.getOption('view');
                if (viewType === 'timeGridDay') {
                    if (delta > 80) this.changeView('dayGridMonth');
                } else if (viewType === 'dayGridMonth') {
                    if (delta < -80) this.calendar.next();
                    else if (delta > 80) this.calendar.prev();
                }
            }, { passive: true });

            calendarEl.style.height = '100%';

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
            setTimeout(() => { this.calendar.refetchEvents(); }, 50);
        } else {
            console.warn('⚠️ Calendar nicht initialisiert');
        }
    }

    gotoDate(dateStr) {
        if (this.calendar) this.calendar.setOption('date', new Date(dateStr));
    }

    changeView(viewName, date) {
        if (!this.calendar) return;
        this.calendar.setOption('view', viewName);
        if (date) this.calendar.setOption('date', date instanceof Date ? date : new Date(date));
    }

    getCurrentView() {
        return this.calendar ? { type: this.calendar.getOption('view') } : null;
    }

    today() {
        if (this.calendar) this.calendar.today();
    }
}

export { KronosCalendar };
export const kronosCalendar = new KronosCalendar();
