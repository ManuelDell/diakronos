"""P4k: Tests fuer die portierten Restendpunkte in `admin_hub`.

Quelle: referenz/diakronos-frappe/diakonos/diakonos/api/admin_hub.py
Neu portiert: get_dsgvo_uebersicht, get_anmeldungen_hub, genehmige_anmeldung,
lehne_anmeldung_ab, get_anmeldeformulare, create_anmeldeformular,
update_anmeldeformular_felder
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest


@pytest.fixture()
def rollen(monkeypatch):
    from diakronos_app.api import admin_hub
    from diakronos_app.frappe_compat import permissions

    halt: dict[str, Any] = {"roles": ["Mitgliederadministrator"]}
    hole = lambda user=None: list(halt["roles"])   # noqa: E731
    for mod in (permissions, admin_hub):
        if hasattr(mod, "get_roles"):
            monkeypatch.setattr(mod, "get_roles", hole)
    monkeypatch.setattr(permissions, "is_guest", lambda user=None: False)
    return halt


@pytest.fixture()
def sess(patched_db):
    s = patched_db()
    yield s
    s.close()


# ── Admin-Gate fuer alle neuen Endpunkte ────────────────────────────────────


@pytest.mark.parametrize("name", [
    "get_dsgvo_uebersicht", "get_anmeldungen_hub", "get_anmeldeformulare",
])
def test_neue_lese_endpunkte_brauchen_adminrolle(client, seed_mitglieder, rollen, name):
    rollen["roles"] = []
    r = client.get(f"/api/method/admin_hub.{name}")
    assert r.status_code == 403, r.text
    assert r.json()["exception"] == "PermissionError"


def test_alle_p4k_admin_hub_endpunkte_sind_registriert():
    from diakronos_app.frappe_compat.registry import lookup, options_for

    for name in ("get_dsgvo_uebersicht", "get_anmeldungen_hub", "genehmige_anmeldung",
                 "lehne_anmeldung_ab", "get_anmeldeformulare", "create_anmeldeformular",
                 "update_anmeldeformular_felder"):
        fn = lookup(f"admin_hub.{name}")
        assert fn is not None, f"admin_hub.{name} nicht registriert"
        assert options_for(fn)["allow_guest"] is False, f"{name} darf nicht Guest sein"


# ── DSGVO-Uebersicht ────────────────────────────────────────────────────────


def test_dsgvo_uebersicht_struktur(client, seed_mitglieder, rollen, sess):
    from diakronos_app.models.diakonos import DSGVOEinwilligung

    sess.add_all([
        DSGVOEinwilligung(name="DSG-1", mitglied="M-0001", aktion="erteilt"),
        DSGVOEinwilligung(name="DSG-2", mitglied="M-0002", aktion="widerrufen"),
    ])
    sess.commit()

    r = client.get("/api/method/admin_hub.get_dsgvo_uebersicht")
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert isinstance(msg, (dict, list)), msg


def test_dsgvo_uebersicht_leer_ist_ok(client, seed_mitglieder, rollen):
    r = client.get("/api/method/admin_hub.get_dsgvo_uebersicht")
    assert r.status_code == 200, r.text


# ── Anmeldungen-Hub ─────────────────────────────────────────────────────────


def test_anmeldungen_hub_zeigt_offene(client, seed_mitglieder, rollen, sess):
    from diakronos_app.models.diakonos import Anmeldung

    sess.add_all([
        Anmeldung(name="ANM-1", status="Anmeldeanfrage", anmeldedatum=date.today()),
        Anmeldung(name="ANM-2", status="Ausstehend", anmeldedatum=date.today()),
        Anmeldung(name="ANM-3", status="Bestaetigt", anmeldedatum=date.today()),
    ])
    sess.commit()

    r = client.get("/api/method/admin_hub.get_anmeldungen_hub")
    assert r.status_code == 200, r.text
    assert "ANM-1" in r.text


# ── Genehmigen / Ablehnen ───────────────────────────────────────────────────


def test_genehmige_anmeldung_setzt_bestaetigt(client, seed_mitglieder, rollen, sess):
    from diakronos_app.models.diakonos import Anmeldung

    sess.add(Anmeldung(name="ANM-G", status="Anmeldeanfrage", anmeldedatum=date.today()))
    sess.commit()

    r = client.post("/api/method/admin_hub.genehmige_anmeldung",
                    json={"anmeldung_id": "ANM-G"})
    assert r.status_code == 200, r.text
    sess.expire_all()
    assert sess.get(Anmeldung, "ANM-G").status in {"Bestaetigt", "Bestätigt"}


def test_lehne_anmeldung_ab_setzt_abgelehnt(client, seed_mitglieder, rollen, sess):
    from diakronos_app.models.diakonos import Anmeldung

    sess.add(Anmeldung(name="ANM-L", status="Anmeldeanfrage", anmeldedatum=date.today()))
    sess.commit()

    r = client.post("/api/method/admin_hub.lehne_anmeldung_ab",
                    json={"anmeldung_id": "ANM-L", "grund": "Kein Bedarf"})
    assert r.status_code == 200, r.text
    sess.expire_all()
    assert sess.get(Anmeldung, "ANM-L").status in {"Abgelehnt", "abgelehnt"}


def test_genehmige_unbekannte_anmeldung_scheitert(client, seed_mitglieder, rollen):
    r = client.post("/api/method/admin_hub.genehmige_anmeldung",
                    json={"anmeldung_id": "ANM-999"})
    assert r.status_code >= 400, r.text


# ── Anmeldeformulare ────────────────────────────────────────────────────────


def test_anmeldeformulare_liste_leer_ok(client, seed_mitglieder, rollen):
    r = client.get("/api/method/admin_hub.get_anmeldeformulare")
    assert r.status_code == 200, r.text


def test_create_anmeldeformular_legt_an(client, seed_mitglieder, rollen, sess):
    from diakronos_app.models.diakonos import Anmeldeformular

    r = client.post("/api/method/admin_hub.create_anmeldeformular",
                    json={"bezeichnung": "Sommerfest 2026", "aktiv": 1})
    assert r.status_code == 200, r.text
    treffer = [f for f in sess.query(Anmeldeformular).all()
               if f.bezeichnung == "Sommerfest 2026"]
    assert len(treffer) == 1
