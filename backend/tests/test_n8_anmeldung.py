"""N8: eine atomare Login-Einstellung, nur Admins, kein stiller Teilstand."""
import pytest

API = '/api/method/diakronos.anmeldung.'


def test_einstellungen_atomare_uebernahme(client, patched_db):
    from diakronos_app.models.auth_oidc import Anmeldeeinstellungen, ANMELDEEINSTELLUNGEN_NAME
    from diakronos_app.models.core import HasRole
    # N9b/R-N8-3: den Modus „unbekannte Nutzer anlegen“ darf nur ein System
    # Manager speichern. Der Test-Administrator bekommt dazu die Rolle
    # ausdruecklich (die Rolle, nicht der Administrator-Sonderfall, ist hier
    # die Schranke).
    with patched_db() as sess:
        sess.add(HasRole(name='n8-sysadmin-rolle', parent='Administrator',
                         parenttype='User', parentfield='roles', idx=1,
                         role='System Manager'))
        sess.commit()
    daten = {'modus': 'anlegen_mit_rollen', 'admin_ueber_gruppen': False,
             'zuordnungen': [{'gruppe': 'musik-leitung', 'rolle': 'Kalenderadministrator'}]}
    r = client.post(API + 'anmeldung_speichern', json=daten)
    assert r.status_code == 200, r.text
    vorher = client.post(API + 'anmeldung_get_einstellungen').json()['message']
    daten['modus'] = 'als_gast_anlegen'
    daten['zuordnungen'][0]['rolle'] = ''
    r = client.post(API + 'anmeldung_speichern', json=daten)
    assert r.status_code == 417, r.text
    nachher = client.post(API + 'anmeldung_get_einstellungen').json()['message']
    assert nachher == vorher
    with patched_db() as sess:
        assert sess.get(Anmeldeeinstellungen, ANMELDEEINSTELLUNGEN_NAME).unbekannte_nutzer == 'anlegen_mit_rollen'


@pytest.mark.parametrize('zuordnungen', [
    [{'gruppe': 'musik', 'rolle': 'Fantasierolle'}],
    [{'gruppe': '', 'rolle': 'Mitglied'}],
    [{'gruppe': 'musik', 'rolle': 'Mitglied'}, {'gruppe': 'musik', 'rolle': 'Mitglied'}],
    {'gruppe': 'musik', 'rolle': 'Mitglied'},
])
def test_ungueltige_zuordnung_bleibt_ohne_nebenwirkung(client, zuordnungen):
    vorher = client.post(API + 'anmeldung_get_einstellungen').json()['message']
    r = client.post(API + 'anmeldung_speichern', json={
        'modus': 'als_gast_anlegen', 'zuordnungen': zuordnungen})
    assert r.status_code == 417, r.text
    assert client.post(API + 'anmeldung_get_einstellungen').json()['message'] == vorher


def test_speichern_nur_post_und_admin(client, set_user):
    assert client.get(API + 'anmeldung_speichern', params={'modus': 'abweisen'}).status_code >= 400
    set_user('Guest')
    # Seit P2-1: Gaeste bekommen 401 SessionExpired statt 403 (Vertragswechsel).
    for r in (client.post(API + 'anmeldung_speichern', json={'modus': 'abweisen'}),
              client.post('/api/method/zugang.get_wartende_konten')):
        assert r.status_code == 401 and r.json().get('exc_type') == 'SessionExpired', r.text


def test_system_manager_gruppen_nicht_durch_mitgliederadmin(client, set_user, patched_db):
    from diakronos_app.models.core import User, HasRole
    with patched_db() as sess:
        sess.add(User(name='n8-admin', enabled=True))
        sess.add(HasRole(name='n8-rolle', parent='n8-admin', parenttype='User',
                         parentfield='roles', role='Mitgliederadministrator', idx=1))
        sess.commit()
    set_user('n8-admin')
    r = client.post(API + 'anmeldung_speichern', json={
        'modus': 'anlegen_mit_rollen', 'admin_ueber_gruppen': True,
        'zuordnungen': [{'gruppe': 'leitung', 'rolle': 'System Manager'}]})
    assert r.status_code == 403, r.text


