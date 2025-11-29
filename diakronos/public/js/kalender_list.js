frappe.listview_settings['Kalender'] = {
    onload: function (listview) {
        listview.page.add_button(__('Zur Kalender Übersicht'), function () {
            frappe.set_route('calendar_overview');
        }, 'Ansicht');
    }
};
