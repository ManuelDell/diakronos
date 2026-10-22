"""ID-1e (N4): das Adressbuch liefert Nicht-Admins keinen Klarnamen mehr.

WARUM DIESER TEST HIER STEHT
----------------------------
R-ID-1/N4: Den Fix in `api/mitglieder.py::get_adressbuch` (Kürzung ausgetretener
Personen über `personen_anzeige.kuerze_zeilen`) belegte bisher NUR
`tests/test_id1_leak.py` — und der läuft ausschließlich mit `ID1_POSTGRES_URL`,
also nie in der normalen SQLite-Suite. Ein unbeabsichtigtes Zurückdrehen wäre
still geblieben.

WAS ER PRÜFT (ohne PostgreSQL, ohne ID1_POSTGRES_URL)
-----------------------------------------------------
Ein Mitglied ohne Verwaltungsrolle ruft `get_adressbuch` auf und bekommt für
eine AUSGETRETENE Person der eigenen Gruppe die Kurzform („Vorname N.“, kein
Nachname, maskierte Adresse) — für eine aktive Person dagegen den Klarnamen.
Die Gegenprobe schließt den Leerlauf aus: ohne sie wäre „kein Klarname“ auch
dann grün, wenn der Leser die Person gar nicht sieht.
"""
from __future__ import annotations

import json

import pytest

from tests.test_permissions import hierarchie  # noqa: F401 — Fixture

#: Ausgetretene Person in DB-A (derselben Welt wie `mitglied-a`).
AUSGETRETEN = "M-verantw-a"
AKTIV = "M-untergruppe-a1"
LESER = "mitglied-a@example.org"


@pytest.fixture()
def sess(patched_db):
    s = patched_db()
    yield s
    s.close()


def _set_user(user: str) -> None:
    from diakronos_app.frappe_compat.session import set_user

    set_user(user)


def _austreten(sess) -> None:
    """Die Zielperson austreten lassen — über dasselbe Merkmal wie der Austritt.

    ``personen_anzeige.ist_ausgeschieden`` fragt Status ODER `austritt_datum`;
    gesetzt wird hier beides, wie `api/austritt.mitglied_austritt` es tut.
    """
    from datetime import date

    from diakronos_app.models.diakonos import Mitglied

    m = sess.get(Mitglied, AUSGETRETEN)
    m.status = "Ausgetreten"
    m.austritt_datum = date(2026, 10, 1)
    sess.commit()


def _adressbuch(client) -> dict[str, dict]:
    r = client.get("/api/method/mitglieder.get_adressbuch", params={"suche": ""})
    assert r.status_code == 200, r.text
    return {z["name"]: z for z in r.json()["message"]["data"]}


def test_adressbuch_kuerzt_ausgetretene_fuer_nicht_admin(client, hierarchie, sess):  # noqa: F811
    """Der Kern von N4: kein Klarname, keine Klar-Mail, kein Nachname."""
    _austreten(sess)
    _set_user(LESER)
    zeilen = _adressbuch(client)

    assert AUSGETRETEN in zeilen, "Testaufbau: der Leser sieht die Person nicht"
    zeile = zeilen[AUSGETRETEN]
    # Kurzform „Vera A.“ im Feld `vorname` (dieselbe Regel wie Liste/Detail).
    assert zeile["vorname"] == "Vera A.", zeile
    assert not zeile["nachname"], zeile
    assert "Vera A." not in json.dumps(zeilen.get(AKTIV, {})), zeile
    # Die Adresse ist maskiert (ausgetreten = keine Klar-Mail), egal wie die
    # Freigabe steht: `kuerze` setzt sie immer auf die Kurzform.
    assert zeile["email"] in (None, "ver*******.org"), zeile


def test_adressbuch_zeigt_aktive_person_weiter_mit_namen(client, hierarchie, sess):  # noqa: F811
    """Gegenprobe: der Test ist nicht grün, weil das Adressbuch leer ist."""
    _austreten(sess)
    _set_user(LESER)
    zeilen = _adressbuch(client)
    assert AKTIV in zeilen, "Testaufbau: aktive Person fehlt — Probe wäre leer"
    assert zeilen[AKTIV]["vorname"] == "Ulrike", zeilen[AKTIV]
    assert zeilen[AKTIV]["nachname"] == "A", zeilen[AKTIV]
