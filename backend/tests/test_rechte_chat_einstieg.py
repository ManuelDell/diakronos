"""Rechte-Kern: ``darf_chat_irgendwo_moderieren`` — Einstieg „Chat“ (Operator 19.11.2026).

Der Kalender zeigt den Reiter „Chat“ aus ``get_session_info.chat_moderieren``
statt fuer jede Person ``meldungen_liste`` zu fragen (403-Rauschen, Schleife
ueber alle Gespraeche). Das Flag darf NIE etwas anderes sagen als die Liste:
wer es hat, bekommt keine 403 — wer es nicht hat, bekommt 403.
"""

from __future__ import annotations

import pytest

from diakronos_app.models.core import User
from diakronos_app.models.diakonos import Mitglied
from diakronos_app.models.rechte import RechteGruppenrolle, RechteModul
from test_chat6_meldung import (  # noqa: F401 — Fixture-Welt teilen
    ADMIN, FREMD, GL, HV, JUGEND, MV, NOTEN, SAENGER, _set_user, welt,
)

JUGEND_HV = "jugendhv@x.org"


@pytest.fixture()
def mehr(welt):  # noqa: F811
    welt.add(User(name=JUGEND_HV, email=JUGEND_HV, enabled=1, full_name="Jh"))
    welt.add(Mitglied(name="M-Jh", vorname="Jh", nachname="X", email=JUGEND_HV, user=JUGEND_HV))
    welt.add(RechteGruppenrolle(gruppe="Jugend", benutzer=JUGEND_HV, rolle="HV"))
    welt.commit()
    return welt


def _flag(konto):
    from diakronos_app import rechte

    return rechte.darf_chat_irgendwo_moderieren(konto)


def test_wer_den_einstieg_hat(mehr):
    assert _flag(ADMIN)            # Meldestelle
    assert _flag(HV) and _flag(MV)
    assert _flag(GL)               # GL der Untergruppe mit Chat-Modul
    for konto in (SAENGER, NOTEN, FREMD, JUGEND, JUGEND_HV, "Guest", None, ""):
        assert not _flag(konto), konto   # JUGEND_HV: Gruppe ohne Chat-Modul


def test_modul_aus_nimmt_den_einstieg(mehr):
    from diakronos_app import rechte

    mehr.query(RechteModul).filter_by(gruppe="Chor", modul="chat").delete()
    mehr.commit()
    rechte.merker_leeren()
    assert not _flag(HV) and not _flag(GL)
    assert _flag(ADMIN)


def test_flag_stimmt_mit_der_liste_ueberein(mehr):
    """Kein zweiter Weg: Flag ja ⇔ ``meldungen_liste`` ohne 403."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    _set_user(SAENGER)
    C.gespraech_anlegen("Chor")
    _set_user(NOTEN)
    C.gespraech_anlegen("Chor", "UG-Noten")
    for konto in (ADMIN, HV, MV, GL, SAENGER, NOTEN, FREMD, JUGEND, JUGEND_HV):
        _set_user(konto)
        try:
            C.meldungen_liste()
            liste = True
        except PermissionError:
            liste = False
        assert _flag(konto) is liste, konto


def test_session_info_traegt_das_flag(mehr):
    from diakronos_app.api.kronos import permissions as P

    _set_user(HV)
    assert P.get_session_info()["chat_moderieren"] is True
    _set_user(SAENGER)
    assert P.get_session_info()["chat_moderieren"] is False


def test_boot_traegt_dasselbe_flag(mehr):
    """Boot-Objekt und get_session_info sagen dasselbe (eine Kernfrage)."""
    from diakronos_app import spa

    assert spa._chat_moderieren(HV) is True
    assert spa._chat_moderieren(SAENGER) is False
    assert spa._chat_moderieren(ADMIN) is True
