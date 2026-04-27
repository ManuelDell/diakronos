# Copyright (c) 2025, Dells Dienste and contributors
# For license information, please see license.txt

import json
import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, now_datetime
from frappe import _

from diakronos.diakonos.api.audit_policy.engine import get_active_policies, evaluate_policy
from diakronos.diakonos.api.audit_policy.notifications import send_notification


class AuditConfirmationRequired(frappe.ValidationError):
    """Wird geworfen wenn eine Audit-Policy eine Bestätigung verlangt."""
    pass


# Inverse relationship map: wenn A→B vom Typ X, dann B→A hat Typ Y
_INVERSE = {
    "Elternteil": "Kind",
    "Kind":       "Elternteil",
    "Ehepartner": "Ehepartner",
    "Geschwister": "Geschwister",
    "Sonstiges":   "Sonstiges",
}


_DSGVO_FIELDS = {
    "datenschutz_einwilligung", "email", "telefonnummer", "vorname",
    "nachname", "geburtstag", "postleitzahl", "wohnort", "straße",
    "nummer", "geschlecht", "familienstand", "foto", "status"
}


def _map_action_to_audit_type(action):
    mapping = {
        "write": "Profiländerung",
        "read": "Datenzugriff",
        "delete": "Dateilöschung",
        "export": "DSGVO-Export",
        "permission_change": "Berechtigungsänderung",
    }
    return mapping.get(action, "Sonstiges")


def _get_client_ip():
    if hasattr(frappe, "request") and frappe.request:
        forwarded = frappe.get_request_header("X-Forwarded-For", "").split(",")[0].strip()
        return forwarded or frappe.request.environ.get("REMOTE_ADDR")
    return None


def _get_user_agent():
    if hasattr(frappe, "request") and frappe.request:
        return (getattr(frappe.request, "headers", {}) or {}).get("User-Agent", "")
    return None


