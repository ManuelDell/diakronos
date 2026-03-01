// modal_view.js – event_detail_display (bereinigt)

class DiakronosViewModal {
    static show(element) {
        if (!element?.name) {
            console.warn('⚠️ Kein valides Element übergeben');
            return;
        }

        // Kompakte Zeit-Formatierung (wie zuletzt besprochen)
        function formatEventTime(startStr, endStr = null, allDay = false) {
            if (!startStr) return '—';

            const start = new Date(startStr);
            const end = endStr ? new Date(endStr) : null;

            const formatDay = (date) => {
                return date.toLocaleDateString('de-DE', {
                    weekday: 'short',
                    day: 'numeric',
                    month: 'short'
                }).replace(/\.$/, ''); // Entfernt letzten Punkt
            };

            const formatTime = (date) => {
                return date.toLocaleTimeString('de-DE', {
                    hour: '2-digit',
                    minute: '2-digit'
                });
            };

            if (allDay) {
                if (end && start.toDateString() !== end.toDateString()) {
                    return `${formatDay(start)} – ${formatDay(end)}`;
                }
                return formatDay(start);
            }

            const startDay = formatDay(start);
            const startTime = formatTime(start);

            if (!end || start.toDateString() === end.toDateString()) {
                const endTime = formatTime(end);
                return `${startDay} ${startTime} – ${endTime}`;
            } else {
                const endDay = formatDay(end);
                const endTime = formatTime(end);
                return `${startDay} ${startTime} – ${endDay} ${endTime}`;
            }
        }

        const modalHTML = `
            <div class="diakronos-modal fade show" tabindex="-1" role="dialog" aria-labelledby="modalLabel" aria-hidden="true">
                <div class="diakronos-modal-dialog modal-dialog-centered modal-md">
                    <div class="diakronos-modal-content">
                        <!-- Farbige Leiste oben – Kalenderfarbe -->
                        <div class="diakronos-color-bar" style="background-color: ${element.element_color || 'var(--primary)'};"></div>
                        <div class="diakronos-modal-header">
                            <h5 class="modal-title" id="modalLabel">${element.element_name || 'Termin'}</h5>
                            <button type="button" class="diakronos-close-btn" aria-label="Schließen">×</button>
                        </div>
                        <div class="diakronos-modal-body">
                            <div class="event-time">${formatEventTime(element.element_start, element.element_end, element.all_day)}</div>
                            <dl class="diakronos-dl">
                                <dt>Kalender</dt><dd>${element.element_calendar || '—'}</dd>
                                <dt>Kategorie</dt><dd>${element.event_category_name || '—'}</dd>
                                <dt>Beschreibung</dt><dd class="description">${element.description?.replace(/\n/g, '<br>') || '—'}</dd>
                            </dl>
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
    }
}

export { DiakronosViewModal };
