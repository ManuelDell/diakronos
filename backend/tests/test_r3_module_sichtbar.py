"""R-3: sichtbare Module (Navigation) aus dem EINEN Rechtesystem."""

from __future__ import annotations

from diakronos_app import rechte as R
from diakronos_app.models.rechte import RechteFreigabe, RechteObjekt

from test_r1_rechte_kern import ADMIN, CHORSAENGER, FREMD, REBEKKA, SAMUEL, welt  # noqa: F401


def test_module_ueber_gruppen(welt):
    assert "lieder" in R.sichtbare_module(CHORSAENGER)
    assert "lieder" not in R.sichtbare_module(SAMUEL)
    # FREMD ist in keiner Gruppe, liest aber den gemeindeweit freigegebenen Jugendkalender
    assert R.sichtbare_module(FREMD) == {"kalender"}


def test_gemeinde_inhalte_machen_modul_fuer_alle_mitglieder_sichtbar(welt):
    welt.add(RechteObjekt(typ="beitrag", objekt="B1", gruppe=None, gemeinde_status="aktiv"))
    welt.commit()
    assert "beitraege" in R.sichtbare_module(FREMD)


def test_einzelfreigabe_macht_modul_sichtbar(welt):
    welt.add_all([
        RechteObjekt(typ="wiki", objekt="W-privat", gruppe=None),
        RechteFreigabe(typ="wiki", objekt="W-privat", benutzer=FREMD, lesen=True),
    ])
    welt.commit()
    assert "wiki" in R.sichtbare_module(FREMD)


def test_admin_sieht_alle_module(welt):
    assert R.sichtbare_module(ADMIN) == set(R.MODULE)


def test_boot_liefert_module_sichtbar(welt):
    from diakronos_app import spa

    assert spa._module_sichtbar(REBEKKA) == sorted(R.sichtbare_module(REBEKKA))
    assert spa._module_sichtbar("Guest") == []
