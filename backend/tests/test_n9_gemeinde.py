"""N9: Gemeinde-, Modul- und Datenschutz-Einstellungen — nur Admin, atomar."""
import pytest

API = '/api/method/gemeinde.'


def test_gemeinde_lesen_legt_sichere_voreinstellung_an(client, patched_db):
    d = client.post(API + 'gemeinde_get_einstellungen').json()['message']
    assert d['gemeindename'] == ''
    assert d['kontakt_email'] == ''
    assert d['oeffentliche_adresse'] == ''
    assert d['link_laufzeit_tage'] == 30
    assert d['link_max_anmeldungen'] == 0
    assert {m['schluessel'] for m in d['module']} == {
        'diakronos', 'kronos', 'diakonos', 'psalmos', 'seelsorge'}


def test_gemeinde_speichern_und_wiederlesen(client, patched_db):
    r = client.post(API + 'gemeinde_speichern', json={
        'gemeindename': 'Versöhnungskirche Heilbronn',
        'kontakt_email': 'buero@example.org',
        'oeffentliche_adresse': 'https://gemeinde.example.org/',
        'willkommenstext': 'Schön, dass du da bist.',
        'link_laufzeit_tage': 14,
        'link_max_anmeldungen': 50,
    })
    assert r.status_code == 200, r.text
    d = client.post(API + 'gemeinde_get_einstellungen').json()['message']
    assert d['gemeindename'] == 'Versöhnungskirche Heilbronn'
    assert d['kontakt_email'] == 'buero@example.org'
    # Schluss-Schrägstrich wird entfernt, damit Links sauber zusammengesetzt werden.
    assert d['oeffentliche_adresse'] == 'https://gemeinde.example.org'
    assert d['willkommenstext'] == 'Schön, dass du da bist.'
    assert d['link_laufzeit_tage'] == 14
    assert d['link_max_anmeldungen'] == 50
    # Der Gemeindename landet wirklich in der portierten Single.
    from diakronos_app.models.diakronos import DiakronosEinstellungen
    with patched_db() as sess:
        zeile = sess.get(DiakronosEinstellungen, 'Diakronos Einstellungen')
        assert zeile.organisationsname == 'Versöhnungskirche Heilbronn'


@pytest.mark.parametrize('daten,grund', [
    ({'gemeindename': ''}, 'Pflichtfeld'),
    ({'gemeindename': 'X', 'kontakt_email': 'keine-adresse'}, 'E-Mail'),
    ({'gemeindename': 'X', 'oeffentliche_adresse': 'gemeinde.example.org'}, 'http'),
    ({'gemeindename': 'X', 'link_laufzeit_tage': -1}, 'Laufzeit'),
    ({'gemeindename': 'X', 'link_max_anmeldungen': 999999}, 'Anmeldungen'),
    ({'gemeindename': 'X' * 141}, 'zu lang'),
])
def test_gemeinde_ungueltige_eingabe_bleibt_ohne_nebenwirkung(client, daten, grund):
    vorher = client.post(API + 'gemeinde_get_einstellungen').json()['message']
    r = client.post(API + 'gemeinde_speichern', json=daten)
    assert r.status_code == 417, r.text
    assert grund in r.text or 'gueltig' in r.text or 'zwischen' in r.text
    assert client.post(API + 'gemeinde_get_einstellungen').json()['message'] == vorher


def test_modul_schalten(client, patched_db):
    r = client.post(API + 'gemeinde_setze_modul',
                    json={'schluessel': 'psalmos', 'sichtbar': True})
    assert r.status_code == 200, r.text
    d = client.post(API + 'gemeinde_get_einstellungen').json()['message']
    assert next(m for m in d['module'] if m['schluessel'] == 'psalmos')['sichtbar'] is True
    r = client.post(API + 'gemeinde_setze_modul',
                    json={'schluessel': 'gibtsnicht', 'sichtbar': True})
    assert r.status_code == 417, r.text


def test_datenschutz_defaults_und_version_steigt_nur_bei_aenderung(client):
    d = client.post(API + 'datenschutz_get_texte').json()['message']
    assert d['version'] == 1
    assert 'widerrufen' in d['einwilligung']
    assert d['veroeffentlicht'] is False
    # Gleicher Inhalt -> keine neue Fassung.
    r = client.post(API + 'datenschutz_speichern', json={
        'einwilligung': d['einwilligung'],
        'datenschutzerklaerung': d['datenschutzerklaerung'],
        'aufbewahrung': d['aufbewahrung'],
        'veroeffentlicht': True,
    })
    assert r.status_code == 200, r.text
    assert r.json()['message']['version'] == 1
    # Echte Aenderung -> Fassung 2.
    r = client.post(API + 'datenschutz_speichern', json={
        'einwilligung': d['einwilligung'] + ' (Stand 2026)',
        'datenschutzerklaerung': d['datenschutzerklaerung'],
        'aufbewahrung': d['aufbewahrung'],
        'veroeffentlicht': True,
    })
    assert r.json()['message']['version'] == 2
    assert client.post(API + 'datenschutz_get_texte').json()['message']['veroeffentlicht'] is True


def test_datenschutz_pflichtfelder(client):
    d = client.post(API + 'datenschutz_get_texte').json()['message']
    r = client.post(API + 'datenschutz_speichern', json={
        'einwilligung': '',
        'datenschutzerklaerung': d['datenschutzerklaerung'],
        'aufbewahrung': d['aufbewahrung'],
    })
    assert r.status_code == 417, r.text


def test_nur_admin_darf_lesen_und_schreiben(client, set_user):
    set_user('Guest')
    # Guest wird vom Router als abgelaufene Anmeldung behandelt -> 401.
    assert client.post(API + 'gemeinde_get_einstellungen').status_code == 401
    assert client.post(API + 'datenschutz_get_texte').status_code == 401
    assert client.post(API + 'gemeinde_setze_modul',
                       json={'schluessel': 'kronos', 'sichtbar': True}).status_code == 401


def test_speichern_nur_post(client, monkeypatch):
    from diakronos_app.api import gemeinde

    class _Req:
        method = 'GET'

    with pytest.raises(Exception):
        gemeinde.gemeinde_speichern(gemeindename='X', request=_Req())


def test_gepflegter_einwilligungstext_wird_in_der_registrierung_genutzt(client):
    """N9: der unter Datenschutz-Texte gepflegte Text ersetzt den Code-Standard.

    N9b (H-1/M-2): Ohne veroeffentlichte Fassung gilt der Server-Standardtext
    (dieselbe Quelle, die die oeffentliche Seite anzeigt). Erst das
    Veroeffentlichen macht den gepflegten Wortlaut wirksam.
    """
    from diakronos_app.api import gemeinde, registrierung

    # Ohne veroeffentlichten Text gilt der Standardtext der Gemeinde-Quelle.
    assert registrierung._dsgvo_text_aktuell() == gemeinde.STANDARD_EINWILLIGUNG

    r = client.post(API + 'datenschutz_speichern', json={
        'einwilligung': 'Eigener Einwilligungstext der Testgemeinde.',
        'datenschutzerklaerung': 'Erklaerung',
        'aufbewahrung': 'Aufbewahrung',
        'veroeffentlicht': True,
    })
    assert r.status_code == 200, r.text
    assert registrierung._dsgvo_text_aktuell() == 'Eigener Einwilligungstext der Testgemeinde.'
