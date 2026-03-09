from frappe import _

def get_data():
    return [
        {
            "module_name": "Diakronos",
            "label": _("Diakronos"),
            "color": "#4A90D9",
            "icon": "assets/diakronos/images/kronos-logo.svg",
            "type": "module",
            "description": _("Kirchenverwaltung – Kalender, Gemeinde, Einstellungen."),
        }
    ]
