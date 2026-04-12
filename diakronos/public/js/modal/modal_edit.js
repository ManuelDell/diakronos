// modal_edit.js – Termin bearbeiten

import { kronosCalendar } from '../builder/kronos_calendar.js';
import { escHtml, safeCssColor } from '../html_utils.js';
import { showConflictModal } from './modal_conflict.js';

class DiakronosEditModal {
    static async show(element) {
        if (!element?.name) {
            console.warn('⚠️ Kein valides Element übergeben');
            return;
        }

        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

        // Daten parallel laden
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

        const ressourcePflicht  = settings.ressource_pflichtfeld || false;
        const currentRessource  = element.ressource || '';

        const modalHTML = `
        <div class="diakronos-modal fade show" tabindex="-1" role="dialog">
            <div class="diakronos-modal-dialog modal-dialog-centered modal-lg">
                <div class="diakronos-modal-content">
                    <div class="diakronos-color-bar" style="background-color: ${safeCssColor(element.element_color)};"></div>

                    <div class="diakronos-modal-header">
                        <h5 class="modal-title">Termin bearbeiten</h5>
                        <button type="button" class="diakronos-close-btn" aria-label="Schließen">×</button>
                    </div>

                    <div class="diakronos-tabs">
                        <button class="tab-btn active" data-tab="basic">Grunddaten</button>
                        <button class="tab-btn" data-tab="details">Weitere Details</button>
                    </div>

                    <div class="diakronos-modal-body">
                        <!-- Tab 1: Grunddaten -->
                        <div id="tab-basic" class="tab-content active">
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
                                <label>Ressource ${ressourcePflicht ? '<span class="required">*</span>' : ''}</label>
                                <select id="element_ressource">
                                    <option value="">— Kein Raum —</option>
                                    ${ressources.map(r => `
                                        <option value="${escHtml(r.id)}" ${currentRessource === r.id ? 'selected' : ''}>
                                            ${escHtml(r.title)}${r.kapazitaet ? ` (${r.kapazitaet} Plätze)` : ''}
                                        </option>
                                    `).join('')}
                                </select>
                            </div>

                            <div class="description-group">
                                <label>Beschreibung</label>
                                <textarea id="description" rows="4">${element.description || ''}</textarea>
                            </div>
                        </div>

                        <!-- Tab 2: Weitere Details -->
                        <div id="tab-details" class="tab-content">
                            <div class="form-group">
                                <label>Kalender</label>
                                <select id="element_calendar">
                                    <option value="">— Bitte wählen —</option>
                                    ${writableCalendars.map(cal => `
                                        <option value="${escHtml(cal.name)}" ${cal.name === element.element_calendar ? 'selected' : ''}>
                                            ${escHtml(cal.calendar_name || cal.name)}
                                        </option>
                                    `).join('')}
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Kategorie</label>
                                <select id="element_category">
                                    <option value="">—</option>
                                    ${categories.map(cat => `
                                        <option value="${escHtml(cat.name)}" ${cat.name === element.element_category ? 'selected' : ''}>
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
                        <button type="button" class="btn btn-danger" id="delete-btn">Löschen</button>
                        <div class="footer-right">
                            <button type="button" class="btn btn-secondary" id="cancel-btn">Abbrechen</button>
                            <button type="button" class="btn btn-primary" id="save-btn">Speichern</button>
                        </div>
                    </div>
                    <div class="diakronos-modal-footer delete-confirm" id="delete-confirm" style="display:none;">
                        <span class="delete-confirm-text">Termin wirklich löschen?</span>
                        <div class="footer-right">
                            <button type="button" class="btn btn-secondary" id="delete-cancel-btn">Abbrechen</button>
                            <button type="button" class="btn btn-danger" id="delete-confirm-btn">Ja, löschen</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        const modal = document.querySelector('.diakronos-modal:last-child');

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
                defaultDate: element.element_start ? element.element_start.slice(0, 16) : null,
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
                defaultDate: element.element_end ? element.element_end.slice(0, 16) : null,
                minDate:     element.element_start ? element.element_start.slice(0, 16) : null,
            });
        }

        // Ganztägig → nur Zeitauswahl deaktivieren, Datumsauswahl bleibt aktiv
        const allDayCheckbox = modal.querySelector('#all_day');
        allDayCheckbox.addEventListener('change', () => {
            const isAllDay = allDayCheckbox.checked;
            if (fpStart && fpEnd) {
                // Datumsauswahl immer erlauben (clickOpens = true)
                // Nur Zeitauswahl dynamisch ein/ausschalten
                fpStart.set('enableTime', !isAllDay);
                fpEnd.set('enableTime', !isAllDay);
                // altInput nicht deaktivieren (Eingabefeld bleibt bedienbar)
                if (isAllDay) {
                    // Nur Zeitkomponenten anpassen, Datum beibehalten
                    const startDate = fpStart.selectedDates[0];
                    const endDate = fpEnd.selectedDates[0] || startDate;
                    
                    if (startDate) {
                        fpStart.setDate(new Date(startDate.getFullYear(), startDate.getMonth(), 
                                                startDate.getDate(), 0, 0));
                    }
                    if (endDate) {
                        fpEnd.setDate(new Date(endDate.getFullYear(), endDate.getMonth(), endDate.getDate(), 23, 59));
                    }
                }
            } else {
                startInput.disabled = isAllDay;
                endInput.disabled   = isAllDay;
            }
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

        const switchToTab = (tabName) => {
            modal.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            modal.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            modal.querySelector(`[data-tab="${tabName}"]`)?.classList.add('active');
            modal.querySelector(`#tab-${tabName}`)?.classList.add('active');
        };

        const showError = (msg) => {
            const el = modal.querySelector('#modal-error');
            el.textContent = msg;
            el.classList.add('visible');
        };

        // Schließen
        modal.querySelector('.diakronos-close-btn').onclick = () => modal.remove();
        modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape') modal.remove(); }, { once: true });
        modal.querySelector('#cancel-btn').onclick = () => modal.remove();

        // Löschen – inline Bestätigung
        const mainFooter    = modal.querySelector('.diakronos-modal-footer:not(.delete-confirm)');
        const confirmFooter = modal.querySelector('#delete-confirm');
        modal.querySelector('#delete-btn').onclick = () => {
            mainFooter.style.display    = 'none';
            confirmFooter.style.display = 'flex';
        };
        modal.querySelector('#delete-cancel-btn').onclick = () => {
            confirmFooter.style.display = 'none';
            mainFooter.style.display    = 'flex';
        };
        modal.querySelector('#delete-confirm-btn').addEventListener('click', async () => {
            const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
            try {
                const response = await fetch('/api/method/diakronos.kronos.api.event_crud.delete_event', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'X-Frappe-CSRF-Token': csrf
                    },
                    body: JSON.stringify({ name: element.name })
                });
                if (response.ok) {
                    if (kronosCalendar) kronosCalendar.refetchEvents();
                    modal.remove();
                } else {
                    confirmFooter.style.display = 'none';
                    mainFooter.style.display    = 'flex';
                    showError('Löschen fehlgeschlagen. Bitte erneut versuchen.');
                }
            } catch (err) {
                console.error('API-Fehler:', err);
            }
        });

        // Speichern
        modal.querySelector('#save-btn').addEventListener('click', async () => {
            const csrf         = document.querySelector('meta[name="csrf-token"]')?.content || '';
            const ressourceVal = modal.querySelector('#element_ressource').value;
            const ignoreConf   = modal.querySelector('#ignore_conflict').checked;
            const startVal     = startInput.value;
            const endVal       = endInput.value;

            if (!modal.querySelector('#element_name').value.trim()) {
                switchToTab('basic');
                showError('Bitte einen Titel eingeben.');
                return;
            }

            if (ressourcePflicht && !ressourceVal) {
                switchToTab('basic');
                showError('Bitte eine Ressource auswählen (Pflichtfeld in den Einstellungen).');
                return;
            }

            // Konfliktprüfung
            let finalStatus        = element.status || 'Festgelegt';
            let finalIgnoreConflict = ignoreConf;

            if (ressourceVal && !ignoreConf) {
                try {
                    const conflictRes = await fetch('/api/method/diakronos.kronos.api.ressource_api.check_resource_conflict', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
                        body: JSON.stringify({
                            ressource:     ressourceVal,
                            element_start: startVal,
                            element_end:   endVal,
                            exclude_id:    element.name
                        })
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

            const payload = {
                name:             element.name,
                element_name:     modal.querySelector('#element_name').value,
                element_start:    startVal,
                element_end:      endVal,
                all_day:          allDayCheckbox.checked,
                description:      modal.querySelector('#description').value,
                element_category: modal.querySelector('#element_category').value,
                element_calendar: modal.querySelector('#element_calendar').value,
                ressource:        ressourceVal,
                ignore_conflict:  finalIgnoreConflict,
                status:           finalStatus,
                series_id:        element.series_id || ''
            };

            try {
                const response = await fetch('/api/method/diakronos.kronos.api.event_crud.save_event', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'X-Frappe-CSRF-Token': csrf
                    },
                    body: JSON.stringify(payload)
                });

                if (response.ok) {
                    if (finalStatus === 'Konflikt') {
                        document.dispatchEvent(new CustomEvent('kronos:conflict_created'));
                    }
                    if (kronosCalendar) kronosCalendar.refetchEvents();
                    modal.remove();
                } else {
                    const errText = await response.text();
                    console.error('Fehler beim Speichern:', errText);
                    saveBtn.disabled = false;
                    saveBtn.textContent = 'Speichern';
                    showError('Fehler beim Speichern. Bitte erneut versuchen.');
                }
            } catch (err) {
                console.error('API-Fehler:', err);
                saveBtn.disabled = false;
                saveBtn.textContent = 'Speichern';
                showError('Verbindungsfehler. Bitte Seite neu laden.');
            }
        });
    }
}

export { DiakronosEditModal };
