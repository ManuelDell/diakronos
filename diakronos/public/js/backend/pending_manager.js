// backend/pending_manager.js – Session-Zwischenspeicher für Vorschläge
// Events werden sofort als "Vorschlag" in die DB geschrieben.
// PendingManager merkt sich welche IDs in dieser Session neu erstellt wurden.

const _pending = []; // Array von { id, calendarName, title }

export const PendingManager = {
    add(id, calendarName, title) {
        if (!_pending.find(e => e.id === id)) {
            _pending.push({ id, calendarName, title: title || 'Termin' });
            _dispatch();
        }
    },

    remove(id) {
        const i = _pending.findIndex(e => e.id === id);
        if (i !== -1) {
            _pending.splice(i, 1);
            _dispatch();
        }
    },

    clear() {
        _pending.length = 0;
        _dispatch();
    },

    getAll()  { return [..._pending]; },
    count()   { return _pending.length; },

    /** Gruppiert nach calendarName → { calendarName: [{ id, title }] } */
    grouped() {
        const map = {};
        for (const e of _pending) {
            if (!map[e.calendarName]) map[e.calendarName] = [];
            map[e.calendarName].push({ id: e.id, title: e.title });
        }
        return map;
    },
};

function _dispatch() {
    document.dispatchEvent(new CustomEvent('pending:changed', {
        detail: { count: _pending.length }
    }));
}
