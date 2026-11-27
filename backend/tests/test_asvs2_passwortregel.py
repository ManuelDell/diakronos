"""ASVS2-2: Die EINE Passwortregel lehnt haeufige und triviale Passwoerter ab.

ASVS 5: mindestens 8 Zeichen und Abgleich mit einer Liste haeufiger
Passwoerter (mindestens die 3000 haeufigsten). Die Liste liegt im Paket
(anmeldung/daten/haeufige_passwoerter.txt, SecLists, MIT).
"""
from __future__ import annotations

import pytest

from diakronos_app.anmeldung.passwortzugang import haeufige_passwoerter, pruefe_passwort
from diakronos_app.frappe_compat.exceptions import ValidationError


def test_liste_ist_im_paket_und_gross_genug() -> None:
    liste = haeufige_passwoerter()
    assert len(liste) >= 2000
    assert all(len(p) >= 8 for p in liste)
    assert "password" in liste and "passwort123" in liste


@pytest.mark.parametrize("pw", ["password", "Password", "PASSWORT123", "qwertyuiop", "12345678",
                                "iloveyou", "hallo1234", "gemeinde123"])
def test_haeufige_passwoerter_abgelehnt(pw) -> None:
    with pytest.raises(ValidationError, match="haeufigsten"):
        pruefe_passwort(pw)


@pytest.mark.parametrize("pw", ["aaaaaaaa", "11111111111", "        "])
def test_ein_wiederholtes_zeichen_abgelehnt(pw) -> None:
    with pytest.raises(ValidationError):
        pruefe_passwort(pw)


def test_anmeldename_oder_email_abgelehnt() -> None:
    with pytest.raises(ValidationError, match="Anmeldename"):
        pruefe_passwort("lena.leser@x.org", benutzer="lena.leser@x.org")
    with pytest.raises(ValidationError, match="Anmeldename"):
        pruefe_passwort("Lena.Leser", benutzer="lena.leser@x.org")


@pytest.mark.parametrize("pw", ["Kirchturm-Glocke-7", "musterhausen-demo", "x9!Fv#2qLm"])
def test_ordentliche_passwoerter_gehen_durch(pw) -> None:
    pruefe_passwort(pw, benutzer="lena.leser@x.org")


def test_laengen_grenzen_bleiben() -> None:
    with pytest.raises(ValidationError, match="zwischen 8 und 1024"):
        pruefe_passwort("kurz7!a")
    with pytest.raises(ValidationError, match="zwischen 8 und 1024"):
        pruefe_passwort("x" * 1025)
