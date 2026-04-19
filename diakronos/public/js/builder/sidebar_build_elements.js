import { KronosMiniCalendar, initMiniCalendar } from "./kronos_mini_calendar.js";
import { kronosCalendar } from "./kronos_calendar.js";
import { setSelectedCalendars, getSelectedCalendars } from '../backend/data.js';

export async function sidebar_build_elements(mainContentEl) {
    const sidebar = document.querySelector('.kronos-sidebar');
    if (!sidebar) {
        console.error('❌ .kronos-sidebar nicht gefunden – Sidebar-Bau abgebrochen');
        return;
    }

    const miniContainer = sidebar.querySelector('#mini-kalender');
    if (miniContainer && KronosMiniCalendar) {
        if (!miniContainer.dataset.initialized) {
            initMiniCalendar();
            miniContainer.dataset.initialized = 'true';
        }
    } else {
        console.warn('⚠️ Mini-Kalender konnte nicht gestartet werden', {
            container: !!miniContainer,
            klasse: !!KronosMiniCalendar
        });
    }

    const calendarList = sidebar.querySelector('#calendar-list');
    if (!calendarList) {
        console.error('❌ #calendar-list nicht gefunden');
        return;
    }

    // ── Sidebar-Titel ─────────────────────────────────────────────────────────
    const calSection = sidebar.querySelector('.sidebar-calenderlist-section');
    const titleEl = calSection?.querySelector('.sidebar-title');
    if (titleEl) titleEl.textContent = 'Meine Kalender';

    // ── Kalender-Liste laden ─────────────────────────────────────────────────
    calendarList.innerHTML = '<p class="text-muted p-3">Kalender werden geladen...</p>';

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

            calendarList.innerHTML = '';

            if (calendars.length === 0) {
                calendarList.innerHTML = '<p class="text-muted p-3">Keine Kalender freigegeben</p>';
                return;
            }

            const writable = calendars.filter(cal => cal.write === true);
            const readableOnly = calendars.filter(cal => cal.write !== true);

            let selected = JSON.parse(localStorage.getItem('selected_calendars')) || calendars.map(cal => cal.name);
            setSelectedCalendars(selected);

            function createCalendarItem(cal, isChecked) {
                const item = document.createElement('div');
                item.className = 'calendar-item';
                item.setAttribute('data-color', cal.color || 'var(--primary)');

                item.innerHTML = `
                    <input type="checkbox" id="cal-${cal.name}" ${isChecked ? 'checked' : ''}>
                    <label for="cal-${cal.name}">${cal.title || cal.name}</label>
                    ${cal.write ? '<span class="pencil-icon" title="Schreibrecht">✎</span>' : ''}
                `;

                const checkbox = item.querySelector('input');
                item.style.setProperty('--calendar-color', cal.color || 'var(--primary)');
                checkbox.style.borderColor = cal.color || 'var(--primary)';

                checkbox.addEventListener('change', () => {
                    let selectedCalendars = getSelectedCalendars();
                    if (checkbox.checked) {
                        if (!selectedCalendars.includes(cal.name)) {
                            selectedCalendars.push(cal.name);
                        }
                    } else {
                        selectedCalendars = selectedCalendars.filter(n => n !== cal.name);
                    }
                    setSelectedCalendars(selectedCalendars);
                    localStorage.setItem('selected_calendars', JSON.stringify(selectedCalendars));
                    if (kronosCalendar) kronosCalendar.refetchEvents();
                });

                return item;
            }

            if (writable.length > 0) {
                const writeGroup = document.createElement('div');
                writeGroup.className = 'calendar-group writable';
                writeGroup.innerHTML = '<h4 class="group-title">Schreibzugriff</h4>';
                writable.forEach(cal => {
                    writeGroup.appendChild(createCalendarItem(cal, selected.includes(cal.name)));
                });
                calendarList.appendChild(writeGroup);
            }

            if (readableOnly.length > 0) {
                const readGroup = document.createElement('div');
                readGroup.className = 'calendar-group readable';
                readGroup.innerHTML = '<h4 class="group-title">Nur Lesen</h4>';
                readableOnly.forEach(cal => {
                    readGroup.appendChild(createCalendarItem(cal, selected.includes(cal.name)));
                });
                calendarList.appendChild(readGroup);
            }

        } catch (err) {
            console.error('❌ Fehler beim Laden der Kalender:', err);
            calendarList.innerHTML = '<p class="text-danger p-3">Fehler beim Laden der Kalender: ' + err.message + '</p>';
        }
    }

    await loadCalendars();

    if (kronosCalendar) {
        kronosCalendar.refetchEvents();
    }

    // ── Import-Button (nur für Administrator / Kalenderadministrator) ─────────
    const userRoles = window._kronosUserRoles || [];
    if (userRoles.includes('Administrator') || userRoles.includes('Kalenderadministrator')) {
        const importBtn = document.createElement('a');
        importBtn.className = 'sidebar-import-btn';
        importBtn.href = '/app/google-kalender-import';
        importBtn.innerHTML = '<span class="sidebar-import-icon">⬆</span> Kalender importieren';
        sidebar.appendChild(importBtn);
    }

    // ── Hilfe-Button ─────────────────────────────────────────────────────────
    const helpBtn = document.createElement('button');
    helpBtn.className = 'sidebar-help-btn';
    helpBtn.innerHTML = '<span class="sidebar-help-icon">?</span> Hilfe & Infos';
    sidebar.appendChild(helpBtn);
    helpBtn.addEventListener('click', _showHelpModal);
}

