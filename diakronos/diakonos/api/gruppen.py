# Copyright (c) 2025, Dells Dienste and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from diakronos.diakonos.api.session import check_permission

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

    aufgaben = frappe.get_all(
        "Gruppen Aufgabe",
        filters={"gruppe": gruppe_id, "untergruppe": ["", None]},
        fields=["name", "titel", "erledigt", "faellig"],
        order_by="erledigt asc, creation asc",
        ignore_permissions=True,
    )
    ankuendigungen = frappe.get_all(
        "Gruppen Ankuendigung",
        filters={"gruppe": gruppe_id, "untergruppe": ["", None]},
        fields=["name", "titel", "text", "pinned", "creation"],
        order_by="pinned desc, creation desc",
        ignore_permissions=True,
    )
    wiki_artikel = []
    if frappe.db.has_column("Wiki Artikel", "gruppe"):
        wiki_artikel = frappe.get_all(
            "Wiki Artikel",
            filters={"gruppe": gruppe_id},
            fields=["name", "titel"],
            limit=5,
            ignore_permissions=True,
        )
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
        "aufgaben": aufgaben,
        "ankuendigungen": ankuendigungen,
        "wiki_artikel": wiki_artikel,
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

    aufgaben_ug = frappe.get_all(
        "Gruppen Aufgabe",
        filters={"untergruppe": untergruppe_id},
        fields=["name", "titel", "erledigt", "faellig"],
        order_by="erledigt asc, creation asc",
        ignore_permissions=True,
    )
    ankuendigungen_ug = frappe.get_all(
        "Gruppen Ankuendigung",
        filters={"untergruppe": untergruppe_id},
        fields=["name", "titel", "text", "pinned", "creation"],
        order_by="pinned desc, creation desc",
        ignore_permissions=True,
    )
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
        "aufgaben": aufgaben_ug,
        "ankuendigungen": ankuendigungen_ug,
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


@frappe.whitelist()
def get_gruppen_for_orgchart():
	"""Gibt Dienstbereiche, Gruppen und Untergruppen als flaches Array für d3-org-chart zurück."""
	gruppen_result = get_gruppen_hierarchie()
	gruppen_list = gruppen_result.get("gruppen", [])

	dienstbereiche = frappe.get_all(
		"Dienstbereich",
		fields=["name", "ministry", "farbe", "icon", "beschreibung"],
		order_by="sortierung asc, ministry asc",
	)

	untergruppen = frappe.get_all(
		"Untergruppe",
		fields=["name", "untergruppenname", "gruppe", "status", "beschreibung"],
		filters={"status": ["!=", "Archiviert"]},
		order_by="untergruppenname asc",
	)

	ug_counts = {}
	for u in untergruppen:
		ug_counts[u["name"]] = frappe.db.count("Untergruppenmitgliedschaft", {"parent": u["name"], "status": "Aktiv"})

	nodes = [{"id": "virtual-root", "parentId": None, "name": "", "type": "root"}]

	db_names = {db["name"] for db in dienstbereiche}
	for db in dienstbereiche:
		nodes.append({
			"id": f"db_{db['name']}",
			"parentId": "virtual-root",
			"name": db["ministry"],
			"type": "dienstbereich",
			"raw_name": db["name"],
			"farbe": db.get("farbe") or "#667eea",
			"icon": db.get("icon") or "",
			"beschreibung": db.get("beschreibung") or "",
		})

	gruppe_extra = {g["name"]: g for g in frappe.get_all(
		"Gruppe",
		fields=["name", "treffpunkt", "treffzeit"],
	)}

	gruppe_names = set()
	for g in gruppen_list:
		if not g.get("dienstbereich") or g["dienstbereich"] not in db_names:
			continue
		gruppe_names.add(g["name"])
		extra = gruppe_extra.get(g["name"], {})
		nodes.append({
			"id": f"g_{g['name']}",
			"parentId": f"db_{g['dienstbereich']}",
			"name": g["gruppenname"],
			"type": "gruppe",
			"raw_name": g["name"],
			"mitglieder_count": g.get("mitglieder_count", 0),
			"beschreibung": g.get("beschreibung") or "",
			"treffpunkt": extra.get("treffpunkt") or "",
			"treffzeit": extra.get("treffzeit") or "",
		})

	ug_extra = {u["name"]: u for u in frappe.get_all(
		"Untergruppe",
		fields=["name", "treffpunkt", "treffzeit"],
	)}

	for u in untergruppen:
		if not u.get("gruppe") or u["gruppe"] not in gruppe_names:
			continue
		extra = ug_extra.get(u["name"], {})
		nodes.append({
			"id": f"ug_{u['name']}",
			"parentId": f"g_{u['gruppe']}",
			"name": u["untergruppenname"],
			"type": "untergruppe",
			"raw_name": u["name"],
			"mitglieder_count": ug_counts.get(u["name"], 0),
			"beschreibung": u.get("beschreibung") or "",
			"treffpunkt": extra.get("treffpunkt") or "",
			"treffzeit": extra.get("treffzeit") or "",
		})

	return {"success": True, "nodes": nodes}


