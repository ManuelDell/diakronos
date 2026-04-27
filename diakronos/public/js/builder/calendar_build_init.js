// builder/calendar_build_init.js – Initialisierungs-Orchestrator

import { kronosCalendar } from './kronos_calendar.js';
import { DiakronosCreateModal } from '../modal/modal_create.js';
import { PendingManager } from '../backend/pending_manager.js';
import { getViewMode } from '../backend/data.js';
import { ICON_MODERATION_LG } from '../shared/icons.js';

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

    // ── Floating Moderation-Button ────────────────────────────────────────────
    const pendingBtn = document.createElement('a');
    pendingBtn.className = 'kronos-pending-btn';
    pendingBtn.href = '/kronos/moderation';
    pendingBtn.setAttribute('aria-label', 'Zur Terminmoderation');
    pendingBtn.innerHTML = `
        ${ICON_MODERATION_LG}
        <span class="pending-btn-text">Moderation</span>
        <span class="pending-btn-badge" id="pending-badge">0</span>
    `;
    pendingBtn.hidden = true;
    document.body.appendChild(pendingBtn);

    // Zählt offene Termine (Vorschlag + Konflikt) aus der DB
    async function _fetchModerationCount() {
        try {
            const res = await fetch(
                '/api/method/diakronos.kronos.api.kanban_api.get_moderation_count',
                { headers: { 'X-Frappe-CSRF-Token': 'fetch' } }
            );
            if (!res.ok) return 0;
            const data = await res.json();
            return (data.message?.count) ?? 0;
        } catch {
            return 0;
        }
    }

    async function _syncModerationBtn() {
        const isEditMode = !getViewMode();
        if (!isEditMode) {
            pendingBtn.hidden = true;
            return;
        }
        const count = await _fetchModerationCount();
        const badge = document.getElementById('pending-badge');
        if (badge) badge.textContent = count;
        pendingBtn.hidden = count === 0;
    }

    // Bei Modus-Wechsel (View ↔ Edit) aktualisieren
    document.addEventListener('toggleChange', _syncModerationBtn);
    // Initial laden
    _syncModerationBtn();

    // beforeunload: Warnung wenn noch Session-Vorschläge vorhanden
    window.addEventListener('beforeunload', (e) => {
        if (PendingManager.count() > 0) {
            e.preventDefault();
            e.returnValue = '';
        }
    });
}