def test_passwort_uebernehmen_bremse_vor_teurer_arbeit(client, monkeypatch):
    from diakronos_app.anmeldung import passwortzugang
    from diakronos_app.frappe_compat import loginversuche
    aufrufe = []
    monkeypatch.setattr(loginversuche, 'pruefe_und_merke', lambda *a, **kw: (False, 'ip'))
    monkeypatch.setattr(passwortzugang, 'passwort_uebernehmen', lambda *a: aufrufe.append(a))
    r = client.post('/api/method/zugang.passwort_uebernehmen', json={'token': 'x' * 43, 'passwort': 'lang-genug-123'})
    assert r.status_code == 429, r.text
    assert not aufrufe


def test_sitzung_prueft_erstwechsel_nur_einmal_je_kurzem_cache(client, patched_db, monkeypatch):
    from diakronos_app.anmeldung import passwortzugang as p
    from diakronos_app.frappe_compat import sitzungen, benutzer_status
    from diakronos_app.frappe_compat.session import testnaht_aus
    aufrufe = []
    echt = p.wechsel_noetig
    monkeypatch.setattr(p, 'wechsel_noetig', lambda user: (aufrufe.append(user), echt(user))[1])
    benutzer_status.vergiss('Administrator')
    sid, _ = sitzungen.anlegen('Administrator')
    client.cookies.set('sid', sid)
    with testnaht_aus():
        for _ in range(3):
            assert client.get('/api/method/session.get_current_user_context').status_code == 200
    assert len(aufrufe) <= 1


def test_sso_mitglied_zuordnung_nur_verifiziert(patched_db, fake_redis):
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.models.auth_oidc import Anmeldeeinstellungen, ANMELDEEINSTELLUNGEN_NAME
    from diakronos_app.anmeldung.zuordnung import ExternesKonto, loese_konto_auf
    with patched_db() as sess:
        sess.add(Mitglied(name='N8-Person', vorname='N8', nachname='Person', email='person@example.org', status='Mitglied'))
        sess.add(Anmeldeeinstellungen(name=ANMELDEEINSTELLUNGEN_NAME,
                                     unbekannte_nutzer='anlegen_mit_rollen', admin_ueber_gruppen=False))
        sess.commit()
    with patched_db() as sess:
        result = loese_konto_auf(sess, ExternesKonto(issuer='https://sso.example.org', sub='unverified',
                               email='person@example.org', email_verified=False))
        sess.commit()
        assert sess.get(Mitglied, 'N8-Person').user is None
    with patched_db() as sess:
        result = loese_konto_auf(sess, ExternesKonto(issuer='https://sso.example.org', sub='verified',
                               email='person@example.org', email_verified=True))
        sess.commit()
        assert result.erlaubt
        assert sess.get(Mitglied, 'N8-Person').user == result.user


@pytest.mark.parametrize('verified', [False, None, 'true', 1, True])
def test_oidc_claim_nur_echtes_true(verified):
    from diakronos_app.anmeldung.routen import _konto_aus_claims
    k = _konto_aus_claims('https://sso.example.org', {'sub': 'a', 'email_verified': verified})
    assert k.email_verified is (verified is True)


@pytest.mark.parametrize('fall', ['bekannt', 'ausgeschlossen', 'anderes_konto'])
def test_mitglied_ohne_konto_im_sicheren_default(patched_db, fake_redis, fall):
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.models.core import User
    from diakronos_app.anmeldung.zuordnung import ExternesKonto, loese_konto_auf
    with patched_db() as sess:
        if fall == 'anderes_konto':
            sess.add(User(name='anderes', enabled=True))
            sess.flush()
        sess.add(Mitglied(name='N8-Bekannt', vorname='Bekannte', nachname='Person',
            email='bekannt@example.org', status='Mitglied', ausgeschlossen=fall == 'ausgeschlossen',
            user='anderes' if fall == 'anderes_konto' else None))
        sess.commit()
    with patched_db() as sess:
        r = loese_konto_auf(sess, ExternesKonto(issuer='https://sso.example.org', sub='b',
            email='bekannt@example.org', email_verified=True))
        if fall == 'bekannt':
            assert r.erlaubt
            sess.commit()
            assert sess.get(Mitglied, 'N8-Bekannt').user == r.user
        else:
            assert not r.erlaubt
            sess.rollback()
            assert sess.get(User, 'bekannt@example.org') is None


