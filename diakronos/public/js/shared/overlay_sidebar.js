/**
 * shared/overlay_sidebar.js – Standard-Overlay-Sidebar für alle Diakronos-Module
 *
 * Die Sidebar legt sich von links über den Inhalt (position:fixed).
 * Sie verdrängt den Hauptinhalt NICHT – unabhängig von Desktop/Mobile.
 *
 * Verwendung:
 *   import { initOverlaySidebar } from '../shared/overlay_sidebar.js';
 *
 *   const sidebar = initOverlaySidebar({
 *       sidebarEl:      document.querySelector('.psalmos-sidebar'),
 *       backdropEl:     document.querySelector('.psalmos-sidebar-backdrop'),
 *       toggleEvent:    'psalmos:toggleSidebar',  // Custom-Event-Name vom Header
 *   });
 *
 *   // Programmatisch steuern:
 *   sidebar.open();
 *   sidebar.close();
 *   sidebar.toggle();
 */

export function initOverlaySidebar({ sidebarEl, backdropEl, toggleEvent = 'diakronos:toggleSidebar' } = {}) {
    if (!sidebarEl || !backdropEl) {
        console.error('[shared/overlay_sidebar] sidebarEl oder backdropEl fehlt');
        return { open: () => {}, close: () => {}, toggle: () => {} };
    }

    const open = () => {
        sidebarEl.classList.add('active');
        backdropEl.classList.add('active');
    };

    const close = () => {
        sidebarEl.classList.remove('active');
        backdropEl.classList.remove('active');
        document.getElementById('hamburger-3')?.classList.remove('is-active');
    };

    const toggle = () => sidebarEl.classList.contains('active') ? close() : open();

    // Hamburger-Event vom Header
    document.addEventListener(toggleEvent, toggle);

    // Backdrop-Klick schließt Sidebar
    backdropEl.addEventListener('click', close);

    // Escape-Taste schließt Sidebar
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && sidebarEl.classList.contains('active')) close();
    });

    return { open, close, toggle };
}