@frappe.whitelist()
def get_user_create_permissions():
	"""Gibt zurück, welche Strukturen der aktuelle User erstellen darf."""
	user = frappe.session.user
	roles = frappe.get_roles(user)
	is_admin = any(r in roles for r in ["System Manager", "Mitgliederadministrator"])

	result = {
		"can_create_dienstbereich": False,
		"can_create_gruppe": False,
		"can_create_untergruppe": False,
		"allowed_dienstbereiche": [],
		"allowed_gruppen": [],
	}

	if is_admin or "Gemeindeverantwortlicher" in roles:
		result["can_create_dienstbereich"] = True

	db_verantwortlich = frappe.db.sql(
		"SELECT DISTINCT parent FROM `tabDienstbereich Verantwortlicher` WHERE user = %s", user, as_dict=True
	)
	if db_verantwortlich or is_admin:
		result["can_create_gruppe"] = True
		result["allowed_dienstbereiche"] = [r["parent"] for r in db_verantwortlich]

	g_verantwortlich = frappe.db.sql(
		"SELECT DISTINCT parent FROM `tabGruppe Verantwortlicher` WHERE user = %s",
		user, as_dict=True
	)
	if g_verantwortlich or is_admin:
		result["can_create_untergruppe"] = True
		result["allowed_gruppen"] = [r["parent"] for r in g_verantwortlich]

	result["can_create_any"] = any([
		result["can_create_dienstbereich"],
		result["can_create_gruppe"],
		result["can_create_untergruppe"],
	])
	return result


@frappe.whitelist()
def create_dienstbereich(name, beschreibung=None, farbe=None):
	"""Erstellt einen neuen Dienstbereich. Nur für Gemeindeverantwortliche."""
	user = frappe.session.user
	roles = frappe.get_roles(user)
	if not any(r in roles for r in ["System Manager", "Mitgliederadministrator", "Gemeindeverantwortlicher"]):
		frappe.throw(_("Nur Gemeindeverantwortliche können Dienstbereiche erstellen."), frappe.PermissionError)
	doc = frappe.get_doc({
		"doctype": "Dienstbereich",
		"ministry": name,
		"beschreibung": beschreibung or "",
		"farbe": farbe or "#667eea",
	})
	doc.insert()
	frappe.db.commit()
	return {"success": True, "name": doc.name}


@frappe.whitelist()
def create_gruppe(name, dienstbereich, gruppentyp=None, beschreibung=None, treffpunkt=None, treffzeit=None):
	"""Erstellt eine neue Gruppe. Nur für Dienstbereichsverantwortliche."""
	user = frappe.session.user
	roles = frappe.get_roles(user)
	is_admin = any(r in roles for r in ["System Manager", "Mitgliederadministrator"])
	if not is_admin:
		if not frappe.db.exists("Dienstbereich Verantwortlicher", {"parent": dienstbereich, "user": user}):
			frappe.throw(_("Du bist kein Verantwortlicher dieses Dienstbereichs."), frappe.PermissionError)
	doc = frappe.get_doc({
		"doctype": "Gruppe",
		"gruppenname": name,
		"dienstbereich": dienstbereich,
		"gruppentyp": gruppentyp or None,
		"beschreibung": beschreibung or "",
		"treffpunkt": treffpunkt or "",
		"treffzeit": treffzeit or "",
		"status": "Aktiv",
	})
	doc.insert()
	frappe.db.commit()
	return {"success": True, "name": doc.name}


@frappe.whitelist()
def create_untergruppe(name, gruppe, beschreibung=None, treffpunkt=None, treffzeit=None):
	"""Erstellt eine neue Untergruppe. Nur für Gruppenverantwortliche."""
	user = frappe.session.user
	roles = frappe.get_roles(user)
	is_admin = any(r in roles for r in ["System Manager", "Mitgliederadministrator"])
	if not is_admin:
		mitglied = _get_current_user_mitglied()
		if not mitglied or not frappe.db.exists("Gruppe Verantwortlicher", {"parent": gruppe, "user": user}):
			frappe.throw(_("Du bist kein Verantwortlicher dieser Gruppe."), frappe.PermissionError)
	doc = frappe.get_doc({
		"doctype": "Untergruppe",
		"untergruppenname": name,
		"gruppe": gruppe,
		"beschreibung": beschreibung or "",
		"treffpunkt": treffpunkt or "",
		"treffzeit": treffzeit or "",
		"status": "Aktiv",
	})
	doc.insert()
	frappe.db.commit()
	return {"success": True, "name": doc.name}


