/**
 * ═══════════════════════════════════════════════════════════════
 * KRONOS MODAL - SMART EDIT DIALOG
 * ═══════════════════════════════════════════════════════════════
 */

class KronosSmartEditDialog {
    
    /**
     * 🎯 SMART EDIT DIALOG
     * Zeigt nur die Felder die für die Aktion relevant sind
     */
    static showSmartEditDialog(element, options) {
        console.log('🎯 Öffne Smart Edit:', options);
        console.log('🎯 Element:', element);
        
        const {
            action = 'edit_single',
            title = 'Bearbeiten',
            editableFields = [],
            showDelete = false,
            confirmText = '💾 Speichern'
        } = options;
        
        // Erstelle Modal
        const { modal, dialog } = KronosModalBase.createModal({
            id: 'smart-edit-modal-' + Date.now(),
            width: '450px',
            maxHeight: '80vh'
        });
        
        // Feldkonfiguration
        const fieldDefinitions = {
            'element_name': {
                label: 'Titel',
                type: 'text',
                value: element.element_name || '',
                id: 'smart-title'
            },
            'description': {
                label: 'Beschreibung',
                type: 'textarea',
                value: element.description || '',
                id: 'smart-description'
            },
            'element_start': {
                label: 'Startdatum & Zeit',
                type: 'datetime-local',
                value: KronosModalHelpers.formatToLocalDatetime(element.element_start),
                id: 'smart-start'
            },
            'element_end': {
                label: 'Enddatum & Zeit',
                type: 'datetime-local',
                value: KronosModalHelpers.formatToLocalDatetime(element.element_end),
                id: 'smart-end'
            }
        };
        
        // Baue Dialog HTML
        const header = KronosModalBase.createHeader({
            emoji: '✏️',
            title: title,
            subtitle: 'Nur dieser Termin wird geändert'
        });
        dialog.appendChild(header);
        
        // Form Container
        const formContainer = document.createElement('div');
        formContainer.id = 'form-fields';
        formContainer.style.cssText = 'margin-bottom: 20px;';
        
        editableFields.forEach(fieldKey => {
            const field = fieldDefinitions[fieldKey];
            if (!field) {
                console.warn('⚠️ Feld nicht definiert:', fieldKey);
                return;
            }
            
            const { container, inputEl } = KronosModalBase.createFormField({
                label: field.label,
                type: field.type,
                id: field.id,
                value: field.value
            });
            
            formContainer.appendChild(container);
        });
        
        dialog.appendChild(formContainer);
        
        // Button Container
        const buttonContainer = document.createElement('div');
        buttonContainer.style.cssText = 'display: flex; gap: 10px; justify-content: space-between;';
        
        // Linke Seite: Delete Button (falls vorhanden)
        const leftButtons = document.createElement('div');
        
        if (showDelete) {
            const deleteBtn = KronosModalBase.createButton({
                id: 'smart-delete',
                text: '🗑️ Löschen',
                onClick: () => KronosSmartEditDialog._handleDelete(element, modal)
            });
            deleteBtn.style.background = '#ffebee';
            deleteBtn.style.color = '#d32f2f';
            deleteBtn.style.border = '1px solid #d32f2f';
            leftButtons.appendChild(deleteBtn);
        }
        buttonContainer.appendChild(leftButtons);
        
        // Rechte Seite: Cancel & Save
        const rightButtons = document.createElement('div');
        rightButtons.style.cssText = 'display: flex; gap: 10px;';
        
        const cancelBtn = KronosModalBase.createButton({
            id: 'smart-cancel',
            text: 'Abbrechen',
            primary: false,
            onClick: () => KronosModalHelpers.closeModal(modal)
        });
        rightButtons.appendChild(cancelBtn);
        
        const saveBtn = KronosModalBase.createButton({
            id: 'smart-save',
            text: confirmText,
            primary: true,
            onClick: () => KronosSmartEditDialog._handleSave(element, editableFields, fieldDefinitions, modal)
        });
        rightButtons.appendChild(saveBtn);
        
        buttonContainer.appendChild(rightButtons);
        dialog.appendChild(buttonContainer);
        
        // Setup Close Handlers
        KronosModalBase.setupCloseHandlers(modal, null);
    }
    
    /**
     * 💾 HANDLE SAVE
     */
    static _handleSave(element, editableFields, fieldDefinitions, modal) {
        console.log('💾 Speichere...');
        
        const updateData = {};
        editableFields.forEach(fieldKey => {
            const field = fieldDefinitions[fieldKey];
            if (field && field.id) {
                const input = document.getElementById(field.id);
                if (input) {
                    updateData[fieldKey] = input.value;
                }
            }
        });
        
        console.log('📤 Update Daten:', updateData);
        
        // Speichern via Helper
        KronosModalHelpers.saveSingleEvent(element, updateData)
            .then((r) => {
                console.log('✅ Backend Response:', r);
                KronosModalHelpers.showSuccess('Termin aktualisiert!');
                KronosModalHelpers.closeModal(modal);
                
                // Refresh Calendar
                if (window.kronosCalendar) {
                    window.kronosCalendar.refetchEvents();
                }
            })
            .catch((err) => {
                console.error('❌ Fehler beim Speichern:', err);
                KronosModalHelpers.showError('Fehler beim Speichern');
            });
    }
    
    /**
     * 🗑️ HANDLE DELETE
     */
    static _handleDelete(element, modal) {
        if (confirm('🗑️ Termin wirklich löschen?')) {
            KronosModalHelpers.deleteElement('Element', element.name)
                .then((r) => {
                    console.log('✅ Element gelöscht:', r);
                    KronosModalHelpers.showSuccess('Termin gelöscht!');
                    KronosModalHelpers.closeModal(modal);
                    
                    if (window.kronosCalendar) {
                        window.kronosCalendar.refetchEvents();
                    }
                })
                .catch((err) => {
                    console.error('❌ Fehler beim Löschen:', err);
                    KronosModalHelpers.showError('Fehler beim Löschen');
                });
        }
    }
}

// Export
window.KronosSmartEditDialog = KronosSmartEditDialog;
console.log('✅ Smart Edit Dialog geladen');
