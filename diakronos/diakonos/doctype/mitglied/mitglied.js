// Copyright (c) 2025, Dells Dienste and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mitglied", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("DSGVO-Daten exportieren"), () => {
                _dsgvo_export(frm);
            }, __("Datenschutz"));

            frm.add_custom_button(__("Einwilligung erfassen"), () => {
                _dsgvo_einwilligung_erfassen(frm);
            }, __("Datenschutz"));
        }
    },

    dsgvo_export(frm) {
        _dsgvo_export(frm);
    },
});

function _dsgvo_export(frm) {
    frappe.call({
        method: "diakronos.diakonos.api.dsgvo_export.export_mitglied_data",
        args: { mitglied_name: frm.doc.name },
        callback(r) {
            if (!r.message) return;
            const json = JSON.stringify(r.message, null, 2);
            const blob = new Blob([json], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `DSGVO-Export-${frm.doc.name}.json`;
            a.click();
            URL.revokeObjectURL(url);
            frappe.show_alert({ message: __("Export erstellt"), indicator: "green" });
        },
    });
}

function _dsgvo_einwilligung_erfassen(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __("DSGVO-Einwilligung erfassen"),
        fields: [
            {
                fieldname: "einwilligungstext",
                fieldtype: "Small Text",
                label: __("Einwilligungstext (Snapshot)"),
                default: "Ich willige in die Speicherung und Verarbeitung meiner personenbezogenen Daten gemäß DSGVO ein.",
            },
            {
                fieldname: "ip_adresse",
                fieldtype: "Data",
                label: __("IP-Adresse (optional)"),
            },
        ],
        primary_action_label: __("Einwilligung speichern"),
        primary_action(values) {
            frappe.db.insert({
                doctype: "DSGVO Einwilligung",
                mitglied: frm.doc.name,
                zeitstempel: frappe.datetime.now_datetime(),
                einwilligungstext: values.einwilligungstext,
                ip_adresse: values.ip_adresse || "",
                widerrufen: 0,
            }).then(() => {
                dialog.hide();
                frappe.show_alert({ message: __("Einwilligung gespeichert"), indicator: "green" });
                frm.reload_doc();
            });
        },
    });
    dialog.show();
}
