// modal_day_events.js – day_events_list_modal

import { kronosCalendar } from '../builder/kronos_calendar.js';
import { DiakronosViewModal } from './modal_view.js';

class DiakronosDayEventsModal {
    static show(dateStr) {
        if (!dateStr) return;

        if (!kronosCalendar?.calendar) {
            console.warn('⚠️ Kalender nicht verfügbar');
            return;
        }

        const cal = kronosCalendar.calendar;
        const allEvents = cal.getEvents();

        // Ganztages- und normale Events für den Tag filtern
        const dayStart = new Date(dateStr);
        dayStart.setHours(0, 0, 0, 0);
        const dayEnd = new Date(dayStart);
        dayEnd.setDate(dayEnd.getDate() + 1);

        const dayEvents = allEvents.filter(event => {
            const start = new Date(event.start);
            const end = event.end ? new Date(event.end) : null;

            // Ganztägig: Wenn allDay true oder Start/End innerhalb des Tages
            if (event.allDay) {
                return start < dayEnd && (!end || end > dayStart);
            }

            // Normale Events
            return start >= dayStart && start < dayEnd;
        });

        // Sortieren: Ganztägig zuerst, dann nach Startzeit
        dayEvents.sort((a, b) => {
            if (a.allDay && !b.allDay) return -1;
            if (!a.allDay && b.allDay) return 1;
            return new Date(a.start) - new Date(b.start);
        });

        const modalHTML = `
            <div class="diakronos-modal fade show" tabindex="-1" role="dialog" aria-labelledby="modalLabel" aria-hidden="true">
                <div class="diakronos-modal-dialog modal-dialog-centered modal-md">
                    <div class="diakronos-modal-content">
                        <div class="diakronos-modal-header">
                            <h5 class="modal-title" id="modalLabel">Termine am ${formatDay(dateStr)}</h5>
                            <button type="button" class="diakronos-close-btn" aria-label="Schließen">×</button>
                        </div>
                        <div class="diakronos-modal-body">
                            ${dayEvents.length === 0 ? '<p>Keine Termine an diesem Tag.</p>' : ''}
                            <ul class="diakronos-events-list">
                                ${dayEvents.map(event => `
                                    <li class="event-item" data-event-id="${event.id}" style="border-left: 4px solid ${event.backgroundColor || 'var(--primary)'}; cursor: pointer;">
                                        <div class="event-title">${event.title || 'Termin'}</div>
                                        <div class="event-time">
                                            ${event.allDay ? 'Ganztägig' : formatEventTime(event.startStr, event.endStr, event.allDay)}
                                        </div>
                                    </li>
                                `).join('')}
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);

        const modal = document.querySelector('.diakronos-modal:last-child');
        setTimeout(() => modal.classList.add('show'), 10);

        // Schließen-Logik
        const closeBtn = modal.querySelector('.diakronos-close-btn');
        closeBtn.onclick = () => modal.remove();

        modal.onclick = (e) => {
            if (e.target === modal) modal.remove();
        };

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') modal.remove();
        }, { once: true });

        // Klick auf Event-Item: View-Modal öffnen und Tages-Modal schließen
        modal.querySelectorAll('.event-item').forEach(item => {
            item.addEventListener('click', () => {
                const eventId = item.dataset.eventId;
                const selectedEvent = dayEvents.find(ev => ev.id === eventId);
                
                if (selectedEvent) {
                    // Verhindert das Aufrufen, falls DiakronosViewModal z.B. noch nicht geladen sein sollte
                    if (typeof DiakronosViewModal !== 'undefined') {
                        // extendedProps enthält in der Regel die Rohdaten des Frappe-Dokuments
                        DiakronosViewModal.show(selectedEvent.extendedProps);
                    } else {
                        console.warn('⚠️ DiakronosViewModal nicht verfügbar');
                    }
                }
                modal.remove();
            });
        });
    }
}

// Hilfsfunktion für Datum (wie bisher)
function formatDay(dtStr) {
    const d = new Date(dtStr);
    return d.toLocaleDateString('de-DE', { weekday: 'long', day: 'numeric', month: 'long' });
}

// Deine kompakte Zeit-Formatierung (aus vorher)
function formatEventTime(startStr, endStr = null, allDay = false) {
    if (!startStr) return '—';

    const start = new Date(startStr);
    const end = endStr ? new Date(endStr) : null;

    const formatDay = (date) => {
        if (!date) return '';
        return date.toLocaleDateString('de-DE', {
            weekday: 'short',
            day: 'numeric',
            month: 'short'
        }).replace(/\.$/, ''); // Do. 19. Feb.
    };

    const formatTime = (date) => {
        if (!date) return '';
        return date.toLocaleTimeString('de-DE', {
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    if (allDay) {
        // Ganztägig: nur Datum(e)
        if (end && start.toDateString() !== end.toDateString()) {
            return `${formatDay(start)} – ${formatDay(end)}`;
        }
        return `${formatDay(start)} (ganztägig)`;
    }

    // Mit Uhrzeit
    const startDay = formatDay(start);
    const startTime = formatTime(start);

    if (!end || start.toDateString() === end.toDateString()) {
        // Gleicher Tag
        const endTime = formatTime(end) || 'offen';
        return `${startDay} ${startTime} – ${endTime}`;
    } else {
        // Mehrere Tage
        const endDay = formatDay(end);
        const endTime = formatTime(end) || 'offen';
        return `${startDay} ${startTime} – ${endDay} ${endTime}`;
    }
}

export { DiakronosDayEventsModal };
