"""UX3d — Kalender-Reiter „Zu prüfen“ erscheint nur für Moderatoren.

Die Oberfläche blendet den vierten Kalender-Reiter anhand des Boot-Objekts
(`window.__DIakonosBOOT.can_moderate`) ein und aus. Damit das keine zweite
Wahrheit neben dem Endpunkt wird, liefert `spa.boot_fuer_request()` exakt das,
was `get_session_info()` als `can_moderate` meldet — beide lesen
`get_accessible_calendars()` und dessen Feld `is_moderator`.

Geprüft wird hier der SERVER (das Frontend in
`frontend/tests/ux3d-kalender-pruefen.test.mjs`):

* Moderator eines Kalenders OHNE Admin-Rolle -> Reiter ja.
* Mitglied ohne Moderationsrecht -> Reiter nein (fail closed).
* Kalenderadministrator -> ja (er ist Moderator jedes Kalenders; dieselbe
  Aussage wie `get_session_info`).
* Gast / fehlende Sitzung / Lesefehler -> nein (das Boot-Objekt darf nie
  scheitern und nie ein Recht erfinden).

Datenbank: ausschliesslich ``patched_db`` (SQLite) — nie der Betrieb.
"""
from __future__ import annotations

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
import diakronos_app.spa as spa
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User, UserRole
from diakronos_app.models.kronos import Kalender, KalenderModerator


@pytest.fixture()
def welt(patched_db):
    """Ein Kalender mit Leserecht für „Mitglied“, Moderator ohne Admin-Rolle."""
    sess = patched_db()
    sess.add_all([
        User(name="admin-kal@example.org", email="admin-kal@example.org",
             full_name="KalAdmin", enabled=True),
        User(name="mitglied-a@example.org", email="mitglied-a@example.org",
             full_name="Mitglied A", enabled=True),
        User(name="moderator@example.org", email="moderator@example.org",
             full_name="Moderator", enabled=True),
    ])
    sess.add_all([
        HasRole(name="HR-1", parent="admin-kal@example.org", parenttype="User",
                parentfield="roles", role="Kalenderadministrator",
                docstatus=0, idx=1),
        HasRole(name="HR-2", parent="mitglied-a@example.org", parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
        HasRole(name="HR-3", parent="moderator@example.org", parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
    ])
    sess.flush()
    sess.add(Kalender(name="KAL-PUB", calendar_name="Gottesdienste",
                      calendar_color="#3366ff", selbstverwaltet=False,
                      docstatus=0, idx=0))
    sess.flush()
    sess.add(UserRole(name="UR-1", parent="KAL-PUB", parenttype="Kalender",
                      parentfield="leserechte", role="Mitglied",
                      docstatus=0, idx=1))
    sess.add(KalenderModerator(name="KM-1", parent="KAL-PUB",
                               parenttype="Kalender",
                               parentfield="kalendermoderatoren",
                               user="moderator@example.org", docstatus=0, idx=1))
    sess.commit()
    sess.close()
    return patched_db


def test_moderator_ohne_adminrolle_bekommt_den_reiter(welt):
    set_user("moderator@example.org")
    assert spa.boot_fuer_request()["can_moderate"] is True


def test_mitglied_ohne_moderationsrecht_bekommt_ihn_nicht(welt):
    set_user("mitglied-a@example.org")
    assert spa.boot_fuer_request()["can_moderate"] is False


def test_kalenderadministrator_ist_moderator(welt):
    set_user("admin-kal@example.org")
    assert spa.boot_fuer_request()["can_moderate"] is True


def test_gast_und_fehlende_sitzung_ergeben_false(welt):
    set_user("Guest")
    assert spa.boot_fuer_request()["can_moderate"] is False


def test_lesefehler_ergibt_false(monkeypatch):
    """Ein kaputter Rechte-Leser darf das Boot-Objekt nicht scheitern lassen —
    und darf auch kein Recht erfinden (Sonst zeigte die Oberfläche einen Reiter,
    den der Server anschließend mit „Zugriff verweigert“ beantwortet)."""
    from diakronos_app.api.kronos import permissions as perms

    def kaputt(*_a, **_k):
        raise RuntimeError("DB weg")

    monkeypatch.setattr(perms, "get_accessible_calendars", kaputt)
    assert spa._darf_pruefen("mitglied-a@example.org") is False


def test_boot_und_endpunkt_stimmen_ueberein(welt):
    """EINE Wahrheit: der Schlüssel im Boot-Objekt ist genau `can_moderate`."""
    for nutzer, erwartet in [
        ("moderator@example.org", True),
        ("mitglied-a@example.org", False),
        ("admin-kal@example.org", True),
    ]:
        set_user(nutzer)
        from diakronos_app.api.kronos import permissions as perms

        assert spa.boot_fuer_request()["can_moderate"] is erwartet, nutzer
        assert bool(perms.get_session_info()["can_moderate"]) is erwartet, nutzer
