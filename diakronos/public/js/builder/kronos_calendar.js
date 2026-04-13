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
        this._resourcesLoaded = false;
    }

    kronos_calendar_init() {
        const calendarEl = document.getElementById('calendar');
        if (!calendarEl) {
            console.error('❌ Calendar Element nicht gefunden');
            return;
        }

        if (!window.EventCalendar?.create) {
            console.error('❌ EventCalendar nicht gefunden (window.EventCalendar.create)');
            return;
        }

        try {
            const isViewMode = getViewMode();

            this.calendar = window.EventCalendar.create(calendarEl, {
                view: 'dayGridMonth',
                locale: 'de',
                eventTimeFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
                headerToolbar: false,
                weekNumbers: true,
                height: '100%',
                editable: !isViewMode,
                selectable: !isViewMode,

                resources: [],
                events: [],
                eventSources: [
                    {
                        events: function(fetchInfo, successCallback, failureCallback) {
                            const startDate = fetchInfo.startStr ? fetchInfo.startStr.split('T')[0] : '';
                            const endDate   = fetchInfo.endStr   ? fetchInfo.endStr.split('T')[0]   : '';
                            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
                            const activeCalendars = getSelectedCalendars();

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
                                    view_mode: getViewMode()
                                })
                            })
                            .then(response => {
                                if (!response.ok) return response.text().then(t => { throw new Error(t); });
                                return response.json();
                            })
                            .then(result => successCallback(result.message || []))
                            .catch(err => {
                                console.error('❌ Events Fetch Fehler:', err);
                                failureCallback(err);
                            });
                        }
                    }
                ],

                dateClick: function(info) {
                    if (getViewMode()) {
                        if (DiakronosDayEventsModal) {
                            DiakronosDayEventsModal.show(info.dateStr);
                        }
                    } else {
                        // Edit-Modus: Create-Modal mit Datum vorbelegen
                        if (!DiakronosCreateModal) return;
                        const now = new Date();
                        const roundedMin = Math.round(now.getMinutes() / 5) * 5;
                        const carryHour = Math.floor(roundedMin / 60);
                        const h = (now.getHours() + carryHour) % 24;
                        const m = roundedMin % 60;
                        const pad = n => String(n).padStart(2, '0');
                        DiakronosCreateModal.show({
                            element_start: `${info.dateStr}T${pad(h)}:${pad(m)}`,
                            element_end:   `${info.dateStr}T${pad((h + 1) % 24)}:${pad(m)}`,
                        });
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
                    const vt = info.view.type;
                    const isResourceView = vt === 'resourceTimelineDay'
                        || vt === 'resourceTimelineWeek'
                        || vt === 'resourceTimelineMonth';

                    if (isResourceView) {
                        // Ressourcen laden sobald die Ressourcenansicht erstmals aktiviert wird
                        if (!this._resourcesLoaded) {
                            this._loadResources();
                        }
                    }
                },

                // Dot-Style für Termine im Monatsview (wie FullCalendar-Standard)
                eventClassNames: (info) => {
                    const isMonthView = this.calendar?.getOption('view') === 'dayGridMonth';
                    const isMobile   = window.innerWidth <= 430;
                    const isMultiDay = !info.event.allDay && info.event.end &&
                        new Date(info.event.start).toDateString() !== new Date(info.event.end).toDateString();
                    const useDot = !info.event.allDay && isMonthView && !isMobile && !isMultiDay;
                    return useDot ? ['ec-event-dot-style'] : [];
                },

                eventContent: (info) => {
                    const event = info.event;
                    const isMonthView = this.calendar?.getOption('view') === 'dayGridMonth';
                    const isMobile   = window.innerWidth <= 430;
                    const isMultiDay = !event.allDay && event.end &&
                        new Date(event.start).toDateString() !== new Date(event.end).toDateString();
                    const safe = s => (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

                    if (!event.allDay && isMonthView && !isMobile && !isMultiDay) {
                        const color = event.backgroundColor || 'var(--primary)';
                        return { html:
                            `<div class="ec-event-body ec-dot-body">` +
                            `<span class="ec-dot" style="background:${safe(color)}"></span>` +
                            `<h4 class="ec-event-title">${safe(event.title)}</h4>` +
                            `</div>`
                        };
                    }

                    // Ganztags- und Mehrtagestermine: keine Uhrzeit anzeigen
                    const showTime = !event.allDay && !isMultiDay;
                    const timeHtml = showTime && info.timeText
                        ? `<span class="ec-event-time">${safe(info.timeText)}</span>` : '';
                    return { html:
                        `<div class="ec-event-body">${timeHtml}<h4 class="ec-event-title">${safe(event.title)}</h4></div>`
                    };
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
            // Ressourcen werden lazy beim ersten Wechsel in eine Ressourcen-Ansicht geladen

        } catch (error) {
            console.error('❌ Fehler beim Initialisieren:', error);
            console.error(' Stack:', error.stack);
        }
    }

    // =========================================================================
    // HELPER METHODEN
    // =========================================================================

    async _loadResources() {
        this._resourcesLoaded = true; // vorzeitig setzen → kein Doppel-Request
        const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
        try {
            const res = await fetch('/api/method/diakronos.kronos.api.ressource_api.get_ressources', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
                body: JSON.stringify({})
            });
            const data = await res.json();
            const resources = (data.message || []).map(r => ({ id: r.id, title: r.title }));
            // Dummy-Resource für Termine ohne Raum-Zuordnung (am Ende)
            resources.push({ id: '__unassigned__', title: 'Nicht zugeordnet' });
            if (this.calendar) {
                this.calendar.setOption('resources', resources);
                // refetchResources() zwingt EC die Ressource-Zeilen neu zu rendern
                this.calendar.refetchResources();
            }
        } catch (e) {
            this._resourcesLoaded = false; // bei Fehler: nächster Versuch erlaubt
            console.warn('Ressourcen konnten nicht geladen werden:', e);
        }
    }

    refetchEvents() {
        if (this.calendar) {
            setTimeout(() => { this.calendar.refetchEvents(); }, 50);
        } else {
            console.warn('⚠️ Calendar nicht initialisiert');
        }
    }

    gotoDate(dateStr) {
        if (this.calendar) this.calendar.setOption('date', dateStr instanceof Date ? dateStr : new Date(dateStr));
    }

    changeView(viewName, date) {
        if (!this.calendar) return;
        this.calendar.setOption('view', viewName);
        if (date) this.calendar.setOption('date', date instanceof Date ? date : new Date(date));
    }

    getCurrentView() {
        return this.calendar ? this.calendar.getView() : null;
    }

    today() {
        if (this.calendar) this.calendar.setOption('date', new Date());
    }
}

export { KronosCalendar };
export const kronosCalendar = new KronosCalendar();
