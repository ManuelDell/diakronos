"""P1-8b — Reproduktionstests der Sicherheitsnacharbeit (R-P1-8).

Diese Tests stammen aus dem unabhaengigen Sicherheits-Review
(Befund) und waren VOR der Behebung rot:

  * B1 — ein Mitgliederadministrator konnte ein Konto mit System-Manager-Rolle
    uebernehmen (Passwort setzen, sperren) bzw. sich/anderen die
    Verwaltungsrolle geben.
  * B2 — der letzte aktive Administrator konnte sich selbst aussperren
    (Konto sperren, Rolle entziehen, Mitglied ausschliessen).
  * W5 — Guest und deaktivierte Konten liessen sich als Verantwortliche
    eintragen.

Jeder Test waere ohne die zugehoerige Aenderung in `api/zugang.py`,
`api/verantwortliche.py`, `api/mitglieder.py` und `planrahmen/rechte.py` rot.
"""

from __future__ import annotations

import pytest

from diakronos_app.frappe_compat.exceptions import (
    PermissionError as FrappePermissionError,
    ValidationError,
)
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Gruppe, Mitglied


def _konto(sess, email: str, rolle: str | None = None, *, enabled: bool = True) -> None:
    """Konto mit optionaler Rolle und verknuepftem Mitglied anlegen."""
    sess.add(User(name=email, email=email, full_name=email, enabled=enabled))
    if rolle:
        sess.add(HasRole(name=f"HR-{email}-{rolle}", parent=email, parenttype="User",
                         parentfield="roles", role=rolle, docstatus=0, idx=1))
    sess.add(Mitglied(name=f"M-{email}", vorname=email, nachname="Test",
                      email=email, status="Mitglied", user=email, docstatus=0, idx=0))
    sess.commit()


# ── B1: Eskalation ueber Zugang ─────────────────────────────────────────────


def test_mitgliederadmin_darf_system_manager_passwort_nicht_setzen(patched_db) -> None:
    """B1: Passwort-Uebernahme eines System-Manager-Kontos ist verweigert."""
    from diakronos_app.api.zugang import setze_passwort

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "sm@x.org", "System Manager")
    set_user("ma@x.org")

    with pytest.raises(FrappePermissionError):
        setze_passwort("M-sm@x.org", "NeuesPasswort123")


def test_mitgliederadmin_darf_system_manager_nicht_sperren(patched_db) -> None:
    """B1: Sperren eines System-Manager-Kontos ist verweigert."""
    from diakronos_app.api.zugang import konto_sperren

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "sm@x.org", "System Manager")
    set_user("ma@x.org")

    with pytest.raises(FrappePermissionError):
        konto_sperren("M-sm@x.org", True)


def test_mitgliederadmin_darf_mitgliederadmin_rolle_nicht_vergeben(patched_db) -> None:
    """B1: Nur System Manager vergibt die Verwaltungsrolle."""
    from diakronos_app.api.zugang import setze_rollen

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "x@x.org", "Mitglied")
    set_user("ma@x.org")

    with pytest.raises(FrappePermissionError):
        setze_rollen("M-x@x.org", ["Mitgliederadministrator"])


def test_mitgliederadmin_darf_einfache_rollen_pflegen(patched_db) -> None:
    """Gegenprobe: einfache (Nicht-Admin-)Rollen darf er weiter setzen."""
    from diakronos_app.api.zugang import setze_rollen

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "x@x.org", "Mitglied")
    set_user("ma@x.org")

    r = setze_rollen("M-x@x.org", ["Mitglied", "Kalenderadministrator"])
    assert r["success"] is True
    assert "Kalenderadministrator" in r["konto"]["rollen"]


def test_system_manager_darf_kalenderadmin_vergeben(patched_db) -> None:
    """Gegenprobe: ein System Manager darf einfache Rollen vergeben."""
    from diakronos_app.api.zugang import setze_rollen

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "x@x.org", "Mitglied")
    set_user("sm@x.org")

    r = setze_rollen("M-x@x.org", ["Kalenderadministrator"])
    assert "Kalenderadministrator" in r["konto"]["rollen"]


# ── B2: Aussperr-Schutz ─────────────────────────────────────────────────────


def test_letzter_system_manager_kann_sich_nicht_sperren(patched_db) -> None:
    """B2: der letzte aktive System Manager darf sich nicht selbst sperren."""
    from diakronos_app.api.zugang import konto_sperren

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")

    with pytest.raises(FrappePermissionError):
        konto_sperren("M-sm@x.org", True)


def test_letzter_admin_kann_sich_rolle_nicht_entziehen(patched_db) -> None:
    """B2: auch der letzte Mitgliederadministrator bleibt geschuetzt."""
    from diakronos_app.api.zugang import setze_rollen

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    set_user("ma@x.org")

    with pytest.raises(FrappePermissionError):
        setze_rollen("M-ma@x.org", ["Mitglied"])


def test_zweiter_system_manager_erlaubt_selbstsperre(patched_db) -> None:
    """Gegenprobe: mit zwei System Managern ist das Sperren des einen erlaubt."""
    from diakronos_app.api.zugang import konto_sperren

    sess = patched_db()
    _konto(sess, "sm1@x.org", "System Manager")
    _konto(sess, "sm2@x.org", "System Manager")
    set_user("sm1@x.org")

    r = konto_sperren("M-sm2@x.org", True)
    assert r["konto"]["enabled"] is False


def test_letzter_system_manager_kann_sich_nicht_ausschliessen(patched_db) -> None:
    """B2: der letzte aktive System Manager darf sich nicht ausschliessen."""
    from diakronos_app.api.mitglieder import schliesse_mitglied_aus

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")

    with pytest.raises(FrappePermissionError):
        schliesse_mitglied_aus("M-sm@x.org", "Test")
    # Die Markierung darf NICHT gesetzt geblieben sein (Ruecknahme).
    sess.expire_all()
    m = sess.get(Mitglied, "M-sm@x.org")
    assert bool(m.ausgeschlossen) is False


# ── W5: Verantwortliche — Guest/deaktiviert/ausgeschlossen abgelehnt ────────


def test_guest_kann_nicht_verantwortlicher_werden(patched_db) -> None:
    """W5: „Guest" ist kein gueltiger Verantwortlicher."""
    from diakronos_app.api.verantwortliche import set_verantwortliche

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    sess.add(Gruppe(name="G1", docstatus=0, idx=0))
    sess.add(User(name="Guest", email="guest@x", full_name="Guest", enabled=True))
    sess.commit()
    set_user("ma@x.org")

    with pytest.raises(ValidationError):
        set_verantwortliche("Gruppe", "G1", ["Guest"])


def test_gesperrtes_konto_kann_nicht_verantwortlicher_werden(patched_db) -> None:
    """W5: ein deaktiviertes Konto ist keine gueltige Besetzung."""
    from diakronos_app.api.verantwortliche import set_verantwortliche

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "off@x.org", "Mitglied", enabled=False)
    sess.add(Gruppe(name="G1", docstatus=0, idx=0))
    sess.commit()
    set_user("ma@x.org")

    with pytest.raises(ValidationError):
        set_verantwortliche("Gruppe", "G1", ["off@x.org"])
