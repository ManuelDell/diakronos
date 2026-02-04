// diakronos/diakonos/doctype/mitglied/mitglied_list.js

frappe.listview_settings['Mitglied'] = {
    onload: function(listview) {
        // Import Button hinzufügen
        listview.page.add_inner_button(__('Mitglieder importieren'), function() {
            show_mitglied_import_dialog();
        }, __('Aktionen'));
        
        // Template Download Button
        listview.page.add_menu_item(__('Import-Template herunterladen'), function() {
            download_mitglied_template();
        }, true);
    },
    
    // Weitere List View Einstellungen
    get_indicator: function(doc) {
        if (doc.auf_bemerkung_gesetzt) {
            return [__("Auf Bemerkung gesetzt"), "orange", "auf_bemerkung_gesetzt,=,1"];
        }
    }
};

function show_mitglied_import_dialog() {
    let d = new frappe.ui.Dialog({
        title: __('Mitglieder importieren'),
        size: 'large',
        fields: [
            {
                fieldtype: 'Section Break',
                label: __('Datei Upload')
            },
            {
                label: __('CSV oder Excel Datei'),
                fieldname: 'import_file',
                fieldtype: 'Attach',
                reqd: 1,
                description: __('Unterstützte Formate: .csv, .xlsx, .xls')
            },
            {
                fieldname: 'cb1',
                fieldtype: 'Column Break'
            },
            {
                label: __('Benutzer automatisch anlegen'),
                fieldname: 'create_users',
                fieldtype: 'Check',
                default: 0,
                description: __('Erstellt automatisch Benutzerkonten für alle Mitglieder')
            },
            {
                fieldname: 'sb2',
                fieldtype: 'Section Break',
                label: __('Validierung')
            },
            {
                fieldtype: 'HTML',
                fieldname: 'validation_results',
                options: '<div class="text-muted">' + __('Laden Sie eine Datei hoch und klicken Sie auf "Validieren"') + '</div>'
            },
            {
                fieldname: 'sb3',
                fieldtype: 'Section Break',
                label: __('Hinweise')
            },
            {
                fieldtype: 'HTML',
                options: `
                    <div style="padding: 15px; background: var(--bg-light-gray); border-radius: var(--border-radius);">
                        <h6><strong>${__('Erforderliche Felder:')}</strong></h6>
                        <ul>
                            <li><strong>vorname</strong> - Vorname des Mitglieds</li>
                            <li><strong>nachname</strong> - Nachname des Mitglieds</li>
                            <li><strong>e_mail</strong> - E-Mail-Adresse (muss eindeutig sein)</li>
                        </ul>
                        <h6><strong>${__('Optionale Felder:')}</strong></h6>
                        <ul>
                            <li>geburtsdatum (Format: YYYY-MM-DD)</li>
                            <li>postleitzahl</li>
                            <li>strasse</li>
                            <li>wohnort</li>
                            <li>nummer (Hausnummer)</li>
                            <li>telefonnummer</li>
                            <li>mitglied_seit (Format: YYYY-MM-DD)</li>
                            <li>auf_bemerkung_gesetzt (0 oder 1)</li>
                        </ul>
                        <p class="text-muted small mt-3">
                            <strong>${__('Hinweis:')}</strong> Spaltennamen können Groß-/Kleinschreibung, 
                            Leerzeichen und Bindestriche enthalten. Sie werden automatisch normalisiert.
                        </p>
                    </div>
                `
            }
        ],
        primary_action_label: __('Validieren'),
        primary_action(values) {
            if (!values.import_file) {
                frappe.msgprint(__('Bitte wählen Sie eine Datei aus'));
                return;
            }
            
            // Validierung durchführen
            frappe.call({
                method: 'diakronos.diakonos.doctype.mitglied.mitglied_bulk_import.mitglied_validate_import',
                args: {
                    file_url: values.import_file
                },
                freeze: true,
                freeze_message: __('Validiere Daten...'),
                callback: function(r) {
                    if (r.message) {
                        display_validation_results(r.message, d);
                        
                        if (r.message.success) {
                            // Primären Button zu "Importieren" ändern
                            d.set_primary_action(__('Importieren'), function() {
                                perform_import(values, d);
                            });
                        }
                    }
                }
            });
        }
    });
    
    d.show();
}

