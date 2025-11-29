frappe.views.calendar['Kalender'] = {
    get_events: function (start, end, filters, event_type, format_event) {
        // Hole alle Element-Termine im Zeitraum
        return frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Element',
                fields: [
                    'name',
                    'element_name as title',
                    'element_start as start',
                    'element_end as end',
                    'element_color as color',
                    'element_calendar'
                ],
                filters: [
                    ['element_start', '>=', start.toISOString()],
                    ['element_end', '<=', end.toISOString()]
                ]
            }
        }).then(r => {
            // Filter nach Kalender aus Sidebar
            let events = r.message;
            if (filters.element_calendar && filters.element_calendar.length > 0) {
                events = events.filter(ev => filters.element_calendar.includes(ev.element_calendar));
            }
            return events.map(ev => ({
                id: ev.name,
                title: ev.title,
                start: ev.start,
                end: ev.end,
                color: ev.color
            }));
        });
    },
    get_filters: function () {
        // Liste aller Kalender für die Sidebar
        return frappe.db.get_list('Kalender', { fields: ['name'], limit_page_length: 100 }).then(kalender_list => {
            return [
                {
                    fieldname: 'element_calendar',
                    label: __('Kalender'),
                    fieldtype: 'MultiSelect',
                    options: kalender_list.map(k => k.name).join('\n'),
                    default: kalender_list.map(k => k.name)
                }
            ];
        });
    }
};
