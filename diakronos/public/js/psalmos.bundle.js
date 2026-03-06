// psalmos.bundle.js – Einstiegspunkt für die Psalmos SPA
// Nutzt die shared Module für Header und Sidebar.

import { buildStandardHeader } from './shared/header.js';
import { initOverlaySidebar }  from './shared/overlay_sidebar.js';

document.addEventListener('DOMContentLoaded', () => {

    // ── Header ────────────────────────────────────────────────────────────────
    buildStandardHeader({
        headerEl:       document.querySelector('.psalmos-header'),
        title:          'Psalmos',
        logoSvg:        '<path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z"/>',
        hamburgerEvent: 'psalmos:toggleSidebar',
        startseiteHref: '/diakronos',
    });

    // ── Overlay-Sidebar ───────────────────────────────────────────────────────
    initOverlaySidebar({
        sidebarEl:   document.querySelector('.psalmos-sidebar'),
        backdropEl:  document.querySelector('.psalmos-sidebar-backdrop'),
        toggleEvent: 'psalmos:toggleSidebar',
    });

});
