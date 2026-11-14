"""R-2: Rollen und Module verwalten (``diakronos_app.rechte.verwaltung``).

Regeln (Manuel 11.11.): HV/MV ernennt nur der HV; GL ernennen HV und MV;
das HV-Amt wird nur mit Bestaetigung uebertragen, der alte HV wird MV;
den ersten HV und die Module setzt der Administrator.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from diakronos_app import rechte as R
from diakronos_app.frappe_compat.exceptions import PermissionError, ValidationError
from diakronos_app.models.core import User
from diakronos_app.models.rechte import RechteGruppenrolle, RechteModul
from diakronos_app.rechte import verwaltung as V

from test_r1_rechte_kern import (  # noqa: F401 — gemeinsame Welt
    ADMIN, ANNA, CHORSAENGER, FREMD, GL, MIRA, REBEKKA, SAMUEL, SOPRAN, unter, welt,
)


def _rollen(sess, gruppe):
    sess.expire_all()
    return {(z.benutzer, z.rolle, z.untergruppe) for z in sess.execute(
        select(RechteGruppenrolle).where(RechteGruppenrolle.gruppe == gruppe)).scalars()}


def test_hv_ernennt_und_entfernt_mv(welt):
    V.ernenne_mv(REBEKKA, "Chor", ANNA)
    assert (ANNA, "MV", None) in _rollen(welt, "Chor")
    assert R.gruppenrolle(ANNA, "Chor") == "MV"
    V.entferne_mv(REBEKKA, "Chor", ANNA)
    assert (ANNA, "MV", None) not in _rollen(welt, "Chor")


def test_mv_ernennt_keine_mv(welt):
    with pytest.raises(PermissionError):
        V.ernenne_mv(MIRA, "Chor", ANNA)
    with pytest.raises(PermissionError):
        V.entferne_mv(MIRA, "Chor", MIRA)


def test_fremder_hv_ernennt_nicht_in_anderer_gruppe(welt):
    with pytest.raises(PermissionError):
        V.ernenne_mv(SAMUEL, "Chor", ANNA)


def test_hv_kann_nicht_entfernt_werden(welt):
    with pytest.raises(ValidationError):
        V.entferne_mv(REBEKKA, "Chor", REBEKKA)


def test_ernennen_nur_aktive_konten(welt):
    welt.add(User(name="aus@example.org", email="aus@example.org", enabled=0))
    welt.commit()
    with pytest.raises(ValidationError):
        V.ernenne_mv(REBEKKA, "Chor", "aus@example.org")
    with pytest.raises(ValidationError):
        V.ernenne_mv(REBEKKA, "Chor", "gibtsnicht@example.org")


def test_hv_uebertragen_braucht_bestaetigung(welt):
    with pytest.raises(ValidationError):
        V.uebertrage_hv(REBEKKA, "Chor", ANNA, bestaetigt=False)
    assert R.gruppenrolle(REBEKKA, "Chor") == "HV"


def test_hv_uebertragen_alter_hv_wird_mv(welt):
    V.uebertrage_hv(REBEKKA, "Chor", ANNA, bestaetigt=True)
    rollen = _rollen(welt, "Chor")
    assert (ANNA, "HV", None) in rollen
    assert (REBEKKA, "MV", None) in rollen
    assert sum(1 for _b, r, _u in rollen if r == "HV") == 1
    # neuer HV darf jetzt ernennen, alter nicht mehr
    assert R.darf(ANNA, R.ROLLEN, "gruppe", gruppe="Chor")
    assert not R.darf(REBEKKA, R.ROLLEN, "gruppe", gruppe="Chor")


def test_hv_uebertragen_an_bisherigen_mv_ohne_doppelzeile(welt):
    V.uebertrage_hv(REBEKKA, "Chor", MIRA, bestaetigt=True, alter_hv_wird_mv=False)
    rollen = _rollen(welt, "Chor")
    assert (MIRA, "HV", None) in rollen
    assert not any(b == REBEKKA for b, _r, _u in rollen)


def test_mv_kann_hv_nicht_uebertragen(welt):
    with pytest.raises(PermissionError):
        V.uebertrage_hv(MIRA, "Chor", MIRA, bestaetigt=True)


def test_ersten_hv_setzt_nur_admin(welt):
    from diakronos_app.models.diakonos import Gruppe

    welt.add(Gruppe(name="Neu", gruppenname="Neue Gruppe"))
    welt.commit()
    with pytest.raises(PermissionError):
        V.uebertrage_hv(REBEKKA, "Neu", REBEKKA, bestaetigt=True)
    V.uebertrage_hv(ADMIN, "Neu", SAMUEL, bestaetigt=True)
    assert R.gruppenrolle(SAMUEL, "Neu") == "HV"


def test_gl_ernennen_hv_und_mv_nicht_gl(unter):
    V.ernenne_gl(MIRA, "Sopran", SOPRAN)
    assert R.untergruppenrolle(SOPRAN, "Sopran") == "GL"
    with pytest.raises(PermissionError):
        V.ernenne_gl(GL, "Sopran", ANNA)
    V.entferne_gl(REBEKKA, "Sopran", SOPRAN)
    assert R.untergruppenrolle(SOPRAN, "Sopran") == "Mitglied"


def test_gl_bleibt_beim_mv_werden_erhalten(unter):
    """GL einer Untergruppe und MV der Hauptgruppe sind getrennte Rollen."""
    V.ernenne_mv(REBEKKA, "Chor", GL)
    rollen = _rollen(unter, "Chor")
    assert (GL, "MV", None) in rollen
    assert (GL, "GL", "Sopran") in rollen


def test_module_setzt_nur_admin(welt):
    with pytest.raises(PermissionError):
        V.setze_module(REBEKKA, "Chor", ["kalender"])
    V.setze_module(ADMIN, "Jugend", ["kalender", "lieder"])
    welt.expire_all()
    module = set(welt.execute(select(RechteModul.modul).where(RechteModul.gruppe == "Jugend")).scalars())
    assert module == {"kalender", "lieder"}
    assert R.darf(SAMUEL, R.SCHREIBEN, "lied", "L1")
    with pytest.raises(ValidationError):
        V.setze_module(ADMIN, "Jugend", ["zauberei"])


def test_rollen_der_gruppe_zeigt_erlaubte_knoepfe(unter):
    hv = V.rollen_der_gruppe(REBEKKA, "Chor")
    assert hv["darf_hv_mv_ernennen"] and hv["darf_verwalten"]
    mv = V.rollen_der_gruppe(MIRA, "Chor")
    assert not mv["darf_hv_mv_ernennen"] and mv["darf_verwalten"]
    gl = next(r for r in hv["rollen"] if r["rolle"] == "GL")
    assert (gl["benutzer"], gl["untergruppe"], gl["untergruppe_name"]) == (GL, "Sopran", "Sopran")
    assert gl["name"] == "Gabi U"
    with pytest.raises(PermissionError):
        V.rollen_der_gruppe(FREMD, "Chor")


def test_rollen_der_gruppe_lesende_sehen_namen_keine_konten(unter):
    """UI-R1/R-9: Mitglieder sehen die Namen der Leitung, nicht deren Kontokennung."""
    lesend = V.rollen_der_gruppe(CHORSAENGER, "Chor")
    assert not lesend["darf_verwalten"]
    assert all(r["benutzer"] is None for r in lesend["rollen"])
    assert {r["name"] for r in lesend["rollen"]} >= {"Rebekka Fink", "Mira Mit"}


def test_aenderungen_werden_protokolliert(welt, monkeypatch):
    eintraege = []
    from diakronos_app.api import audit

    monkeypatch.setattr(audit, "log", lambda *a, **k: eintraege.append(a))
    V.ernenne_mv(REBEKKA, "Chor", ANNA)
    V.uebertrage_hv(REBEKKA, "Chor", ANNA, bestaetigt=True)
    assert [e[0] for e in eintraege] == ["Berechtigungsänderung", "Berechtigungsänderung"]
    assert "HV-Amt übertragen" in eintraege[-1][3]


def test_endpunkte_sind_post_only():
    """Schreibende Rechte-Endpunkte sind im Register POST-only (CSRF)."""
    from test_sec11_methoden import _betriebseintraege

    eintraege = {k: e for k, e in _betriebseintraege().items() if k.startswith("diakronos_app.api.rechte.")}
    for name in ("ernenne_mv", "entferne_mv", "ernenne_gl", "entferne_gl", "uebertrage_hv", "setze_module"):
        e = eintraege[f"diakronos_app.api.rechte.{name}"]
        assert e["optionen"].get("methods") == ("POST",), name
