# Copyright (c) 2026, Dells Dienste and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime
from diakronos.diakonos.api.audit import log


class Anmeldung(Document):

    def before_insert(self):
        if not self.dsgvo_zustimmung:
            frappe.throw("DSGVO-Einwilligung ist erforderlich.", title="Datenschutz")

    def on_update(self):
        """Wenn Admin auf 'Bestätigt' setzt → Mitglied + DSGVO Einwilligung anlegen."""
        if self.status == "Bestätigt" and not self.verarbeitet:
            self._create_mitglied_und_dsgvo()

    # ── Mitglied + DSGVO anlegen ─────────────────────────────────────────────────

    def _create_mitglied_und_dsgvo(self):
        mitglied_status = (
            "Mitglied" if self.anmeldungstyp == "Mitglied-Registrierung" else "Gast"
        )

        mitglied = frappe.get_doc({
            "doctype":       "Mitglied",
            "vorname":       self.vorname,
            "nachname":      self.nachname,
            "email":         self.email or "",
            "telefonnummer": self.telefon or "",
            "geburtstag":    self.geburtstag or None,
            "status":        mitglied_status,
        })
        mitglied.insert(ignore_permissions=True)

        dsgvo_zeitstempel = now_datetime()
        frappe.get_doc({
            "doctype":           "DSGVO Einwilligung",
            "mitglied":          mitglied.name,
            "zeitstempel":       dsgvo_zeitstempel,
            "einwilligungstext": self.dsgvo_text_snapshot or _dsgvo_standardtext(),
            "ip_adresse":        self.ip_adresse or "",
            "widerrufen":        0,
        }).insert(ignore_permissions=True)

        frappe.db.set_value(
            "Mitglied", mitglied.name,
            {
                "datenschutz_einwilligung": 1,
                "datenschutz_datum": str(dsgvo_zeitstempel)[:10],
            },
            update_modified=False,
        )

        log(
            action_typ="Profiländerung",
            target_doctype="Mitglied",
            target_name=mitglied.name,
            begruendung=f"Mitglied aus Anmeldung {self.name} bestätigt (Typ: {self.anmeldungstyp})",
        )

        frappe.db.set_value("Anmeldung", self.name, {
            "mitglied":    mitglied.name,
            "verarbeitet": 1,
        }, update_modified=False)

        self._notify_mitgliederadmin(mitglied.name)

    def _notify_mitgliederadmin(self, mitglied_name):
        admins = frappe.get_all(
            "Has Role",
            filters={"role": "Mitgliederadministrator", "parenttype": "User"},
            pluck="parent",
        )
        for user in admins:
            frappe.get_doc({
                "doctype":       "Notification Log",
                "subject":       f"Mitglied angelegt: {self.vorname} {self.nachname}",
                "email_content": (
                    f"Anmeldung <b>{self.name}</b> bestätigt.<br>"
                    f"Mitglied: <b>{mitglied_name}</b>"
                ),
                "for_user":      user,
                "document_type": "Mitglied",
                "document_name": mitglied_name,
                "type":          "Alert",
            }).insert(ignore_permissions=True)


def _dsgvo_standardtext():
    return (
        "Ich willige ein, dass meine personenbezogenen Daten (Name, Kontaktdaten) "
        "zum Zweck der Mitgliederverwaltung gemäß Art. 6 Abs. 1 lit. a DSGVO "
        "gespeichert und verarbeitet werden. Die Einwilligung kann jederzeit "
        "widerrufen werden."
    )
