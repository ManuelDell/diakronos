// public/js/builder/header_build_elements.js

window.header_build_elements = function() {
//    console.log('header_build_elements → Starte Header-Bau');

    const header = document.querySelector('.kronos-header');
    if (!header) {
        console.error('❌ Kein <header class="kronos-header"> in der Seite gefunden');
        return;
    }

    // Alten Inhalt löschen
    header.innerHTML = '';

    // ── Header Left: Logo + Hamburger ───────────────────────────────────────
    const headerLeft = document.createElement('div');
    headerLeft.className = 'header-left';

    const hamburger = document.createElement('div');
    hamburger.className = 'hamburger';
    hamburger.id = 'hamburger-3';
    hamburger.setAttribute('aria-label', 'Seitenleiste ein-/ausblenden');
    hamburger.innerHTML = '<span class="line"></span><span class="line"></span><span class="line"></span>';
    headerLeft.appendChild(hamburger);

    const logo = document.createElement('img');
    logo.src = '/assets/diakronos/images/diakronos-logo.svg';
    logo.alt = 'Diakronos Logo';
    logo.id = 'logopicture'
    logo.style.height = 'var(--button-height)';
    headerLeft.appendChild(logo);

// 3. Kalender-Text (direkt daneben)
    const calendarName = document.createElement('span');
    calendarName.id = 'calendar-name';
    calendarName.className = 'calendar-name-in-header';  // neue Klasse nur für Styling
    calendarName.textContent = 'Kalender';
    headerLeft.appendChild(calendarName);

// ── Heute-Button ─────────────────────────────────────────────────────────────
const todaybutton = document.createElement('button');
todaybutton.className = 'todaybutton';
todaybutton.id = 'today-btn';
todaybutton.textContent = 'Heute';
todaybutton.setAttribute('aria-label', 'Zum heutigen Tag springen');

// Klick-Handler – leise & robust
todaybutton.addEventListener('click', () => {
    // 1. Haupt-FullCalendar auf heute setzen
    window.kronosCalendar?.calendar?.today();

    // 2. Mini-Kalender synchronisieren (wenn Instanz verfügbar)
    if (window.kronosMiniCalendar) {
        window.kronosMiniCalendar.m = moment();
        window.kronosMiniCalendar.render();
    }
    // Kein else – wir wollen keine Warnungen im Produktivbetrieb
});

headerLeft.appendChild(todaybutton);

    headerLeft.appendChild(todaybutton);

    header.appendChild(headerLeft);

    // ── Header Center: Prev – Datum – Next ───────────────────────────────────
    const headerCenter = document.createElement('div');
    headerCenter.className = 'header-center';

    // ── Vorheriger Monat ─────────────────────────────────────────────────────
    const prevBtn = document.createElement('button');
    prevBtn.className = 'nav-btn prev-month';
    prevBtn.setAttribute('aria-label', 'Vorheriger Monat');

    // Empfohlene Variante 1: Chevron left
    prevBtn.innerHTML = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="23" height="23" fill="currentColor">
        <path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/>
    </svg>
    `;
    headerCenter.appendChild(prevBtn);

    // ── Nächster Monat ───────────────────────────────────────────────────────
    const nextBtn = document.createElement('button');
    nextBtn.className = 'nav-btn next-month';
    nextBtn.setAttribute('aria-label', 'Nächster Monat');

    nextBtn.innerHTML = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="23" height="23" fill="currentColor">
        <path d="M8.59 16.59L10 18l6-6-6-6-1.41 1.41L13.17 12z"/>
    </svg>
    `;
    headerCenter.appendChild(nextBtn);

    const dateDisplay = document.createElement('span');
    dateDisplay.id = 'current-date-display';
    dateDisplay.className = 'current-date';
    dateDisplay.textContent = 'Lade...';
    headerCenter.appendChild(dateDisplay);

    header.appendChild(headerCenter);

    // ── Header Right: View-Selector + Profil ────────────────────────────────
    const headerRight = document.createElement('div');
    headerRight.className = 'header-right';

    const viewSelector = document.createElement('select');
    viewSelector.id = 'view-selector';
    viewSelector.className = 'view-dropdown';
    viewSelector.setAttribute('aria-label', 'Ansicht wählen');
    viewSelector.innerHTML = `
        <option value="dayGridMonth">Monat</option>
        <option value="timeGridWeek">Woche</option>
        <option value="timeGridDay">Tag</option>
    `;
    headerRight.appendChild(viewSelector);

// 2. Toggle-Button-Group (zwei Buttons ohne Gap, abgerundet außen)
    const toggleGroup = document.createElement('div');
    toggleGroup.className = 'toggle-container';
    toggleGroup.setAttribute('data-toggle-group', 'edit-mode');  // Sinnvoller Name
    toggleGroup.setAttribute('aria-label', 'Bearbeitungs- / Ansichtsmodus');
    toggleGroup.innerHTML = `
        <button class="toggle-btn toggle-left active" aria-label="Normaler Ansichtsmodus" title="Nur anzeigen">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20">
                <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/>
            </svg>
        </button>
        <button class="toggle-btn toggle-right" aria-label="Bearbeitungsmodus" title="Termine verschieben / bearbeiten">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20">
                <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>
            </svg>
        </button>
    `;
    headerRight.appendChild(toggleGroup);

    // Profil-Avatar – aus body data-Attributen lesen
    const profileAvatar = document.createElement('div');
    profileAvatar.className = 'profile-avatar';

    // Werte aus body holen
    const initial = document.body.dataset.userInitial || '?';
    const fullname = document.body.dataset.userFullname || 'Gast';

    profileAvatar.textContent = initial;
    profileAvatar.setAttribute('title', fullname);

    // Debug-Ausgabe
//    console.log('Avatar-Initial aus body:', initial);
//    console.log('Avatar-Fullname aus body:', fullname);

    headerRight.appendChild(profileAvatar);

    header.appendChild(headerRight);

    
    // ── Hamburger Klick-Handler ─────────────────────────────────────────────
    hamburger.addEventListener('click', () => {
        const sidebar = document.querySelector('.kronos-sidebar');
        if (sidebar) {
            sidebar.classList.toggle('active');
            
            // Optional: Zusätzliche Sicherheit – Breite explizit setzen (falls CSS mal überschrieben wird)
            if (sidebar.classList.contains('active')) {
                sidebar.style.width = '280px';
            } else {
                sidebar.style.width = '0px';
            }
        }
        hamburger.classList.toggle('is-active');
//        console.log('Hamburger toggled – Sidebar active:', sidebar?.classList.contains('active'));
    });

    // ── Warte auf Kalender-Ready (statt Polling) ─────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
        const tryConnect = () => {
            if (window.kronosCalendar && window.kronosCalendar.calendar) {
                const calendar = window.kronosCalendar.calendar;

                const updateDateDisplay = () => {
                    dateDisplay.textContent = calendar.view.title || 'Kein Titel';
//                    console.log('Datum aktualisiert:', calendar.view.title);
                };

                calendar.on('datesSet', updateDateDisplay);
                updateDateDisplay();

                prevBtn.addEventListener('click', () => calendar.prev());
                nextBtn.addEventListener('click', () => calendar.next());

                viewSelector.addEventListener('change', (e) => calendar.changeView(e.target.value));

//                console.log('Navigation verbunden mit kronosCalendar');
            } else {
                // Noch nicht da → warte kurz und versuche erneut
                setTimeout(tryConnect, 200);
            }
        };

        tryConnect(); // Sofort starten
    }); 

        // ── Toggle-Handler: Initialisiert Klick-Logik für alle Toggle-Container ─
    function initToggleButtons() {
        document.querySelectorAll('.toggle-container').forEach(container => {
            const buttons = container.querySelectorAll('.toggle-btn');
            
            buttons.forEach(btn => {
                btn.addEventListener('click', () => {
                    // Entferne active von allen in der Gruppe
                    buttons.forEach(b => b.classList.remove('active'));
                    
                    // Setze active auf geklicktem
                    btn.classList.add('active');
                    
                    // Optional: Event triggern für weitere Logik (z.B. Edit-Modus togglen)
                    const event = new CustomEvent('toggleChange', {
                        detail: {
                            group: container.dataset.toggleGroup,
                            active: btn.classList.contains('toggle-left') ? 'left' : 'right'
                        }
                    });
                    container.dispatchEvent(event);
//                    console.log('Toggle gewechselt:', event.detail);
                });
            });
        });
    }

    // Init aufrufen (nach DOM-Einfügen)
    initToggleButtons();

    // ── FullCalendar-Verknüpfung mit Polling ────────────────────────────────
    const tryConnectCalendar = setInterval(() => {
        if (window.kronosCalendar && window.kronosCalendar.calendar) {
            clearInterval(tryConnectCalendar);
            const calendar = window.kronosCalendar.calendar;

            const updateDateDisplay = () => {
                const title = calendar.view.title;
                dateDisplay.textContent = title || 'Kein Titel';
//                console.log('Datum aktualisiert:', title);
            };

            calendar.on('datesSet', updateDateDisplay);
            updateDateDisplay(); // Sofort aufrufen

            prevBtn.addEventListener('click', () => {
                calendar.prev();
//                console.log('← Vorheriger Monat');
            });

            nextBtn.addEventListener('click', () => {
                calendar.next();
//                console.log('→ Nächster Monat');
            });

            viewSelector.addEventListener('change', (e) => {
                const viewName = e.target.value;
                calendar.changeView(viewName);
//                console.log(`Ansicht gewechselt zu: ${viewName}`);
            });

//            console.log('Header erfolgreich mit KronosCalendar verbunden');
        }
    }, 200);

    // Fallback nach 10 Sekunden
    setTimeout(() => {
        if (dateDisplay.textContent === 'Lade...') {
            dateDisplay.textContent = 'Kalender nicht geladen';
            console.warn('Kalender-Instanz nach 10s nicht gefunden');
        }
    }, 10000);

    // ── Avatar per API laden (reines fetch + CSRF aus meta oder Cookie) ─────
    async function loadUserAvatar() {
        let csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        if (!csrfToken) {
            const match = document.cookie.match(/csrftoken=([^;]+)/);
            csrfToken = match ? match[1] : '';
//            console.log('Fallback CSRF aus Cookie:', csrfToken);
        } else {
//            console.log('CSRF aus meta:', csrfToken);
        }

        if (!csrfToken) {
            console.error('Kein CSRF-Token gefunden – API-Call wird fehlschlagen');
            profileAvatar.textContent = '!';
            return;
        }

        try {
            const response = await fetch('/api/method/diakronos.kronos.api.permissions.get_session_info', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Frappe-CSRF-Token': csrfToken
                },
                credentials: 'include',
                body: JSON.stringify({})  // leerer Body für GET-ähnlichen Call
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`API-Fehler: ${response.status} - ${errorText}`);
            }

            const result = await response.json();
            const userInfo = result.message;

            profileAvatar.textContent = userInfo.initial || '?';
            profileAvatar.setAttribute('title', userInfo.full_name || userInfo.name);
//            console.log('Avatar geladen:', userInfo.initial);
        } catch (err) {
            console.error('Avatar-Ladefehler:', err);
            profileAvatar.textContent = '!';
        }
    }

    loadUserAvatar();

//    console.log('header_build_elements → Header-Inhalt eingefügt');
};