// diakronos/public/js/kronos_calendar.js
// events_color_force_inline_apply: Force Farben inline mit eventDidMount (Doku: https://fullcalendar.io/docs/eventDidMount)

class KronosCalendar {
    constructor() {
        this.calendar = null;
    }

    kronos_calendar_init() {
        console.log('🗓️ kronos_calendar_init: Starte Kalender...');
        
        const calendarEl = document.getElementById('calendar');
        if (!calendarEl) {
            console.error('❌ calendar_element_not_found');
            return;
        }

        this.calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            locale: 'de',
            headerToolbar: false,
            height: '100%',
            editable: true,
            selectable: true,
            events: function(fetchInfo, successCallback, failureCallback) {
                frappe.call({
                    method: 'diakronos.kronos.api.event_crud.get_events',
                    args: {
                        start: fetchInfo.startStr,
                        end: fetchInfo.endStr
                    },
                    callback: (r) => {
                        if (r.message) {
                            const events = r.message.map(event => ({
                                ...event,
                                backgroundColor: event.color || '#007bff',
                                borderColor: event.color || '#007bff',
                                textColor: '#ffffff'
                            }));
                            console.log('✅ events_color_debug: Sample event color:', events[0]?.backgroundColor || 'None');
                            successCallback(events);
                        } else {
                            failureCallback('events_load_failed');
                        }
                    }
                });
            },
            // events_color_force_inline_apply: Force Farben bei Render (um Overrides zu umgehen)
        eventDidMount: function(info) {
                const el = info.el;
                const bgColor = info.event.backgroundColor || '#007bff';  // Aus Kalender-Farbe via API
                el.style.backgroundColor = bgColor;  // Inline setzten (priorisiert über CSS)
                el.style.borderColor = bgColor;
                el.style.color = '#ffffff';  // Kontrast
                console.log('✅ eventDidMount_debug: Forced color for', info.event.title, ':', bgColor);  // Debug
            },
            dateClick: (info) => {
                KronosCreateDialog.showCreateDialog(info.dateStr, {});
            },
            eventClick: (info) => {
                KronosEventClickHandler.showEventClickDialog(info.event);
            }
        });

        this.calendar.render();
        console.log('✅ kronos_calendar_render: Kalender gerendert');
    }

    events_refetch() {
        if (this.calendar) {
            this.calendar.refetchEvents();
        }
    }
}

window.KronosCalendar = KronosCalendar;
console.log('✅ kronos_calendar_class_loaded');