"""N1: „Datenschutz offen“ zählt PERSONEN, nicht Protokollzeilen (UXD-R16).

Vorher zählte `get_statistik` die Zeilen in „DSGVO Einwilligung“ — auch Foto-
und Werbe-Einträge. Die Kachel zeigte damit mehr als es Personen gibt. Jetzt
ist `Mitglied.datenschutz_einwilligung` die maßgebliche Quelle.
"""

from __future__ import annotations

from datetime import datetime
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


def test_datenschutz_kachel_zaehlt_personen(client, seed_mitglieder, rollen):
    """Mehrere Protokollzeilen für EINE Person dürfen die Zahl nicht erhöhen."""
    from diakronos_app.models.diakonos import DSGVOEinwilligung, Mitglied

    # Zwei von drei Personen haben eingewilligt.
    seed_mitglieder.query(Mitglied).filter(Mitglied.name == "M-0001").update(
        {"datenschutz_einwilligung": True})
    seed_mitglieder.query(Mitglied).filter(Mitglied.name == "M-0002").update(
        {"datenschutz_einwilligung": True})
    # Für M-0001 gibt es MEHRERE Protokollzeilen (Einwilligung, Foto, Werbung).
    seed_mitglieder.add_all([
        DSGVOEinwilligung(name="DSG-1", mitglied="M-0001", aktion="erteilt", typ="datenschutz"),
        DSGVOEinwilligung(name="DSG-2", mitglied="M-0001", aktion="erteilt", typ="foto"),
        DSGVOEinwilligung(name="DSG-3", mitglied="M-0001", aktion="erteilt", typ="werbung"),
    ])
    seed_mitglieder.commit()

    r = client.get("/api/method/admin_hub.get_statistik")
    assert r.status_code == 200, r.text
    dsgvo = r.json()["message"]["dsgvo"]

    assert dsgvo["ok"] == 2, f"2 Personen mit Einwilligung erwartet, war {dsgvo['ok']}"
    assert dsgvo["fehlt"] == 1, f"1 Person ohne Einwilligung erwartet, war {dsgvo['fehlt']}"


def test_datenschutz_widerruf_zaehlt_personen(client, seed_mitglieder, rollen):
    """Der Widerruf-Zähler zählt PERSONEN mit jüngstem Widerruf (UXD-R16).

    Mehrere Widerrufszeilen EINER Person zählen einmal; ein Foto-Widerruf
    (typ != "datenschutz") zählt gar nicht.
    """
    from diakronos_app.models.diakonos import DSGVOEinwilligung

    seed_mitglieder.add_all([
        DSGVOEinwilligung(name="DSG-1", mitglied="M-0001", typ="datenschutz",
                          aktion="erteilt", zeitstempel=datetime(2026, 1, 1)),
        # M-0002 widerruft zweimal — zählt als EINE Person.
        DSGVOEinwilligung(name="DSG-2", mitglied="M-0002", typ="datenschutz",
                          aktion="erteilt", zeitstempel=datetime(2026, 1, 1)),
        DSGVOEinwilligung(name="DSG-3", mitglied="M-0002", typ="datenschutz",
                          aktion="widerrufen", zeitstempel=datetime(2026, 2, 1)),
        DSGVOEinwilligung(name="DSG-4", mitglied="M-0002", typ="datenschutz",
                          aktion="widerrufen", zeitstempel=datetime(2026, 3, 1)),
        # Foto-Widerruf darf nicht als Datenschutz-Widerruf zählen.
        DSGVOEinwilligung(name="DSG-5", mitglied="M-0003", typ="foto",
                          aktion="widerrufen", zeitstempel=datetime(2026, 3, 1)),
    ])
    seed_mitglieder.commit()

    r = client.get("/api/method/admin_hub.get_statistik")
    assert r.status_code == 200, r.text
    assert r.json()["message"]["dsgvo"]["widerrufen"] == 1
