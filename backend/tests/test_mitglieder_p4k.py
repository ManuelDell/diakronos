"""P4k: Tests fuer die portierten Restendpunkte in `mitglieder`.

Quelle: referenz/diakronos-frappe/diakronos/diakonos/api/mitglieder.py
Deckt die 7 neu portierten Funktionen ab:
  get_adressbuch, create_mitglied, update_mitglied,
  update_mitglied_with_confirmation, get_gruppen_for_mitglied,
  get_beziehungen_for_mitglied, widerruf_einwilligung
Sowie die Sichtbarkeitsregel (Nicht-Admin sieht fremde Daten NICHT).
"""

from __future__ import annotations

import json
from typing import Any

import pytest


@pytest.fixture()
def rollen(monkeypatch):
    from diakronos_app.api import mitglieder
    from diakronos_app.frappe_compat import permissions

    halt: dict[str, Any] = {"roles": ["Mitgliederadministrator"], "user": "admin@example.org"}
    hole = lambda user=None: list(halt["roles"])   # noqa: E731
    for mod in (permissions, mitglieder):
        if hasattr(mod, "get_roles"):
            monkeypatch.setattr(mod, "get_roles", hole)
    # `mitglieder` hat `is_admin`/`mitglied_permissions` per `from ... import`
    # gebunden — Patches auf `permissions` allein greifen dort nicht.
    monkeypatch.setattr(mitglieder, "_is_admin", lambda: True)
    monkeypatch.setattr(permissions, "is_guest", lambda user=None: False)
    return halt


@pytest.fixture()
def sess(patched_db):
    s = patched_db()
    yield s
    s.close()


# ── Widerruf ────────────────────────────────────────────────────────────────


def test_widerruf_legt_dsgvo_zeile_mit_aktion_widerrufen_an(client, seed_mitglieder, rollen, sess):
    """Der Altcode loggt NUR zuvor gesetzte Einwilligungen (Quelle: 473-509).

    Also erst eine Einwilligung setzen, dann widerrufen -> genau eine Zeile.
    """
    from diakronos_app.models.diakonos import DSGVOEinwilligung, Mitglied

    m = sess.get(Mitglied, "M-0001")
    m.datenschutz_einwilligung = True
    sess.commit()

    r = client.post("/api/method/mitglieder.widerruf_einwilligung",
                    json={"mitglied_id": "M-0001"})
    assert r.status_code == 200, r.text

    sess.expire_all()
    zeilen = sess.query(DSGVOEinwilligung).filter_by(mitglied="M-0001").all()
    assert zeilen, "Widerruf muss eine DSGVO-Zeile fuer die gesetzte Einwilligung anlegen"
    assert all(z.aktion == "widerrufen" for z in zeilen), [z.aktion for z in zeilen]
    assert sess.get(Mitglied, "M-0001").datenschutz_einwilligung in (False, 0, None)


def test_widerruf_ohne_gesetzte_einwilligung_loggt_nichts(client, seed_mitglieder, rollen, sess):
    """Ohne vorher gesetzte Einwilligung entsteht keine Zeile (kein Rauschen)."""
    from diakronos_app.models.diakonos import DSGVOEinwilligung

    r = client.post("/api/method/mitglieder.widerruf_einwilligung",
                    json={"mitglied_id": "M-0002"})
    assert r.status_code == 200, r.text
    assert sess.query(DSGVOEinwilligung).filter_by(mitglied="M-0002").all() == []


def test_widerruf_ist_nicht_guest(client):
    from diakronos_app.api import mitglieder as m
    from diakronos_app.frappe_compat.registry import lookup, options_for

    fn = lookup("mitglieder.widerruf_einwilligung")
    assert fn is m.widerruf_einwilligung
    assert options_for(fn)["allow_guest"] is False


# ── Adressbuch ──────────────────────────────────────────────────────────────


def test_adressbuch_admin_sieht_alle(client, seed_mitglieder, rollen):
    r = client.get("/api/method/mitglieder.get_adressbuch")
    assert r.status_code == 200, r.text
    namen = {e.get("name") for e in r.json()["message"]["data"]}
    assert {"M-0001", "M-0002", "M-0003"} <= namen


def test_adressbuch_suche_filtert(client, seed_mitglieder, rollen):
    r = client.get("/api/method/mitglieder.get_adressbuch", params={"suche": "Bruno"})
    assert r.status_code == 200, r.text
    namen = {e.get("name") for e in r.json()["message"]["data"]}
    assert "M-0002" in namen
    assert "M-0001" not in namen


def test_adressbuch_maskiert_nicht_freigegebene_felder(client, seed_mitglieder, rollen, sess):
    """Default-Sichtbarkeit: email/telefon sichtbar, adresse/geburtstag NICHT."""
    from diakronos_app.models.diakonos import Mitglied

    m = sess.get(Mitglied, "M-0001")
    m.adressbuch_sichtbarkeit = json.dumps(
        {"email": True, "telefonnummer": False, "adresse": False, "geburtstag": False})
    sess.commit()

    r = client.get("/api/method/mitglieder.get_adressbuch")
    assert r.status_code == 200, r.text
    e = next(x for x in r.json()["message"]["data"] if x.get("name") == "M-0001")
    assert e.get("email") == "anna@example.org"
    assert not e.get("telefonnummer"), f"telefonnummer muss maskiert sein: {e}"
    assert not e.get("adresse"), f"adresse muss maskiert sein: {e}"


