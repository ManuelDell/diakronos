// kronos.bundle.js – Einstiegspunkt (esbuild/Frappe)
// Alle Logik liegt in builder/, modal/ und backend/

import { header_build_elements } from './builder/header_build_elements.js';
import { sidebar_build_elements } from './builder/sidebar_build_elements.js';
import { kronos_calendar_init }   from './builder/calendar_build_init.js';

document.addEventListener('DOMContentLoaded', () => {
    window._kronosUserRoles = JSON.parse(
        document.body.dataset.userRoles || '[]'
    );

    try {
        header_build_elements();
        sidebar_build_elements();
        kronos_calendar_init();
    } catch (err) {
        console.error('Initialisierungsfehler:', err);
    }
});
