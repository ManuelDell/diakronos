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
    headerLeft.appendChild(todaybutton);
    header.appendChild(headerLeft);

    // ── Header Center: Prev – Datum – Next ───────────────────────────────────
    const headerCenter = document.createElement('div');
    headerCenter.className = 'header-center';

    const prevBtn = document.createElement('button');
    prevBtn.className = 'nav-btn prev-month';
    prevBtn.setAttribute('aria-label', 'Vorheriger Monat');
    prevBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="23" height="23" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 6l-6 6l6 6"/></svg>`;
    headerCenter.appendChild(prevBtn);

    const nextBtn = document.createElement('button');
    nextBtn.className = 'nav-btn next-month';
    nextBtn.setAttribute('aria-label', 'Nächster Monat');
    nextBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="23" height="23" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6l-6 6"/></svg>`;
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

    // Ressourcen-Ansicht-Mapping: Normal-View → Resource-View
    const RESOURCE_VIEW_MAP = {
        'dayGridMonth': 'resourceTimelineMonth',
        'timeGridWeek': 'resourceTimelineWeek',
        'timeGridDay':  'resourceTimelineDay',
        'listMonth':    'resourceTimelineWeek',
    };
    const RESOURCE_VIEWS = new Set(Object.values(RESOURCE_VIEW_MAP));

    let _lastNormalView  = 'dayGridMonth';
    let _isResourceView  = false;

    // ── Raumbelegung-Button (Desktop/Tablet only) ─────────────────────────────
    const resourceBtn = document.createElement('button');
    resourceBtn.id        = 'resource-toggle-btn';
    resourceBtn.className = 'resource-toggle-btn';
    resourceBtn.setAttribute('aria-label', 'Raumbelegung anzeigen');
    resourceBtn.setAttribute('aria-pressed', 'false');
    resourceBtn.title = 'Raumbelegung';
    resourceBtn.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 5a1 1 0 0 1 1-1h16a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5z"/><path d="M3 13a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-6z"/><path d="M15 13a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-6z"/></svg>
        <span class="resource-btn-label">Raumbelegung</span>
    `;
    headerRight.appendChild(resourceBtn);

    const viewSelector = document.createElement('select');
    viewSelector.id = 'view-selector';
    viewSelector.className = 'view-dropdown';
    viewSelector.setAttribute('aria-label', 'Ansicht wählen');
    viewSelector.innerHTML = `
        <option value="dayGridMonth">Monat</option>
        <option value="timeGridWeek">Woche</option>
        <option value="timeGridDay">Tag</option>
        <option value="listMonth">Liste</option>
    `;
    headerRight.appendChild(viewSelector);

    // Toggle View / Edit – Standard: View (links) aktiv
    const toggleGroup = document.createElement('div');
    toggleGroup.className = 'toggle-container';
    toggleGroup.setAttribute('data-toggle-group', 'edit-mode');
    toggleGroup.setAttribute('aria-label', 'Bearbeitungs- / Ansichtsmodus');
    toggleGroup.innerHTML = `
        <button class="toggle-btn toggle-left active" aria-label="Ansichtsmodus" title="Nur anzeigen">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 12a2 2 0 1 0 4 0a2 2 0 0 0 -4 0"/><path d="M21 12c-2.4 4 -5.4 6 -9 6c-3.6 0 -6.6 -2 -9 -6c2.4 -4 5.4 -6 9 -6c3.6 0 6.6 2 9 6"/></svg>
        </button>
        <button class="toggle-btn toggle-right" aria-label="Bearbeitungsmodus" title="Termine verschieben / bearbeiten">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4l10.5 -10.5a2.828 2.828 0 1 0 -4 -4l-10.5 10.5v4"/><path d="M13.5 6.5l4 4"/></svg>
        </button>
    `;
    headerRight.appendChild(toggleGroup);

    // Heute-Icon-Button (nur Mobile)
    const todayIconBtn = document.createElement('button');
    todayIconBtn.className = 'today-icon-btn';
    todayIconBtn.setAttribute('aria-label', 'Zum heutigen Tag springen');
    todayIconBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7a2 2 0 0 1 2 -2h12a2 2 0 0 1 2 2v12a2 2 0 0 1 -2 2h-12a2 2 0 0 1 -2 -2v-12"/><path d="M16 3v4"/><path d="M8 3v4"/><path d="M4 11h16"/><path d="M11 15h1"/><path d="M12 15v3"/></svg>`;
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
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 8v-2a2 2 0 0 0 -2 -2h-7a2 2 0 0 0 -2 2v12a2 2 0 0 0 2 2h7a2 2 0 0 0 2 -2v-2"/><path d="M9 12h12l-3 -3"/><path d="M18 15l3 -3"/></svg>
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
            kronosCalendar.calendar.setOption('editable',   !isView);
            kronosCalendar.calendar.setOption('selectable', !isView);
            // Termine neu laden: view_mode ändert welche Statuses sichtbar sind
            kronosCalendar.refetchEvents();
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
    // Header-Datum via ec:datesSet DOM-Event (EventCalendar hat kein .on())
    document.addEventListener('ec:datesSet', (e) => {
        dateDisplay.textContent = e.detail.view.title || '';
        const mobileEl = document.getElementById('mobile-month-display');
        if (mobileEl) {
            mobileEl.textContent = moment(e.detail.start).locale('de').format('MMMM');
        }

        // Raumbelegung-Button-Status synchronisieren
        const viewType = e.detail.view.type;
        _isResourceView = RESOURCE_VIEWS.has(viewType);
        resourceBtn.classList.toggle('active', _isResourceView);
        resourceBtn.setAttribute('aria-pressed', _isResourceView ? 'true' : 'false');

        // Dropdown-Wert aktualisieren (zeigt Normal-View, nicht Resource-View)
        if (!_isResourceView && viewSelector.value !== viewType) {
            viewSelector.value = viewType;
        }
    });

    const tryConnectCalendar = setInterval(() => {
        if (kronosCalendar?.calendar) {
            clearInterval(tryConnectCalendar);
            const calendar = kronosCalendar.calendar;
            prevBtn.addEventListener('click', () => calendar.prev());
            nextBtn.addEventListener('click', () => calendar.next());

            // Add event listeners for today buttons
            const todayBtn = document.getElementById('today-btn');
            const todayIcon = document.querySelector('.today-icon-btn');
            const todayHandler = () => {
                kronosCalendar.today();
                if (kronosMiniCalendar) {
                    kronosMiniCalendar.m = moment();
                    kronosMiniCalendar.render();
                }
            };
            if (todayBtn) todayBtn.addEventListener('click', todayHandler);
            if (todayIcon) todayIcon.addEventListener('click', todayHandler);


            viewSelector.addEventListener('change', (e) => {
                _lastNormalView = e.target.value;
                _isResourceView = false;
                resourceBtn.classList.remove('active');
                resourceBtn.setAttribute('aria-pressed', 'false');
                kronosCalendar.changeView(e.target.value);
            });

            resourceBtn.addEventListener('click', () => {
                if (_isResourceView) {
                    // Zurück zur normalen Ansicht: Slot-Dauer zurücksetzen
                    calendar.setOption('slotDuration', '01:00:00');
                    kronosCalendar.changeView(_lastNormalView);
                } else {
                    // Aktuelle Normal-Ansicht merken, zur Ressource-Ansicht wechseln
                    const currentView = calendar.getOption('view');
                    if (!RESOURCE_VIEWS.has(currentView)) {
                        _lastNormalView = currentView;
                    }
                    // Tagesscheiben statt Stundenscheiben – alle drei Resource-Ansichten
                    calendar.setOption('slotDuration', {days: 1});
                    const resourceView = RESOURCE_VIEW_MAP[_lastNormalView] || 'resourceTimelineWeek';
                    kronosCalendar.changeView(resourceView);
                }
            });
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
                deskLink.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h4a1 1 0 0 1 1 1v6a1 1 0 0 1 -1 1h-4a1 1 0 0 1 -1 -1v-6a1 1 0 0 1 1 -1"/><path d="M5 16h4a1 1 0 0 1 1 1v2a1 1 0 0 1 -1 1h-4a1 1 0 0 1 -1 -1v-2a1 1 0 0 1 1 -1"/><path d="M15 12h4a1 1 0 0 1 1 1v6a1 1 0 0 1 -1 1h-4a1 1 0 0 1 -1 -1v-6a1 1 0 0 1 1 -1"/><path d="M15 4h4a1 1 0 0 1 1 1v2a1 1 0 0 1 -1 1h-4a1 1 0 0 1 -1 -1v-2a1 1 0 0 1 1 -1"/></svg> Zurück zum Desk`;
                profileDropdown.insertBefore(deskLink, profileDropdown.firstChild);
            }
            if (userInfo?.can_moderate) {
                const modLink = document.createElement('a');
                modLink.className = 'profile-dropdown-item';
                modLink.href = '/kronos/moderation';
                modLink.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h6v6h-6z"/><path d="M14 4h6v6h-6z"/><path d="M4 14h6v6h-6z"/><path d="M17 17m-3 0a3 3 0 1 0 6 0a3 3 0 1 0 -6 0"/></svg> Terminmoderation`;
                const logoutBtn = profileDropdown.querySelector('.profile-dropdown-logout');
                profileDropdown.insertBefore(modLink, logoutBtn);
            }
        } catch (_) { /* kein Desk-Link – kein Problem */ }
    }

    loadDeskLink();
}
