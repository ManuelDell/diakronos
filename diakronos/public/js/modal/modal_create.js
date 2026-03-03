// modal_create.js – neuer_termin_dialog

import { kronosCalendar } from '../builder/kronos_calendar.js';
import { escHtml } from '../html_utils.js';

class DiakronosCreateModal {
    static async show(initialData = {}) {
        const element = initialData || {};

        // Schreibbare Kalender laden (inkl. Farbe)
        let writableCalendars = [];
        try {
            const res = await fetch('/api/method/diakronos.kronos.api.permissions.get_writable_calendars');
            if (res.ok) {
                const data = await res.json();
                writableCalendars = data.message || [];
            }
        } catch (err) {
            console.warn('Schreibrechte konnten nicht geladen werden:', err);
        }

        // Farb-Map: { calendarName → color }
        const calendarColors = {};
        writableCalendars.forEach(cal => {
            calendarColors[cal.name] = cal.calendar_color || '#9ca3af';
        });

        // Alle Kategorien laden
        let categories = [];
        try {
            const res = await fetch('/api/resource/Eventkategorie?fields=["name","event_category_name"]&limit_page_length=500');
            if (res.ok) {
                const data = await res.json();
                categories = data.data || [];
            }
        } catch (err) {
            console.warn('Kategorien konnten nicht geladen werden:', err);
        }

        const modalHTML = `
            <div class="diakronos-modal" tabindex="-1" role="dialog">
                <div class="diakronos-modal-dialog modal-dialog-centered modal-lg">
                    <div class="diakronos-modal-content">
                        <div class="diakronos-color-bar" id="modal-color-bar" style="background-color: var(--primary);"></div>

                        <div class="diakronos-modal-header">
                            <h5 class="modal-title">Neuer Termin</h5>
                            <button type="button" class="diakronos-close-btn" aria-label="Schließen">&times;</button>
                        </div>

                        <div class="diakronos-tabs">
                            <button class="tab-btn active" data-tab="basic">Grunddaten</button>
                            <button class="tab-btn" data-tab="details">Details</button>
                        </div>

                        <!-- Tab 1: Grunddaten – Titel, Zeit, Kalender -->
                        <div id="tab-basic" class="tab-content active">
                            <div class="diakronos-modal-body">
                                <div class="form-group">
                                    <label>Titel <span class="required">*</span></label>
                                    <input type="text" id="element_name" value="${escHtml(element.element_name)}" required>
                                </div>

                                <div class="form-row">
                                    <div class="form-group">
                                        <label>Beginn <span class="required">*</span></label>
                                        <input type="text" id="element_start" placeholder="Datum und Uhrzeit wählen" readonly>
                                    </div>
                                    <div class="form-group">
                                        <label>Ende <span class="required">*</span></label>
                                        <input type="text" id="element_end" placeholder="Datum und Uhrzeit wählen" readonly>
                                    </div>
                                </div>

                                <div class="checkbox-row">
                                    <label class="checkbox-label">
                                        <input type="checkbox" id="all_day" ${element.all_day ? 'checked' : ''}>
                                        Ganztägig
                                    </label>
                                </div>

                                <div class="form-group">
                                    <label>Kalender <span class="required">*</span></label>
                                    <select id="element_calendar">
                                        <option value="">— Bitte wählen —</option>
                                        ${writableCalendars.map(cal => `
                                            <option value="${escHtml(cal.name)}" data-color="${escHtml(cal.calendar_color || '#9ca3af')}">
                                                ${escHtml(cal.calendar_name || cal.name)}
                                            </option>
                                        `).join('')}
                                    </select>
                                </div>
                            </div>
                        </div>

                        <!-- Tab 2: Details – Serie, Beschreibung, Kategorie -->
                        <div id="tab-details" class="tab-content">
                            <div class="diakronos-modal-body">
                                <div class="checkbox-row">
                                    <label class="checkbox-label">
                                        <input type="checkbox" id="repeat_this_event" ${element.repeat_this_event ? 'checked' : ''}>
                                        Termin wiederholen (Serie)
                                    </label>
                                </div>

                                <div id="series-options" class="series-options" style="display: ${element.repeat_this_event ? 'block' : 'none'};">
                                    <div class="form-row">
                                        <div class="form-group">
                                            <label>Wiederholung</label>
                                            <select id="repeat_type">
                                                <option value="weekly" selected>Wöchentlich</option>
                                                <option value="daily">Täglich</option>
                                                <option value="monthly">Monatlich</option>
                                                <option value="yearly">Jährlich</option>
                                            </select>
                                        </div>
                                        <div class="form-group">
                                            <label>Serie endet am</label>
                                            <input type="text" id="series_end" placeholder="Datum wählen" readonly>
                                        </div>
                                    </div>
                                </div>

                                <div class="description-group">
                                    <label>Beschreibung</label>
                                    <textarea id="description" rows="4">${element.description || ''}</textarea>
                                </div>

                                <div class="form-group">
                                    <label>Kategorie</label>
                                    <select id="element_category">
                                        <option value="">—</option>
                                        ${categories.map(cat => `
                                            <option value="${escHtml(cat.name)}">
                                                ${escHtml(cat.event_category_name || cat.name)}
                                            </option>
                                        `).join('')}
                                    </select>
                                </div>
                            </div>
                        </div>

                        <p class="modal-error" id="modal-error"></p>
                        <div class="diakronos-modal-footer">
                            <button type="button" class="btn btn-secondary" id="cancel-btn">Abbrechen</button>
                            <button type="button" class="btn btn-primary" id="save-btn">Erstellen</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        const modal = document.querySelector('.diakronos-modal:last-child');
        requestAnimationFrame(() => modal.classList.add('show'));

        // Farbleiste live aktualisieren bei Kalender-Auswahl
        const colorBar  = modal.querySelector('#modal-color-bar');
        const calSelect = modal.querySelector('#element_calendar');
        calSelect.addEventListener('change', () => {
            colorBar.style.backgroundColor = calendarColors[calSelect.value] || 'var(--primary)';
        });

        // Tab-Switching
        modal.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                modal.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                modal.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');
                modal.querySelector(`#tab-${btn.dataset.tab}`).classList.add('active');
            });
        });

        // Serie Checkbox
        const repeatCheckbox = modal.querySelector('#repeat_this_event');
        const seriesOptions  = modal.querySelector('#series-options');
        repeatCheckbox.addEventListener('change', () => {
            seriesOptions.style.display = repeatCheckbox.checked ? 'block' : 'none';
        });

        // Flatpickr – Datum/Uhrzeit-Picker
        const startInput = modal.querySelector('#element_start');
        const endInput   = modal.querySelector('#element_end');
        let fpStart = null, fpEnd = null;

        if (window.flatpickr) {
            const fpLocale = window.flatpickr.l10ns?.de || 'default';
            const baseOpts = {
                locale:          fpLocale,
                enableTime:      true,
                time_24hr:       true,
                dateFormat:      'Y-m-dTH:i',   // ISO-Format für Backend
                altInput:        true,
                altFormat:       'j. F Y, H:i',  // Anzeige: "15. März 2026, 14:30"
                minuteIncrement: 5,
            };

            fpStart = window.flatpickr(startInput, {
                ...baseOpts,
                defaultDate: element.element_start || null,
                onChange: ([date]) => {
                    if (!date || !fpEnd) return;
                    const endDates = fpEnd.selectedDates;
                    // End automatisch 1 h nach Start setzen wenn leer oder vor Start
                    if (!endDates.length || endDates[0] <= date) {
                        fpEnd.setDate(new Date(date.getTime() + 60 * 60 * 1000));
                    }
                    fpEnd.set('minDate', date);
                },
            });

            fpEnd = window.flatpickr(endInput, {
                ...baseOpts,
                defaultDate: element.element_end || null,
                minDate:     element.element_start || null,
            });

            // Serien-Enddatum: nur Datum, keine Uhrzeit
            const seriesEndInput = modal.querySelector('#series_end');
            if (seriesEndInput) {
                window.flatpickr(seriesEndInput, {
                    locale:     fpLocale,
                    dateFormat: 'Y-m-d',
                    altInput:   true,
                    altFormat:  'j. F Y',
                    minDate:    'today',
                });
            }
        }

        // Ganztägig → Zeitfelder deaktivieren
        const allDayCheckbox = modal.querySelector('#all_day');
        allDayCheckbox.addEventListener('change', () => {
            const isAllDay = allDayCheckbox.checked;
            if (fpStart && fpEnd) {
                fpStart.set('clickOpens', !isAllDay);
                fpEnd.set('clickOpens',   !isAllDay);
                if (fpStart.altInput) fpStart.altInput.disabled = isAllDay;
                if (fpEnd.altInput)   fpEnd.altInput.disabled   = isAllDay;
                if (isAllDay) {
                    const d = fpStart.selectedDates[0] || new Date();
                    const [y, mo, day] = [d.getFullYear(), d.getMonth(), d.getDate()];
                    fpStart.setDate(new Date(y, mo, day, 0, 0));
                    fpEnd.setDate(new Date(y, mo, day, 23, 59));
                }
            } else {
                startInput.disabled = isAllDay;
                endInput.disabled   = isAllDay;
            }
        });

        // Schließen
        modal.querySelector('.diakronos-close-btn').onclick = () => modal.remove();
        modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape') modal.remove(); }, { once: true });

        const showError = (msg) => {
            const el = modal.querySelector('#modal-error');
            el.textContent = msg;
            el.classList.add('visible');
        };

        const switchToTab = (tabName) => {
            modal.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            modal.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            modal.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
            modal.querySelector(`#tab-${tabName}`).classList.add('active');
        };

        // Speichern
        modal.querySelector('#save-btn').addEventListener('click', async () => {
            const calendarVal = calSelect.value;
            if (!calendarVal) {
                switchToTab('basic');
                showError('Bitte einen Kalender auswählen.');
                return;
            }
            const hasStart = fpStart ? fpStart.selectedDates.length > 0 : !!startInput.value;
            if (!hasStart) {
                switchToTab('basic');
                showError('Bitte Beginn ausfüllen.');
                return;
            }

            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
            const isSeries  = repeatCheckbox.checked;

            const endpoint = isSeries
                ? '/api/method/diakronos.kronos.api.event_crud.create_series'
                : '/api/method/diakronos.kronos.api.event_crud.create_event';

            const payload = {
                element_name:     modal.querySelector('#element_name').value,
                element_start:    startInput.value,
                element_end:      endInput.value,
                element_calendar: calendarVal,
                all_day:          allDayCheckbox.checked,
                description:      modal.querySelector('#description').value,
                element_category: modal.querySelector('#element_category').value,
                status:           'Festgelegt',
            };

            if (isSeries) {
                payload.repeat_type = modal.querySelector('#repeat_type').value;
                payload.series_end  = modal.querySelector('#series_end').value || null;
            }

            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'X-Frappe-CSRF-Token': csrfToken
                    },
                    body: JSON.stringify(payload)
                });

                if (response.ok) {
                    if (kronosCalendar) kronosCalendar.refetchEvents();
                    modal.remove();
                } else {
                    const errText = await response.text();
                    console.error('Fehler-Details:', errText);
                    showError('Fehler beim Erstellen. Bitte erneut versuchen.');
                }
            } catch (err) {
                console.error('API-Fehler:', err);
                showError('Verbindungsfehler. Bitte Seite neu laden.');
            }
        });

        // Abbrechen
        modal.querySelector('#cancel-btn').onclick = () => modal.remove();
    }
}

export { DiakronosCreateModal };
