"""N4 — Dialog „Mitglied hinzufügen“: Dublettenprüfung beim Tippen.

Der Dialog fragt beim Verlassen eines Feldes den Server
(`mitglieder.pruefe_mitglied_dublette`), ob dieselbe Person schon existiert:
gleiche E-Mail blockiert das Speichern, gleicher Name warnt nur. Der Endpunkt
liefert dafür Name, Status und Gruppen der vorhandenen Person.

Die verbindliche Prüfung bleibt in `create_mitglied` (siehe
test_p1_9_mitglieder_kern.py) — dieser Endpunkt ist nur der Hinweis für die
Oberfläche und darf denselben Treffer melden.
"""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture()
def rollen(monkeypatch):
    """Mitgliederadministrator fuer die Endpunkte (Muster test_p1_9)."""
    from diakronos_app.api import mitglieder
    from diakronos_app.frappe_compat import permissions

    halt: dict[str, Any] = {"roles": ["Mitgliederadministrator"], "user": "admin@example.org"}
    hole = lambda user=None: list(halt["roles"])  # noqa: E731
    kein_gast = lambda user=None: False  # noqa: E731
    for mod in (permissions, mitglieder):
        if hasattr(mod, "get_roles"):
            monkeypatch.setattr(mod, "get_roles", hole)
        if hasattr(mod, "is_guest"):
            monkeypatch.setattr(mod, "is_guest", kein_gast)
    monkeypatch.setattr(mitglieder, "_is_admin", lambda: True)
    return halt


def _pruefe(client, **felder):
    return client.post("/api/method/mitglieder.pruefe_mitglied_dublette", json=felder)


def test_dublette_kein_treffer(client, seed_mitglieder, rollen):
    """Eine unbekannte Person meldet keinen Treffer."""
    r = _pruefe(client, vorname="Neo", nachname="Neu", email="neo@example.org")
    assert r.status_code == 200, r.text
    assert r.json()["message"]["dublette"] is None


def test_dublette_gleiche_email_meldet_treffer(client, seed_mitglieder, rollen):
    """Gleiche E-Mail -> Hinweis mit Grund „email“ und der vorhandenen Person."""
    r = _pruefe(client, vorname="Anders", nachname="Name", email="anna@example.org")
    assert r.status_code == 200, r.text
    d = r.json()["message"]["dublette"]
    assert d is not None
    assert d["grund"] == "email"
    assert d["mitglied_id"] == "M-0001"
    assert d["name"] == "Anna Beispiel"
    assert d["status"] == "Mitglied"


def test_dublette_email_ist_gross_klein_unabhaengig(client, seed_mitglieder, rollen):
    """OP-ADMIN-7: E-Mail wird normalisiert; „ANNA@…“ trifft „anna@…“."""
    r = _pruefe(client, vorname="", nachname="", email="  ANNA@Example.ORG ")
    assert r.status_code == 200, r.text
    d = r.json()["message"]["dublette"]
    assert d is not None and d["grund"] == "email" and d["mitglied_id"] == "M-0001"


def test_dublette_gleicher_name_warnt_nur(client, seed_mitglieder, rollen):
    """Gleicher Vor-/Nachname -> Grund „name“ (die Oberfläche warnt nur)."""
    r = _pruefe(client, vorname="Bruno", nachname="Brandner", email="")
    assert r.status_code == 200, r.text
    d = r.json()["message"]["dublette"]
    assert d is not None
    assert d["grund"] == "name"
    assert d["mitglied_id"] == "M-0002"


def test_dublette_email_hat_vorrang_vor_name(client, seed_mitglieder, rollen):
    """Passt beides, gewinnt die E-Mail (sie ist der harte Riegel)."""
    r = _pruefe(client, vorname="Anna", nachname="Beispiel", email="anna@example.org")
    assert r.status_code == 200, r.text
    assert r.json()["message"]["dublette"]["grund"] == "email"


def test_dublette_hinweis_nennt_gruppen(client, seed_mitglieder, rollen):
    """Der Hinweis nennt die Gruppen der vorhandenen Person (Konzept Abschn. 4).

    Regression: `get_all` mit `limit_page_length=0` lieferte NULL Zeilen — der
    Hinweis zeigte dann fälschlich „ohne Gruppe“. Gruppen entstehen sonst nur
    über einen eigenen Anlegeweg; hier direkt gesetzt, damit der Hinweis-Text
    wirklich geprüft wird.
    """
    from diakronos_app.models.diakonos import Gruppe, Gruppenmitgliedschaft

    sess = seed_mitglieder
    sess.add(Gruppe(name="G-1", gruppenname="Chor", docstatus=0, idx=0))
    sess.add(Gruppenmitgliedschaft(name="GM-1", parent="G-1", parenttype="Gruppe",
                                   parentfield="mitglieder", mitglied="M-0001",
                                   rolle="Mitglied", docstatus=0, idx=0))
    sess.commit()

    r = _pruefe(client, vorname="", nachname="", email="anna@example.org")
    assert r.status_code == 200, r.text
    d = r.json()["message"]["dublette"]
    assert d["gruppen"] == ["Chor"], d


def test_dublette_ohne_angaben_kein_treffer(client, seed_mitglieder, rollen):
    """Ohne E-Mail und ohne vollen Namen gibt es nichts zu vergleichen."""
    r = _pruefe(client, vorname="Nur", nachname="", email="")
    assert r.status_code == 200, r.text
    assert r.json()["message"]["dublette"] is None


def test_dublette_verlangt_admin(client, seed_mitglieder, monkeypatch):
    """Der Endpunkt ist auf Mitgliederadministratoren beschränkt."""
    from diakronos_app.api import mitglieder

    monkeypatch.setattr(mitglieder, "_is_admin", lambda: False)
    r = _pruefe(client, vorname="Anna", nachname="Beispiel", email="anna@example.org")
    assert r.status_code >= 400
    assert "administrator" in r.text.lower()