function _showHelpModal() {
    if (document.getElementById('diakronos-help-overlay')) {
        document.getElementById('diakronos-help-overlay').classList.add('visible');
        return;
    }

    const davUrl = `${window.location.origin}/dav/`;

    const overlay = document.createElement('div');
    overlay.id = 'diakronos-help-overlay';
    overlay.className = 'diakronos-help-overlay';
    overlay.innerHTML = `
        <div class="diakronos-help-box">
            <button class="diakronos-help-close" aria-label="Schließen">&times;</button>
            <h2 class="diakronos-help-title">Kalender auf dem Handy einrichten</h2>
            <p class="diakronos-help-intro">Ihr könnt die Gemeindekalender direkt in euer Handy oder euren Computer laden – so habt ihr die Termine immer dabei.</p>

            <div class="diakronos-help-credentials">
                <div class="diakronos-help-cred-row">
                    <span class="diakronos-help-cred-label">Server-Adresse</span>
                    <span class="diakronos-help-cred-value">${davUrl}</span>
                </div>
                <div class="diakronos-help-cred-row">
                    <span class="diakronos-help-cred-label">Benutzername</span>
                    <span class="diakronos-help-cred-value diakronos-help-cred-muted">eure Anmelde-E-Mail-Adresse</span>
                </div>
                <div class="diakronos-help-cred-row">
                    <span class="diakronos-help-cred-label">Passwort</span>
                    <span class="diakronos-help-cred-value diakronos-help-cred-muted">euer normales Anmelde-Passwort</span>
                </div>
            </div>

            <div class="diakronos-help-section">
                <h3>iPhone / iPad</h3>
                <ol>
                    <li>Öffnet <strong>Einstellungen</strong> → <strong>Apps</strong> → <strong>Kalender</strong> → <strong>Kalender-Accounts</strong></li>
                    <li>Tippt auf <strong>Account hinzufügen</strong> → <strong>Andere</strong></li>
                    <li>Wählt <strong>CalDAV-Account hinzufügen</strong></li>
                    <li>Tragt Server-Adresse, Benutzername und Passwort von oben ein</li>
                    <li>Auf <strong>Weiter</strong> tippen – fertig!</li>
                </ol>
            </div>

            <div class="diakronos-help-section">
                <h3>Android (mit der App DAVx⁵)</h3>
                <ol>
                    <li>Installiert <strong>DAVx⁵</strong> kostenlos aus dem Play Store</li>
                    <li>Öffnet die App und tippt auf das <strong>+</strong>-Symbol</li>
                    <li>Wählt <strong>Mit URL und Benutzername anmelden</strong></li>
                    <li>Tragt Server-Adresse, Benutzername und Passwort von oben ein</li>
                    <li>Wählt die gewünschten Kalender aus und synchronisiert</li>
                </ol>
            </div>

            <div class="diakronos-help-section">
                <h3>Thunderbird (Computer)</h3>
                <ol>
                    <li>Öffnet Thunderbird → <strong>Kalender</strong>-Ansicht</li>
                    <li>Rechtsklick in der Kalender-Liste → <strong>Neuer Kalender…</strong></li>
                    <li>Wählt <strong>Im Netzwerk</strong> → Typ <strong>CalDAV</strong></li>
                    <li>Tragt die Server-Adresse von oben ein</li>
                    <li>Benutzername und Passwort eingeben – fertig!</li>
                </ol>
            </div>

            <div class="diakronos-help-footer">
                Diakronos · Dells Dienste
            </div>
        </div>
    `;

    document.body.appendChild(overlay);
    requestAnimationFrame(() => overlay.classList.add('visible'));

    function closeOverlay() {
        overlay.classList.remove('visible');
        overlay.addEventListener('transitionend', () => overlay.remove(), { once: true });
    }
    overlay.querySelector('.diakronos-help-close').addEventListener('click', closeOverlay);
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeOverlay();
    });
}
