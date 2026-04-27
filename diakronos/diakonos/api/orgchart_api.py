import frappe


@frappe.whitelist()
def get_orgchart_data():
    settings = frappe.get_single("Diakronos Einstellungen")
    org_name = settings.get("organisationsname") or "Meine Gemeinde"

    # Dienstbereiche
    dienstbereiche = frappe.get_all(
        "Dienstbereich",
        fields=["name", "ministry", "farbe", "icon", "sortierung"],
        order_by="sortierung asc, ministry asc",
    )

    # Gruppen mit Dienstbereich-Link
    gruppen = frappe.get_all(
        "Gruppe",
        filters={"status": "Aktiv"},
        fields=["name", "gruppenname", "gruppentyp", "dienstbereich"],
    )

    # Untergruppen mit Gruppe-Link
    untergruppen = frappe.get_all(
        "Untergruppe",
        filters={"status": "Aktiv"},
        fields=["name", "untergruppenname", "gruppe"],
    )

    # Verantwortliche für Gruppen (erste Person = Leiter-Anzeige)
    gruppen_ids = [g.name for g in gruppen]
    verantwortliche_map = {}
    if gruppen_ids:
        rows = frappe.db.sql(
            """
            SELECT gv.parent, u.full_name
            FROM `tabGruppe Verantwortlicher` gv
            JOIN `tabUser` u ON u.name = gv.user
            WHERE gv.parent IN %(ids)s
            ORDER BY gv.idx ASC
            """,
            {"ids": gruppen_ids},
            as_dict=True,
        )
        for r in rows:
            if r.parent not in verantwortliche_map:
                verantwortliche_map[r.parent] = r.full_name

    # Mitgliederzahlen: Gruppen
    gruppe_counts = {
        r.parent: r.cnt
        for r in frappe.db.sql(
            "SELECT parent, COUNT(*) AS cnt FROM `tabGruppenmitgliedschaft` WHERE status='Aktiv' GROUP BY parent",
            as_dict=True,
        )
    }

    # Mitgliederzahlen: Untergruppen
    untergruppe_counts = {
        r.parent: r.cnt
        for r in frappe.db.sql(
            "SELECT parent, COUNT(*) AS cnt FROM `tabUntergruppenmitgliedschaft` WHERE status='Aktiv' GROUP BY parent",
            as_dict=True,
        )
    }

    # Mitglieder je Gruppe (für Expand)
    gruppe_members = frappe.db.sql(
        """
        SELECT gm.parent AS gruppe, gm.mitglied, gm.rolle,
               m.vorname, m.nachname, m.foto
        FROM `tabGruppenmitgliedschaft` gm
        JOIN `tabMitglied` m ON m.name = gm.mitglied
        WHERE gm.status = 'Aktiv'
        ORDER BY m.nachname, m.vorname
        """,
        as_dict=True,
    )

    # Mitglieder je Untergruppe (für Expand)
    ug_members = frappe.db.sql(
        """
        SELECT ugm.parent AS untergruppe, ugm.mitglied, ugm.rolle,
               m.vorname, m.nachname, m.foto
        FROM `tabUntergruppenmitgliedschaft` ugm
        JOIN `tabMitglied` m ON m.name = ugm.mitglied
        WHERE ugm.status = 'Aktiv'
        ORDER BY m.nachname, m.vorname
        """,
        as_dict=True,
    )

    nodes = []

    # Root
    total_members = sum(gruppe_counts.values()) + sum(untergruppe_counts.values())
    nodes.append({
        "id": "__root__",
        "parentId": "",
        "name": org_name,
        "node_type": "org",
        "member_count": total_members,
    })

    # Dienstbereich-Knoten
    for db in dienstbereiche:
        nodes.append({
            "id": db.name,
            "parentId": "__root__",
            "name": db.ministry,
            "node_type": "dienstbereich",
            "farbe": db.farbe or "",
            "icon": db.icon or "",
            "member_count": 0,
        })

    # Gruppen-Knoten
    for g in gruppen:
        parent_id = g.dienstbereich if g.dienstbereich else "__root__"
        nodes.append({
            "id": g.name,
            "parentId": parent_id,
            "name": g.gruppenname,
            "node_type": "gruppe",
            "gruppentyp": g.gruppentyp or "",
            "leiter": verantwortliche_map.get(g.name, ""),
            "member_count": gruppe_counts.get(g.name, 0),
        })

    # Untergruppen-Knoten
    for ug in untergruppen:
        nodes.append({
            "id": ug.name,
            "parentId": ug.gruppe if ug.gruppe else "__root__",
            "name": ug.untergruppenname,
            "node_type": "untergruppe",
            "member_count": untergruppe_counts.get(ug.name, 0),
        })

    # Mitglieder je Gruppe
    for m in gruppe_members:
        nodes.append({
            "id": f"m__{m.mitglied}__{m.gruppe}",
            "parentId": m.gruppe,
            "name": f"{m.vorname} {m.nachname}",
            "node_type": "mitglied",
            "rolle": m.rolle or "",
            "foto": m.foto or "",
        })

    # Mitglieder je Untergruppe
    for m in ug_members:
        nodes.append({
            "id": f"m__{m.mitglied}__{m.untergruppe}",
            "parentId": m.untergruppe,
            "name": f"{m.vorname} {m.nachname}",
            "node_type": "mitglied",
            "rolle": m.rolle or "",
            "foto": m.foto or "",
        })

    return nodes
