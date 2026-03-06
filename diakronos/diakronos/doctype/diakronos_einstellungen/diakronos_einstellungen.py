import os
import re
import frappe
from frappe.model.document import Document

# (field_prefix, Frappe-Modulname)
KNOWN_MODULES = [
    ("diakronos", "Diakronos"),
    ("kronos",    "Kronos"),
    ("diakonos",  "Diakonos"),
    ("psalmos",   "Psalmos"),
    ("seelsorge", "Seelsorge"),
]

MODULE_DEFAULTS = {
    "Diakronos": {
        "anzeige_name": "Diakronos",
        "standard_icon": "/assets/diakronos/images/diakronos-logo.svg",
        "im_app_bereich_anzeigen": 1,
    },
    "Kronos": {
        "anzeige_name": "Kronos",
        "standard_icon": "/assets/diakronos/images/kronos-logo.svg",
        "im_app_bereich_anzeigen": 1,
    },
    "Diakonos": {
        "anzeige_name": "Diakonos",
        "standard_icon": "/assets/diakronos/images/diakonos-logo.svg",
        "im_app_bereich_anzeigen": 1,
    },
    "Psalmos": {
        "anzeige_name": "Psalmos",
        "standard_icon": "/assets/diakronos/images/psalmos-logo.svg",
        "im_app_bereich_anzeigen": 0,
    },
    "Seelsorge": {
        "anzeige_name": "Seelsorge",
        "standard_icon": "/assets/diakronos/images/seelsorge-logo.svg",
        "im_app_bereich_anzeigen": 0,
    },
}

# Feste Route-Überschreibungen (übersteuert Workspace-Lookup)
MODULE_ROUTES = {
    "Diakronos": "/app/\u00fcbersichtsseite",
    "Kronos":    "/kronos",    # Hub-Seite (leitet bei 1 Tool direkt weiter)
    "Psalmos":   "/psalmos",   # Eigene www-Seite
}

# Hartcodierte Tool-Seiten pro Submodul (Route nie via Admin änderbar)
MODULE_PAGES = {
    "Diakronos": [],   # kein Hub – direkt zu Workspace
    "Kronos": [
        {
            "key":          "kalender",
            "default_name": "Kalender",
            "route":        "/kronos/calendar",
            "default_icon": "/assets/diakronos/images/icons/calendar-week-icon.svg",
        },
    ],
    "Diakonos": [
        {
            "key":          "mitglieder",
            "default_name": "Mitglieder",
            "route":        "/app/diakonos",
            "default_icon": "",
        },
    ],
    "Psalmos": [
        {
            "key":          "lieder",
            "default_name": "Liederdatenbank",
            "route":        "/psalmos",
            "default_icon": "/assets/diakronos/images/psalmos-logo.svg",
        },
    ],
    "Seelsorge": [
        {
            "key":          "seelsorge",
            "default_name": "Seelsorge",
            "route":        "/app/seelsorge",
            "default_icon": "",
        },
    ],
}


