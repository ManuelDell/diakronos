/**
 * ═══════════════════════════════════════════════════════════════
 * KRONOS CALENDAR - EVENTS MODULE
 * ═══════════════════════════════════════════════════════════════
 * KRITISCHE FIXES:
 * ✅ cache: false überall hinzugefügt
 * ✅ formatDateForBackend() statt toISOString()
 * ✅ error-Handler in ALLEN Methoden
 * ✅ Validierung vor API-Calls
 * ✅ Korrekte Frappe API-Methodennamen
 * ✅ force: true bei deleteEvent()
 */


class KronosEvents {
    
    /**
     * Aktualisiere einen Event
     * ✅ RICHTIG: Verwendet formatDateForBackend() für UTC-Konvertierung
     * ✅ RICHTIG: hat error-Handler
     * ✅ RICHTIG: cache: false
     */
    static updateEvent(event) {
        console.log('🔄 Aktualisiere Event:', event.id);
        
        // 🔐 VALIDIERUNG
        if (!event || !event.id) {
            console.error('❌ Event.id erforderlich');
            frappe.show_alert({ 
                message: '❌ Event-ID fehlt', 
                indicator: 'red' 
            });
            return;
        }
        
        if (!event.start || !event.end) {
            console.error('❌ Start- und Enddatum erforderlich');
            frappe.show_alert({ 
                message: '❌ Start- und Enddatum erforderlich', 
                indicator: 'red' 
            });
            return;
        }
        
        // 🔧 KORREKTE KONVERTIERUNG: formatDateForBackend() verwenden!
        const startStr = window.kronosCalendar.formatDateForBackend(event.start);
        const endStr = window.kronosCalendar.formatDateForBackend(event.end);
        
        console.log('📤 Sende Update mit UTC-Konvertierung:', { startStr, endStr });
        
        frappe.call({
            method: 'diakronos.kronos.api.event_crud.update_event',
            args: {
                'name': event.id,
                'element_name': event.title,
                'element_start': startStr,  // ✅ UTC Format!
                'element_end': endStr,      // ✅ UTC Format!
                'element_calendar': event.calendarId || 'Standard'
            },
            cache: false,  // ← KRITISCH: Nicht cachen!
            callback: (r) => {
                if (r.message) {
                    console.log('✅ Event aktualisiert:', r.message.name);
                    frappe.show_alert({
                        message: '✅ Termin aktualisiert',
                        indicator: 'green'
                    });
                    window.kronosCalendar.refetchEvents();
                } else if (r.exc) {
                    console.error('❌ Update fehlgeschlagen:', r.exc);
                    frappe.show_alert({
                        message: '❌ Fehler beim Aktualisieren',
                        indicator: 'red'
                    });
                }
            },
            error: (err) => {
                console.error('❌ Frappe Call Fehler:', err);
                frappe.show_alert({
                    message: '❌ Fehler beim Aktualisieren',
                    indicator: 'red'
                });
            }
        });
    }


    /**
     * Erstelle einen neuen Event
     * ✅ RICHTIG: Validiert Eingaben
     * ✅ RICHTIG: error-Handler
     * ✅ RICHTIG: cache: false
     */
    static createEvent(title, start, end) {
        console.log('➕ Erstelle Event:', { title, start, end });
        
        // 🔐 VALIDIERUNG
        if (!title || title.trim() === '') {
            console.error('❌ Titel erforderlich');
            frappe.show_alert({
                message: '❌ Titel erforderlich',
                indicator: 'red'
            });
            return;
        }
        
        if (!start) {
            console.error('❌ Startdatum erforderlich');
            frappe.show_alert({
                message: '❌ Startdatum erforderlich',
                indicator: 'red'
            });
            return;
        }
        
        // 🔧 KORREKTE KONVERTIERUNG
        const startStr = window.kronosCalendar.formatDateForBackend(start);
        const endStr = end ? window.kronosCalendar.formatDateForBackend(end) : startStr;
        
        console.log('📤 Sende Create mit UTC-Konvertierung:', { title, startStr, endStr });
        
        // Baue Element-Objekt (EXAKT wie in kronoscalendar.js)
        const docData = {
            doctype: 'Element',
            element_name: title,
            element_calendar: 'Standard',
            element_start: startStr,    // ✅ UTC Format!
            element_end: endStr,        // ✅ UTC Format!
            repeatthisevent: 0,
            repeaton: 'Weekly'
        };
        
        frappe.call({
            method: 'frappe.client.insert',
            args: {
                doc: docData
            },
            cache: false,  // ← KRITISCH: Nicht cachen!
            callback: (r) => {
                if (r.message) {
                    console.log('✅ Element erstellt:', r.message.name);
                    frappe.show_alert({
                        message: `✅ Termin "${title}" erfolgreich erstellt!`,
                        indicator: 'green'
                    });
                    window.kronosCalendar.refetchEvents();
                } else if (r.exc) {
                    console.error('❌ Erstellen fehlgeschlagen:', r.exc);
                    frappe.show_alert({
                        message: '❌ Fehler beim Erstellen',
                        indicator: 'red'
                    });
                }
            },
            error: (err) => {
                console.error('❌ Frappe Call Fehler:', err);
                frappe.show_alert({
                    message: '❌ Fehler beim Erstellen',
                    indicator: 'red'
                });
            }
        });
    }


    /**
     * Lösche einen Event
     * ✅ RICHTIG: force: true für sichere Löschung
     * ✅ RICHTIG: error-Handler
     * ✅ RICHTIG: cache: false
     * ✅ RICHTIG: Validierung
     */
    static deleteEvent(eventId) {
        console.log('🗑️ Lösche Event:', eventId);
        
        // 🔐 VALIDIERUNG
        if (!eventId) {
            console.error('❌ Event-ID erforderlich');
            frappe.show_alert({
                message: '❌ Event-ID erforderlich',
                indicator: 'red'
            });
            return;
        }
        
        // 🔒 BESTÄTIGUNG
        frappe.confirm(
            '⚠️ Termin wirklich löschen?',
            () => {
                frappe.call({
                    method: 'frappe.client.delete',
                    args: {
                        doctype: 'Element',
                        name: eventId,
                        force: true  // ← KRITISCH: force-Delete!
                    },
                    cache: false,  // ← KRITISCH: Nicht cachen!
                    callback: (r) => {
                        if (r.message) {
                            console.log('✅ Event gelöscht:', eventId);
                            frappe.show_alert({
                                message: '✅ Termin gelöscht',
                                indicator: 'green'
                            });
                            window.kronosCalendar.refetchEvents();
                        } else if (r.exc) {
                            console.error('❌ Löschen fehlgeschlagen:', r.exc);
                            frappe.show_alert({
                                message: '❌ Fehler beim Löschen',
                                indicator: 'red'
                            });
                        }
                    },
                    error: (err) => {
                        console.error('❌ Frappe Call Fehler:', err);
                        frappe.show_alert({
                            message: '❌ Fehler beim Löschen',
                            indicator: 'red'
                        });
                    }
                });
            }
        );
    }
}


console.log('✅ Events Modul geladen (mit Fixes)');