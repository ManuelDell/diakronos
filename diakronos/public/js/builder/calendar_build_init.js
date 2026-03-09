// builder/calendar_build_init.js – Initialisierungs-Orchestrator

import { kronosCalendar } from './kronos_calendar.js';
import { DiakronosCreateModal } from '../modal/modal_create.js';

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

    // Singleton-Instanz initialisieren (kein new KronosCalendar() hier!)
    kronosCalendar.kronos_calendar_init();

    // FAB-Button (+) verdrahten → öffnet Create-Modal unabhängig vom View-Modus
    const fab = document.querySelector('.kronos-fab');
    if (fab) {
        fab.addEventListener('click', () => DiakronosCreateModal.show({}));
    }

    console.log('🎉 KRONOS KALENDER VOLLSTÄNDIG INITIALISIERT');
}
