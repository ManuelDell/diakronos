/**
 * ═══════════════════════════════════════════════════════════════
 * KRONOS CALENDAR - EVENTS MODULE
 * ═══════════════════════════════════════════════════════════════
 */

class KronosEvents {
    
    static updateEvent(event) {
        console.log('🔄 Aktualisiere Event:', event.id);
        
        frappe.call({
            method: 'diakronos.kronos.api.tui_management.event_update_from_tui',
            args: {
                name: event.id,
                title: event.title,
                start: event.start?.toISOString(),
                end: event.end?.toISOString(),
                calendar_id: 'Standard',
                is_all_day: event.allDay || false
            },
            callback: () => {
                frappe.show_alert({message: '✅ Termin aktualisiert', indicator: 'green'});
                window.kronosCalendar.refetchEvents();
            },
            error: (err) => {
                console.error('❌ Fehler beim Update:', err);
                frappe.show_alert({message: '❌ Fehler beim Aktualisieren', indicator: 'red'});
            }
        });
    }

    static createEvent(title, start, end) {
        console.log('➕ Erstelle Event:', {title, start, end});
        
        frappe.call({
            method: 'diakronos.kronos.api.tui_management.event_create_from_tui',
            args: {
                title: title,
                start: start,
                end: end || start,
                calendar_id: 'Standard',
                is_all_day: false
            },
            callback: () => {
                window.kronosCalendar.refetchEvents();
                frappe.show_alert({message: '✅ Termin erstellt', indicator: 'green'});
                console.log('✅ Event erfolgreich erstellt!');
            },
            error: (err) => {
                console.error('❌ Fehler beim Erstellen:', err);
                frappe.show_alert({message: '❌ Fehler beim Erstellen', indicator: 'red'});
            }
        });
    }

    static deleteEvent(eventId) {
        console.log('🗑️ Lösche Event:', eventId);
        
        frappe.call({
            method: 'diakronos.kronos.api.events.delete_event',
            args: {
                name: eventId
            },
            callback: () => {
                window.kronosCalendar.refetchEvents();
                frappe.show_alert({message: '✅ Termin gelöscht', indicator: 'green'});
            },
            error: (err) => {
                console.error('❌ Fehler beim Löschen:', err);
                frappe.show_alert({message: '❌ Fehler beim Löschen', indicator: 'red'});
            }
        });
    }
}

console.log('✅ Events Modul geladen');
