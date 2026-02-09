// calendar_build_init.js – Calendar-Element + Init
// Alternative / Ergänzung – immer Deutsch erzwingen, wenn nicht anders definiert
if (window.moment) {
    moment.locale('de');
//    console.log('Moment-Locale auf Deutsch fixiert');
}

window.calendar_build_init = async function(mainContentEl) {
    // ── Header zuerst bauen ─────────────────────────────────────────────────
    const appContainer = document.querySelector('.kronos-app-container');
    if (appContainer && typeof window.header_build_elements === 'function') {
        window.header_build_elements(appContainer);
    } else {
        console.error('Konnte header_build_elements nicht aufrufen');
    }
    if (typeof window.sidebar_build_elements === 'function') {
        console.log('Sidebar-Bau vor Kalender-Init');
        await window.sidebar_build_elements(mainContentEl);  // ← await, damit selectedCalendars da ist
    }
    const calendarEl = document.createElement('div');
    calendarEl.id = 'calendar';
    calendarEl.className = 'kronos-calendar';
    mainContentEl.appendChild(calendarEl);
//    console.log('✅ Kalender-Element hinzugefügt');

    // Warte auf KronosCalendar Klasse
    let retries = 0;
    const maxRetries = 50;
    while (!window.KronosCalendar && retries < maxRetries) {
        await new Promise(resolve => setTimeout(resolve, 100));
        retries++;
    }
    if (!window.KronosCalendar) {
        throw new Error('KronosCalendar konnte nicht geladen werden');
    }
//    console.log('✅ KronosCalendar Klasse verfügbar');

    const kronosCalendar = new window.KronosCalendar();
    kronosCalendar.kronos_calendar_init();
//   console.log('✅ Haupt-Kalender initialisiert');

    const calendarSize = {
        width: document.querySelector('#calendar')?.offsetWidth,
        height: document.querySelector('#calendar')?.offsetHeight
    };
//    console.log('✅ Kalender-Größe:', calendarSize);

    // View Switcher Buttons
    const viewBtns = document.querySelectorAll('.view-btn');
    if (viewBtns.length > 0) {
        viewBtns[0].classList.add('active');
        viewBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                viewBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                if (window.kronosCalendar && window.kronosCalendar.calendar) {
                    window.kronosCalendar.changeView(btn.dataset.view);
//                    console.log('👁️ View geändert zu:', btn.dataset.view);
                }
            });
        });
//        console.log('✅ View-Switcher-Buttons verknüpft');
    }

    // Date Display Update
    if (window.kronosCalendar && window.kronosCalendar.calendar) {
        const dateDisplay = document.getElementById('current-date-display');
        const updateDate = () => {
            const view = window.kronosCalendar.calendar.view;
            if (dateDisplay && view) {
                dateDisplay.textContent = view.title;
            }
        };
        window.kronosCalendar.calendar.on('datesSet', updateDate);
        updateDate();
//        console.log('✅ Datums-Display verknüpft');
    }

    // Create Button
    const createBtn = document.querySelector('.create-btn');
    if (createBtn) {
        createBtn.addEventListener('click', () => {
            if (window.KronosCreateDialog && window.KronosCreateDialog.showCreateDialog) {
                const today = new Date().toISOString().split('T')[0];
                window.KronosCreateDialog.showCreateDialog(today);
                console.log('📝 Create Dialog geöffnet für:', today);
            } else {
                frappe.msgprint({
                    message: 'Dialog wird noch geladen. Bitte versuchen Sie es gleich erneut.',
                    indicator: 'yellow'
                });
            }
        });
//        console.log('✅ Create-Button verknüpft');
    }

    // =====================================
    // Header-Pfeile (< / >) – offizielle FullCalendar-Methoden
    // =====================================
    if (window.kronosCalendar && window.kronosCalendar.calendar) {
        const calendar = window.kronosCalendar.calendar;
        const dateDisplay = document.getElementById('current-date-display');
        const prevBtn = document.querySelector('.prev-month');
        const nextBtn = document.querySelector('.next-month');

        // Datum aktualisieren (offiziell über 'datesSet')
        const updateDateDisplay = () => {
            if (dateDisplay) {
                dateDisplay.textContent = calendar.view.title;
            }
        };

        calendar.on('datesSet', updateDateDisplay);
        updateDateDisplay(); // Sofort initial

        // Pfeil-Buttons – offizielle .prev() / .next()
        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                calendar.prev();
//                console.log('← Vorheriger Monat');
            });
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                calendar.next();
//                console.log('→ Nächster Monat');
            });
        }

//        console.log('✅ Navigation über eigene Buttons aktiviert (.prev() / .next())');
//    } else {
//        console.warn('KronosCalendar nicht verfügbar – Navigation wartet');
    }

//   frappe.msgprint({
//        message: '✅ Kronos Kalender erfolgreich geladen!',
//        indicator: 'green'
//    });
//    console.log('🎉 KRONOS KALENDER VOLLSTÄNDIG INITIALISIERT');
};