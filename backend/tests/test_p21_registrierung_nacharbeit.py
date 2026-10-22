"""P0-4b K1/K3/K4: Token-API, alte NULL-Zähler, Anmeldung ohne JavaScript."""
from diakronos_app.frappe_compat.session import set_user


def test_token_api_bremst_vor_db(client, monkeypatch):
    from diakronos_app.anmeldung import registrierungsbremse
    monkeypatch.setattr(registrierungsbremse, 'zaehle_validierung', lambda ip: False)
    set_user('Guest')
    r = client.post('/api/method/diakronos.diakonos.api.registrierung.validate_token', json={'token':'ungueltig'})
    assert r.status_code == 417, r.text
    assert 'viele' in r.json()['message']


def test_null_zaehler_wird_bei_begrenztem_link_reserviert(patched_db):
    from sqlalchemy import text
    from diakronos_app.models.diakonos import Registrierungslink
    from diakronos_app.api.registrierung import _inkrementiere_zaehler
    with patched_db.begin() as s:
        s.add(Registrierungslink(name='p21-link', max_anmeldungen=1))
        s.flush()
        s.execute(text("UPDATE registrierungslink SET anmeldungen_count=NULL WHERE name='p21-link'"))
    assert _inkrementiere_zaehler('p21-link', 1) is True
    assert _inkrementiere_zaehler('p21-link', 1) is False
    with patched_db() as s:
        assert s.get(Registrierungslink, 'p21-link').anmeldungen_count == 1


def test_anmeldebruecke_hat_sicheren_noscript_link():
    from diakronos_app.anmeldung.routen import _hash_bruecke_seite
    html = _hash_bruecke_seite('/diakonos?x=1&y=2')
    assert '<noscript>' in html
    assert 'href="/login?sso=1&amp;redirect-to=%2Fdiakonos%3Fx%3D1%26y%3D2"' in html