class Mitglied(Document):

    def validate(self):
        # Nur bei Updates (nicht bei Neuanlage)
        if self.is_new():
            return
        # Interne Kaskaden-Aufrufe (z.B. _sync_beziehungen) überspringen
        skip_set = getattr(frappe.local, "audit_skip", None)
        if skip_set and self.name in skip_set:
            return
        self._check_audit_policies()

    def before_save(self):
        self._set_ancestor_path()

    def on_update(self):
        self._write_audit_log()
        self._sync_beziehungen()
        self._sync_dsgvo_status()

    def on_trash(self):
        self._delete_anhaenge()

    # ── Audit Policy Layer (DocType-Controller) ──────────────────────────────

    def _check_audit_policies(self):
        """Prüft Audit-Policies für geänderte Felder in validate()."""
        changed_fields = []
        old_values = {}  # old_value für on_update() merken
        for field in _DSGVO_FIELDS:
            try:
                old_val = self.get_db_value(field)
                new_val = getattr(self, field, None)
                if old_val != new_val:
                    changed_fields.append(field)
                    old_values[field] = old_val
            except Exception:
                pass

        if not changed_fields:
            return

        # Policies laden
        policies = get_active_policies(doctype="Mitglied", action="write")
        if not policies:
            return

        actor = frappe.session.user
        target_user = self.owner
        triggered = None
        consequence = "audit_silent"
        confirm_reason = None

        # Bestätigung aus Request extrahieren
        confirmation = getattr(frappe.local, "audit_confirmation", None)

        for field in changed_fields:
            for policy in policies:
                if evaluate_policy(policy, actor=actor, target_user=target_user, field_name=field):
                    triggered = policy
                    consequence = policy.get("consequence") or "audit_silent"
                    break
            if triggered:
                break

        if triggered and consequence == "confirm_required":
            if not confirmation or confirmation.get("policy_name") != triggered.get("name"):
                policy_json = json.dumps({
                    "policy_name": triggered.get("name"),
                    "confirm_prompt": triggered.get("confirm_prompt") or "Diese Änderung erfordert eine Begründung.",
                    "confirm_field_label": triggered.get("confirm_field_label") or "Begründung",
                })
                frappe.throw(
                    f"CONFIRM_REQUIRED:{policy_json}",
                    exc=AuditConfirmationRequired,
                    title=_("Bestätigung erforderlich")
                )
            confirm_reason = confirmation.get("reason")

        # Für on_update() merken
        self._audit_triggered = triggered
        self._audit_consequence = consequence
        self._audit_changed_fields = changed_fields
        self._audit_old_values = old_values
        self._audit_confirm_reason = confirm_reason
        self._audit_actor = actor
        self._audit_target_user = target_user

    def _write_audit_log(self):
        """Schreibt Audit-Log in on_update() — atomar in derselben Transaktion."""
        triggered = getattr(self, "_audit_triggered", None)
        if not triggered:
            return

        # Double-Log-Schutz (wenn Decorator bereits geloggt hat)
        if not hasattr(frappe.local, "audit_log_written"):
            frappe.local.audit_log_written = set()
        log_key = ("Mitglied", self.name)
        if log_key in frappe.local.audit_log_written:
            return
        frappe.local.audit_log_written.add(log_key)

        field_name = self._audit_changed_fields[0] if self._audit_changed_fields else None
        old_value = self._audit_old_values.get(field_name) if field_name else None
        new_value = getattr(self, field_name, None) if field_name else None

        log_doc = frappe.get_doc({
            "doctype": "Audit Log",
            "zeitstempel": now_datetime(),
            "status": "completed",
            "action_typ": _map_action_to_audit_type("write"),
            "actor": self._audit_actor,
            "target_doctype": "Mitglied",
            "target_name": self.name,
            "target_user": self._audit_target_user,
            "policy_triggered": triggered.get("name"),
            "consequence": self._audit_consequence,
            "field_changed": field_name,
            "old_value": str(old_value)[:240] if old_value is not None else None,
            "new_value": str(new_value)[:240] if new_value is not None else None,
            "confirm_reason": self._audit_confirm_reason,
            "confirmed_at": now_datetime() if self._audit_confirm_reason else None,
            "begruendung": self._audit_confirm_reason or "",
            "ip_address": _get_client_ip(),
            "user_agent": _get_user_agent(),
        })
        try:
            frappe.local.audit_policy_logged = True
            log_doc.insert(ignore_permissions=True)
        finally:
            frappe.local.audit_policy_logged = False

        # Notification asynchron senden
        if self._audit_consequence in ("notify", "confirm_required") or (
            triggered.get("notify_on_confirm") and self._audit_confirm_reason
        ):
            frappe.enqueue(
                send_notification,
                queue="short",
                audit_log_name=log_doc.name,
                target_user=self._audit_target_user,
            )

    # ── DSGVO-Status ────────────────────────────────────────────────────────────

    def _sync_dsgvo_status(self):
        """Setzt datenschutz_einwilligung/datum basierend auf aktiver DSGVO Einwilligung."""
        aktiv = frappe.db.get_value(
            "DSGVO Einwilligung",
            {"mitglied": self.name, "widerrufen": 0},
            ["name", "zeitstempel"],
            order_by="zeitstempel desc",
            as_dict=True,
        )
        hat_einwilligung = bool(aktiv)
        datum = str(aktiv.zeitstempel)[:10] if aktiv else None

        frappe.db.set_value(
            "Mitglied", self.name,
            {
                "datenschutz_einwilligung": 1 if hat_einwilligung else 0,
                "datenschutz_datum": datum,
            },
            update_modified=False,
        )

    # ── Bidirektionale Beziehungen ───────────────────────────────────────────────

    def _sync_beziehungen(self):
        """Hält Beziehungen bidirektional konsistent."""
        # Rekursionsschutz: verhindert Endlosschleifen bei zirkulären Beziehungen
        if not hasattr(frappe.local, "_sync_beziehungen_active"):
            frappe.local._sync_beziehungen_active = set()
        if self.name in frappe.local._sync_beziehungen_active:
            return
        frappe.local._sync_beziehungen_active.add(self.name)
        try:
            for row in self.get("beziehungen") or []:
                if row.ist_spiegel:
                    continue
                ziel_name = row.beziehung_zu
                if not ziel_name or ziel_name == self.name:
                    continue
                inv_typ = _INVERSE.get(row.beziehungstyp, "Sonstiges")
                self._ensure_mirror(ziel_name, self.name, inv_typ)
        finally:
            frappe.local._sync_beziehungen_active.discard(self.name)
            if not frappe.local._sync_beziehungen_active:
                del frappe.local._sync_beziehungen_active

    def _ensure_mirror(self, elternteil_name, kind_name, inv_typ):
        ziel = frappe.get_doc("Mitglied", elternteil_name)
        existing = [
            r for r in (ziel.get("beziehungen") or [])
            if r.beziehung_zu == kind_name and r.ist_spiegel
        ]
        # Pro-Dokument audit_skip statt globalem Boolean
        if not hasattr(frappe.local, "audit_skip"):
            frappe.local.audit_skip = set()
        frappe.local.audit_skip.add(ziel.name)
        try:
            if existing:
                if existing[0].beziehungstyp != inv_typ:
                    existing[0].beziehungstyp = inv_typ
                    ziel.save(ignore_permissions=True)
                return
            ziel.append("beziehungen", {
                "beziehung_zu": kind_name,
                "beziehungstyp": inv_typ,
                "ist_spiegel": 1,
            })
            ziel.save(ignore_permissions=True)
        finally:
            frappe.local.audit_skip.discard(ziel.name)
            if not frappe.local.audit_skip:
                del frappe.local.audit_skip

    # ── Cascade-Delete ──────────────────────────────────────────────────────────

    def _delete_anhaenge(self):
        for name in frappe.get_all("Sicherer Anhang", filters={"mitglied": self.name}, pluck="name"):
            frappe.delete_doc("Sicherer Anhang", name, ignore_permissions=True, force=True)

    # ── Ancestor Path ───────────────────────────────────────────────────────────

    def _set_ancestor_path(self):
        """Berechnet den ancestor_path aus Gruppen-, Untergruppen- und Bereichszuordnungen."""
        bereiche = []
        for row in self.get("bereiche") or []:
            if row.get("dienstbereich"):
                bereiche.append(row.dienstbereich)

        gruppen = []
        if self.name:
            gruppen = frappe.get_all(
                "Gruppenmitgliedschaft",
                filters={"mitglied": self.name},
                pluck="parent",
            ) or []
            untergruppen = frappe.get_all(
                "Untergruppenmitgliedschaft",
                filters={"mitglied": self.name},
                pluck="parent",
            ) or []
            gruppen = gruppen + untergruppen

        gruppen = sorted(set(gruppen))
        bereiche = sorted(set(bereiche))

        gruppen_pfad = "/" + "/".join(gruppen) + "/" if gruppen else "/"
        bereich_pfad = "/" + "/".join(bereiche) + "/" if bereiche else "/"

        self.ancestor_path = f"{gruppen_pfad}|{bereich_pfad}"