def test_adressbuch_nicht_admin_sieht_fremde_nicht(client, seed_mitglieder, rollen, monkeypatch):
    """Sichtbarkeitsregel: Nicht-Admin sieht nicht die ganze Gemeinde."""
    from diakronos_app.api import mitglieder

    rollen["roles"] = ["Mitglied"]
    monkeypatch.setattr(mitglieder, "_is_admin", lambda: False)
    monkeypatch.setattr(mitglieder, "_user_email", lambda: "clara@example.org")

    r = client.get("/api/method/mitglieder.get_adressbuch")
    assert r.status_code == 200, r.text
    namen = {e.get("name") for e in r.json()["message"]["data"]}
    assert "M-0001" not in namen, f"Anna darf fuer Clara nicht sichtbar sein: {namen}"
    assert "M-0002" not in namen, f"Bruno darf fuer Clara nicht sichtbar sein: {namen}"


# ── create_mitglied ─────────────────────────────────────────────────────────


def test_create_mitglied_legt_an(client, seed_mitglieder, rollen, sess):
    from diakronos_app.models.diakonos import Mitglied

    r = client.post("/api/method/mitglieder.create_mitglied",
                    json={"vorname": "Dora", "nachname": "Dorn", "email": "dora@example.org",
                          "status": "Gast"})
    assert r.status_code == 200, r.text
    neu = [m for m in sess.query(Mitglied).all() if m.nachname == "Dorn"]
    assert len(neu) == 1
    assert neu[0].vorname == "Dora"
    assert neu[0].status == "Gast"


def test_create_mitglied_verlangt_vorname_und_nachname(client, seed_mitglieder, rollen):
    r = client.post("/api/method/mitglieder.create_mitglied", json={"vorname": "Nur"})
    assert r.status_code == 417, r.text
    assert r.json().get("exception") in {"ValidationError", "MandatoryError"}


# ── update_mitglied ─────────────────────────────────────────────────────────


def test_update_mitglied_schreibt_feld(client, seed_mitglieder, rollen, sess):
    from diakronos_app.models.diakonos import Mitglied

    r = client.post("/api/method/mitglieder.update_mitglied",
                    json={"mitglied_id": "M-0001", "data": {"vorname": "Annelie"}})
    assert r.status_code == 200, r.text
    sess.expire_all()
    assert sess.get(Mitglied, "M-0001").vorname == "Annelie"


def test_update_mitglied_ignoriert_unbekannte_felder(client, seed_mitglieder, rollen, sess):
    """Feldinjektion: nicht deklarierte Felder duerfen nicht durchgereicht werden."""
    from diakronos_app.models.diakonos import Mitglied

    r = client.post("/api/method/mitglieder.update_mitglied",
                    json={"mitglied_id": "M-0001",
                          "data": {"vorname": "Ok", "harmlos_aber_fremd": "X"}})
    assert r.status_code == 200, r.text
    sess.expire_all()
    m = sess.get(Mitglied, "M-0001")
    assert m.vorname == "Ok"
    assert not hasattr(m, "harmlos_aber_fremd")


def test_update_mitglied_unbekanntes_mitglied_scheitert(client, seed_mitglieder, rollen):
    r = client.post("/api/method/mitglieder.update_mitglied",
                    json={"mitglied_id": "M-9999", "data": {"vorname": "X"}})
    assert r.status_code >= 400, r.text
    assert r.json().get("exception") in {"DoesNotExistError", "ValidationError"}


def test_update_mitglied_with_confirmation_braucht_bestaetigung(client, seed_mitglieder, rollen):
    """`audit_confirmation` ist Pflichtparameter (Quelle: mitglieder.py:372) — ohne
    sie darf gar kein Schreibzugriff starten."""
    r = client.post("/api/method/mitglieder.update_mitglied_with_confirmation",
                    json={"mitglied_id": "M-0001", "data": {"vorname": "Neu"}})
    assert r.status_code >= 400, r.text


def test_update_mitglied_with_confirmation_schreibt_mit_bestaetigung(client, seed_mitglieder, rollen, sess):
    from diakronos_app.models.diakonos import Mitglied

    r = client.post("/api/method/mitglieder.update_mitglied_with_confirmation",
                    json={"mitglied_id": "M-0001", "data": {"vorname": "Bestaetigt"},
                          "audit_confirmation": {"bestaetigt": True}})
    assert r.status_code == 200, r.text
    sess.expire_all()
    assert sess.get(Mitglied, "M-0001").vorname == "Bestaetigt"


# ── Gruppen / Beziehungen ───────────────────────────────────────────────────


def test_get_gruppen_for_mitglied_struktur_ohne_mitgliedschaft(client, seed_mitglieder, rollen):
    """Ohne Mitgliedschaft bleiben nur die ancestor_path-Segmente (Quelle: 410-446)."""
    r = client.post("/api/method/mitglieder.get_gruppen_for_mitglied",
                    json={"mitglied_id": "M-0001"})
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["success"] is True
    assert isinstance(msg["data"], list)


def test_get_beziehungen_for_mitglied_leer_ohne_daten(client, seed_mitglieder, rollen):
    r = client.post("/api/method/mitglieder.get_beziehungen_for_mitglied",
                    json={"mitglied_id": "M-0001"})
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["success"] is True
    assert msg["data"] == []


def test_alle_p4k_mitglieder_endpunkte_sind_registriert():
    from diakronos_app.frappe_compat.registry import lookup, options_for

    for name in ("get_adressbuch", "create_mitglied", "update_mitglied",
                 "update_mitglied_with_confirmation", "get_gruppen_for_mitglied",
                 "get_beziehungen_for_mitglied", "widerruf_einwilligung",
                 "set_mitglied_status", "schliesse_mitglied_aus",
                 "import_mitglieder_vorschau", "import_mitglieder_uebernehmen"):
        fn = lookup(f"mitglieder.{name}")
        assert fn is not None, f"mitglieder.{name} nicht registriert"
        assert options_for(fn)["allow_guest"] is False, f"{name} darf nicht Guest sein"
