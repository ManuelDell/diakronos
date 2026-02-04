# diakronos/kronos/api/__init__.py - Fixed für attribute_resolve
from .permissions import get_accessible_calendars, has_calendar_permission, get_element_creation_dialog_defaults  # Aus permissions.py für Kalender-Berechtigungen
from .calendar_get import get_calendar_events  # Aus calendar_get.py für Event-Fetch
from .event_crud import get_events, create_event, update_event, delete_event, get_event_details  # Aus event_crud.py für Eventplanung
from .cache_invalidator import invalidate_events_cache  # Aus cache_invalidator.py für Cache-Refresh nach Event-Update
from .series_create import create_event_series  # Aus series_create.py für Serien-Events in Kronos
from .series_update import update_series_batch_fast, delete_series_batch_fast  # Aus series_update.py für Serien-Updates

__all__ = [  # Macht alles exportierbar für Frappe
    'get_accessible_calendars', 'has_calendar_permission', 'get_element_creation_dialog_defaults',
    'get_calendar_events', 'create_event', 'update_event', 'delete_event', 'get_event_details',
    'invalidate_events_cache', 'create_event_series', 'update_series_batch_fast', 'delete_series_batch_fast'
]