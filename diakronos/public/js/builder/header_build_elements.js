// builder/header_build_elements.js – Header DOM-Builder

import { kronosMiniCalendar } from './kronos_mini_calendar.js';
import { kronosCalendar } from './kronos_calendar.js';
import { setViewMode } from '../backend/data.js';

export function header_build_elements() {
    const header = document.querySelector('.kronos-header');
    if (!header) {
        console.error('❌ Kein <header class="kronos-header"> in der Seite gefunden');
        return;
    }

    header.innerHTML = '';

    // ── Header Left: Hamburger + Logo + Kalender-Name + Heute-Button ────────
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
    logo.id = 'logopicture';
    logo.style.height = 'var(--button-height)';
    headerLeft.appendChild(logo);

    const calendarName = document.createElement('span');
    calendarName.id = 'calendar-name';
    calendarName.className = 'calendar-name-in-header';
    calendarName.textContent = 'Kalender';
    headerLeft.appendChild(calendarName);

    const todaybutton = document.createElement('button');
    todaybutton.className = 'todaybutton';
    todaybutton.id = 'today-btn';
    todaybutton.textContent = 'Heute';
    todaybutton.setAttribute('aria-label', 'Zum heutigen Tag springen');
    todaybutton.addEventListener('click', () => {
        kronosCalendar?.calendar?.today();
        if (kronosMiniCalendar) {
            kronosMiniCalendar.m = moment();
            kronosMiniCalendar.render();
        }
    });
    headerLeft.appendChild(todaybutton);
    header.appendChild(headerLeft);

    // ── Header Center: Prev – Datum – Next ───────────────────────────────────
    const headerCenter = document.createElement('div');
    headerCenter.className = 'header-center';

    const prevBtn = document.createElement('button');
    prevBtn.className = 'nav-btn prev-month';
    prevBtn.setAttribute('aria-label', 'Vorheriger Monat');
    prevBtn.innerHTML = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="23" height="23" fill="currentColor">
        <path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/>
    </svg>`;
    headerCenter.appendChild(prevBtn);

    const nextBtn = document.createElement('button');
    nextBtn.className = 'nav-btn next-month';
    nextBtn.setAttribute('aria-label', 'Nächster Monat');
    nextBtn.innerHTML = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="23" height="23" fill="currentColor">
        <path d="M8.59 16.59L10 18l6-6-6-6-1.41 1.41L13.17 12z"/>
    </svg>`;
    headerCenter.appendChild(nextBtn);

    const dateDisplay = document.createElement('span');
    dateDisplay.id = 'current-date-display';
    dateDisplay.className = 'current-date';
    dateDisplay.textContent = 'Lade...';
    headerCenter.appendChild(dateDisplay);

    header.appendChild(headerCenter);

    // ── Header Right: View-Selector + View/Edit-Toggle + Avatar ─────────────
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

    // Toggle View / Edit – Standard: View (links) aktiv
    const toggleGroup = document.createElement('div');
    toggleGroup.className = 'toggle-container';
    toggleGroup.setAttribute('data-toggle-group', 'edit-mode');
    toggleGroup.setAttribute('aria-label', 'Bearbeitungs- / Ansichtsmodus');
    toggleGroup.innerHTML = `
        <button class="toggle-btn toggle-left active" aria-label="Ansichtsmodus" title="Nur anzeigen">
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

    // Profil-Avatar + Dropdown
    const profileWrapper = document.createElement('div');
    profileWrapper.className = 'profile-menu-wrapper';

    const profileAvatar = document.createElement('div');
    profileAvatar.className = 'profile-avatar';
    const initial  = document.body.dataset.userInitial  || '?';
    const fullname = document.body.dataset.userFullname || 'Gast';
    profileAvatar.textContent = initial;
    profileAvatar.setAttribute('title', fullname);

    const profileDropdown = document.createElement('div');
    profileDropdown.className = 'profile-dropdown';
    profileDropdown.innerHTML = `
        <a class="profile-dropdown-item" href="/app">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                <path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/>
            </svg>
            Zurück zum Desk
        </a>
        <a class="profile-dropdown-item" href="/apps">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                <path d="M4 8h4V4H4v4zm6 12h4v-4h-4v4zm-6 0h4v-4H4v4zm0-6h4v-4H4v4zm6 0h4v-4h-4v4zm6-10v4h4V4h-4zm-6 4h4V4h-4v4zm6 6h4v-4h-4v4zm0 6h4v-4h-4v4z"/>
            </svg>
            Apps
        </a>
        <div class="profile-dropdown-divider"></div>
        <button class="profile-dropdown-item profile-dropdown-logout">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                <path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z"/>
            </svg>
            Abmelden
        </button>
    `;

    profileWrapper.appendChild(profileAvatar);
    profileWrapper.appendChild(profileDropdown);
    headerRight.appendChild(profileWrapper);

    // Dropdown öffnen/schließen
    profileAvatar.addEventListener('click', (e) => {
        e.stopPropagation();
        profileDropdown.classList.toggle('open');
    });
    document.addEventListener('click', () => profileDropdown.classList.remove('open'));
    profileDropdown.addEventListener('click', (e) => e.stopPropagation());

    // Logout
    profileDropdown.querySelector('.profile-dropdown-logout').addEventListener('click', async () => {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
        try {
            await fetch('/api/method/logout', {
                method: 'POST',
                headers: { 'X-Frappe-CSRF-Token': csrfToken },
                credentials: 'include'
            });
        } finally {
            window.location.href = '/login';
        }
    });

    header.appendChild(headerRight);

    // ── Toggle-Logik (einmalig definiert) ────────────────────────────────────
    function initToggleButtons() {
        document.querySelectorAll('.toggle-container').forEach(container => {
            const buttons = container.querySelectorAll('.toggle-btn');
            buttons.forEach(btn => {
                btn.addEventListener('click', () => {
                    buttons.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    container.dispatchEvent(new CustomEvent('toggleChange', {
                        detail: {
                            group: container.dataset.toggleGroup,
                            active: btn.classList.contains('toggle-left') ? 'left' : 'right'
                        },
                        bubbles: true
                    }));
                });
            });
        });
    }

    initToggleButtons();

    // ── Modus-Änderung: View (links) = true, Edit (rechts) = false ───────────
    document.addEventListener('toggleChange', (e) => {
        const { group, active } = e.detail;
        if (group !== 'edit-mode') return;

        const isView = active === 'left';
        setViewMode(isView);

        if (kronosCalendar?.calendar) {
            kronosCalendar.calendar.setOption('editable',              !isView);
            kronosCalendar.calendar.setOption('eventStartEditable',    !isView);
            kronosCalendar.calendar.setOption('eventDurationEditable', !isView);
            kronosCalendar.calendar.setOption('droppable',             !isView);
            kronosCalendar.calendar.setOption('selectable',            !isView);
        }
    });

    // ── Hamburger ────────────────────────────────────────────────────────────
    hamburger.addEventListener('click', () => {
        const sidebar = document.querySelector('.kronos-sidebar');
        if (sidebar) {
            sidebar.classList.toggle('active');
            sidebar.style.width = sidebar.classList.contains('active') ? '280px' : '0px';
        }
        hamburger.classList.toggle('is-active');
    });

    // ── Kalender-Navigation (Polling bis Kalender initialisiert) ─────────────
    const tryConnectCalendar = setInterval(() => {
        if (kronosCalendar?.calendar) {
            clearInterval(tryConnectCalendar);
            const calendar = kronosCalendar.calendar;

            const updateDateDisplay = () => {
                dateDisplay.textContent = calendar.view.title || '';
            };
            calendar.on('datesSet', updateDateDisplay);
            updateDateDisplay();

            prevBtn.addEventListener('click', () => calendar.prev());
            nextBtn.addEventListener('click', () => calendar.next());
            viewSelector.addEventListener('change', (e) => calendar.changeView(e.target.value));
        }
    }, 200);

    setTimeout(() => {
        if (dateDisplay.textContent === 'Lade...') {
            clearInterval(tryConnectCalendar);
            dateDisplay.textContent = '';
            console.warn('Kalender-Instanz nach 10s nicht gefunden');
        }
    }, 10000);

    // ── Avatar per API laden ─────────────────────────────────────────────────
    async function loadUserAvatar() {
        let csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        if (!csrfToken) {
            const match = document.cookie.match(/csrftoken=([^;]+)/);
            csrfToken = match ? match[1] : '';
        }
        if (!csrfToken) {
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
                body: JSON.stringify({})
            });

            if (!response.ok) throw new Error(`API-Fehler: ${response.status}`);

            const result = await response.json();
            const userInfo = result.message;
            profileAvatar.textContent = userInfo.initial || '?';
            profileAvatar.setAttribute('title', userInfo.full_name || userInfo.name);
        } catch (err) {
            console.error('Avatar-Ladefehler:', err);
            profileAvatar.textContent = '!';
        }
    }

    loadUserAvatar();
}
