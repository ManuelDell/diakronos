// kronos_calendar.js – angepasst für v6 Global Bundle (Plugins entfernt, da im Bundle integriert)
class KronosCalendar {
    constructor() {
        this.calendar = null;
    }

    kronos_calendar_init() {
//        console.log('🗓️ kronos_calendar_init: Starte Kalender...');
        
        const calendarEl = document.getElementById('calendar');
        if (!calendarEl) {
            console.error('❌ Calendar Element nicht gefunden');
            return;
        }

        // =========================================================================
        // KRITISCH: window.FullCalendar muss von kronos_calendar_page.js gesetzt sein!
        // =========================================================================
        if (!window.FullCalendar || !window.FullCalendar.Calendar) {
            console.error('❌ FullCalendar nicht im window verfügbar!');
            console.error('   Prüfe: Wurde loadFullCalendarGlobal() aufgerufen?');
            console.error('   window.FullCalendar:', window.FullCalendar);
            return;
        }

        // Destrukturiere NUR Calendar aus window.FullCalendar
        const { 
            Calendar
        } = window.FullCalendar;

        // Validierung: Calendar vorhanden? (Plugins sind intern)
        if (!Calendar) {
            console.error('❌ Kritische Calendar-Klasse fehlt');
            return;
        }

//        console.log('✅ FullCalendar verfügbar:', {
//            Calendar: !!Calendar
//        });

        try {
            // Erstelle Calendar-Instanz ohne plugins-Array
            this.calendar = new Calendar(calendarEl, {
                // plugins: [] ← Entfernt: Nicht nötig beim global bundle
                initialView: 'dayGridMonth',
                locale: 'de',
                // Header wird in kronos_calendar_page.js verwaltet
                headerToolbar: false,
                weekNumbers: true, 
                // Layout
                height: '100%',
                expandRows: true,
                // Interaktion
                editable: true,
                selectable: true,
                selectMirror: true,
                // Events (umgeschrieben auf reines fetch, ohne frappe.call)
                events: async function(fetchInfo, successCallback, failureCallback) {
                    const startDate = fetchInfo.startStr.split('T')[0];
                    const endDate   = fetchInfo.endStr.split('T')[0];
                    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

                    console.log('Events-Fetch gestartet – Zeitraum:', startDate, 'bis', endDate);
                    console.log('Ausgewählte Kalender (Fallback):', window.selectedCalendars || 'NOCH NICHT GESETZT');

                    try {
                        const response = await fetch('/api/method/diakronos.kronos.api.calendar_get.get_calendar_events', {
                            method: 'POST',
                            credentials: 'include',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-Frappe-CSRF-Token': csrfToken
                            },
                            body: JSON.stringify({
                                start_date: startDate,
                                end_date: endDate,
                                calendar_filter: JSON.stringify(window.selectedCalendars || [])  // Fallback leer → alle erlaubten
                            })
                        });

                        if (!response.ok) throw new Error(await response.text());

                        const result = await response.json();
                        const events = result.message || result || [];
                        console.log('Gefetchte Events:', events.length, events);

                        successCallback(events);
                    } catch (err) {
                        console.error('❌ Events Fetch Fehler:', err);
                        failureCallback(err);
                    }
                },
                // Callbacks
//                datesSet: (info) => {
//                    console.log('📆 Datum-Range aktualisiert:', {
//                        start: info.startStr,
//                        end: info.endStr,
//                        view: info.view.type
//                    });
//                    if (window.kronosMiniCalendar) {
//                        window.kronosMiniCalendar.syncWithMain();
//                    }
//                },
                dateClick: (info) => {
                    console.log('📅 Datum geklickt:', info.dateStr);
                    KronosCreateDialog.showCreateDialog(info.dateStr);
                },
                eventClick: (info) => {
                    console.log('🔍 Event geklickt:', info.event.id);
                    KronosEventClickHandler.showEventClickDialog(info.event);
                },
                eventDrop: (info) => {
                    console.log('📦 Event verschoben:', info.event.id);
                    KronosEvents.updateEvent(info.event);
                },
                eventResize: (info) => {
                    console.log('📏 Event resized:', info.event.id);
                    KronosEvents.updateEvent(info.event);
                },
                select: (info) => {
                    console.log('🗓️ Bereich ausgewählt:', info.startStr);
                    KronosCreateDialog.showCreateDialog(info.startStr);
                }
            });

            // Automatisches Kalender-Resize NACH Abschluss der Sidebar-Transition
            const sidebar = document.querySelector('.kronos-sidebar');

            if (sidebar && window.kronosCalendar && window.kronosCalendar.calendar) {
            // Einmaliger Listener für jedes Transition-Ende
            sidebar.addEventListener('transitionend', (event) => {
                // Nur reagieren, wenn wirklich die width animiert wurde
                if (event.propertyName === 'width') {
                window.kronosCalendar.calendar.updateSize();
                //console.log('✅ Kalender resized NACH Sidebar-Transition-Ende');
                }
            });

//            console.log('✅ transitionend-Listener auf Sidebar aktiviert');
//            } else {
//            console.warn('⚠️ transitionend-Listener konnte nicht gestartet werden');
            }
            this.calendar.render();
            console.log('✅ kronos_calendar_render: Kalender erfolgreich gerendert');
            // Innerhalb von kronos_calendar_init, nach calendar.render()
            // Header-Pfeile verknüpfen
            const dateDisplay = document.getElementById('current-date-display');
            const prevBtn = document.querySelector('.prev-month');
            const nextBtn = document.querySelector('.next-month');
            const updateDateDisplay = () => {
                if (dateDisplay) {
                    dateDisplay.textContent = this.calendar.view.title;
                }
            };
            this.calendar.on('datesSet', updateDateDisplay);
            updateDateDisplay();
            if (prevBtn) {
                prevBtn.addEventListener('click', () => this.calendar.prev());
            }
            if (nextBtn) {
                nextBtn.addEventListener('click', () => this.calendar.next());
            }
//            console.log('✅ Eigene Header-Pfeile verknüpft');
            // Forciere Höhe auf 100%
            calendarEl.style.height = '100%';
            this.calendar.updateSize();
            setTimeout(() => {
                const fc = document.querySelector('.fc');
                console.log('FC AFTER INIT HEIGHT:', fc.offsetHeight);
                console.log('FC STYLE.HEIGHT:', fc.style.height);
                console.log('CALENDAR EL HEIGHT:', calendarEl.offsetHeight);
            }, 100);
        } catch (error) {
            console.error('❌ Fehler beim Initialisieren:', error);
            console.error(' Stack:', error.stack);
            return null;
        }
    }

    // =========================================================================
    // HELPER METHODEN
    // =========================================================================

    /**
     * Events neu laden (z.B. nach Änderungen)
     */
    refetchEvents() {
        if (this.calendar) {
            this.calendar.refetchEvents();
//            console.log('🔄 Events refetched');
        } else {
            console.warn('⚠️ Calendar nicht initialisiert');
        }
    }

    /**
     * Zur bestimmtem Datum springen
     */
    gotoDate(dateStr) {
        if (this.calendar) {
            this.calendar.gotoDate(dateStr);
//            console.log('➡️ Sprung zu:', dateStr);
        }
    }

    /**
     * View wechseln
     */
    changeView(viewName) {
        if (this.calendar) {
            this.calendar.changeView(viewName);
//            console.log('👁️ View gewechselt zu:', viewName);
        }
    }

    /**
     * Aktuelles View ermitteln
     */
    getCurrentView() {
        return this.calendar ? this.calendar.view : null;
    }

    /**
     * Heute anzeigen
     */
    today() {
        if (this.calendar) {
            this.calendar.today();
//            console.log('🏠 Heute angezeigt');
        }
    }
    
}

window.kronosCalendar = new KronosCalendar();
window.kronosCalendar.kronos_calendar_init();

console.log('kronosCalendar Instanz gesetzt:', window.kronosCalendar);