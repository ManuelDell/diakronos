"""ASVS2-3: Angemeldete Nutzer koennen ihr EIGENES Passwort aendern.

Verlangt das aktuelle Passwort, prueft das neue mit der einen Passwortregel,
begrenzt Versuche je Konto und beendet danach alle Sitzungen des Kontos.
"""
from __future__ import annotations

import pytest

KONTO = "lena@example.org"
ALT = "Kirchturm-Glocke-7"
NEU = "Orgelpfeife-Sonntag-9"


@pytest.fixture()
def konto(patched_db, monkeypatch):
    from diakronos_app.frappe_compat import benutzer_status
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.frappe_compat.session import set_user
    from diakronos_app.models.core import User

    with patched_db() as sess:
        sess.add(User(name=KONTO, email=KONTO, enabled=True, password_hash=neuer_hash(ALT)))
        sess.commit()
    from diakronos_app.frappe_compat import loginversuche

    # Das Versuchsbudget lebt im (Test-)Redis und wuerde sonst von Test zu Test
    # weiterzaehlen.
    loginversuche._client().delete(loginversuche._limit_key("passwort_aendern", KONTO))
    widerrufen: list[str] = []
    monkeypatch.setattr(benutzer_status, "widerrufe_sitzungen", lambda u: widerrufen.append(u) or 1)
    set_user(KONTO)
    return widerrufen


def _hash(patched_db):
    from diakronos_app.models.core import User

    with patched_db() as sess:
        return sess.get(User, KONTO).password_hash


def test_aendern_mit_richtigem_aktuellen_passwort(konto, patched_db) -> None:
    from diakronos_app.api.profile import passwort_aendern
    from diakronos_app.frappe_compat.passwoerter import pruefe

    antwort = passwort_aendern(aktuelles_passwort=ALT, neues_passwort=NEU)
    assert antwort == {"success": True, "neu_anmelden": True}
    assert pruefe(NEU, _hash(patched_db)) and not pruefe(ALT, _hash(patched_db))
    assert konto == [KONTO], "alle Sitzungen des Kontos werden beendet"


def test_falsches_aktuelles_passwort_aendert_nichts(konto, patched_db) -> None:
    from diakronos_app.api.profile import passwort_aendern

    vorher = _hash(patched_db)
    with pytest.raises(Exception, match="aktuelle Passwort stimmt nicht"):
        passwort_aendern(aktuelles_passwort="falsch-falsch-1", neues_passwort=NEU)
    assert _hash(patched_db) == vorher and konto == []


@pytest.mark.parametrize("neu, grund", [
    ("password123", "haeufigsten"), ("kurz", "zwischen 8"), (ALT, "unterscheiden"),
    (KONTO, "Anmeldename"),
])
def test_neues_passwort_muss_der_regel_folgen(konto, patched_db, neu, grund) -> None:
    from diakronos_app.api.profile import passwort_aendern

    vorher = _hash(patched_db)
    with pytest.raises(Exception, match=grund):
        passwort_aendern(aktuelles_passwort=ALT, neues_passwort=neu)
    assert _hash(patched_db) == vorher


def test_hoechstens_fuenf_versuche_je_konto(konto, patched_db) -> None:
    from diakronos_app.api.profile import PASSWORT_AENDERN_MAX, passwort_aendern

    for _ in range(PASSWORT_AENDERN_MAX):
        with pytest.raises(Exception, match="stimmt nicht"):
            passwort_aendern(aktuelles_passwort="falsch-falsch-1", neues_passwort=NEU)
    # Auch mit dem RICHTIGEN Passwort ist jetzt Schluss — das Budget zaehlt Versuche.
    with pytest.raises(Exception, match="Zu viele Versuche"):
        passwort_aendern(aktuelles_passwort=ALT, neues_passwort=NEU)


def test_bei_oidc_kein_lokales_passwort(konto, patched_db, monkeypatch) -> None:
    from diakronos_app.anmeldung import konfiguration
    from diakronos_app.api.profile import passwort_aendern

    monkeypatch.setattr(konfiguration, "oidc_aktiv", lambda: True)
    with pytest.raises(Exception, match="Authentik"):
        passwort_aendern(aktuelles_passwort=ALT, neues_passwort=NEU)


def test_gast_darf_nicht(patched_db) -> None:
    from diakronos_app.api.profile import passwort_aendern
    from diakronos_app.frappe_compat.session import set_user

    set_user("Guest")
    with pytest.raises(Exception):
        passwort_aendern(aktuelles_passwort=ALT, neues_passwort=NEU)


def test_methode_ist_unter_dem_profilpfad_erreichbar_und_nur_post() -> None:
    """Die Oberflaeche ruft `diakronos.diakonos.api.profile.passwort_aendern` (wie die
    uebrigen Profil-Aufrufe) — der Pfad muss aufloesen, nur per POST."""
    import diakronos_app.api  # noqa: F401 — Registrierung
    from diakronos_app.frappe_compat.registry import lookup, methoden_fuer

    fn = lookup("diakronos.diakonos.api.profile.passwort_aendern")
    assert fn is not None and fn.__name__ == "passwort_aendern"
    assert methoden_fuer(fn) == ("POST",)


def test_anmeldemaske_kennt_den_grund_passwort() -> None:
    from diakronos_app.anmeldung.routen import grund_hinweis

    assert "neuen Passwort" in grund_hinweis("passwort")
