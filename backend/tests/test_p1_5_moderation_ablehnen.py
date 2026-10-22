"""P1-5 — OP-EVENT-12: Moderation kann Vorschlaege mit Begruendung ablehnen.

Regressionstests fuer den Nachtbefund:

  * Es gab KEIN „Ablehnen mit Begruendung". Der einzige Weg war
    Kalender -> Bearbeitungsmodus -> Loeschen (ohne Grund, ohne Nachricht an
    den Antragsteller).
  * Die Moderationskarte zeigte den Antragsteller nicht.

Neu:
  * `resolve_conflict(action="ablehnen", grund=...)` -> Status „Abgelehnt",
    Grund wird an die Beschreibung angehaengt, der Antragsteller bekommt eine
    Nachricht (Notification Log, dieselbe Quelle wie useNotifications).
  * Der Grund ist Pflicht — auch auf Serverseite.
  * `_fmt_event` liefert `owner` und `antragsteller` mit.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from diakronos_app.frappe_compat.query import get_all, get_value
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import NotificationLog, User
from diakronos_app.models.kronos import Element, Kalender, KalenderModerator

KANBAN_MODUL = "diakronos.kronos.api.kanban_api"
KALENDER = "KAL-ABLEHNEN"
ANTRAgSTELLER = "anna@example.org"
MODERATOR = "moderator@example.org"


@pytest.fixture()
def welt(patched_db):
    sess = patched_db()

    tag = (datetime.now() + timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)

    sess.add_all([
        User(name=ANTRAgSTELLER, full_name="Anna Antrag",
             enabled=1, user_type="System User"),
        User(name=MODERATOR, full_name="Mara Moderator",
             enabled=1, user_type="System User"),
        Kalender(name=KALENDER, calendar_name="Gemeinde", calendar_color="#111111",
                 selbstverwaltet=0, docstatus=0, idx=0),
        KalenderModerator(name="KM-1", parent=KALENDER, parenttype="Kalender",
                          parentfield="kalendermoderatoren", user=MODERATOR,
                          docstatus=0, idx=1),
        Element(name="ELE-VS", element_name="Adventssingen", element_calendar=KALENDER,
                status="Vorschlag", owner=ANTRAgSTELLER,
                description="Bitte um 18:00",
                element_start=tag.replace(hour=18), element_end=tag.replace(hour=20),
                all_day=0, series_id="", docstatus=0, idx=0),
    ])
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def als_moderator(patched_db, welt):
    """`set_user` gilt nur, solange die Test-Naht offen ist (Kontextmanager) —
    die Naht liegt deshalb INNERHALB des Tests, nicht in einer Fixture darum.

    B-1: Die Fixture haengt von `welt` ab. Ohne diese Abhaengigkeit kam sie
    VOR `welt` dran und die Tests liefen gegen eine leere Datenbank
    („Termin nicht gefunden")."""
    set_user(MODERATOR)
    yield MODERATOR
    set_user("Administrator")


# ── Ablehnen ────────────────────────────────────────────────────────────────


def test_ablehnen_ohne_grund_wird_abgelehnt(client, als_moderator):
    r = client.post(f"/api/method/{KANBAN_MODUL}.resolve_conflict",
                    data={"element_id": "ELE-VS", "action": "ablehnen"})
    assert r.status_code == 417, r.text
    assert "Grund" in r.text

    # Status bleibt unveraendert.
    assert get_value("Element", "ELE-VS", "status") == "Vorschlag"


def test_ablehnen_setzt_status_und_grund_in_eigenem_feld(client, als_moderator):
    r = client.post(f"/api/method/{KANBAN_MODUL}.resolve_conflict",
                    data={"element_id": "ELE-VS", "action": "ablehnen",
                          "grund": "Raum ist an dem Abend belegt."})
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["new_status"] == "Abgelehnt"
    assert msg["action"] == "ablehnen"

    assert get_value("Element", "ELE-VS", "status") == "Abgelehnt"
    # W-1: Der Grund steht in einem eigenen Feld …
    assert get_value("Element", "ELE-VS", "ablehnungs_grund") == "Raum ist an dem Abend belegt."
    assert get_value("Element", "ELE-VS", "moderiert_von") == MODERATOR
    # … und NICHT in der oeffentlichen Beschreibung (alter Text bleibt unberuehrt).
    beschreibung = get_value("Element", "ELE-VS", "description")
    assert beschreibung == "Bitte um 18:00"
    assert "Abgelehnt" not in beschreibung
    assert "Raum ist an dem Abend belegt." not in beschreibung


def test_abgelehnter_termin_verschwindet_aus_dem_kalender(client, als_moderator):
    """W-1: Ein abgelehnter Termin erscheint fuer niemanden mehr im Kalender —
    auch nicht im Bearbeitungsmodus der Moderatoren."""
    tag = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    modul = "diakronos.kronos.calendar_get"

    r = client.post(f"/api/method/{KANBAN_MODUL}.resolve_conflict",
                    data={"element_id": "ELE-VS", "action": "ablehnen", "grund": "Doppelbuchung"})
    assert r.status_code == 200, r.text

    # Bearbeitungsmodus (view_mode=False) — der Termin ist weg.
    r = client.get(f"/api/method/{modul}.get_calendar_events",
                   params={"start_date": tag, "end_date": tag, "view_mode": "false"})
    assert r.status_code == 200, r.text
    ids = [e["id"] for e in r.json()["message"]]
    assert "ELE-VS" not in ids, ids

    # Moderations-Historie: nur hier bleibt er sichtbar, mit Grund.
    r = client.get(f"/api/method/{KANBAN_MODUL}.get_kanban_board_data")
    board = r.json()["message"]
    assert "ELE-VS" not in [v["id"] for v in board["vorschlaege"]]
    assert "ELE-VS" not in [v["id"] for v in board["konflikte"]]
    historie = next(v for v in board["abgelehnt"] if v["id"] == "ELE-VS")
    assert historie["ablehnungs_grund"] == "Doppelbuchung"
    assert historie["moderiert_von"] == MODERATOR


def test_ablehnen_nachricht_an_den_antragsteller(client, als_moderator):
    r = client.post(f"/api/method/{KANBAN_MODUL}.resolve_conflict",
                    data={"element_id": "ELE-VS", "action": "ablehnen",
                          "grund": "Doppelbuchung"})
    assert r.status_code == 200, r.text

    nachrichten = get_all(
        "Notification Log",
        filters={"for_user": ANTRAgSTELLER},
        fields=["subject", "email_content"],
    )
    assert len(nachrichten) == 1
    assert "Adventssingen" in nachrichten[0]["subject"]
    assert "Doppelbuchung" in nachrichten[0]["email_content"]


def test_ablehnen_ohne_moderationsrecht_verboten(client, welt):
    """Ein normales Mitglied darf nicht ablehnen (OP-EVENT-1 bleibt gueltig)."""
    set_user(ANTRAgSTELLER)
    try:
        r = client.post(f"/api/method/{KANBAN_MODUL}.resolve_conflict",
                        data={"element_id": "ELE-VS", "action": "ablehnen",
                              "grund": "weil ich es kann"})
        assert r.status_code == 403, r.text
    finally:
        set_user("Administrator")

    assert get_value("Element", "ELE-VS", "status") == "Vorschlag"


# ── Antragsteller auf der Karte ─────────────────────────────────────────────


def test_board_data_liefert_antragsteller(client, als_moderator):
    r = client.get(f"/api/method/{KANBAN_MODUL}.get_kanban_board_data")
    assert r.status_code == 200, r.text
    board = r.json()["message"]
    karte = next(v for v in board["vorschlaege"] if v["id"] == "ELE-VS")
    assert karte["owner"] == ANTRAgSTELLER
    # Klarname aus dem User-Datensatz.
    assert karte["antragsteller"] == "Anna Antrag"
