"""ID-1d — Neue Mitglieder bekommen nie eine vom Client gewaehlte Kennung.

Ausgangsbefund (N2): Ueber die generischen Schreibwege
(`/api/resource/Mitglied` POST, `frappe.client.insert`, `_create`/Import) wurde
ein mitgeschickter `name` als Primaerschluessel uebernommen. Ein Aufrufer
konnte damit die Kennung einer Person bestimmen — auf die Rollen, Verweise und
die Anonymisierung zeigen.

Zusage der Karte: Beim Anlegen eines Mitglieds wird `name` ueber JEDEN Weg
serverseitig vergeben, eine vom Client gelieferte Kennung (`"Max Muster"`)
wird ignoriert. Gespeicherte Kennung entspricht ``^[0-9a-f]{8}-[0-9a-f]$``.
Andere DocTypes bleiben unveraendert.

Die Tests sind mit Absicht auf der ALTEN Basis rot: dort entsteht die Zeile
mit `name="Max Muster"` (bzw. `"M-0100"`).
"""

from __future__ import annotations

import json
import re

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.diakonos import Anmeldung, Mitglied

KENNUNG = re.compile(r"^[0-9a-f]{8}-[0-9a-f]$")
CLIENT_NAME = "Max Muster"


def _als_admin(monkeypatch):
    """Rollen auf Admin setzen — die Wege sind rollengebunden (fail closed)."""
    from diakronos_app.frappe_compat import permissions

    monkeypatch.setattr(
        permissions, "get_roles", lambda user=None: ["Mitgliederadministrator"]
    )
    monkeypatch.setattr(permissions, "is_guest", lambda user=None: False)


@pytest.fixture()
def admin(patched_db, monkeypatch):
    """Admin an allen Tueren: Identitaetsnaht UND Rollenquelle.

    `frappe.client.insert`/`/api/resource` pruefen `session.user` gegen
    "Guest"; die Fachendpunkte fragen die Rollen ueber `permissions.get_roles`
    — und `api/admin_hub.py` haelt eine EIGENE Bindung derselben Funktion.
    Alle drei werden gesetzt (Muster aus `test_admin_hub_p4k.py`), damit der
    Test den Schreibweg prueft und nicht die Rollenmatrix.
    """
    from diakronos_app.api import admin_hub
    from diakronos_app.frappe_compat import permissions, reset_user

    hole = lambda user=None: ["Mitgliederadministrator"]  # noqa: E731
    for mod in (permissions, admin_hub):
        if hasattr(mod, "get_roles"):
            monkeypatch.setattr(mod, "get_roles", hole)
    monkeypatch.setattr(admin_hub, "is_guest", lambda user=None: False)
    monkeypatch.setattr(permissions, "is_guest", lambda user=None: False)
    set_user("Administrator")
    yield
    reset_user()


def _mitglieder(patched_db):
    sess = patched_db()
    try:
        return sess.query(Mitglied).all()
    finally:
        sess.close()


# ── Weg 1: POST /api/resource/Mitglied ──────────────────────────────────────

def test_rest_resource_post_vergibt_kennung_serverseitig(client, patched_db, monkeypatch):
    _als_admin(monkeypatch)
    r = client.post(
        "/api/resource/Mitglied",
        json={"name": CLIENT_NAME, "vorname": "Max", "nachname": "Muster"},
    )
    assert r.status_code == 200, r.text
    gespeichert = r.json()["data"]["name"]
    assert gespeichert != CLIENT_NAME
    assert KENNUNG.match(gespeichert), gespeichert
    # Auch in der Datenbank steht die Server-Kennung, keine zweite Zeile.
    zeilen = _mitglieder(patched_db)
    assert [m.name for m in zeilen] == [gespeichert]
    assert zeilen[0].vorname == "Max"


def test_rest_resource_post_ignoriert_vorhandene_kennung(client, patched_db, monkeypatch):
    """Ein Client-`name` darf auch keine BESTEHENDE Zeile ueberschreiben.

    Vorher war `name` im POST ein Update: derselbe Aufruf mit der Kennung
    eines vorhandenen Mitglieds schrieb auf dessen Zeile. Jetzt ist der POST
    immer ein Anlegen mit frischer Server-Kennung (Frappe-Semantik: Anlegen
    ist Anlegen).
    """
    _als_admin(monkeypatch)
    sess = patched_db()
    sess.add(Mitglied(name="M-0001", vorname="Anna", nachname="Beispiel",
                      status="Mitglied", docstatus=0, idx=0))
    sess.commit()
    sess.close()

    r = client.post(
        "/api/resource/Mitglied",
        json={"name": "M-0001", "vorname": "Untergeschoben", "nachname": "Person"},
    )
    assert r.status_code == 200, r.text
    assert KENNUNG.match(r.json()["data"]["name"]), r.json()

    sess = patched_db()
    anna = sess.get(Mitglied, "M-0001")
    assert anna.vorname == "Anna"          # Bestandszeile unberuehrt
    assert sess.query(Mitglied).count() == 2
    sess.close()


