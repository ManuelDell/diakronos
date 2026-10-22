"""Kronos-API-Ports (P4b: Kern).

Die Module dieses Pakets sind 1:1-Portierungen der Altcode-Module
`diakronos.kronos.api.<modul>`. Die SPA ruft ausschliesslich die
ORIGINAL-dotted-paths auf:

    diakronos.kronos.api.permissions.get_session_info
    diakronos.kronos.api.calendar_get.get_calendar_events
    diakronos.kronos.api.event_crud.create_event
    diakronos.kronos.api.series.update_series_batch_fast
    ...

Damit diese Pfade aufloesen, traegt JEDES Modul die Konstante
`FRAPPE_MODULE` mit seinem Original-Pfad; `frappe_compat/registry.py`
registriert daraus zusaetzlich den vollen Original-Schluessel (main 33c296a).
Ein Alias-Paket `diakronos/` gibt es bewusst NICHT — ein Mechanismus, nicht
zwei (sonst Wartungsfalle bei 104 Endpunkten).

`_shared` (jetzt `frappe_compat/api_helpers`) haelt die gemeinsamen
Frappe-Ersatz-Helfer, damit es EINE Umsetzung gibt — analog zum P4a-Muster in
`diakronos_app/api/gruppen.py`. Der Helfer liegt seit P8 in `frappe_compat/`,
weil er moduluebergreifend benutzt wird und inhaltlich Frappe-Emulation ist,
kein Kronos-Fachmodul.

Import-Seiteneffekt: `diakronos_app.api.__init__` importiert dieses Paket,
damit die Endpunkte beim Laden der Registry bekannt sind.
"""

from __future__ import annotations

# Die Fachmodule MUSSEN hier importiert werden: `import diakronos_app.api`
# importiert nur `diakronos_app.api.kronos`, nicht dessen Kinder. Ohne diese
# Zeilen laufen die `@whitelist`-Dekoratoren nie und kein einziger Kronos-Pfad
# ist in der Registry — genau der Fehler, der bei der ersten Fassung auftrat.
from diakronos_app.api.kronos import permissions  # noqa: F401
from diakronos_app.api.kronos import calendar_get  # noqa: F401
from diakronos_app.api.kronos import event_crud  # noqa: F401
from diakronos_app.api.kronos import moderation  # noqa: F401 — P1-1b: zentrale Moderationsregel
from diakronos_app.api.kronos import series  # noqa: F401
from diakronos_app.api.kronos import ressource_api  # noqa: F401 — P4c1: Ressourcen
from diakronos_app.api.kronos import kalender  # noqa: F401 — P4c1: Anmelde-Kalender
# P2-5: Kalenderverwaltung (anlegen/aendern/loeschen, Rechte, Moderatoren).
from diakronos_app.api.kronos import kalender_verwaltung  # noqa: F401
# P4c3: Ablaufplan + Kanban (Original: diakronos.kronos.api.{ablaufplan_api,kanban_api}).
from diakronos_app.api.kronos import ablaufplan_api  # noqa: F401
from diakronos_app.api.kronos import kanban_api  # noqa: F401
from diakronos_app.api.kronos import google_import  # noqa: F401 — G1a

__all__ = [
    "permissions",
    "calendar_get",
    "event_crud",
    "moderation",
    "series",
    "ressource_api",
    "kalender",
    "ablaufplan_api",
    "kanban_api",
]