@frappe.whitelist()
def update_gruppe(name, gruppenname=None, beschreibung=None, treffpunkt=None, treffzeit=None):
	"""Aktualisiert eine Gruppe. Verantwortliche oder uebergeordnete Admins."""
	user = frappe.session.user
	roles = frappe.get_roles(user)
	is_admin = any(r in roles for r in ["System Manager", "Mitgliederadministrator"])
	if not is_admin:
		gruppe_doc = frappe.get_doc("Gruppe", name)
		is_db_verantwortlich = frappe.db.exists("Dienstbereich Verantwortlicher", {"parent": gruppe_doc.dienstbereich, "user": user})
		is_g_verantwortlich = frappe.db.exists("Gruppe Verantwortlicher", {"parent": name, "user": user})
		if not is_db_verantwortlich and not is_g_verantwortlich:
			frappe.throw(_("Keine Berechtigung zum Bearbeiten dieser Gruppe."), frappe.PermissionError)
	doc = frappe.get_doc("Gruppe", name)
	if gruppenname: doc.gruppenname = gruppenname
	if beschreibung is not None: doc.beschreibung = beschreibung
	if treffpunkt is not None: doc.treffpunkt = treffpunkt
	if treffzeit is not None: doc.treffzeit = treffzeit
	doc.save()
	frappe.db.commit()
	return {"success": True}


@frappe.whitelist()
def update_untergruppe(name, untergruppenname=None, beschreibung=None, treffpunkt=None, treffzeit=None):
	"""Aktualisiert eine Untergruppe."""
	user = frappe.session.user
	roles = frappe.get_roles(user)
	is_admin = any(r in roles for r in ["System Manager", "Mitgliederadministrator"])
	if not is_admin:
		ug_doc = frappe.get_doc("Untergruppe", name)
		is_g_verantwortlich = frappe.db.exists("Gruppe Verantwortlicher", {"parent": ug_doc.gruppe, "user": user})
		is_ug_verantwortlich = frappe.db.exists("Untergruppe Verantwortlicher", {"parent": name, "user": user})
		if not is_g_verantwortlich and not is_ug_verantwortlich:
			frappe.throw(_("Keine Berechtigung zum Bearbeiten dieser Untergruppe."), frappe.PermissionError)
	doc = frappe.get_doc("Untergruppe", name)
	if untergruppenname: doc.untergruppenname = untergruppenname
	if beschreibung is not None: doc.beschreibung = beschreibung
	if treffpunkt is not None: doc.treffpunkt = treffpunkt
	if treffzeit is not None: doc.treffzeit = treffzeit
	doc.save()
	frappe.db.commit()
	return {"success": True}


