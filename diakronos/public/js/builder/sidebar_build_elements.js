// sidebar_build_elements.js – Sidebar-Struktur (subject_verb_object)

window.sidebar_build_elements = function(mainContentEl) {
    // Sidebar-Element erstellen
    const sidebar = document.createElement('aside');
    sidebar.className = 'kronos-sidebar';
    sidebar.setAttribute('aria-label', 'Kalender-Navigation');

    // Inneres HTML – alle Sections
    sidebar.innerHTML = `
        <div class="sidebar-section">
            <!-- Mini-Kalender – fester Container mit Höhe -->
            <div id="mini-kalender" style="height: 250px; min-height: 200px;"></div>
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

    // Sidebar in den Haupt-Content einfügen
    mainContentEl.appendChild(sidebar);
    console.log('✅ Sidebar hinzugefügt');


    // Mini-Kalender laden 
    const miniScript = document.createElement('script');
    miniScript.src = '/assets/diakronos/js/kronos_mini_calendar.js';
    miniScript.onload = () => {
        console.log('✅ Mini-Kalender-Script geladen');
        if (window.KronosMiniCalendar) {
            new window.KronosMiniCalendar('#mini-kalender');
            console.log('✅ Mini-Kalender in Sidebar gestartet');
        }
    };
    miniScript.onerror = () => console.error('❌ Mini-Kalender-Script Fehler');
    document.head.appendChild(miniScript);
    window.miniCalendar = new KronosMiniCalendar('#mini-kalender');

    // Calendar List aus Frappe
    const calendarList = document.getElementById('calendar-list');
    if (calendarList) {
        frappe.call({
            method: 'diakronos.kronos.api.calendar_get.get_accessible_calendars',
            callback: (r) => {
                if (r.message) {
                    calendarList.innerHTML = r.message.map(cal => `
                        <div class="calendar-item">
                            <input type="checkbox" id="cal-${cal.name}" checked data-calendar="${cal.name}">
                            <label for="cal-${cal.name}">${cal.title}</label>
                            <button class="calendar-options-btn" aria-label="More options">⋮</button>
                        </div>
                    `).join('');
                    calendarList.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
                        checkbox.addEventListener('change', () => {
                            if (window.kronosCalendar && window.kronosCalendar.calendar) {
                                window.kronosCalendar.refetchEvents();
                                console.log('🔄 Events neu geladen (Calendar Checkbox)');
                            }
                        });
                    });
                    console.log('✅ Kalender-Liste geladen:', r.message.length, 'Kalender');
                }
            }
        });
    }

    // Sofort den Mini-Kalender initialisieren (nachdem das Element im DOM ist)
    const miniContainer = sidebar.querySelector('#mini-kalender');
    if (miniContainer && window.KronosMiniCalendar) {
        new window.KronosMiniCalendar('#mini-kalender');
        console.log('✅ Mini-Kalender direkt nach Sidebar-Bau initialisiert');
    } else {
        console.warn('⚠️ Mini-Kalender konnte nicht initialisiert werden', {
            container: !!miniContainer,
            klasse: !!window.KronosMiniCalendar
        });
    }
};