"""P0-4b K2/K5: feste atomare Fenster und begrenzter Token-Keyspace."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from redis import Redis
from redis.exceptions import ConnectionError

from diakronos_app.anmeldung import registrierungsbremse as bremse
from diakronos_app.frappe_compat.session import set_user

MODUL = '/api/method/diakronos.diakonos.api.registrierung'


def test_fenster_ist_atomar_und_repariert_alten_schluessel(privater_redis_url, monkeypatch):
    """Echtes Redis: Parallelaufrufe und geerbter Schlüssel ohne Ablauf."""
    monkeypatch.setattr(bremse.settings, 'registrierung_fenster_sekunden', 60)
    client = Redis.from_url(privater_redis_url)
    key = 'p21-fenster'
    try:
        # Vor der Reparatur konnte INCR ohne EXPIRE im Store zurückbleiben.
        client.set(key, 3)
        assert bremse._zaehle(client, key, 10) is True
        assert 0 < client.ttl(key) <= 60
        # Ein bestehendes Fenster wird auch bei weiterer Last NICHT verlängert.
        client.expire(key, 20)
        with ThreadPoolExecutor(max_workers=8) as pool:
            erlaubt = list(pool.map(lambda _: bremse._zaehle(client, key, 10), range(16)))
        assert sum(erlaubt) == 6
        assert int(client.get(key)) == 20
        assert 0 < client.ttl(key) <= 20
    finally:
        client.delete(key)
        client.close()


def test_zaehler_verwendet_eine_redis_transaktion(fake_redis, monkeypatch):
    """Kein einzeln bestätigtes INCR vor dem Setzen des Ablaufs."""
    pipeline = fake_redis.pipeline
    transaktionen = []

    def beobachte(transaction=True):
        transaktionen.append(transaction)
        return pipeline(transaction=transaction)

    monkeypatch.setattr(fake_redis, 'pipeline', beobachte)
    assert bremse._zaehle(fake_redis, 'p21-atomar', 2) is True
    assert transaktionen == [True]
    assert fake_redis.ttl('p21-atomar') > 0


@pytest.mark.parametrize('methode', ['submit_registrierung', 'submit_gast'])
def test_ungueltige_tokens_erzeugen_keine_link_schluessel(client, fake_redis, monkeypatch, methode):
    monkeypatch.setattr(bremse.settings, 'registrierung_max_ip', 100)
    from diakronos_app import request_context
    monkeypatch.setattr(request_context, 'zaehler_client_ip', lambda: '203.0.113.7')
    set_user('Guest')
    for i in range(5):
        r = client.post(f'{MODUL}.{methode}', json={
            'token': f'frei-erfunden-{i}', 'vorname': 'Test', 'nachname': 'Person', 'dsgvo': True,
        })
        assert r.status_code == 403, r.text
    assert list(fake_redis.scan_iter(match=f'{bremse.SCHLUESSEL_PRAEFIX}link:*')) == []
    assert bremse.zaehler_stand('203.0.113.7', client=fake_redis)['ip'] == 5


@pytest.mark.parametrize('methode', ['submit_registrierung', 'submit_gast', 'validate_token'])
def test_redis_ausfall_verweigert_mit_verstaendlichem_hinweis(client, fake_redis, monkeypatch, methode):
    def ausgefallen(*args, **kwargs):
        raise ConnectionError('interne-redis-adresse-nicht-offenlegen')

    monkeypatch.setattr(fake_redis, 'pipeline', ausgefallen)
    monkeypatch.setattr(fake_redis, 'incr', ausgefallen)
    from diakronos_app import request_context
    monkeypatch.setattr(request_context, 'zaehler_client_ip', lambda: '203.0.113.7')
    set_user('Guest')
    r = client.post(f'{MODUL}.{methode}', json={
        'token': 'frei-erfunden', 'vorname': 'Test', 'nachname': 'Person', 'dsgvo': True,
    })
    assert r.status_code == 417, r.text
    assert 'später erneut' in r.json()['message']
    assert 'interne-redis' not in r.text


def test_redis_ausfall_zeigt_oeffentliche_fehlerseite(fake_redis, monkeypatch):
    from diakronos_app import request_context, spa

    def ausgefallen(*args, **kwargs):
        raise ConnectionError('interne-redis-adresse-nicht-offenlegen')

    monkeypatch.setattr(fake_redis, 'pipeline', ausgefallen)
    monkeypatch.setattr(fake_redis, 'incr', ausgefallen)
    monkeypatch.setattr(request_context, 'zaehler_client_ip', lambda: '203.0.113.7')
    daten = spa._oeffentliche_daten('registrierung', 'frei-erfunden')
    assert 'später erneut' in daten['linkFehler']
    assert daten['token'] == ''
    assert 'interne-redis' not in str(daten)
