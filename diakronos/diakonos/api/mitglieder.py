# Copyright (c) 2025, Dells Dienste and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _

from diakronos.diakonos.api.session import get_mitglied_permissions
from diakronos.diakonos.api.audit_policy.decorator import audit_policy_enforced

ADMIN_ROLES = ["System Manager", "Mitgliederadministrator"]


# ── Liste / Übersicht ───────────────────────────────────────────────────────

@frappe.whitelist()
def get_mitglieder_liste(start=0, limit=20, suche="", status="", sort_by="name", sort_order="asc"):
    """
    Gibt paginierte Mitglieder-Liste zurück.
    Respektiert Permissions: Admin sieht alle, User nur eigene Gruppe/Bereich.
    """
    user = frappe.session.user
    roles = frappe.get_roles(user)
    is_admin = any(r in roles for r in ADMIN_ROLES)

    # Sortierung validieren (SQL-Injection-Schutz)
    allowed_sort_fields = {
        "name", "vorname", "nachname", "email", "status",
        "geburtstag", "wohnort", "postleitzahl", "creation", "modified"
    }
    if sort_by not in allowed_sort_fields:
        sort_by = "name"
    sort_order = "desc" if sort_order.lower() == "desc" else "asc"

    params = {
        "start": int(start),
        "limit": int(limit),
        "suche": f"%{suche}%" if suche else "%%",
    }

    filters_sql = ""
    if status:
        filters_sql += " AND m.status = %(status)s"
        params["status"] = status

    # Permission-Filter
    permission_filter_sql = "1=1"
    if not is_admin:
        # Normaler User: nur überlappende ancestor_paths
        current_mitglied = _get_current_user_mitglied()
        if current_mitglied and current_mitglied.get("ancestor_path"):
            segments = _extract_path_segments(current_mitglied["ancestor_path"])
            if segments:
                like_clauses = []
                for idx, seg in enumerate(segments):
                    key = f"seg_{idx}"
                    like_clauses.append(f"CONCAT('/', COALESCE(m.ancestor_path, ''), '/') LIKE %({key})s")
                    params[key] = f"%/{seg}/%"
                permission_filter_sql = "(" + " OR ".join(like_clauses) + ")"
            else:
                # User hat Pfad aber keine Segmente → Fallback auf eigenes Profil
                user_email = frappe.db.get_value("User", user, "email") or user
                permission_filter_sql = "m.email = %(user_email)s"
                params["user_email"] = user_email
        else:
            # User ohne ancestor_path: nur eigenes Profil via Email-Match
            user_email = frappe.db.get_value("User", user, "email") or user
            permission_filter_sql = "m.email = %(user_email)s"
            params["user_email"] = user_email

    query = f"""
        SELECT
            m.name,
            m.vorname,
            m.nachname,
            CONCAT_WS(' ', NULLIF(m.vorname, ''), NULLIF(m.nachname, '')) as full_name,
            m.email,
            m.status,
            m.foto,
            m.telefonnummer,
            m.geburtstag,
            m.postleitzahl,
            m.wohnort,
            m.straße,
            m.nummer,
            m.geschlecht,
            m.familienstand,
            m.ancestor_path
        FROM `tabMitglied` m
        WHERE 1=1
          AND (
              m.vorname LIKE %(suche)s
              OR m.nachname LIKE %(suche)s
              OR m.email LIKE %(suche)s
          )
          {filters_sql}
          AND {permission_filter_sql}
        ORDER BY m.`{sort_by}` {sort_order}
        LIMIT %(start)s, %(limit)s
    """

    data = frappe.db.sql(query, params, as_dict=True)

    # Total-Count für Pagination
    count_query = f"""
        SELECT COUNT(*) as total
        FROM `tabMitglied` m
        WHERE 1=1
          AND (
              m.vorname LIKE %(suche)s
              OR m.nachname LIKE %(suche)s
              OR m.email LIKE %(suche)s
          )
          {filters_sql}
          AND {permission_filter_sql}
    """
    total_result = frappe.db.sql(count_query, params, as_dict=True)
    total = total_result[0].total if total_result else 0

    return {
        "success": True,
        "data": data,
        "total": total,
        "start": int(start),
        "limit": int(limit),
    }


# ── Erstellen ───────────────────────────────────────────────────────────────

