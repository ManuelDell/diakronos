"""B2: zusätzliche Auslieferungs- und Seitenkanal-Regressionsfälle."""
import json

import pytest

from tests.test_b2_adressbuch_sichtbarkeit import (
    SICHTBAR, _pfd_daten, _set_user, _sichtbarkeit_setzen, sess,
)
from tests.test_permissions import hierarchie


@pytest.mark.parametrize("doctype", ["Mitglied", "DSGVO Einwilligung"])
@pytest.mark.parametrize("params", [
    {}, {"fields": '["*"]'}, {"pluck": "email"}, {"as_list": "1"},
    {"filters": '{"telefonnummer": ["like", "%123%"]}'},
    {"or_filters": '{"email": ["like", "%secret%"]}'},
])
def test_resource_liste_fuer_normale_nutzer_verweigert(client, hierarchie, doctype, params):
    _set_user("mitglied-a@example.org")
    r = client.get(f"/api/resource/{doctype}", params=params)
    assert r.status_code == 403


def test_resource_detail_maskiert(client, hierarchie, sess):
    _pfd_daten(sess)
    _sichtbarkeit_setzen(sess, SICHTBAR, email=False, telefonnummer=False,
                         adresse=False, geburtstag=False)
    _set_user("mitglied-a@example.org")
    r = client.get(f"/api/resource/Mitglied/{SICHTBAR}")
    assert r.status_code == 200
    data = r.json()["data"]
    for field in ["email", "telefonnummer", "geburtstag", "wohnort", "postleitzahl"]:
        assert data[field] is None
    assert "notiz" not in data
    assert "datenschutz_einwilligung" not in data


def test_resource_detail_fremder_bereich_verweigert(client, hierarchie):
    _set_user("mitglied-a@example.org")
    assert client.get("/api/resource/Mitglied/M-gruppe-b1").status_code == 403


@pytest.mark.parametrize("field", ["email", "geburtstag", "wohnort", "postleitzahl"])
def test_sortierung_nach_privaten_feldern_verweigert(client, hierarchie, field):
    _set_user("mitglied-a@example.org")
    r = client.get("/api/method/mitglieder.get_mitglieder_liste", params={"sort_by": field})
    assert r.status_code == 403


def test_teilfreigabe_oeffnet_nicht_die_anderen_felder():
    from diakronos_app.frappe_compat.mitglied_sichtbarkeit import sichtbarkeit_lesen
    assert sichtbarkeit_lesen('{"email": true}') == {
        "email": True, "telefonnummer": False, "adresse": False, "geburtstag": False,
    }
