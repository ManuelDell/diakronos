"""DEV-7b — Nacharbeit Moderation-Freigabe (Karte t_ede5c173).

Zwei Punkte aus dem Opus-Review, hier als Backend-Tests festgehalten:

(2) KONFLIKT-FREIGABE GILT ALS BEWUSST UEBERGANGEN
    Der Konflikt-Dialog bietet „Freigeben“ an und schickt dafuer
    `action=festlegen` mit. Das ist gewollt (der Moderator entscheidet
    bewusst, Operator-Entscheidung) — dann darf der Konflikt aber nicht
    erneut als Konflikt auftauchen. Die Oberflaeche setzt deshalb
    zusaetzlich `ueberschneidung=1`; der Server schreibt dann
    `ignore_conflict=1` mit.

    ROT ohne die Aenderung: `festlegen` liess `ignore_conflict` unberuehrt,
    der Termin blieb mit `ignore_conflict=0` stehen und wurde bei der
    naechsten Konfliktberechnung wieder gemeldet.

    Abgrenzung: der Weg OHNE `ueberschneidung` (Vorschlagsdialog) setzt den
    Vermerk NICHT — sonst wuerde jede Freigabe Konflikte stillschweigend
    abhaken.

(3) MODERATOR EINES ANDEREN KALENDERS DARF NICHT FREIGEBEN (403)
    Das Moderationsrecht haengt am KALENDER des Termins
    (`_require_moderator`). Ein Moderator des fremden Kalenders ist damit
    kein Moderator dieses Termins — unabhaengig davon, ob er den Termin
    sehen oder eigene Termine anlegen darf.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

import diakronos_app.api  # noqa: E402,F401  (registriert die @whitelist-Pfade)

from diakronos_app.frappe_compat.api_helpers import get_value
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User, UserRole
from diakronos_app.models.kronos import (
    Element,
    Kalender,
    KalenderModerator,
    Ressource,
)

KANBAN_MODUL = "diakronos.kronos.api.kanban_api"

MODERATOR = "moderator-dev7b@example.org"
FREMD_MODERATOR = "fremdmod-dev7b@example.org"
SCHREIBER = "schreiber-dev7b@example.org"

KAL = "KAL-DEV7B"
KAL_FREMD = "KAL-DEV7B-FREMD"
RAUM = "RES-DEV7B"


@pytest.fixture()
def welt(patched_db):
    """Zwei Kalender: DEV7B (MODERATOR) und FREMD (FREMD_MODERATOR).

    SCHREIBER hat in FREMD Schreibrecht, aber kein Moderationsrecht — damit
    ist „Schreibrecht ist kein Moderationsrecht“ mitgeprueft.
    """
    sess = patched_db()
    sess.add_all([
        User(name=MODERATOR, email=MODERATOR, full_name="Mara Moderator", enabled=True),
        User(name=FREMD_MODERATOR, email=FREMD_MODERATOR, full_name="Fred Fremd",
             enabled=True),
        User(name=SCHREIBER, email=SCHREIBER, full_name="Sven Schreiber", enabled=True),
    ])
    for i, email in enumerate((MODERATOR, FREMD_MODERATOR, SCHREIBER), start=1):
        sess.add(HasRole(name=f"HR-DEV7B-{i}", parent=email, parenttype="User",
                         parentfield="roles", role="Mitglied", docstatus=0, idx=1))
    sess.add_all([
        Kalender(name=KAL, calendar_name="Gemeinde", calendar_color="#333333",
                 selbstverwaltet=0, docstatus=0, idx=0),
        Kalender(name=KAL_FREMD, calendar_name="Fremd", calendar_color="#444444",
                 selbstverwaltet=0, docstatus=0, idx=0),
        Ressource(name=RAUM, ressource_name="Gemeindesaal", typ="Raum",
                  kapazitaet=80, wartung=0, docstatus=0, idx=0),
    ])
    sess.flush()
    sess.add_all([
        KalenderModerator(name="KM-DEV7B-1", parent=KAL, parenttype="Kalender",
                          parentfield="kalendermoderatoren", user=MODERATOR,
                          docstatus=0, idx=1),
        KalenderModerator(name="KM-DEV7B-2", parent=KAL_FREMD, parenttype="Kalender",
                          parentfield="kalendermoderatoren", user=FREMD_MODERATOR,
                          docstatus=0, idx=1),
        # Schreibrecht (kein Moderationsrecht) im FREMden Kalender.
        UserRole(name="UR-DEV7B-1", parent=KAL_FREMD, parenttype="Kalender",
                 parentfield="schreibrechte", role="Mitglied", docstatus=0, idx=1),
    ])
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture(autouse=True)
def _reset_user():
    yield
    set_user("Administrator")


def _termin(sess, name, *, kalender=KAL, status="Konflikt", owner=None,
            stunde=10, ressource=RAUM):
    tag = (datetime.now() + timedelta(days=9)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    el = Element(
        name=name, element_name=name, element_calendar=kalender,
        element_start=tag.replace(hour=stunde), element_end=tag.replace(hour=stunde + 2),
        all_day=0, status=status, series_id="", docstatus=0, idx=0,
        owner=owner or SCHREIBER, description="", ressource=ressource,
        ignore_conflict=0,
    )
    sess.add(el)
    sess.commit()
    return el


def _konflikt_freigeben(client, name, **extra):
    daten = {"element_id": name, "action": "festlegen", "title": name}
    daten.update(extra)
    return client.post(f"/api/method/{KANBAN_MODUL}.resolve_conflict", data=daten)


# ═══════════════════════════════════════════════════════════════════════════
# (2) Freigabe MIT Ueberschneidung -> ignore_conflict=1
# ═══════════════════════════════════════════════════════════════════════════

def test_konflikt_freigabe_setzt_ignore_conflict(client, welt):
    """„Freigeben“ im Konflikt-Dialog: Status Festgelegt UND bewusst
    uebergangen (`ignore_conflict=1`)."""
    _termin(welt, "ELE-DEV7B-K1")
    set_user(MODERATOR)

    r = _konflikt_freigeben(client, "ELE-DEV7B-K1", ueberschneidung=1)
    assert r.status_code == 200, r.text
    assert r.json()["message"]["new_status"] == "Festgelegt"
    assert get_value("Element", "ELE-DEV7B-K1", "status") == "Festgelegt"
    assert int(get_value("Element", "ELE-DEV7B-K1", "ignore_conflict")) == 1
    assert get_value("Element", "ELE-DEV7B-K1", "moderiert_von") == MODERATOR


def test_konflikt_freigabe_taucht_nicht_erneut_als_konflikt_auf(client, welt):
    """Nach der Freigabe ist der Termin weder Vorschlag noch Konflikt auf dem
    Board — er ist entschieden (Status Festgelegt)."""
    _termin(welt, "ELE-DEV7B-K2")
    set_user(MODERATOR)
    _konflikt_freigeben(client, "ELE-DEV7B-K2", ueberschneidung=1)

    r = client.post(f"/api/method/{KANBAN_MODUL}.get_kanban_board_data", data={})
    assert r.status_code == 200, r.text
    board = r.json()["message"]
    ids = {e["id"] for spalte in ("vorschlaege", "konflikte")
           for e in board.get(spalte, [])}
    assert "ELE-DEV7B-K2" not in ids


def test_freigabe_ohne_ueberschneidung_laesst_vermerk_unberuehrt(client, welt):
    """Vorschlagsdialog (kein Konflikt): `ignore_conflict` bleibt 0.

    Sonst wuerde jede Freigabe Konflikte stillschweigend abhaken.
    """
    _termin(welt, "ELE-DEV7B-V1", status="Vorschlag")
    set_user(MODERATOR)

    r = _konflikt_freigeben(client, "ELE-DEV7B-V1")
    assert r.status_code == 200, r.text
    assert get_value("Element", "ELE-DEV7B-V1", "status") == "Festgelegt"
    assert int(get_value("Element", "ELE-DEV7B-V1", "ignore_conflict")) == 0


@pytest.mark.parametrize("wert", ["0", "false", 0, False, ""])
def test_ueberschneidung_null_wirkt_nicht(client, welt, wert):
    """`ueberschneidung` ist ein Schalter, kein Wahrheitswert per „nicht leer“:
    `"0"` ist ein nicht-leerer Text und darf NICHT als ja gelten."""
    _termin(welt, f"ELE-DEV7B-N-{wert!s}", status="Vorschlag")
    set_user(MODERATOR)

    r = _konflikt_freigeben(client, f"ELE-DEV7B-N-{wert!s}", ueberschneidung=wert)
    assert r.status_code == 200, r.text
    assert int(get_value("Element", f"ELE-DEV7B-N-{wert!s}", "ignore_conflict")) == 0


# ═══════════════════════════════════════════════════════════════════════════
# (3) Moderator eines ANDEREN Kalenders kann nicht freigeben (403)
# ═══════════════════════════════════════════════════════════════════════════

def test_moderator_anderen_kalenders_darf_nicht_freigeben(client, welt):
    """FREMD_MODERATOR moderiert KAL_FREMD, nicht KAL -> 403, nichts geaendert."""
    _termin(welt, "ELE-DEV7B-FREMD-1", kalender=KAL)
    set_user(FREMD_MODERATOR)

    r = _konflikt_freigeben(client, "ELE-DEV7B-FREMD-1", ueberschneidung=1)
    assert r.status_code == 403, r.text
    assert get_value("Element", "ELE-DEV7B-FREMD-1", "status") == "Konflikt"
    assert int(get_value("Element", "ELE-DEV7B-FREMD-1", "ignore_conflict")) == 0
    assert not get_value("Element", "ELE-DEV7B-FREMD-1", "moderiert_von")


def test_moderator_anderen_kalenders_darf_auch_nicht_ablehnen(client, welt):
    """Dieselbe Schranke fuer den anderen Weg (Ablehnen) — ein fremder
    Moderator darf hier gar nichts entscheiden."""
    _termin(welt, "ELE-DEV7B-FREMD-2", kalender=KAL, status="Vorschlag")
    set_user(FREMD_MODERATOR)

    r = client.post(f"/api/method/{KANBAN_MODUL}.resolve_conflict",
                    data={"element_id": "ELE-DEV7B-FREMD-2", "action": "ablehnen",
                          "grund": "Nicht mein Kalender"})
    assert r.status_code == 403, r.text
    assert get_value("Element", "ELE-DEV7B-FREMD-2", "status") == "Vorschlag"


def test_schreibrecht_ist_kein_moderationsrecht(client, welt):
    """SCHREIBER hat in KAL_FREMD Schreibrecht — das ist kein
    Moderationsrecht (OP-EVENT-1 bleibt gueltig)."""
    _termin(welt, "ELE-DEV7B-FREMD-3", kalender=KAL_FREMD, status="Vorschlag")
    set_user(SCHREIBER)

    r = _konflikt_freigeben(client, "ELE-DEV7B-FREMD-3")
    assert r.status_code == 403, r.text
    assert get_value("Element", "ELE-DEV7B-FREMD-3", "status") == "Vorschlag"


def test_moderator_seines_kalenders_bleibt_erlaubt(client, welt):
    """Gegenprobe: der zustaendige Moderator darf weiterhin freigeben."""
    _termin(welt, "ELE-DEV7B-OK-1")
    set_user(MODERATOR)

    r = _konflikt_freigeben(client, "ELE-DEV7B-OK-1", ueberschneidung=1)
    assert r.status_code == 200, r.text
    assert get_value("Element", "ELE-DEV7B-OK-1", "status") == "Festgelegt"
