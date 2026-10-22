"""UNABHAENGIGE Reviewer-Pruefung der Pflicht-Verweigerungen aus der P3-Karte.

Bewusst NICHT aus test_permissions.py abgeleitet: eigene Formulierung, eigene
Erwartungen. Faellt einer dieser Faelle auf "erlaubt", ist die Karte gescheitert.
"""
import pytest
from diakronos_app.frappe_compat import permissions as P
from diakronos_app.frappe_compat.session import set_user
from tests.test_permissions import hierarchie  # noqa: F401


def _erlaubt(doctype, name, aktion="read"):
    return P.check_permission(doctype, name, aktion).get("allowed")


def test_mitglied_sieht_kein_mitglied_aus_fremdem_bereich(hierarchie):  # noqa: F811
    set_user("mitglied-a@example.org")
    assert _erlaubt("Mitglied", "M-gruppe-b1", "read") is False


def test_mitglied_schreibt_keine_gruppe_auch_nicht_die_eigene(hierarchie):  # noqa: F811
    set_user("mitglied-a@example.org")
    for aktion in ("write", "create", "delete"):
        assert _erlaubt("Gruppe", "G-A1", aktion) is False, f"{aktion} auf eigene Gruppe erlaubt!"
        assert _erlaubt("Gruppe", "G-B1", aktion) is False, f"{aktion} auf fremde Gruppe erlaubt!"


def test_benutzer_ohne_mitglied_datensatz_sieht_keine_gruppe(hierarchie):  # noqa: F811
    set_user("ohne-mitglied@example.org")
    assert _erlaubt("Gruppe", "G-A1", "read") is False
    assert _erlaubt("Dienstbereich", "DB-A", "read") is False
    assert _erlaubt("Untergruppe", "UG-A1", "read") is False


def test_guest_sieht_nichts(hierarchie):  # noqa: F811
    set_user("Guest")
    for dt, nm in (("Mitglied", "M-gruppe-a1"), ("Gruppe", "G-A1"),
                   ("Dienstbereich", "DB-A"), ("Untergruppe", "UG-A1")):
        assert _erlaubt(dt, nm, "read") is False, f"Guest darf {dt} lesen!"


def test_unbekannter_doctype_wird_verweigert(hierarchie):  # noqa: F811
    """Unbekannter DocType -> deny, fuer jeden NICHT-Admin.

    Admins ausgenommen: das Original (api/session.py) kurzschliesst
    `if is_admin: return allowed` VOR jeder DocType-Pruefung. Ein Admin
    bekommt dort also auch fuer einen unbekannten DocType `admin_role`.
    Das ist originalgetreu und bewusst so portiert — die Kartenformulierung
    "unbekannter DocType muss verweigern" war an dieser Stelle unpraezise.
    """
    for u in ("mitglied-a@example.org", "ohne-mitglied@example.org", "Guest"):
        set_user(u)
        r = P.check_permission("Gibt Es Nicht", "irgendwas", "read")
        assert r["allowed"] is False, f"{u} darf unbekannten DocType lesen!"
        assert r["reason"] == "unsupported_doctype"


def test_fremdes_mitglied_auch_nicht_schreibend(hierarchie):  # noqa: F811
    set_user("mitglied-a@example.org")
    assert _erlaubt("Mitglied", "M-gruppe-b1", "write") is False
