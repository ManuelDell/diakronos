// modal_series_handler.js – Serien-Dialoge für Drag & Drop und Bearbeiten

import { kronosCalendar } from '../builder/kronos_calendar.js';

const CSRF = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

function showConfirm(message) {
    return new Promise((resolve) => {
        const modal = openModal(`
            <div class="diakronos-modal">
                <div class="diakronos-modal-dialog" style="max-width: 360px;">
                    <div class="diakronos-modal-body" style="padding: var(--gap-xl);">
                        <p style="color: var(--text-primary); margin-bottom: var(--gap-l);">${message}</p>
                    </div>
                    <div class="diakronos-modal-footer">
                        <button class="btn btn-secondary" data-action="no">Abbrechen</button>
                        <button class="btn btn-danger" data-action="yes">Löschen</button>
                    </div>
                </div>
            </div>
        `);
        const done = (r) => { closeModal(modal); resolve(r); };
        modal.querySelector('[data-action="no"]').onclick  = () => done(false);
        modal.querySelector('[data-action="yes"]').onclick = () => done(true);
        modal.onclick = (e) => { if (e.target === modal) done(false); };
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape') done(false); }, { once: true });
    });
}

function openModal(html) {
    document.body.insertAdjacentHTML('beforeend', html);
    const modal = document.body.lastElementChild;
    requestAnimationFrame(() => modal.classList.add('show'));
    return modal;
}

function closeModal(modal) {
    modal.classList.remove('show');
    setTimeout(() => modal.remove(), 300);
}

class DiakronosSeriesHandler {

    /**
     * Drag & Drop Bestätigung für Serientermine.
     * Gibt ein Promise zurück: { confirmed: true, rememberSession: bool } oder null (Abbruch).
     */
    static showDragConfirmation(event) {
        return new Promise((resolve) => {
            const color = event.extendedProps?.element_color || 'var(--primary)';
            const name  = event.title || 'Serientermin';

            const modal = openModal(`
                <div class="diakronos-modal">
                    <div class="diakronos-modal-dialog" style="max-width: 380px;">
                        <div class="diakronos-color-bar" style="background: ${color};"></div>
                        <div class="diakronos-modal-header">
                            <h5 class="modal-title">Serientermin</h5>
                            <button class="diakronos-close-btn" data-action="close">&times;</button>
                        </div>
                        <div class="diakronos-modal-body drag-confirm-body">
                            <p class="series-event-name">${name}</p>
                            <p class="series-confirm-text">
                                Diesen Termin aus der Serie lösen und verschieben?
                            </p>
                            <label class="checkbox-label">
                                <input type="checkbox" id="session-remember">
                                Diese Sitzung nicht mehr fragen
                            </label>
                        </div>
                        <div class="diakronos-modal-footer">
                            <button class="btn btn-secondary" data-action="cancel">Abbrechen</button>
                            <button class="btn btn-primary" data-action="confirm">Ja, Sicher</button>
                        </div>
                    </div>
                </div>
            `);

            const done = (result) => { closeModal(modal); resolve(result); };

            modal.querySelector('[data-action="close"]').onclick  = () => done(null);
            modal.querySelector('[data-action="cancel"]').onclick = () => done(null);
            modal.querySelector('[data-action="confirm"]').onclick = () => done({
                confirmed: true,
                rememberSession: modal.querySelector('#session-remember').checked
            });
            modal.onclick = (e) => { if (e.target === modal) done(null); };
            document.addEventListener('keydown', (e) => { if (e.key === 'Escape') done(null); }, { once: true });
        });
    }

    /**
     * Optionen-Dialog beim Anklicken eines Serientermins im Bearbeitungsmodus.
     * Gibt ein Promise zurück: 'edit' | 'cancelled'
     */
    static showEditOptions(element) {
        return new Promise((resolve) => {
            const color = element.element_color || 'var(--primary)';
            const name  = element.element_name || 'Serientermin';

            const modal = openModal(`
                <div class="diakronos-modal">
                    <div class="diakronos-modal-dialog" style="max-width: 400px;">
                        <div class="diakronos-color-bar" style="background: ${color};"></div>
                        <div class="diakronos-modal-header">
                            <h5 class="modal-title">Serientermin</h5>
                            <button class="diakronos-close-btn" data-action="close">&times;</button>
                        </div>
                        <div class="diakronos-modal-body">
                            <p class="series-event-name">${name}</p>
                            <p class="series-prompt">Was möchten Sie tun?</p>
                            <div class="series-option-btns">
                                <button class="btn btn-primary" data-action="edit">
                                    Bearbeiten als Einzeltermin
                                </button>
                                <button class="btn btn-danger" data-action="delete-future">
                                    Alle nachfolgenden Termine löschen
                                </button>
                                <button class="btn btn-danger" data-action="delete-all">
                                    Gesamte Serie löschen
                                </button>
                            </div>
                        </div>
                        <div class="diakronos-modal-footer">
                            <button class="btn btn-secondary" data-action="cancel">Abbrechen</button>
                        </div>
                    </div>
                </div>
            `);

            const done = (action) => { closeModal(modal); resolve(action); };

            modal.querySelector('[data-action="close"]').onclick  = () => done('cancelled');
            modal.querySelector('[data-action="cancel"]').onclick = () => done('cancelled');
            modal.onclick = (e) => { if (e.target === modal) done('cancelled'); };
            document.addEventListener('keydown', (e) => { if (e.key === 'Escape') done('cancelled'); }, { once: true });

            // Bearbeiten als Einzeltermin → gibt Kontrolle an kronos_calendar.js zurück
            modal.querySelector('[data-action="edit"]').onclick = () => done('edit');

            // Alle nachfolgenden Termine löschen
            modal.querySelector('[data-action="delete-future"]').onclick = async () => {
                const confirmed = await showConfirm(`Alle Termine dieser Serie ab <strong>${name}</strong> löschen?`);
                if (!confirmed) return;
                try {
                    await fetch('/api/method/diakronos.kronos.api.series_update.delete_future_series_events', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-Frappe-CSRF-Token': CSRF() },
                        body: JSON.stringify({ series_id: element.series_id, from_date: element.element_start })
                    });
                    kronosCalendar.refetchEvents();
                    done('cancelled');
                } catch {
                    console.error('Fehler beim Löschen der nachfolgenden Termine.');
                }
            };

            // Gesamte Serie löschen
            modal.querySelector('[data-action="delete-all"]').onclick = async () => {
                const confirmed = await showConfirm(`Gesamte Serie <strong>${name}</strong> unwiderruflich löschen?`);
                if (!confirmed) return;
                try {
                    await fetch('/api/method/diakronos.kronos.api.series_update.delete_series_batch_fast', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-Frappe-CSRF-Token': CSRF() },
                        body: JSON.stringify({ series_id: element.series_id })
                    });
                    kronosCalendar.refetchEvents();
                    done('cancelled');
                } catch {
                    console.error('Fehler beim Löschen der Serie.');
                }
            };
        });
    }
}

export { DiakronosSeriesHandler };
