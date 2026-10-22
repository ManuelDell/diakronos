"""Portierung von `diakronos.diakonos.api.orgchart_api` (Altcode, Frappe).

VORLAGE (READ-ONLY): `referenz/diakronos-frappe/diakronos/diakonos/api/orgchart_api.py`

Uebersetzen heisst hier: **dieselbe Signatur, dieselbe Antwortstruktur,
dieselbe Logik.** Portiert ist der eine Endpunkt des Originals:

    get_orgchart_data()

Die vier `frappe.db.sql`-Abfragen des Originals sind hier alle auf
`get_all`/SQLAlchemy umgestellt (kein rohes SQL noetig):

    * Verantwortliche je Gruppe  -> get_all("Gruppe Verantwortlicher") + User-
      Join. Der Original-Join auf `tabUser` holt nur `full_name`; in der
      Compat-Schicht ist `User` ein eigenes Modell, also ueber `get_value`
      einzeln aufgeloest.
    * Mitgliederzahlen           -> Aggregation in Python statt `GROUP BY`.
      Konnte auf `get_all` umgestellt werden; kein rohes SQL noetig.
    * Mitglieder je Gruppe/UG    -> get_all(...) + Mitglied-Aufloesung.

Der Original-Endpunkt benutzt **keine** Permission-Pruefung (`@whitelist`
mit Login, sonst nichts) — das ist hier unveraendert uebernommen, nicht
"verbessert". Die SPA nutzt ihn als reine Struktur-/Organigramm-Datenquelle.
"""

from __future__ import annotations

# Original-Frappe-Modulpfad. Die SPA ruft ausschliesslich diese Form auf;
# die Registry registriert daraus `diakronos.diakonos.api.orgchart_api.<funktion>`.
FRAPPE_MODULE = "diakronos.diakonos.api.orgchart_api"

from diakronos_app.frappe_compat import get_all, whitelist
from diakronos_app.frappe_compat.query import get_value
# UXD-R28/DES-04: die eine Farbreinigungsstelle (gemeinsam mit gruppen.py).
from diakronos_app.api.farbe import _normalisiere_farbe

# Quelle: orgchart_api.py — der Altcode liest den Single "Diakronos Einstellungen".
_EINSTELLUNGEN = "Diakronos Einstellungen"
_DEFAULT_ORG_NAME = "Meine Gemeinde"


def _org_name() -> str:
    """`settings.get("organisationsname") or "Meine Gemeinde"`.

    Der Original nutzt `frappe.get_single("Diakronos Einstellungen")`. In der
    Compat-Schicht gibt es keinen Single-Zugriff; der Wert wird direkt aus der
    Tabelle gelesen. Fehlt der Single oder das Feld, greift der Default des
    Originals.
    """
    row = get_value(_EINSTELLUNGEN, {"name": "Diakronos Einstellungen"},
                    ["organisationsname"], as_dict=True)
    if not row:
        rows = get_all(_EINSTELLUNGEN, fields=["organisationsname"],
                       limit_page_length=1)
        row = rows[0] if rows else None
    if not row:
        return _DEFAULT_ORG_NAME
    return row.get("organisationsname") or _DEFAULT_ORG_NAME


def _full_name_for_user(user: str | None) -> str | None:
    """`JOIN tabUser u ON u.name = gv.user` -> `u.full_name`."""
    if not user:
        return None
    return get_value("User", user, "full_name")


