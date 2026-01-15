/**
 * ═══════════════════════════════════════════════════════════════
 * KRONOS CALENDAR - CALENDAR MODULE MIT SERIENTERMIN
 * ═══════════════════════════════════════════════════════════════
 * Verwaltet die FullCalendar Integration und Event-Handling
 * MIT: Modal-Dialog für Element-Erstellung mit Serientermin-Feldern
 * 
 * ⚠️ KRITISCH: Alle DateTime-Handling MUSS LOCAL sein!
 * 🔧 TIMEZONE-FIX: datetime-local gibt bereits LOCAL Zeit zurück
 * 🧹 CACHE-FIX: cache: false + refetchEvents() (moderne Frappe)
 */



class KronosCalendar {
    constructor() {
        this.calendar = null;
        this.currentFormData = null;
        this.calendarColors = {};
        console.log('📅 KronosCalendar Module geladen');
    }



    init() {
        const calendarEl = document.getElementById('calendar');
        if (!calendarEl) {
            console.error('❌ #calendar element nicht gefunden!');
            return;
        }


        console.log('🎯 Initialisiere FullCalendar...');
        
        const options = {
            headerToolbar: false,
            initialView: 'dayGridMonth',
            locale: 'de',
            firstDay: 1,
            dayMaxEvents: 3,
            height: '100%',
            contentHeight: '100%',


            events: (info, successCallback, failureCallback) => {
                this.loadEvents(info, successCallback, failureCallback);
            },


            eventDidMount: (info) => {
                this.styleEvent(info);
            },


            editable: true,
            
            eventDrop: (info) => {
                const elementId = ElementExtractId.fromEvent(info.event);
                
                console.group('📍 EVENT DROP');
                console.log('Extracted ID:', elementId);
                console.log('Neue Zeit:', info.event.start);
                
                if (!ElementExtractId.isValid(elementId)) {
                    console.error('❌ Ungültige Event-ID!');
                    console.groupEnd();
                    frappe.show_alert({
                        message: '❌ Fehler: Event-ID konnte nicht ermittelt werden',
                        indicator: 'red'
                    });
                    info.revert();  // ← KRITISCH: Event zurückspringen wenn ungültig
                    return;
                }
                
                // ✅ SIMPEL: Nimm die Zeit direkt, konvertiere zu String
                const startStr = this.formatDateForBackend(info.event.start);
                const endStr = this.formatDateForBackend(info.event.end || info.event.start);
                
                console.log('Start → Backend:', startStr);
                console.log('End → Backend:', endStr);
                console.log('✅ Sende Update...');
                console.groupEnd();
                
                frappe.call({
                    method: 'diakronos.kronos.api.event_crud.update_event',
                    args: {
                        'name': elementId,
                        'element_start': startStr,
                        'element_end': endStr
                    },
                    cache: false,  // ← KRITISCH: Nicht cachen!
                    callback: (r) => {
                        if (r.exc) {
                            console.error('❌ Update fehlgeschlagen:', r.exc);
                            frappe.show_alert({
                                message: '❌ Fehler beim Verschieben',
                                indicator: 'red'
                            });
                            info.revert();  // ← KRITISCH: info.revert() bei Fehler!
                        } else {
                            console.log('✅ Event erfolgreich verschoben');
                            frappe.show_alert({
                                message: '✅ Termin aktualisiert',
                                indicator: 'green'
                            });
                            this.refetchEvents();  // ← Events neuladen!
                        }
                    },
                    error: (err) => {
                        console.error('❌ Frappe Call Fehler:', err);
                        frappe.show_alert({
                            message: '❌ Fehler beim Verschieben',
                            indicator: 'red'
                        });
                        info.revert();  // ← KRITISCH: info.revert() im error-handler!
                    }
                });
            },


            eventResize: (info) => {
                const elementId = ElementExtractId.fromEvent(info.event);
                
                console.group('📏 EVENT RESIZE');
                console.log('Extracted ID:', elementId);
                
                if (!ElementExtractId.isValid(elementId)) {
                    console.error('❌ Ungültige Event-ID!');
                    console.groupEnd();
                    frappe.show_alert({
                        message: '❌ Fehler: Event-ID konnte nicht ermittelt werden',
                        indicator: 'red'
                    });
                    info.revert();  // ← KRITISCH: Event zurückspringen wenn ungültig
                    return;
                }
                
                // ✅ SIMPEL: Direkt formatieren
                const startStr = this.formatDateForBackend(info.event.start);
                const endStr = this.formatDateForBackend(info.event.end || info.event.start);
                
                console.log('Start → Backend:', startStr);
                console.log('✅ Sende Update...');
                console.groupEnd();
                
                frappe.call({
                    method: 'diakronos.kronos.api.event_crud.update_event',
                    args: {
                        'name': elementId,
                        'element_start': startStr,
                        'element_end': endStr
                    },
                    cache: false,  // ← KRITISCH: Nicht cachen!
                    callback: (r) => {
                        if (r.exc) {
                            console.error('❌ Update fehlgeschlagen:', r.exc);
                            frappe.show_alert({
                                message: '❌ Fehler beim Vergrößern',
                                indicator: 'red'
                            });
                            info.revert();  // ← KRITISCH: info.revert() bei Fehler!
                        } else {
                            console.log('✅ Event erfolgreich vergrößert');
                            frappe.show_alert({
                                message: '✅ Termin vergrößert',
                                indicator: 'green'
                            });
                            this.refetchEvents();  // ← Events neuladen!
                        }
                    },
                    error: (err) => {
                        console.error('❌ Frappe Call Fehler:', err);
                        frappe.show_alert({
                            message: '❌ Fehler beim Vergrößern',
                            indicator: 'red'
                        });
                        info.revert();  // ← KRITISCH: info.revert() im error-handler!
                    }
                });
            },


            eventClick: (info) => {
                const elementId = ElementExtractId.fromEvent(info.event);
                
                if (ElementExtractId.isValid(elementId)) {
                    console.log('🖱️ Event geklickt:', elementId);
                    // ✅ RICHTIG: Rufe KronosModal auf statt zu navigieren
                    KronosModal.showEventClickDialog({
                        id: elementId,
                        title: info.event.title,
                        start: info.event.start,
                        end: info.event.end
                    });
                }
            },


            
            dateClick: (info) => {
                console.log('📅 dateClick triggered:', info.dateStr);
                this.handleDateClick(info);
            }
        };


        try {
            this.calendar = new FullCalendar.Calendar(calendarEl, options);
            this.calendar.render();
            console.log('✅ FullCalendar gerendert!');


            setTimeout(() => {
                this.calendar.updateSize();
                console.log('✅ Calendar Size updated');
            }, 100);
        } catch (e) {
            console.error('❌ Fehler beim Initialisieren:', e.message);
        }
    }



