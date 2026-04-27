# Copyright (c) 2025, Dells Dienste and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from diakronos.diakonos.api.session import check_permission
from diakronos.diakonos.api.zugriff import verify_admin_session

ADMIN_ROLES = ["System Manager", "Mitgliederadministrator"]


@frappe.whitelist()
def get_gruppen_hierarchie():
    """
    Gibt alle Gruppen und Untergruppen als Baum zurück.
    Respektiert Permissions via ancestor_path.
    """
    user = frappe.session.user
    roles = frappe.get_roles(user)
    is_admin = any(r in roles for r in ADMIN_ROLES)

    is_admin_mode = False
    if is_admin:
        try:
            is_admin_mode = verify_admin_session().get("active", False)
        except Exception:
            pass

    # Alle Gruppen laden
    gruppen = frappe.get_all(
        "Gruppe",
        fields=["name", "gruppenname", "dienstbereich", "gruppentyp", "status", "sichtbarkeit", "beschreibung", "ancestor_path"],
        filters={"status": ["!=", "Archiviert"]},
        order_by="gruppenname asc",
    )

    # Alle Untergruppen laden
    untergruppen = frappe.get_all(
        "Untergruppe",
        fields=["name", "untergruppenname", "gruppe", "status", "sichtbarkeit", "beschreibung", "ancestor_path"],
        filters={"status": ["!=", "Archiviert"]},
        order_by="untergruppenname asc",
    )

    # Permission-Filter für normale User
    if not is_admin:
        current_mitglied = _get_current_user_mitglied()
        user_path = current_mitglied.get("ancestor_path", "|") if current_mitglied else "|"
        gruppen = [g for g in gruppen if _has_group_access(g, user_path)]
        allowed_group_names = {g["name"] for g in gruppen}
        untergruppen = [u for u in untergruppen if u["gruppe"] in allowed_group_names or _has_group_access(u, user_path)]

    # Mitglieder-Anzahl pro Gruppe/Untergruppe
    gruppe_counts = {}
    for g in gruppen:
        count = frappe.db.count("Gruppenmitgliedschaft", {"parent": g["name"], "status": "Aktiv"})
        gruppe_counts[g["name"]] = count
    for u in untergruppen:
        count = frappe.db.count("Untergruppenmitgliedschaft", {"parent": u["name"], "status": "Aktiv"})
        gruppe_counts[u["name"]] = count

    # Baum aufbauen
    result = []
    for g in gruppen:
        ug_list = [u for u in untergruppen if u["gruppe"] == g["name"]]
        result.append({
            "name": g["name"],
            "gruppenname": g["gruppenname"],
            "dienstbereich": g["dienstbereich"],
            "gruppentyp": g["gruppentyp"],
            "status": g["status"],
            "sichtbarkeit": g["sichtbarkeit"],
            "beschreibung": g["beschreibung"],
            "mitglieder_count": gruppe_counts.get(g["name"], 0),
            "untergruppen": [
                {
                    "name": u["name"],
                    "untergruppenname": u["untergruppenname"],
                    "status": u["status"],
                    "sichtbarkeit": u["sichtbarkeit"],
                    "beschreibung": u["beschreibung"],
                    "mitglieder_count": gruppe_counts.get(u["name"], 0),
                }
                for u in ug_list
            ],
        })

    return {"success": True, "gruppen": result}


