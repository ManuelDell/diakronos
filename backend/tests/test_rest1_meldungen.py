"""REST-1 (5)/(6) — Meldungen an Eingeteilte: Ressourcen-Aenderung und Absage.

Befund (5) aus der Boardpruefung: Aendert ein MODERATOR an einem festgelegten
Termin nur die zusaetzlichen Ressourcen (Ort wechselt von „Gemeindehaus“ auf
„Jugendraum“), erfuhr die eingeteilte Person nichts — der alt/neu-Vergleich
liess `zusaetzliche_ressourcen` aus.

Befund (6) (P2-1/P2-4c sollten es erledigt haben): Einzeltermin und Serie
loeschen muss den Eingeteilten eine Absage schicken.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User, UserRole
from diakronos_app.models.diakonos import Mitglied
from diakronos_app.models.kronos import (
    Element,
    ElementMitarbeiter,
    ElementRessource,
    Kalender,
    KalenderModerator,
)
from diakronos_app.models.core import NotificationLog

EVENT_MODUL = "diakronos.kronos.api.event_crud"

ANNA = "anna@example.org"
MODERATOR = "moderator@example.org"
KALENDER = "Gemeinde"


@pytest.fixture()
def welt(patched_db):
    """Kalender mit Leserecht fuer Alle, Mitglied mit Konto, Moderator."""
    sess = patched_db()
    sess.add_all([
        User(name=ANNA, email=ANNA, full_name="Anna Beispiel", enabled=True),
        User(name=MODERATOR, email=MODERATOR, full_name="Moderator", enabled=True),
        Mitglied(name="M-0001", vorname="Anna", nachname="Beispiel",
                 email=ANNA, user=ANNA, status="Mitglied", docstatus=0, idx=0,
                 ancestor_path="/M-0001"),
        Kalender(name=KALENDER, calendar_name=KALENDER,
                 selbstverwaltet=0, docstatus=0, idx=0),
        HasRole(name="HR-KALMOD", parent=MODERATOR, parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
        UserRole(name="UR-GEM-LESEN", parent=KALENDER, parenttype="Kalender",
                 parentfield="leserechte", role="All", docstatus=0, idx=1),
        UserRole(name="UR-GEM-SCHREIB", parent=KALENDER, parenttype="Kalender",
                 parentfield="schreibrechte", role="All", docstatus=0, idx=2),
        KalenderModerator(name="KM-1", parent=KALENDER, parenttype="Kalender",
                          parentfield="kalendermoderatoren", user=MODERATOR,
                          docstatus=0, idx=1),
    ])
    sess.commit()
    yield sess
    sess.close()


def _termin(sess, name="EL-1", status="Festgelegt", mitarbeiter=True):
    start = (datetime.now() + timedelta(days=10)).replace(microsecond=0)
    sess.add(Element(
        name=name, element_name="Chorprobe", element_start=start,
        element_end=start + timedelta(hours=2), element_calendar=KALENDER,
        ressource=None, status=status, ignore_conflict=0, docstatus=0, idx=0,
        owner=MODERATOR,
    ))
    sess.add(ElementRessource(
        name="ER-" + name, parent=name, parenttype="Element",
        parentfield="zusaetzliche_ressourcen", ressource=None,
        freitext_ressource="Gemeindehaus", status="Bestätigt", notiz="",
        docstatus=0, idx=1,
    ))
    if mitarbeiter:
        sess.add(ElementMitarbeiter(
            name="EM-" + name, parent=name, parenttype="Element",
            parentfield="mitarbeiter", mitglied="M-0001", dienstrolle=None,
            bestaetigt=True, notiz="", docstatus=0, idx=1,
        ))
    sess.commit()


def _meldungen(sess, user=ANNA):
    sess.expire_all()
    return sess.query(NotificationLog).filter(NotificationLog.for_user == user).all()


@pytest.fixture()
def als_moderator(welt):
    set_user(MODERATOR)
    yield MODERATOR
    set_user("Administrator")


def test_moderator_ressourcenwechsel_meldet_eingeteilte(client, welt, als_moderator):
    """Wirksame Aenderung der weiteren Orte meldet die eingeteilte Person."""
    _termin(welt)

    r = client.post(f"/api/method/{EVENT_MODUL}.update_event", json={
        "name": "EL-1",
        "zusaetzliche_ressourcen": [
            {"freitext_ressource": "Jugendraum", "status": "Bestätigt"},
        ],
    })
    assert r.status_code == 200, r.text
    assert not r.json()["message"].get("aenderung_wartet")

    meldungen = _meldungen(welt)
    assert meldungen, "Eingeteilte Person wurde nicht benachrichtigt"
    assert "Weitere Orte/Ressourcen" in meldungen[0].email_content, meldungen[0].email_content


def test_unveraenderte_ressourcen_melden_nichts(client, welt, als_moderator):
    """Gegenprobe: derselbe Stand erzeugt keine Nachricht (B-2)."""
    _termin(welt)

    r = client.post(f"/api/method/{EVENT_MODUL}.update_event", json={
        "name": "EL-1",
        "zusaetzliche_ressourcen": [
            {"freitext_ressource": "Gemeindehaus", "status": "Bestätigt"},
        ],
    })
    assert r.status_code == 200, r.text
    assert _meldungen(welt) == []


def test_einzeltermin_loeschen_schickt_absage(client, welt, als_moderator):
    """(6) Einzeltermin: Eingeteilte bekommen eine Absage."""
    _termin(welt, "EL-2")

    r = client.post(f"/api/method/{EVENT_MODUL}.delete_event", json={"name": "EL-2"})
    assert r.status_code == 200, r.text

    meldungen = _meldungen(welt)
    assert meldungen, "Keine Absage an die eingeteilte Person"
    assert "abgesagt" in meldungen[0].subject.lower(), meldungen[0].subject


def test_serien_loeschung_schickt_absage(client, welt, als_moderator):
    """(6) Serie: dieselbe Absage fuer alle betroffenen Termine."""
    _termin(welt, "EL-3")
    _termin(welt, "EL-4")
    # Beide Termine gehoeren zu einer Serie (series_id ist das Bindeglied).
    for name in ("EL-3", "EL-4"):
        doc = welt.get(Element, name)
        doc.series_id = "SERIE-1"
    welt.commit()

    r = client.post("/api/method/diakronos.kronos.api.series.delete_series_batch_fast",
                    json={"series_id": "SERIE-1"})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["deleted_count"] == 2

    meldungen = _meldungen(welt)
    assert meldungen, "Keine Absage bei der Serien-Loeschung"
    assert any("abgesagt" in m.subject.lower() for m in meldungen), [
        m.subject for m in meldungen
    ]


def test_save_event_ressourcenwechsel_meldet(client, welt, als_moderator):
    """Derselbe Nachweis ueber `save_event` — den Schreibweg der Oberflaeche.

    Die Oberflaeche schickt den vollen Feldsatz; ohne den alt/neu-Vergleich je
    Feld meldete jede Speicherung alle Felder. Hier muss genau die
    Ressourcen-Aenderung ankommen.
    """
    _termin(welt, "EL-5")

    r = client.post(f"/api/method/{EVENT_MODUL}.save_event", json={
        "name": "EL-5",
        "element_name": "Chorprobe",
        "element_start": "2026-12-01 19:00:00",
        "element_end": "2026-12-01 21:00:00",
        "element_calendar": KALENDER,
        "all_day": 0,
        "status": "Festgelegt",
        "description": "",
        "zusaetzliche_ressourcen": [
            {"freitext_ressource": "Jugendraum", "status": "Bestätigt"},
        ],
    })
    assert r.status_code == 200, r.text

    meldungen = _meldungen(welt)
    assert meldungen, "Eingeteilte Person wurde nicht benachrichtigt"
    assert "Weitere Orte/Ressourcen" in meldungen[0].email_content, meldungen[0].email_content


def test_ressource_entfernen_meldet(client, welt, als_moderator):
    """„Ort gestrichen“ ist ebenfalls eine wirksame Aenderung."""
    _termin(welt, "EL-6")

    r = client.post(f"/api/method/{EVENT_MODUL}.update_event", json={
        "name": "EL-6",
        "zusaetzliche_ressourcen": [],
    })
    assert r.status_code == 200, r.text

    meldungen = _meldungen(welt)
    assert meldungen, "Das Entfernen des Ortes wurde nicht gemeldet"
    assert "Weitere Orte/Ressourcen" in meldungen[0].email_content, meldungen[0].email_content
