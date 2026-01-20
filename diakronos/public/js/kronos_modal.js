/**
 * ═══════════════════════════════════════════════════════════════
 * KRONOS CALENDAR - MODAL MODULE (REFACTORED - MODULAR)
 * ═══════════════════════════════════════════════════════════════
 * 
 * Entry Point für alle Modal-Funktionen
 * Lädt alle Sub-Module und stellt unified API bereit
 * 
 * DEPENDENCIES (in dieser Reihenfolge):
 * 1. modal_helpers.js
 * 2. modal_base.js
 * 3. modal_event_click.js
 * 4. modal_smart_edit.js
 * 5. modal_series_handler.js
 * 6. modal_create_dialog.js
 * 7. kronos_modal.js (diese Datei)
 */

class KronosModal {
    
    /**
     * 🏗️ INITIALIZE
     * Wird aufgerufen wenn Kalender geladen wird
     */
    static init() {
        console.log('🚀 KronosModal initialisieren...');
        
        // Prüfe ob alle Dependencies geladen sind
        const requiredModules = [
            'KronosModalHelpers',
            'KronosModalBase',
            'KronosEventClickHandler',
            'KronosSmartEditDialog',
            'KronosSeriesHandler',
            'KronosCreateDialog'
        ];
        
        const missingModules = requiredModules.filter(m => !window[m]);
        
        if (missingModules.length > 0) {
            console.error('❌ Fehlende Module:', missingModules);
            console.error('⚠️ Stellen Sie sicher, dass alle Modal-Module geladen sind!');
            return false;
        }
        
        console.log('✅ Alle Module geladen');
        
        // Lade CSS Animations
        KronosModal._loadStyles();
        
        // Setze Global Functions
        window.KronosModal = KronosModal;
        
        console.log('✅ KronosModal ready');
        return true;
    }
    
    /**
     * 💬 PUBLIC API - diese Funktionen werden von außen aufgerufen
     */
    
    /**
     * 🖱️ Wird aufgerufen wenn User auf Termin klickt
     */
    static showEventClickDialog(eventData) {
        KronosEventClickHandler.showEventClickDialog(eventData);
    }
    
    /**
     * ✨ Wird aufgerufen wenn User neuen Termin erstellen will
     */
    static showCreateDialog(dateStr) {
        KronosCreateDialog.showCreateDialog(dateStr);
    }
    
    /**
     * 🎯 Direkter Zugriff auf Edit Dialog (für erweiterte Nutzung)
     */
    static showSmartEditDialog(element, options) {
        KronosSmartEditDialog.showSmartEditDialog(element, options);
    }
    
    /**
     * 📺 Direkter Zugriff auf Series Handler (für erweiterte Nutzung)
     */
    static showSeriesHandler(element) {
        KronosSeriesHandler.showSeriesHandler(element);
    }
    
    /**
     * 🎛️ PRIVATE - STYLE LOADING
     */
    static _loadStyles() {
        if (document.getElementById('kronos-modal-styles')) {
            console.log('ℹ️ Modal Styles bereits geladen');
            return;
        }
        
        const style = document.createElement('style');
        style.id = 'kronos-modal-styles';
        style.textContent = `
            /* ═══════════════════════════════════════════════════════ */
            /* MODAL ANIMATIONS */
            /* ═══════════════════════════════════════════════════════ */
            
            @keyframes slideUp {
                from {
                    opacity: 0;
                    transform: translateY(20px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            /* ═══════════════════════════════════════════════════════ */
            /* BUTTON STATES */
            /* ═══════════════════════════════════════════════════════ */
            
            #smart-save {
                transition: background-color 0.2s ease-out !important;
            }
            
            #smart-save:hover {
                background-color: #1967d2 !important;
            }
            
            #smart-cancel:hover {
                background-color: #efefef !important;
            }
            
            #event-save {
                transition: background-color 0.2s ease-out !important;
            }
            
            #event-save:hover {
                background-color: #1967d2 !important;
            }
            
            #event-cancel:hover {
                background-color: #f5f5f5 !important;
            }
            
            #smart-delete:hover {
                background-color: #ffcdd2 !important;
            }
            
            #series-cancel:hover {
                background-color: #efefef !important;
            }
            
            /* ═══════════════════════════════════════════════════════ */
            /* SERIES OPTIONS */
            /* ═══════════════════════════════════════════════════════ */
            
            .series-option {
                cursor: pointer;
            }
            
            .series-option:hover {
                box-shadow: 0 4px 8px rgba(0,0,0,0.1) !important;
            }
            
            /* ═══════════════════════════════════════════════════════ */
            /* FORM INPUTS */
            /* ═══════════════════════════════════════════════════════ */
            
            input[type="text"]:focus,
            input[type="datetime-local"]:focus,
            input[type="date"]:focus,
            textarea:focus,
            select:focus {
                border-color: #1f73e6 !important;
                outline: 2px solid rgba(31, 115, 230, 0.1) !important;
            }
            
            /* ═══════════════════════════════════════════════════════ */
            /* CHECKBOX STYLING */
            /* ═══════════════════════════════════════════════════════ */
            
            input[type="checkbox"] {
                accent-color: #1f73e6;
                cursor: pointer;
            }
        `;
        
        document.head.appendChild(style);
        console.log('✅ Modal Styles geladen');
    }
}

// ═════════════════════════════════════════════════
// AUTO-INIT (wenn dieses Script geladen wird)
// ═════════════════════════════════════════════════

// Warte kurz, damit alle Dependencies geladen sind
setTimeout(() => {
    KronosModal.init();
}, 100);

console.log('✅ Modal Modul geladen (REFACTORED - MODULAR)');
console.log('🌍 window.KronosModal verfügbar:', typeof window.KronosModal);
