// modal_event_click.js – kleiner Fix für v6 Event-Objekt (id aus event.id, extendedProps)

class KronosEventClickHandler {
    
    static showEventClickDialog(eventData) {
        console.log('🔍 Event geklickt:', eventData);
        
        if (!eventData || !eventData.id) {
            console.error('❌ Ungültige Event-Daten');
            return;
        }
        
        // Lade komplette Element-Daten vom Backend
        frappe.call({
            method: 'frappe.client.get',
            args: {
                doctype: 'Element',
                name: eventData.id  // v6: eventData.id ist der Name
            },
            callback: (r) => {
                if (r.message) {
                    const element = r.message;
                    console.log('📋 Element Daten geladen:', element);
                    
                    const isSeriesInstance = !!element.series_id;
                    console.log('📺 isSeriesInstance:', isSeriesInstance);
                    
                    if (isSeriesInstance) {
                        KronosSeriesHandler.showSeriesHandler(element);
                    } else {
                        KronosSmartEditDialog.showSmartEditDialog(element, {
                            action: 'edit_single',
                            title: 'Termin bearbeiten',
                            editableFields: ['element_name', 'description', 'element_start', 'element_end'],
                            showDelete: true
                        });
                    }
                } else {
                    KronosModalHelpers.showError('Event konnte nicht geladen werden');
                }
            },
            error: (err) => {
                console.error('❌ Fehler beim Laden:', err);
                KronosModalHelpers.showError('Fehler beim Laden des Events');
            }
        });
    }
}

// Export
window.KronosEventClickHandler = KronosEventClickHandler;
console.log('✅ Event Click Handler geladen');