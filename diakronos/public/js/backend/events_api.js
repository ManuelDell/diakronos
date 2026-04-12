// backend/events_api.js – Event CRUD über native fetch() API
// Kein frappe.call / frappe.show_alert / window – reine fetch-Aufrufe

/**
 * Gibt einen lokalen Datetime-String zurück (ohne Timezone-Suffix).
 * Frappe speichert naive Datetimes – toISOString() würde UTC senden und
 * beim Strippen des Timezone-Offsets die Zeit verschieben.
 * Format: "YYYY-MM-DD HH:MM:SS"
 */
function toLocalDateTimeString(date) {
    const pad = n => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
           `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

class KronosEvents {

    /**
     * Aktualisiert ein Event nach Drag & Drop oder Resize.
     * @param {Object} event        – EventCalendar event object
     * @param {Object} calendarRef  – KronosCalendar-Instanz (für refetchEvents)
     */
    static async updateEvent(event, calendarRef, forceSeriesDetach = false) {
        if (!event?.id) {
            console.error('❌ Event.id erforderlich');
            return;
        }
        if (!event.start || !event.end) {
            console.error('❌ Start- und Enddatum erforderlich');
            return;
        }

        const props = event.extendedProps || {};
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

        try {
            const response = await fetch('/api/method/diakronos.kronos.api.event_crud.save_event', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-Frappe-CSRF-Token': csrfToken
                },
                body: JSON.stringify({
                    name:             event.id,
                    element_name:     event.title,
                    element_start:    toLocalDateTimeString(event.start),
                    element_end:      toLocalDateTimeString(event.end),
                    element_calendar: props.element_calendar || '',
                    all_day:          event.allDay || false,
                    description:      props.description || '',
                    element_category: props.element_category || '',
                    status:           props.status || 'Festgelegt',
                    series_id:        forceSeriesDetach ? '' : (props.series_id || '')
                })
            });

            if (!response.ok) throw new Error(await response.text());

            const result = await response.json();
            if (result.message?.success) {
                calendarRef?.refetchEvents();
            } else {
                console.error('❌ Update fehlgeschlagen:', result.exc);
            }
        } catch (err) {
            console.error('❌ Update Fehler:', err);
        }
    }

    /**
     * Erstellt ein neues Event.
     * @param {string} title
     * @param {Date|string} start
     * @param {Date|string} end
     * @param {Object} calendarRef – KronosCalendar-Instanz (für refetchEvents)
     */
    static async createEvent(title, start, end, element_calendar, calendarRef, extraFields = {}) {
        if (!title?.trim()) {
            console.error('❌ Titel erforderlich');
            return;
        }
        if (!start) {
            console.error('❌ Startdatum erforderlich');
            return;
        }
        if (!element_calendar) {
            console.error('❌ Kalender erforderlich');
            return;
        }

        const startStr = start instanceof Date ? toLocalDateTimeString(start) : start;
        const endStr   = end   instanceof Date ? toLocalDateTimeString(end)   : (end || startStr);
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

        try {
            const response = await fetch('/api/method/diakronos.kronos.api.event_crud.create_event', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-Frappe-CSRF-Token': csrfToken
                },
                body: JSON.stringify({
                    element_name:     title,
                    element_calendar: element_calendar,
                    element_start:    startStr,
                    element_end:      endStr,
                    all_day:          extraFields.all_day || false,
                    description:      extraFields.description || '',
                    element_category: extraFields.element_category || '',
                    status:           extraFields.status || 'Festgelegt'
                })
            });

            if (!response.ok) throw new Error(await response.text());

            const result = await response.json();
            if (result.message?.id) {
                calendarRef?.refetchEvents();
            }
        } catch (err) {
            console.error('❌ Create Fehler:', err);
        }
    }

    /**
     * Löscht ein Event.
     * @param {string} eventId
     * @param {Object} calendarRef – KronosCalendar-Instanz (für refetchEvents)
     */
    static async deleteEvent(eventId, calendarRef) {
        if (!eventId) {
            console.error('❌ Event-ID erforderlich');
            return;
        }
        if (!window.confirm('⚠️ Termin wirklich löschen?')) return;

        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

        try {
            const response = await fetch(`/api/resource/Element/${eventId}`, {
                method: 'DELETE',
                headers: { 'X-Frappe-CSRF-Token': csrfToken }
            });

            if (!response.ok) throw new Error(await response.text());

            calendarRef?.refetchEvents();
        } catch (err) {
            console.error('❌ Delete Fehler:', err);
        }
    }
}

export { KronosEvents };
