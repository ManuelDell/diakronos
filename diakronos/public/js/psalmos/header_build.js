// psalmos/header_build.js – Header DOM-Builder für die Psalmos-Seite
// Verwendet dieselben CSS-Klassen wie Kronos (header-left, header-right,
// hamburger #hamburger-3, profile-avatar …) für visuell identischen Header.

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
    logoWrapper.style.cssText = 'display:flex;align-items:center;gap:8px;height:var(--button-height);';

    const logoIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    logoIcon.setAttribute('viewBox', '0 0 24 24');
    logoIcon.setAttribute('height', 'var(--button-height)');
    logoIcon.setAttribute('fill', 'currentColor');
    logoIcon.setAttribute('aria-hidden', 'true');
    logoIcon.style.color = 'var(--primary)';
    logoIcon.innerHTML = '<path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z"/>';

    const logoText = document.createElement('span');
    logoText.textContent = 'Psalmos';
    logoText.style.cssText = 'font-weight:600;font-size:1.1rem;color:var(--text-color);white-space:nowrap;';

    logoWrapper.appendChild(logoIcon);
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
    viewEditToggle.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round" class="view-icon">
            <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/>
            <circle cx="12" cy="12" r="3"/>
        </svg>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round" class="edit-icon" style="display:none;">
            <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>
        </svg>
    `;
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
        <a class="profile-dropdown-item" href="/diakronos">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l-2 0l9 -9l9 9l-2 0"/><path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2 -2v-7"/><path d="M9 21v-6a2 2 0 0 1 2 -2h2a2 2 0 0 1 2 2v6"/></svg>
            Startseite
        </a>
        <div class="profile-dropdown-divider"></div>
        <button class="profile-dropdown-item profile-dropdown-logout">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 8v-2a2 2 0 0 0 -2 -2h-7a2 2 0 0 0 -2 2v12a2 2 0 0 0 2 2h7a2 2 0 0 0 2 -2v-2"/><path d="M9 12h12l-3 -3"/><path d="M18 15l3 -3"/></svg>
            Abmelden
        </button>
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
            deskLink.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h4a1 1 0 0 1 1 1v6a1 1 0 0 1 -1 1h-4a1 1 0 0 1 -1 -1v-6a1 1 0 0 1 1 -1"/><path d="M5 16h4a1 1 0 0 1 1 1v2a1 1 0 0 1 -1 1h-4a1 1 0 0 1 -1 -1v-2a1 1 0 0 1 1 -1"/><path d="M15 12h4a1 1 0 0 1 1 1v6a1 1 0 0 1 -1 1h-4a1 1 0 0 1 -1 -1v-6a1 1 0 0 1 1 -1"/><path d="M15 4h4a1 1 0 0 1 1 1v2a1 1 0 0 1 -1 1h-4a1 1 0 0 1 -1 -1v-2a1 1 0 0 1 1 -1"/></svg> Zurück zum Desk`;
            profileDropdown.insertBefore(deskLink, profileDropdown.firstChild);
        }
    } catch (err) {
        console.error('Avatar-Ladefehler:', err);
        profileAvatar.textContent = '!';
    }
}
