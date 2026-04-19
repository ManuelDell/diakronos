// kronos.bundle.js – Einstiegspunkt (esbuild/Frappe)
// Alle Logik liegt in builder/, modal/ und backend/

import { header_build_elements } from './builder/header_build_elements.js';
import { sidebar_build_elements } from './builder/sidebar_build_elements.js';
import { kronos_calendar_init }   from './builder/calendar_build_init.js';
import { initStateFromDOM }       from './shared/state.js';
import { kronosCalendar }         from './builder/kronos_calendar.js';
import { initKronosSearch }       from './search/kronos_search.js';

document.addEventListener('DOMContentLoaded', () => {
    initStateFromDOM();

    try {
        header_build_elements();
        sidebar_build_elements();
        kronos_calendar_init();
        initKronosSearch((event) => {
            kronosCalendar.highlightEvent(event.id, event.start);
        });
    } catch (err) {
        console.error('Initialisierungsfehler:', err);
    }
});

