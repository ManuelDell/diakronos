"""Portierung von `diakronos.caldav` (Altcode, Frappe) — NUR LESENDER CalDAV-Server.

VORLAGE (READ-ONLY):
  referenz/diakronos-frappe/diakronos/caldav/server.py  (393 LOC)
  referenz/diakronos-frappe/diakronos/caldav/ical.py    (61 LOC)
  referenz/diakronos-frappe/diakronos/caldav/auth.py    (24 LOC)

Im Original haengt der Server an einem `before_request`-Hook
(`diakronos/hooks.py:211 -> diakronos.caldav.server.intercept`), der `/dav/*`
und `/.well-known/caldav` abfaengt, BEVOR Frappe routet. Ein solcher Hook
existiert im FastAPI-Ziel nicht; die Routen werden deshalb ueber
`register_dav_routes(app)` an die Anwendung gehaengt.

Abweichungen und Begruendungen: siehe Docstrings in `caldav/server.py`
(`_get_user_calendars`) und `caldav/auth.py`.

Architektur-Entscheidung (Karte P6b): CalDAV laeuft ueber DIESEN Server, nicht
ueber den Radicale-Sidecar. Ein zweiter Speicher waere eine zweite Quelle der
Wahrheit fuer Termine gewesen (Sync-Zwang, Doppelhaltung).
"""

from __future__ import annotations

from diakronos_app.caldav.server import register_dav_routes

__all__ = ["register_dav_routes"]
