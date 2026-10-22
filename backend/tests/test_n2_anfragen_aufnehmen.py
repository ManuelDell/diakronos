"""N2 — Reiter „Anfragen“: Aufnehmen mit Status und Gruppe.

Deckt die Zugaben des Pakets N2 (Neuordnung, Konzept Abschnitt 3, Reiter 3)
und die zugehoerigen Befunde der Nachtpruefung ab:

  OP-ADMIN-7  „Aufnehmen“ waehlt Status und Gruppe; die Anmeldung traegt ein
              Zielfeld `gruppe`, das nicht mehr still im Hintergrund greift.
  OP-ADMIN-8  Das Anmeldungs-Hub liefert das Zielfeld `gruppe` mit, damit die
              Oberflaeche „Aufnehmen“ vorbelegen kann.

Jeder Test ist zuerst rot gelaufen (Reproduktion) und danach gruen.
"""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture()
def rollen(monkeypatch):
    """Admin-Rollen fuer die Mitglieder-Endpunkte (Muster test_p1_9_mitglieder_kern)."""
    from diakronos_app.api import admin_hub, mitglieder
    from diakronos_app.frappe_compat import permissions

    halt: dict[str, Any] = {"roles": ["Mitgliederadministrator"], "user": "admin@example.org"}
    hole = lambda user=None: list(halt["roles"])  # noqa: E731
    kein_gast = lambda user=None: False  # noqa: E731
    for mod in (permissions, mitglieder, admin_hub):
        if hasattr(mod, "get_roles"):
            monkeypatch.setattr(mod, "get_roles", hole)
        if hasattr(mod, "is_guest"):
            monkeypatch.setattr(mod, "is_guest", kein_gast)
    monkeypatch.setattr(mitglieder, "_is_admin", lambda: True)
    return halt


@pytest.fixture()
def sess(patched_db):
    s = patched_db()
    yield s
    s.close()


def _anmeldung(sess, name, **werte):
    from diakronos_app.models.diakonos import Anmeldung

    a = Anmeldung(
        name=name,
        vorname=werte.get("vorname", "Neu"),
        nachname=werte.get("nachname", "Person"),
        email=werte.get("email", ""),
        telefon=werte.get("telefon", ""),
        geburtstag=werte.get("geburtstag"),
        kommentar=werte.get("kommentar", ""),
        status="Anmeldeanfrage",
        anmeldungstyp=werte.get("anmeldungstyp", "Mitglied-Registrierung"),
        gruppe=werte.get("gruppe"),
        verarbeitet=0,
    )
    sess.add(a)
    sess.commit()
    return name


def _gruppe(sess, name, gruppenname):
    from diakronos_app.models.diakonos import Gruppe

    sess.add(Gruppe(name=name, gruppenname=gruppenname, docstatus=0, idx=0))
    sess.commit()
    return name


# ── OP-ADMIN-7: Status beim Aufnehmen waehlbar ─────────────────────────────


def test_aufnehmen_setzt_gewaehlten_status(client, seed_mitglieder, rollen, sess):
    """Ohne Vorgabe gilt weiter der aus `anmeldungstyp` abgeleitete Status."""
    from diakronos_app.models.diakonos import Mitglied

    _anmeldung(sess, "A-STAT1", email="stat1@example.org", anmeldungstyp="Mitglied-Registrierung")
    r = client.post(
        "/api/method/admin_hub.genehmige_anmeldung",
        json={"anmeldung_id": "A-STAT1", "status": "Passives Mitglied"},
    )
    assert r.status_code == 200, r.text
    mitglied_name = r.json()["message"]["mitglied"]
    sess.expire_all()
    assert sess.get(Mitglied, mitglied_name).status == "Passives Mitglied"


def test_aufnehmen_ohne_status_bleibt_anmeldungstyp(client, seed_mitglieder, rollen, sess):
    """Der neue Parameter ist optional — das Altverhalten bleibt erhalten."""
    from diakronos_app.models.diakonos import Mitglied

    _anmeldung(sess, "A-STAT2", email="stat2@example.org", anmeldungstyp="Gast-Anmeldung")
    r = client.post(
        "/api/method/admin_hub.genehmige_anmeldung",
        json={"anmeldung_id": "A-STAT2"},
    )
    assert r.status_code == 200, r.text
    mitglied_name = r.json()["message"]["mitglied"]
    sess.expire_all()
    assert sess.get(Mitglied, mitglied_name).status == "Gast"


def test_aufnehmen_status_wird_nicht_erfunden(client, seed_mitglieder, rollen, sess):
    """Ein unbekannter Status wird abgewiesen, kein Freitext im Mitglied."""
    _anmeldung(sess, "A-STAT3", email="stat3@example.org")
    r = client.post(
        "/api/method/admin_hub.genehmige_anmeldung",
        json={"anmeldung_id": "A-STAT3", "status": "Oberboss"},
    )
    assert r.status_code >= 400, r.text


# ── OP-ADMIN-7: Gruppe beim Aufnehmen waehlbar ─────────────────────────────


