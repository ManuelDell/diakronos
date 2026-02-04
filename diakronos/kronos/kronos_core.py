# diakronos/kronos/kronos_core.py
"""
Kronos Core - Haupteinstiegspunkt für alle APIs.
Importiert und registriert alle Module.
"""

# Importiere alle API-Funktionen
from .api.calendars import (
    get_accessible_calendars,
    get_calendar_details
)

from .api.events import (
    get_calendar_events,
    get_event_details
)

from .api.permissions import (
    has_calendar_permission,
    check_user_permission
)

from .api.sync import (
    sync_nextcloud_events,
    sync_all_calendars
)

# Importiere Manager-Klasse
from .core.manager import KronosCalendarManager

# Exportiere für externe Nutzung
__all__ = [
    # API Functions
    'get_accessible_calendars',
    'get_calendar_details',
    'get_calendar_events',
    'get_event_details',
    'has_calendar_permission',
    'check_user_permission',
    'sync_nextcloud_events',
    'sync_all_calendars',
    # Classes
    'KronosCalendarManager'
]
