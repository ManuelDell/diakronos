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

    const mobileMonthDisplay = document.createElement('span');
    mobileMonthDisplay.id = 'mobile-month-display';
    mobileMonthDisplay.className = 'mobile-month-display';
    headerLeft.appendChild(mobileMonthDisplay);

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

    // Heute-Icon-Button (nur Mobile)
    const todayIconBtn = document.createElement('button');
    todayIconBtn.className = 'today-icon-btn';
    todayIconBtn.setAttribute('aria-label', 'Zum heutigen Tag springen');
    todayIconBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="4" width="18" height="18" rx="2"/>
        <line x1="16" y1="2" x2="16" y2="6"/>
        <line x1="8" y1="2" x2="8" y2="6"/>
        <line x1="3" y1="10" x2="21" y2="10"/>
        <circle cx="12" cy="16" r="1.5" fill="currentColor" stroke="none"/>
    </svg>`;
    todayIconBtn.addEventListener('click', () => {
        kronosCalendar?.calendar?.today();
        if (kronosMiniCalendar) {
            kronosMiniCalendar.m = moment();
            kronosMiniCalendar.render();
        }
    });
    headerRight.appendChild(todayIconBtn);

    // Profil-Avatar + Dropdown
    const profileWrapper = document.createElement('div');
    profileWrapper.className = 'profile-menu-wrapper';

    const profileAvatar = document.createElement('div');
    profileAvatar.className = 'profile-avatar';
    const initial   = document.body.dataset.userInitial  || '?';
    const fullname  = document.body.dataset.userFullname || 'Gast';
    const userImage = document.body.dataset.userImage    || '';
    profileAvatar.setAttribute('title', fullname);
    if (userImage) {
        const img = document.createElement('img');
        img.alt = fullname;
        img.style.cssText = 'width:100%;height:100%;object-fit:cover;border-radius:50%;';
        img.onerror = () => { profileAvatar.innerHTML = ''; profileAvatar.textContent = initial; };
        img.src = userImage;
        profileAvatar.appendChild(img);
    } else {
        profileAvatar.textContent = initial;
    }

    const profileDropdown = document.createElement('div');
    profileDropdown.className = 'profile-dropdown';
    profileDropdown.innerHTML = `
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

    // Dropdown öffnen/schließen – position: fixed relativ zum Viewport
    profileAvatar.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpening = !profileDropdown.classList.contains('open');
        profileDropdown.classList.toggle('open');
        if (isOpening) {
            const avatarRect = profileAvatar.getBoundingClientRect();
            profileDropdown.style.top  = (avatarRect.bottom + 8) + 'px';
            profileDropdown.style.right = (window.innerWidth - avatarRect.right) + 'px';
            profileDropdown.style.left = '';
        }
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
            if (window.innerWidth > 768) {
                sidebar.style.width = sidebar.classList.contains('active') ? '280px' : '0px';
            } else {
                sidebar.style.width = '';  // CSS-Medienabfrage übernimmt auf Mobile
            }
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
                const mobileEl = document.getElementById('mobile-month-display');
                if (mobileEl) {
                    mobileEl.textContent = moment(calendar.getDate()).locale('de').format('MMMM');
                }
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

    // ── Desk-Link per API prüfen (nur für berechtigte Nutzer) ────────────────
    async function loadDeskLink() {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        if (!csrfToken) return;
        try {
            const response = await fetch('/api/method/diakronos.kronos.api.permissions.get_session_info', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrfToken },
                credentials: 'include',
                body: JSON.stringify({})
            });
            if (!response.ok) return;
            const { message: userInfo } = await response.json();
            if (userInfo?.can_access_desk) {
                const deskLink = document.createElement('a');
                deskLink.className = 'profile-dropdown-item';
                deskLink.href = '/app';
                deskLink.innerHTML = `
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                        <path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/>
                    </svg>
                    Zurück zum Desk`;
                profileDropdown.insertBefore(deskLink, profileDropdown.firstChild);
            }
        } catch (_) { /* kein Desk-Link – kein Problem */ }
    }

    loadDeskLink();
}
