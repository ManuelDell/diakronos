"""R-11: Altpfade auf das EINE Rechtesystem umgestellt (Plan diakronos-rechte).

Soll (Manuel 11.11.):
  * „Der Admin ist ja der einzige der alles darf“ — die Mitgliederverwaltung
    ist eine Fachverwaltung (Personen, Konten), kein Vollzugriff: keine
    Gruppenrollen, kein Papierkorb, keine generische REST-Schnittstelle.
  * Personen: Namen aller Mitglieder fuer alle Gemeindemitglieder; weitere
    Daten (Beziehungen, fremde Gruppen) nur nach Freigabe bzw. fuer die
    Verwaltung — kein ancestor_path mehr.
  * Gruppen-/Bereichsrechte kommen aus dem Kern; Dienstbereiche verleihen
    keine Rechte mehr.
"""

from __future__ import annotations

import pytest

from diakronos_app.frappe_compat import permissions as P
from diakronos_app.frappe_compat.exceptions import PermissionError as PermErr
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Mitglied, MitgliedBeziehung

from test_r1_rechte_kern import (  # noqa: F401 — gemeinsame Welt
    ADMIN, CHORSAENGER, FREMD, MIRA, REBEKKA, SAMUEL, welt,
)

VERWALTUNG = "verwaltung@example.org"   # nur Systemrolle Mitgliederadministrator


@pytest.fixture()
def r11(welt):
    welt.add(User(name=VERWALTUNG, email=VERWALTUNG, enabled=1))
    welt.add(Mitglied(name="M-Ve", vorname="Ve", nachname="Waltung", email=VERWALTUNG, user=VERWALTUNG))
    welt.add(HasRole(name="hr-ve", parent=VERWALTUNG, parenttype="User", role="Mitgliederadministrator"))
    welt.add(MitgliedBeziehung(name="bz1", parent="M-Sa", parenttype="Mitglied", parentfield="beziehungen",
                               beziehung_zu="M-Fr", beziehungstyp="Ehepartner"))
    welt.commit()
    return welt


@pytest.fixture(autouse=True)
def _zuruecksetzen():
    yield
    set_user("Administrator")


def _als(user, fn, *a, **kw):
    set_user(user)
    try:
        return fn(*a, **kw)
    finally:
        set_user("Administrator")


# ── R-11a: Admin-Begriff ────────────────────────────────────────────────────

def test_mitgliederverwaltung_ist_kein_admin(r11):
    assert P.is_admin(ADMIN) and P.is_admin("Administrator")
    assert not P.is_admin(VERWALTUNG)
    assert P.ist_mitgliederverwaltung(VERWALTUNG) and P.ist_mitgliederverwaltung(ADMIN)
    assert not P.ist_mitgliederverwaltung(CHORSAENGER)


def test_mitgliederverwaltung_ohne_rest_vollzugriff(r11):
    from diakronos_app.frappe_compat.router import _resource_denied

    set_user(VERWALTUNG)
    assert _resource_denied("Gruppe", "list") is not None
    assert _resource_denied("Gruppe", "write") is not None
    set_user(ADMIN)
    assert _resource_denied("Gruppe", "list") is None


def test_mitgliederverwaltung_ohne_papierkorb_und_gruppenrollen(r11):
    from diakronos_app.api import papierkorb as PK
    from diakronos_app.api import verantwortliche as V

    with pytest.raises(PermErr):
        _als(VERWALTUNG, PK.liste)
    assert _als(ADMIN, PK.liste)["success"]
    with pytest.raises(PermErr):
        _als(VERWALTUNG, V.set_verantwortliche, "Gruppe", "Chor", [VERWALTUNG])


def test_boot_flags(r11):
    from diakronos_app.api import session as S

    ctx = _als(VERWALTUNG, S.get_current_user_context)
    assert not ctx["is_admin"] and ctx["ist_mitgliederverwaltung"]
    assert ctx["permissions"]["can_view_dsgvo"] and not ctx["permissions"]["can_edit_gruppen"]
    ctx = _als(CHORSAENGER, S.get_current_user_context)
    assert not ctx["is_admin"] and not ctx["ist_mitgliederverwaltung"]
    assert ctx["permissions"]["can_view_gruppen"] and not ctx["permissions"]["can_view_bereiche"]


# ── R-11b: Personen-Sicht ───────────────────────────────────────────────────

