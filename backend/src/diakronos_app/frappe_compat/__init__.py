"""Frappe-Compat-Schicht — ersetzt `frappe.*` fuer das Standalone-Backend.

Oeffentliche API (bewusst klein gehalten, waechst mit dem Port):

    from diakronos_app import frappe_compat as frappe
    frappe.get_doc("Mitglied", "M-0001")
    frappe.get_all("Mitglied", filters={"status": "Mitglied"}, fields=["name"])
    frappe.db.get_value("Mitglied", "M-0001", "email")
    frappe.throw("...", frappe.ValidationError)
    frappe.session.user

Diese Schicht ist NICHT Frappe. Sie bildet die im Altcode tatsaechlich benutzten
Teile ab (siehe Nutzungsabzug der Frappe-API), nicht die gesamte Frappe-API.
"""

from __future__ import annotations

from .db import Database, db
from .doc import Document, new_doc
from .exceptions import (
	DoesNotExistError,
	DuplicateEntryError,
	FrappeCompatError,
	PermissionError,
	ValidationError,
	throw,
)
from .query import get_all, get_doc, get_value
from .queue import EnqueueError, enqueue
from .realtime import EVENT_GCAL_IMPORT_PROGRESS, publish_realtime, sio, socket_app
from .registry import whitelist
from .session import GUEST, reset_user, session, set_user

# Berechtigungen — echte Hierarchie-Logik aus P3, fail closed.
# Spezifikation mit Fundstellen: Docstrings in `permissions.py`.
from .permissions import (
	check_permission,
	darf_entwurf_sehen,
	get_roles,
	has_bereichs_zugriff,
	has_role,
	is_admin,
	is_guest,
	ist_verantwortlich_fuer,
	mitglied_permissions,
	require_admin,
	require_mitglied_edit,
	require_mitglied_view,
)

__all__ = [
	"Database",
	"db",
	"Document",
	"new_doc",
	"get_doc",
	"get_all",
	"get_value",
	"whitelist",
	"session",
	"set_user",
	"reset_user",
	"GUEST",
	"enqueue",
	"EnqueueError",
	"publish_realtime",
	"sio",
	"socket_app",
	"EVENT_GCAL_IMPORT_PROGRESS",
	"throw",
	"FrappeCompatError",
	"ValidationError",
	"PermissionError",
	"DoesNotExistError",
	"DuplicateEntryError",
	"get_roles",
	"has_role",
	"is_admin",
	"is_guest",
	"require_admin",
	"check_permission",
	"mitglied_permissions",
	"require_mitglied_view",
	"require_mitglied_edit",
	"ist_verantwortlich_fuer",
	"has_bereichs_zugriff",
	"darf_entwurf_sehen",
]
