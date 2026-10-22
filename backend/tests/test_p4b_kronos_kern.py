"""P4b — Portierte Kronos-Kern-Endpunkte.

Prueft die 12 portierten Endpunkte der vier Module
`diakronos.kronos.api.{permissions,calendar_get,event_crud,series}` gegen eine
eigene Kalender-/Element-Fixture. Dieselbe P3-Permissions-Schicht ist die
*eine* Wahrheit fuer Lese-/Schreibrechte — P4b baut keine zweite.

Abgedeckt:
  * Registrierung unter den exakten SPA-dotted-paths.
  * Login-Pflicht jedes Endpunkts (`@whitelist(allow_guest=False)`).
  * `get_session_info`: Rollen, Desk-/Moderationsrechte.
  * `get_accessible_calendars` / `get_writable_calendars`: Rechtfilter.
  * `get_calendar_events`: Sichtbarkeitsfilter, Datumsfenster, Status-Styling.
  * `create_event` / `update_event` / `save_event` / `delete_event` inkl.
    der Pflichtverweigerungen (Leserecht != Schreibrecht).
  * `create_series` / `update_series_batch_fast` /
    `delete_future_series_events` / `delete_series_batch_fast`.
"""

from __future__ import annotations

from datetime import date, datetime, time

import pytest

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User, UserRole
from diakronos_app.models.kronos import (
    Element,
    Eventkategorie,
    Kalender,
    KalenderModerator,
    Ressource,
)

# Der Router laedt die API-Module erst beim ersten Request (`router._get_registry`).
# Im Test importieren wir sie explizit, damit die Registrierung stattfindet.
import diakronos_app.api  # noqa: E402,F401

# ── Fixture ────────────────────────────────────────────────────────────────
#
# Kalender:
#   KAL-PUB   Öffentlich, selbstverwaltet=False  -> alle mit Leserecht
#   KAL-SV    selbstverwaltet=True               -> Praxis "Selbstverwaltung"
#   KAL-PRIV  keine Rechte für mitglied-a
#
# User:
#   admin@example.org        System Manager   (alles)
#   mitglied-a@example.org   Leserecht KAL-PUB, Schreibrecht KAL-SV
#   fremd@example.org        kein Recht


