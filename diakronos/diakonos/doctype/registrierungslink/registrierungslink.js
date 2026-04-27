frappe.ui.form.on("Registrierungslink", {
    refresh(frm) {
        if (!frm.is_new() && frm.doc.slug) {
            const pfad = frm.doc.typ === "Mitglied-Registrierung" ? "registrierung" : "gast";
            const url  = `${window.location.origin}/diakonos/${pfad}?token=${frm.doc.slug}`;

            frm.add_custom_button(__("Link kopieren"), () => {
                navigator.clipboard.writeText(url).then(() => {
                    frappe.show_alert({ message: __("Link kopiert!"), indicator: "green" });
                });
            });

            frm.add_custom_button(__("Link öffnen"), () => {
                window.open(url, "_blank");
            });

            // Zeige URL als lesbares Feld an
            if (!frm.doc.link_anzeige || frm.doc.link_anzeige !== url) {
                frappe.db.set_value("Registrierungslink", frm.doc.name, "link_anzeige", url, () => {
                    frm.reload_doc();
                });
            }
        }

        if (!frm.is_new()) {
            const count = frm.doc.anmeldungen_count || 0;
            const max   = frm.doc.max_anmeldungen || 0;
            const info  = max > 0
                ? `${count} / ${max} Anmeldungen`
                : `${count} Anmeldungen (unbegrenzt)`;
            frm.dashboard.add_indicator(info, count > 0 ? "green" : "gray");
        }
    },
});
