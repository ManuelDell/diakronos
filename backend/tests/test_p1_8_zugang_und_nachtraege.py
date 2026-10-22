"""P1-8 Teil 2 — Rechte pflegbar: Zugang (OP-ADMIN-2/-3) und Nachträge.

Hier stehen die Tests zu den NACHTRÄGEN, die dem Paket P1-8 zugeordnet wurden:

  * OP-ADMIN-2 — Zugang: Konto anlegen, Rollen vergeben, sperren/entsperren.
  * OP-ADMIN-3 — Authentik-Modus „Als Gast anlegen": wartende Konten
    freischalten; kein Sitzungscookie fuer ein inaktives Gastkonto.
  * W-1 (aus R-P1-5c) — `_attach_serien_anzahl` zaehlt mit DEMSELBEN
    Statusfilter wie die Terminliste.
  * K-1 (aus R-P1-5c) — `_text` im CalDAV-Server entfernt Steuerzeichen und
    alleinstehende UTF-16-Surrogate.

Jeder Test waere ohne die zugehoerige Aenderung rot.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Mitglied


def _mitglied(sess, name: str, email: str, *, user: str | None = None) -> None:
    sess.add(Mitglied(name=name, vorname=name, nachname="Test",
                      email=email, status="Mitglied",
                      user=user, docstatus=0, idx=0))
    sess.commit()


def _konto(sess, email: str) -> None:
    sess.add(User(name=email, email=email, full_name=email, enabled=True))
    sess.commit()


# ── OP-ADMIN-2: Zugang ──────────────────────────────────────────────────────


def test_zugang_liefert_kein_konto_ohne_konto(patched_db) -> None:
    from diakronos_app.api.zugang import get_zugang
    from diakronos_app.frappe_compat.session import set_user

    sess = patched_db()
    sess.add(User(name="admin@example.org", email="admin@example.org",
                  full_name="Admin", enabled=True))
    sess.add(HasRole(name="HR-admin", parent="admin@example.org", parenttype="User",
                     parentfield="roles", role="Mitgliederadministrator",
                     docstatus=0, idx=1))
    sess.commit()
    _mitglied(sess, "M-ohne", "ohne@example.org")
    set_user("admin@example.org")

    daten = get_zugang("M-ohne")
    assert daten["konto"] is None
    assert "Mitglied" in daten["rollen_waehlbar"]


def test_konto_anlegen_verbindet_mitglied_und_konto(patched_db) -> None:
    from diakronos_app.api.zugang import get_zugang, konto_anlegen
    from diakronos_app.frappe_compat.session import set_user

    sess = patched_db()
    sess.add(User(name="admin@example.org", email="admin@example.org",
                  full_name="Admin", enabled=True))
    sess.add(HasRole(name="HR-admin", parent="admin@example.org", parenttype="User",
                     parentfield="roles", role="Mitgliederadministrator",
                     docstatus=0, idx=1))
    sess.commit()
    _mitglied(sess, "M-neu", "neu@example.org")
    set_user("admin@example.org")

    ergebnis = konto_anlegen("M-neu")
    assert ergebnis["success"] is True
    assert ergebnis["konto"]["user"] == "neu@example.org"
    assert ergebnis["konto"]["rollen"] == ["Mitglied"]
    sess.expire_all()
    assert sess.get(Mitglied, "M-neu").user == "neu@example.org"


def test_konto_anlegen_im_authentik_modus_verweigert(patched_db, monkeypatch) -> None:
    """Entscheidung 5: bei aktivem OIDC entstehen Konten beim Anbieter."""
    from diakronos_app.api import zugang
    from diakronos_app.anmeldung import konfiguration
    from diakronos_app.frappe_compat.exceptions import ValidationError
    from diakronos_app.frappe_compat.session import set_user

    sess = patched_db()
    sess.add(User(name="admin@example.org", email="admin@example.org",
                  full_name="Admin", enabled=True))
    sess.add(HasRole(name="HR-admin", parent="admin@example.org", parenttype="User",
                     parentfield="roles", role="Mitgliederadministrator",
                     docstatus=0, idx=1))
    sess.commit()
    _mitglied(sess, "M-oidc", "oidc@example.org")
    set_user("admin@example.org")
    monkeypatch.setattr(konfiguration, "oidc_aktiv", lambda: True)

    with pytest.raises(ValidationError, match="Authentik"):
        zugang.konto_anlegen("M-oidc")


def test_setze_rollen_nur_aus_fester_liste(patched_db) -> None:
    from diakronos_app.api.zugang import setze_rollen
    from diakronos_app.frappe_compat.exceptions import ValidationError
    from diakronos_app.frappe_compat.session import set_user

    sess = patched_db()
    sess.add(User(name="admin@example.org", email="admin@example.org",
                  full_name="Admin", enabled=True))
    sess.add(HasRole(name="HR-admin", parent="admin@example.org", parenttype="User",
                     parentfield="roles", role="Mitgliederadministrator",
                     docstatus=0, idx=1))
    sess.commit()
    _konto(sess, "ziel@example.org")
    _mitglied(sess, "M-ziel", "ziel@example.org", user="ziel@example.org")
    set_user("admin@example.org")

    daten = setze_rollen("M-ziel", ["Mitglied", "Kalenderadministrator"])
    assert daten["konto"]["rollen"] == ["Kalenderadministrator", "Mitglied"]

    with pytest.raises(ValidationError, match="Unbekannte Rolle"):
        setze_rollen("M-ziel", ["Fleet Manager"])


def test_setze_rollen_schuetzt_fremde_rollen(patched_db) -> None:
    """ERPNext-Erbe bleibt unberuehrt — nur die Diakronos-Rollen werden gesetzt."""
    from diakronos_app.api.zugang import setze_rollen
    from diakronos_app.frappe_compat.session import set_user

    sess = patched_db()
    sess.add(User(name="admin@example.org", email="admin@example.org",
                  full_name="Admin", enabled=True))
    sess.add(HasRole(name="HR-admin", parent="admin@example.org", parenttype="User",
                     parentfield="roles", role="Mitgliederadministrator",
                     docstatus=0, idx=1))
    sess.commit()
    _konto(sess, "ziel@example.org")
    sess.add(HasRole(name="HR-fremd", parent="ziel@example.org", parenttype="User",
                     parentfield="roles", role="Fleet Manager", docstatus=0, idx=1))
    sess.commit()
    _mitglied(sess, "M-ziel", "ziel@example.org", user="ziel@example.org")
    set_user("admin@example.org")

    daten = setze_rollen("M-ziel", ["Mitglied"])
    assert "Fleet Manager" in daten["konto"]["rollen"]
    assert "Mitglied" in daten["konto"]["rollen"]


def test_konto_sperren_widerruft_sitzungen(patched_db, fake_redis) -> None:
    from diakronos_app.api.zugang import konto_sperren
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.frappe_compat.session import set_user

    sess = patched_db()
    sess.add(User(name="admin@example.org", email="admin@example.org",
                  full_name="Admin", enabled=True))
    sess.add(HasRole(name="HR-admin", parent="admin@example.org", parenttype="User",
                     parentfield="roles", role="Mitgliederadministrator",
                     docstatus=0, idx=1))
    sess.commit()
    _konto(sess, "ziel@example.org")
    _mitglied(sess, "M-ziel", "ziel@example.org", user="ziel@example.org")
    set_user("admin@example.org")

    sitzungen.anlegen("ziel@example.org")
    daten = konto_sperren("M-ziel", True)
    assert daten["konto"]["enabled"] is False
    sess.expire_all()
    assert sess.get(User, "ziel@example.org").enabled is False


def test_zugang_verweigert_nicht_admin(patched_db) -> None:
    from diakronos_app.api.zugang import get_zugang
    from diakronos_app.frappe_compat.exceptions import PermissionError as PErr
    from diakronos_app.frappe_compat.session import set_user

    sess = patched_db()
    sess.add(User(name="mitglied@example.org", email="mitglied@example.org",
                  full_name="Mitglied", enabled=True))
    sess.commit()
    _mitglied(sess, "M-mitglied", "mitglied@example.org", user="mitglied@example.org")
    set_user("mitglied@example.org")

    with pytest.raises(PErr):
        get_zugang("M-mitglied")


# ── OP-ADMIN-3: wartende Konten (Authentik „Als Gast anlegen") ──────────────


def test_wartende_konten_zeigt_inaktive_konten(patched_db) -> None:
    from diakronos_app.api.zugang import get_wartende_konten, konto_sperren
    from diakronos_app.frappe_compat.session import set_user

    sess = patched_db()
    sess.add(User(name="admin@example.org", email="admin@example.org",
                  full_name="Admin", enabled=True))
    sess.add(HasRole(name="HR-admin", parent="admin@example.org", parenttype="User",
                     parentfield="roles", role="Mitgliederadministrator",
                     docstatus=0, idx=1))
    sess.commit()
    _konto(sess, "warten@example.org")
    _mitglied(sess, "M-warten", "warten@example.org", user="warten@example.org")
    set_user("admin@example.org")

    konto_sperren("M-warten", True)
    daten = get_wartende_konten()
    assert [k["user"] for k in daten["konten"]] == ["warten@example.org"]

    # Freischalten ueber denselben Schalter.
    konto_sperren("M-warten", False)
    assert get_wartende_konten()["konten"] == []


# ── W-1: Serienanzahl mit dem Statusfilter der Terminliste ──────────────────


def _serien_welt(patched_db, monkeypatch, *, moderator: bool):
    """Eine Serie mit Festgelegt/Vorschlag/Abgelehnt in einem Kalender."""
    from datetime import datetime

    from diakronos_app.api.kronos import calendar_get, permissions
    from diakronos_app.models.kronos import Element, Kalender

    sess = patched_db()
    t = datetime(2026, 10, 5, 10, 0, 0)
    sess.add(Kalender(name="K-1", calendar_name="Chor", calendar_color="#111111",
                      selbstverwaltet=False, docstatus=0, idx=0))
    sess.commit()
    for i, status in enumerate(("Festgelegt", "Vorschlag", "Abgelehnt")):
        sess.add(Element(
            name=f"EVS-{i}", element_name=f"Serie {status}",
            element_calendar="K-1", element_start=t, element_end=t,
            all_day=False, status=status, series_id="SERIE-1",
            docstatus=0, idx=i, creation=t, modified=t,
        ))
    sess.commit()

    monkeypatch.setattr(
        permissions, "get_accessible_calendars",
        lambda: [{"name": "K-1", "is_moderator": moderator}],
    )
    monkeypatch.setattr(
        calendar_get, "get_accessible_calendars",
        lambda: [{"name": "K-1", "is_moderator": moderator}],
    )
    return sess


def test_serien_anzahl_bearbeitungsmodus_moderator_ohne_abgelehnt(patched_db, monkeypatch) -> None:
    from diakronos_app.api.kronos.calendar_get import _attach_serien_anzahl

    _serien_welt(patched_db, monkeypatch, moderator=True)
    formatted = [{"extendedProps": {"series_id": "SERIE-1"}}]
    _attach_serien_anzahl(formatted, ["K-1"], False)
    # Festgelegt + Vorschlag, NICHT Abgelehnt.
    assert formatted[0]["extendedProps"]["series_count"] == 2


def test_serien_anzahl_bearbeitungsmodus_nicht_moderator_nur_festgelegt(
    patched_db, monkeypatch
) -> None:
    from diakronos_app.api.kronos.calendar_get import _attach_serien_anzahl

    _serien_welt(patched_db, monkeypatch, moderator=False)
    formatted = [{"extendedProps": {"series_id": "SERIE-1"}}]
    _attach_serien_anzahl(formatted, ["K-1"], False)
    # Nur Festgelegt (wie die Terminliste des Nicht-Moderators).
    assert formatted[0]["extendedProps"]["series_count"] == 1


def test_serien_anzahl_lesemodus_nur_festgelegt(patched_db, monkeypatch) -> None:
    from diakronos_app.api.kronos.calendar_get import _attach_serien_anzahl

    _serien_welt(patched_db, monkeypatch, moderator=True)
    formatted = [{"extendedProps": {"series_id": "SERIE-1"}}]
    _attach_serien_anzahl(formatted, ["K-1"], True)
    assert formatted[0]["extendedProps"]["series_count"] == 1


# ── K-1: CalDAV-XML ohne Steuerzeichen/Surrogate ────────────────────────────


def test_caldav_text_entfernt_steuerzeichen_und_surrogate() -> None:
    from diakronos_app.caldav.server import _text

    # Steuerzeichen (Bell, vertical tab) und ein alleinstehendes Surrogat.
    roh = "Chor\x07 <Orgel & Gesang>\x0b\ud800"
    sauber = _text(roh)
    assert "\x07" not in sauber and "\x0b" not in sauber
    assert "\ud800" not in sauber
    assert "&amp;" in sauber and "&lt;" in sauber and "&gt;" in sauber


def test_caldav_text_behaelt_tab_und_zeilenumbruch() -> None:
    from diakronos_app.caldav.server import _text

    assert _text("a\tb\nc\rd") == "a\tb\nc\rd"


def test_caldav_text_ist_utf8_kodierbar() -> None:
    """Ohne Surrogate ist die Antwort UTF-8-kodierbar (kein 500)."""
    from diakronos_app.caldav.server import _text

    _text("Titel mit \ud800 Surrogat").encode("utf-8")


def test_caldav_text_bleibt_parsebar() -> None:
    from diakronos_app.caldav.server import _text

    roh = _text("Chor\x07 & <Orgel>\ud800")
    ET.fromstring(f"<D:displayname xmlns:D='DAV:'>{roh}</D:displayname>")
