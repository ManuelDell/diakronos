"""B2: Verwaltungswerte und Schreib-Antworten dürfen nicht durchrutschen."""
import json

import pytest

from tests.test_b2_adressbuch_sichtbarkeit import (
    SICHTBAR, _detail, _set_user, _sichtbarkeit_setzen, sess, _verantwortlichen_zeile,
)
from tests.test_permissions import hierarchie


def test_dsgvo_ist_unbekannt_statt_falsch(client, hierarchie):
    _set_user("mitglied-a@example.org")
    assert all(v is None for v in _detail(client, SICHTBAR)["dsgvo"].values())


def test_verantwortlicher_account_verraet_keine_email(hierarchie, sess):
    from diakronos_app.api.gruppen import get_gruppe_detail
    user = "zz-b-leiter@example.invalid"
    mid = _verantwortlichen_zeile(sess, user)
    _sichtbarkeit_setzen(sess, mid, email=False)
    _set_user("mitglied-a@example.org")
    assert user not in json.dumps(get_gruppe_detail("G-A1"))


@pytest.mark.parametrize("wert", ["false", "true", 1, [], None])
def test_profile_schreiben_keine_implizite_freigabe(hierarchie, sess, wert):
    from diakronos_app.api.profile import update_adressbuch_sichtbarkeit
    from diakronos_app.models.diakonos import Mitglied
    _set_user("mitglied-a@example.org")
    update_adressbuch_sichtbarkeit({"email": wert})
    sess.expire_all()
    assert json.loads(sess.get(Mitglied, "M-gruppe-a1").adressbuch_sichtbarkeit)["email"] is False


def test_profil_defaults_entsprechen_serverregel():
    from diakronos_app.api.profile import _sichtbarkeit_lesen
    assert _sichtbarkeit_lesen(None) == dict.fromkeys(
        ["email", "telefonnummer", "adresse", "geburtstag"], False)


@pytest.mark.parametrize("method", ["post", "put"])
def test_resource_schreibantworten_verweigert(client, hierarchie, method):
    _set_user("mitglied-a@example.org")
    url = "/api/resource/Mitglied" + (f"/{SICHTBAR}" if method == "put" else "")
    assert getattr(client, method)(url, json={}).status_code == 403


def test_resource_einwilligung_detail_verweigert(client, hierarchie):
    _set_user("mitglied-a@example.org")
    assert client.get("/api/resource/DSGVO%20Einwilligung/zz-b-nicht-da").status_code == 403