function display_validation_results(results, dialog) {
    let html = '';
    
    if (results.success) {
        html = `
            <div class="alert alert-success">
                <strong><i class="fa fa-check-circle"></i> ${__('Validierung erfolgreich!')}</strong>
                <p class="mt-2 mb-0">${__('Alle {0} Datensätze sind gültig und können importiert werden.', [results.total_rows])}</p>
            </div>
        `;
    } else {
        html = `
            <div class="alert alert-warning">
                <strong><i class="fa fa-exclamation-triangle"></i> ${__('Validierung mit Fehlern')}</strong>
                <p class="mt-2">
                    ${__('Gültige Datensätze:')} <strong>${results.valid_rows}</strong> von <strong>${results.total_rows}</strong><br>
                    ${__('Fehlerhafte Datensätze:')} <strong>${results.error_count}</strong>
                </p>
            </div>
        `;
        
        if (results.duplicate_count > 0) {
            html += `
                <div class="alert alert-info">
                    <i class="fa fa-info-circle"></i> ${__('Duplikate gefunden:')} <strong>${results.duplicate_count}</strong>
                </div>
            `;
        }
        
        if (results.errors && results.errors.length > 0) {
            html += `
                <div class="mt-3">
                    <h6><strong>${__('Fehlerdetails:')}</strong></h6>
                    <table class="table table-bordered table-sm">
                        <thead>
                            <tr>
                                <th>${__('Zeile')}</th>
                                <th>${__('Fehler')}</th>
                            </tr>
                        </thead>
                        <tbody>
            `;
            
            results.errors.slice(0, 20).forEach(function(err) {
                html += `
                    <tr>
                        <td>${err.row}</td>
                        <td>${err.errors.join(', ')}</td>
                    </tr>
                `;
            });
            
            html += `
                        </tbody>
                    </table>
            `;
            
            if (results.errors.length > 20) {
                html += `<p class="text-muted">${__('... und {0} weitere Fehler', [results.errors.length - 20])}</p>`;
            }
            
            html += `
                    <p class="text-danger mt-2">
                        <strong>${__('Bitte korrigieren Sie die Fehler in Ihrer Datei und versuchen Sie es erneut.')}</strong>
                    </p>
                </div>
            `;
        }
    }
    
    // Preview anzeigen
    if (results.preview && results.preview.length > 0) {
        html += `
            <div class="mt-4">
                <h6><strong>${__('Vorschau (erste 10 Zeilen):')}</strong></h6>
                <table class="table table-bordered table-sm">
                    <thead>
                        <tr>
                            <th>${__('Zeile')}</th>
                            <th>${__('Vorname')}</th>
                            <th>${__('Nachname')}</th>
                            <th>${__('E-Mail')}</th>
                            <th>${__('Status')}</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        results.preview.forEach(function(row) {
            let status_class = row.status === 'OK' ? 'success' : 'danger';
            html += `
                <tr>
                    <td>${row.row}</td>
                    <td>${row.vorname || ''}</td>
                    <td>${row.nachname || ''}</td>
                    <td>${row.e_mail || ''}</td>
                    <td><span class="badge badge-${status_class}">${row.status}</span></td>
                </tr>
            `;
        });
        
        html += `
                    </tbody>
                </table>
            </div>
        `;
    }
    
    dialog.fields_dict.validation_results.$wrapper.html(html);
}

function perform_import(values, dialog) {
    frappe.confirm(
        __('Möchten Sie {0} Mitglied(er) wirklich importieren?', [dialog.validation_results?.total_rows || 'die']),
        function() {
            frappe.call({
                method: 'diakronos.diakonos.doctype.mitglied.mitglied_bulk_import.mitglied_bulk_import',
                args: {
                    file_url: values.import_file,
                    create_users: values.create_users ? 1 : 0
                },
                freeze: true,
                freeze_message: __('Importiere Mitglieder... Dies kann einige Minuten dauern.'),
                callback: function(r) {
                    if (r.message) {
                        dialog.hide();
                        show_import_results(r.message);
                        
                        // Liste aktualisieren
                        frappe.set_route('List', 'Mitglied');
                        setTimeout(function() {
                            cur_list && cur_list.refresh();
                        }, 1000);
                    }
                }
            });
        }
    );
}

function show_import_results(results) {
    let indicator = results.errors.length === 0 ? 'green' : 
                   results.success > 0 ? 'orange' : 'red';
    
    let message = `
        <div class="import-summary">
            <h5>${__('Import abgeschlossen')}</h5>
            <table class="table table-borderless">
                <tr>
                    <td><strong>${__('Gesamt:')}</strong></td>
                    <td>${results.total}</td>
                </tr>
                <tr style="color: green;">
                    <td><strong>${__('Erfolgreich:')}</strong></td>
                    <td><strong>${results.success}</strong></td>
                </tr>
                <tr style="color: red;">
                    <td><strong>${__('Fehler:')}</strong></td>
                    <td><strong>${results.errors.length}</strong></td>
                </tr>
            </table>
    `;
    
    if (results.errors.length > 0) {
        message += `
            <hr>
            <h6><strong>${__('Fehlerdetails:')}</strong></h6>
            <div style="max-height: 300px; overflow-y: auto;">
                <table class="table table-bordered table-sm">
                    <thead>
                        <tr>
                            <th>${__('Zeile')}</th>
                            <th>${__('Vorname')}</th>
                            <th>${__('Nachname')}</th>
                            <th>${__('Fehler')}</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        results.errors.forEach(function(err) {
            message += `
                <tr>
                    <td>${err.row}</td>
                    <td>${err.vorname || '-'}</td>
                    <td>${err.nachname || '-'}</td>
                    <td>${err.error}</td>
                </tr>
            `;
        });
        
        message += `
                    </tbody>
                </table>
            </div>
        `;
    }
    
    if (results.created_members && results.created_members.length > 0) {
        message += `
            <hr>
            <h6><strong>${__('Beispiele erfolgreich importierter Mitglieder:')}</strong></h6>
            <ul>
        `;
        
        results.created_members.forEach(function(member) {
            message += `<li>${member.vorname} ${member.nachname} (${member.e_mail})</li>`;
        });
        
        message += `
            </ul>
        `;
    }
    
    message += '</div>';
    
    frappe.msgprint({
        title: __('Import Ergebnis'),
        message: message,
        indicator: indicator,
        primary_action: {
            label: __('Zur Mitgliederliste'),
            action: function() {
                frappe.set_route('List', 'Mitglied');
            }
        }
    });
}

function download_mitglied_template() {
    frappe.call({
        method: 'diakronos.diakonos.doctype.mitglied.mitglied_bulk_import.mitglied_download_template',
        callback: function(r) {
            if (r.message) {
                // CSV Download
                let blob = new Blob([r.message], { type: 'text/csv;charset=utf-8;' });
                let link = document.createElement('a');
                let url = URL.createObjectURL(blob);
                link.setAttribute('href', url);
                link.setAttribute('download', 'mitglied_import_template.csv');
                link.style.visibility = 'hidden';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                
                frappe.show_alert({
                    message: __('Template heruntergeladen'),
                    indicator: 'green'
                }, 3);
            }
        }
    });
}
