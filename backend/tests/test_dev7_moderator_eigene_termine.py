"""DEV-7 — Ein Kalendermoderator gibt SEINE EIGENEN Terminvorschlaege frei.

Befund DMB-eb5c6c69ea54 (Manuel): „Ein Kalendermoderator, der selber Termine
freigeben kann, soll auch seine eigenen bestaetigen koennen! (was wenn es nur
einen Verwalter gibt)“.

BEFUND (in diesem Test festgehalten): Das Backend sperrt die Selbstfreigabe
NICHT. `resolve_conflict`, `finalize_staged_events` und
`aenderung_freigeben` pruefen ausschliesslich das Moderationsrecht am
KALENDER (`_require_moderator` / `pruefe_moderationsrecht`) — es gibt
nirgends einen Vergleich `owner == aufrufender Nutzer`. Der eigene Termin
landete nur deshalb unter „Vorschlaege“, weil `create_event` JEDEN neuen
Termin als „Vorschlag“ anlegt (`_erzwungener_status`) und die
Moderationsoberflaeche fuer einen einfachen Vorschlag nur „Speichern“ und
„Ablehnen…“ anbietet — kein „Freigeben“. Der Moderator musste den Umweg
„Vorschlag nach rechts in Freigeben ziehen“ oder „Alle freigeben“ gehen.

Diese Tests sichern BEIDE Seiten ab:

  * Backend: ein Moderator gibt seinen eigenen Vorschlag frei — der Termin
    wird „Festgelegt“, der Audit-Eintrag (moderiert_von/status) entsteht.
  * Backend: die Freigabe eines EIGENEN Aenderungsvorschlags (Element
    Aenderung) funktioniert genauso.
  * Abgrenzung: ein Nicht-Moderator bleibt aussen vor (unveraendertes Recht).
  * Neu: `resolve_conflict(action="festlegen")` aus der Vorschlagsliste —
    vorher war das nur ueber das Staging moeglich.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

import diakronos_app.api  # noqa: E402,F401  (registriert die @whitelist-Pfade)

from diakronos_app.frappe_compat.api_helpers import get_value
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User, UserRole
from diakronos_app.models.kronos import (
    Element,
    ElementAenderung,
    Kalender,
    KalenderModerator,
)

KANBAN_MODUL = "diakronos.kronos.api.kanban_api"
EVENT_MODUL = "diakronos.kronos.api.event_crud"

MODERATOR = "moderator-dev7@example.org"
SCHREIBER = "schreiber-dev7@example.org"
KAL = "KAL-DEV7"


@pytest.fixture()
def welt(patched_db):
    """Ein Kalender: MODERATOR moderiert, SCHREIBER darf nur schreiben."""
    sess = patched_db()
    sess.add_all([
        User(name=MODERATOR, email=MODERATOR, full_name="Mara Moderator",
             enabled=True),
        User(name=SCHREIBER, email=SCHREIBER, full_name="Sven Schreiber",
             enabled=True),
    ])
    sess.add_all([
        HasRole(name="HR-DEV7-M", parent=MODERATOR, parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
        HasRole(name="HR-DEV7-S", parent=SCHREIBER, parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
    ])
    sess.add(
        Kalender(name=KAL, calendar_name="Gemeinde", calendar_color="#333333",
                 selbstverwaltet=0, docstatus=0, idx=0),
    )
    sess.flush()
    sess.add_all([
        UserRole(name="UR-DEV7-1", parent=KAL, parenttype="Kalender",
                 parentfield="schreibrechte", role="Mitglied", docstatus=0, idx=1),
        KalenderModerator(name="KM-DEV7-1", parent=KAL, parenttype="Kalender",
                          parentfield="kalendermoderatoren", user=MODERATOR,
                          docstatus=0, idx=1),
    ])
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture(autouse=True)
def _reset_user():
    yield
    set_user("Administrator")


def _als(user):
    set_user(user)


def _vorschlag(sess, name, owner, *, titel="Test"):
    tag = (datetime.now() + timedelta(days=5)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    el = Element(
        name=name, element_name=titel, element_calendar=KAL,
        element_start=tag.replace(hour=19), element_end=tag.replace(hour=20),
        all_day=0, status="Vorschlag", series_id="", docstatus=0, idx=0,
        owner=owner, description="",
    )
    sess.add(el)
    sess.commit()
    return el


# ═══════════════════════════════════════════════════════════════════════════
# 1 — Moderator gibt den EIGENEN Vorschlag frei (Befund)
# ═══════════════════════════════════════════════════════════════════════════

def test_moderator_gibt_eigenen_vorschlag_frei(client, welt):
    """Ein Moderator gibt seinen EIGENEN einfachen Vorschlag ueber
    `resolve_conflict(action='festlegen')` frei — der Weg, den der
    Vorschlagsdialog mit dem Knopf „Freigeben“ jetzt anbietet.

    Vorher (ROT): der Zweig `festlegen` setzte keinen Status, der Termin blieb
    „Vorschlag“.
    """
    _vorschlag(welt, "ELE-DEV7-EIGEN", MODERATOR)
    _als(MODERATOR)

    r = client.post(f"/api/method/{KANBAN_MODUL}.resolve_conflict",
                    data={"element_id": "ELE-DEV7-EIGEN", "action": "festlegen",
                          "title": "Test"})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["new_status"] == "Festgelegt"
    assert get_value("Element", "ELE-DEV7-EIGEN", "status") == "Festgelegt"
    # Audit: der Freigebende steht am Termin (auch bei Selbstfreigabe).
    assert get_value("Element", "ELE-DEV7-EIGEN", "moderiert_von") == MODERATOR


def test_moderator_gibt_fremden_vorschlag_frei(client, welt):
    """Derselbe Weg fuer einen FREMDEN Vorschlag (Antragsteller = SCHREIBER).

    Der Moderator entscheidet hier NICHT ueber seinen eigenen Termin — die
    Schranke ist allein das Moderationsrecht am Kalender.
    """
    _vorschlag(welt, "ELE-DEV7-FREMD-MOD", SCHREIBER)
    _als(MODERATOR)

    r = client.post(f"/api/method/{KANBAN_MODUL}.resolve_conflict",
                    data={"element_id": "ELE-DEV7-FREMD-MOD", "action": "festlegen",
                          "title": "Test"})
    assert r.status_code == 200, r.text
    assert get_value("Element", "ELE-DEV7-FREMD-MOD", "status") == "Festgelegt"
    assert get_value("Element", "ELE-DEV7-FREMD-MOD", "moderiert_von") == MODERATOR


def test_moderator_gibt_eigenen_vorschlag_ueber_staging_frei(client, welt):
    """Der bisherige Weg (Staging) war nie gesperrt — Beleg fuer den Befund,
    dass die SERVERSEITE die Selbstfreigabe erlaubt. Seit DEV-7 traegt auch
    dieser Weg den Freigebenden mit."""
    _vorschlag(welt, "ELE-DEV7-STAGE", MODERATOR)
    _als(MODERATOR)

    r = client.post(f"/api/method/{KANBAN_MODUL}.finalize_staged_events",
                    data={"event_ids": json.dumps(["ELE-DEV7-STAGE"])})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["finalized"] == 1
    assert get_value("Element", "ELE-DEV7-STAGE", "status") == "Festgelegt"
    assert get_value("Element", "ELE-DEV7-STAGE", "moderiert_von") == MODERATOR


def test_moderator_lehnt_eigenen_vorschlag_ab(client, welt):
    """Ablehnen des eigenen Vorschlags bleibt moeglich (Audit + Grund)."""
    _vorschlag(welt, "ELE-DEV7-EIGEN-AB", MODERATOR)
    _als(MODERATOR)

    r = client.post(f"/api/method/{KANBAN_MODUL}.resolve_conflict",
                    data={"element_id": "ELE-DEV7-EIGEN-AB", "action": "ablehnen",
                          "grund": "Doppelung mit Gemeindefest"})
    assert r.status_code == 200, r.text
    assert get_value("Element", "ELE-DEV7-EIGEN-AB", "status") == "Abgelehnt"
    assert get_value("Element", "ELE-DEV7-EIGEN-AB", "moderiert_von") == MODERATOR


def test_moderator_gibt_eigenen_aenderungsvorschlag_frei(client, welt):
    """Eigener Aenderungsvorschlag (Element Aenderung): Freigabe bleibt moeglich."""
    _vorschlag(welt, "ELE-DEV7-AEND", MODERATOR)
    # Termin festlegen und einen offenen Aenderungsvorschlag des Moderators selbst anlegen.
    set_user("Administrator")
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    _update_doc("Element", "ELE-DEV7-AEND", {"status": "Festgelegt"})
    welt.add(ElementAenderung(
        name="ELEMAEND-DEV7", element="ELE-DEV7-AEND", element_calendar=KAL,
        antragsteller=MODERATOR,
        vorschlag=json.dumps({"element_start": "2027-05-02 19:00:00"}),
        docstatus=0, idx=0,
    ))
    welt.commit()

    _als(MODERATOR)
    r = client.post(f"/api/method/{EVENT_MODUL}.aenderung_freigeben",
                    data={"name": "ELEMAEND-DEV7"})
    assert r.status_code == 200, r.text
    # Datumswerte kommen aus der Compat-Schicht als String zurueck.
    assert str(get_value("Element", "ELE-DEV7-AEND", "element_start"))[:19] == \
        "2027-05-02 19:00:00"


# ═══════════════════════════════════════════════════════════════════════════
# 2 — Rechte anderer Rollen bleiben unveraendert
# ═══════════════════════════════════════════════════════════════════════════

def test_nicht_moderator_gibt_eigenen_vorschlag_nicht_frei(client, welt):
    """Abgrenzung: Schreibrecht allein rechtfertigt KEINE Freigabe — auch nicht
    am eigenen Termin (OP-EVENT-1 bleibt gueltig)."""
    _vorschlag(welt, "ELE-DEV7-FREMD", SCHREIBER)
    _als(SCHREIBER)

    r = client.post(f"/api/method/{KANBAN_MODUL}.resolve_conflict",
                    data={"element_id": "ELE-DEV7-FREMD", "action": "festlegen",
                          "title": "Test"})
    assert r.status_code == 403, r.text
    assert get_value("Element", "ELE-DEV7-FREMD", "status") == "Vorschlag"


def test_nicht_moderator_bleibt_beim_anlegen_im_vorschlag(client, welt):
    """`create_event` zwingt weiterhin jeden Nicht-Moderator auf „Vorschlag“."""
    _als(SCHREIBER)
    r = client.post(f"/api/method/{EVENT_MODUL}.create_event",
                    data={"element_name": "Test 2", "element_calendar": KAL,
                          "element_start": "2027-06-01 19:00", "element_end": "2027-06-01 20:00",
                          "status": "Festgelegt"})
    assert r.status_code == 200, r.text
    antwort = r.json()["message"]
    name = antwort["id"]
    # Der Server meldet den tatsaechlich gesetzten Status mit (BF1-A).
    assert antwort["status"] == "Vorschlag"
    assert get_value("Element", name, "status") == "Vorschlag"


def test_nicht_moderator_gibt_auch_eigenen_vorschlag_nicht_ueber_staging_frei(client, welt):
    """Auch der Staging-Weg bleibt fuer Nicht-Moderatoren gesperrt — am EIGENEN
    Termin genauso wie an einem fremden (Rechte anderer Rollen unveraendert).
    """
    _vorschlag(welt, "ELE-DEV7-S-AB", SCHREIBER)
    _als(SCHREIBER)

    r = client.post(f"/api/method/{KANBAN_MODUL}.finalize_staged_events",
                    data={"event_ids": json.dumps(["ELE-DEV7-S-AB"])})
    assert r.status_code == 403, r.text
    assert get_value("Element", "ELE-DEV7-S-AB", "status") == "Vorschlag"
    assert not get_value("Element", "ELE-DEV7-S-AB", "moderiert_von")
