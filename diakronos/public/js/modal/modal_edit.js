// modal_edit.js – Termin bearbeiten

import { kronosCalendar } from '../builder/kronos_calendar.js';

class DiakronosEditModal {
    static async show(element) {
        if (!element?.name) {
            console.warn('⚠️ Kein valides Element übergeben');
            return;
        }

        // 1. Daten laden BEVOR das HTML gebaut wird
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

        // 2. HTML mit vorhandenen Daten bauen
        const modalHTML = `
        <div class="diakronos-modal fade show" tabindex="-1" role="dialog">
            <div class="diakronos-modal-dialog modal-dialog-centered modal-lg">
                <div class="diakronos-modal-content">
                    <div class="diakronos-color-bar" style="background-color: ${element.element_color || 'var(--primary)'};"></div>

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
                                <input type="text" id="element_name" value="${element.element_name || ''}" required>
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

                            <div class="description-group">
                                <label>Beschreibung</label>
                                <textarea id="description" rows="5">${element.description || ''}</textarea>
                            </div>
                        </div>

                        <!-- Tab 2: Weitere Details -->
                        <div id="tab-details" class="tab-content">
                            <div class="form-group">
                                <label>Kalender</label>
                                <select id="element_calendar">
                                    <option value="">— Bitte wählen —</option>
                                    ${writableCalendars.map(cal => `
                                        <option value="${cal.name}" ${cal.name === element.element_calendar ? 'selected' : ''}>
                                            ${cal.calendar_name || cal.name}
                                        </option>
                                    `).join('')}
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Kategorie</label>
                                <select id="element_category">
                                    <option value="">—</option>
                                    ${categories.map(cat => `
                                        <option value="${cat.name}" ${cat.name === element.element_category ? 'selected' : ''}>
                                            ${cat.event_category_name || cat.name}
                                        </option>
                                    `).join('')}
                                </select>
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

        // 3. HTML einfügen
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        const modal = document.querySelector('.diakronos-modal:last-child');

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
                dateFormat:      'Y-m-dTH:i',
                altInput:        true,
                altFormat:       'j. F Y, H:i',
                minuteIncrement: 5,
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

        // Tab-Switching
        modal.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                modal.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                modal.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');
                modal.querySelector(`#tab-${btn.dataset.tab}`).classList.add('active');
            });
        });

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
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
            try {
                const response = await fetch('/api/method/diakronos.kronos.api.event_crud.delete_event', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'X-Frappe-CSRF-Token': csrfToken
                    },
                    body: JSON.stringify({ name: element.name })
                });
                if (response.ok) {
                    if (kronosCalendar) kronosCalendar.refetchEvents();
                    modal.remove();
                } else {
                    confirmFooter.style.display = 'none';
                    mainFooter.style.display    = 'flex';
                    const errEl = modal.querySelector('#modal-error');
                    errEl.textContent = 'Löschen fehlgeschlagen. Bitte erneut versuchen.';
                    errEl.classList.add('visible');
                }
            } catch (err) {
                console.error('API-Fehler:', err);
            }
        });

        // Speichern
        modal.querySelector('#save-btn').addEventListener('click', async () => {
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
            const payload = {
                name:             element.name,
                element_name:     modal.querySelector('#element_name').value,
                element_start:    modal.querySelector('#element_start').value,
                element_end:      modal.querySelector('#element_end').value,
                all_day:          modal.querySelector('#all_day').checked,
                description:      modal.querySelector('#description').value,
                element_category: modal.querySelector('#element_category').value,
                element_calendar: modal.querySelector('#element_calendar').value,
                status:           element.status || 'Festgelegt',
                series_id:        element.series_id || ''
            };

            try {
                const response = await fetch('/api/method/diakronos.kronos.api.event_crud.save_event', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'X-Frappe-CSRF-Token': csrfToken
                    },
                    body: JSON.stringify(payload)
                });

                const errEl = modal.querySelector('#modal-error');
                if (response.ok) {
                    if (kronosCalendar) kronosCalendar.refetchEvents();
                    modal.remove();
                } else {
                    const errText = await response.text();
                    console.error('Fehler beim Speichern:', errText);
                    errEl.textContent = 'Fehler beim Speichern. Bitte erneut versuchen.';
                    errEl.classList.add('visible');
                }
            } catch (err) {
                console.error('API-Fehler:', err);
                const errEl = modal.querySelector('#modal-error');
                errEl.textContent = 'Verbindungsfehler. Bitte Seite neu laden.';
                errEl.classList.add('visible');
            }
        });
    }
}

export { DiakronosEditModal };
