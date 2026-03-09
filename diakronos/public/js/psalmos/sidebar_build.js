// psalmos/sidebar_build.js – Overlay-Sidebar für die Psalmos-Seite

export function initPsalmosSidebar() {
    const sidebar  = document.querySelector('.psalmos-sidebar');
    const backdrop = document.querySelector('.psalmos-sidebar-backdrop');

    if (!sidebar || !backdrop) {
        console.error('❌ psalmos-sidebar oder psalmos-sidebar-backdrop nicht gefunden');
        return;
    }

    const open = () => {
        sidebar.classList.add('active');
        backdrop.classList.add('active');
    };

    const close = () => {
        sidebar.classList.remove('active');
        backdrop.classList.remove('active');
        // Hamburger-Animation zurücksetzen
        document.getElementById('hamburger-3')?.classList.remove('is-active');
    };

    const toggle = () => sidebar.classList.contains('active') ? close() : open();

    // Hamburger-Event (von header_build.js gefeuert)
    document.addEventListener('psalmos:toggleSidebar', toggle);

    // Backdrop-Klick schließt Sidebar
    backdrop.addEventListener('click', close);

    // Escape-Taste schließt Sidebar
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && sidebar.classList.contains('active')) {
            close();
        }
    });
}
