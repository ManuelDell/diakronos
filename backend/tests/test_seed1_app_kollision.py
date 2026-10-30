"""SEED-1 Punkt 3 — Kollision Dienstbereich/Gruppe: Organigramm bleibt eindeutig.

Der Seed vergab ``dienstbereich.name = "technik"`` UND ``gruppe.name =
"technik"``. Die Kartenfrage war, ob das ein reiner Seed-Fehler war oder ob
auch der Betrieb diesen Zustand herstellen kann. Geprueft wird ueber die
ECHTEN Wege (``create_dienstbereich`` / ``create_gruppe`` /
``orgchart_api.get_orgchart_data``), nicht per SQL.

Befund (belegt durch die Tests unten):
  * ``create_dienstbereich("Technik")`` vergibt eine UUID-Kennung, NICHT den
    Anzeigenamen — der Dienstanzeigename steht in ``ministry``.
  * ``create_gruppe(...)`` vergibt ebenfalls eine UUID-Kennung.
  * Zwei Datensaetze mit gleicher Kennung koennen also ueber die Oberflaeche
    nicht entstehen: ``dienstbereich`` und ``gruppe`` sind getrennte Tabellen
    mit eigenen Primaerschluesseln, die jeweils serverseitig vergeben werden.
  * Die Kollision war damit ein ARTEFAKT des Seeds (feste, sprechende
    Kennungen in ``tools/demo/musterhausen_daten.py``), kein App-Fehler.

ORG-1: fuer ALTDATEN und Importe bleibt die Kollision trotzdem moeglich, und
``orgchart_api.get_orgchart_data`` ist dort die zweite Verteidigungslinie.
Sie bildet die Knoten-``id`` seit ORG-1 mit Typ-Praefix (``db_``/``g_``/
``ug_``) — dieselbe Sprechweise wie ``get_gruppen_for_orgchart``. Der frueher
hier stehende Tripwire-Test („kein Typ-Praefix“) ist durch die positiven
Tests ersetzt: gleiche Kennung in beiden Tabellen -> eindeutige Knoten,
richtige Elternkanten, richtige Klick-Ziele (``raw_name``).
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def welt(patched_db):
    sess = patched_db()
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Dienstbereich, Mitglied

    sess.add_all([
        User(name="admin@example.org", email="admin@example.org",
             full_name="Admin", enabled=True),
        HasRole(name="HR-1", parent="admin@example.org", parenttype="User",
                parentfield="roles", role="System Manager", docstatus=0, idx=1),
        Dienstbereich(name="DB-A", ministry="Gottesdienst", docstatus=0, idx=0),
        Mitglied(name="M-1", vorname="Admin", nachname="Person",
                 email="admin@example.org", status="Mitglied",
                 user="admin@example.org", docstatus=0, idx=0),
    ])
    sess.commit()
    from diakronos_app.frappe_compat.session import set_user

    set_user("admin@example.org")
    yield sess


def _kollision(welt):
    """Dienstbereich UND Gruppe mit DERSELBEN Kennung — Altdaten-Lage.

    Ueber die Oberflaeche nicht herstellbar (siehe
    ``test_app_vergibt_eigene_kennungen``); hier direkt in die Tabellen
    geschrieben, weil genau dieser Altbestand aus Importen existiert.
    """
    from diakronos_app.models.diakonos import Gruppe, Untergruppe

    welt.add_all([
        Gruppe(name="DB-A", gruppenname="Technikteam", dienstbereich="DB-A",
               status="Aktiv", docstatus=0, idx=0),
        Untergruppe(name="DB-A-UG", untergruppenname="Nord-Team",
                    gruppe="DB-A", status="Aktiv", docstatus=0, idx=0),
    ])
    welt.commit()


def test_app_vergibt_eigene_kennungen(welt):
    """Die echten Anlege-Wege vergeben UUID-Kennungen, nicht den Anzeigenamen.

    Damit kann ueber die Oberflaeche keine Kennung entstehen, die ein
    Dienstbereich und eine Gruppe gemeinsam tragen.
    """
    from diakronos_app.api.gruppen import create_dienstbereich, create_gruppe

    db = create_dienstbereich("Technik")
    g = create_gruppe("Technikteam", dienstbereich="DB-A")
    assert db["name"] != "Technik", "Dienstbereich-Kennung ist der Anzeigename"
    assert g["name"] != "Technikteam", "Gruppen-Kennung ist der Anzeigename"
    assert db["name"] != g["name"]


def test_orgchart_api_knoten_ids_sind_trotz_kollision_eindeutig(welt):
    """ORG-1: gleiche Kennung in beiden Tabellen -> trotzdem zwei Knoten.

    Vorher stand die Kennung ohne Typ in ``id``: zwei Knoten mit ``id "DB-A"``,
    d3-org-chart bricht mit „ambiguous: DB-A“ ab und das Organigramm laedt
    nicht. Mit Typ-Praefix sind es ``db_DB-A`` und ``g_DB-A``.
    """
    from diakronos_app.api.orgchart_api import get_orgchart_data

    _kollision(welt)
    nodes = get_orgchart_data()

    ids = [n["id"] for n in nodes]
    doppelt = {i for i in ids if ids.count(i) > 1}
    assert not doppelt, f"Knoten-IDs mehrfach vergeben: {sorted(doppelt)}"

    by_id = {n["id"]: n for n in nodes}
    assert by_id["db_DB-A"]["node_type"] == "dienstbereich"
    assert by_id["g_DB-A"]["node_type"] == "gruppe"
    # Beide tragen dieselbe ECHTE Kennung — nur die Knoten-id unterscheidet sie.
    assert by_id["db_DB-A"]["raw_name"] == "DB-A"
    assert by_id["g_DB-A"]["raw_name"] == "DB-A"


def test_orgchart_api_elternkanten_und_klick_ziele_bei_kollision(welt):
    """ORG-1: Elternkanten zeigen auf die PRAEFIGIERTE Kennung.

    Die Gruppe haengt am Dienstbereich (``db_DB-A``), die Untergruppe an der
    Gruppe (``g_DB-A``) — nicht an sich selbst. Und jedes Klick-Ziel
    (``raw_name``) ist die echte Kennung des Datensatzes, damit die
    Detailseite den Datensatz findet.
    """
    from diakronos_app.api.orgchart_api import get_orgchart_data

    _kollision(welt)
    nodes = get_orgchart_data()
    by_id = {n["id"]: n for n in nodes}

    assert by_id["g_DB-A"]["parentId"] == "db_DB-A"
    assert by_id["ug_DB-A-UG"]["parentId"] == "g_DB-A"

    # Jede Elternkante zeigt auf einen vorhandenen Knoten (der Wurzelknoten
    # traegt eine leere Elternkante).
    bekannt = set(by_id)
    for node in nodes:
        if node.get("parentId"):
            assert node["parentId"] in bekannt, node

    # Klick-Ziel: der rohe Name, nicht die Knoten-Kennung.
    for node in nodes:
        if node["node_type"] in ("dienstbereich", "gruppe", "untergruppe"):
            assert not node["raw_name"].startswith(("db_", "g_", "ug_")), node
            assert node["id"].endswith(node["raw_name"]), node


def test_orgchart_api_und_neuer_endpunkt_sprechen_dieselben_ids(welt):
    """ORG-1: beide Organigramm-Endpunkte benutzen dieselben Knoten-IDs.

    ``get_gruppen_for_orgchart`` (Ansicht Gruppen) praefigierte schon immer;
    ``get_orgchart_data`` (eigene Organigramm-Seite) zieht nach. Sonst muesste
    jede Oberflaeche zwei Sprechweisen kennen.
    """
    from diakronos_app.api.gruppen import get_gruppen_for_orgchart
    from diakronos_app.api.orgchart_api import get_orgchart_data

    _kollision(welt)
    ids_neu = {n["id"] for n in get_gruppen_for_orgchart()["nodes"]}
    ids_alt = {n["id"] for n in get_orgchart_data()}

    assert "db_DB-A" in ids_neu and "g_DB-A" in ids_neu
    assert "db_DB-A" in ids_alt and "g_DB-A" in ids_alt
