/**
 * shared/header.js – Wiederverwendbarer Standard-Header für alle Diakronos-Module
 *
 * Aufbau:
 *   [hamburger] [logo/title | left-slot] ──── [center-slot] ──── [right-slot | avatar]
 *
 * Verwendung:
 *   import { buildStandardHeader } from '../shared/header.js';
 *
 *   const { leftSlot, centerSlot, rightSlot } = buildStandardHeader({
 *       headerEl:       document.querySelector('.mein-header'),
 *       title:          'Psalmos',
 *       logoSrc:        '/assets/diakronos/images/psalmos-logo.svg',  // optional
 *       logoSvg:        '<path d="..."/>',                             // alternativ zu logoSrc
 *       hamburgerEvent: 'psalmos:toggleSidebar',   // Custom-Event-Name beim Hamburger-Klick
 *       startseiteHref: '/diakronos',              // Link in Dropdown
 *   });
 *
 *   // Eigene Elemente in Slots einfügen:
 *   centerSlot.appendChild(myNavButtons);
 *   rightSlot.prepend(myViewSelector);
 *
 * Klassen: Nutzt kronos_header_buttons.scss – header-left, header-right, header-center,
 *          hamburger #hamburger-3, profile-avatar, profile-dropdown, …
 */

export function buildStandardHeader({
    headerEl,
    title          = '',
    logoSrc        = '',
    logoSvg        = '',
    hamburgerEvent = 'diakronos:toggleSidebar',
    startseiteHref = '/diakronos',
} = {}) {
    if (!headerEl) {
        console.error('[shared/header] headerEl fehlt');
        return {};
    }
    headerEl.innerHTML = '';

    // ── LINKS ─────────────────────────────────────────────────────────────────
    const headerLeft = document.createElement('div');
    headerLeft.className = 'header-left';

    // Hamburger
    const hamburger = document.createElement('div');
    hamburger.className = 'hamburger';
    hamburger.id = 'hamburger-3';
    hamburger.setAttribute('aria-label', 'Seitenleiste ein-/ausblenden');
    hamburger.innerHTML = '<span class="line"></span><span class="line"></span><span class="line"></span>';
    hamburger.addEventListener('click', () => {
        hamburger.classList.toggle('is-active');
        document.dispatchEvent(new CustomEvent(hamburgerEvent));
    });
    headerLeft.appendChild(hamburger);

    // Logo (img oder inline-SVG) + Titel
    if (logoSrc) {
        const img = document.createElement('img');
        img.src = logoSrc;
        img.alt = title || 'Logo';
        img.id  = 'logopicture';
        img.style.height = 'var(--button-height)';
        headerLeft.appendChild(img);
    } else if (logoSvg) {
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', '0 0 24 24');
        svg.setAttribute('aria-hidden', 'true');
        svg.style.cssText = 'height:var(--button-height);fill:currentColor;color:var(--primary);';
        svg.innerHTML = logoSvg;
        headerLeft.appendChild(svg);
    }

    if (title) {
        const titleEl = document.createElement('span');
        titleEl.className = 'calendar-name-in-header';
        titleEl.textContent = title;
        headerLeft.appendChild(titleEl);
    }

    // Slot für modulspezifische Links rechts vom Titel
    const leftSlot = document.createElement('div');
    leftSlot.className = 'header-left-slot';
    leftSlot.style.cssText = 'display:contents;';   // unsichtbarer Wrapper
    headerLeft.appendChild(leftSlot);

    headerEl.appendChild(headerLeft);

    // ── MITTE ─────────────────────────────────────────────────────────────────
    const headerCenter = document.createElement('div');
    headerCenter.className = 'header-center';
    headerEl.appendChild(headerCenter);

    // ── RECHTS ────────────────────────────────────────────────────────────────
    const headerRight = document.createElement('div');
    headerRight.className = 'header-right';

    // Slot für modulspezifische Elemente (View-Selector, Toggle etc.)
    const rightSlot = document.createElement('div');
    rightSlot.className = 'header-right-slot';
    rightSlot.style.cssText = 'display:contents;';
    headerRight.appendChild(rightSlot);

    // Avatar + Dropdown (immer vorhanden)
    const profileWrapper = document.createElement('div');
    profileWrapper.className = 'profile-menu-wrapper';

    const profileAvatar = document.createElement('div');
    profileAvatar.className = 'profile-avatar';
    profileAvatar.textContent = document.body.dataset.userInitial || '?';
    profileAvatar.setAttribute('title', document.body.dataset.userFullname || '');

    const profileDropdown = document.createElement('div');
    profileDropdown.className = 'profile-dropdown';
    profileDropdown.innerHTML = `
        <a class="profile-dropdown-item" href="${startseiteHref}">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                <path d="M4 8h4V4H4v4zm6 12h4v-4h-4v4zm-6 0h4v-4H4v4zm0-6h4v-4H4v4zm6 0h4v-4h-4v4zm6-10v4h4V4h-4zm-6 4h4V4h-4v4zm6 6h4v-4h-4v4zm0 6h4v-4h-4v4z"/>
            </svg>
            Startseite
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
    headerEl.appendChild(headerRight);

    // ── Dropdown-Logik (position:fixed) ───────────────────────────────────────
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

    profileDropdown.querySelector('.profile-dropdown-logout').addEventListener('click', async () => {
        const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
        try {
            await fetch('/api/method/logout', {
                method: 'POST',
                headers: { 'X-Frappe-CSRF-Token': csrf },
                credentials: 'include'
            });
        } finally {
            window.location.href = '/login';
        }
    });

    // ── Avatar asynchron laden ────────────────────────────────────────────────
    _loadAvatar(profileAvatar, profileDropdown);

    return { leftSlot, centerSlot: headerCenter, rightSlot };
}

async function _loadAvatar(profileAvatar, profileDropdown) {
    let csrf = document.querySelector('meta[name="csrf-token"]')?.content;
    if (!csrf) {
        const m = document.cookie.match(/csrftoken=([^;]+)/);
        csrf = m ? m[1] : '';
    }
    if (!csrf) { profileAvatar.textContent = '!'; return; }

    try {
        const res = await fetch('/api/method/diakronos.kronos.api.permissions.get_session_info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
            credentials: 'include',
            body: '{}'
        });
        if (!res.ok) throw new Error(res.status);
        const info = (await res.json()).message;

        profileAvatar.setAttribute('title', info.full_name || info.name);
        if (info.user_image) {
            profileAvatar.innerHTML = '';
            const img = document.createElement('img');
            img.src = info.user_image;
            img.alt = info.full_name || info.name;
            img.style.cssText = 'width:100%;height:100%;object-fit:cover;border-radius:50%;';
            profileAvatar.appendChild(img);
        } else {
            profileAvatar.textContent = info.initial || '?';
        }

        if (info.can_access_desk) {
            const link = document.createElement('a');
            link.className = 'profile-dropdown-item';
            link.href = '/app';
            link.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                    <path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/>
                </svg>
                Zurück zum Desk`;
            profileDropdown.insertBefore(link, profileDropdown.firstChild);
        }
    } catch (e) {
        console.error('[shared/header] Avatar-Fehler:', e);
        profileAvatar.textContent = '!';
    }
}
