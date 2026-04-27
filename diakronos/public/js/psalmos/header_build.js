// psalmos/header_build.js – Header DOM-Builder für die Psalmos-Seite
// Verwendet dieselben CSS-Klassen wie Kronos (header-left, header-right,
// hamburger #hamburger-3, profile-avatar …) für visuell identischen Header.

import { ICON_EYE, ICON_PENCIL, ICON_HOME, ICON_LOGOUT, ICON_DASHBOARD, ICON_MUSIC } from '../shared/icons.js';

export function buildPsalmosHeader() {
    const header = document.querySelector('.psalmos-header');
    if (!header) {
        console.error('❌ Kein <header class="psalmos-header"> gefunden');
        return;
    }
    header.innerHTML = '';

    // ── Links: Hamburger + Logo ───────────────────────────────────────────────
    const headerLeft = document.createElement('div');
    headerLeft.className = 'header-left';

    const hamburger = document.createElement('div');
    hamburger.className = 'hamburger';
    hamburger.id = 'hamburger-3';
    hamburger.setAttribute('aria-label', 'Seitenleiste ein-/ausblenden');
    hamburger.innerHTML = '<span class="line"></span><span class="line"></span><span class="line"></span>';
    hamburger.addEventListener('click', () => {
        hamburger.classList.toggle('is-active');
        document.dispatchEvent(new CustomEvent('psalmos:toggleSidebar'));
    });
    headerLeft.appendChild(hamburger);

    // Logo: Musiknoten-SVG (analog zu diakronos-logo.svg in Kronos)
    const logoWrapper = document.createElement('div');
    logoWrapper.style.cssText = 'display:flex;align-items:center;gap:8px;height:var(--button-height);color:var(--primary);';
    logoWrapper.innerHTML = ICON_MUSIC;

    const logoText = document.createElement('span');
    logoText.textContent = 'Psalmos';
    logoText.style.cssText = 'font-weight:600;font-size:1.1rem;color:var(--text-color);white-space:nowrap;';
    logoWrapper.appendChild(logoText);
    headerLeft.appendChild(logoWrapper);
    header.appendChild(headerLeft);

    // ── Rechts: View/Edit Toggle + Avatar + Dropdown ──────────────────────────
    const headerRight = document.createElement('div');
    headerRight.className = 'header-right';

    // View/Edit Toggle Button (zwischen Logo und Avatar)
    const viewEditToggle = document.createElement('button');
    viewEditToggle.className = 'view-edit-toggle';
    viewEditToggle.setAttribute('aria-label', 'Ansichtsmodus umschalten');
    viewEditToggle.innerHTML = `${ICON_EYE}${ICON_PENCIL}`;
    viewEditToggle.addEventListener('click', () => {
        const isViewMode = viewEditToggle.classList.contains('view-mode');
        viewEditToggle.classList.toggle('view-mode', !isViewMode);
        viewEditToggle.classList.toggle('edit-mode', isViewMode);
        document.dispatchEvent(new CustomEvent('diakronos:toggleViewMode', { 
            detail: { isViewMode: !isViewMode } 
        }));
    });
    viewEditToggle.classList.add('view-mode');
    headerRight.appendChild(viewEditToggle);

    const profileWrapper = document.createElement('div');
    profileWrapper.className = 'profile-menu-wrapper';

    const profileAvatar = document.createElement('div');
    profileAvatar.className = 'profile-avatar';
    profileAvatar.textContent = document.body.dataset.userInitial || '?';
    profileAvatar.setAttribute('title', document.body.dataset.userFullname || 'Gast');

    const profileDropdown = document.createElement('div');
    profileDropdown.className = 'profile-dropdown';
    profileDropdown.innerHTML = `
        <a class="profile-dropdown-item" href="/diakronos">${ICON_HOME} Startseite</a>
        <div class="profile-dropdown-divider"></div>
        <button class="profile-dropdown-item profile-dropdown-logout">${ICON_LOGOUT} Abmelden</button>
    `;

    profileWrapper.appendChild(profileAvatar);
    profileWrapper.appendChild(profileDropdown);
    headerRight.appendChild(profileWrapper);
    header.appendChild(headerRight);

    // ── Dropdown: position:fixed via getBoundingClientRect (wie Kronos) ───────
    profileAvatar.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpening = !profileDropdown.classList.contains('open');
        profileDropdown.classList.toggle('open');
        if (isOpening) {
            const rect = profileAvatar.getBoundingClientRect();
            profileDropdown.style.top   = (rect.bottom + 8) + 'px';
            profileDropdown.style.right = (window.innerWidth - rect.right) + 'px';
            profileDropdown.style.left  = '';
        }
    });
    document.addEventListener('click', () => profileDropdown.classList.remove('open'));
    profileDropdown.addEventListener('click', (e) => e.stopPropagation());

    // ── Logout ────────────────────────────────────────────────────────────────
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

    // ── Avatar per API laden (identisch zu Kronos) ────────────────────────────
    _loadUserAvatar(profileAvatar, profileDropdown);
}

async function _loadUserAvatar(profileAvatar, profileDropdown) {
    let csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
    if (!csrfToken) {
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        csrfToken = match ? match[1] : '';
    }
    if (!csrfToken) { profileAvatar.textContent = '!'; return; }

    try {
        const response = await fetch('/api/method/diakronos.kronos.api.permissions.get_session_info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrfToken },
            credentials: 'include',
            body: JSON.stringify({})
        });
        if (!response.ok) throw new Error(`API-Fehler: ${response.status}`);

        const userInfo = (await response.json()).message;
        profileAvatar.setAttribute('title', userInfo.full_name || userInfo.name);

        if (userInfo.user_image) {
            profileAvatar.innerHTML = '';
            const img = document.createElement('img');
            img.src = userInfo.user_image;
            img.alt = userInfo.full_name || userInfo.name;
            img.style.cssText = 'width:100%;height:100%;object-fit:cover;border-radius:50%;';
            profileAvatar.appendChild(img);
        } else {
            profileAvatar.textContent = userInfo.initial || '?';
        }

        if (userInfo.can_access_desk) {
            const deskLink = document.createElement('a');
            deskLink.className = 'profile-dropdown-item';
            deskLink.href = '/app';
            deskLink.innerHTML = `${ICON_DASHBOARD} Zurück zum Desk`;
            profileDropdown.insertBefore(deskLink, profileDropdown.firstChild);
        }
    } catch (err) {
        console.error('Avatar-Ladefehler:', err);
        profileAvatar.textContent = '!';
    }
}