@whitelist(allow_guest=False)
def get_orgchart_data():
    """Flache Knotenliste fuer das d3-Organigramm (Quelle: orgchart_api.py:4)."""
    org_name = _org_name()

    # Dienstbereiche — Quelle: orgchart_api.py:8-13
    dienstbereiche = get_all(
        "Dienstbereich",
        fields=["name", "ministry", "farbe", "icon", "sortierung"],
        order_by="sortierung asc, ministry asc",
    )

    # Gruppen mit Dienstbereich-Link — Quelle: orgchart_api.py:15-20
    gruppen = get_all(
        "Gruppe",
        filters={"status": "Aktiv"},
        fields=["name", "gruppenname", "gruppentyp", "dienstbereich"],
    )

    # Untergruppen mit Gruppe-Link — Quelle: orgchart_api.py:22-27
    untergruppen = get_all(
        "Untergruppe",
        filters={"status": "Aktiv"},
        fields=["name", "untergruppenname", "gruppe"],
    )

    # Verantwortliche fuer Gruppen (erste Person = Leiter-Anzeige).
    # Quelle: orgchart_api.py:29-45 — ORDER BY gv.idx ASC ist die Kind-
    # Tabellen-Sortierung; der erste Treffer je parent gewinnt.
    verantwortliche_map: dict[str, str] = {}
    if gruppen:
        rows = get_all(
            "Gruppe Verantwortlicher",
            filters={"parent": ["in", [g["name"] for g in gruppen]]},
            fields=["parent", "user"],
            order_by="idx asc",
        )
        for r in rows:
            parent = r.get("parent")
            if parent not in verantwortliche_map:
                verantwortliche_map[parent] = _full_name_for_user(r.get("user")) or ""

    # Mitgliederzahlen: Gruppen — Quelle: orgchart_api.py:47-55 (GROUP BY).
    gruppe_counts: dict[str, int] = {}
    for row in get_all(
        "Gruppenmitgliedschaft",
        filters={"status": "Aktiv"},
        fields=["parent"],
    ):
        parent = row.get("parent")
        gruppe_counts[parent] = gruppe_counts.get(parent, 0) + 1

    # Mitgliederzahlen: Untergruppen — Quelle: orgchart_api.py:57-65.
    untergruppe_counts: dict[str, int] = {}
    for row in get_all(
        "Untergruppenmitgliedschaft",
        filters={"status": "Aktiv"},
        fields=["parent"],
    ):
        parent = row.get("parent")
        untergruppe_counts[parent] = untergruppe_counts.get(parent, 0) + 1

    # Mitglieder je Gruppe (fuer Expand). Quelle: orgchart_api.py:67-78 —
    # ORDER BY m.nachname, m.vorname ueber den Mitglied-Join. Aufgeloest in
    # Python, weil get_all keine Join-Sortierung kennt.
    _rows = get_all(
        "Gruppenmitgliedschaft",
        filters={"status": "Aktiv"},
        fields=["parent", "mitglied", "rolle"],
    )
    gruppe_members = _sorted_member_rows(_rows, "gruppe")

    # Mitglieder je Untergruppe (fuer Expand) — Quelle: orgchart_api.py:80-91.
    _rows = get_all(
        "Untergruppenmitgliedschaft",
        filters={"status": "Aktiv"},
        fields=["parent", "mitglied", "rolle"],
    )
    ug_members = _sorted_member_rows(_rows, "untergruppe")

    nodes: list[dict] = []

    # Root — Quelle: orgchart_api.py:95-104
    total_members = sum(gruppe_counts.values()) + sum(untergruppe_counts.values())
    nodes.append({
        "id": "__root__",
        "parentId": "",
        "name": org_name,
        "node_type": "org",
        "member_count": total_members,
    })

    # Dienstbereich-Knoten — Quelle: orgchart_api.py:106-116
    for db in dienstbereiche:
        nodes.append({
            "id": db["name"],
            "parentId": "__root__",
            "name": db["ministry"],
            "node_type": "dienstbereich",
            "farbe": _normalisiere_farbe(db.get("farbe")),
            "icon": db.get("icon") or "",
            "member_count": 0,
        })

    # Gruppen-Knoten — Quelle: orgchart_api.py:118-129
    for g in gruppen:
        parent_id = g["dienstbereich"] if g.get("dienstbereich") else "__root__"
        nodes.append({
            "id": g["name"],
            "parentId": parent_id,
            "name": g["gruppenname"],
            "node_type": "gruppe",
            "gruppentyp": g.get("gruppentyp") or "",
            "leiter": verantwortliche_map.get(g["name"], ""),
            "member_count": gruppe_counts.get(g["name"], 0),
        })

    # Untergruppen-Knoten — Quelle: orgchart_api.py:131-139
    for ug in untergruppen:
        nodes.append({
            "id": ug["name"],
            "parentId": ug["gruppe"] if ug.get("gruppe") else "__root__",
            "name": ug["untergruppenname"],
            "node_type": "untergruppe",
            "member_count": untergruppe_counts.get(ug["name"], 0),
        })

    # Mitglieder je Gruppe — Quelle: orgchart_api.py:141-151
    for m in gruppe_members:
        nodes.append({
            "id": f"m__{m['mitglied']}__{m['gruppe']}",
            "parentId": m["gruppe"],
            "name": m["full_name"],
            "node_type": "mitglied",
            "rolle": m.get("rolle") or "",
            "foto": m.get("foto") or "",
        })

    # Mitglieder je Untergruppe — Quelle: orgchart_api.py:153-163
    for m in ug_members:
        nodes.append({
            "id": f"m__{m['mitglied']}__{m['untergruppe']}",
            "parentId": m["untergruppe"],
            "name": m["full_name"],
            "node_type": "mitglied",
            "rolle": m.get("rolle") or "",
            "foto": m.get("foto") or "",
        })

    return nodes


def _sorted_member_rows(rows: list[dict], parent_key: str) -> list[dict]:
    """Mitglieder aufloesen und wie das Original sortieren.

    Quelle: orgchart_api.py:73 `ORDER BY m.nachname, m.vorname`. SQLite und
    PostgreSQL sortieren NULL anders als MySQL; `or ""` macht die Sortierung
    deterministisch und entspricht der Anzeige-Reihenfolge des Originals.
    """
    out: list[dict] = []
    # AUSTRITT-b (B1): Anzeigename ueber die eine Regel — die Sortierung
    # braucht weiter Vor-/Nachname, deshalb kommen sie mit.
    from diakronos_app.frappe_compat.personen_anzeige import PersonenSicht, anzeigename

    sicht = PersonenSicht.aus()
    for row in rows:
        mitglied = row.get("mitglied")
        if not mitglied:
            continue
        m = get_value(
            "Mitglied", mitglied,
            ["vorname", "nachname", "foto", "ausgeschlossen", "status",
             "austritt_datum"],
            as_dict=True,
        ) or {}
        out.append({
            parent_key: row.get("parent"),
            "mitglied": mitglied,
            "gruppe": row.get("parent"),
            "untergruppe": row.get("parent"),
            "rolle": row.get("rolle"),
            "foto": m.get("foto"),
            "full_name": anzeigename(m, sicht=sicht),
            "_nachname": m.get("nachname") or "",
            "_vorname": m.get("vorname") or "",
        })
    out.sort(key=lambda r: (r["_nachname"], r["_vorname"]))
    return out


__all__ = ["get_orgchart_data"]
