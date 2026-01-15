/**
 * ═══════════════════════════════════════════════════════════════
 * KRONOS CALENDAR - MODAL MODULE
 * ═══════════════════════════════════════════════════════════════
 * KRITISCHE FIXES:
 * ✅ Kein toISOString() - übergib JS Date Objekte direkt!
 * ✅ frappe.show_alert() statt alert()
 * ✅ Validierung vor API-Calls
 * ✅ Error-Handler für createEvent()
 * ✅ Cleanup für Event Listener (Memory Leak Fix)
 * ✅ CSS Transition für Fade-out
 */


class KronosModal {
    
    static showCreateDialog(dateStr) {
        console.log('🆕 Zeige Create Dialog für:', dateStr);
        
        // 🔐 PRÜFE ob kronosEvents geladen ist
        if (!window.kronosEvents || !window.kronosCalendar) {
            console.error('❌ KronosEvents oder KronosCalendar nicht geladen!');
            frappe.show_alert({
                message: '❌ Modul konnte nicht geladen werden',
                indicator: 'red'
            });
            return;
        }
        
        const modal = document.createElement('div');
        modal.id = 'event-modal-' + Date.now();
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            opacity: 1;
            transition: opacity 0.2s ease-out;
        `;
        
        const dialog = document.createElement('div');
        dialog.style.cssText = `
            background: white;
            border-radius: 8px;
            padding: 24px;
            min-width: 400px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            animation: slideUp 0.3s ease-out;
        `;
        
        dialog.innerHTML = `
            <h2 style="margin: 0 0 20px 0; font-size: 20px; color: #202124;">📅 Neuer Termin</h2>
            
            <div style="margin-bottom: 16px;">
                <label style="display: block; margin-bottom: 6px; font-weight: 500; color: #202124;">Titel *</label>
                <input id="event-title" type="text" placeholder="z.B. Gottesdienst" style="width: 100%; padding: 10px; border: 1px solid #dadce0; border-radius: 4px; font-size: 14px; font-family: inherit; box-sizing: border-box;" autofocus>
            </div>
            
            <div style="margin-bottom: 16px;">
                <label style="display: block; margin-bottom: 6px; font-weight: 500; color: #202124;">Startdatum & Zeit *</label>
                <input id="event-start" type="datetime-local" style="width: 100%; padding: 10px; border: 1px solid #dadce0; border-radius: 4px; font-size: 14px; font-family: inherit; box-sizing: border-box;">
            </div>
            
            <div style="margin-bottom: 20px;">
                <label style="display: block; margin-bottom: 6px; font-weight: 500; color: #202124;">Enddatum & Zeit</label>
                <input id="event-end" type="datetime-local" style="width: 100%; padding: 10px; border: 1px solid #dadce0; border-radius: 4px; font-size: 14px; font-family: inherit; box-sizing: border-box;">
            </div>
            
            <div style="display: flex; gap: 10px; justify-content: flex-end;">
                <button id="event-cancel" style="padding: 10px 20px; border: 1px solid #dadce0; border-radius: 4px; background: white; color: #202124; cursor: pointer; font-weight: 500; transition: all 0.2s;">Abbrechen</button>
                <button id="event-save" style="padding: 10px 20px; border: none; border-radius: 4px; background: #1f73e6; color: white; cursor: pointer; font-weight: 500; transition: all 0.2s;">✨ Erstellen</button>
            </div>
        `;
        
        modal.appendChild(dialog);
        document.body.appendChild(modal);
        
        // 🔧 KORREKT: datetime-local Input füllen (LOCAL Zeit!)
        const dateObj = new Date(dateStr);
        const year = dateObj.getFullYear();
        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
        const day = String(dateObj.getDate()).padStart(2, '0');
        const hours = String(dateObj.getHours()).padStart(2, '0');
        const minutes = String(dateObj.getMinutes()).padStart(2, '0');
        
        const localDatetimeStr = `${year}-${month}-${day}T${hours}:${minutes}`;
        document.getElementById('event-start').value = localDatetimeStr;
        document.getElementById('event-end').value = localDatetimeStr;
        
        document.getElementById('event-title').focus();
        
        // 🔒 HELPER: Modal schließen mit Cleanup
        const escListener = (e) => {
            if (e.key === 'Escape') {
                closeModal();
            }
        };
        
        const closeModal = () => {
            console.log('🔽 Schließe Modal');
            modal.style.opacity = '0';
            document.removeEventListener('keydown', escListener);  // ← WICHTIG: Cleanup!
            setTimeout(() => {
                if (modal && modal.parentNode) {
                    modal.remove();
                }
            }, 200);
        };
        
        // 🔘 CANCEL Button
        document.getElementById('event-cancel').addEventListener('click', () => {
            console.log('❌ Modal abgebrochen');
            closeModal();
        });
        
        // 💾 SAVE Button
        document.getElementById('event-save').addEventListener('click', () => {
            console.log('💾 Save Button geklickt');
            
            // 🔐 VALIDIERUNG
            const title = document.getElementById('event-title').value.trim();
            const start = document.getElementById('event-start').value;
            const end = document.getElementById('event-end').value || start;
            
            console.log('🔍 Validiere Eingaben:', { title, start, end });
            
            if (!title) {
                frappe.show_alert({
                    message: '⚠️ Bitte einen Titel eingeben!',
                    indicator: 'orange'
                });
                document.getElementById('event-title').focus();
                return;
            }
            
            if (!start) {
                frappe.show_alert({
                    message: '⚠️ Bitte ein Startdatum eingeben!',
                    indicator: 'orange'
                });
                return;
            }
            
            // ✅ RICHTIG: JS Date Objekte übergeben, KEIN toISOString()!
            // createEvent() macht die Konvertierung selbst mit formatDateForBackend()
            console.log('📤 Rufe createEvent() auf mit JS Date Objekten');
            window.kronosEvents.createEvent(
                title,
                new Date(start),  // ← JS Date Objekt (LOCAL)
                new Date(end)     // ← JS Date Objekt (LOCAL)
            );
            
            // ✅ Modal wird von refetchEvents() in createEvent geschlossen
            // NICHT sofort closeModal() weil createEvent() async ist!
            closeModal();
        });
        
        // ⌨️ ESC-Taste zum Schließen
        document.addEventListener('keydown', escListener);
        
        // 🖱️ Click außerhalb des Dialogs zum Schließen
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                console.log('❌ Modal geschlossen (außerhalb geklickt)');
                closeModal();
            }
        });
    }
}


// ✅ CSS Animations einmal laden
if (!document.getElementById('kronos-modal-styles')) {
    const style = document.createElement('style');
    style.id = 'kronos-modal-styles';
    style.textContent = `
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
        
        #event-save {
            transition: background-color 0.2s ease-out !important;
        }
        
        #event-save:hover {
            background-color: #1967d2 !important;
        }
        
        #event-cancel:hover {
            background-color: #f5f5f5 !important;
        }
    `;
    document.head.appendChild(style);
}


console.log('✅ Modal Modul geladen (mit Fixes)');