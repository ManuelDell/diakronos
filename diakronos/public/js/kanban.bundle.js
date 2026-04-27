// kanban.bundle.js – Terminmoderation Kanban Board

import { initKronosSearch } from './search/kronos_search.js';
import { ICON_REPEAT_SM as ICON_REPEAT, ICON_WARN, ICON_INFO, ICON_BUILDING, ICON_BUILDING_MD, ICON_CALENDAR, ICON_CALENDAR_LG, ICON_WARN_LG, ICON_CLOCK, ICON_EYE_OFF, ICON_CHECK, ICON_FLOPPY, ICON_SEARCH_SM, ICON_LOGOUT } from './shared/icons.js';

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
let boardData  = { vorschlaege: [], konflikte: [], staging: [], notifications: {} };
let stagingIds = [];  // ordered list of individual event IDs in Festlegen column
let ressources = [];  // [{id, title}]

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
    return str.slice(0, 16).replace(' ', 'T');
}

function fromDateTimeLocal(str) {
    if (!str) return '';
    return str.replace('T', ' ') + ':00';
}

function safe(s) {
    return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ── Serie Grouping ────────────────────────────────────────────────────────────
/**
 * Groups a flat list of events into display items:
 * - Events without series_id → kept as-is ({type: "event", ...})
 * - Events with same series_id → grouped into one {type: "serie", ...}
 */
function groupItems(events) {
    const seriesMap = {};
    const result    = [];

    events.forEach(ev => {
        if (ev.series_id) {
            if (!seriesMap[ev.series_id]) seriesMap[ev.series_id] = [];
            seriesMap[ev.series_id].push(ev);
        } else {
            result.push(ev);
        }
    });

    Object.entries(seriesMap).forEach(([sid, evts]) => {
        const sorted      = [...evts].sort((a, b) => (a.start || '').localeCompare(b.start || ''));
        const first       = sorted[0];
        const last        = sorted[sorted.length - 1];
        const hasKonflikt = evts.some(e => e.status === 'Konflikt');
        result.push({
            type:            'serie',
            id:              sid,
            series_id:       sid,
            title:           first.title,
            count:           evts.length,
            event_ids:       evts.map(e => e.id),
            events:          evts,
            first_start:     first.start,
            last_start:      last.start,
            all_day:         first.all_day,
            calendar:        first.calendar,
            calendar_title:  first.calendar_title,
            calendar_color:  first.calendar_color,
            has_konflikt:    hasKonflikt,
            konflikt_events: evts.filter(e => e.status === 'Konflikt'),
            status:          hasKonflikt ? 'Konflikt' : 'Vorschlag',
        });
    });

    return result;
}

/**
 * Rebuilds the staging display groups from boardData.staging + stagingIds order.
 * Series events are collapsed into one group; singles stay as individual items.
 */
function buildStagingGroups() {
    const seriesMap = {};
    boardData.staging.forEach(ev => {
        if (ev.series_id) {
            if (!seriesMap[ev.series_id]) seriesMap[ev.series_id] = [];
            seriesMap[ev.series_id].push(ev);
        }
    });

    const groups    = [];
    const processed = new Set();

    for (const id of stagingIds) {
        const ev = boardData.staging.find(e => e.id === id);
        if (!ev) continue;

        if (ev.series_id) {
            if (processed.has(ev.series_id)) continue;
            processed.add(ev.series_id);
            const evts   = seriesMap[ev.series_id] || [];
            const sorted = [...evts].sort((a, b) => (a.start || '').localeCompare(b.start || ''));
            groups.push({
                type:           'serie',
                id:             ev.series_id,
                series_id:      ev.series_id,
                title:          ev.title,
                count:          evts.length,
                event_ids:      evts.map(e => e.id),
                first_start:    sorted[0]?.start,
                last_start:     sorted[sorted.length - 1]?.start,
                all_day:        ev.all_day,
                calendar_title: ev.calendar_title,
                calendar_color: ev.calendar_color,
                _origin:        ev._origin || 'vorschlaege',
            });
        } else {
            if (processed.has(ev.id)) continue;
            processed.add(ev.id);
            groups.push(ev);
        }
    }
    return groups;
}

// ── Card builders ─────────────────────────────────────────────────────────────

function buildCard(event, column) {
    const card = document.createElement('div');
    card.className = 'kanban-card' + (column === 'konflikte' ? ' kanban-card-konflikt' : '');
    card.dataset.id     = event.id;
    card.dataset.type   = 'event';
    card.dataset.origin = column === 'festlegen' ? (event._origin || 'vorschlaege') : column;

    const notif = boardData.notifications[event.id];
    const notifHtml = notif
        ? `<div class="kanban-card-notif">${ICON_INFO} Bearbeitet von ${safe(notif.by || 'Unbekannt')}</div>`
        : '';

    const ressourceHtml = event.ressource
        ? `<div class="kanban-card-ressource">${ICON_BUILDING} ${safe(event.ressource)}</div>`
        : '';

    const removeBtn = column === 'festlegen'
        ? `<button class="kanban-card-remove" title="Zurück">×</button>` : '';

    const konfliktBadge = column === 'konflikte'
        ? `<span class="kanban-badge-konflikt">${ICON_WARN} Konflikt</span>` : '';

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

function buildSeriesCard(group, column) {
    const card = document.createElement('div');
    card.className = 'kanban-card kanban-card-serie' + (group.has_konflikt ? ' kanban-card-konflikt' : '');
    card.dataset.id     = group.series_id;
    card.dataset.type   = 'serie';
    card.dataset.origin = column === 'festlegen' ? (group._origin || 'vorschlaege') : column;

    const removeBtn = column === 'festlegen'
        ? `<button class="kanban-card-remove" title="Zurück">×</button>` : '';

    const konfliktBadge = group.has_konflikt
        ? `<span class="kanban-badge-konflikt">${ICON_WARN} Konflikt</span>` : '';

    // Date range
    const sameDay = group.first_start === group.last_start;
    const dateRange = sameDay
        ? fmtDate(group.first_start, group.all_day)
        : `${fmtDate(group.first_start, group.all_day)} – ${fmtDate(group.last_start, group.all_day)}`;

    // Conflicting dates list (only in konflikte column, collapsed by default)
    let konfliktListHtml = '';
    if (column === 'konflikte' && group.konflikt_events?.length) {
        const items = group.konflikt_events.map(ev =>
            `<li class="kanban-serie-konflikt-item" data-id="${safe(ev.id)}">
                ${ICON_WARN} ${fmtDate(ev.start, ev.all_day)}
                <button class="kanban-serie-resolve-btn" data-id="${safe(ev.id)}" title="Diesen Konflikt auflösen">Auflösen</button>
             </li>`
        ).join('');
        konfliktListHtml = `
            <div class="kanban-serie-konflikt-list">
                <div class="kanban-serie-konflikt-header" data-toggle="conflict-list">
                    ${ICON_WARN} ${group.konflikt_events.length} von ${group.count} Terminen haben einen Konflikt
                    <svg class="kanban-toggle-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6l6-6"/></svg>
                </div>
                <ul class="kanban-serie-konflikt-items">${items}</ul>
            </div>`;
    }

    card.innerHTML = `
        <div class="kanban-card-strip" style="background:${group.calendar_color}"></div>
        <div class="kanban-card-body">
            <div class="kanban-card-header">
                <span class="kanban-card-title">${safe(group.title)}</span>
                <span class="kanban-serie-badge">${ICON_REPEAT} ${group.count} Termine</span>
                ${konfliktBadge}
                ${removeBtn}
            </div>
            <div class="kanban-card-time">${dateRange}</div>
            <div class="kanban-card-cal">
                <span class="kanban-dot" style="background:${group.calendar_color}"></span>
                ${safe(group.calendar_title)}
            </div>
            ${konfliktListHtml}
        </div>
    `;

    // Toggle conflict list
    card.querySelector('[data-toggle="conflict-list"]')?.addEventListener('click', (e) => {
        e.stopPropagation();
        const list = card.querySelector('.kanban-serie-konflikt-items');
        const icon = card.querySelector('.kanban-toggle-icon');
        list?.classList.toggle('open');
        icon?.classList.toggle('rotated');
    });

    return card;
}

// ── Render ────────────────────────────────────────────────────────────────────
function renderBoard() {
    const sortV    = document.getElementById('sort-vorschlaege');
    const sortK    = document.getElementById('sort-konflikte');
    const sortF    = document.getElementById('sort-festlegen');
    const dropHint = document.getElementById('drop-hint');

    sortV.innerHTML = '';
    sortK.innerHTML = '';
    sortF.innerHTML = '';

    // ── Vorschläge ────────────────────────────────────────────────────────────
    const groupedV = groupItems(boardData.vorschlaege);
    if (groupedV.length === 0) {
        sortV.innerHTML = '<div class="kanban-empty-hint">Keine Vorschläge</div>';
    } else {
        groupedV.forEach(item => {
            if (item.type === 'serie') {
                const card = buildSeriesCard(item, 'vorschlaege');
                card.addEventListener('click', (e) => {
                    if (e.target.closest('.kanban-card-remove')) return;
                    openSeriesModal(item);
                });
                sortV.appendChild(card);
            } else {
                const card = buildCard(item, 'vorschlaege');
                card.addEventListener('click', () => openEditModal(item));
                sortV.appendChild(card);
            }
        });
    }

    // ── Konflikte ─────────────────────────────────────────────────────────────
    const groupedK = groupItems(boardData.konflikte);
    if (groupedK.length === 0) {
        sortK.innerHTML = '<div class="kanban-empty-hint">Keine Konflikte</div>';
    } else {
        groupedK.forEach(item => {
            if (item.type === 'serie') {
                const card = buildSeriesCard(item, 'konflikte');
                // Wire up individual "Auflösen" buttons
                card.querySelectorAll('.kanban-serie-resolve-btn').forEach(btn => {
                    btn.addEventListener('click', async (e) => {
                        e.stopPropagation();
                        const eid = btn.dataset.id;
                        const ev  = item.events.find(x => x.id === eid);
                        if (ev) await openConflictModal(ev);
                    });
                });
                card.addEventListener('click', (e) => {
                    if (e.target.closest('.kanban-serie-resolve-btn')) return;
                    if (e.target.closest('[data-toggle="conflict-list"]')) return;
                    openSeriesKonfliktModal(item);
                });
                sortK.appendChild(card);
            } else {
                const card = buildCard(item, 'konflikte');
                card.addEventListener('click', () => openConflictModal(item));
                sortK.appendChild(card);
            }
        });
    }

    // ── Festlegen ─────────────────────────────────────────────────────────────
    const stagingGroups = buildStagingGroups();

    if (stagingGroups.length === 0) {
        dropHint.style.display = 'flex';
    } else {
        dropHint.style.display = 'none';
        stagingGroups.forEach(item => {
            let card;
            if (item.type === 'serie') {
                card = buildSeriesCard(item, 'festlegen');
                card.querySelector('.kanban-card-remove')?.addEventListener('click', (e) => {
                    e.stopPropagation();
                    removeFromStaging(item.series_id, 'serie');
                });
                card.addEventListener('click', (e) => {
                    if (e.target.classList.contains('kanban-card-remove')) return;
                    openSeriesModal(item);
                });
            } else {
                card = buildCard(item, 'festlegen');
                card.querySelector('.kanban-card-remove')?.addEventListener('click', (e) => {
                    e.stopPropagation();
                    removeFromStaging(item.id, 'event');
                });
                card.addEventListener('click', (e) => {
                    if (e.target.classList.contains('kanban-card-remove')) return;
                    openEditModal(item);
                });
            }
            sortF.appendChild(card);
        });
    }

    // Update counts
    const totalV = boardData.vorschlaege.length;
    const totalK = boardData.konflikte.length;
    const totalF = stagingIds.length; // individual event count
    document.getElementById('count-vorschlaege').textContent = totalV;
    document.getElementById('count-konflikte').textContent   = totalK;
    document.getElementById('count-festlegen').textContent   = totalF;

    // Save button state
    document.getElementById('kanban-save-btn').disabled = stagingIds.length === 0;
}

function removeFromStaging(id, type) {
    if (type === 'serie') {
        const seriesEvents = boardData.staging.filter(e => e.series_id === id);
        const seriesEventIds = new Set(seriesEvents.map(e => e.id));
        stagingIds = stagingIds.filter(sid => !seriesEventIds.has(sid));
        boardData.staging = boardData.staging.filter(e => e.series_id !== id);
        seriesEvents.forEach(ev => {
            if (ev.status === 'Konflikt') boardData.konflikte.push(ev);
            else boardData.vorschlaege.push(ev);
        });
    } else {
        stagingIds = stagingIds.filter(i => i !== id);
        const ev = boardData.staging.find(e => e.id === id);
        if (ev) {
            boardData.staging = boardData.staging.filter(e => e.id !== id);
            if (ev.status === 'Konflikt') boardData.konflikte.push(ev);
            else boardData.vorschlaege.push(ev);
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
        group:      { name: 'vorschlaege', pull: true, put: false },
        sort:       false,
        animation:  150,
        ghostClass: 'kanban-ghost',
        dragClass:  'kanban-dragging',
        filter:     '.kanban-empty-hint',
    });

    // Festlegen: accepts from Vorschläge only
    Sortable.create(document.getElementById('sort-festlegen'), {
        group:      { name: 'festlegen', pull: false, put: ['vorschlaege'] },
        sort:       true,
        animation:  150,
        ghostClass: 'kanban-ghost',
        dragClass:  'kanban-dragging',
        onAdd(evt) {
            const id   = evt.item.dataset.id;
            const type = evt.item.dataset.type || 'event';
            if (!id) return;

            if (type === 'serie') {
                // Move all individual events of this series from vorschlaege to staging
                const seriesEvents = boardData.vorschlaege.filter(e => e.series_id === id);
                if (!seriesEvents.length) return;
                boardData.vorschlaege = boardData.vorschlaege.filter(e => e.series_id !== id);
                seriesEvents.forEach(ev => {
                    ev._origin = 'vorschlaege';
                    boardData.staging.push(ev);
                    if (!stagingIds.includes(ev.id)) stagingIds.push(ev.id);
                });
            } else {
                const ev = boardData.vorschlaege.find(e => e.id === id);
                if (!ev) return;
                boardData.vorschlaege = boardData.vorschlaege.filter(e => e.id !== id);
                ev._origin = 'vorschlaege';
                boardData.staging.push(ev);
                if (!stagingIds.includes(id)) stagingIds.push(id);
            }
            renderBoard();
            debouncedSaveState();
        },
    });
}

// ── Mini-Monatskalender ───────────────────────────────────────────────────────
function buildMiniMonthCalendar(refDateStr, highlightDates = []) {
    const ref = new Date(refDateStr);
    if (isNaN(ref)) return '';
    const year = ref.getFullYear(), month = ref.getMonth();
    const MONTHS = ['Januar','Februar','März','April','Mai','Juni',
                    'Juli','August','September','Oktober','November','Dezember'];
    const DAYS   = ['Mo','Di','Mi','Do','Fr','Sa','So'];

    const hSet = new Set(highlightDates.map(d => {
        const dt = new Date(d);
        return isNaN(dt) ? null : `${dt.getFullYear()}-${dt.getMonth()}-${dt.getDate()}`;
    }).filter(Boolean));

    const firstDow    = (new Date(year, month, 1).getDay() + 6) % 7; // Mon=0
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const today       = new Date();

    let html = `<div class="kanban-mini-cal">
        <div class="kanban-mini-cal-title">${MONTHS[month]} ${year}</div>
        <div class="kanban-mini-cal-grid">`;
    DAYS.forEach(d => { html += `<div class="kanban-mini-cal-dh">${d}</div>`; });
    for (let i = 0; i < firstDow; i++) html += `<div class="kanban-mini-cal-day"></div>`;
    for (let d = 1; d <= daysInMonth; d++) {
        const isToday = today.getFullYear() === year && today.getMonth() === month && today.getDate() === d;
        const isEvent = hSet.has(`${year}-${month}-${d}`);
        let cls = 'kanban-mini-cal-day';
        if (isToday) cls += ' is-today';
        if (isEvent) cls += ' is-event';
        html += `<div class="${cls}">${d}</div>`;
    }
    return html + '</div></div>';
}

// ── Modals ────────────────────────────────────────────────────────────────────
function openEditModal(event) {
    const overlay = document.getElementById('conflict-overlay');
    const wide = window.innerWidth >= 860;

    const calPanel = wide && event.start
        ? `<div class="kanban-modal-cal-panel">
               ${buildMiniMonthCalendar(event.start, [event.start])}
           </div>`
        : '';

    if (wide && event.start) {
        overlay.innerHTML = `
            <div class="kanban-modal-box kanban-modal-with-cal">
                <div class="kanban-modal-header">
                    <h3>Termin bearbeiten</h3>
                    <button class="kanban-modal-close">&times;</button>
                </div>
                <div class="kanban-modal-split">
                    <div class="kanban-modal-left">
                        <form class="kanban-edit-form" style="padding:16px 18px">
                            ${buildEditFormFields(event)}
                            <div class="kanban-modal-footer" style="border-top:none;padding:8px 0 0">
                                <button type="submit" class="btn btn-primary">Speichern</button>
                            </div>
                        </form>
                    </div>
                    ${calPanel}
                </div>
            </div>`;
    } else {
        overlay.innerHTML = buildEditModalHTML(event);
    }
    overlay.style.display = 'flex';

    const form     = overlay.querySelector('.kanban-edit-form');
    const closeBtn = overlay.querySelector('.kanban-modal-close');

    closeBtn.onclick = () => { overlay.style.display = 'none'; };
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.style.display = 'none'; }, { once: true });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const data      = getFormData(form, event);
        const submitBtn = form.querySelector('[type=submit]');
        submitBtn.disabled = true;
        try {
            await API.post('diakronos.kronos.api.kanban_api.resolve_conflict', {
                element_id: event.id, action: 'vorschlag', ...data,
            });
            overlay.style.display = 'none';
            await reloadBoard();
        } catch(ex) {
            console.error(ex);
            submitBtn.disabled = false;
        }
    });
}