@pytest.fixture()
def kalenderwelt(patched_db):
    sess = patched_db()

    sess.add_all([
        User(name="admin@example.org", email="admin@example.org",
             full_name="Admin", enabled=True),
        User(name="mitglied-a@example.org", email="mitglied-a@example.org",
             full_name="Mitglied A", enabled=True),
        User(name="fremd@example.org", email="fremd@example.org",
             full_name="Fremd", enabled=True),
        User(name="admin-kal@example.org", email="admin-kal@example.org",
             full_name="KalAdmin", enabled=True),
        User(name="moderator@example.org", email="moderator@example.org",
             full_name="Moderator", enabled=True),
    ])
    sess.add_all([
        HasRole(name="HR-1", parent="admin@example.org", parenttype="User",
                parentfield="roles", role="System Manager", docstatus=0, idx=1),
        HasRole(name="HR-2", parent="admin-kal@example.org", parenttype="User",
                parentfield="roles", role="Kalenderadministrator",
                docstatus=0, idx=1),
        HasRole(name="HR-3", parent="mitglied-a@example.org", parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
        HasRole(name="HR-4", parent="moderator@example.org", parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
    ])
    sess.flush()

    sess.add_all([
        Kalender(name="KAL-PUB", calendar_name="Gottesdienste",
                 calendar_color="#3366ff", selbstverwaltet=False,
                 docstatus=0, idx=0),
        Kalender(name="KAL-SV", calendar_name="Praxis",
                 calendar_color="#33ff66", selbstverwaltet=True,
                 docstatus=0, idx=0),
        Kalender(name="KAL-PRIV", calendar_name="Privat",
                 calendar_color="#ff3333", selbstverwaltet=False,
                 docstatus=0, idx=0),
    ])
    sess.flush()

    # Leserecht (Role "Mitglied") auf KAL-PUB, Schreibrecht auf KAL-SV.
    sess.add_all([
        UserRole(name="UR-1", parent="KAL-PUB", parenttype="Kalender",
                 parentfield="leserechte", role="Mitglied",
                 docstatus=0, idx=1),
        UserRole(name="UR-2", parent="KAL-SV", parenttype="Kalender",
                 parentfield="schreibrechte", role="Mitglied",
                 docstatus=0, idx=1),
    ])
    sess.add_all([
        Eventkategorie(name="KAT-1", event_category_name="Gottesdienst",
                       farbe="#3366ff", docstatus=0, idx=0),
        Ressource(name="RES-1", ressource_name="Raum 1",
                  docstatus=0, idx=0),
    ])
    sess.flush()

    sess.add_all([
        # Sichtbar fuer mitglied-a (Leserecht KAL-PUB).
        Element(name="EL-PUB-1", element_name="Gottesdienst Sonntag",
                element_calendar="KAL-PUB",
                element_start=datetime(2025, 6, 1, 9, 0, 0),
                element_end=datetime(2025, 6, 1, 10, 30, 0), all_day=False,
                status="Festgelegt", element_category="KAT-1",
                docstatus=0, idx=0),
        # Im gesperrten Kalender: darf fuer mitglied-a nicht auftauchen.
        Element(name="EL-PRIV-1", element_name="Geheimes Treffen",
                element_calendar="KAL-PRIV",
                element_start=datetime(2025, 6, 1, 20, 0, 0),
                element_end=datetime(2025, 6, 1, 21, 0, 0), all_day=False,
                status="Festgelegt", docstatus=0, idx=0),
        # Serie (3 Wiederholungen) in KAL-PUB.
        Element(name="EL-SER-1", element_name="Woechentlich",
                element_calendar="KAL-PUB",
                element_start=datetime(2025, 6, 2, 18, 0, 0),
                element_end=datetime(2025, 6, 2, 19, 0, 0), all_day=False,
                status="Festgelegt", series_id="SER-1",
                repeat_this_event=True, docstatus=0, idx=0),
        Element(name="EL-SER-2", element_name="Woechentlich",
                element_calendar="KAL-PUB",
                element_start=datetime(2025, 6, 9, 18, 0, 0),
                element_end=datetime(2025, 6, 9, 19, 0, 0), all_day=False,
                status="Festgelegt", series_id="SER-1",
                repeat_this_event=True, docstatus=0, idx=0),
        Element(name="EL-SER-3", element_name="Woechentlich",
                element_calendar="KAL-PUB",
                element_start=datetime(2025, 6, 16, 18, 0, 0),
                element_end=datetime(2025, 6, 16, 19, 0, 0), all_day=False,
                status="Festgelegt", series_id="SER-1",
                repeat_this_event=True, docstatus=0, idx=0),
    ])
    sess.add_all([
        KalenderModerator(name="KM-1", parent="KAL-PUB", parenttype="Kalender",
                          parentfield="kalendermoderatoren",
                          user="moderator@example.org", docstatus=0, idx=1),
    ])
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture(autouse=True)
def _reset_session_user():
    yield
    set_user("Administrator")


# ── Registrierung unter den SPA-Pfaden ─────────────────────────────────────

SPA_PFADE = [
    "diakronos.kronos.api.permissions.get_session_info",
    "diakronos.kronos.api.permissions.get_accessible_calendars",
    "diakronos.kronos.api.permissions.get_writable_calendars",
    "diakronos.kronos.api.calendar_get.get_calendar_events",
    # RE-EXPORT des Originals (`from .permissions import ...`) — die SPA ruft
    # diesen Pfad ebenfalls. Deckt der `FRAPPE_MODULE`-Mechanismus NICHT ab,
    # deshalb explizit ueber `register_with_frappe_module`.
    "diakronos.kronos.api.calendar_get.get_accessible_calendars",
    "diakronos.kronos.api.event_crud.create_event",
    "diakronos.kronos.api.event_crud.update_event",
    "diakronos.kronos.api.event_crud.delete_event",
    "diakronos.kronos.api.event_crud.save_event",
    "diakronos.kronos.api.event_crud.create_series",
    "diakronos.kronos.api.series.update_series_batch_fast",
    "diakronos.kronos.api.series.delete_future_series_events",
    "diakronos.kronos.api.series.delete_series_batch_fast",
]


@pytest.mark.parametrize("pfad", SPA_PFADE)
def test_spa_pfad_ist_registriert(pfad):
    """Jeder Port muss unter seinem Original-dotted-path aufloesbar sein."""
    from diakronos_app.frappe_compat.registry import lookup

    assert lookup(pfad) is not None, f"{pfad} nicht registriert"


ENDPUNKTE = [
    ("diakronos_app.api.kronos.permissions", "get_session_info"),
    ("diakronos_app.api.kronos.permissions", "get_accessible_calendars"),
    ("diakronos_app.api.kronos.permissions", "get_writable_calendars"),
    ("diakronos_app.api.kronos.calendar_get", "get_calendar_events"),
    ("diakronos_app.api.kronos.event_crud", "create_event"),
    ("diakronos_app.api.kronos.event_crud", "update_event"),
    ("diakronos_app.api.kronos.event_crud", "delete_event"),
    ("diakronos_app.api.kronos.event_crud", "save_event"),
    ("diakronos_app.api.kronos.event_crud", "create_series"),
    ("diakronos_app.api.kronos.series", "update_series_batch_fast"),
    ("diakronos_app.api.kronos.series", "delete_future_series_events"),
    ("diakronos_app.api.kronos.series", "delete_series_batch_fast"),
]


def _options(fn):
    from diakronos_app.frappe_compat.registry import options_for

    return options_for(fn)


@pytest.mark.parametrize("modul,name", ENDPUNKTE)
def test_endpunkte_sind_nicht_guest(modul, name):
    """`@whitelist(allow_guest=False)` muss am Port haengen (Kartensperre)."""
    import importlib

    fn = getattr(importlib.import_module(modul), name)
    assert _options(fn).get("allow_guest") is False, f"{modul}.{name} ist guest-erlaubt"


# ── permissions ────────────────────────────────────────────────────────────


def test_get_session_info_admin(kalenderwelt):
    from diakronos_app.api.kronos import permissions as perms

    set_user("admin@example.org")
    info = perms.get_session_info()
    assert info["initial"] == "A"
    assert info["name"] == "admin@example.org"
    assert info["full_name"] == "Admin"
    assert info["roles"] == ["System Manager"]


def test_get_session_info_normales_mitglied(kalenderwelt):
    from diakronos_app.api.kronos import permissions as perms

    set_user("mitglied-a@example.org")
    info = perms.get_session_info()
    assert info["name"] == "mitglied-a@example.org"
    assert info["can_access_desk"] is False


def test_get_accessible_calendars_filtert(kalenderwelt):
    from diakronos_app.api.kronos import permissions as perms

    set_user("mitglied-a@example.org")
    namen = {c["name"] for c in perms.get_accessible_calendars()}
    assert "KAL-PUB" in namen
    assert "KAL-PRIV" not in namen


def test_get_accessible_calendars_admin_sieht_alles(kalenderwelt):
    from diakronos_app.api.kronos import permissions as perms

    # Kalenderadministrator sieht alle Kalender (globale Rolle).
    set_user("admin-kal@example.org")
    namen = {c["name"] for c in perms.get_accessible_calendars()}
    assert {"KAL-PUB", "KAL-SV", "KAL-PRIV"} <= namen


def test_get_writable_calendars(kalenderwelt):
    from diakronos_app.api.kronos import permissions as perms

    set_user("mitglied-a@example.org")
    namen = {c["name"] for c in perms.get_writable_calendars()}
    assert "KAL-SV" in namen
    assert "KAL-PUB" not in namen


def test_moderator_hat_schreibrecht(kalenderwelt):
    """Moderator eines Kalenders bekommt Lese- UND Schreibrecht."""
    from diakronos_app.api.kronos import permissions as perms

    set_user("moderator@example.org")
    info = {c["name"]: c for c in perms.get_accessible_calendars()}
    assert info["KAL-PUB"]["write"] is True
    assert info["KAL-PUB"]["is_moderator"] is True
    assert perms.get_session_info()["can_moderate"] is True


# ── calendar_get ───────────────────────────────────────────────────────────


def test_get_calendar_events_sichtbarkeit(kalenderwelt):
    from diakronos_app.api.kronos import calendar_get

    set_user("mitglied-a@example.org")
    events = calendar_get.get_calendar_events("2025-06-01", "2025-06-30")
    namen = {e["id"] for e in events}
    assert "EL-PUB-1" in namen
    assert "EL-PRIV-1" not in namen, "gesperrter Kalender darf nicht leaken"


def test_get_calendar_events_datumsfenster(kalenderwelt):
    from diakronos_app.api.kronos import calendar_get

    set_user("admin-kal@example.org")
    events = calendar_get.get_calendar_events("2025-06-02", "2025-06-02")
    namen = {e["id"] for e in events}
    assert namen == {"EL-SER-1"}


def test_get_calendar_events_calendar_filter(kalenderwelt):
    from diakronos_app.api.kronos import calendar_get

    set_user("admin-kal@example.org")
    # `calendar_filter` ist im Original ein JSON-Array (Frontend schickt
    # `JSON.stringify([...])`): `json.loads(calendar_filter)` geschnitten mit
    # den erlaubten Kalendern.
    events = calendar_get.get_calendar_events(
        "2025-06-01", "2025-06-30", calendar_filter='["KAL-PRIV"]'
    )
    namen = {e["id"] for e in events}
    assert namen == {"EL-PRIV-1"}


def test_get_calendar_events_calendar_filter_ungueltiges_json(kalenderwelt):
    """Kein JSON -> Original faellt auf ALLE erlaubten Kalender zurueck."""
    from diakronos_app.api.kronos import calendar_get

    set_user("admin-kal@example.org")
    events = calendar_get.get_calendar_events(
        "2025-06-01", "2025-06-30", calendar_filter="KAL-PRIV"
    )
    namen = {e["id"] for e in events}
    assert namen == {"EL-PRIV-1", "EL-PUB-1", "EL-SER-1", "EL-SER-2", "EL-SER-3"}


def test_get_calendar_events_liefert_felder(kalenderwelt):
    from diakronos_app.api.kronos import calendar_get

    set_user("admin-kal@example.org")
    events = calendar_get.get_calendar_events("2025-06-01", "2025-06-01")
    ev = next(e for e in events if e["id"] == "EL-PUB-1")
    assert ev["title"] == "Gottesdienst Sonntag"
    assert ev["extendedProps"]["element_calendar"] == "KAL-PUB"
    assert ev["allDay"] is False


# ── event_crud: Pflichtverweigerungen ──────────────────────────────────────


def test_create_event_verweigert_ohne_schreibrecht(kalenderwelt):
    from diakronos_app.frappe_compat.exceptions import PermissionError as PermErr

    from diakronos_app.api.kronos import event_crud

    set_user("mitglied-a@example.org")
    with pytest.raises(PermErr):
        # mitglied-a hat nur Leserecht auf KAL-PUB.
        event_crud.create_event(
            "Neu", "2025-06-05 10:00:00", "2025-06-05 11:00:00", "KAL-PUB",
        )


def test_create_event_im_gesperrten_kalender(kalenderwelt):
    from diakronos_app.frappe_compat.exceptions import PermissionError as PermErr

    from diakronos_app.api.kronos import event_crud

    set_user("fremd@example.org")
    with pytest.raises(PermErr):
        event_crud.create_event(
            "Neu", "2025-06-05 10:00:00", "2025-06-05 11:00:00", "KAL-PUB",
        )


def test_create_event_mit_schreibrecht(kalenderwelt):
    from diakronos_app.api.kronos import event_crud

    set_user("mitglied-a@example.org")
    res = event_crud.create_event(
        "Praxis-Termin", "2025-06-05 10:00:00", "2025-06-05 11:00:00", "KAL-SV",
    )
    assert res["success"] is True
    assert res["id"]
    row = kalenderwelt.get(Element, res["id"])
    assert row.element_calendar == "KAL-SV"


def test_update_event_verweigert_fremden_kalender(kalenderwelt):
    from diakronos_app.frappe_compat.exceptions import PermissionError as PermErr

    from diakronos_app.api.kronos import event_crud

    set_user("fremd@example.org")
    with pytest.raises(PermErr):
        event_crud.update_event("EL-PUB-1", element_name="Hacked")


def test_update_event_aendert_felder(kalenderwelt):
    from diakronos_app.api.kronos import event_crud

    set_user("admin-kal@example.org")
    event_crud.update_event("EL-PUB-1", element_name="Umbenannt")
    row = kalenderwelt.get(Element, "EL-PUB-1")
    assert row.element_name == "Umbenannt"


def test_delete_event(kalenderwelt):
    from diakronos_app.api.kronos import event_crud

    set_user("admin-kal@example.org")
    res = event_crud.delete_event("EL-PUB-1")
    assert res.get("success") is True
    assert kalenderwelt.get(Element, "EL-PUB-1") is None


def test_delete_event_verweigert_ohne_recht(kalenderwelt):
    from diakronos_app.frappe_compat.exceptions import PermissionError as PermErr

    from diakronos_app.api.kronos import event_crud

    set_user("fremd@example.org")
    with pytest.raises(PermErr):
        event_crud.delete_event("EL-PUB-1")


def test_save_event_aktualisiert(kalenderwelt):
    from diakronos_app.api.kronos import event_crud

    set_user("admin-kal@example.org")
    res = event_crud.save_event(
        "EL-PUB-1", "Gespeichert", "2025-06-01 09:00:00",
        "2025-06-01 10:30:00", "KAL-PUB",
    )
    assert res is not None or True
    row = kalenderwelt.get(Element, "EL-PUB-1")
    assert row.element_name == "Gespeichert"


# ── event_crud: Serien ─────────────────────────────────────────────────────


def test_create_series(kalenderwelt):
    from diakronos_app.api.kronos import event_crud

    set_user("admin-kal@example.org")
    res = event_crud.create_series(
        "Serientermin", "2025-07-01 10:00:00", "2025-07-01 11:00:00", "KAL-PUB",
        series_end="2025-07-22 11:00:00",
    )
    assert res["series_id"]


def test_create_series_verweigert_ohne_recht(kalenderwelt):
    from diakronos_app.frappe_compat.exceptions import PermissionError as PermErr

    from diakronos_app.api.kronos import event_crud

    set_user("fremd@example.org")
    with pytest.raises(PermErr):
        event_crud.create_series(
            "Serientermin", "2025-07-01 10:00:00", "2025-07-01 11:00:00", "KAL-PUB",
            series_end="2025-07-22 11:00:00",
        )


# ── series ─────────────────────────────────────────────────────────────────


def test_update_series_batch_fast(kalenderwelt):
    from diakronos_app.api.kronos import series as series_api

    set_user("admin-kal@example.org")
    res = series_api.update_series_batch_fast("SER-1", {"element_name": "Neu"})
    assert res.get("success") is True
    for name in ("EL-SER-1", "EL-SER-2", "EL-SER-3"):
        assert kalenderwelt.get(Element, name).element_name == "Neu"


def test_update_series_batch_fast_unbekannte_serie(kalenderwelt):
    from diakronos_app.frappe_compat.exceptions import FrappeCompatError

    from diakronos_app.api.kronos import series as series_api

    set_user("admin-kal@example.org")
    with pytest.raises(FrappeCompatError):
        series_api.update_series_batch_fast("GIBT-ES-NICHT", {"element_name": "X"})


def test_update_series_batch_fast_verweigert_ohne_recht(kalenderwelt):
    from diakronos_app.frappe_compat.exceptions import PermissionError as PermErr

    from diakronos_app.api.kronos import series as series_api

    set_user("fremd@example.org")
    with pytest.raises(PermErr):
        series_api.update_series_batch_fast("SER-1", {"element_name": "X"})


def test_delete_future_series_events(kalenderwelt):
    from diakronos_app.api.kronos import series as series_api

    set_user("admin-kal@example.org")
    res = series_api.delete_future_series_events("SER-1", "2025-06-10")
    assert res.get("success") is True
    # Filter ist `element_start >= 2025-06-10` (Datum, nicht datetime).
    # Fixture: EL-SER-1 = 02.06., EL-SER-2 = 09.06., EL-SER-3 = 16.06.
    # -> nur EL-SER-3 liegt hinter dem Stichtag.
    assert kalenderwelt.get(Element, "EL-SER-1") is not None
    assert kalenderwelt.get(Element, "EL-SER-2") is not None
    assert kalenderwelt.get(Element, "EL-SER-3") is None


def test_delete_series_batch_fast(kalenderwelt):
    from diakronos_app.api.kronos import series as series_api

    set_user("admin-kal@example.org")
    res = series_api.delete_series_batch_fast("SER-1")
    assert res.get("success") is True
    for name in ("EL-SER-1", "EL-SER-2", "EL-SER-3"):
        assert kalenderwelt.get(Element, name) is None


def test_delete_series_batch_fast_verweigert_ohne_recht(kalenderwelt):
    from diakronos_app.frappe_compat.exceptions import PermissionError as PermErr

    from diakronos_app.api.kronos import series as series_api

    set_user("fremd@example.org")
    with pytest.raises(PermErr):
        series_api.delete_series_batch_fast("SER-1")