def test_zweites_mitglied_mit_derselben_adresse_gibt_es_nicht(patched_db, engine):
    """SEC-b: Der frueher hier gepruefte Fall „doppelt“ ist nicht mehr moeglich.

    Fachentscheidung (Manuel 2026-10-19): Jede Person hat eine eigene
    E-Mail-Adresse. Die Zuordnung ueber die E-Mail kann daher keinen
    „ersten Treffer“ mehr waehlen — der partielle Unique-Index
    `uq_mitglied_email_normalisiert` verweigert das zweite Mitglied schon
    beim Schreiben.

    Geprueft wird bewusst ueber direkten SQL-Weg: der SQLAlchemy-ORM legt
    Einfuegungen in SQLite als Mehrfach-Statement an, das den Ausdrucksindex
    nicht auswertet. PostgreSQL — der Betriebsfall — prueft ihn sehr wohl
    (Beleg im Abschlusskommentar der Karte); hier wird die Indexdefinition
    selbst gepruefet.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from diakronos_app.models.diakonos import Mitglied
    with patched_db() as sess:
        sess.add(Mitglied(name='N8-Erste', vorname='Erste', nachname='Person',
                          email='bekannt@example.org', status='Mitglied'))
        sess.commit()
    # Ein zweiter Datensatz mit derselben Adresse (andere Schreibweise) wird
    # vom Index abgewiesen.
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text(
                "insert into mitglied (name, email) values ('N8-Doppelt', '  BExANNT@example.org ')"
            ))


def test_wartendes_oidc_konto_freischalten_und_ablehnen(client, patched_db):
    from diakronos_app.models.core import User, HasRole
    from diakronos_app.models.auth_oidc import OidcIdentitaet
    with patched_db() as sess:
        sess.add(HasRole(name='n8-system', parent='Administrator', parenttype='User',
                         parentfield='roles', role='System Manager', idx=1))
        sess.add(User(name='n8-wartend', email='wartend@example.org', enabled=False))
        sess.flush()
        sess.add(OidcIdentitaet(issuer='https://sso.example.org', sub='wartend', user='n8-wartend'))
        sess.commit()
    antwort = client.post('/api/method/zugang.get_wartende_konten')
    assert antwort.status_code == 200, antwort.text
    liste = antwort.json()['message']['konten']
    assert any(k['user'] == 'n8-wartend' and k['mitglied'] is None for k in liste)
    for freischalten in [False, True]:
        r = client.post('/api/method/zugang.konto_freischalten', json={'user': 'n8-wartend', 'freischalten': freischalten})
        assert r.status_code == 200, r.text
        with patched_db() as sess:
            assert sess.get(User, 'n8-wartend').enabled is freischalten


def test_erstwechselcache_widerruf_und_fail_closed(client, patched_db, fake_redis, monkeypatch):
    from diakronos_app.anmeldung import passwortzugang as p
    from diakronos_app.frappe_compat import benutzer_status
    assert p.wechsel_noetig_gecacht('Administrator') is False
    with patched_db() as sess:
        p.startpasswort_markieren(sess, 'Administrator')
        sess.commit()
    benutzer_status.vergiss('Administrator')
    assert p.wechsel_noetig_gecacht('Administrator') is True
    monkeypatch.setattr(benutzer_status, '_client', lambda: (_ for _ in ()).throw(RuntimeError('offline')))
    assert p.wechsel_noetig_gecacht('Administrator') is True


def test_passwortbremse_zaehlt_auch_wechselnde_tokens(client, monkeypatch):
    from diakronos_app.anmeldung import passwortzugang
    from diakronos_app.settings import settings
    import diakronos_app.request_context as kontext
    monkeypatch.setattr(settings, 'login_max_versuche_ip', 2)
    monkeypatch.setattr(kontext, 'zaehler_client_ip', lambda: '203.0.113.42')
    monkeypatch.setattr(passwortzugang, 'passwort_uebernehmen', lambda *a: {'success': True})
    codes = [client.post('/api/method/zugang.passwort_uebernehmen', json={
        'token': str(i) * 43, 'passwort': 'lang-genug-123'}).status_code for i in range(3)]
    assert codes == [200, 200, 429]
