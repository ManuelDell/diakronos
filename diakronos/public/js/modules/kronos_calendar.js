/**
 * ═══════════════════════════════════════════════════════════════
 * KRONOS CALENDAR - CALENDAR MODULE MIT SERIENTERMIN
 * ═══════════════════════════════════════════════════════════════
 * Verwaltet die FullCalendar Integration und Event-Handling
 * MIT: Modal-Dialog für Element-Erstellung mit Serientermin-Feldern
 */

class KronosCalendar {
    constructor() {
        this.calendar = null;
        this.currentFormData = null;
        console.log('📅 KronosCalendar Module geladen');
    }

    init() {
        const calendarEl = document.getElementById('calendar');
        if (!calendarEl) {
            console.error('❌ #calendar element nicht gefunden!');
            return;
        }

        console.log('🎯 Initialisiere FullCalendar...');
        
        const options = {
            headerToolbar: false,
            initialView: 'dayGridMonth',
            locale: 'de',
            firstDay: 1,
            dayMaxEvents: 3,
            height: '100%',
            contentHeight: '100%',

            events: (info, successCallback, failureCallback) => {
                this.loadEvents(info, successCallback, failureCallback);
            },

            eventDidMount: (info) => {
                this.styleEvent(info);
            },

            editable: true,
            eventDrop: (info) => window.kronosEvents.updateEvent(info.event),
            eventResize: (info) => window.kronosEvents.updateEvent(info.event),
            eventClick: (info) => {
                window.location.href = `/app/element/${info.event.id}`;
            },
            
            dateClick: (info) => {
                console.log('📅 dateClick triggered:', info.dateStr);
                this.handleDateClick(info);
            }
        };

        try {
            this.calendar = new FullCalendar.Calendar(calendarEl, options);
            this.calendar.render();
            console.log('✅ FullCalendar gerendert!');

            setTimeout(() => {
                this.calendar.updateSize();
                console.log('✅ Calendar Size updated');
            }, 100);
        } catch (e) {
            console.error('❌ Fehler beim Initialisieren:', e.message);
        }
    }

    handleDateClick(info) {
        console.log('🔐 Prüfe Schreibrechte...');
        
        frappe.call({
            method: 'diakronos.kronos.api.permissions.can_create_event',
            callback: (r) => {
                console.log('📋 Berechtigung-Response:', r.message);
                
                if (r.message && r.message.can_create) {
                    console.log('✅ User darf erstellen');
                    this.openQuickEntry(info.dateStr, r.message);
                } else {
                    console.log('🔒 User hat kein Schreibrecht');
                    frappe.show_alert({
                        message: '🔒 Du hast keine Berechtigung, Termine zu erstellen',
                        indicator: 'orange'
                    });
                }
            },
            error: (err) => {
                console.error('❌ Fehler bei Berechtigungsprüfung:', err);
                frappe.show_alert({
                    message: '❌ Fehler bei der Berechtigungsprüfung',
                    indicator: 'red'
                });
            }
        });
    }

