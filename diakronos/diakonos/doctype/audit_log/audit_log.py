import frappe
from frappe.model.document import Document


class AuditLog(Document):
    def before_rename(self, old, new, merge=False):
        frappe.throw("Audit Log kann nicht umbenannt werden.", frappe.PermissionError)

    def on_update(self):
        if getattr(frappe.local, "audit_policy_logged", False):
            return
        frappe.throw("Audit Log kann nicht bearbeitet werden.", frappe.PermissionError)

    def on_trash(self):
        if getattr(frappe.local, "audit_policy_logged", False):
            return
        frappe.throw("Audit Log kann nicht gelöscht werden.", frappe.PermissionError)


def prevent_modification(doc, method):
    """Hook-Version für DocType-Events in hooks.py"""
    if getattr(frappe.local, "audit_policy_logged", False):
        return
    frappe.throw("Audit Log kann nicht bearbeitet oder gelöscht werden.", frappe.PermissionError)


def create_audit_log_db_triggers():
    """Erstellt MariaDB-Trigger, die UPDATE und DELETE auf tabAudit Log verbieten.
    Sollte als after_migrate Hook oder manuell ausgeführt werden.
    """
    try:
        # Trigger: Verhindere DELETE
        frappe.db.sql("""
            CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
            BEFORE DELETE ON `tabAudit Log`
            FOR EACH ROW
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Audit Log deletion is forbidden';
        """)
        # Trigger: Verhindere UPDATE (außer anonymized_at und notification_gesendet)
        frappe.db.sql("""
            CREATE TRIGGER IF NOT EXISTS audit_log_no_update
            BEFORE UPDATE ON `tabAudit Log`
            FOR EACH ROW
            BEGIN
                IF OLD.anonymized_at IS NULL AND NEW.anonymized_at IS NOT NULL THEN
                    -- Erlaubt: Anonymisierung
                    SET @dummy = 1;
                ELSEIF OLD.notification_gesendet = 0 AND NEW.notification_gesendet = 1 THEN
                    -- Erlaubt: Notification-Flag setzen
                    SET @dummy = 1;
                ELSE
                    SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'Audit Log modification is forbidden';
                END IF;
            END;
        """)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Audit Log DB Trigger creation failed: {e}")


def setup_audit_log_protection():
    """Wird von hooks.py after_migrate aufgerufen."""
    create_audit_log_db_triggers()