def test_rest_resource_put_aendert_die_kennung_nicht(client, patched_db, monkeypatch):
    """`name` im Rumpf einer AENDERUNG ist kein Umbenennen (Pfad gewinnt)."""
    _als_admin(monkeypatch)
    sess = patched_db()
    sess.add(Mitglied(name="M-0001", vorname="Anna", nachname="Beispiel",
                      status="Mitglied", docstatus=0, idx=0))
    sess.commit()
    sess.close()

    r = client.put(
        "/api/resource/Mitglied/M-0001",
        json={"name": CLIENT_NAME, "vorname": "Geaendert"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["name"] == "M-0001"

    sess = patched_db()
    assert sess.get(Mitglied, "M-0001").vorname == "Geaendert"
    assert sess.get(Mitglied, CLIENT_NAME) is None
    sess.close()


# ── Weg 2: frappe.client.insert ─────────────────────────────────────────────

def test_client_insert_vergibt_kennung_serverseitig(admin, patched_db):
    from diakronos_app.api.frappe_core import insert

    r = insert(doc={"doctype": "Mitglied", "name": CLIENT_NAME,
                    "vorname": "Max", "nachname": "Muster"})
    assert r["name"] != CLIENT_NAME
    assert KENNUNG.match(r["name"]), r["name"]
    assert [m.name for m in _mitglieder(patched_db)] == [r["name"]]


def test_client_insert_legt_kein_mitglied_auf_bestehender_kennung_an(admin, patched_db):
    from diakronos_app.api.frappe_core import insert

    sess = patched_db()
    sess.add(Mitglied(name="M-0001", vorname="Anna", nachname="Beispiel",
                      status="Mitglied", docstatus=0, idx=0))
    sess.commit()
    sess.close()

    r = insert(doc={"doctype": "Mitglied", "name": "M-0001",
                    "vorname": "Untergeschoben", "nachname": "Person"})
    assert KENNUNG.match(r["name"]), r["name"]

    sess = patched_db()
    assert sess.get(Mitglied, "M-0001").vorname == "Anna"
    assert sess.query(Mitglied).count() == 2
    sess.close()


# ── Weg 3: _create (create_mitglied, Import, Registrierung -> Mitglied) ─────

def test_create_mitglied_vergibt_kennung_serverseitig(client, patched_db, monkeypatch):
    """`create_mitglied` meldet die Server-Kennung zurueck und speichert sie."""
    _als_admin(monkeypatch)
    r = client.post(
        "/api/method/diakronos.diakonos.api.mitglieder.create_mitglied",
        json={"vorname": "Max", "nachname": "Muster", "name": CLIENT_NAME},
    )
    assert r.status_code == 200, r.text
    kennung = r.json()["message"]["mitglied_id"]
    assert KENNUNG.match(kennung), kennung
    assert CLIENT_NAME not in [m.name for m in _mitglieder(patched_db)]


def test_import_vergibt_kennung_serverseitig(client, patched_db, monkeypatch):
    """Der CSV-Import laeuft ueber `_create("Mitglied", ...)`."""
    _als_admin(monkeypatch)
    csv = "Vorname;Nachname;E-Mail\nMax;Muster;max@example.org\n"
    r = client.post(
        "/api/method/diakronos.diakonos.api.mitglieder.import_mitglieder_uebernehmen",
        json={"csv_inhalt": csv, "bestaetigt": 1},
    )
    assert r.status_code == 200, r.text
    zeilen = _mitglieder(patched_db)
    assert len(zeilen) == 1
    assert KENNUNG.match(zeilen[0].name), zeilen[0].name
    assert zeilen[0].vorname == "Max"


# ── Weg 4: Registrierung -> Mitglied (genehmige_anmeldung) ──────────────────

def test_genehmigte_registrierung_vergibt_kennung_serverseitig(patched_db, admin, client):
    """Die Anmeldung einer Person traegt ebenfalls nur eine Server-Kennung."""
    sess = patched_db()
    sess.add(Anmeldung(name="AN-1", anmeldungstyp="Mitglied-Registrierung",
                       status="Anmeldeanfrage", vorname="Max", nachname="Muster",
                       email="max@example.org", verarbeitet=False,
                       dsgvo_zustimmung=True, docstatus=0, idx=0))
    sess.commit()
    sess.close()

    r = client.post(
        "/api/method/diakronos.diakonos.api.admin_hub.genehmige_anmeldung",
        json={"anmeldung_id": "AN-1"},
    )
    assert r.status_code == 200, r.text
    mitglied_name = r.json()["message"]["mitglied"]
    assert KENNUNG.match(mitglied_name), mitglied_name
    assert CLIENT_NAME not in [m.name for m in _mitglieder(patched_db)]
    # Die Anmeldung selbst behaelt ihre (server-vergebene) Kennung.
    sess = patched_db()
    assert sess.get(Anmeldung, "AN-1") is not None
    sess.close()


# ── Weg 5: frappe.get_doc({...}).insert() (Document) ────────────────────────

def test_document_insert_vergibt_kennung_serverseitig(client, patched_db, admin):
    from diakronos_app.frappe_compat.doc import new_doc

    doc = new_doc("Mitglied", name=CLIENT_NAME, vorname="Max", nachname="Muster")
    doc.insert()
    assert KENNUNG.match(doc.name), doc.name
    assert [m.name for m in _mitglieder(patched_db)] == [doc.name]


# ── Abgrenzung: andere DocTypes bleiben unveraendert ────────────────────────

def test_andere_doctypes_behalten_ihre_kennung(admin, patched_db):
    """Nur PERSONEN-Kennungen werden vergeben — `Gruppe` bleibt wie bisher."""
    from diakronos_app.api.frappe_core import insert

    r = insert(doc={"doctype": "Gruppe", "name": "G-1", "gruppenname": "Chor"})
    assert r["name"] == "G-1"


def test_kennung_form_stammt_aus_new_name():
    """Die zugesagte Form kommt aus `_new_name()` — nicht aus einem Muster."""
    from diakronos_app.frappe_compat.api_helpers import _new_name

    proben = {_new_name() for _ in range(200)}
    assert len(proben) == 200
    for probe in proben:
        assert KENNUNG.match(probe), probe
    from diakronos_app.frappe_compat.api_helpers import PERSONEN_KENNUNGEN

    assert "Mitglied" in PERSONEN_KENNUNGEN
