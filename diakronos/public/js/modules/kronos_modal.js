/**
 * ═══════════════════════════════════════════════════════════════
 * KRONOS CALENDAR - MODAL MODULE (FIXED VERSION)
 * ═══════════════════════════════════════════════════════════════
 * ✅ Event Click Handler
 * ✅ Create Dialog
 * ✅ Series Handler mit Smart Edit
 * ✅ KEIN Frappe UI - Alles als PopUp vor dem Kalender
 * 
 * 🔧 FIXED:
 * - HTML-Escaping-Fehler behoben
 * - Feldnamen korrekt (element_name, description, element_start, element_end)
 * - Arrow Functions korrekt formatiert
 */

class KronosModal {
    
    /**
     * 🖱️ EVENT CLICK HANDLER
     */
    static showEventClickDialog(eventData) {
        console.log('🔍 Event geklickt:', eventData);
        
        if (!eventData || !eventData.id) {
            console.error('❌ Ungültige Event-Daten');
            return;
        }
        
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
                    
                    const isSeriesInstance = !!element.series_id;
                    console.log('📺 isSeriesInstance:', isSeriesInstance);
                    
                    if (isSeriesInstance) {
                        KronosModal.showSeriesHandler(element);
                    } else {
                        KronosModal.showSmartEditDialog(element, {
                            action: 'edit_single',
                            title: 'Termin bearbeiten',
                            editableFields: ['element_name', 'description', 'element_start', 'element_end'],
                            showDelete: true
                        });
                    }
                } else {
                    frappe.show_alert({
                        message: '❌ Event konnte nicht geladen werden',
                        indicator: 'red'
                    });
                }
            },
            error: (err) => {
                console.error('❌ Fehler beim Laden:', err);
                frappe.show_alert({
                    message: '❌ Fehler beim Laden des Events',
                    indicator: 'red'
                });
            }
        });
    }
    
    /**
     * 📺 SERIES HANDLER
     */
    static showSeriesHandler(element) {
        console.log('📺 Öffne Serie-Handler für Element:', element.name);
        console.log('📺 Series ID:', element.series_id);
        
        const modal = document.createElement('div');
        modal.id = 'series-modal-' + Date.now();
        modal.style.cssText = 'position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 9999; opacity: 1; transition: opacity 0.2s ease-out;';
        
        const dialog = document.createElement('div');
        dialog.style.cssText = 'background: white; border-radius: 8px; padding: 24px; min-width: 500px; max-width: 600px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); animation: slideUp 0.3s ease-out;';
        
        dialog.innerHTML = `
            <div style="margin-bottom: 24px;">
                <h2 style="margin: 0 0 8px 0; font-size: 18px; color: #202124;">
                    📺 Serienoptionen für: <strong>${KronosModal._escapeHtml(element.element_name)}</strong>
                </h2>
                <p style="margin: 0; color: #666; font-size: 13px;">
                    Dieser Termin ist Teil einer Serie. Wie möchtest du fortfahren?
                </p>
            </div>
            
            <div style="display: flex; flex-direction: column; gap: 12px; margin-bottom: 20px;">
                
                <button id="series-edit-single" class="series-option" style="
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
                ">
                    <div style="margin-bottom: 4px;">⚡ Nur diesen Termin bearbeiten</div>
                    <div style="font-size: 12px; color: rgba(245, 127, 23, 0.8); font-weight: normal;">
                        Ändert nur diesen speziellen Termin
                    </div>
                </button>
                
                <button id="series-remove" class="series-option" style="
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
                ">
                    <div style="margin-bottom: 4px;">🔗 Aus Serie entfernen</div>
                    <div style="font-size: 12px; color: rgba(106, 27, 154, 0.8); font-weight: normal;">
                        Wird zu einem unabhängigen Termin
                    </div>
                </button>
                
                <button id="series-delete-all" class="series-option" style="
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
                ">
                    <div style="margin-bottom: 4px;">🗑️ Ganze Serie löschen</div>
                    <div style="font-size: 12px; color: rgba(198, 40, 40, 0.8); font-weight: normal;">
                        Löscht ALLE Termine dieser Serie
                    </div>
                </button>
            </div>
            
            <div style="display: flex; gap: 10px; justify-content: flex-end;">
                <button id="series-cancel" style="
                    padding: 10px 20px;
                    border: 1px solid #dadce0;
                    border-radius: 4px;
                    background: #f5f5f5;
                    color: #202124;
                    cursor: pointer;
                    font-weight: 500;
                    transition: all 0.2s;
                ">
                    Abbrechen
                </button>
            </div>
        `;
        
        modal.appendChild(dialog);
        document.body.appendChild(modal);
        
        const addHoverEffect = (buttonId) => {
            const btn = document.getElementById(buttonId);
            if (btn) {
                btn.addEventListener('mouseenter', () => {
                    btn.style.transform = 'translateY(-2px)';
                    btn.style.boxShadow = '0 4px 8px rgba(0,0,0,0.1)';
                });
                btn.addEventListener('mouseleave', () => {
                    btn.style.transform = 'translateY(0)';
                    btn.style.boxShadow = 'none';
                });
            }
        };
        
        document.querySelectorAll('.series-option').forEach(btn => {
            addHoverEffect(btn.id);
        });
        
        const closeModal = () => {
            console.log('🔽 Schließe Series-Modal');
            modal.style.opacity = '0';
            document.removeEventListener('keydown', escListener);
            setTimeout(() => {
                if (modal && modal.parentNode) {
                    modal.remove();
                }
            }, 200);
        };
        
        document.getElementById('series-cancel')?.addEventListener('click', closeModal);
        
        document.getElementById('series-edit-single')?.addEventListener('click', () => {
            console.log('⚡ Bearbeite nur diesen Termin');
            closeModal();
            
            KronosModal.showSmartEditDialog(element, {
                action: 'edit_single',
                title: 'Nur diesen Termin bearbeiten',
                editableFields: ['element_name', 'description', 'element_start', 'element_end'],
                showDelete: true
            });
        });
        
        document.getElementById('series-remove')?.addEventListener('click', () => {
            console.log('🔗 Entferne aus Serie:', element.name);
            
            if (!confirm('🔗 Diesen Termin wirklich aus der Serie entfernen?')) {
                return;
            }
            
            closeModal();
            
            frappe.call({
                method: 'frappe.client.set_value',
                args: {
                    doctype: 'Element',
                    name: element.name,
                    fieldname: { series_id: null }
                },
                callback: (r) => {
                    frappe.show_alert({
                        message: '✅ Termin aus Serie entfernt!',
                        indicator: 'green'
                    });
                    if (window.kronosCalendar) {
                        window.kronosCalendar.refetchEvents();
                    }
                },
                error: (err) => {
                    console.error('❌ Fehler beim Entfernen:', err);
                    frappe.show_alert({
                        message: '❌ Fehler beim Entfernen',
                        indicator: 'red'
                    });
                }
            });
        });
        
        document.getElementById('series-delete-all')?.addEventListener('click', () => {
            console.log('🗑️ Lösche ganze Serie');
            
            if (!confirm('⚠️ ACHTUNG: Das löscht ALLE Termine dieser Serie! Wirklich fortfahren?')) {
                return;
            }
            
            closeModal();
            
            const series_id = element.series_id;
            
            if (!series_id) {
                frappe.show_alert({
                    message: '❌ Fehler: Keine Serie ID gefunden!',
                    indicator: 'red'
                });
                return;
            }
            
            frappe.call({
                method: 'diakronos.kronos.api.series_update.delete_series_batch',
                args: { series_id: series_id },
                callback: (r) => {
                    console.log('🗑️ Delete Response:', r);
                    
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: `✅ ${r.message.deleted_count} Termine gelöscht!`,
                            indicator: 'green'
                        });
                        if (window.kronosCalendar) {
                            window.kronosCalendar.refetchEvents();
                        }
                    } else {
                        frappe.show_alert({
                            message: '❌ Unerwartete Antwort vom Server',
                            indicator: 'red'
                        });
                    }
                },
                error: (err) => {
                    console.error('❌ Fehler beim Löschen:', err);
                    frappe.show_alert({
                        message: '❌ Fehler beim Löschen der Serie',
                        indicator: 'red'
                    });
                }
            });
        });

        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal();
            }
        });
        
        const escListener = (e) => {
            if (e.key === 'Escape') {
                closeModal();
            }
        };
        document.addEventListener('keydown', escListener);
    }
    
    /**
     * 🎯 SMART EDIT DIALOG
     */
    static showSmartEditDialog(element, options) {
        console.log('🎯 Öffne Smart Edit:', options);
        console.log('🎯 Element:', element);
        
        const {
            action,
            title,
            editableFields = [],
            showDelete = false,
            confirmText = '💾 Speichern'
        } = options;
        
        const modal = document.createElement('div');
        modal.id = 'smart-edit-modal-' + Date.now();
        modal.style.cssText = 'position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 9999; opacity: 1; transition: opacity 0.2s ease-out;';
        
        const dialog = document.createElement('div');
        dialog.style.cssText = 'background: white; border-radius: 8px; padding: 24px; min-width: 450px; max-height: 80vh; overflow-y: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.15); animation: slideUp 0.3s ease-out;';
        
        let fieldsHTML = '';
        
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
                value: KronosModal._formatToLocalDatetime(element.element_start),
                id: 'smart-start'
            },
            'element_end': {
                label: 'Enddatum & Zeit',
                type: 'datetime-local',
                value: KronosModal._formatToLocalDatetime(element.element_end),
                id: 'smart-end'
            }
        };
        
        editableFields.forEach(fieldKey => {
            const field = fieldDefinitions[fieldKey];
            if (!field) {
                console.warn('⚠️ Feld nicht definiert:', fieldKey);
                return;
            }
            
            let fieldHTML = `<div style="margin-bottom: 16px;">
                <label style="display: block; margin-bottom: 6px; font-weight: 500; color: #202124;">
                    ${field.label}
                </label>`;
            
            if (field.type === 'textarea') {
                fieldHTML += `
                    <textarea id="${field.id}" style="
                        width: 100%;
                        padding: 10px;
                        border: 1px solid #dadce0;
                        border-radius: 4px;
                        font-size: 14px;
                        font-family: inherit;
                        box-sizing: border-box;
                        height: 80px;
                        resize: vertical;
                    ">${KronosModal._escapeHtml(field.value)}</textarea>
                `;
            } else {
                fieldHTML += `
                    <input 
                        id="${field.id}" 
                        type="${field.type}" 
                        value="${field.value}" 
                        style="
                            width: 100%;
                            padding: 10px;
                            border: 1px solid #dadce0;
                            border-radius: 4px;
                            font-size: 14px;
                            font-family: inherit;
                            box-sizing: border-box;
                        "
                    />
                `;
            }
            
            fieldHTML += `</div>`;
            fieldsHTML += fieldHTML;
        });
        
        const actionBadges = { 'edit_single': '✏️' };
        const actionDescriptions = { 'edit_single': 'Nur dieser Termin wird geändert' };
        
        const deleteButtonHTML = (showDelete) ? `
            <button id="smart-delete" style="
                padding: 8px 16px;
                border: 1px solid #d32f2f;
                border-radius: 4px;
                background: #ffebee;
                color: #d32f2f;
                cursor: pointer;
                font-weight: 500;
                transition: all 0.2s;
            ">
                🗑️ Löschen
            </button>
        ` : '';
        
        dialog.innerHTML = `
            <div style="margin-bottom: 24px; display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <h2 style="margin: 0 0 8px 0; font-size: 18px; color: #202124;">
                        ${actionBadges[action]} ${title}
                    </h2>
                    <p style="margin: 0; color: #999; font-size: 12px;">
                        ${actionDescriptions[action]}
                    </p>
                </div>
            </div>
            
            <div id="form-fields" style="margin-bottom: 20px;">
                ${fieldsHTML}
            </div>
            
            <div style="display: flex; gap: 10px; justify-content: space-between;">
                <div>
                    ${deleteButtonHTML}
                </div>
                <div style="display: flex; gap: 10px;">
                    <button id="smart-cancel" style="
                        padding: 10px 20px;
                        border: 1px solid #dadce0;
                        border-radius: 4px;
                        background: #f5f5f5;
                        color: #202124;
                        cursor: pointer;
                        font-weight: 500;
                        transition: all 0.2s;
                    ">
                        Abbrechen
                    </button>
                    <button id="smart-save" style="
                        padding: 10px 20px;
                        border: none;
                        border-radius: 4px;
                        background: #1f73e6;
                        color: white;
                        cursor: pointer;
                        font-weight: 500;
                        transition: all 0.2s;
                    ">
                        ${confirmText}
                    </button>
                </div>
            </div>
        `;
        
        modal.appendChild(dialog);
        document.body.appendChild(modal);
        
        const closeModal = () => {
            console.log('🔽 Schließe Smart Edit Modal');
            modal.style.opacity = '0';
            document.removeEventListener('keydown', escListener);
            setTimeout(() => {
                if (modal && modal.parentNode) {
                    modal.remove();
                }
            }, 200);
        };
        
        document.getElementById('smart-cancel').addEventListener('click', closeModal);
        
        if (showDelete) {
            document.getElementById('smart-delete').addEventListener('click', () => {
                if (confirm('🗑️ Termin wirklich löschen?')) {
                    frappe.call({
                        method: 'frappe.client.delete',
                        args: {
                            doctype: 'Element',
                            name: element.name
                        },
                        callback: (r) => {
                            frappe.show_alert({
                                message: '✅ Termin gelöscht!',
                                indicator: 'green'
                            });
                            closeModal();
                            if (window.kronosCalendar) {
                                window.kronosCalendar.refetchEvents();
                            }
                        },
                        error: (err) => {
                            console.error('❌ Fehler beim Löschen:', err);
                            frappe.show_alert({
                                message: '❌ Fehler beim Löschen',
                                indicator: 'red'
                            });
                        }
                    });
                }
            });
        }

        document.getElementById('smart-save').addEventListener('click', () => {
            console.log('💾 Speichere mit Action:', action);
            
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
            KronosModal._saveSingleEvent(element, updateData, closeModal);
        });

        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal();
            }
        });
        
        const escListener = (e) => {
            if (e.key === 'Escape') {
                closeModal();
            }
        };
        document.addEventListener('keydown', escListener);
    }
    
    /**
     * 💾 SPEICHERE EINEN TERMIN
     */
    static _saveSingleEvent(element, updateData, closeModal) {
        console.log('💾 Speichere Termin:', element.name);
        
        const payload = {};
        Object.entries(updateData).forEach(([key, value]) => {
            if (key.includes('start') || key.includes('end')) {
                const date = new Date(value);
                const year = date.getFullYear();
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const day = String(date.getDate()).padStart(2, '0');
                const hours = String(date.getHours()).padStart(2, '0');
                const minutes = String(date.getMinutes()).padStart(2, '0');
                const seconds = String(date.getSeconds()).padStart(2, '0');
                
                payload[key] = `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
                console.log(`🔧 Konvertiert ${key}: ${value} -> ${payload[key]}`);
            } else {
                payload[key] = value;
            }
        });
        
        console.log('📤 Final Payload:', payload);
        
        frappe.call({
            method: 'frappe.client.set_value',
            args: {
                doctype: 'Element',
                name: element.name,
                fieldname: payload
            },
            callback: (r) => {
                console.log('✅ Backend Response:', r);
                frappe.show_alert({
                    message: '✅ Termin aktualisiert!',
                    indicator: 'green'
                });
                closeModal();
                
                if (window.kronosCalendar) {
                    window.kronosCalendar.refetchEvents();
                }
            },
            error: (err) => {
                console.error('❌ Fehler beim Speichern:', err);
                frappe.show_alert({
                    message: '❌ Fehler beim Speichern',
                    indicator: 'red'
                });
            }
        });
    }

    static _formatToLocalDatetime(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        return `${year}-${month}-${day}T${hours}:${minutes}`;
    }
    
    static _escapeHtml(text) {
        if (!text) return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return String(text).replace(/[&<>"']/g, m => map[m]);
    }
    
    /**
     * ✨ CREATE DIALOG
     */
    static showCreateDialog(dateStr) {
        console.log('✨ Zeige Create Dialog für:', dateStr);
        
        if (!window.kronosCalendar) {
            console.error('❌ KronosCalendar nicht geladen!');
            frappe.show_alert({
                message: '❌ Modul konnte nicht geladen werden',
                indicator: 'red'
            });
            return;
        }
        
        const modal = document.createElement('div');
        modal.id = 'event-modal-' + Date.now();
        modal.style.cssText = 'position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 9999; opacity: 1; transition: opacity 0.2s ease-out;';
        
        const dialog = document.createElement('div');
        dialog.style.cssText = 'background: white; border-radius: 8px; padding: 24px; min-width: 500px; max-height: 90vh; overflow-y: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.15); animation: slideUp 0.3s ease-out;';
        
        dialog.innerHTML = `
            <h2 style="margin: 0 0 20px 0; font-size: 20px; color: #202124;">✨ Neuer Termin</h2>
            
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
            
            <div style="margin-bottom: 20px; padding: 16px; background: #f5f5f5; border-radius: 6px;">
                <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; margin: 0;">
                    <input id="event-repeat" type="checkbox" style="width: 20px; height: 20px; cursor: pointer;">
                    <div>
                        <div style="font-weight: 500; color: #202124;">🔄 Wiederkehrend</div>
                        <div style="font-size: 12px; color: #666;">Erstelle einen Serientermin</div>
                    </div>
                </label>
            </div>
            
            <div id="series-fields" style="display: none; padding: 16px; background: #fff8e1; border-radius: 6px; margin-bottom: 20px; border-left: 4px solid #f57f17;">
                
                <div style="margin-bottom: 16px;">
                    <label style="display: block; margin-bottom: 6px; font-weight: 500; color: #202124;">Wiederholung *</label>
                    <select id="event-pattern" style="width: 100%; padding: 10px; border: 1px solid #dadce0; border-radius: 4px; font-size: 14px; box-sizing: border-box;">
                        <option value="Daily">📅 Täglich</option>
                        <option value="Weekly" selected>📆 Wöchentlich</option>
                        <option value="Monthly">📊 Monatlich</option>
                        <option value="Quarterly">📈 Vierteljährlich</option>
                        <option value="Half Yearly">📉 Halbjährlich</option>
                        <option value="Yearly">🎯 Jährlich</option>
                    </select>
                </div>
                
                <div id="weekdays-group" style="margin-bottom: 16px;">
                    <label style="display: block; margin-bottom: 8px; font-weight: 500; color: #202124;">Wochentage</label>
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px;">
                        <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
                            <input id="event-monday" type="checkbox" checked> Montag
                        </label>
                        <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
                            <input id="event-tuesday" type="checkbox"> Dienstag
                        </label>
                        <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
                            <input id="event-wednesday" type="checkbox"> Mittwoch
                        </label>
                        <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
                            <input id="event-thursday" type="checkbox"> Donnerstag
                        </label>
                        <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
                            <input id="event-friday" type="checkbox"> Freitag
                        </label>
                        <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
                            <input id="event-saturday" type="checkbox"> Samstag
                        </label>
                        <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
                            <input id="event-sunday" type="checkbox"> Sonntag
                        </label>
                    </div>
                </div>
                
                <div style="margin-bottom: 16px;">
                    <label style="display: block; margin-bottom: 6px; font-weight: 500; color: #202124;">Endet am *</label>
                    <input id="event-repeat-till" type="date" style="width: 100%; padding: 10px; border: 1px solid #dadce0; border-radius: 4px; font-size: 14px; box-sizing: border-box;">
                </div>
            </div>
            
            <div style="display: flex; gap: 10px; justify-content: flex-end;">
                <button id="event-cancel" style="padding: 10px 20px; border: 1px solid #dadce0; border-radius: 4px; background: white; color: #202124; cursor: pointer; font-weight: 500; transition: all 0.2s;">Abbrechen</button>
                <button id="event-save" style="padding: 10px 20px; border: none; border-radius: 4px; background: #1f73e6; color: white; cursor: pointer; font-weight: 500; transition: all 0.2s;">✨ Erstellen</button>
            </div>
        `;
        
        modal.appendChild(dialog);
        document.body.appendChild(modal);
        
        const dateObj = new Date(dateStr);
        const year = dateObj.getFullYear();
        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
        const day = String(dateObj.getDate()).padStart(2, '0');
        const hours = String(dateObj.getHours()).padStart(2, '0');
        const minutes = String(dateObj.getMinutes()).padStart(2, '0');
        
        const localDatetimeStr = `${year}-${month}-${day}T${hours}:${minutes}`;
        document.getElementById('event-start').value = localDatetimeStr;
        document.getElementById('event-end').value = localDatetimeStr;
        
        const repeatTillDate = new Date(dateObj);
        repeatTillDate.setFullYear(repeatTillDate.getFullYear() + 1);
        const repeatTillStr = repeatTillDate.toISOString().split('T')[0];
        document.getElementById('event-repeat-till').value = repeatTillStr;
        
        document.getElementById('event-title').focus();
        
        const repeatCheckbox = document.getElementById('event-repeat');
        const seriesFields = document.getElementById('series-fields');
        const patternSelect = document.getElementById('event-pattern');
        const weekdaysGroup = document.getElementById('weekdays-group');
        
        repeatCheckbox.addEventListener('change', (e) => {
            console.log('🔄 Wiederholung:', e.target.checked);
            seriesFields.style.display = e.target.checked ? 'block' : 'none';
        });
        
        patternSelect.addEventListener('change', (e) => {
            console.log('📅 Pattern geändert:', e.target.value);
            weekdaysGroup.style.display = e.target.value === 'Weekly' ? 'block' : 'none';
        });
        
        const closeModal = () => {
            console.log('🔽 Schließe Create Modal');
            modal.style.opacity = '0';
            document.removeEventListener('keydown', escListener);
            setTimeout(() => {
                if (modal && modal.parentNode) {
                    modal.remove();
                }
            }, 200);
        };
        
        document.getElementById('event-cancel').addEventListener('click', closeModal);
        
        document.getElementById('event-save').addEventListener('click', () => {
            console.log('💾 Create Dialog Save');
            
            const title = document.getElementById('event-title').value.trim();
            const start = document.getElementById('event-start').value;
            const end = document.getElementById('event-end').value || start;
            const isRepeat = document.getElementById('event-repeat').checked;
            
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
            
            const doc = {
                doctype: 'Element',
                element_name: title,
                element_start: start,
                element_end: end,
                repeatthisevent: isRepeat ? 1 : 0
            };
            
            if (isRepeat) {
                const pattern = document.getElementById('event-pattern').value;
                const repeatTill = document.getElementById('event-repeat-till').value;
                
                if (!repeatTill) {
                    frappe.show_alert({
                        message: '⚠️ Bitte ein Enddatum eingeben!',
                        indicator: 'orange'
                    });
                    return;
                }
                
                doc.repeaton = pattern;
                doc.repeattill = repeatTill;
                
                if (pattern === 'Weekly') {
                    doc.monday = document.getElementById('event-monday').checked ? 1 : 0;
                    doc.tuesday = document.getElementById('event-tuesday').checked ? 1 : 0;
                    doc.wednesday = document.getElementById('event-wednesday').checked ? 1 : 0;
                    doc.thursday = document.getElementById('event-thursday').checked ? 1 : 0;
                    doc.friday = document.getElementById('event-friday').checked ? 1 : 0;
                    doc.saturday = document.getElementById('event-saturday').checked ? 1 : 0;
                    doc.sunday = document.getElementById('event-sunday').checked ? 1 : 0;
                }
            }
            
            console.log('📤 Sende Dokument:', doc);
            
            frappe.call({
                method: 'frappe.client.insert',
                args: { doc: doc },
                callback: (r) => {
                    if (r.message) {
                        const elementId = r.message.name;
                        console.log('✅ Element erstellt:', elementId);
                        
                        if (isRepeat) {
                            console.log('🔄 Erstelle Serie-Instanzen für:', elementId);
                            
                            frappe.call({
                                method: 'diakronos.kronos.api.series_create.create_event_series',
                                args: { series_element_id: elementId },
                                callback: (series_response) => {
                                    console.log('✅ Serie erstellt:', series_response.message);
                                    frappe.show_alert({
                                        message: `✅ ${series_response.message.generated_count} Termine erstellt!`,
                                        indicator: 'green'
                                    });
                                    closeModal();
                                    if (window.kronosCalendar) {
                                        window.kronosCalendar.refetchEvents();
                                    }
                                },
                                error: (err) => {
                                    console.error('❌ Serie-Fehler:', err);
                                    frappe.show_alert({
                                        message: '❌ Fehler beim Erstellen der Serie',
                                        indicator: 'red'
                                    });
                                    closeModal();
                                }
                            });
                        } else {
                            frappe.show_alert({
                                message: `✅ Termin "${title}" erstellt!`,
                                indicator: 'green'
                            });
                            closeModal();
                            if (window.kronosCalendar) {
                                window.kronosCalendar.refetchEvents();
                            }
                        }
                    }
                },
                error: (err) => {
                    console.error('❌ Fehler beim Erstellen:', err);
                    frappe.show_alert({
                        message: '❌ Fehler beim Erstellen des Termins',
                        indicator: 'red'
                    });
                }
            });
        });
        
        const escListener = (e) => {
            if (e.key === 'Escape') {
                closeModal();
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

// ═════════════════════════════════════════════════
// CSS ANIMATIONS
// ═════════════════════════════════════════════════

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
        
        .series-option:hover {
            cursor: pointer;
        }
    `;
    
    document.head.appendChild(style);
}

// ═════════════════════════════════════════════════
// EXPORT ZUM GLOBAL SCOPE
// ═════════════════════════════════════════════════

window.KronosModal = KronosModal;

console.log('✅ Modal Modul geladen (FIXED Version)');
console.log('🌍 window.KronosModal verfügbar:', typeof window.KronosModal);