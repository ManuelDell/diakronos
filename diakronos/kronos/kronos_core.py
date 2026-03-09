# diakronos/kronos/kronos_core.py
"""
Kronos Core - Haupteinstiegspunkt für alle APIs.
Importiert und registriert alle Module.
"""

# Importiere alle API-Funktionen
from .api.calendar_get import (
    get_accessible_calendars,
    get_calendar_details
)

from .api.event_crud import (
    get_event_details
)

from .api.calendar_get import (
    get_calendar_events
)

# Importiere Manager-Klasse
from .core.manager import KronosCalendarManager

# Exportiere für externe Nutzung
__all__ = [
    # API Functions
    'get_accessible_calendars',
    'get_calendar_details',
    'get_calendar_events',
    'get_event_details'
]