def test_namen_fuer_alle_mitglieder_weitere_daten_nicht(r11):
    from diakronos_app.api import mitglieder as M

    perms = _als(FREMD, P.mitglied_permissions, "M-Sa")
    assert perms["can_view"] and not perms["can_edit"] and not perms["can_view_sensitive"]
    detail = _als(FREMD, M.get_mitglied_detail, "M-Sa")["data"]
    assert detail["vorname"] == "Sa"
    assert detail["beziehungen"] == [] and detail["gruppenmitgliedschaften"] == []
    with pytest.raises(PermErr):
        _als(FREMD, M.get_beziehungen_for_mitglied, "M-Sa")
    assert _als(FREMD, M.get_gruppen_for_mitglied, "M-Sa")["data"] == []

    # Mitglied der Gruppe sieht die Mitgliedschaft, Verwaltung und die Person alles
    assert [g["gruppe"] for g in _als(MIRA, M.get_gruppen_for_mitglied, "M-Sa")["data"]] == ["Chor"]
    assert _als(VERWALTUNG, M.get_mitglied_detail, "M-Sa")["data"]["beziehungen"]
    assert _als(CHORSAENGER, M.get_beziehungen_for_mitglied, "M-Sa")["data"]


def test_mitgliederliste_und_suche_zeigen_alle_namen(r11):
    from diakronos_app.api import mitglieder as M
    from diakronos_app.api import suche as SU

    namen = {z["name"] for z in _als(FREMD, M.get_mitglieder_liste, limit=100)["data"]}
    assert {"M-Sa", "M-Rebekka", "M-Ve"} <= namen
    treffer = _als(FREMD, SU._personen, "Rebekka", 10, FREMD)
    assert [t["titel"] for t in treffer] == ["Rebekka Fink"]


# ── R-11c/d: Gruppen und Bereiche am Kern ───────────────────────────────────

def test_check_permission_gruppe_und_bereich(r11):
    assert _als(CHORSAENGER, P.check_permission, "Gruppe", "Chor", "read")["allowed"]
    assert not _als(CHORSAENGER, P.check_permission, "Gruppe", "Chor", "write")["allowed"]
    assert _als(MIRA, P.check_permission, "Gruppe", "Chor", "write")["allowed"]
    assert not _als(FREMD, P.check_permission, "Gruppe", "Chor", "read")["allowed"]
    assert not _als(REBEKKA, P.check_permission, "Dienstbereich", "Musik", "read")["allowed"]
    assert _als(MIRA, P.ist_verantwortlich_fuer, "Musik", "Chor")
    assert not _als(CHORSAENGER, P.ist_verantwortlich_fuer, "Musik", "Chor")
    assert not _als(SAMUEL, P.has_bereichs_zugriff, "Musik", None)
    assert _als(CHORSAENGER, P.has_bereichs_zugriff, "Musik", "Chor")


def test_eigene_gruppen_aus_dem_kern(r11):
    from diakronos_app import rechte

    assert rechte.eigene_gruppen(CHORSAENGER) == {"Chor"}
    assert rechte.eigene_gruppen(MIRA) == {"Chor"}
    assert rechte.eigene_gruppen(FREMD) == set()


def test_gruppe_endgueltig_nimmt_rechte_mit(r11):
    from diakronos_app import papierkorb
    from diakronos_app.models.rechte import RechteGruppenrolle, RechteModul, RechteObjekt

    papierkorb._endgueltig_gruppe("Jugend")
    r11.expire_all()
    assert r11.query(RechteGruppenrolle).filter_by(gruppe="Jugend").count() == 0
    assert r11.query(RechteModul).filter_by(gruppe="Jugend").count() == 0
    kal = r11.query(RechteObjekt).filter_by(typ="kalender", objekt="jugendkal").one()
    assert kal.gruppe is None  # Gemeinde-Objekt: nur Admin/Fachverwaltung


# ── R-11e: Kalender-Altfelder ───────────────────────────────────────────────

def test_kalenderverwaltung_alte_felder_aus_dem_rechtesystem(r11):
    from diakronos_app.api.kronos.kalender_verwaltung import _alte_felder_aus_rechten
    from diakronos_app.models.rechte import RechteFreigabe

    r11.add(RechteFreigabe(typ="kalender", objekt="jugendkal", benutzer=MIRA, lesen=True, moderieren=True))
    r11.commit()
    assert _alte_felder_aus_rechten("jugendkal") == {
        "leserechte": ["Mitglied"], "schreibrechte": [], "moderatoren": [MIRA]}
    assert _alte_felder_aus_rechten("chorkal")["leserechte"] == []