@frappe.whitelist()
def create_mitglied(vorname, nachname, email="", status="Gast", gruppe_id=None, create_user=False):
    """
    Legt ein neues Mitglied an.
    Optionen:
      - gruppe_id: fügt das Mitglied direkt einer Gruppe hinzu
      - create_user: legt gleichzeitig einen Frappe-Website-User an (benötigt E-Mail)
    """
    roles = frappe.get_roles(frappe.session.user)
    if not any(r in roles for r in ADMIN_ROLES):
        frappe.throw(_("Nur Administratoren dürfen Mitglieder anlegen."), frappe.PermissionError)

    vorname = (vorname or "").strip()
    nachname = (nachname or "").strip()
    email = (email or "").strip().lower()

    if not vorname or not nachname:
        frappe.throw(_("Vor- und Nachname sind Pflichtfelder."), frappe.ValidationError)

    if frappe.utils.cint(create_user) and not email:
        frappe.throw(_("Eine E-Mail-Adresse wird benötigt um einen Login-Account anzulegen."), frappe.ValidationError)

    valid_statuses = {"Mitglied", "Gast", "Passiver Gast", "Passives Mitglied"}
    if status not in valid_statuses:
        status = "Gast"

    doc = frappe.get_doc({
        "doctype": "Mitglied",
        "vorname": vorname,
        "nachname": nachname,
        "email": email or None,
        "status": status,
    })
    doc.insert(ignore_permissions=True)

    if gruppe_id:
        try:
            from diakronos.diakonos.api.gruppen import add_mitglied_to_gruppe
            add_mitglied_to_gruppe(gruppe_id=gruppe_id, mitglied_id=doc.name, rolle="Mitglied", is_untergruppe=False)
        except Exception as e:
            frappe.log_error(f"Gruppe-Zuweisung fehlgeschlagen: {e}", "create_mitglied")

    if frappe.utils.cint(create_user) and email:
        from diakronos.diakonos.api.nutzer import mitglied_zu_nutzer
        mitglied_zu_nutzer(doc)

    frappe.db.commit()

    return {
        "success": True,
        "mitglied_id": doc.name,
        "mitglied_name": f"{vorname} {nachname}",
    }


# ── Detail ──────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_mitglied_detail(mitglied_id):
    """
    Gibt vollständige Details eines Mitglieds zurück.
    Inklusive Child-Tables: bereiche, beziehungen, gruppenmitgliedschaften.
    Prüft Permissions via session.get_mitglied_permissions().
    """
    perms = get_mitglied_permissions(mitglied_id)
    if not perms.get("can_view"):
        frappe.throw(_("Kein Zugriff"), frappe.PermissionError)

    doc = frappe.get_doc("Mitglied", mitglied_id)
    result = doc.as_dict()

    # Gruppenmitgliedschaften explizit anreichern (falls nicht in as_dict)
    gruppenmitgliedschaften = frappe.get_all(
        "Gruppenmitgliedschaft",
        filters={"mitglied": mitglied_id},
        fields=["name", "parent as gruppe", "rolle", "beitrittsdatum", "status"],
    )
    for g in gruppenmitgliedschaften:
        g["gruppenname"] = frappe.db.get_value("Gruppe", g.get("gruppe"), "gruppenname")
    result["gruppenmitgliedschaften"] = gruppenmitgliedschaften

    return {
        "success": True,
        "data": result,
        "permissions": perms,
    }


# ── Update ──────────────────────────────────────────────────────────────────

@frappe.whitelist()
def update_mitglied(mitglied_id, data, **kwargs):
    """
    Aktualisiert ein Mitglied.
    Audit-Policy wird vom DocType-Controller (Mitglied.validate/on_update) verwaltet.
    """
    perms = get_mitglied_permissions(mitglied_id)
    if not perms.get("can_edit"):
        frappe.throw(_("Kein Zugriff"), frappe.PermissionError)

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            frappe.throw(_("Ungültiges JSON-Format im Parameter 'data'."), frappe.ValidationError)

    doc = frappe.get_doc("Mitglied", mitglied_id)

    # Erlaubte Felder zur Aktualisierung (Whitelist)
    allowed_fields = {
        "vorname", "nachname", "email", "telefonnummer", "geburtstag",
        "postleitzahl", "wohnort", "straße", "nummer", "geschlecht",
        "familienstand", "foto", "datenschutz_einwilligung", "status"
    }

    # Alias-Mapping: Frontend-Namen → DocType-Namen
    field_aliases = {
        "telefon": "telefonnummer",
        "strasse": "straße",
        "hausnummer": "nummer",
        "plz": "postleitzahl",
        "ort": "wohnort",
    }

    updated = False
    for key, value in data.items():
        mapped_key = field_aliases.get(key, key)
        if mapped_key in allowed_fields and hasattr(doc, mapped_key):
            setattr(doc, mapped_key, value)
            updated = True

    if updated:
        doc.save()

    return {
        "success": True,
        "message": _("Mitglied aktualisiert."),
        "mitglied_id": doc.name,
    }