    openQuickEntry(dateStr, permissionData) {
        console.log('📝 Öffne Element-Form Modal für:', dateStr);
        
        frappe.call({
            method: 'diakronos.kronos.api.permissions.get_element_creation_dialog_defaults',
            args: {
                date_str: dateStr,
                calendar_name: permissionData.default_calendar
            },
            callback: (r) => {
                console.log('📋 Dialog Defaults:', r.message);
                
                if (r.message && r.message.can_create) {
                    const defaults = r.message.defaults;
                    this.currentFormData = defaults;
                    
                    const modalId = 'kronos_element_modal_' + Date.now();
                    const html = `
                        <div id="${modalId}" class="kronos-modal" style="
                            position: fixed;
                            top: 0;
                            left: 0;
                            width: 100%;
                            height: 100%;
                            background: rgba(0,0,0,0.5);
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            z-index: 9999;
                            overflow-y: auto;
                        ">
                            <div class="kronos-modal-content" style="
                                background: white;
                                border-radius: 8px;
                                padding: 30px;
                                width: 90%;
                                max-width: 600px;
                                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                                margin: 20px auto;
                            ">
                                <h3 style="margin-top: 0; margin-bottom: 20px; font-size: 18px;">📅 Neuer Termin</h3>
                                
                                <div class="form-group" style="margin-bottom: 15px;">
                                    <label style="display: block; margin-bottom: 5px; font-weight: 500;">Titel *</label>
                                    <input type="text" id="modal_element_name" class="form-control" placeholder="z.B. Gottesdienst" required style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box;">
                                </div>
                                
                                <div class="form-group" style="margin-bottom: 15px;">
                                    <label style="display: block; margin-bottom: 5px; font-weight: 500;">Kalender *</label>
                                    <select id="modal_element_calendar" class="form-control" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box;">
                                        ${permissionData.writable_calendars.map(cal => 
                                            `<option value="${cal.value}" ${cal.value === defaults.element_calendar ? 'selected' : ''}>${cal.label}</option>`
                                        ).join('')}
                                    </select>
                                </div>
                                
                                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px;">
                                    <div class="form-group">
                                        <label style="display: block; margin-bottom: 5px; font-weight: 500; font-size: 13px;">Start *</label>
                                        <input type="datetime-local" id="modal_element_start" class="form-control" value="${this.formatDatetimeLocal(defaults.element_start)}" required style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; font-size: 12px;">
                                    </div>
                                    
                                    <div class="form-group">
                                        <label style="display: block; margin-bottom: 5px; font-weight: 500; font-size: 13px;">Ende *</label>
                                        <input type="datetime-local" id="modal_element_end" class="form-control" value="${this.formatDatetimeLocal(defaults.element_end)}" required style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; font-size: 12px;">
                                    </div>
                                </div>
                                
                                <hr style="margin: 20px 0; border: none; border-top: 1px solid #e0e0e0;">
                                <h4 style="margin-top: 20px; margin-bottom: 15px; font-size: 14px; font-weight: 600;">Serientermin (Wiederholung)</h4>
                                
                                <div class="form-group" style="margin-bottom: 15px;">
                                    <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; font-weight: 500;">
                                        <input type="checkbox" id="modal_repeatthisevent" style="width: 16px; height: 16px; cursor: pointer;">
                                        <span>Diese Veranstaltung wiederholen</span>
                                    </label>
                                </div>
                                
                                <div id="repeat_pattern_section" style="display: none; margin-bottom: 15px;">
                                    <label style="display: block; margin-bottom: 8px; font-weight: 500; font-size: 13px;">Wiederholungsmuster</label>
                                    <select id="modal_repeaton" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box;">
                                        <option value="Daily">Täglich</option>
                                        <option value="Weekly" selected>Wöchentlich</option>
                                        <option value="Monthly">Monatlich</option>
                                        <option value="Quarterly">Vierteljährlich</option>
                                        <option value="Half Yearly">Halbjährlich</option>
                                        <option value="Yearly">Jährlich</option>
                                    </select>
                                </div>
                                
                                <div id="weekday_section" style="display: none; margin-bottom: 15px;">
                                    <label style="display: block; margin-bottom: 10px; font-weight: 500; font-size: 13px;">Wochentage</label>
                                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px;">
                                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px;">
                                            <input type="checkbox" id="modal_monday" style="cursor: pointer;">
                                            <span>Montag</span>
                                        </label>
                                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px;">
                                            <input type="checkbox" id="modal_tuesday" style="cursor: pointer;">
                                            <span>Dienstag</span>
                                        </label>
                                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px;">
                                            <input type="checkbox" id="modal_wednesday" style="cursor: pointer;">
                                            <span>Mittwoch</span>
                                        </label>
                                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px;">
                                            <input type="checkbox" id="modal_thursday" style="cursor: pointer;">
                                            <span>Donnerstag</span>
                                        </label>
                                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px;">
                                            <input type="checkbox" id="modal_friday" style="cursor: pointer;">
                                            <span>Freitag</span>
                                        </label>
                                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px;">
                                            <input type="checkbox" id="modal_saturday" style="cursor: pointer;">
                                            <span>Samstag</span>
                                        </label>
                                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px;">
                                            <input type="checkbox" id="modal_sunday" style="cursor: pointer;">
                                            <span>Sonntag</span>
                                        </label>
                                    </div>
                                </div>
                                
                                <div id="repeat_till_section" style="display: none;">
                                    <label style="display: block; margin-bottom: 5px; font-weight: 500; font-size: 13px;">Wiederholungen bis</label>
                                    <input type="date" id="modal_repeattill" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box;">
                                    <small style="color: #999; display: block; margin-top: 3px;">Leer lassen = endlose Wiederholung</small>
                                </div>
                                
                                <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px;">
                                    <button id="btn_cancel_${modalId}" class="btn btn-secondary" style="padding: 10px 16px; cursor: pointer; background: #f0f0f0; border: 1px solid #ddd; border-radius: 4px; font-weight: 500;">Abbrechen</button>
                                    <button id="btn_save_${modalId}" class="btn btn-primary" style="padding: 10px 16px; cursor: pointer; background: #2196F3; color: white; border: none; border-radius: 4px; font-weight: 500;">💾 Speichern</button>
                                </div>
                            </div>
                        </div>
                    `;
                    
                    document.body.insertAdjacentHTML('beforeend', html);
                    
                    const self = this;
                    const modal = document.getElementById(modalId);
                    
                    const repeatCheckbox = document.getElementById('modal_repeatthisevent');
                    const repeatPatternSection = document.getElementById('repeat_pattern_section');
                    const weekdaySection = document.getElementById('weekday_section');
                    const repeatTillSection = document.getElementById('repeat_till_section');
                    const repeatOnSelect = document.getElementById('modal_repeaton');
                    
                    repeatCheckbox.addEventListener('change', () => {
                        const isChecked = repeatCheckbox.checked;
                        repeatPatternSection.style.display = isChecked ? 'block' : 'none';
                        repeatTillSection.style.display = isChecked ? 'block' : 'none';
                        
                        if (isChecked && repeatOnSelect.value === 'Weekly') {
                            weekdaySection.style.display = 'grid';
                        } else {
                            weekdaySection.style.display = 'none';
                        }
                    });
                    
                    repeatOnSelect.addEventListener('change', () => {
                        if (repeatCheckbox.checked && repeatOnSelect.value === 'Weekly') {
                            weekdaySection.style.display = 'grid';
                        } else {
                            weekdaySection.style.display = 'none';
                        }
                    });
                    
                    document.getElementById(`btn_save_${modalId}`).addEventListener('click', () => {
                        console.log('💾 Save Button geklickt');
                        self.saveElement();
                        modal.remove();
                    });
                    
                    document.getElementById(`btn_cancel_${modalId}`).addEventListener('click', () => {
                        console.log('❌ Formular abgebrochen');
                        modal.remove();
                    });
                    
                    modal.addEventListener('click', (e) => {
                        if (e.target === modal) {
                            console.log('❌ Modal geschlossen (außerhalb geklickt)');
                            modal.remove();
                        }
                    });
                    
                } else {
                    frappe.show_alert({
                        message: '❌ Fehler beim Laden der Dialog-Einstellungen',
                        indicator: 'red'
                    });
                }
            },
            error: (err) => {
                console.error('❌ Fehler beim Laden der Dialog-Defaults:', err);
                frappe.show_alert({
                    message: '❌ Fehler beim Öffnen des Formulars',
                    indicator: 'red'
                });
            }
        });
    }


