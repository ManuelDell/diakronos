// modal/modal_conflict.js – Zeitüberschneidungs-Warnung

/**
 * Zeigt einen Konflikt-Dialog wenn eine Ressource bereits belegt ist.
 *
 * @param {Object} conflictingEvent  – { id, title, start, end }
 * @returns {Promise<'ignore'|'conflict'|null>}
 *   'ignore'   → Termin speichern, ignore_conflict = true
 *   'conflict' → Termin speichern, status = 'Konflikt'
 *   null       → Abbrechen
 */
export function showConflictModal(conflictingEvent) {
    return new Promise(resolve => {

        const fmt = (iso) => {
            try {
                return new Date(iso.replace(' ', 'T')).toLocaleString('de-DE', {
                    weekday: 'short', day: 'numeric', month: 'short',
                    hour: '2-digit', minute: '2-digit'
                });
            } catch { return iso; }
        };

        const modal = document.createElement('div');
        modal.className = 'diakronos-modal diakronos-conflict-modal';
        modal.innerHTML = `
            <div class="diakronos-modal-dialog modal-dialog-centered">
                <div class="diakronos-modal-content">
                    <div class="conflict-modal-header">
                        <span class="conflict-icon">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M12 9v4"/><path d="M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214a1.914 1.914 0 0 0 1.636 -2.87l-8.106 -13.536a1.914 1.914 0 0 0 -3.274 0z"/><path d="M12 16h.01"/>
                            </svg>
                        </span>
                        <h5>Zeitüberschneidung</h5>
                        <button class="diakronos-close-btn conflict-close-btn">&times;</button>
                    </div>
                    <div class="conflict-modal-body">
                        <p class="conflict-message">
                            Die gewählte Ressource ist bereits belegt:
                        </p>
                        <div class="conflict-event-card">
                            <strong>${conflictingEvent.title || 'Unbekannter Termin'}</strong>
                            <span class="conflict-event-time">
                                ${fmt(conflictingEvent.start)} – ${fmt(conflictingEvent.end)}
                            </span>
                        </div>
                        <p class="conflict-question">Wie soll fortgefahren werden?</p>
                    </div>
                    <div class="conflict-modal-footer">
                        <button class="btn btn-secondary conflict-btn-abort" title="Zurück zum Formular">
                            Abbrechen
                        </button>
                        <button class="btn btn-warning conflict-btn-ignore" title="Trotzdem speichern, Ressource bleibt besetzt">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M3 7a2 2 0 0 1 2 -2h14a2 2 0 0 1 2 2v10a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-10z"/>
                                <path d="M3 11h18"/>
                            </svg>
                            Trotzdem speichern
                        </button>
                        <button class="btn btn-danger conflict-btn-conflict" title="Als Konfliktermin eintragen">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M12 9v4"/><path d="M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214a1.914 1.914 0 0 0 1.636 -2.87l-8.106 -13.536a1.914 1.914 0 0 0 -3.274 0z"/><path d="M12 16h.01"/>
                            </svg>
                            Als Konflikt markieren
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        requestAnimationFrame(() => modal.classList.add('show'));

        const close = (result) => {
            modal.classList.remove('show');
            modal.addEventListener('transitionend', () => modal.remove(), { once: true });
            resolve(result);
        };

        modal.querySelector('.conflict-close-btn').onclick  = () => close(null);
        modal.querySelector('.conflict-btn-abort').onclick  = () => close(null);
        modal.querySelector('.conflict-btn-ignore').onclick   = () => close('ignore');
        modal.querySelector('.conflict-btn-conflict').onclick = () => close('conflict');
        modal.addEventListener('click', e => { if (e.target === modal) close(null); });
    });
}
