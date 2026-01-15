/**
 * ═══════════════════════════════════════════════════════════════
 * KRONOS MODAL - EVENT CLICK HANDLER
 * ═══════════════════════════════════════════════════════════════
 */

class KronosEventClickHandler {
    
    /**
     * 🖱️ EVENT CLICK HANDLER
     * Wird aufgerufen wenn User auf einen Termin klickt
     */
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
                name: eventData.id
            },
            callback: (r) => {
                if (r.message) {
                    const element = r.message;
                    console.log('📋 Element Daten geladen:', element);
                    
                    // Prüfe ob Serientermin
                    const isSeriesInstance = !!element.series_id;
                    console.log('📺 isSeriesInstance:', isSeriesInstance);
                    
                    if (isSeriesInstance) {
                        // Öffne Serie-Handler
                        KronosSeriesHandler.showSeriesHandler(element);
                    } else {
                        // Öffne Edit Dialog für normale Termine
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
