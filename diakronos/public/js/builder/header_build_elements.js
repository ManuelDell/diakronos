// public/js/builder/header_build_elements.js

window.header_build_elements = function() {
    console.log('header_build_elements → Starte Header-Bau');

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
    logo.style.height = '35px';
    headerLeft.appendChild(logo);

    header.appendChild(headerLeft);

    // ── Header Center: Prev – Datum – Next ───────────────────────────────────
    const headerCenter = document.createElement('div');
    headerCenter.className = 'header-center';

    const prevBtn = document.createElement('button');
    prevBtn.className = 'nav-btn prev-month';
    prevBtn.setAttribute('aria-label', 'Vorheriger Monat');
    prevBtn.textContent = '<';
    headerCenter.appendChild(prevBtn);

    const nextBtn = document.createElement('button');
    nextBtn.className = 'nav-btn next-month';
    nextBtn.setAttribute('aria-label', 'Nächster Monat');
    nextBtn.textContent = '>';
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

    // Profil-Avatar – aus body data-Attributen lesen
    const profileAvatar = document.createElement('div');
    profileAvatar.className = 'profile-avatar';

    // Werte aus body holen
    const initial = document.body.dataset.userInitial || '?';
    const fullname = document.body.dataset.userFullname || 'Gast';

    profileAvatar.textContent = initial;
    profileAvatar.setAttribute('title', fullname);

    // Debug-Ausgabe
    console.log('Avatar-Initial aus body:', initial);
    console.log('Avatar-Fullname aus body:', fullname);

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
        console.log('Hamburger toggled – Sidebar active:', sidebar?.classList.contains('active'));
    });

    // ── Warte auf Kalender-Ready (statt Polling) ─────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
        const tryConnect = () => {
            if (window.kronosCalendar && window.kronosCalendar.calendar) {
                const calendar = window.kronosCalendar.calendar;

                const updateDateDisplay = () => {
                    dateDisplay.textContent = calendar.view.title || 'Kein Titel';
                    console.log('Datum aktualisiert:', calendar.view.title);
                };

                calendar.on('datesSet', updateDateDisplay);
                updateDateDisplay();

                prevBtn.addEventListener('click', () => calendar.prev());
                nextBtn.addEventListener('click', () => calendar.next());

                viewSelector.addEventListener('change', (e) => calendar.changeView(e.target.value));

                console.log('Navigation verbunden mit kronosCalendar');
            } else {
                // Noch nicht da → warte kurz und versuche erneut
                setTimeout(tryConnect, 200);
            }
        };

        tryConnect(); // Sofort starten
    }); 

    // ── FullCalendar-Verknüpfung mit Polling ────────────────────────────────
    const tryConnectCalendar = setInterval(() => {
        if (window.kronosCalendar && window.kronosCalendar.calendar) {
            clearInterval(tryConnectCalendar);
            const calendar = window.kronosCalendar.calendar;

            const updateDateDisplay = () => {
                const title = calendar.view.title;
                dateDisplay.textContent = title || 'Kein Titel';
                console.log('Datum aktualisiert:', title);
            };

            calendar.on('datesSet', updateDateDisplay);
            updateDateDisplay(); // Sofort aufrufen

            prevBtn.addEventListener('click', () => {
                calendar.prev();
                console.log('← Vorheriger Monat');
            });

            nextBtn.addEventListener('click', () => {
                calendar.next();
                console.log('→ Nächster Monat');
            });

            viewSelector.addEventListener('change', (e) => {
                const viewName = e.target.value;
                calendar.changeView(viewName);
                console.log(`Ansicht gewechselt zu: ${viewName}`);
            });

            console.log('Header erfolgreich mit KronosCalendar verbunden');
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
            console.log('Fallback CSRF aus Cookie:', csrfToken);
        } else {
            console.log('CSRF aus meta:', csrfToken);
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
            console.log('Avatar geladen:', userInfo.initial);
        } catch (err) {
            console.error('Avatar-Ladefehler:', err);
            profileAvatar.textContent = '!';
        }
    }

    loadUserAvatar();

    // API sofort starten
    loadUserAvatar();

    console.log('header_build_elements → Header-Inhalt eingefügt');
};