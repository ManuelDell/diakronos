"""N5: Einmalige Passwort-Links und verpflichtender Wechsel ohne Vollsitzung."""
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture()
def konto(patched_db):
    from diakronos_app.models.core import User
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    with patched_db() as sess:
        sess.add(User(name="neu@example.org", email="neu@example.org", enabled=True,
                      password_hash=neuer_hash("Startpasswort-123")))
        sess.commit()
    return "neu@example.org"


def test_einladung_einmalig_und_nur_hash(konto, patched_db):
    from diakronos_app.anmeldung import passwortzugang as p
    from diakronos_app.models.passwortzugang import Passwortzugang
    from diakronos_app.models.core import User
    from diakronos_app.frappe_compat.passwoerter import pruefe
    link = p.link_erzeugen(konto)
    kennung = link["link"].split("#token=")[1]
    with patched_db() as sess:
        row = sess.get(Passwortzugang, konto)
        assert row.token_hash and kennung not in row.token_hash
        rest = row.gueltig_bis - datetime.now(timezone.utc).replace(tzinfo=None)
        assert timedelta(days=7, seconds=-5) < rest <= timedelta(days=7)
    p.passwort_uebernehmen(kennung, "NeuesPasswort-123")
    with patched_db() as sess:
        assert pruefe("NeuesPasswort-123", sess.get(User, konto).password_hash)
    with pytest.raises(Exception, match="gültig"):
        p.passwort_uebernehmen(kennung, "NochEinPasswort-123")


def test_neuer_link_entwertet_alten_und_abgelaufene_links(konto, patched_db):
    from diakronos_app.anmeldung import passwortzugang as p
    from diakronos_app.models.passwortzugang import Passwortzugang
    alt = p.link_erzeugen(konto)["link"].split("#token=")[1]
    neu = p.link_erzeugen(konto)["link"].split("#token=")[1]
    with pytest.raises(Exception, match="gültig"):
        p.passwort_uebernehmen(alt, "NeuesPasswort-123")
    with patched_db() as sess:
        sess.get(Passwortzugang, konto).gueltig_bis = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        sess.commit()
    with pytest.raises(Exception, match="gültig"):
        p.passwort_uebernehmen(neu, "NeuesPasswort-123")


def test_startpasswort_erzwingt_wechsel_ohne_sid(client, konto, patched_db, set_user):
    from diakronos_app.anmeldung import passwortzugang as p
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.frappe_compat.session import testnaht_aus
    from diakronos_app.caldav.auth import _check_credentials
    with patched_db() as sess:
        p.startpasswort_markieren(sess, konto)
        sess.commit()
    assert p.wechsel_noetig(konto)
    assert not _check_credentials(konto, "Startpasswort-123")
    with testnaht_aus():
        antwort = client.post("/api/method/login", json={"usr": konto, "pwd": "Startpasswort-123"})
    assert antwort.status_code == 200, antwort.text
    assert "sid=" not in antwort.headers.get("set-cookie", "")
    assert antwort.json()["passwortwechsel"] is True
    kennung = antwort.json()["redirect_to"].split("#token=")[1]
    with pytest.raises(Exception, match="unterscheiden"):
        p.passwort_uebernehmen(kennung, "Startpasswort-123")
    p.passwort_uebernehmen(kennung, "NeuesPasswort-123")
    assert not p.wechsel_noetig(konto)
    with testnaht_aus():
        antwort = client.post("/api/method/login", json={"usr": konto, "pwd": "NeuesPasswort-123"})
    assert antwort.status_code == 200, antwort.text
    assert "sid=" in antwort.headers.get("set-cookie", "")


def test_gesperrtes_konto_kann_token_nicht_nutzen(konto, patched_db):
    from diakronos_app.anmeldung import passwortzugang as p
    from diakronos_app.models.core import User
    kennung = p.link_erzeugen(konto)["link"].split("#token=")[1]
    with patched_db() as sess:
        sess.get(User, konto).enabled = False
        sess.commit()
    with pytest.raises(Exception, match="gültig"):
        p.passwort_uebernehmen(kennung, "NeuesPasswort-123")


def test_oeffentlicher_weg_nur_post(client, konto):
    from diakronos_app.anmeldung import passwortzugang as p
    kennung = p.link_erzeugen(konto)["link"].split("#token=")[1]
    r = client.get("/api/method/zugang.passwort_uebernehmen", params={"kennung": kennung, "passwort": "NeuesPasswort-123"})
    assert r.status_code >= 400, r.text
    r = client.get("/diakonos/passwort-setzen")
    assert r.status_code == 200, r.text
    assert 'no-store' in r.headers['cache-control']
    assert r.headers['referrer-policy'] == 'no-referrer'
    assert 'Passwort setzen' in r.text


@pytest.fixture()
def admin(patched_db, set_user):
    from diakronos_app.models.core import User, HasRole
    with patched_db() as sess:
        sess.add(User(name="n5-admin", enabled=True))
        sess.add(HasRole(name="N5-admin-rolle", parent="n5-admin", parenttype="User",
                         parentfield="roles", role="Mitgliederadministrator", idx=1))
        sess.commit()
    set_user("n5-admin")


