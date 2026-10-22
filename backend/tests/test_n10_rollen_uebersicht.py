"""N10 — Rollenuebersicht (Lese-Tabelle des Abschnitts „Rollen & Rechte").

Der Endpunkt `get_rollen_uebersicht` liefert je Person mit Konto die Rollen
und den Kontozustand sowie die waehlbare Rollenliste und den System-Manager-
Status. Er ist die Datengrundlage der neuen Einstellungsseite; die Rechte
kommen vom Server (nur Administratoren).
"""

from __future__ import annotations

from diakronos_app.frappe_compat.exceptions import (
    PermissionError as FrappePermissionError,
)
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Mitglied

WEG = "diakronos.diakonos.api.zugang.get_rollen_uebersicht"


def _konto(sess, email: str, rolle: str | None = None, *, enabled: bool = True,
           mitglied: bool = True) -> None:
    sess.add(User(name=email, email=email, full_name=email, enabled=enabled))
    if rolle:
        sess.add(HasRole(
            name=f"HR-{email}-{rolle}", parent=email, parenttype="User",
            parentfield="roles", role=rolle, docstatus=0, idx=1,
        ))
    if mitglied:
        sess.add(Mitglied(
            name=f"M-{email}", vorname="Vorname", nachname="Nachname", email=email,
            status="Mitglied", user=email, docstatus=0, idx=0,
        ))
    sess.commit()


def test_rollen_uebersicht_listet_konten_mit_rollen(patched_db, fake_redis) -> None:
    from diakronos_app.api.zugang import get_rollen_uebersicht

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "leiter@x.org", "Mitglied")
    set_user("sm@x.org")

    daten = get_rollen_uebersicht()

    konten = {k["user"]: k for k in daten["konten"]}
    assert "sm@x.org" in konten and "leiter@x.org" in konten
    assert "System Manager" in konten["sm@x.org"]["rollen"]
    assert "Mitglied" in konten["leiter@x.org"]["rollen"]
    assert konten["leiter@x.org"]["mitglied"] == "M-leiter@x.org"
    assert "sm@x.org" in daten["aktive_system_manager"]
    assert daten["ist_system_manager"] is True
    assert "Mitglied" in daten["rollen_waehlbar"]


def test_rollen_uebersicht_zeigt_gesperrtes_konto(patched_db, fake_redis) -> None:
    from diakronos_app.api.zugang import get_rollen_uebersicht

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "gesperrt@x.org", "Mitglied", enabled=False)
    set_user("sm@x.org")

    daten = get_rollen_uebersicht()
    konten = {k["user"]: k for k in daten["konten"]}
    assert konten["gesperrt@x.org"]["enabled"] is False


def test_rollen_uebersicht_nur_admin(patched_db, fake_redis) -> None:
    from diakronos_app.api.zugang import get_rollen_uebersicht

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "mitglied@x.org", "Mitglied")
    set_user("mitglied@x.org")

    try:
        get_rollen_uebersicht()
    except FrappePermissionError:
        return
    raise AssertionError("Nicht-Admin durfte die Rollenuebersicht lesen.")


# ── K2/K3 (R-N10): darf_verwalten und Gastkonto-Hinweis ────────────────────


def test_darf_verwalten_ist_fuer_mitgliederadmin_falsch(patched_db, fake_redis) -> None:
    """K3: `darf_verwalten` ist NICHT konstant True.

    Ein Mitgliederadministrator darf keine Verwaltungsrollen vergeben/entziehen
    (`setze_rollen` prueft dasselbe) — also ist der Wert fuer ihn False.
    """
    from diakronos_app.api.zugang import get_rollen_uebersicht

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    set_user("ma@x.org")

    daten = get_rollen_uebersicht()
    assert daten["ist_system_manager"] is False
    assert daten["darf_verwalten"] is False


def test_darf_verwalten_ist_fuer_system_manager_wahr(patched_db, fake_redis) -> None:
    """K3: der System Manager darf Verwaltungsrollen vergeben."""
    from diakronos_app.api.zugang import get_rollen_uebersicht

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")

    daten = get_rollen_uebersicht()
    assert daten["darf_verwalten"] is True


def test_konto_ohne_mitglied_traegt_hinweis(patched_db, fake_redis) -> None:
    """K2: Ein Konto ohne Mitglied nennt den Grund (Freischalten unter Anmeldung)."""
    from diakronos_app.api.zugang import get_rollen_uebersicht

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "ohne-mitglied@x.org", None, mitglied=False)
    set_user("sm@x.org")

    daten = get_rollen_uebersicht()
    konten = {k["user"]: k for k in daten["konten"]}
    zeile = konten["ohne-mitglied@x.org"]
    assert zeile["mitglied"] is None
    assert zeile["hinweis"] and "Anmeldung" in zeile["hinweis"]
    # Ein Konto MIT Mitglied traegt keinen Hinweis.
    assert konten["sm@x.org"]["hinweis"] is None