    formatDatetimeLocal(datetimeStr) {
        if (!datetimeStr) return '';
        return datetimeStr.replace(' ', 'T').slice(0, 16);
    }

    saveElement() {
        console.log('💾 Speichere Element mit Serie...');
        
        const element_name = document.getElementById('modal_element_name')?.value;
        const element_calendar = document.getElementById('modal_element_calendar')?.value;
        const element_start = document.getElementById('modal_element_start')?.value;
        const element_end = document.getElementById('modal_element_end')?.value;
        
        // Serie-Felder
        const repeatthisevent = document.getElementById('modal_repeatthisevent')?.checked ? 1 : 0;
        const repeaton = document.getElementById('modal_repeaton')?.value || 'Weekly';
        const repeattill = document.getElementById('modal_repeattill')?.value || null;
        
        // Wochentage
        const monday = document.getElementById('modal_monday')?.checked ? 1 : 0;
        const tuesday = document.getElementById('modal_tuesday')?.checked ? 1 : 0;
        const wednesday = document.getElementById('modal_wednesday')?.checked ? 1 : 0;
        const thursday = document.getElementById('modal_thursday')?.checked ? 1 : 0;
        const friday = document.getElementById('modal_friday')?.checked ? 1 : 0;
        const saturday = document.getElementById('modal_saturday')?.checked ? 1 : 0;
        const sunday = document.getElementById('modal_sunday')?.checked ? 1 : 0;
        
        console.log('🔍 Form Values:', { element_name, element_calendar, element_start, element_end, repeatthisevent, repeaton });
        
        if (!element_name || element_name.trim() === '') {
            frappe.show_alert({ 
                message: '❌ Titel erforderlich', 
                indicator: 'red' 
            });
            return;
        }
        
        if (!element_start || !element_end) {
            frappe.show_alert({ 
                message: '❌ Start- und Endzeit erforderlich', 
                indicator: 'red' 
            });
            return;
        }
        
        const startDateTime = element_start.replace('T', ' ') + ':00';
        const endDateTime = element_end.replace('T', ' ') + ':00';
        
        console.log('📤 Sende Daten zum Backend:', { element_name, element_calendar, startDateTime, endDateTime, repeatthisevent });
        
        // Baue Element-Objekt - EXAKT wie in der Element-DocType Definition
        const docData = {
            doctype: 'Element',
            element_name: element_name,
            element_calendar: element_calendar,
            element_start: startDateTime,
            element_end: endDateTime,
            repeatthisevent: repeatthisevent,
            repeaton: repeaton,
            repeattill: repeattill,
            monday: monday,
            tuesday: tuesday,
            wednesday: wednesday,
            thursday: thursday,
            friday: friday,
            saturday: saturday,
            sunday: sunday
        };
        
        frappe.call({
            method: 'frappe.client.insert',
            args: {
                doc: docData
            },
            callback: (r) => {
                console.log('✅ Response:', r);
                if (r.message) {
                    console.log('✅ Element erstellt:', r.message.name);
                    frappe.show_alert({
                        message: `✅ Termin "${element_name}" erfolgreich erstellt!`,
                        indicator: 'green'
                    });
                    
                    // Cache leeren damit neue Events geladen werden
                    frappe.call({
                        method: 'diakronos.kronos.api.events.clear_events_cache',
                        callback: () => {
                            console.log('🔄 Cache geleert, lade Events neu...');
                            setTimeout(() => {
                                this.refetchEvents();
                            }, 300);
                        }
                    });
                }
            },
            error: (err) => {
                console.error('❌ Fehler beim Speichern:', err);
                frappe.show_alert({
                    message: '❌ Fehler beim Speichern des Termins',
                    indicator: 'red'
                });
            }
        });
    }