    handleDateClick(info) {
        console.log('🔐 Prüfe Schreibrechte...');
        
        frappe.call({
            method: 'diakronos.kronos.api.permissions.can_create_event',
            cache: false,  // ← WICHTIG: Nicht cachen!
            callback: (r) => {
                console.log('📋 Berechtigung-Response:', r.message);
                
                if (r.message && r.message.can_create) {
                    console.log('✅ User darf erstellen');
                    this.openQuickEntry(info.dateStr, r.message);
                } else {
                    console.log('🔒 User hat kein Schreibrecht');
                    frappe.show_alert({
                        message: '🔒 Du hast keine Berechtigung, Termine zu erstellen',
                        indicator: 'orange'
                    });
                }
            },
            error: (err) => {
                console.error('❌ Fehler bei Berechtigungsprüfung:', err);
                frappe.show_alert({
                    message: '❌ Fehler bei der Berechtigungsprüfung',
                    indicator: 'red'
                });
            }
        });
    }



    openQuickEntry(dateStr, permissionData) {
        console.log('📝 Öffne Create Dialog via modal_create_dialog.js');
        
        // ✅ Rufe die externe Modal-Datei auf
        if (window.KronosModal && window.KronosModal.showCreateDialog) {
            window.KronosModal.showCreateDialog(dateStr, permissionData);
        } else {
            console.error('❌ KronosModal nicht geladen!');
            frappe.show_alert({
                message: '❌ Modal-System nicht verfügbar',
                indicator: 'red'
            });
        }
    }






