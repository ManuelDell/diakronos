import functools
import hashlib
import json
import frappe
from frappe import _
from frappe.utils import now_datetime

from diakronos.diakonos.api.audit_policy.engine import get_active_policies, evaluate_policy
from diakronos.diakonos.api.audit_policy.notifications import send_notification


def _set_idempotency_key_atomic(cache_key, payload_hash, ttl):
    """Atomarer Idempotency-Check via Redis SET NX EX.
    Speichert den Payload-Hash, um denselben Key für unterschiedliche Daten zu erkennen.
    Gibt True zurück wenn Key neu gesetzt wurde, False wenn er schon existiert.
    Wirft ValidationError wenn Key für andere Daten wiederverwendet wird.
    """
    try:
        redis_client = frappe.cache().redis
        if redis_client:
            result = redis_client.set(cache_key, payload_hash, nx=True, ex=ttl)
            if result is not None:
                return True
            # Key existiert bereits – prüfe Payload-Hash
            stored = redis_client.get(cache_key)
            if stored and stored.decode() != payload_hash:
                frappe.throw(
                    _("Idempotenz-Key wurde für andere Daten verwendet."),
                    frappe.ValidationError
                )
            return False
    except frappe.ValidationError:
        raise
    except Exception:
        pass

    # Fallback: nicht-atomar (wenn Redis nicht verfügbar)
    stored = frappe.cache().get_value(cache_key)
    if stored:
        if stored != payload_hash:
            frappe.throw(
                _("Idempotenz-Key wurde für andere Daten verwendet."),
                frappe.ValidationError
            )
        return False
    frappe.cache().set_value(cache_key, payload_hash, expires_in_sec=ttl)
    return True


def _map_action_to_audit_type(action):
    """Mappt interne Actions auf erlaubte Audit-Log-Aktionstypen."""
    mapping = {
        "write": "Profiländerung",
        "read": "Datenzugriff",
        "delete": "Dateilöschung",
        "export": "DSGVO-Export",
        "permission_change": "Berechtigungsänderung",
    }
    return mapping.get(action, "Sonstiges")


def _get_client_ip():
    """Ermittelt die Client-IP robust mit Proxy-Fallback."""
    if hasattr(frappe, "request") and frappe.request:
        forwarded = frappe.get_request_header("X-Forwarded-For", "").split(",")[0].strip()
        return forwarded or frappe.request.environ.get("REMOTE_ADDR")
    return None


def _get_user_agent():
    """Ermittelt den User-Agent robust."""
    if hasattr(frappe, "request") and frappe.request:
        return (getattr(frappe.request, "headers", {}) or {}).get("User-Agent", "")
    return None