@frappe.whitelist()
def get_gruppen_page_data():
    user = frappe.session.user
    roles = frappe.get_roles(user)
    is_admin = any(r in roles for r in ["System Manager", "Mitgliederadministrator"])
    mitglied_name = frappe.db.get_value("Mitglied", {"user": user}, "name")
    verantwortlich = frappe.db.sql(
        "SELECT DISTINCT parent FROM `tabGruppe Verantwortlicher` WHERE user=%s", user, as_dict=True)
    verantwortlich_names = {r["parent"] for r in verantwortlich}
    member_names = set()
    if mitglied_name:
        rows = frappe.db.sql(
            "SELECT DISTINCT parent FROM `tabGruppenmitgliedschaft` WHERE mitglied=%s AND status='Aktiv'",
            mitglied_name, as_dict=True)
        member_names = {r["parent"] for r in rows}
    my_groups = verantwortlich_names | member_names

    def g_dict(g, ist_verantwortlich=False, ist_meins=False):
        db_abbr, db_farbe = "", "#667eea"
        if g.get("dienstbereich"):
            db_doc = frappe.db.get_value("Dienstbereich", g["dienstbereich"], ["ministry","farbe"], as_dict=True) or {}
            db_name = db_doc.get("ministry") or ""
            db_farbe = db_doc.get("farbe") or "#667eea"
            db_abbr = "".join(w[0].upper() for w in db_name.split()[:2]) if db_name else ""
        typ_name = ""
        if g.get("gruppentyp"):
            typ_name = frappe.db.get_value("Gruppentyp", g["gruppentyp"], "typname") or ""
        count = frappe.db.count("Gruppenmitgliedschaft", {"parent": g["name"], "status": "Aktiv"})
        return {"name": g["name"], "gruppenname": g["gruppenname"],
            "dienstbereich_abbr": db_abbr, "dienstbereich_farbe": db_farbe,
            "gruppentyp_name": typ_name, "bild": g.get("bild") or "",
            "mitglieder_count": count,
            "ist_verantwortlich": ist_verantwortlich, "ist_meins": ist_meins}

    meine_gruppen = []
    filters = {"status": "Aktiv"}
    if not is_admin and my_groups:
        filters["name"] = ["in", list(my_groups)]
    if is_admin or my_groups:
        for g in frappe.get_all("Gruppe", filters=filters,
                fields=["name","gruppenname","dienstbereich","gruppentyp","bild"]):
            meine_gruppen.append(g_dict(g,
                ist_verantwortlich=g["name"] in verantwortlich_names, ist_meins=True))

    typen = []
    for typ in frappe.get_all("Gruppentyp", fields=["name","typname","bild","farbe"]):
        gruppen = []
        for g in frappe.get_all("Gruppe",
                filters={"gruppentyp": typ["name"], "status": "Aktiv"},
                fields=["name","gruppenname","dienstbereich","bild","sichtbarkeit"]):
            if g["sichtbarkeit"] == "Versteckt":
                continue
            if g["sichtbarkeit"] == "Intern" and g["name"] not in my_groups and not is_admin:
                continue
            gruppen.append(g_dict(g, ist_meins=g["name"] in my_groups))
        typen.append({"name": typ["name"], "typname": typ["typname"],
            "bild": typ.get("bild") or "", "farbe": typ.get("farbe") or "#667eea",
            "gruppen": gruppen, "gruppen_count": len(gruppen)})

    return {"meine_gruppen": meine_gruppen, "gruppentypen": typen}


# ── Aufgaben ─────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_aufgaben(gruppe_id=None, untergruppe_id=None):
    filters = {}
    if untergruppe_id:
        filters[untergruppe] = untergruppe_id
    elif gruppe_id:
        filters[gruppe] = gruppe_id
    else:
        frappe.throw(gruppe_id oder untergruppe_id erforderlich)
    items = frappe.get_all(
        Gruppen Aufgabe,
        filters=filters,
        fields=[name, titel, erledigt, faellig, erstellt_von],
        order_by=erledigt asc, creation asc,
        ignore_permissions=True,
    )
    return {success: True, data: items}


@frappe.whitelist()
def create_aufgabe(titel, gruppe_id=None, untergruppe_id=None, faellig=None):
    from diakronos.diakonos.api.profile import _get_my_mitglied
    try:
        mid = _get_my_mitglied()
    except Exception:
        mid = None
    doc = frappe.get_doc({
        doctype: Gruppen Aufgabe,
        titel: titel,
        gruppe: gruppe_id or None,
        untergruppe: untergruppe_id or None,
        faellig: faellig or None,
        erstellt_von: mid,
        erledigt: 0,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {success: True, name: doc.name}


@frappe.whitelist()
def toggle_aufgabe(aufgabe_id):
    doc = frappe.get_doc(Gruppen Aufgabe, aufgabe_id)
    doc.erledigt = 0 if doc.erledigt else 1
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {success: True, erledigt: doc.erledigt}


# ── Ankündigungen ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_ankuendigungen(gruppe_id=None, untergruppe_id=None):
    filters = {}
    if untergruppe_id:
        filters[untergruppe] = untergruppe_id
    elif gruppe_id:
        filters[gruppe] = gruppe_id
    else:
        frappe.throw(gruppe_id oder untergruppe_id erforderlich)
    items = frappe.get_all(
        Gruppen Ankuendigung,
        filters=filters,
        fields=[name, titel, text, erstellt_von, pinned, creation],
        order_by=pinned desc, creation desc,
        ignore_permissions=True,
    )
    return {success: True, data: items}


@frappe.whitelist()
def create_ankuendigung(titel, text=, gruppe_id=None, untergruppe_id=None):
    from diakronos.diakonos.api.profile import _get_my_mitglied
    try:
        mid = _get_my_mitglied()
    except Exception:
        mid = None
    doc = frappe.get_doc({
        doctype: Gruppen Ankuendigung,
        titel: titel,
        text: text,
        gruppe: gruppe_id or None,
        untergruppe: untergruppe_id or None,
        erstellt_von: mid,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {success: True, name: doc.name}