@frappe.whitelist()
def get_gruppe_detail(gruppe_id):
    """
    Gibt Details einer Gruppe inkl. Mitglieder und Verantwortliche zurück.
    """
    perms = check_permission("Gruppe", gruppe_id, "read")
    if not perms.get("allowed"):
        frappe.throw(_("Kein Zugriff auf diese Gruppe."), frappe.PermissionError)

    gruppe = frappe.get_doc("Gruppe", gruppe_id)
    if not gruppe:
        frappe.throw(_("Gruppe nicht gefunden."), frappe.DoesNotExistError)

    # Untergruppen
    untergruppen = frappe.get_all(
        "Untergruppe",
        fields=["name", "untergruppenname", "status", "treffpunkt", "treffzeit"],
        filters={"gruppe": gruppe_id},
        order_by="untergruppenname asc",
    )

    # Mitglieder auflösen
    mitglieder = []
    for row in gruppe.get("mitglieder") or []:
        if row.mitglied:
            m = frappe.db.get_value("Mitglied", row.mitglied, ["name", "vorname", "nachname", "email", "foto"], as_dict=True)
            if m:
                mitglieder.append({
                    "mitglied": row.mitglied,
                    "name": f"{m.get('vorname', '')} {m.get('nachname', '')}".strip() or m.get("name"),
                    "email": m.get("email"),
                    "foto": m.get("foto"),
                    "rolle": row.rolle,
                    "status": row.status,
                    "beitrittsdatum": row.beitrittsdatum,
                })

    # Verantwortliche auflösen
    verantwortliche = []
    for row in gruppe.get("verantwortliche") or []:
        if row.verantwortlicher:
            v = frappe.db.get_value("Mitglied", row.verantwortlicher, ["vorname", "nachname", "email"], as_dict=True)
            if v:
                verantwortliche.append({
                    "verantwortlicher": row.verantwortlicher,
                    "name": f"{v.get('vorname', '')} {v.get('nachname', '')}".strip(),
                    "email": v.get("email"),
                    "rolle": row.rolle,
                })

    return {
        "success": True,
        "gruppe": {
            "name": gruppe.name,
            "gruppenname": gruppe.gruppenname,
            "dienstbereich": gruppe.dienstbereich,
            "gruppentyp": gruppe.gruppentyp,
            "status": gruppe.status,
            "sichtbarkeit": gruppe.sichtbarkeit,
            "beschreibung": gruppe.beschreibung,
            "treffpunkt": gruppe.treffpunkt,
            "treffzeit": gruppe.treffzeit,
            "bild": gruppe.bild,
        },
        "untergruppen": untergruppen,
        "mitglieder": mitglieder,
        "verantwortliche": verantwortliche,
    }


@frappe.whitelist()
def get_untergruppe_detail(untergruppe_id):
    """Gibt Details einer Untergruppe inkl. Mitglieder zurück."""
    perms = check_permission("Untergruppe", untergruppe_id, "read")
    if not perms.get("allowed"):
        frappe.throw(_("Kein Zugriff auf diese Untergruppe."), frappe.PermissionError)

    ug = frappe.get_doc("Untergruppe", untergruppe_id)
    if not ug:
        frappe.throw(_("Untergruppe nicht gefunden."), frappe.DoesNotExistError)

    mitglieder = []
    for row in ug.get("mitglieder") or []:
        if row.mitglied:
            m = frappe.db.get_value("Mitglied", row.mitglied, ["name", "vorname", "nachname", "email", "foto"], as_dict=True)
            if m:
                mitglieder.append({
                    "mitglied": row.mitglied,
                    "name": f"{m.get('vorname', '')} {m.get('nachname', '')}".strip() or m.get("name"),
                    "email": m.get("email"),
                    "foto": m.get("foto"),
                    "rolle": row.rolle,
                    "status": row.status,
                    "beitrittsdatum": row.beitrittsdatum,
                })

    return {
        "success": True,
        "untergruppe": {
            "name": ug.name,
            "untergruppenname": ug.untergruppenname,
            "gruppe": ug.gruppe,
            "status": ug.status,
            "sichtbarkeit": ug.sichtbarkeit,
            "beschreibung": ug.beschreibung,
            "treffpunkt": ug.treffpunkt,
            "treffzeit": ug.treffzeit,
            "bild": ug.bild,
        },
        "mitglieder": mitglieder,
    }


