// modal_create.js – neuer_termin_dialog

import { kronosCalendar } from '../builder/kronos_calendar.js';
import { escHtml }         from '../html_utils.js';
import { PendingManager }  from '../backend/pending_manager.js';
import { showConflictModal } from './modal_conflict.js';

class DiakronosCreateModal {
    static async show(initialData = {}) {
        const element = initialData || {};

        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

        // Schreibbare Kalender, Kategorien, Ressourcen und Einstellungen parallel laden
        const [writableCalendars, categories, ressources, settings] = await Promise.all([
            fetch('/api/method/diakronos.kronos.api.permissions.get_writable_calendars')
                .then(r => r.ok ? r.json().then(d => d.message || []) : [])
                .catch(() => []),
            fetch('/api/resource/Eventkategorie?fields=["name","event_category_name"]&limit_page_length=500')
                .then(r => r.ok ? r.json().then(d => d.data || []) : [])
                .catch(() => []),
            fetch('/api/method/diakronos.kronos.api.ressource_api.get_ressources', {
                method: 'POST', headers: { 'X-Frappe-CSRF-Token': csrfToken }
            }).then(r => r.ok ? r.json().then(d => d.message || []) : [])
              .catch(() => []),
            fetch('/api/method/diakronos.kronos.api.ressource_api.get_kronos_settings', {
                method: 'POST', headers: { 'X-Frappe-CSRF-Token': csrfToken }
            }).then(r => r.ok ? r.json().then(d => d.message || {}) : {})
              .catch(() => ({})),
        ]);

        const calendarColors = {};
        writableCalendars.forEach(cal => {
            calendarColors[cal.name] = cal.calendar_color || '#9ca3af';
        });

        const ressourcePflicht    = settings.ressource_pflichtfeld || false;
        const standardRessource   = element.ressource || settings.standard_ressource || '';

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

                        <!-- Tab 1: Grunddaten -->
                        <div id="tab-basic" class="tab-content active">
                            <div class="diakronos-modal-body">
                                <div class="form-group">
                                    <label>Titel <span class="required">*</span></label>
                                    <input type="text" id="element_name" value="${escHtml(element.element_name || '')}" required>
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

                                <div class="form-group">
                                    <label>Ressource ${ressourcePflicht ? '<span class="required">*</span>' : ''}</label>
                                    <select id="element_ressource">
                                        <option value="">— Kein Raum —</option>
                                        ${ressources.map(r => `
                                            <option value="${escHtml(r.id)}" ${standardRessource === r.id ? 'selected' : ''}>
                                                ${escHtml(r.title)}${r.kapazitaet ? ` (${r.kapazitaet} Plätze)` : ''}
                                            </option>
                                        `).join('')}
                                    </select>
                                </div>
                            </div>
                        </div>

                        <!-- Tab 2: Details -->
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

                                <div class="checkbox-row">
                                    <label class="checkbox-label checkbox-label-muted" title="Dieser Termin löst keine Konflikte aus, auch wenn die Ressource belegt ist">
                                        <input type="checkbox" id="ignore_conflict" ${element.ignore_conflict ? 'checked' : ''}>
                                        Konflikte ignorieren
                                    </label>
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

        // Farbleiste
        const colorBar  = modal.querySelector('#modal-color-bar');
        const calSelect = modal.querySelector('#element_calendar');
        calSelect.addEventListener('change', () => {
            colorBar.style.backgroundColor = calendarColors[calSelect.value] || 'var(--primary)';
        });

        // Vorauswahl Kalender-Farbe
        if (element.element_calendar && calendarColors[element.element_calendar]) {
            calSelect.value = element.element_calendar;
            colorBar.style.backgroundColor = calendarColors[element.element_calendar];
        }

        // Tab-Switching
        modal.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                modal.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                modal.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');
                modal.querySelector(`#tab-${btn.dataset.tab}`).classList.add('active');
            });
        });

        // Serie-Checkbox
        const repeatCheckbox = modal.querySelector('#repeat_this_event');
        const seriesOptions  = modal.querySelector('#series-options');
        repeatCheckbox.addEventListener('change', () => {
            seriesOptions.style.display = repeatCheckbox.checked ? 'block' : 'none';
        });

        // Flatpickr
        const startInput = modal.querySelector('#element_start');
        const endInput   = modal.querySelector('#element_end');
        let fpStart = null, fpEnd = null;

        if (window.flatpickr) {
            const fpLocale = window.flatpickr.l10ns?.de || 'default';
            const baseOpts = {
                locale: fpLocale, enableTime: true, time_24hr: true,
                dateFormat: 'Y-m-dTH:i', altInput: true,
                altFormat: 'j. F Y, H:i', minuteIncrement: 5,
            };
            fpStart = window.flatpickr(startInput, {
                ...baseOpts,
                defaultDate: element.element_start || null,
                onChange: ([date]) => {
                    if (!date || !fpEnd) return;
                    const endDates = fpEnd.selectedDates;
                    if (!endDates.length || endDates[0] <= date) {
                        fpEnd.setDate(new Date(date.getTime() + 60 * 60 * 1000));
                    }
                    fpEnd.set('minDate', date);
                },
            });
            fpEnd = window.flatpickr(endInput, {
                ...baseOpts,
                defaultDate: element.element_end || null,
                minDate: element.element_start || null,
            });
            const seriesEndInput = modal.querySelector('#series_end');
            if (seriesEndInput) {
                window.flatpickr(seriesEndInput, {
                    locale: fpLocale, dateFormat: 'Y-m-d',
                    altInput: true, altFormat: 'j. F Y', minDate: 'today',
                });
            }
        }

        // Ganztägig
        const allDayCheckbox = modal.querySelector('#all_day');
        allDayCheckbox.addEventListener('change', () => {
            const isAllDay = allDayCheckbox.checked;
            if (fpStart && fpEnd) {
                fpStart.set('enableTime', !isAllDay);
                fpEnd.set('enableTime', !isAllDay);
                if (isAllDay) {
                    // Nur Zeitkomponenten anpassen, Datum beibehalten
                    const startDate = fpStart.selectedDates[0];
                    const endDate = fpEnd.selectedDates[0] || startDate;
                    
                    if (startDate) {
                        fpStart.setDate(new Date(startDate.getFullYear(), startDate.getMonth(), 
                                                startDate.getDate(), 0, 0));
                    }
                    if (endDate) {
                        fpEnd.setDate(new Date(endDate.getFullYear(), endDate.getMonth(), 
                                              endDate.getDate(), 23, 59));
                    }
                }
            }
        });

        // Schließen
        const closeModal = () => { modal.classList.remove('show'); setTimeout(() => modal.remove(), 200); };
        modal.querySelector('.diakronos-close-btn').onclick = closeModal;
        modal.querySelector('#cancel-btn').onclick = closeModal;
        modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });
        document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); }, { once: true });

        const showError = (msg) => {
            const el = modal.querySelector('#modal-error');
            el.textContent = msg;
            el.classList.add('visible');
        };

        const switchToTab = (tabName) => {
            modal.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            modal.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            modal.querySelector(`[data-tab="${tabName}"]`)?.classList.add('active');
            modal.querySelector(`#tab-${tabName}`)?.classList.add('active');
        };

        // Speichern
        modal.querySelector('#save-btn').addEventListener('click', async () => {
            const calendarVal  = calSelect.value;
            const ressourceVal = modal.querySelector('#element_ressource').value;
            const titleVal     = modal.querySelector('#element_name').value.trim();

            if (!titleVal) { switchToTab('basic'); showError('Bitte einen Titel eingeben.'); return; }
            if (!calendarVal) { switchToTab('basic'); showError('Bitte einen Kalender auswählen.'); return; }

            const hasStart = fpStart ? fpStart.selectedDates.length > 0 : !!startInput.value;
            if (!hasStart) { switchToTab('basic'); showError('Bitte Beginn ausfüllen.'); return; }

            if (ressourcePflicht && !ressourceVal) {
                switchToTab('basic');
                showError('Bitte eine Ressource auswählen (Pflichtfeld in den Einstellungen).');
                return;
            }

            const startVal   = startInput.value;
            const endVal     = endInput.value;
            const isSeries   = repeatCheckbox.checked;
            const ignoreConf = modal.querySelector('#ignore_conflict').checked;

            // Konfliktprüfung
            let finalStatus        = undefined; // Backend setzt "Vorschlag"
            let finalIgnoreConflict = ignoreConf;

            if (ressourceVal && !ignoreConf) {
                const csrfT = document.querySelector('meta[name="csrf-token"]')?.content || '';
                try {
                    const conflictRes = await fetch('/api/method/diakronos.kronos.api.ressource_api.check_resource_conflict', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrfT },
                        body: JSON.stringify({ ressource: ressourceVal, element_start: startVal, element_end: endVal })
                    });
                    if (conflictRes.ok) {
                        const conflictData = (await conflictRes.json()).message;
                        if (conflictData) {
                            const decision = await showConflictModal(conflictData);
                            if (decision === null) return; // Abbrechen
                            if (decision === 'ignore')   finalIgnoreConflict = true;
                            if (decision === 'conflict') finalStatus = 'Konflikt';
                        }
                    }
                } catch (e) {
                    console.warn('Konfliktprüfung fehlgeschlagen (wird ignoriert):', e);
                }
            }

            const saveBtn = modal.querySelector('#save-btn');
            saveBtn.disabled = true;
            saveBtn.textContent = '…';

            const endpoint = isSeries
                ? '/api/method/diakronos.kronos.api.event_crud.create_series'
                : '/api/method/diakronos.kronos.api.event_crud.create_event';

            const payload = {
                element_name:     titleVal,
                element_start:    startVal,
                element_end:      endVal,
                element_calendar: calendarVal,
                all_day:          allDayCheckbox.checked,
                description:      modal.querySelector('#description').value,
                element_category: modal.querySelector('#element_category').value,
                ressource:        ressourceVal,
                ignore_conflict:  finalIgnoreConflict,
                ...(finalStatus ? { status: finalStatus } : {}),
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
                    const result = await response.json();
                    // Einzeltermin: id, Serientermine: created_ids[]
                    const createdIds = result.message?.created_ids || (result.message?.id ? [result.message.id] : []);
                    for (const id of createdIds) {
                        PendingManager.add(id, calendarVal, titleVal);
                    }
                    if (finalStatus === 'Konflikt') {
                        document.dispatchEvent(new CustomEvent('kronos:conflict_created'));
                    }
                    if (kronosCalendar) kronosCalendar.refetchEvents();
                    closeModal();
                } else {
                    const errText = await response.text();
                    console.error('Fehler-Details:', errText);
                    showError('Fehler beim Erstellen. Bitte erneut versuchen.');
                    saveBtn.disabled = false;
                    saveBtn.textContent = 'Erstellen';
                }
            } catch (err) {
                console.error('API-Fehler:', err);
                showError('Verbindungsfehler. Bitte Seite neu laden.');
                saveBtn.disabled = false;
                saveBtn.textContent = 'Erstellen';
            }
        });
    }
}

export { DiakronosCreateModal };