@frappe.whitelist()
def update_mitglied_with_confirmation(mitglied_id, data, audit_confirmation):
    """
    Aktualisiert ein Mitglied MIT Audit-Bestätigung.
    Setzt frappe.local.audit_confirmation vor dem Save, damit der Controller
    die Bestätigung in validate() vorfindet.
    """
    perms = get_mitglied_permissions(mitglied_id)
    if not perms.get("can_edit"):
        frappe.throw(_("Kein Zugriff"), frappe.PermissionError)

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            frappe.throw(_("Ungültiges JSON-Format im Parameter 'data'."), frappe.ValidationError)

    if isinstance(audit_confirmation, str):
        try:
            audit_confirmation = json.loads(audit_confirmation)
        except json.JSONDecodeError:
            frappe.throw(_("Ungültiges JSON-Format in audit_confirmation."), frappe.ValidationError)

    # Bestätigung in frappe.local setzen (wird von Mitglied.validate() gelesen)
    frappe.local.audit_confirmation = audit_confirmation

    try:
        doc = frappe.get_doc("Mitglied", mitglied_id)

        allowed_fields = {
            "vorname", "nachname", "email", "telefonnummer", "geburtstag",
            "postleitzahl", "wohnort", "straße", "nummer", "geschlecht",
            "familienstand", "foto", "datenschutz_einwilligung", "status"
        }
        field_aliases = {
            "telefon": "telefonnummer",
            "strasse": "straße",
            "hausnummer": "nummer",
            "plz": "postleitzahl",
            "ort": "wohnort",
        }

        updated = False
        for key, value in data.items():
            mapped_key = field_aliases.get(key, key)
            if mapped_key in allowed_fields and hasattr(doc, mapped_key):
                setattr(doc, mapped_key, value)
                updated = True

        if updated:
            doc.save()
    finally:
        if hasattr(frappe.local, "audit_confirmation"):
            del frappe.local.audit_confirmation

    return {
        "success": True,
        "message": _("Mitglied aktualisiert."),
        "mitglied_id": doc.name,
    }


# ── Gruppen ─────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_gruppen_for_mitglied(mitglied_id):
    """Gibt alle Gruppen zurück, in denen das Mitglied ist."""
    perms = get_mitglied_permissions(mitglied_id)
    if not perms.get("can_view"):
        frappe.throw(_("Kein Zugriff"), frappe.PermissionError)

    # Explizite Gruppenmitgliedschaften
    gruppen = frappe.get_all(
        "Gruppenmitgliedschaft",
        filters={"mitglied": mitglied_id},
        fields=["name", "parent as gruppe", "rolle", "beitrittsdatum", "status"],
    )
    for g in gruppen:
        g["gruppenname"] = frappe.db.get_value("Gruppe", g.get("gruppe"), "gruppenname")

    # Zusätzlich aus ancestor_path parsen (ergänzend)
    mitglied = frappe.db.get_value(
        "Mitglied", mitglied_id, ["ancestor_path"], as_dict=True
    )
    if mitglied and mitglied.get("ancestor_path"):
        parts = mitglied["ancestor_path"].split("|")
        gruppen_segmente = [g for g in parts[0].split("/") if g] if parts else []
        for seg in gruppen_segmente:
            if not any(g.get("gruppe") == seg for g in gruppen):
                gruppen.append({
                    "gruppe": seg,
                    "rolle": None,
                    "source": "ancestor_path",
                })

    return {
        "success": True,
        "data": gruppen,
    }


# ── Beziehungen ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_beziehungen_for_mitglied(mitglied_id):
    """Gibt alle Beziehungen eines Mitglieds zurück."""
    perms = get_mitglied_permissions(mitglied_id)
    if not perms.get("can_view"):
        frappe.throw(_("Kein Zugriff"), frappe.PermissionError)

    beziehungen = frappe.get_all(
        "Mitglied Beziehung",
        filters={"parent": mitglied_id, "parenttype": "Mitglied"},
        fields=["*"],
        order_by="idx asc",
    )

    return {
        "success": True,
        "data": beziehungen,
    }


# ── DSGVO ───────────────────────────────────────────────────────────────────

@frappe.whitelist()
def widerruf_einwilligung(mitglied_id, **kwargs):
    """
    Widerruft die DSGVO-Einwilligung eines Mitglieds.
    Audit-Policy wird vom DocType-Controller (Mitglied.validate/on_update) verwaltet.
    """
    from diakronos.diakonos.api.session import get_mitglied_permissions
    perms = get_mitglied_permissions(mitglied_id)
    if not perms.get("can_edit"):
        frappe.throw(_("Kein Zugriff"), frappe.PermissionError)

    # Bestätigung an Controller weitergeben (P3-Migration)
    confirmation = kwargs.pop("__audit_confirmation", None)
    if confirmation:
        frappe.local.audit_confirmation = confirmation

    doc = frappe.get_doc("Mitglied", mitglied_id)
    doc.datenschutz_einwilligung = 0
    doc.datenschutz_datum = None
    doc.save()

    return {
        "success": True,
        "message": _("Einwilligung widerrufen."),
    }


# ── Helpers ─────────────────────────────────────────────────────────────────

def _get_current_user_mitglied():
    """Holt den Mitglied-Datensatz des aktuellen Users."""
    user = frappe.session.user
    email = frappe.db.get_value("User", user, "email") or user
    return frappe.db.get_value(
        "Mitglied", {"email": email},
        ["name", "ancestor_path", "email", "status"],
        as_dict=True,
    )


def _extract_path_segments(path):
    """Extrahiert alle Gruppen- und Bereichs-Segmente aus einem ancestor_path."""
    if not path:
        return []
    parts = path.split("|")
    gruppen = [g for g in parts[0].split("/") if g]
    bereiche = [b for b in parts[1].split("/") if b] if len(parts) > 1 else []
    return gruppen + bereiche
