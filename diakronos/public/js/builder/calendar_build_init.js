// builder/calendar_build_init.js – Initialisierungs-Orchestrator

import { kronosCalendar } from './kronos_calendar.js';
import { DiakronosCreateModal } from '../modal/modal_create.js';
import { PendingManager } from '../backend/pending_manager.js';
import { getViewMode } from '../backend/data.js';

export function kronos_calendar_init() {
    // Kalender-Container sicherstellen
    let calendarEl = document.querySelector('#calendar');
    if (!calendarEl) {
        calendarEl = document.createElement('div');
        calendarEl.id = 'calendar';
        calendarEl.className = 'kronos-calendar';
        const mainContent = document.querySelector('.kronos-main-content') || document.body;
        mainContent.appendChild(calendarEl);
    }

    // Singleton-Instanz initialisieren
    kronosCalendar.kronos_calendar_init();

    // FAB-Button (+) → öffnet Create-Modal
    const fab = document.querySelector('.kronos-fab');
    if (fab) {
        fab.addEventListener('click', () => DiakronosCreateModal.show({}));
    }

    // ── Floating Pending-Save-Button ─────────────────────────────────────────
    const mainContent = document.querySelector('.kronos-main-content') || document.body;

    const pendingBtn = document.createElement('a');
    pendingBtn.className = 'kronos-pending-btn';
    pendingBtn.href = '/kronos/moderation';
    pendingBtn.setAttribute('aria-label', 'Zur Terminmoderation');
    pendingBtn.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h6v6h-6z"/><path d="M14 4h6v6h-6z"/><path d="M4 14h6v6h-6z"/><path d="M17 17m-3 0a3 3 0 1 0 6 0a3 3 0 1 0 -6 0"/></svg>
        <span class="pending-btn-text">Moderation</span>
        <span class="pending-btn-badge" id="pending-badge">0</span>
    `;
    pendingBtn.hidden = true;
    document.body.appendChild(pendingBtn);  // an body: kein overflow:hidden-Clipping

    function _syncPendingBtn() {
        const isEditMode = !getViewMode();
        pendingBtn.hidden = !isEditMode;
        const count = PendingManager.count();
        const badge = document.getElementById('pending-badge');
        if (badge) badge.textContent = count;
    }

    document.addEventListener('pending:changed', _syncPendingBtn);
    // Auch bei Modus-Wechsel (View ↔ Edit) aktualisieren
    document.addEventListener('toggleChange', _syncPendingBtn);

    // beforeunload: Warnung wenn noch ausstehende Termine vorhanden
    window.addEventListener('beforeunload', (e) => {
        if (PendingManager.count() > 0) {
            e.preventDefault();
            e.returnValue = '';
        }
    });
}
