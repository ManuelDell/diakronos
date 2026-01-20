/**
 * ═══════════════════════════════════════════════════════════════
 * KRONOS MODAL - CREATE DIALOG
 * ═══════════════════════════════════════════════════════════════
 * ✨ Neuer Termin Dialog mit Kalender & Kategorie aus Frappe
 */

class KronosCreateDialog {
    
    /**
     * ✨ CREATE DIALOG
     * Zeigt Dialog für neuen Termin
     */
    static async showCreateDialog(dateStr, permissionData) {
        console.log('✨ Zeige Create Dialog für:', dateStr);
        console.log('📋 Permission Data:', permissionData);
        
        if (!window.kronosCalendar) {
            console.error('❌ KronosCalendar nicht geladen!');
            KronosModalHelpers.showError('Modul konnte nicht geladen werden');
            return;
        }
        
        // Erstelle Modal
        const { modal, dialog } = KronosModalBase.createModal({
            id: 'event-modal-' + Date.now(),
            width: '500px',
            maxHeight: '90vh'
        });
        
        // Header
        const header = KronosModalBase.createHeader({
            emoji: '✨',
            title: 'Neuer Termin'
        });
        dialog.appendChild(header);
        
        // Hauptformular
        const mainForm = document.createElement('div');
        mainForm.style.cssText = 'margin-bottom: 20px;';
        
        // Titel Feld
        const { container: titleContainer, inputEl: titleInput } = KronosModalBase.createFormField({
            label: 'Titel',
            type: 'text',
            id: 'event-title',
            placeholder: 'z.B. Gottesdienst',
            required: true
        });
        mainForm.appendChild(titleContainer);
        
        // ⏳ LADE ALLE OPTIONEN AUS FRAPPE - VOR DEN DROPDOWNS
        const dropdownOptions = await KronosModalHelpers.loadDropdownOptions();
        
        // 🆕 KALENDER FELD - AUS FRAPPE BACKEND
        const { container: calendarContainer, inputEl: calendarSelect } = KronosModalBase.createFormField({
            label: 'Kalender',
            type: 'select',
            id: 'event-calendar',
            required: true
        });
        
        // Kalender füllen (Priorität: Backend > permissionData)
        calendarSelect.innerHTML = '<option value="">─ Kalender wählen ─</option>';
        
        let calendarsToUse = [];
        if (dropdownOptions.calendars && dropdownOptions.calendars.length > 0) {
            console.log('📅 Kalender aus Backend:', dropdownOptions.calendars);
            calendarsToUse = dropdownOptions.calendars;
        } else if (permissionData && permissionData.writable_calendars && permissionData.writable_calendars.length > 0) {
            console.log('📅 Fallback - Kalender aus permissionData:', permissionData.writable_calendars);
            calendarsToUse = permissionData.writable_calendars.map(cal => ({
                name: cal.value,
                calendar_name: cal.label
            }));
        } else {
            console.warn('⚠️ Keine Kalender gefunden!');
        }
        
        calendarsToUse.forEach(cal => {
            const option = document.createElement('option');
            option.value = cal.name;
            option.textContent = `📅 ${cal.calendar_name || cal.name}`;
            calendarSelect.appendChild(option);
        });
        
        mainForm.appendChild(calendarContainer);
        
        // 🆕 KATEGORIE FELD - AUS FRAPPE BACKEND
        const { container: categoryContainer, inputEl: categorySelect } = KronosModalBase.createFormField({
            label: 'Kategorie',
            type: 'select',
            id: 'event-category',
            required: false
        });
        
        // Kategorien füllen
        categorySelect.innerHTML = '<option value="">─ Keine ─</option>';
        if (dropdownOptions.categories && dropdownOptions.categories.length > 0) {
            console.log('📂 Kategorien aus Backend:', dropdownOptions.categories);
            dropdownOptions.categories.forEach(cat => {
                const option = document.createElement('option');
                option.value = cat.name;
                option.textContent = `📂 ${cat.name}`;
                categorySelect.appendChild(option);
            });
        } else {
            console.warn('⚠️ Keine Kategorien gefunden!');
        }
        
        mainForm.appendChild(categoryContainer);
        
        // Start Feld
        const { container: startContainer, inputEl: startInput } = KronosModalBase.createFormField({
            label: 'Startdatum & Zeit',
            type: 'datetime-local',
            id: 'event-start',
            required: true
        });
        mainForm.appendChild(startContainer);
        
        // End Feld
        const { container: endContainer, inputEl: endInput } = KronosModalBase.createFormField({
            label: 'Enddatum & Zeit',
            type: 'datetime-local',
            id: 'event-end'
        });
        mainForm.appendChild(endContainer);
        
        dialog.appendChild(mainForm);
        
        // Wiederkehrend Checkbox Container
        const repeatContainer = document.createElement('div');
        repeatContainer.style.cssText = 'margin-bottom: 20px; padding: 16px; background: #f5f5f5; border-radius: 6px;';
        
        const repeatLabel = document.createElement('label');
        repeatLabel.style.cssText = 'display: flex; align-items: center; gap: 10px; cursor: pointer; margin: 0;';
        
        const repeatCheckbox = document.createElement('input');
        repeatCheckbox.id = 'event-repeat';
        repeatCheckbox.type = 'checkbox';
        repeatCheckbox.style.cssText = 'width: 20px; height: 20px; cursor: pointer;';
        repeatLabel.appendChild(repeatCheckbox);
        
        const repeatLabelText = document.createElement('div');
        repeatLabelText.innerHTML = `
            <div style="font-weight: 500; color: #202124;">🔄 Wiederkehrend</div>
            <div style="font-size: 12px; color: #666;">Erstelle einen Serientermin</div>
        `;
        repeatLabel.appendChild(repeatLabelText);
        repeatContainer.appendChild(repeatLabel);
        dialog.appendChild(repeatContainer);
        
        // Serie-Felder (versteckt)
        const seriesFields = document.createElement('div');
        seriesFields.id = 'series-fields';
        seriesFields.style.cssText = 'display: none; padding: 16px; background: #fff8e1; border-radius: 6px; margin-bottom: 20px; border-left: 4px solid #f57f17;';
        
        // Pattern Select
        const { container: patternContainer, inputEl: patternSelect } = KronosModalBase.createFormField({
            label: 'Wiederholung',
            type: 'select',
            id: 'event-pattern',
            required: true
        });
        
        const patterns = [
            { value: 'Daily', text: '📅 Täglich' },
            { value: 'Weekly', text: '📆 Wöchentlich' },
            { value: 'Monthly', text: '📊 Monatlich' },
            { value: 'Quarterly', text: '📈 Vierteljährlich' },
            { value: 'Half Yearly', text: '📉 Halbjährlich' },
            { value: 'Yearly', text: '🎯 Jährlich' }
        ];
        
        patterns.forEach(p => {
            const option = document.createElement('option');
            option.value = p.value;
            option.textContent = p.text;
            if (p.value === 'Weekly') option.selected = true;
            patternSelect.appendChild(option);
        });
        
        seriesFields.appendChild(patternContainer);
        
        // Wochentage Container
        const weekdaysGroup = document.createElement('div');
        weekdaysGroup.id = 'weekdays-group';
        weekdaysGroup.style.cssText = 'margin-bottom: 16px;';
        
        const weekdaysLabel = document.createElement('label');
        weekdaysLabel.style.cssText = 'display: block; margin-bottom: 8px; font-weight: 500; color: #202124;';
        weekdaysLabel.textContent = 'Wochentage';
        weekdaysGroup.appendChild(weekdaysLabel);
        
        const weekdaysGrid = document.createElement('div');
        weekdaysGrid.style.cssText = 'display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px;';
        
        const weekdays = [
            { id: 'event-monday', text: 'Montag', checked: true },
            { id: 'event-tuesday', text: 'Dienstag', checked: false },
            { id: 'event-wednesday', text: 'Mittwoch', checked: false },
            { id: 'event-thursday', text: 'Donnerstag', checked: false },
            { id: 'event-friday', text: 'Freitag', checked: false },
            { id: 'event-saturday', text: 'Samstag', checked: false },
            { id: 'event-sunday', text: 'Sonntag', checked: false }
        ];
        
        weekdays.forEach(day => {
            const dayLabel = document.createElement('label');
            dayLabel.style.cssText = 'display: flex; align-items: center; gap: 6px; cursor: pointer;';
            
            const checkbox = document.createElement('input');
            checkbox.id = day.id;
            checkbox.type = 'checkbox';
            checkbox.checked = day.checked;
            dayLabel.appendChild(checkbox);
            
            dayLabel.appendChild(document.createTextNode(day.text));
            weekdaysGrid.appendChild(dayLabel);
        });
        
        weekdaysGroup.appendChild(weekdaysGrid);
        seriesFields.appendChild(weekdaysGroup);
        
        // Repeat Till Feld
        const { container: repeatTillContainer, inputEl: repeatTillInput } = KronosModalBase.createFormField({
            label: 'Endet am',
            type: 'date',
            id: 'event-repeat-till',
            required: true
        });
        seriesFields.appendChild(repeatTillContainer);
        
        dialog.appendChild(seriesFields);
        
        // Setze Initial Values
        const dateObj = new Date(dateStr);
        const localDatetimeStr = KronosModalHelpers.formatToLocalDatetime(dateStr);
        startInput.value = localDatetimeStr;
        endInput.value = localDatetimeStr;
        
        const repeatTillDate = new Date(dateObj);
        repeatTillDate.setFullYear(repeatTillDate.getFullYear() + 1);
        const repeatTillStr = repeatTillDate.toISOString().split('T')[0];
        repeatTillInput.value = repeatTillStr;
        
        titleInput.focus();
        
        // Event Listeners
        repeatCheckbox.addEventListener('change', (e) => {
            console.log('🔄 Wiederholung:', e.target.checked);
            seriesFields.style.display = e.target.checked ? 'block' : 'none';
        });
        
        patternSelect.addEventListener('change', (e) => {
            console.log('📅 Pattern geändert:', e.target.value);
            weekdaysGroup.style.display = e.target.value === 'Weekly' ? 'block' : 'none';
        });
        
        // Footer Buttons
        const footerContainer = document.createElement('div');
        footerContainer.style.cssText = 'display: flex; gap: 10px; justify-content: flex-end;';
        
        const cancelBtn = KronosModalBase.createButton({
            id: 'event-cancel',
            text: 'Abbrechen',
            primary: false,
            onClick: () => KronosModalHelpers.closeModal(modal)
        });
        footerContainer.appendChild(cancelBtn);
        
        const saveBtn = KronosModalBase.createButton({
            id: 'event-save',
            text: '✨ Erstellen',
            primary: true,
            onClick: () => KronosCreateDialog._handleSave(titleInput, calendarSelect, categorySelect, startInput, endInput, repeatCheckbox, patternSelect, repeatTillInput, modal)
        });
        footerContainer.appendChild(saveBtn);
        
        dialog.appendChild(footerContainer);
        
        // Setup Close Handlers
        KronosModalBase.setupCloseHandlers(modal, null);
    }
    
