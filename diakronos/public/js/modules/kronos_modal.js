/**
 * ═══════════════════════════════════════════════════════════════
 * KRONOS CALENDAR - MODAL MODULE
 * ═══════════════════════════════════════════════════════════════
 */

class KronosModal {
    
    static showCreateDialog(dateStr) {
        console.log('🆕 Zeige Create Dialog für:', dateStr);
        
        const modal = document.createElement('div');
        modal.id = 'event-modal';
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
            animation: fadeIn 0.2s ease-in;
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
                <button id="event-cancel" style="padding: 10px 20px; border: 1px solid #dadce0; border-radius: 4px; background: white; color: #202124; cursor: pointer; font-weight: 500;">Abbrechen</button>
                <button id="event-save" style="padding: 10px 20px; border: none; border-radius: 4px; background: #1f73e6; color: white; cursor: pointer; font-weight: 500;">✨ Erstellen</button>
            </div>
        `;
        
        modal.appendChild(dialog);
        document.body.appendChild(modal);
        
        const dateObj = new Date(dateStr);
        const isoString = dateObj.toISOString().slice(0, 16);
        document.getElementById('event-start').value = isoString;
        document.getElementById('event-end').value = isoString;
        
        document.getElementById('event-title').focus();
        
        const closeModal = () => {
            modal.style.opacity = '0';
            setTimeout(() => modal.remove(), 200);
        };
        
        document.getElementById('event-cancel').addEventListener('click', closeModal);
        
        document.getElementById('event-save').addEventListener('click', () => {
            const title = document.getElementById('event-title').value.trim();
            const start = document.getElementById('event-start').value;
            const end = document.getElementById('event-end').value || start;
            
            if (!title) {
                alert('⚠️ Bitte einen Titel eingeben!');
                document.getElementById('event-title').focus();
                return;
            }
            
            if (!start) {
                alert('⚠️ Bitte ein Startdatum eingeben!');
                return;
            }
            
            window.kronosEvents.createEvent(
                title,
                new Date(start).toISOString(),
                new Date(end).toISOString()
            );
            
            closeModal();
        });
        
        const escListener = (e) => {
            if (e.key === 'Escape') {
                closeModal();
                document.removeEventListener('keydown', escListener);
            }
        };
        document.addEventListener('keydown', escListener);
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal();
            }
        });
    }
}

if (!document.getElementById('kronos-modal-styles')) {
    const style = document.createElement('style');
    style.id = 'kronos-modal-styles';
    style.textContent = `
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
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
        
        #event-save:hover {
            background: #1967d2 !important;
        }
    `;
    document.head.appendChild(style);
}

console.log('✅ Modal Modul geladen');
