window.sidebar_build_elements = async function(mainContentEl) {
    // Sidebar und calendar-list finden (bereits in HTML vorhanden)
    const sidebar = document.querySelector('.kronos-sidebar');
    if (!sidebar) {
        console.error('❌ .kronos-sidebar nicht gefunden – Sidebar-Bau abgebrochen');
        return;
    }

    console.log('✅ Sidebar gefunden – starte Befüllung');

    // 1. Mini-Kalender starten (Container ist bereits in HTML)
    const miniContainer = sidebar.querySelector('#mini-kalender');
    if (miniContainer && window.KronosMiniCalendar) {
        // Sicherstellen, dass er nur einmal initialisiert wird
        if (!miniContainer.dataset.initialized) {
            new window.KronosMiniCalendar('#mini-kalender');
            miniContainer.dataset.initialized = 'true';
            console.log('✅ Mini-Kalender in bestehendem Container gestartet');
        }
    } else {
        console.warn('⚠️ Mini-Kalender konnte nicht gestartet werden', {
            container: !!miniContainer,
            klasse: !!window.KronosMiniCalendar
        });
    }

    // 2. Kalenderliste finden und per API befüllen
    const calendarList = sidebar.querySelector('#calendar-list');
    if (!calendarList) {
        console.error('❌ #calendar-list nicht gefunden');
        return;
    }

    // Bestehenden Inhalt leeren + Lade-Hinweis
    calendarList.innerHTML = '<p class="text-muted p-3">Kalender werden geladen...</p>';

    // API-Aufruf für Kalenderdaten
    async function loadCalendars() {
        try {
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
            const response = await fetch('/api/method/diakronos.kronos.api.permissions.get_accessible_calendars', {
                method: 'GET',
                credentials: 'include',
                headers: {
                    'Accept': 'application/json',
                    'X-Frappe-CSRF-Token': csrfToken
                }
            });

            if (!response.ok) {
                throw new Error(`API Fehler: ${response.status} - ${response.statusText}`);
            }

            const result = await response.json();
            const calendars = result.message || [];
            console.log('✅ Kalender via API geladen:', calendars.length);
            console.log('Empfangene Kalender (raw):', calendars);
            console.log('Anzahl Kalender:', calendars.length);
            if (calendars.length > 0) {
                console.log('Erster Kalender:', calendars[0]);
            }

            // Lade-Text entfernen
            calendarList.innerHTML = '';

            if (calendars.length === 0) {
                calendarList.innerHTML = '<p class="text-muted p-3">Keine Kalender freigegeben</p>';
                return;
            }

            // Aufteilung in schreibbar / nur lesbar
            const writable = calendars.filter(cal => cal.write === true);
            const readableOnly = calendars.filter(cal => cal.write !== true);

            // Aus localStorage laden oder alle selektieren (Standard: alle aktiviert)
            let selected = JSON.parse(localStorage.getItem('selected_calendars')) || calendars.map(cal => cal.name);
            window.selectedCalendars = selected;

            // Hilfsfunktion zum Erstellen eines Kalender-Eintrags
            function createCalendarItem(cal, isChecked) {
                const item = document.createElement('div');
                item.className = 'calendar-item';
                item.setAttribute('data-color', cal.color || 'var(--primary)');

                // Erst innerHTML setzen (damit das input-Element existiert)
                item.innerHTML = `
                    <input type="checkbox" id="cal-${cal.name}" ${isChecked ? 'checked' : ''}>
                    <label for="cal-${cal.name}">${cal.title || cal.name}</label>
                    ${cal.write ? '<span class="pencil-icon" title="Schreibrecht">✎</span>' : ''}
                `;

                // Jetzt checkbox holen – existiert jetzt!
                const checkbox = item.querySelector('input');

                // CSS-Variable + direkte Styles setzen
                item.style.setProperty('--calendar-color', cal.color || 'var(--primary)');
                checkbox.style.borderColor = cal.color || 'var(--primary)';

                // Change-Event
                checkbox.addEventListener('change', () => {
                    if (checkbox.checked) {
                        if (!window.selectedCalendars.includes(cal.name)) {
                            window.selectedCalendars.push(cal.name);
                        }
                    } else {
                        window.selectedCalendars = window.selectedCalendars.filter(n => n !== cal.name);
                    }

                    localStorage.setItem('selected_calendars', JSON.stringify(window.selectedCalendars));

                    if (window.kronosCalendar) {
                        window.kronosCalendar.refetchEvents();
                    }
                });

                return item;
            }

            // Schreibzugriff-Gruppe
            if (writable.length > 0) {
                const writeGroup = document.createElement('div');
                writeGroup.className = 'calendar-group writable';
                writeGroup.innerHTML = '<h4 class="group-title">Schreibzugriff</h4>';

                writable.forEach(cal => {
                    writeGroup.appendChild(createCalendarItem(cal, selected.includes(cal.name)));
                });

                console.log('Schreibgruppe gebaut – Kinder:', writeGroup.children.length);
                calendarList.appendChild(writeGroup);
            }

            // Nur-Lesen-Gruppe
            if (readableOnly.length > 0) {
                const readGroup = document.createElement('div');
                readGroup.className = 'calendar-group readable';
                readGroup.innerHTML = '<h4 class="group-title">Nur Lesen</h4>';

                readableOnly.forEach(cal => {
                    readGroup.appendChild(createCalendarItem(cal, selected.includes(cal.name)));
                });

                console.log('Nur-Lesen-Gruppe gebaut – Kinder:', readGroup.children.length);
                calendarList.appendChild(readGroup);
            }

        } catch (err) {
            console.error('❌ Fehler beim Laden der Kalender:', err);
            calendarList.innerHTML = '<p class="text-danger p-3">Fehler beim Laden der Kalender: ' + err.message + '</p>';
        }
    }

    // API-Aufruf starten und warten
    await loadCalendars();

    console.log('Sidebar vollständig gerendert – Kalenderanzahl:', calendarList.children.length);

    // Nach dem Bau: Kalender neu laden (damit Termine mit aktueller Auswahl erscheinen)
    if (window.kronosCalendar) {
        console.log('Initial refetch nach Sidebar-Bau');
        window.kronosCalendar.refetchEvents();
    }
};