// kanban.bundle.js – Terminmoderation Kanban Board

const API = {
    async post(method, body = {}) {
        const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
        const res = await fetch(`/api/method/${method}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
            body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error(`API ${method} failed: ${res.status}`);
        const data = await res.json();
        return data.message;
    }
};

// ── State ─────────────────────────────────────────────────────────────────────
let boardData    = { vorschlaege: [], konflikte: [], staging: [], notifications: {} };
let stagingIds   = [];  // ordered list of IDs in Festlegen column
let ressources   = [];  // [{id, title}]

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtDate(str, allDay) {
    if (!str) return '';
    const d = new Date(str);
    if (isNaN(d)) return str;
    const opts = { weekday: 'short', day: '2-digit', month: '2-digit' };
    if (allDay) return d.toLocaleDateString('de-DE', opts);
    return d.toLocaleDateString('de-DE', opts) + ' · ' +
           d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
}

function toDateTimeLocal(str) {
    if (!str) return '';
    // str: "2024-01-15 14:00:00" → "2024-01-15T14:00"
    return str.slice(0, 16).replace(' ', 'T');
}

function fromDateTimeLocal(str) {
    if (!str) return '';
    return str.replace('T', ' ') + ':00';
}

function safe(s) {
    return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ── Card builder ──────────────────────────────────────────────────────────────
function buildCard(event, column) {
    const card = document.createElement('div');
    card.className = 'kanban-card' + (column === 'konflikte' ? ' kanban-card-konflikt' : '');
    card.dataset.id     = event.id;
    card.dataset.origin = column === 'festlegen' ? (event._origin || 'vorschlaege') : column;

    const notif = boardData.notifications[event.id];
    const notifHtml = notif
        ? `<div class="kanban-card-notif">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v4"/><path d="M12 16v.01"/></svg>
              Bearbeitet von ${safe(notif.by || 'Unbekannt')}
           </div>`
        : '';

    const ressourceHtml = event.ressource
        ? `<div class="kanban-card-ressource">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v2a3 3 0 0 1-3 3h-12a3 3 0 0 1-3-3z"/><path d="M3 17a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v0a2 2 0 0 1-2 2h-14a2 2 0 0 1-2-2z"/></svg>
              ${safe(event.ressource)}
           </div>`
        : '';

    const removeBtn = column === 'festlegen'
        ? `<button class="kanban-card-remove" title="Zurück">×</button>`
        : '';

    const konfliktBadge = column === 'konflikte'
        ? `<span class="kanban-badge-konflikt">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4"/><circle cx="12" cy="17" r=".5" fill="currentColor"/><path d="M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214a1.914 1.914 0 0 0 1.636-2.87l-8.106-13.536a1.914 1.914 0 0 0-3.274 0z"/></svg>
              Konflikt
           </span>`
        : '';

    card.innerHTML = `
        <div class="kanban-card-strip" style="background:${event.calendar_color}"></div>
        <div class="kanban-card-body">
            <div class="kanban-card-header">
                <span class="kanban-card-title">${safe(event.title)}</span>
                ${konfliktBadge}
                ${removeBtn}
            </div>
            <div class="kanban-card-time">${fmtDate(event.start, event.all_day)}${event.end && !event.all_day ? ' – ' + fmtDate(event.end, true).replace(/\w+\.,?\s*/, '') : ''}</div>
            <div class="kanban-card-cal">
                <span class="kanban-dot" style="background:${event.calendar_color}"></span>
                ${safe(event.calendar_title)}
            </div>
            ${ressourceHtml}
            ${notifHtml}
        </div>
    `;

    return card;
}

// ── Render ────────────────────────────────────────────────────────────────────
function renderBoard() {
    const sortV = document.getElementById('sort-vorschlaege');
    const sortK = document.getElementById('sort-konflikte');
    const sortF = document.getElementById('sort-festlegen');
    const dropHint = document.getElementById('drop-hint');

    sortV.innerHTML = '';
    sortK.innerHTML = '';
    sortF.innerHTML = '';

    if (boardData.vorschlaege.length === 0) {
        sortV.innerHTML = '<div class="kanban-empty-hint">Keine Vorschläge</div>';
    } else {
        boardData.vorschlaege.forEach(ev => {
            const card = buildCard(ev, 'vorschlaege');
            card.addEventListener('click', () => openEditModal(ev));
            sortV.appendChild(card);
        });
    }

    if (boardData.konflikte.length === 0) {
        sortK.innerHTML = '<div class="kanban-empty-hint">Keine Konflikte</div>';
    } else {
        boardData.konflikte.forEach(ev => {
            const card = buildCard(ev, 'konflikte');
            card.addEventListener('click', () => openConflictModal(ev));
            sortK.appendChild(card);
        });
    }

    // Festlegen column
    const stagingEvents = stagingIds
        .map(id => boardData.staging.find(e => e.id === id) || null)
        .filter(Boolean);

    if (stagingEvents.length === 0) {
        dropHint.style.display = 'flex';
    } else {
        dropHint.style.display = 'none';
        stagingEvents.forEach(ev => {
            const card = buildCard(ev, 'festlegen');
            card.querySelector('.kanban-card-remove')?.addEventListener('click', (e) => {
                e.stopPropagation();
                removeFromStaging(ev.id);
            });
            card.addEventListener('click', (e) => {
                if (e.target.classList.contains('kanban-card-remove')) return;
                openEditModal(ev);
            });
            sortF.appendChild(card);
        });
    }

    // Update counts
    document.getElementById('count-vorschlaege').textContent = boardData.vorschlaege.length;
    document.getElementById('count-konflikte').textContent   = boardData.konflikte.length;
    document.getElementById('count-festlegen').textContent   = stagingEvents.length;

    // Save button state
    const saveBtn = document.getElementById('kanban-save-btn');
    saveBtn.disabled = stagingEvents.length === 0;
}

function removeFromStaging(id) {
    stagingIds = stagingIds.filter(i => i !== id);
    // Move back to its origin column
    const ev = boardData.staging.find(e => e.id === id);
    if (ev) {
        boardData.staging = boardData.staging.filter(e => e.id !== id);
        if (ev.status === 'Konflikt') {
            boardData.konflikte.push(ev);
        } else {
            boardData.vorschlaege.push(ev);
        }
    }
    renderBoard();
    debouncedSaveState();
}

// ── SortableJS ────────────────────────────────────────────────────────────────
function initSortable() {
    const Sortable = window.Sortable;
    if (!Sortable) { console.error('SortableJS not loaded'); return; }

    // Vorschläge: can be dragged to Festlegen
    Sortable.create(document.getElementById('sort-vorschlaege'), {
        group:     { name: 'vorschlaege', pull: true, put: false },
        sort:      false,
        animation: 150,
        ghostClass: 'kanban-ghost',
        dragClass:  'kanban-dragging',
        filter:    '.kanban-empty-hint',
    });

    // Festlegen: accepts from Vorschläge only
    Sortable.create(document.getElementById('sort-festlegen'), {
        group:     { name: 'festlegen', pull: false, put: ['vorschlaege'] },
        sort:      true,
        animation: 150,
        ghostClass: 'kanban-ghost',
        dragClass:  'kanban-dragging',
        onAdd(evt) {
            const id = evt.item.dataset.id;
            if (!id) return;
            // Find event in vorschlaege
            const ev = boardData.vorschlaege.find(e => e.id === id);
            if (!ev) return;
            boardData.vorschlaege = boardData.vorschlaege.filter(e => e.id !== id);
            ev._origin = 'vorschlaege';
            boardData.staging.push(ev);
            if (!stagingIds.includes(id)) stagingIds.push(id);
            renderBoard();
            debouncedSaveState();
        },
    });
}

// ── Edit modal (for Vorschläge + Festlegen cards) ─────────────────────────────
function openEditModal(event) {
    // Simple inline edit modal for non-conflict events
    const overlay = document.getElementById('conflict-overlay');
    overlay.innerHTML = buildEditModalHTML(event, null);
    overlay.style.display = 'flex';

    const form = overlay.querySelector('.kanban-edit-form');
    const closeBtn = overlay.querySelector('.kanban-modal-close');

    closeBtn.onclick = () => { overlay.style.display = 'none'; };
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.style.display = 'none'; }, { once: true });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const data = getFormData(form, event);
        const submitBtn = form.querySelector('[type=submit]');
        submitBtn.disabled = true;
        try {
            await API.post('diakronos.kronos.api.kanban_api.resolve_conflict', {
                element_id: event.id,
                action: 'vorschlag',
                ...data,
            });
            overlay.style.display = 'none';
            await reloadBoard();
        } catch(ex) {
            console.error(ex);
            submitBtn.disabled = false;
        }
    });
}

// ── Conflict modal ────────────────────────────────────────────────────────────
async function openConflictModal(event) {
    const overlay = document.getElementById('conflict-overlay');
    overlay.innerHTML = `<div class="kanban-modal-loading">Lade Konfliktdaten…</div>`;
    overlay.style.display = 'flex';

    let partner = null;
    try {
        partner = await API.post('diakronos.kronos.api.kanban_api.get_conflict_partner', {
            element_id: event.id
        });
    } catch(e) { /* no partner */ }

    overlay.innerHTML = buildConflictModalHTML(event, partner);

    const form = overlay.querySelector('.kanban-edit-form');

    overlay.querySelector('.kanban-modal-close').onclick = () => {
        overlay.style.display = 'none';
    };
    overlay.addEventListener('click', e => {
        if (e.target === overlay) overlay.style.display = 'none';
    }, { once: true });

    // "Konflikt ignorieren" → ignore_conflict=true, move to Festlegen
    overlay.querySelector('#btn-ignore').onclick = async () => {
        const data = getFormData(form, event);
        overlay.querySelector('#btn-ignore').disabled = true;
        try {
            await API.post('diakronos.kronos.api.kanban_api.resolve_conflict', {
                element_id: event.id, action: 'ignore', ...data,
            });
            // Reload, then move to staging
            await reloadBoard();
            // After reload, the event should now be in vorschlaege (status=Vorschlag)
            // Move it to staging
            const freshEv = boardData.vorschlaege.find(e => e.id === event.id);
            if (freshEv) {
                boardData.vorschlaege = boardData.vorschlaege.filter(e => e.id !== event.id);
                freshEv._origin = 'vorschlaege';
                boardData.staging.push(freshEv);
                if (!stagingIds.includes(freshEv.id)) stagingIds.push(freshEv.id);
                renderBoard();
                debouncedSaveState();
            }
            overlay.style.display = 'none';
        } catch(ex) {
            console.error(ex);
            overlay.querySelector('#btn-ignore').disabled = false;
        }
    };

    // "Vorschlagen" → set status=Vorschlag, move to Vorschläge column
    overlay.querySelector('#btn-vorschlag').onclick = async () => {
        const data = getFormData(form, event);
        overlay.querySelector('#btn-vorschlag').disabled = true;
        try {
            await API.post('diakronos.kronos.api.kanban_api.resolve_conflict', {
                element_id: event.id, action: 'vorschlag', ...data,
            });
            overlay.style.display = 'none';
            await reloadBoard();
        } catch(ex) {
            console.error(ex);
            overlay.querySelector('#btn-vorschlag').disabled = false;
        }
    };

    // "Festlegen" → save edits, move to Festlegen staging
    overlay.querySelector('#btn-festlegen').onclick = async () => {
        const data = getFormData(form, event);
        overlay.querySelector('#btn-festlegen').disabled = true;
        try {
            await API.post('diakronos.kronos.api.kanban_api.resolve_conflict', {
                element_id: event.id, action: 'festlegen', ...data,
            });
            // Move from konflikte to staging
            await reloadBoard();
            const freshEv = boardData.konflikte.find(e => e.id === event.id)
                         || boardData.vorschlaege.find(e => e.id === event.id);
            if (freshEv) {
                boardData.konflikte   = boardData.konflikte.filter(e => e.id !== event.id);
                boardData.vorschlaege = boardData.vorschlaege.filter(e => e.id !== event.id);
                freshEv._origin = 'konflikte';
                boardData.staging.push(freshEv);
                if (!stagingIds.includes(freshEv.id)) stagingIds.push(freshEv.id);
                renderBoard();
                debouncedSaveState();
            }
            overlay.style.display = 'none';
        } catch(ex) {
            console.error(ex);
            overlay.querySelector('#btn-festlegen').disabled = false;
        }
    };
}

function getFormData(form, event) {
    const fd = new FormData(form);
    const allDay = form.querySelector('[name=all_day]')?.checked;
    return {
        title:         fd.get('title') || event.title,
        element_start: allDay ? null : fromDateTimeLocal(fd.get('start') || ''),
        element_end:   allDay ? null : fromDateTimeLocal(fd.get('end') || ''),
        all_day:       allDay ? 1 : 0,
        ressource:     fd.get('ressource') || '',
        description:   fd.get('description') || '',
    };
}

function buildEditFormFields(event) {
    const ressourceOptions = ressources.map(r =>
        `<option value="${safe(r.id)}" ${event.ressource === r.id ? 'selected' : ''}>${safe(r.title)}</option>`
    ).join('');

    return `
        <div class="kanban-form-group">
            <label>Titel</label>
            <input type="text" name="title" value="${safe(event.title)}" required class="kanban-input">
        </div>
        <div class="kanban-form-row">
            <div class="kanban-form-group">
                <label>Beginn</label>
                <input type="datetime-local" name="start" value="${toDateTimeLocal(event.start)}" class="kanban-input">
            </div>
            <div class="kanban-form-group">
                <label>Ende</label>
                <input type="datetime-local" name="end" value="${toDateTimeLocal(event.end)}" class="kanban-input">
            </div>
        </div>
        <div class="kanban-form-group kanban-form-allday">
            <label class="kanban-checkbox-label">
                <input type="checkbox" name="all_day" ${event.all_day ? 'checked' : ''}>
                Ganztägig
            </label>
        </div>
        <div class="kanban-form-group">
            <label>Raum</label>
            <select name="ressource" class="kanban-input">
                <option value="">— Kein Raum —</option>
                ${ressourceOptions}
            </select>
        </div>
        <div class="kanban-form-group">
            <label>Beschreibung</label>
            <textarea name="description" rows="3" class="kanban-input kanban-textarea">${safe(event.description)}</textarea>
        </div>
    `;
}

function buildEditModalHTML(event, partner) {
    return `
        <div class="kanban-modal-box kanban-modal-edit">
            <div class="kanban-modal-header">
                <h3>Termin bearbeiten</h3>
                <button class="kanban-modal-close">&times;</button>
            </div>
            <form class="kanban-edit-form">
                ${buildEditFormFields(event)}
                <div class="kanban-modal-footer">
                    <button type="submit" class="btn btn-primary">Speichern</button>
                </div>
            </form>
        </div>
    `;
}

function buildConflictModalHTML(event, partner) {
    const partnerHtml = partner ? `
        <div class="kanban-conflict-partner">
            <div class="kanban-conflict-partner-header">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4"/><circle cx="12" cy="17" r=".5" fill="currentColor"/><path d="M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214a1.914 1.914 0 0 0 1.636-2.87l-8.106-13.536a1.914 1.914 0 0 0-3.274 0z"/></svg>
                Überschneidung mit
            </div>
            <div class="kanban-partner-card">
                <div class="kanban-partner-title">${safe(partner.title)}</div>
                <div class="kanban-partner-time">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="5" width="16" height="16" rx="2"/><path d="M16 3v4"/><path d="M8 3v4"/><path d="M4 11h16"/></svg>
                    ${fmtDate(partner.start, partner.all_day)}
                </div>
                <div class="kanban-partner-cal">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v4l3 3"/></svg>
                    ${safe(partner.calendar)}
                </div>
                ${partner.ressource ? `<div class="kanban-partner-ressource">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v2a3 3 0 0 1-3 3h-12a3 3 0 0 1-3-3z"/><path d="M3 17a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v0a2 2 0 0 1-2 2h-14a2 2 0 0 1-2-2z"/></svg>
                    ${safe(partner.ressource)}
                </div>` : ''}
                <p class="kanban-partner-hint">
                    Passe Zeit oder Raum an, um den Konflikt zu vermeiden, oder ignoriere ihn bewusst.
                </p>
            </div>
        </div>
    ` : `<div class="kanban-conflict-partner kanban-partner-empty">
            <p>Kein konkreter Konfliktpartner gefunden. Möglicherweise wurde der überschneidende Termin bereits bearbeitet.</p>
         </div>`;

    return `
        <div class="kanban-modal-box kanban-modal-conflict">
            <div class="kanban-modal-header">
                <div class="kanban-modal-title-row">
                    <h3>Konflikt auflösen</h3>
                    <span class="kanban-badge-konflikt-lg">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4"/><circle cx="12" cy="17" r=".5" fill="currentColor"/><path d="M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214a1.914 1.914 0 0 0 1.636-2.87l-8.106-13.536a1.914 1.914 0 0 0-3.274 0z"/></svg>
                        Konflikt
                    </span>
                </div>
                <button class="kanban-modal-close">&times;</button>
            </div>
            <div class="kanban-conflict-body">
                <div class="kanban-conflict-edit">
                    <form class="kanban-edit-form">
                        ${buildEditFormFields(event)}
                    </form>
                </div>
                ${partnerHtml}
            </div>
            <div class="kanban-modal-footer kanban-conflict-footer">
                <button class="btn btn-secondary" id="btn-ignore">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3l18 18"/><path d="M10.584 10.587a2 2 0 0 0 2.828 2.83"/><path d="M9.363 5.365a9.466 9.466 0 0 1 2.637-.365c4 0 7.333 2.333 10 7c-.778 1.361-1.612 2.524-2.503 3.488m-2.14 1.861c-1.631 1.1-3.415 1.651-5.357 1.651c-4 0-7.333-2.333-10-7c1.369-2.395 2.913-4.175 4.632-5.341"/></svg>
                    Konflikt ignorieren
                </button>
                <div style="flex:1"></div>
                <button class="btn btn-warning" id="btn-vorschlag">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0"/><path d="M12 8v4l3 3"/></svg>
                    Vorschlagen
                </button>
                <button class="btn btn-success" id="btn-festlegen">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5l10-10"/></svg>
                    Festlegen
                </button>
            </div>
        </div>
    `;
}

// ── Finalize (Save button) ────────────────────────────────────────────────────
async function finalizeStaging() {
    const btn = document.getElementById('kanban-save-btn');
    btn.disabled = true;
    btn.textContent = '…';
    try {
        const result = await API.post('diakronos.kronos.api.kanban_api.finalize_staged_events', {
            event_ids: stagingIds
        });
        stagingIds = [];
        await reloadBoard();
    } catch(e) {
        console.error('Finalisierung fehlgeschlagen', e);
        btn.disabled = false;
        btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 4h10l4 4v10a2 2 0 0 1-2 2h-12a2 2 0 0 1-2-2v-12a2 2 0 0 1 2-2"/><path d="M12 14m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0"/><path d="M14 4l0 4l-6 0l0-4"/></svg> Alle festlegen`;
    }
}

// ── State persistence ─────────────────────────────────────────────────────────
let _saveTimer = null;
function debouncedSaveState() {
    clearTimeout(_saveTimer);
    _saveTimer = setTimeout(() => {
        API.post('diakronos.kronos.api.kanban_api.save_staging_state', {
            staging_ids: stagingIds
        }).catch(e => console.warn('State save failed', e));
    }, 500);
}

// ── Reload ────────────────────────────────────────────────────────────────────
async function reloadBoard() {
    boardData = await API.post('diakronos.kronos.api.kanban_api.get_kanban_board_data');
    // Merge staging IDs: keep only IDs that are in boardData.staging
    stagingIds = stagingIds.filter(id => boardData.staging.some(e => e.id === id));
    // Add any staging events from boardData not yet in stagingIds
    boardData.staging.forEach(e => {
        if (!stagingIds.includes(e.id)) stagingIds.push(e.id);
    });
    renderBoard();
}

// ── Avatar header ─────────────────────────────────────────────────────────────
function buildAvatarHeader() {
    const wrapper = document.getElementById('kanban-avatar-wrapper');
    if (!wrapper) return;

    const initial   = document.body.dataset.userInitial  || '?';
    const fullname  = document.body.dataset.userFullname || 'Gast';
    const userImage = document.body.dataset.userImage    || '';

    const avatar = document.createElement('div');
    avatar.className = 'kanban-avatar';
    avatar.title = fullname;
    if (userImage) {
        const img = document.createElement('img');
        img.alt = fullname;
        img.onerror = () => { avatar.innerHTML = ''; avatar.textContent = initial; };
        img.src = userImage;
        avatar.appendChild(img);
    } else {
        avatar.textContent = initial;
    }

    const dropdown = document.createElement('div');
    dropdown.className = 'kanban-dropdown';
    dropdown.innerHTML = `
        <a class="kanban-dropdown-item" href="/kronos/calendar">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="5" width="16" height="16" rx="2"/><path d="M16 3v4"/><path d="M8 3v4"/><path d="M4 11h16"/></svg>
            Zurück zum Kalender
        </a>
        <div class="kanban-dropdown-divider"></div>
        <button class="kanban-dropdown-item kanban-dropdown-logout">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 8v-2a2 2 0 0 0-2-2h-7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h7a2 2 0 0 0 2-2v-2"/><path d="M9 12h12l-3-3"/><path d="M18 15l3-3"/></svg>
            Abmelden
        </button>
    `;

    wrapper.appendChild(avatar);
    wrapper.appendChild(dropdown);

    avatar.addEventListener('click', (e) => {
        e.stopPropagation();
        const opening = !dropdown.classList.contains('open');
        dropdown.classList.toggle('open');
        if (opening) {
            const r = avatar.getBoundingClientRect();
            dropdown.style.top   = (r.bottom + 6) + 'px';
            dropdown.style.right = (window.innerWidth - r.right) + 'px';
        }
    });
    document.addEventListener('click', () => dropdown.classList.remove('open'));
    dropdown.addEventListener('click', e => e.stopPropagation());

    dropdown.querySelector('.kanban-dropdown-logout').addEventListener('click', async () => {
        const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
        try {
            await fetch('/api/method/logout', { method: 'POST', headers: { 'X-Frappe-CSRF-Token': csrf } });
        } finally {
            window.location.href = '/login';
        }
    });
}

// ── SortableJS loader ─────────────────────────────────────────────────────────
function loadSortableJS() {
    return new Promise((resolve, reject) => {
        if (window.Sortable) { resolve(); return; }
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js';
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    buildAvatarHeader();

    // Load SortableJS from CDN
    try {
        await loadSortableJS();
    } catch(e) {
        console.error('SortableJS konnte nicht geladen werden', e);
    }

    // Load ressources for dropdowns
    try {
        const r = await API.post('diakronos.kronos.api.ressource_api.get_ressources');
        ressources = (r || []).map(x => ({ id: x.id, title: x.title }));
    } catch(e) { /* no ressources */ }

    // Load board
    try {
        boardData = await API.post('diakronos.kronos.api.kanban_api.get_kanban_board_data');
        stagingIds = boardData.staging.map(e => e.id);
    } catch(e) {
        console.error('Board-Daten konnten nicht geladen werden', e);
        boardData = { vorschlaege: [], konflikte: [], staging: [], notifications: {} };
    }

    renderBoard();
    initSortable();

    document.getElementById('kanban-save-btn').addEventListener('click', finalizeStaging);
});