async function openConflictModal(event) {
    const overlay = document.getElementById('conflict-overlay');
    overlay.innerHTML = `<div class="kanban-modal-loading">Lade Konfliktdaten…</div>`;
    overlay.style.display = 'flex';

    let partner = null;
    try {
        partner = await API.post('diakronos.kronos.api.kanban_api.get_conflict_partner', { element_id: event.id });
    } catch(e) { /* no partner */ }

    overlay.innerHTML = buildConflictModalHTML(event, partner);

    const form = overlay.querySelector('.kanban-edit-form');

    overlay.querySelector('.kanban-modal-close').onclick = () => { overlay.style.display = 'none'; };
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.style.display = 'none'; }, { once: true });

    overlay.querySelector('#btn-ignore').onclick = async () => {
        const data = getFormData(form, event);
        overlay.querySelector('#btn-ignore').disabled = true;
        try {
            await API.post('diakronos.kronos.api.kanban_api.resolve_conflict', {
                element_id: event.id, action: 'ignore', ...data,
            });
            await reloadBoard();
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

    overlay.querySelector('#btn-festlegen').onclick = async () => {
        const data = getFormData(form, event);
        overlay.querySelector('#btn-festlegen').disabled = true;
        try {
            await API.post('diakronos.kronos.api.kanban_api.resolve_conflict', {
                element_id: event.id, action: 'festlegen', ...data,
            });
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

function openSeriesModal(group) {
    const overlay = document.getElementById('conflict-overlay');
    const wide = window.innerWidth >= 860;
    const countLabel = group.count === 1 ? '1 Termin' : `${group.count} Termine`;
    const dateRange = group.first_start === group.last_start
        ? fmtDate(group.first_start, group.all_day)
        : `${fmtDate(group.first_start, group.all_day)} – ${fmtDate(group.last_start, group.all_day)}`;

    const calPanel = wide
        ? `<div class="kanban-modal-cal-panel">
               ${buildMiniMonthCalendar(group.first_start, (group.events || []).map(e => e.start))}
           </div>`
        : '';

    const boxClass = wide ? 'kanban-modal-with-cal' : 'kanban-modal-edit';

    function wrapBody(innerHtml) {
        return wide
            ? `<div class="kanban-modal-split">
                   <div class="kanban-modal-left"><div class="kanban-serie-modal-body">${innerHtml}</div></div>
                   ${calPanel}
               </div>`
            : `<div class="kanban-serie-modal-body">${innerHtml}</div>`;
    }

    const infoHtml = `
        <div class="kanban-serie-info-row">${ICON_CALENDAR} ${safe(dateRange)}</div>
        <div class="kanban-serie-info-row">
            <span class="kanban-dot" style="background:${group.calendar_color}"></span>
            ${safe(group.calendar_title)}
        </div>`;

    function renderView() {
        overlay.querySelector('.kanban-modal-dynamic-body').innerHTML = wrapBody(infoHtml);
        overlay.querySelector('.kanban-modal-dynamic-footer').innerHTML = `
            <button class="btn btn-danger-outline" id="btn-serie-delete">Löschen</button>
            <div style="flex:1"></div>
            <button class="btn btn-secondary" id="btn-serie-close">Schließen</button>
            <button class="btn btn-primary" id="btn-serie-edit">Bearbeiten</button>`;
        bindViewButtons();
    }

    function renderEdit() {
        overlay.querySelector('.kanban-modal-dynamic-body').innerHTML = wrapBody(`
            <div class="kanban-form-group" style="padding:16px 18px 0">
                <label>Titel (alle ${group.count} Termine)</label>
                <input type="text" id="serie-edit-title" value="${safe(group.title)}" class="kanban-input" required>
            </div>`);
        overlay.querySelector('.kanban-modal-dynamic-footer').innerHTML = `
            <button class="btn btn-danger-outline" id="btn-serie-delete">Löschen</button>
            <div style="flex:1"></div>
            <button class="btn btn-secondary" id="btn-serie-cancel">Abbrechen</button>
            <button class="btn btn-primary" id="btn-serie-save">Speichern</button>`;
        overlay.querySelector('#btn-serie-cancel').onclick = renderView;
        overlay.querySelector('#btn-serie-delete').onclick = renderConfirmDelete;
        overlay.querySelector('#btn-serie-save').onclick   = async () => {
            const title = overlay.querySelector('#serie-edit-title')?.value?.trim();
            if (!title) return;
            const btn = overlay.querySelector('#btn-serie-save');
            btn.disabled = true;
            try {
                await API.post('diakronos.kronos.api.series.update_series_batch_fast', {
                    series_id: group.series_id,
                    updates: { element_name: title }
                });
                overlay.style.display = 'none';
                await reloadBoard();
            } catch(e) {
                console.error(e);
                btn.disabled = false;
            }
        };
    }

    function renderConfirmDelete() {
        overlay.querySelector('.kanban-modal-dynamic-body').innerHTML = wrapBody(`
            <div class="kanban-serie-delete-confirm">
                <p>Sollen wirklich alle <strong>${group.count} Termine</strong> der Serie <strong>${safe(group.title)}</strong> unwiderruflich gelöscht werden?</p>
            </div>`);
        overlay.querySelector('.kanban-modal-dynamic-footer').innerHTML = `
            <button class="btn btn-secondary" id="btn-serie-cancel">Abbrechen</button>
            <div style="flex:1"></div>
            <button class="btn btn-danger" id="btn-serie-confirm-delete">Alle löschen</button>`;
        overlay.querySelector('#btn-serie-cancel').onclick = renderView;
        overlay.querySelector('#btn-serie-confirm-delete').onclick = async () => {
            const btn = overlay.querySelector('#btn-serie-confirm-delete');
            btn.disabled = true;
            try {
                await API.post('diakronos.kronos.api.series.delete_series_batch_fast', {
                    series_id: group.series_id
                });
                overlay.style.display = 'none';
                await reloadBoard();
            } catch(e) {
                console.error(e);
                btn.disabled = false;
            }
        };
    }

    function bindViewButtons() {
        overlay.querySelector('#btn-serie-close').onclick  = () => { overlay.style.display = 'none'; };
        overlay.querySelector('#btn-serie-edit').onclick   = renderEdit;
        overlay.querySelector('#btn-serie-delete').onclick = renderConfirmDelete;
    }

    overlay.innerHTML = `
        <div class="kanban-modal-box ${boxClass}">
            <div class="kanban-modal-header">
                <div class="kanban-modal-title-row">
                    <h3>${safe(group.title)}</h3>
                    <span class="kanban-serie-badge-lg">${ICON_REPEAT} ${countLabel}</span>
                </div>
                <button class="kanban-modal-close">&times;</button>
            </div>
            <div class="kanban-modal-dynamic-body"></div>
            <div class="kanban-modal-footer kanban-modal-dynamic-footer"></div>
        </div>
    `;
    overlay.style.display = 'flex';
    overlay.querySelector('.kanban-modal-close').onclick = () => { overlay.style.display = 'none'; };
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.style.display = 'none'; }, { once: true });

    renderView();
}

function openSeriesKonfliktModal(group) {
    const overlay = document.getElementById('conflict-overlay');

    const itemsHtml = (group.konflikt_events || []).map(ev => `
        <div class="kanban-serie-conflict-row">
            <div class="kanban-serie-conflict-date">${ICON_WARN} ${fmtDate(ev.start, ev.all_day)}</div>
            <button class="btn btn-sm btn-secondary kanban-open-conflict-btn" data-id="${safe(ev.id)}">Auflösen</button>
        </div>
    `).join('');

    overlay.innerHTML = `
        <div class="kanban-modal-box kanban-modal-conflict">
            <div class="kanban-modal-header">
                <div class="kanban-modal-title-row">
                    <h3>${safe(group.title)}</h3>
                    <span class="kanban-badge-konflikt-lg">${ICON_WARN} ${group.konflikt_events?.length || 0} Konflikte</span>
                </div>
                <button class="kanban-modal-close">&times;</button>
            </div>
            <div class="kanban-serie-modal-body">
                <p class="kanban-serie-conflict-intro">
                    ${group.konflikt_events?.length} von ${group.count} Serienterminen haben eine Doppelbuchung.
                    Löse jeden Konflikt einzeln auf.
                </p>
                <div class="kanban-serie-conflict-list">${itemsHtml}</div>
            </div>
            <div class="kanban-modal-footer">
                <button class="btn btn-secondary" id="btn-serie-close">Schließen</button>
            </div>
        </div>
    `;
    overlay.style.display = 'flex';

    overlay.querySelector('.kanban-modal-close').onclick = () => { overlay.style.display = 'none'; };
    overlay.querySelector('#btn-serie-close').onclick    = () => { overlay.style.display = 'none'; };
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.style.display = 'none'; }, { once: true });

    // Wire "Auflösen" buttons for individual conflict events
    overlay.querySelectorAll('.kanban-open-conflict-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            overlay.style.display = 'none';
            const eid = btn.dataset.id;
            const ev  = (group.events || []).find(x => x.id === eid)
                     || boardData.konflikte.find(x => x.id === eid);
            if (ev) await openConflictModal(ev);
        });
    });
}

