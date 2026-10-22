"""R1: Auch Löschen darf durch eindeutige E-Mail kein Verwaltungskonto aussperren."""
from __future__ import annotations

import asyncio

import pytest

from diakronos_app.frappe_compat.exceptions import PermissionError as FrappePermissionError
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.diakonos import Mitglied
from test_p1_8d_ausschluss_umgehung import _aktiv, _konto, _rollen


def _loeschen(weg: str, name: str, *, verweigert: bool = False) -> None:
    if weg == "resource_delete":
        from diakronos_app.frappe_compat.router import resource_delete

        antwort = asyncio.run(resource_delete("Mitglied", name))
        assert antwort.status_code == (403 if verweigert else 202)
    else:
        from diakronos_app.frappe_compat.api_helpers import _delete_doc

        if verweigert:
            with pytest.raises(FrappePermissionError):
                _delete_doc("Mitglied", name)
        else:
            _delete_doc("Mitglied", name)


@pytest.mark.parametrize("weg", ["resource_delete", "delete_doc"])
@pytest.mark.parametrize("akteur,reserve,verweigert", [
    ("ma@x.org", False, False),
    ("ma@x.org", True, False),
    ("sm2@x.org", True, False),
])
def test_loeschen_prueft_email_nachzustand(
    patched_db, fake_redis, altbestand_dublette, weg, akteur, reserve, verweigert,
):
    """Das Loeschen der Dublette gibt den ausgeschlossenen SM nicht frei.

    Fachentscheidung (Manuel, 2026-10-19): zwei Mitglieder mit derselben
    Adresse sind nur noch als ALTbestand denkbar. Der Ausschluss des einen
    sperrt das Konto der Adresse (fail closed) — das Konto ist also schon VOR
    dem Loeschen gesperrt und bleibt es danach. Entscheidend ist die Zusage:
    durch das Loeschen wird nie ein zuvor gesperrtes Verwaltungskonto frei
    (sonst liesse sich der letzte System Manager aussperren).
    """
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager", mitglied=False)
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    if reserve:
        _konto(sess, "sm2@x.org", "System Manager")
    sess.add_all([
        Mitglied(name="M-excluded", email="sm@x.org", ausgeschlossen=True),
        # Dublette (gleiche Adresse, zweiter Datensatz) — Altbestand.
        Mitglied(name="M-duplicate", email="SM@x.org", ausgeschlossen=False),
    ])
    sess.commit()
    assert _aktiv("sm@x.org") is False
    set_user(akteur)

    _loeschen(weg, "M-duplicate", verweigert=verweigert)

    sess.expire_all()
    assert (sess.get(Mitglied, "M-duplicate") is not None) is verweigert
    # Kernzusage: das ausgeschlossene Verwaltungskonto wird nicht frei.
    assert _aktiv("sm@x.org") is False
    if reserve:
        assert _aktiv("sm2@x.org")


@pytest.mark.parametrize("weg", ["resource_delete", "delete_doc"])
@pytest.mark.parametrize("ausgeschlossen", [False, True])
def test_normales_mitglied_loeschen_bleibt_erlaubt(
    patched_db, fake_redis, weg, ausgeschlossen,
):
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    sess.add(Mitglied(name="M-normal", email="normal@x.org", ausgeschlossen=ausgeschlossen))
    sess.commit()
    set_user("ma@x.org")

    _loeschen(weg, "M-normal")

    sess.expire_all()
    assert sess.get(Mitglied, "M-normal") is None
    assert _aktiv("sm@x.org")
