/**
 * ═══════════════════════════════════════════════════════════════
 * KRONOS MODAL - SERIES HANDLER
 * ═══════════════════════════════════════════════════════════════
 */

class KronosSeriesHandler {
    
    /**
     * 📺 SERIES HANDLER
     * Zeigt Optionen für Serientermine
     */
    static showSeriesHandler(element) {
        console.log('📺 Öffne Serie-Handler für Element:', element.name);
        console.log('📺 Series ID:', element.series_id);
        
        // Erstelle Modal
        const { modal, dialog } = KronosModalBase.createModal({
            id: 'series-modal-' + Date.now(),
            width: '550px'
        });
        
        // Header
        const header = KronosModalBase.createHeader({
            emoji: '📺',
            title: `Serienoptionen für: ${KronosModalHelpers.escapeHtml(element.element_name)}`,
            subtitle: 'Dieser Termin ist Teil einer Serie. Wie möchtest du fortfahren?'
        });
        dialog.appendChild(header);
        
        // Option Buttons Container
        const optionsContainer = document.createElement('div');
        optionsContainer.style.cssText = 'display: flex; flex-direction: column; gap: 12px; margin-bottom: 20px;';
        
        // Option 1: Edit Single
        const editSingleBtn = document.createElement('button');
        editSingleBtn.id = 'series-edit-single';
        editSingleBtn.className = 'series-option';
        editSingleBtn.style.cssText = `
            padding: 16px;
            border: 2px solid #fff3cd;
            border-radius: 6px;
            background: #fff8e1;
            color: #f57f17;
            cursor: pointer;
            font-weight: 500;
            text-align: left;
            transition: all 0.2s;
            font-size: 14px;
        `;
        editSingleBtn.innerHTML = `
            <div style="margin-bottom: 4px;">⚡ Nur diesen Termin bearbeiten</div>
            <div style="font-size: 12px; color: rgba(245, 127, 23, 0.8); font-weight: normal;">
                Ändert nur diesen speziellen Termin
            </div>
        `;
        editSingleBtn.addEventListener('click', () => {
            console.log('⚡ Bearbeite nur diesen Termin');
            KronosModalHelpers.closeModal(modal, () => {
                KronosSmartEditDialog.showSmartEditDialog(element, {
                    action: 'edit_single',
                    title: 'Nur diesen Termin bearbeiten',
                    editableFields: ['element_name', 'description', 'element_start', 'element_end'],
                    showDelete: true
                });
            });
        });
        KronosModalHelpers.addHoverEffect('series-edit-single');
        optionsContainer.appendChild(editSingleBtn);
        
        // Option 2: Remove from Series
        const removeBtn = document.createElement('button');
        removeBtn.id = 'series-remove';
        removeBtn.className = 'series-option';
        removeBtn.style.cssText = `
            padding: 16px;
            border: 2px solid #e0bee7;
            border-radius: 6px;
            background: #f3e5f5;
            color: #6a1b9a;
            cursor: pointer;
            font-weight: 500;
            text-align: left;
            transition: all 0.2s;
            font-size: 14px;
        `;
        removeBtn.innerHTML = `
            <div style="margin-bottom: 4px;">🔗 Aus Serie entfernen</div>
            <div style="font-size: 12px; color: rgba(106, 27, 154, 0.8); font-weight: normal;">
                Wird zu einem unabhängigen Termin
            </div>
        `;
        removeBtn.addEventListener('click', () => {
            console.log('🔗 Entferne aus Serie:', element.name);
            if (confirm('🔗 Diesen Termin wirklich aus der Serie entfernen?')) {
                KronosSeriesHandler._handleRemoveFromSeries(element, modal);
            }
        });
        KronosModalHelpers.addHoverEffect('series-remove');
        optionsContainer.appendChild(removeBtn);
        
        // Option 3: Delete All Series
        const deleteAllBtn = document.createElement('button');
        deleteAllBtn.id = 'series-delete-all';
        deleteAllBtn.className = 'series-option';
        deleteAllBtn.style.cssText = `
            padding: 16px;
            border: 2px solid #ffcdd2;
            border-radius: 6px;
            background: #ffebee;
            color: #c62828;
            cursor: pointer;
            font-weight: 500;
            text-align: left;
            transition: all 0.2s;
            font-size: 14px;
        `;
        deleteAllBtn.innerHTML = `
            <div style="margin-bottom: 4px;">🗑️ Ganze Serie löschen</div>
            <div style="font-size: 12px; color: rgba(198, 40, 40, 0.8); font-weight: normal;">
                Löscht ALLE Termine dieser Serie
            </div>
        `;
        deleteAllBtn.addEventListener('click', () => {
            console.log('🗑️ Lösche ganze Serie');
            if (confirm('⚠️ ACHTUNG: Das löscht ALLE Termine dieser Serie! Wirklich fortfahren?')) {
                KronosSeriesHandler._handleDeleteSeries(element, modal);
            }
        });
        KronosModalHelpers.addHoverEffect('series-delete-all');
        optionsContainer.appendChild(deleteAllBtn);
        
        dialog.appendChild(optionsContainer);
        
        // Footer Buttons
        const footerContainer = document.createElement('div');
        footerContainer.style.cssText = 'display: flex; gap: 10px; justify-content: flex-end;';
        
        const cancelBtn = KronosModalBase.createButton({
            id: 'series-cancel',
            text: 'Abbrechen',
            primary: false,
            onClick: () => KronosModalHelpers.closeModal(modal)
        });
        footerContainer.appendChild(cancelBtn);
        dialog.appendChild(footerContainer);
        
        // Setup Close Handlers
        KronosModalBase.setupCloseHandlers(modal, null);
    }
    
    /**
     * 🔗 REMOVE FROM SERIES
     */
    static _handleRemoveFromSeries(element, modal) {
        console.log('🔗 Entferne aus Serie...');
        
        KronosModalHelpers.removeFromSeries(element.name)
            .then((r) => {
                console.log('✅ Termin entfernt:', r);
                KronosModalHelpers.showSuccess('Termin aus Serie entfernt!');
                KronosModalHelpers.closeModal(modal);
                
                if (window.kronosCalendar) {
                    window.kronosCalendar.refetchEvents();
                }
            })
            .catch((err) => {
                console.error('❌ Fehler:', err);
                KronosModalHelpers.showError('Fehler beim Entfernen');
            });
    }
    
    /**
     * 🗑️ DELETE SERIES
     */
    static _handleDeleteSeries(element, modal) {
        console.log('🗑️ Lösche Serie...');
        
        const series_id = element.series_id;
        
        if (!series_id) {
            KronosModalHelpers.showError('Keine Serie ID gefunden!');
            return;
        }
        
        KronosModalHelpers.deleteSeries(series_id)
            .then((r) => {
                console.log('✅ Serie gelöscht:', r);
                
                if (r.message && r.message.success) {
                    KronosModalHelpers.showSuccess(`${r.message.deleted_count} Termine gelöscht!`);
                    KronosModalHelpers.closeModal(modal);
                    
                    if (window.kronosCalendar) {
                        window.kronosCalendar.refetchEvents();
                    }
                } else {
                    KronosModalHelpers.showError('Unerwartete Antwort vom Server');
                }
            })
            .catch((err) => {
                console.error('❌ Fehler beim Löschen:', err);
                KronosModalHelpers.showError('Fehler beim Löschen der Serie');
            });
    }
}

// Export
window.KronosSeriesHandler = KronosSeriesHandler;
console.log('✅ Series Handler geladen');
