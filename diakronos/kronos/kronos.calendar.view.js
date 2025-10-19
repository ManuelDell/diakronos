// kronos_calendar_view.js - Custom Calendar Widget
frappe.views.KronosCalendarView = class KronosCalendarView extends frappe.views.ListView {
    setup_defaults() {
        super.setup_defaults();
        this.page_title = __('Kronos Calendar');
    }

    setup_view() {
        this.setup_calendar_toolbar();
        this.setup_calendar_widget();
        this.setup_sidebar_calendars();
    }

    setup_calendar_widget() {
        // Integration mit Frappe's Calendar Widget
        this.calendar = new frappe.widget.CalendarWidget({
            parent: this.$result,
            doctype: "Calendar Event",
            get_events_method: "diakronos.kronos.api.get_calendar_events",
            filters: this.get_calendar_filters(),
            options: {
                header: {
                    left: 'prev,next today',
                    center: 'title',
                    right: 'dayGridMonth,timeGridWeek,timeGridDay'
                },
                views: {
                    dayGridMonth: { buttonText: 'Monat' },
                    timeGridWeek: { buttonText: 'Woche' },
                    timeGridDay: { buttonText: 'Tag' }
                }
            }
        });
    }

    setup_sidebar_calendars() {
        // Kalender-Liste in Sidebar (wie Nextcloud)
        frappe.call({
            method: "diakronos.kronos.api.get_user_calendars",
            callback: (r) => {
                this.render_calendar_sidebar(r.message);
            }
        });
    }

    render_calendar_sidebar(calendars) {
        let sidebar_html = calendars.map(cal => `
            <div class="calendar-item">
                <input type="checkbox" class="calendar-toggle" 
                       data-calendar="${cal.name}" ${cal.visible ? 'checked' : ''}>
                <span class="calendar-color" style="background-color: ${cal.color}"></span>
                <span class="calendar-name">${cal.display_name}</span>
            </div>
        `).join('');

        this.$sidebar.html(`
            <div class="calendar-sidebar">
                <h4>Meine Kalender</h4>
                ${sidebar_html}
            </div>
        `);
    }
}

// Event Handlers für Kalender Toggle
$(document).on('change', '.calendar-toggle', function () {
    const calendar_name = $(this).data('calendar');
    const visible = $(this).is(':checked');

    // Kalender ein-/ausblenden in der Ansicht
    frappe.views.calendar.toggle_calendar(calendar_name, visible);
});
