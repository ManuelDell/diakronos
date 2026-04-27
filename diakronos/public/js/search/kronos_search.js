// search/kronos_search.js – Kronos Terminsuche Overlay

import { ICON_SEARCH, ICON_CLOSE, ICON_CALENDAR as ICON_CAL, ICON_REPEAT } from '../shared/icons.js';

function fmtDate(str, allDay) {
    if (!str) return '';
    const d = new Date(str);
    if (isNaN(d)) return str;
    const opts = { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' };
    if (allDay) return d.toLocaleDateString('de-DE', opts);
    return d.toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit' })
         + ' · ' + d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
}

export function initKronosSearch(onNavigate) {
    // Overlay einmalig bauen
    const overlay = document.createElement('div');
    overlay.id = 'kronos-search-overlay';
    overlay.hidden = true;
    overlay.innerHTML = `
        <div class="kronos-search-box">
            <div class="kronos-search-input-row">
                <span class="kronos-search-icon">${ICON_SEARCH}</span>
                <input id="kronos-search-input"
                       type="search"
                       placeholder="Termin suchen…"
                       autocomplete="off"
                       spellcheck="false" />
                <button class="kronos-search-close-btn" aria-label="Schließen">${ICON_CLOSE}</button>
            </div>
            <ul class="kronos-search-results" hidden></ul>
        </div>
    `;
    document.body.appendChild(overlay);

    const input     = overlay.querySelector('#kronos-search-input');
    const resultsList = overlay.querySelector('.kronos-search-results');
    const closeBtn  = overlay.querySelector('.kronos-search-close-btn');
    let activeIndex = -1;

    // ── Open / Close ──────────────────────────────────────────────────────────
    function open() {
        overlay.hidden = false;
        overlay.classList.remove('has-results');
        resultsList.hidden = true;
        resultsList.innerHTML = '';
        input.value = '';
        activeIndex = -1;
        requestAnimationFrame(() => input.focus());
    }

    function close() {
        overlay.hidden = true;
        overlay.classList.remove('has-results');
    }

    // ── Search ────────────────────────────────────────────────────────────────
    async function doSearch() {
        const q = input.value.trim();
        if (q.length < 2) {
            resultsList.hidden = true;
            overlay.classList.remove('has-results');
            return;
        }

        resultsList.innerHTML = `<li class="kronos-search-empty">Suche…</li>`;
        resultsList.hidden = false;
        overlay.classList.add('has-results');

        try {
            const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
            const res  = await fetch(
                `/api/method/diakronos.kronos.api.search_api.search_events?query=${encodeURIComponent(q)}&limit=15`,
                { headers: { 'X-Frappe-CSRF-Token': csrf } }
            );
            if (!res.ok) throw new Error(res.status);
            const { message: events } = await res.json();
            renderResults(events || []);
        } catch (e) {
            resultsList.innerHTML = `<li class="kronos-search-empty">Fehler bei der Suche.</li>`;
        }
    }

    function renderResults(events) {
        activeIndex = -1;
        if (!events.length) {
            resultsList.innerHTML = `<li class="kronos-search-empty">Keine Termine gefunden.</li>`;
            return;
        }
        resultsList.innerHTML = '';
        events.forEach((ev, i) => {
            const li = document.createElement('li');
            li.className = 'kronos-search-result';
            li.dataset.index = i;

            const seriesBadge = ev.is_series && ev.series_count > 1
                ? `<span class="kronos-result-serie">${ICON_REPEAT} ${ev.series_count} Termine</span>`
                : '';

            li.innerHTML = `
                <span class="kronos-result-dot" style="background:${ev.calendar_color || 'var(--primary)'}"></span>
                <span class="kronos-result-info">
                    <span class="kronos-result-title">${escHtml(ev.title)} ${seriesBadge}</span>
                    <span class="kronos-result-meta">${ICON_CAL} ${fmtDate(ev.start, ev.all_day)} · ${escHtml(ev.calendar_title || '')}</span>
                </span>
            `;
            li.addEventListener('click', () => selectResult(ev));
            resultsList.appendChild(li);
        });
    }

    function selectResult(ev) {
        close();
        onNavigate(ev);
    }

    function setActive(idx) {
        const items = resultsList.querySelectorAll('.kronos-search-result');
        items.forEach(el => el.classList.remove('is-active'));
        if (idx >= 0 && idx < items.length) {
            activeIndex = idx;
            items[idx].classList.add('is-active');
            items[idx].scrollIntoView({ block: 'nearest' });
        } else {
            activeIndex = -1;
        }
    }

    // ── Event Listeners ───────────────────────────────────────────────────────
    closeBtn.addEventListener('click', close);

    // Klick auf Backdrop schließt
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) close();
    });

    // Tastatur
    input.addEventListener('keydown', (e) => {
        const items = resultsList.querySelectorAll('.kronos-search-result');
        if (e.key === 'Escape') { close(); return; }
        if (e.key === 'Enter') {
            e.preventDefault();
            if (activeIndex >= 0 && items[activeIndex]) {
                items[activeIndex].click();
            } else {
                doSearch();
            }
            return;
        }
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setActive(Math.min(activeIndex + 1, items.length - 1));
            return;
        }
        if (e.key === 'ArrowUp') {
            e.preventDefault();
            setActive(Math.max(activeIndex - 1, -1));
        }
    });

    // Global Esc schließt auch wenn Input keinen Fokus hat
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !overlay.hidden) close();
    });

    // Auf Open-Event hören (von Dropdown / Ctrl+F)
    document.addEventListener('kronosSearch:open', open);
}

function escHtml(s) {
    return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
