# diakronos/kronos/api/__init__.py
"""
Exportiert die wichtigsten API-Funktionen für einfache Imports.
"""

from .permissions import (
    get_accessible_calendars
)

from .calendar_get import get_calendar_events

from .event_crud import (
    create_event,
    update_event,
    delete_event,
    get_event_details
)

# Nur die wirklich häufig genutzten exportieren
__all__ = [
    'get_accessible_calendars',
    'has_calendar_permission',
    'get_calendar_events',
    'create_event',
    'update_event',
    'delete_event',
    'get_event_details',
    # sync-Funktionen nur, wenn sie oft von außen gebraucht werden
    # 'sync_nextcloud_events',
    # 'sync_all_calendars',
]