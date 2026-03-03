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

const formHandlers = { refresh(frm) { /* nothing extra needed */ } };

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