    formatDatetimeLocal(datetimeStr) {
        // INPUT: "2026-01-16 08:00:00" (vom Backend, in lokaler Zeit gespeichert)
        // OUTPUT: "2026-01-16T08:00" (für datetime-local Input)
        if (!datetimeStr) return '';
        
        // Parse als lokale Zeit (Backend speichert bereits in lokaler Zeit)
        const parts = datetimeStr.split(' ');
        const date = parts[0]; // "2026-01-16"
        const time = parts[1] ? parts[1].substring(0, 5) : '00:00'; // "08:00"
        
        console.log(`📤 formatDatetimeLocal: ${datetimeStr} → ${date}T${time}`);
        
        return `${date}T${time}`;
    }



    formatDateForBackend(dateObj) {
        // ✅ Einfach: JavaScript Date → "YYYY-MM-DD HH:MM:SS" Format
        // FullCalendar gibt bereits lokale Zeit zurück, keine Konvertierung nötig!
        if (!dateObj) return null;
        
        const year = dateObj.getFullYear();
        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
        const day = String(dateObj.getDate()).padStart(2, '0');
        const hours = String(dateObj.getHours()).padStart(2, '0');
        const minutes = String(dateObj.getMinutes()).padStart(2, '0');
        const seconds = String(dateObj.getSeconds()).padStart(2, '0');
        
        const formatted = `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
        console.log(`📤 formatDateForBackend: ${dateObj} → ${formatted}`);
        return formatted;
    }


    loadEvents(info, successCallback, failureCallback) {
        console.group('🔍 CACHE DEBUG');
        console.log('Start:', info.startStr);
        console.log('End:', info.endStr);
        
        // Prüf ob localStorage gecacht hat
        const storedEvents = localStorage.getItem('kronos_cached_events');
        if (storedEvents) {
            console.warn('⚠️ localStorage hat gecachte Events:', storedEvents.substring(0, 100));
        }
        console.groupEnd();
        
        const startDate = info.startStr.split('T')[0];
        const endDate = info.endStr.split('T')[0];
        
        console.log(`📅 Loading events: ${startDate} → ${endDate}`);
        
        frappe.call({
            method: 'diakronos.kronos.api.calendar_get.get_calendar_events',
            args: {
                start_date: startDate,
                end_date: endDate,
                calendar_filter: '[]'
            },
            cache: false,  // ← KRITISCH: Nie cachen!
            callback: (r) => {
                const events = (r.message || []).map(e => this.mapEvent(e));
                console.log(`✅ ${events.length} Events geladen`);
                successCallback(events);
            },
            error: (err) => {
                console.error('❌ API Error:', err);
                successCallback([]);
            }
        });
    }



    mapEvent(e) {
        return {
            id: e.id,
            title: e.title,
            start: e.start,
            end: e.end || e.start,
            backgroundColor: e.backgroundColor || e.color || '#1f73e6',
            borderColor: 'transparent',
            textColor: '#fff',
            allDay: e.isAllday || false,
            extendedProps: {
                name: e.id,
                calendar: e.calendar,
                calendarColor: e.color
            }
        };
    }



    styleEvent(info) {
        if (info.event.backgroundColor) {
            info.el.style.backgroundColor = info.event.backgroundColor;
            info.el.style.color = '#fff';
            info.el.style.borderColor = 'transparent';
        }
    }



    changeView(view) {
        this.calendar?.changeView(view);
    }



    prev() {
        this.calendar?.prev();
    }



    next() {
        this.calendar?.next();
    }



    today() {
        this.calendar?.today();
    }



    getDate() {
        return this.calendar?.getDate() || new Date();
    }



    refetchEvents() {
        console.log('🔄 Lade Events neu...');
        this.calendar?.refetchEvents();
    }
}



window.kronosCalendar = new KronosCalendar();
console.log('✅ Calendar Modul initialisiert');