@pytest.mark.parametrize("art", ["link", "startpasswort", "kein"])
def test_anlegen_mit_zugangsart(client, admin, patched_db, art):
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.models.core import User
    from diakronos_app.anmeldung.passwortzugang import wechsel_noetig
    r = client.post('/api/method/mitglieder.create_mitglied', json={
        'vorname': 'Neue', 'nachname': 'Person', 'email': 'person@example.org',
        'zugangsart': art, 'startpasswort': 'Startpasswort-123',
    })
    assert r.status_code == 200, r.text
    daten = r.json()['message']
    assert not daten['warnungen'], daten
    with patched_db() as sess:
        mitglied = sess.get(Mitglied, daten['mitglied_id'])
        assert bool(mitglied.user) == (art != 'kein')
        assert bool(sess.get(User, 'person@example.org')) == (art != 'kein')
    if art == 'link':
        assert '#token=' in daten['zugang']['link']
    if art == 'startpasswort':
        assert wechsel_noetig('person@example.org')


def test_oidc_nur_eintrag_und_keine_passwort_wege(client, admin, patched_db, monkeypatch):
    from diakronos_app.anmeldung import konfiguration
    from diakronos_app.models.core import User
    monkeypatch.setattr(konfiguration, 'oidc_aktiv', lambda: True)
    for art in ['link', 'startpasswort']:
        r = client.post('/api/method/mitglieder.create_mitglied', json={
            'vorname': 'SSO', 'nachname': 'Person', 'email': 'sso@example.org',
            'zugangsart': art, 'startpasswort': 'Startpasswort-123',
        })
        assert r.status_code == 417, r.text
    r = client.post('/api/method/mitglieder.create_mitglied', json={
        'vorname': 'SSO', 'nachname': 'Person', 'email': 'sso@example.org', 'zugangsart': 'kein',
    })
    assert r.status_code == 200, r.text
    mid = r.json()['message']['mitglied_id']
    r = client.post('/api/method/zugang.einladungslink', json={'mitglied_id': mid})
    assert r.status_code == 417, r.text
    with patched_db() as sess:
        assert sess.get(User, 'sso@example.org') is None


def test_einladung_keine_uebernahme_von_verwaltungskonto(client, admin, konto, patched_db):
    from diakronos_app.models.core import HasRole
    from diakronos_app.models.diakonos import Mitglied
    with patched_db() as sess:
        sess.add(Mitglied(name='N5-Ziel', vorname='Admin', nachname='Ziel', user=konto,
                          email=konto, status='Mitglied', docstatus=0, idx=0))
        sess.add(HasRole(name='N5-Zielrolle', parent=konto, parenttype='User',
                         parentfield='roles', role='System Manager', idx=1))
        sess.commit()
    r = client.post('/api/method/zugang.einladungslink', json={'mitglied_id': 'N5-Ziel'})
    assert r.status_code == 403, r.text


def test_erstwechsel_entwertet_auch_eine_alte_sid(client, konto, patched_db):
    from diakronos_app.anmeldung.passwortzugang import startpasswort_markieren
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.frappe_compat.session import testnaht_aus
    sid, _ = sitzungen.anlegen(konto)
    with patched_db() as sess:
        startpasswort_markieren(sess, konto)
        sess.commit()
    client.cookies.set('sid', sid)
    with testnaht_aus():
        r = client.get('/api/method/session.get_current_user_context')
    # P2-1 (OP-UI-1): Eine entwertete Sitzung ist „nicht angemeldet" -> 401
    # SessionExpired (frueher 403). Die eigentliche Aussage bleibt: die alte
    # Kennung ist tatsaechlich geloescht.
    assert r.status_code == 401, r.text
    assert r.json()['exc_type'] == 'SessionExpired'
    assert sitzungen.lesen(sid) is None


def test_gepruefte_sso_sitzung_bleibt_trotz_lokalem_erstwechsel_erlaubt(client, konto, patched_db):
    from starlette.requests import Request
    from diakronos_app.anmeldung.passwortzugang import startpasswort_markieren
    from diakronos_app.anmeldung.routen import _neue_sitzung_nach_login
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.frappe_compat.session import testnaht_aus
    with patched_db() as sess:
        startpasswort_markieren(sess, konto)
        sess.commit()
    sid, _ = _neue_sitzung_nach_login(Request({'type': 'http', 'headers': []}), konto)
    client.cookies.set('sid', sid)
    with testnaht_aus():
        r = client.get('/api/method/session.get_current_user_context')
    assert r.status_code == 200, r.text
    assert sitzungen.lesen(sid)['sso'] is True
    # Die Herkunft ist ausschließlich serverseitig gesetzt. Ein lokaler
    # Aufrufer kann die Schranke nicht durch ein frei gesetztes sso umgehen.
    client.cookies.clear()
    with testnaht_aus():
        r = client.post('/api/method/login', json={'usr': konto, 'pwd': 'Startpasswort-123', 'sso': True})
    assert r.status_code == 200 and r.json()['passwortwechsel'] is True, r.text
    assert 'sid=' not in r.headers.get('set-cookie', '')
