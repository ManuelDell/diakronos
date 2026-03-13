// Diakronos Einstellungen – Form JS

const DEFAULTS_METHOD =
    "diakronos.diakronos.doctype.diakronos_einstellungen.diakronos_einstellungen.get_module_defaults";

// Modulkonfiguration: [field_prefix, Frappe-Modulname, Anzeigename]
const MODULES = [
    ["diakronos", "Diakronos",  "Diakronos"],
    ["kronos",    "Kronos",     "Kronos"],
    ["diakonos",  "Diakonos",   "Diakonos"],
    ["psalmos",   "Psalmos",    "Psalmos"],
    ["seelsorge", "Seelsorge",  "Seelsorge"],
];

// ── Formular-Events ───────────────────────────────────────────────────────────

const DEMO_METHOD = "diakronos.diakronos.doctype.diakronos_einstellungen.diakronos_einstellungen.run_demo_data_action";

const formHandlers = {
    refresh(frm) {
        _updateDemoCheckbox(frm);
    },

    demodaten_erstellen(frm) {
        const checked = frm.doc.demodaten_erstellen;
        const aktiv   = frm.doc.demodaten_aktiv;

        if (checked && !aktiv) {
            // Checkbox aktiviert → Demodaten erstellen
            frappe.call({
                method: DEMO_METHOD,
                args: { action: "create" },
                freeze: true,
                freeze_message: "Demodaten werden erstellt…",
                callback(r) {
                    if (!r.exc) frm.reload_doc();
                    else frm.set_value("demodaten_erstellen", 0);
                }
            });
        } else if (!checked && aktiv) {
            // Checkbox deaktiviert → Demodaten löschen (mit Bestätigung)
            frappe.confirm(
                "<b>Alle Daten unwiderruflich löschen?</b><br>" +
                "<span class='text-muted'>Kalender, Termine, Mitglieder und Besucher werden permanent gelöscht.</span>",
                () => {
                    frappe.call({
                        method: DEMO_METHOD,
                        args: { action: "delete" },
                        freeze: true,
                        freeze_message: "Daten werden gelöscht…",
                        callback(r) {
                            if (!r.exc) frm.reload_doc();
                            else frm.set_value("demodaten_erstellen", 1);
                        }
                    });
                },
                () => {
                    // Abgebrochen → Checkbox zurücksetzen
                    frm.set_value("demodaten_erstellen", 1);
                }
            );
        }
    }
};

// Reset-Button und SVG-Validierung pro Modul registrieren
MODULES.forEach(([prefix, moduleName, label]) => {
    formHandlers[`${prefix}_reset`] = (frm) => _confirmReset(frm, prefix, moduleName, label);
    formHandlers[`${prefix}_icon`]  = (frm) => _validateSvg(frm, `${prefix}_icon`);
});

// SVG-Validierung für Tool-Icons
formHandlers["kronos_kalender_icon"] = (frm) => _validateSvg(frm, "kronos_kalender_icon");

frappe.ui.form.on("Diakronos Einstellungen", formHandlers);

// ── Hilfsfunktionen ───────────────────────────────────────────────────────────

function _confirmReset(frm, prefix, moduleName, label) {
    frappe.confirm(
        `<b>${label}</b> wirklich auf Standardwerte zurücksetzen?<br>
         <span class="text-muted">Anzeigename, Icon und Sichtbarkeit werden zurückgesetzt.</span>`,
        () => _applyDefaults(frm, prefix, moduleName, label)
    );
}

// Tool-Felder pro Modul (key → [fieldname, default_value])
const MODULE_TOOL_FIELDS = {
    "kronos": [
        ["kronos_kalender_bezeichnung", "Kalender"],
        ["kronos_kalender_icon",        ""],
    ],
};

function _applyDefaults(frm, prefix, moduleName, label) {
    frappe.call({
        method: DEFAULTS_METHOD,
        args: { module_name: moduleName },
        callback(r) {
            if (!r.message) return;
            const d = r.message;
            frm.set_value(`${prefix}_anzeige_name`,  d.anzeige_name);
            frm.set_value(`${prefix}_icon`,          d.icon || "");
            frm.set_value(`${prefix}_sichtbar`,      d.im_app_bereich_anzeigen);
            frm.set_value(`${prefix}_rollen`,        []);
            // Tool-Felder zurücksetzen (falls vorhanden)
            (MODULE_TOOL_FIELDS[prefix] || []).forEach(([field, def]) => {
                frm.set_value(field, def);
            });
            frappe.show_alert(
                { message: `„${label}" wurde auf Standardwerte zurückgesetzt`, indicator: "blue" },
                5
            );
        },
    });
}

/**
 * Sperrt die Demodaten-Checkbox wenn bereits echte Daten vorhanden sind
 * und keine Demodaten aktiv sind (= echte Daten).
 */
function _updateDemoCheckbox(frm) {
    const demoAktiv = frm.doc.demodaten_aktiv;

    frappe.call({
        method: "frappe.client.get_count",
        args: { doctype: "Kalender" },
        callback(r) {
            const hatDaten = (r.message || 0) > 0;
            const sperren  = hatDaten && !demoAktiv;

            frm.set_df_property("demodaten_erstellen", "read_only", sperren ? 1 : 0);
            frm.set_df_property("demodaten_erstellen", "description",
                sperren
                    ? "Gesperrt: Es sind bereits echte Daten vorhanden."
                    : demoAktiv
                        ? "Deaktivieren → löscht alle vorhandenen Daten."
                        : "Aktivieren → erstellt Beispieldaten (nur möglich wenn keine Daten vorhanden)."
            );
        }
    });
}

/**
 * Prüft nach dem Upload, ob die Datei eine SVG ist.
 * Nicht-SVG-Dateien werden mit einer erklärenden Fehlermeldung abgewiesen.
 */
function _validateSvg(frm, fieldname) {
    const val = frm.doc[fieldname];
    if (!val) return;

    if (!val.toLowerCase().endsWith(".svg")) {
        frm.set_value(fieldname, "");
        frappe.msgprint({
            title: __("Falsches Dateiformat"),
            message: __(
                "Bitte lade das Icon als <b>SVG-Datei</b> hoch.<br><br>" +
                "Nur SVG-Dateien werden im Frappe-App-Bereich und als Modul-Icon korrekt dargestellt. " +
                "PNG/JPG-Dateien werden vom Frappe-App-Screen ignoriert."
            ),
            indicator: "red",
        });
    }
}