// ── Form helpers ──────────────────────────────────────────────────────────────
function getFormData(form, event) {
    const fd     = new FormData(form);
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

function buildEditModalHTML(event) {
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
            <div class="kanban-conflict-partner-header">${ICON_WARN_LG} Überschneidung mit</div>
            <div class="kanban-partner-card">
                <div class="kanban-partner-title">${safe(partner.title)}</div>
                <div class="kanban-partner-time">${ICON_CALENDAR} ${fmtDate(partner.start, partner.all_day)}</div>
                <div class="kanban-partner-cal">${ICON_CLOCK} ${safe(partner.calendar)}</div>
                ${partner.ressource ? `<div class="kanban-partner-ressource">${ICON_BUILDING_MD} ${safe(partner.ressource)}</div>` : ''}
                <p class="kanban-partner-hint">Passe Zeit oder Raum an um den Konflikt zu vermeiden, oder ignoriere ihn bewusst.</p>
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
                    <span class="kanban-badge-konflikt-lg">${ICON_WARN} Konflikt</span>
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
                <button class="btn btn-secondary" id="btn-ignore">${ICON_EYE_OFF} Konflikt ignorieren</button>
                <div style="flex:1"></div>
                <button class="btn btn-warning" id="btn-vorschlag">${ICON_CLOCK} Vorschlagen</button>
                <button class="btn btn-success" id="btn-festlegen">${ICON_CHECK} Festlegen</button>
            </div>
        </div>
    `;
}

// ── Finalize ──────────────────────────────────────────────────────────────────
async function finalizeStaging() {
    const btn = document.getElementById('kanban-save-btn');
    btn.disabled = true;
    btn.textContent = '…';
    try {
        await API.post('diakronos.kronos.api.kanban_api.finalize_staged_events', {
            event_ids: stagingIds
        });
        stagingIds = [];
        await reloadBoard();
    } catch(e) {
        console.error('Finalisierung fehlgeschlagen', e);
        btn.disabled = false;
        btn.innerHTML = `${ICON_FLOPPY} Alle festlegen`;
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
    boardData  = await API.post('diakronos.kronos.api.kanban_api.get_kanban_board_data');
    stagingIds = stagingIds.filter(id => boardData.staging.some(e => e.id === id));
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
        img.alt    = fullname;
        img.onerror = () => { avatar.innerHTML = ''; avatar.textContent = initial; };
        img.src    = userImage;
        avatar.appendChild(img);
    } else {
        avatar.textContent = initial;
    }

    const dropdown = document.createElement('div');
    dropdown.className = 'kanban-dropdown';
    dropdown.innerHTML = `
        <a class="kanban-dropdown-item" href="/kronos/calendar">${ICON_CALENDAR_LG} Zurück zum Kalender</a>
        <button class="kanban-dropdown-item kanban-dropdown-search">${ICON_SEARCH_SM} Suche</button>
        <div class="kanban-dropdown-divider"></div>
        <button class="kanban-dropdown-item kanban-dropdown-logout">${ICON_LOGOUT} Abmelden</button>
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

    dropdown.querySelector('.kanban-dropdown-search').addEventListener('click', () => {
        dropdown.classList.remove('open');
        document.dispatchEvent(new CustomEvent('kronosSearch:open'));
    });

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
        script.src    = 'https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js';
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    buildAvatarHeader();

    try { await loadSortableJS(); }
    catch(e) { console.error('SortableJS konnte nicht geladen werden', e); }

    try {
        const r = await API.post('diakronos.kronos.api.ressource_api.get_ressources');
        ressources = (r || []).map(x => ({ id: x.id, title: x.title }));
    } catch(e) { /* no ressources */ }

    try {
        boardData  = await API.post('diakronos.kronos.api.kanban_api.get_kanban_board_data');
        stagingIds = boardData.staging.map(e => e.id);
    } catch(e) {
        console.error('Board-Daten konnten nicht geladen werden', e);
        boardData = { vorschlaege: [], konflikte: [], staging: [], notifications: {} };
    }

    renderBoard();
    initSortable();

    document.getElementById('kanban-save-btn').addEventListener('click', finalizeStaging);

    // ── Suche ─────────────────────────────────────────────────────────────────
    initKronosSearch((event) => {
        const date = (event.start || '').slice(0, 10);
        window.location.href = `/kronos/calendar${date ? '?date=' + date : ''}`;
    });

    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
            e.preventDefault();
            document.dispatchEvent(new CustomEvent('kronosSearch:open'));
        }
    }, { capture: true });
});