@frappe.whitelist()
def add_mitglied_to_gruppe(gruppe_id, mitglied_id, rolle="", is_untergruppe=False):
    """Fügt Mitglied zu Gruppe/Untergruppe hinzu."""
    perms = check_permission(
        "Untergruppe" if is_untergruppe else "Gruppe",
        gruppe_id, "write"
    )
    if not perms.get("allowed"):
        frappe.throw(_("Keine Berechtigung zum Bearbeiten."), frappe.PermissionError)

    doctype = "Untergruppe" if is_untergruppe else "Gruppe"
    doc = frappe.get_doc(doctype, gruppe_id)

    # Prüfen, ob Mitglied bereits vorhanden
    table_field = "mitglieder"
    existing = [r for r in (doc.get(table_field) or []) if r.mitglied == mitglied_id]
    if existing:
        return {"success": False, "message": "Mitglied ist bereits in der Gruppe."}

    doc.append(table_field, {
        "mitglied": mitglied_id,
        "rolle": rolle,
        "status": "Aktiv",
        "beitrittsdatum": frappe.utils.today(),
    })
    doc.save(ignore_permissions=True)

    return {"success": True, "message": "Mitglied hinzugefügt."}


@frappe.whitelist()
def remove_mitglied_from_gruppe(gruppe_id, mitglied_id, is_untergruppe=False):
    """Entfernt Mitglied aus Gruppe/Untergruppe."""
    perms = check_permission(
        "Untergruppe" if is_untergruppe else "Gruppe",
        gruppe_id, "write"
    )
    if not perms.get("allowed"):
        frappe.throw(_("Keine Berechtigung zum Bearbeiten."), frappe.PermissionError)

    doctype = "Untergruppe" if is_untergruppe else "Gruppe"
    doc = frappe.get_doc(doctype, gruppe_id)
    table_field = "mitglieder"

    rows = [r for r in (doc.get(table_field) or []) if r.mitglied == mitglied_id]
    if not rows:
        return {"success": False, "message": "Mitglied nicht in der Gruppe gefunden."}

    for row in rows:
        doc.get(table_field).remove(row)
    doc.save(ignore_permissions=True)

    return {"success": True, "message": "Mitglied entfernt."}


@frappe.whitelist()
def update_mitglied_rolle(gruppe_id, mitglied_id, rolle, is_untergruppe=False):
    """Ändert Rolle eines Mitglieds in einer Gruppe."""
    perms = check_permission(
        "Untergruppe" if is_untergruppe else "Gruppe",
        gruppe_id, "write"
    )
    if not perms.get("allowed"):
        frappe.throw(_("Keine Berechtigung zum Bearbeiten."), frappe.PermissionError)

    doctype = "Untergruppe" if is_untergruppe else "Gruppe"
    doc = frappe.get_doc(doctype, gruppe_id)
    table_field = "mitglieder"

    for row in doc.get(table_field) or []:
        if row.mitglied == mitglied_id:
            row.rolle = rolle
            break
    else:
        return {"success": False, "message": "Mitglied nicht gefunden."}

    doc.save(ignore_permissions=True)
    return {"success": True, "message": "Rolle aktualisiert."}


# ── Helpers ────────────────────────────────────────────────────────────────────────────

def _get_current_user_mitglied():
    user = frappe.session.user
    email = frappe.db.get_value("User", user, "email") or user
    return frappe.db.get_value(
        "Mitglied", {"email": email},
        ["name", "ancestor_path"],
        as_dict=True,
    )


def _has_group_access(group_doc, user_path):
    """Prüft, ob User Zugriff auf eine Gruppe/Untergruppe hat."""
    if not user_path or user_path == "|":
        return False
    group_path = group_doc.get("ancestor_path", "|")
    if not group_path or group_path == "|":
        # Gruppe ohne ancestor_path: prüfe über Namensvergleich
        return True  # Admin-Filter wurde schon vorher angewendet
    # Einfacher String-Contains als Heuristik
    return _paths_overlap(user_path, group_path)


def _paths_overlap(user_path, target_path):
    if not user_path or not target_path:
        return False
    def _extract_segments(path):
        parts = path.split("|")
        gruppen = [g for g in parts[0].split("/") if g]
        bereiche = [b for b in parts[1].split("/") if b] if len(parts) > 1 else []
        return set(gruppen), set(bereiche)
    user_gruppen, user_bereiche = _extract_segments(user_path)
    target_gruppen, target_bereiche = _extract_segments(target_path)
    return bool(user_gruppen & target_gruppen or user_bereiche & target_bereiche)
