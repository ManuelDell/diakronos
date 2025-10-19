from frappe import _

def get_data():
    return [
        {
            "module_name": "Diakronos",
            "label": _("Diakronos"),
            "color": "#7EB26D",
            "icon": "assets/diakronos/public/images/diakronos-logo.svg",
            "type": "module",
            "description": _("Dein Kirchenverwaltungsprogramm."),
        }
    ]