def test_aufnehmen_weist_gewaehlte_gruppe_zu(client, seed_mitglieder, rollen, sess):
    """Die beim Aufnehmen gewaehlte Gruppe gewinnt gegen das Zielfeld der Anmeldung."""
    from diakronos_app.models.diakonos import Gruppe
    from diakronos_app.frappe_compat import db

    _gruppe(sess, "G-WAHL", "Chor A")
    _gruppe(sess, "G-ALT", "Chor B")
    _anmeldung(sess, "A-GRP1", email="grp1@example.org", gruppe="G-ALT")

    r = client.post(
        "/api/method/admin_hub.genehmige_anmeldung",
        json={"anmeldung_id": "A-GRP1", "gruppe": "G-WAHL"},
    )
    assert r.status_code == 200, r.text
    mitglied_name = r.json()["message"]["mitglied"]
    sess.expire_all()
    assert db.exists("Gruppenmitgliedschaft", {"parent": "G-WAHL", "mitglied": mitglied_name})
    assert not db.exists("Gruppenmitgliedschaft", {"parent": "G-ALT", "mitglied": mitglied_name})


def test_aufnehmen_ohne_gruppe_nutzt_zieldeld_der_anmeldung(client, seed_mitglieder, rollen, sess):
    """Ohne Vorgabe greift weiter das Zielfeld `gruppe` der Anmeldung (B4)."""
    from diakronos_app.frappe_compat import db

    _gruppe(sess, "G-ZIEL", "Chor Z")
    _anmeldung(sess, "A-GRP2", email="grp2@example.org", gruppe="G-ZIEL")

    r = client.post(
        "/api/method/admin_hub.genehmige_anmeldung",
        json={"anmeldung_id": "A-GRP2"},
    )
    assert r.status_code == 200, r.text
    mitglied_name = r.json()["message"]["mitglied"]
    sess.expire_all()
    assert db.exists("Gruppenmitgliedschaft", {"parent": "G-ZIEL", "mitglied": mitglied_name})


def test_aufnehmen_keine_gruppe_ist_durchsetzbar(client, seed_mitglieder, rollen, sess):
    """M1 (R-N2-code): „Keine Gruppe“ muss sich durchsetzen lassen.

    Die Oberflaeche belegt die Auswahl aus dem Zielfeld der Anmeldung vor;
    waehlt die Person „– Keine Gruppe –“, sendet sie `gruppe: ''`. Vorher
    galt `gruppe or zielfeld` — der leere Text fiel auf das Zielfeld zurueck
    und die Anmeldung landete entgegen der Auswahl doch in der Gruppe.
    """
    from diakronos_app.frappe_compat import db

    _gruppe(sess, "G-VORBELEGT", "Chor V")
    _anmeldung(sess, "A-GRP3", email="grp3@example.org", gruppe="G-VORBELEGT")

    r = client.post(
        "/api/method/admin_hub.genehmige_anmeldung",
        json={"anmeldung_id": "A-GRP3", "gruppe": ""},
    )
    assert r.status_code == 200, r.text
    mitglied_name = r.json()["message"]["mitglied"]
    sess.expire_all()
    assert not db.exists(
        "Gruppenmitgliedschaft", {"parent": "G-VORBELEGT", "mitglied": mitglied_name}
    ), "leere Auswahl darf nicht auf das Zielfeld zurueckfallen"


# ── OP-ADMIN-8: Hub liefert das Zielfeld mit ───────────────────────────────


def test_anmeldungen_hub_liefert_zieldeld_gruppe(client, seed_mitglieder, rollen, sess):
    """OP-ADMIN-8: das Hub liefert `gruppe`, damit die Oberflaeche vorbelegen kann."""
    _gruppe(sess, "G-HUB", "Chor Hub")
    _anmeldung(sess, "A-HUB1", email="hub1@example.org", gruppe="G-HUB")

    r = client.post("/api/method/admin_hub.get_anmeldungen_hub")
    assert r.status_code == 200, r.text
    eintrag = next(a for a in r.json()["message"]["anmeldungen"] if a["name"] == "A-HUB1")
    assert eintrag.get("gruppe") == "G-HUB", "Zielfeld `gruppe` fehlt im Hub"


# ── OP-ADMIN-19: Spalte „Felder“ zaehlt die Formularfelder ─────────────────


def test_anmeldeformulare_liefern_feldanzahl(client, seed_mitglieder, rollen, sess):
    """OP-ADMIN-19: die Liste liefert `felder_anzahl` je Formular (statt „–“)."""
    from diakronos_app.models.diakonos import Anmeldeformular, AnmeldeformularFeld

    sess.add(Anmeldeformular(name="F-1", bezeichnung="Standard", docstatus=0, idx=0))
    sess.add_all([
        AnmeldeformularFeld(
            name=f"F-1-{i}", parent="F-1", parenttype="Anmeldeformular",
            parentfield="felder", idx=i, label=f"Feld {i}", feldtyp="Text",
        )
        for i in range(3)
    ])
    sess.commit()

    r = client.post("/api/method/admin_hub.get_anmeldeformulare")
    assert r.status_code == 200, r.text
    formular = next(f for f in r.json()["message"]["formulare"] if f["name"] == "F-1")
    assert formular.get("felder_anzahl") == 3

