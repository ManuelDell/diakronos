// apps/diakronos/diakronos/kronos/doctype/element/element.js

frappe.ui.form.on('Element', {
    refresh(frm) {
        // Wenn das Element Teil einer Serie ist, zeige Serie-Dialog
        if (frm.doc.series_id) {
            show_series_modal(frm);
        }
    }
});


function show_series_modal(frm) {
    let d = new frappe.ui.Dialog({
        title: 'Serienoptionen für: ' + frm.doc.series_id,
        fields: [],
        primary_action_label: null,  // Keine Primary Action
        secondary_action_label: __('Abbruch'),
        secondary_action() {
            d.hide();
            frappe.set_route('List', 'Element');
        }
    });

    // Buttons als HTML (mit Pastelltönen)
    let button_html = `
        <div style="display: flex; flex-direction: column; gap: 15px; padding: 20px;">
            
            <button class="btn btn-block" id="btn-remove" style="
                background-color: #FFB3BA;
                color: #333;
                border: none;
                padding: 12px;
                font-size: 14px;
                font-weight: 500;
                border-radius: 6px;
                cursor: pointer;
                transition: all 0.2s;
            ">
                ➖ Aus Serie entfernen
            </button>

            <button class="btn btn-block" id="btn-edit" style="
                background-color: #BAFFC9;
                color: #333;
                border: none;
                padding: 12px;
                font-size: 14px;
                font-weight: 500;
                border-radius: 6px;
                cursor: pointer;
                transition: all 0.2s;
            ">
                ✏️ Serie bearbeiten (Name + Status)
            </button>

            <button class="btn btn-block" id="btn-delete" style="
                background-color: #FFD3B6;
                color: #333;
                border: none;
                padding: 12px;
                font-size: 14px;
                font-weight: 500;
                border-radius: 6px;
                cursor: pointer;
                transition: all 0.2s;
            ">
                🗑️ Ganze Serie löschen
            </button>

        </div>
    `;

    // HTML ins Dialog einfügen
    d.$body.html(button_html);

    // Hover-Effekte
    let style = document.createElement('style');
    style.textContent = `
        #btn-remove:hover { background-color: #FF9DA5 !important; transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.15); }
        #btn-edit:hover { background-color: #9AFF9A !important; transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.15); }
        #btn-delete:hover { background-color: #FFBB99 !important; transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.15); }
        
        #btn-remove:active { transform: translateY(0); }
        #btn-edit:active { transform: translateY(0); }
        #btn-delete:active { transform: translateY(0); }
    `;
    document.head.appendChild(style);

    // ⭐ WICHTIG: setTimeout damit DOM fertig ist
    setTimeout(function () {
        // Button 1: Aus Serie entfernen
        let btn_remove = document.getElementById('btn-remove');
        if (btn_remove) {
            btn_remove.addEventListener('click', function () {
                frappe.confirm(
                    'Wirklich diesen Termin aus der Serie entfernen? Die Serie bleibt bestehen.',
                    function () {
                        frappe.call({
                            method: 'frappe.client.set_value',
                            args: {
                                doctype: 'Element',
                                name: frm.doc.name,
                                fieldname: {
                                    series_id: ''
                                }
                            },
                            callback: function (r) {
                                if (!r.exc) {
                                    frappe.msgprint({
                                        title: __('Erfolg'),
                                        message: __('Termin aus Serie entfernt. Er ist jetzt ein Einzeltermin.'),
                                        indicator: 'green'
                                    });
                                    d.hide();
                                    frappe.set_route('List', 'Element');
                                }
                            }
                        });
                    }
                );
            });
        }

        // Button 2: Serie bearbeiten
        let btn_edit = document.getElementById('btn-edit');
        if (btn_edit) {
            btn_edit.addEventListener('click', function () {
                show_edit_series_dialog(frm, d);
            });
        }

        // Button 3: Serie löschen
        let btn_delete = document.getElementById('btn-delete');
        if (btn_delete) {
            btn_delete.addEventListener('click', function () {
                frappe.confirm(
                    'Wirklich die GANZE Serie löschen? Alle Termine werden gelöscht!',
                    function () {
                        frappe.call({
                            method: 'diakronos.kronos.series_handler.delete_series_batch',
                            args: {
                                series_id: frm.doc.series_id
                            },
                            callback: function (r) {
                                if (r.message && r.message.success) {
                                    frappe.msgprint({
                                        title: __('Serie gelöscht'),
                                        message: __(r.message.message),
                                        indicator: 'green'
                                    });
                                    d.hide();
                                    frappe.set_route('List', 'Element');
                                }
                            }
                        });
                    }
                );
            });
        }
    }, 100);  // 100ms warten, damit DOM fertig ist

    d.show();
}


function show_edit_series_dialog(frm, parent_dialog) {
    let edit_d = new frappe.ui.Dialog({
        title: 'Serie bearbeiten: ' + frm.doc.series_id,
        fields: [
            {
                label: 'Elementname',
                fieldname: 'element_name',
                fieldtype: 'Data',
                default: frm.doc.element_name,
                reqd: 1
            },
            {
                label: 'Status',
                fieldname: 'status',
                fieldtype: 'Select',
                options: 'Vorschlag\nFestgelegt\nKonflikt',
                default: frm.doc.status,
                reqd: 1
            }
        ],
        primary_action_label: __('Alle aktualisieren'),
        primary_action(values) {
            frappe.call({
                method: 'diakronos.kronos.series_handler.update_series_batch_fast',
                args: {
                    series_id: frm.doc.series_id,
                    updates: {
                        element_name: values.element_name,
                        status: values.status
                    }
                },
                callback: function (r) {
                    if (r.message && r.message.success) {
                        frappe.msgprint({
                            title: __('Serie aktualisiert'),
                            message: __(`${r.message.updated_count} Termine aktualisiert`),
                            indicator: 'green'
                        });
                        edit_d.hide();
                        parent_dialog.hide();
                        frappe.set_route('List', 'Element');
                    }
                }
            });
        }
    });

    edit_d.show();
}
