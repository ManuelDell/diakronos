# diakronos/kronos/api/tui_management.py - SICHER VOR CALENDAR_ID FEHLER

import frappe
from frappe import _
from datetime import datetime

@frappe.whitelist()
def event_create_from_tui(title, start, end, calendar_id, is_all_day):
    """
    Erstellt ein neues Element/Event aus TUI Calendar.
    """
    try:
        user = frappe.session.user
        if not user or user == "Guest":
            frappe.throw(_("Sie müssen angemeldet sein."))

        # ✅ SICHERHEIT: Prüfe ZUERST ob Kalender existiert
        try:
            frappe.get_doc('Kalender', calendar_id)
        except frappe.DoesNotExistError:
            frappe.logger().warning(f"❌ Kalender '{calendar_id}' existiert nicht")
            frappe.throw(_("Kalender existiert nicht"))

        # ✅ WICHTIG: Konvertiere ISO8601 zu Frappe-Format
        start_dt = _parse_iso8601_to_frappe(start)
        end_dt = _parse_iso8601_to_frappe(end)

        # ✅ Erstelle neues Element
        doc = frappe.get_doc({
            'doctype': 'Element',
            'element_name': title,
            'element_start': start_dt,
            'element_end': end_dt,
            'element_calendar': calendar_id,
            'all_day': is_all_day,
            'status': 'Festgelegt',
            'owner': user,
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        frappe.logger().info(f'✅ Element erstellt: {doc.name}')
        return {
            'success': True,
            'name': doc.name,
            'message': _('Termin angelegt')
        }

    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(str(e), 'event_create_from_tui')
        frappe.throw(_('Fehler beim Anlegen: ') + str(e))


def _parse_iso8601_to_frappe(iso_string):
    """
    Konvertiert ISO8601 String (z.B. '2025-12-12T16:36:00.000Z') 
    zu Frappe Datetime Format ('2025-12-12 16:36:00')
    """
    if not iso_string:
        return None
    
    try:
        # Remove 'Z' timezone indicator and parse
        iso_clean = iso_string.replace('Z', '+00:00') if iso_string.endswith('Z') else iso_string
        dt = datetime.fromisoformat(iso_clean)
        
        # Return as Frappe expects: 'YYYY-MM-DD HH:MM:SS'
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        frappe.logger().warning(f"⚠️ Fehler beim Parsen von {iso_string}: {str(e)}")
        return iso_string



@frappe.whitelist()
def event_update_from_tui(name, title, start, end, calendar_id, is_all_day):
    """
    Aktualisiert ein existierendes Element/Event aus TUI Calendar.
    """
    try:
        user = frappe.session.user
        if not user or user == "Guest":
            frappe.throw(_("Sie müssen angemeldet sein."))

        # ✅ Hole das Element
        try:
            doc = frappe.get_doc('Element', name)
        except frappe.DoesNotExistError:
            frappe.logger().warning(f"❌ Element '{name}' existiert nicht")
            frappe.throw(_("Termin existiert nicht"))

        # ✅ Prüfe Berechtigungen
        if doc.owner != user:
            from diakronos.kronos.api.permissions import has_calendar_permission
            if not has_calendar_permission(doc.element_calendar, 'write'):
                frappe.throw(_("Keine Berechtigung zum Bearbeiten"))

        # ✅ WICHTIG: Konvertiere ISO8601 zu Frappe-Format (OHNE self!)
        start_dt = _parse_iso8601_to_frappe(start)
        end_dt = _parse_iso8601_to_frappe(end)

        # ✅ Update mit korrekten Feldnamen
        doc.element_name = title
        doc.element_start = start_dt
        doc.element_end = end_dt
        doc.all_day = is_all_day
        
        # ✅ SICHERHEIT: Nur ändern wenn calendar_id gültig ist
        if calendar_id:
            try:
                frappe.get_doc('Kalender', calendar_id)
                doc.element_calendar = calendar_id
                frappe.logger().info(f"✅ Kalender gewechselt zu: {calendar_id}")
            except frappe.DoesNotExistError:
                frappe.logger().warning(f"⚠️ Kalender '{calendar_id}' existiert nicht, behalte: {doc.element_calendar}")
        
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.logger().info(f'✅ Element aktualisiert: {doc.name}')
        return {
            'success': True,
            'name': doc.name,
            'message': _('Termin aktualisiert')
        }

    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(str(e), 'event_update_from_tui')
        frappe.throw(_('Fehler beim Aktualisieren: ') + str(e))



def _parse_iso8601_to_frappe(iso_string):
    """
    Konvertiert ISO8601 String (z.B. '2025-12-12T16:36:00.000Z') 
    zu Frappe Datetime Format ('2025-12-12 16:36:00')
    """
    if not iso_string:
        return None
    
    try:
        # Remove 'Z' timezone indicator and parse
        iso_clean = iso_string.replace('Z', '+00:00') if iso_string.endswith('Z') else iso_string
        dt = datetime.fromisoformat(iso_clean)
        
        # Return as Frappe expects: 'YYYY-MM-DD HH:MM:SS'
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        frappe.logger().warning(f"⚠️ Fehler beim Parsen von {iso_string}: {str(e)}")
        return iso_string


    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(str(e), 'event_update_from_tui')
        frappe.throw(_('Fehler beim Aktualisieren: ') + str(e))


@frappe.whitelist()
def event_delete_from_tui(name):
    """
    Löscht ein Element/Event aus TUI Calendar.
    """
    try:
        user = frappe.session.user
        if not user or user == "Guest":
            frappe.throw(_("Sie müssen angemeldet sein."))

        # ✅ Hole das Element
        try:
            doc = frappe.get_doc('Element', name)
        except frappe.DoesNotExistError:
            frappe.logger().warning(f"❌ Element '{name}' existiert nicht")
            frappe.throw(_("Termin existiert nicht"))
        
        # ✅ Prüfe Berechtigungen
        if doc.owner != user:
            from diakronos.kronos.api.permissions import has_calendar_permission
            if not has_calendar_permission(doc.element_calendar, 'write'):
                frappe.throw(_("Keine Berechtigung zum Löschen"))

        # ✅ Lösche das Element
        frappe.delete_doc('Element', name, ignore_permissions=True)
        frappe.db.commit()

        frappe.logger().info(f'✅ Element gelöscht: {name}')
        return {
            'success': True,
            'message': _('Termin gelöscht')
        }

    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(str(e), 'event_delete_from_tui')
        frappe.throw(_('Fehler beim Löschen: ') + str(e))
