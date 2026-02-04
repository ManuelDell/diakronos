// sidebar_build_elements.js – Sidebar-Struktur

window.sidebar_build_elements = function(mainContentEl) {
    const sidebar = document.createElement('aside');
    sidebar.className = 'kronos-sidebar';
    sidebar.setAttribute('aria-label', 'Calendar Navigation');
    sidebar.innerHTML = `
        <div class="sidebar-section">
            <div id="mini-kalender"></div>
        </div>
        <div class="sidebar-section">
            <h3 class="sidebar-title">Meine Kalender</h3>
            <div id="calendar-list"></div>
            <button class="add-calendar-btn">+ Kalender hinzufügen</button>
        </div>
        <div class="sidebar-section">
            <button class="sidebar-settings-btn">Einstellungen</button>
        </div>
    `;
    mainContentEl.appendChild(sidebar);
    console.log('✅ Sidebar hinzugefügt');
};