def audit_policy_enforced(doctype, action="write"):
    """Decorator: Prüft Audit-Policies vor Ausführung und loggt das Ereignis.

    - confirm_required ohne Bestätigung → JSON-Response mit requires_confirmation
    - confirm_required mit Bestätigung → Aktion ausführen + loggen + notify
    - notify → Aktion ausführen + loggen + notify
    - audit_silent → Aktion ausführen + loggen
    - Bei Exception → loggen mit status="failed" + Exception weiterwerfen
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            actor = frappe.session.user
            target_name = kwargs.get("mitglied_id") or kwargs.get("docname") or kwargs.get("name")

            # target_user niemals vom Client akzeptieren – immer aus Doc ermitteln
            target_user = None
            if target_name and doctype:
                try:
                    target_user = frappe.db.get_value(doctype, target_name, "owner")
                except Exception:
                    pass

            confirm_reason = None
            idempotency_key = None

            # Bestätigungsobjekt aus Request extrahieren und entfernen
            confirmation = kwargs.pop("__audit_confirmation", None)
            if confirmation and isinstance(confirmation, dict):
                confirm_reason = confirmation.get("reason")
                idempotency_key = confirmation.get("idempotency_key")
                # P3: Auch in frappe.local setzen, damit DocType-Controller es sieht
                frappe.local.audit_confirmation = confirmation

            # Idempotenz-Prüfung (atomar, schnell)
            IDEMPOTENCY_CACHE_PREFIX = "diakronos:audit_idemp:"
            IDEMPOTENCY_TTL = 60
            if idempotency_key:
                cache_key = IDEMPOTENCY_CACHE_PREFIX + str(idempotency_key)
                payload_hash = hashlib.sha256(
                    json.dumps(kwargs, sort_keys=True, default=str).encode()
                ).hexdigest()
                if not _set_idempotency_key_atomic(cache_key, payload_hash, IDEMPOTENCY_TTL):
                    frappe.throw(_("Anfrage bereits verarbeitet."), frappe.ValidationError)

            # Policies laden
            policies = get_active_policies(doctype=doctype, action=action)
            triggered_policy = None
            consequence = "audit_silent"

            for policy in policies:
                if evaluate_policy(policy, actor=actor, target_user=target_user, field_name=kwargs.get("field_name")):
                    triggered_policy = policy
                    consequence = policy.get("consequence") or "audit_silent"
                    break

            # Confirmation-Handling: Wenn Bestätigung erforderlich aber nicht vorhanden
            if triggered_policy and consequence == "confirm_required":
                if not confirm_reason:
                    # Keine Bestätigung vorhanden → Frontend soll Modal anzeigen
                    return {
                        "success": False,
                        "requires_confirmation": True,
                        "policy": {
                            "policy_name": triggered_policy.get("name"),
                            "confirm_prompt": triggered_policy.get("confirm_prompt") or "Diese Aktion erfordert eine Begründung.",
                            "confirm_field_label": triggered_policy.get("confirm_field_label") or "Begründung",
                        }
                    }
                # Validierung: Bestätigung muss zur aktuell evaluierten Policy passen
                if confirmation and confirmation.get("policy_name") != triggered_policy.get("name"):
                    frappe.throw(
                        _("Bestätigungs-Policy stimmt nicht mit der aktiven Regel überein."),
                        frappe.ValidationError
                    )

            # Werte vorbereiten
            old_value = kwargs.get("old_value")
            new_value = kwargs.get("new_value")
            field_name = kwargs.get("field_name")
            data = kwargs.get("data")

            # Batch-Update: gesamte Payload als new_value loggen
            if isinstance(data, dict):
                new_value = json.dumps(data, default=str)

            # Versuche alten Wert aus Doc zu ziehen, nur wenn granularer Vergleich benötigt
            if old_value is None and target_name and doctype and field_name:
                try:
                    old_doc = frappe.get_doc(doctype, target_name)
                    if hasattr(old_doc, field_name):
                        old_value = getattr(old_doc, field_name)
                except Exception:
                    pass

            # Audit Log vorbereiten (Attempt)
            # Double-Log-Schutz: Wenn Controller bereits geloggt hat, überspringen
            if hasattr(frappe.local, "audit_log_written") and (doctype, target_name) in frappe.local.audit_log_written:
                # Controller hat bereits geloggt — Decorator nur noch für Rückwärtskompatibilität
                try:
                    result = func(*args, **kwargs)
                except Exception as e:
                    raise e
                return result

            log_doc = frappe.get_doc({
                "doctype": "Audit Log",
                "zeitstempel": now_datetime(),
                "status": "attempted",
                "action_typ": _map_action_to_audit_type(action),
                "actor": actor,
                "target_doctype": doctype,
                "target_name": target_name,
                "target_user": target_user,
                "policy_triggered": triggered_policy["name"] if triggered_policy else None,
                "consequence": consequence,
                "field_changed": field_name,
                "old_value": str(old_value)[:240] if old_value is not None else None,
                "confirm_reason": confirm_reason,
                "confirmed_at": now_datetime() if confirm_reason else None,
                "begruendung": confirm_reason or "",
                "ip_address": _get_client_ip(),
                "user_agent": _get_user_agent(),
            })

            exception = None
            try:
                result = func(*args, **kwargs)

                # Neuen Wert ermitteln, nur wenn granularer Vergleich benötigt
                if new_value is None and target_name and doctype and field_name:
                    try:
                        new_doc = frappe.get_doc(doctype, target_name)
                        if hasattr(new_doc, field_name):
                            new_value = getattr(new_doc, field_name)
                    except Exception:
                        pass

                log_doc.status = "completed"
                if new_value is not None:
                    log_doc.new_value = str(new_value)[:240]  # truncate for safety

            except Exception as e:
                log_doc.status = "failed"
                log_doc.error_message = str(e)[:240]  # truncate for safety
                exception = e

            finally:
                # Flag setzen, um Double-Logging in Hooks zu vermeiden
                frappe.local.audit_policy_logged = True
                try:
                    log_doc.insert(ignore_permissions=True)
                finally:
                    frappe.local.audit_policy_logged = False

                # Benachrichtigung asynchron senden
                if consequence in ("notify", "confirm_required") or (
                    triggered_policy and triggered_policy.get("notify_on_confirm") and confirm_reason
                ):
                    frappe.enqueue(
                        send_notification,
                        queue="short",
                        audit_log_name=log_doc.name,
                        target_user=target_user,
                    )

                if exception:
                    raise exception

            return result
        return wrapper
    return decorator