    /**
     * 💾 HANDLE SAVE
     */
    static _handleSave(titleInput, calendarSelect, categorySelect, startInput, endInput, repeatCheckbox, patternSelect, repeatTillInput, modal) {
        console.log('💾 Create Dialog Save');
        
        const title = titleInput.value.trim();
        const calendar = calendarSelect.value;
        const category = categorySelect.value;
        const start = startInput.value;
        const end = endInput.value || start;
        const isRepeat = repeatCheckbox.checked;
        
        if (!title) {
            KronosModalHelpers.showWarning('Bitte einen Titel eingeben!');
            titleInput.focus();
            return;
        }
        
        if (!calendar) {
            KronosModalHelpers.showWarning('Bitte einen Kalender wählen!');
            return;
        }
        
        if (!start) {
            KronosModalHelpers.showWarning('Bitte ein Startdatum eingeben!');
            return;
        }
        
        const doc = {
            doctype: 'Element',
            element_name: title,
            element_calendar: calendar,
            element_category: category || null,
            element_start: KronosModalHelpers.convertToMySQLDatetime(start),
            element_end: KronosModalHelpers.convertToMySQLDatetime(end),
            repeat_this_event: isRepeat ? 1 : 0
        };
        
        if (isRepeat) {
            const pattern = patternSelect.value;
            const repeatTill = repeatTillInput.value;
            
            if (!repeatTill) {
                KronosModalHelpers.showWarning('Bitte ein Enddatum eingeben!');
                return;
            }
            
            doc.repeat_on = pattern;
            doc.repeat_till = repeatTill;
            
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
            cache: false,
            callback: (r) => {
                if (r.message) {
                    const elementId = r.message.name;
                    console.log('✅ Element erstellt:', elementId);
                    
                    if (isRepeat) {
                        console.log('🔄 Erstelle Serie-Instanzen für:', elementId);
                        
                        frappe.call({
                            method: 'diakronos.kronos.api.series_create.create_event_series',
                            args: { series_element_id: elementId },
                            cache: false,
                            callback: (series_response) => {
                                console.log('✅ Serie erstellt:', series_response.message);
                                KronosModalHelpers.showSuccess(`${series_response.message.generated_count} Termine erstellt!`);
                                KronosModalHelpers.closeModal(modal);
                                
                                if (window.kronosCalendar) {
                                    window.kronosCalendar.refetchEvents();
                                }
                            },
                            error: (err) => {
                                console.error('❌ Serie-Fehler:', err);
                                KronosModalHelpers.showError('Fehler beim Erstellen der Serie');
                                KronosModalHelpers.closeModal(modal);
                            }
                        });
                    } else {
                        KronosModalHelpers.showSuccess(`Termin "${title}" erstellt!`);
                        KronosModalHelpers.closeModal(modal);
                        
                        if (window.kronosCalendar) {
                            window.kronosCalendar.refetchEvents();
                        }
                    }
                }
            },
            error: (err) => {
                console.error('❌ Fehler beim Erstellen:', err);
                KronosModalHelpers.showError('Fehler beim Erstellen des Termins');
            }
        });
    }
}


// Export
window.KronosCreateDialog = KronosCreateDialog;
console.log('✅ Create Dialog geladen');
