// diakronos/diakronos/page/kronos_calendar_page/kronos_calendar_page.js
// awesome_bar_custom_build_apply: Baue Awesome-Bar um (links Icon + Buttons + Monat/Jahr, rechts Lupe + Drag + Double-Button + Apps + Profil unberührt)
frappe.pages['kronos-calendar-page'].on_page_load = function(wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Kronos Kalender',
        single_column: true
    });

    // container_insert_apply: Füge Kalender ein (Full-Screen unter Awesome-Bar)
    $(wrapper).find('.layout-main-section').html(`
        <div class="kronos-container" style="height: calc(100vh - 72px); padding: 0;">
            <div id="calendar" style="height: 100%;"></div>
        </div>
    `);

    frappe.require([
        '/assets/diakronos/js/fullcalendar_bundle_include/fullcalendar.global.min.js',
        '/assets/diakronos/js/kronos_calendar.js'
    ], function() {
        console.log('✅ fullcalendar_bundle_load und kronos_calendar_load abgeschlossen');

        if (typeof window.KronosCalendar !== 'undefined') {
            window.kronosCalendar = new window.KronosCalendar();
            window.kronosCalendar.kronos_calendar_init();

            // awesome_bar_custom_build_apply: Umbaue Awesome-Bar (links Icon + Buttons + Monat/Jahr, rechts Lupe + Drag + Double-Button + Apps, Profil unberührt)
            window.setTimeout(() => {
                const navbar = document.querySelector('.navbar');
                if (navbar) {
                    // links: System-Icon + Heute + < + > + Monat + Jahr (dynamisch)
                    const currentDate = window.kronosCalendar.calendar.getDate();
                    const month = currentDate.toLocaleString('de', { month: 'long' });
                    const year = currentDate.getFullYear();
                    const leftSection = `
                        <span class="system-icon" style="margin-left: 10px;">
                            <img src="/assets/diakronos/images/diakronos-logo.svg" alt="System-Icon" style="height: 30px;">
                        </span>
                        <button class="btn btn-sm kronos-today" title="Heute">Heute</button>
                        <button class="btn btn-sm kronos-prev" title="Vorheriger"><</button>
                        <button class="btn btn-sm kronos-next" title="Nächster">></button>
                        <span class="current-month">${month}</span>
                        <span class="current-year">${year}</span>
                    `;

                    // rechts: Lupe (korrekte Search), Double-Button (Monat/Woche), Drag-Button (Profil bleibt unberührt)
                    const rightSection = `
                        <button class="btn-reset nav-link search-lupe" title="Suchen" onclick="frappe.searchdialog.search.init_search('', 'global_search')">
                            <svg class="icon icon-sm"><use href="#icon-search"></use></svg>
                        </button>
                        <div class="double-button">
                            <button class="btn-reset left-part" title="Monatsansicht">
                                <img src="/assets/diakronos/images/kalender-icon.png" alt="Monatsansicht" style="height: 24px; width: auto;">
                            </button>
                            <button class="btn-reset right-part" title="Wochenansicht">
                                <img src="/assets/diakronos/images/calendar-week-icon.svg" alt="Wochenansicht" style="height: 24px; width: auto;">
                            </button>
                        </div>
                        <button class="btn-reset nav-link drag-button" title="Drag">
                            <svg class="icon icon-sm"><use href="#icon-drag"></use></svg>
                        </button>
                    `;

                    // awesome_bar_custom_build_apply: Überschreibe Awesome-Bar-Inhalt (links/rechts, Profil unberührt)
                    navbar.innerHTML = `
                        <div class="container">
                            <div class="left-section" style="display: flex; align-items: center; gap: 6px;">${leftSection}</div>
                            <div class="right-section" style="display: flex; align-items: center; gap: 10px; margin-left: auto;">${rightSection}</div>
                        </div>
                    `;
                    console.log('✅ awesome_bar_custom_build_success');
                } else {
                    console.error('❌ navbar_not_found');
                }

                // buttons_handle_events_apply: Verbinde Handler (mit Check für Null-Error)
                const prevBtn = document.querySelector('.kronos-prev');
                if (prevBtn) prevBtn.addEventListener('click', () => window.kronosCalendar.calendar.prev());

                const nextBtn = document.querySelector('.kronos-next');
                if (nextBtn) nextBtn.addEventListener('click', () => window.kronosCalendar.calendar.next());

                const todayBtn = document.querySelector('.kronos-today');
                if (todayBtn) todayBtn.addEventListener('click', () => window.kronosCalendar.calendar.today());

                document.querySelectorAll('.kronos-view').forEach(btn => btn.addEventListener('click', function() {
                    const view = this.dataset.view;
                    window.kronosCalendar.calendar.changeView(view);
                    document.querySelectorAll('.kronos-view').forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                }));

                // kombi_button_function_apply: Kombi-Button-Funktion (Clone-adapted toggle mit conditional active)
                const doubleBtn = document.querySelector('.double-button');
                if (doubleBtn) {
                    const leftPart = doubleBtn.querySelector('.left-part');
                    const rightPart = doubleBtn.querySelector('.right-part');

                    // Initial: Links (Monatsansicht) active wie in Clone default
                    leftPart.classList.add('active');
                    rightPart.classList.remove('active');
                    window.kronosCalendar.calendar.changeView('dayGridMonth');

                    // Listener für left (Clone-like onClick conditional)
                    leftPart.addEventListener('click', () => {
                        leftPart.classList.add('active');
                        rightPart.classList.remove('active');
                        window.kronosCalendar.calendar.changeView('dayGridMonth');
                    });

                    // Listener für right (Clone-like onClick conditional)
                    rightPart.addEventListener('click', () => {
                        rightPart.classList.add('active');
                        leftPart.classList.remove('active');
                        window.kronosCalendar.calendar.changeView('timeGridWeek');
                    });
                }

                // drag_button_function_apply: Drag-Button-Funktion (passe an)
                const dragBtn = document.querySelector('.drag-button');
                if (dragBtn) dragBtn.addEventListener('click', () => console.log('Drag-Button clicked – add function'));
            }, 500); /* Timing für DOM-Load */
        } else {
            console.error('❌ kronos_calendar_class_not_available');
        }

        if (window.KronosModal) {
            window.KronosModal.init();
        }
    });
};