class DiakronosEinstellungen(Document):
    def after_save(self):
        """Nach dem Speichern: Workspaces aktualisieren, hooks.py neu schreiben."""
        self._apply_to_workspaces()
        if self._update_hooks_apps_screen():
            frappe.msgprint(
                msg=(
                    "Die <b>App-Screen-Konfiguration</b> wurde automatisch in "
                    "<code>hooks.py</code> aktualisiert.<br><br>"
                    "&#9888;&#65039; Damit die \u00c4nderungen im Frappe-App-Bereich "
                    "sichtbar werden, muss der Server neu gestartet werden:<br>"
                    "<pre style='margin-top:8px;background:#f4f4f4;"
                    "padding:8px;border-radius:4px'>"
                    "bench --site ecg-hn migrate\n"
                    "bench restart"
                    "</pre>"
                ),
                title="Server-Neustart erforderlich",
                indicator="orange",
            )

    # ------------------------------------------------------------------ #
    # Interne Hilfsmethoden                                                #
    # ------------------------------------------------------------------ #

    def _apply_to_workspaces(self):
        """Überträgt Sichtbarkeit + Rollen auf die zugehörigen Frappe-Workspaces."""
        for prefix, module_name in KNOWN_MODULES:
            sichtbar = getattr(self, f"{prefix}_sichtbar", 1)
            rollen   = getattr(self, f"{prefix}_rollen", []) or []

            workspaces = frappe.get_all(
                "Workspace",
                filters={"module": module_name},
                fields=["name"],
            )
            for ws in workspaces:
                try:
                    ws_doc = frappe.get_doc("Workspace", ws.name)
                    ws_doc.is_hidden = 0 if sichtbar else 1
                    ws_doc.roles = []
                    for entry in rollen:
                        ws_doc.append("roles", {"role": entry.role})
                    ws_doc.save(ignore_permissions=True)
                except Exception as exc:
                    frappe.log_error(
                        f"Workspace-Update für '{ws.name}' fehlgeschlagen.\n{exc}",
                        "DiakronosEinstellungen._apply_to_workspaces",
                    )

    def _update_hooks_apps_screen(self):
        """
        Schreibt add_to_apps_screen in hooks.py neu.
        Gibt True zurück, wenn die Datei geändert wurde.
        """
        hooks_path = os.path.join(frappe.get_app_path("diakronos"), "hooks.py")
        try:
            with open(hooks_path, "r", encoding="utf-8") as f:
                original = f.read()
        except OSError as exc:
            frappe.log_error(f"hooks.py lesen fehlgeschlagen: {exc}",
                             "DiakronosEinstellungen._update_hooks_apps_screen")
            return False

        entries = []
        for prefix, module_name in KNOWN_MODULES:
            if not getattr(self, f"{prefix}_sichtbar", 0):
                continue
            logo  = getattr(self, f"{prefix}_icon", "") or \
                    MODULE_DEFAULTS.get(module_name, {}).get("standard_icon", "")
            label = getattr(self, f"{prefix}_anzeige_name", "") or module_name
            route = _get_module_route(module_name)
            entries.append({
                "name":  prefix,
                "logo":  logo,
                "title": label,
                "route": route,
            })

        lines = ["add_to_apps_screen = ["]
        for e in entries:
            lines.append("    {")
            for k, v in e.items():
                escaped = v.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'        "{k}": "{escaped}",')
            lines.append("    },")
        lines.append("]")
        new_block = "\n".join(lines)

        pattern     = r"add_to_apps_screen\s*=\s*\[.*?\]"
        new_content = re.sub(pattern, new_block, original, flags=re.DOTALL)

        if new_content == original:
            return False

        try:
            with open(hooks_path, "w", encoding="utf-8") as f:
                f.write(new_content)
        except OSError as exc:
            frappe.log_error(f"hooks.py schreiben fehlgeschlagen: {exc}",
                             "DiakronosEinstellungen._update_hooks_apps_screen")
            return False

        return True


# ------------------------------------------------------------------ #
# Whitelisted API                                                      #
# ------------------------------------------------------------------ #


@frappe.whitelist()
def get_module_defaults(module_name):
    """Gibt die Standardwerte eines Moduls zurück (für Reset-Button)."""
    defaults = MODULE_DEFAULTS.get(
        module_name,
        {"anzeige_name": module_name, "standard_icon": "", "im_app_bereich_anzeigen": 1},
    )
    return {
        "anzeige_name":          defaults["anzeige_name"],
        "icon":                  defaults["standard_icon"],
        "im_app_bereich_anzeigen": defaults["im_app_bereich_anzeigen"],
    }


# ------------------------------------------------------------------ #
# Interne Utility                                                      #
# ------------------------------------------------------------------ #


def _get_module_route(module_name):
    if module_name in MODULE_ROUTES:
        return MODULE_ROUTES[module_name]
    workspaces = frappe.get_all(
        "Workspace",
        filters={"module": module_name},
        fields=["name"],
        order_by="name",
        limit=1,
    )
    if workspaces:
        slug = workspaces[0]["name"].lower().replace(" ", "-")
        return f"/app/{slug}"
    return f"/app/{module_name.lower()}"