    loadEvents(info, successCallback, failureCallback) {
        const startDate = info.startStr.split('T')[0];
        const endDate = info.endStr.split('T')[0];
        
        console.log(`📅 Loading events: ${startDate} → ${endDate}`);
        
        frappe.call({
            method: 'diakronos.kronos.api.events.get_calendar_events',
            args: {
                start_date: startDate,
                end_date: endDate,
                calendar_filter: '[]'
            },
            callback: (r) => {
                const events = (r.message || []).map(e => this.mapEvent(e));
                console.log(`✅ ${events.length} Events geladen`);
                successCallback(events);
            },
            error: (err) => {
                console.error('❌ API Error:', err);
                successCallback([]);
            }
        });
    }

    mapEvent(e) {
        const colorMap = {
            'Gottesdienst': '#c41e3a',
            'Bibelstunde': '#4285f4',
            'Gebetskreis': '#34a853',
            'Musikprobe': '#fbbc04',
            'Jugend': '#ea4335',
            'Kinder': '#9c27b0',
            'Seelsorge': '#00bcd4'
        };
        
        let bgColor = '#1f73e6';
        for (const [key, color] of Object.entries(colorMap)) {
            if (e.title && e.title.includes(key)) {
                bgColor = color;
                break;
            }
        }
        
        return {
            id: e.name,
            title: e.title,
            start: e.start,
            end: e.end || e.start,
            backgroundColor: bgColor,
            borderColor: 'transparent',
            textColor: '#fff',
            allDay: e.isAllday || false
        };
    }

    styleEvent(info) {
        if (info.event.backgroundColor) {
            info.el.style.backgroundColor = info.event.backgroundColor;
            info.el.style.color = '#fff';
            info.el.style.borderColor = 'transparent';
        }
    }

    changeView(view) {
        this.calendar?.changeView(view);
    }

    prev() {
        this.calendar?.prev();
    }

    next() {
        this.calendar?.next();
    }

    today() {
        this.calendar?.today();
    }

    getDate() {
        return this.calendar?.getDate() || new Date();
    }

    refetchEvents() {
        console.log('🔄 Lade Events neu...');
        this.calendar?.refetchEvents();
    }
}

window.kronosCalendar = new KronosCalendar();
console.log('✅ Calendar Modul initialisiert');
