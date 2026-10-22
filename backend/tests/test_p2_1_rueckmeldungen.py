"""P2-1: DB-Ausnahmen dürfen weder Werte noch SQL ins Log schreiben."""
from sqlalchemy.exc import IntegrityError
from diakronos_app.frappe_compat.api_helpers import _db_fehler


def test_db_fehler_loggt_keine_parameter(capsys):
    exc = IntegrityError('INSERT INTO mitglied', {'email': 'privat@example.test'}, Exception('privat@example.test'))
    fehler = _db_fehler(exc, 'Mitglied')
    log = capsys.readouterr().err
    assert 'IntegrityError' in log
    assert 'privat@example.test' not in log
    assert 'INSERT' not in log
    assert 'privat@example.test' not in str(fehler)


def test_sitzung_und_objektrechte_bleiben_unterscheidbar(client):
    from diakronos_app.frappe_compat.session import set_user
    set_user('Guest')
    antwort = client.post('/api/method/diakronos.diakonos.api.wiki.create_wiki_artikel', json={'titel': 'Test'})
    assert antwort.status_code == 401
    assert antwort.json()['exc_type'] == 'SessionExpired'
    # Öffentliche Tokenprüfung bleibt ohne Anmeldung erreichbar (Fachfehler,
    # nicht der zentrale Sitzungsfehler).
    antwort = client.get('/api/method/diakronos.diakonos.api.registrierung.validate_token?token=ungueltig')
    assert antwort.status_code != 401


def test_sitzung_status_bindet_csrf_an_identitaet(monkeypatch):
    from starlette.requests import Request
    from diakronos_app.api.session import sitzung_status
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.frappe_compat.session import set_user
    request = Request({'type': 'http', 'headers': [(b'cookie', b'sid=test-sid')]})
    set_user('Administrator')
    monkeypatch.setattr(sitzungen, 'lesen', lambda sid: {'user': 'fremd', 'csrf_token': 'nicht-ausgeben'})
    assert sitzung_status(request).status_code == 401
    monkeypatch.setattr(sitzungen, 'lesen', lambda sid: {'user': 'Administrator', 'csrf_token': 'token'})
    assert sitzung_status(request) == {'user': 'Administrator', 'csrf_token': 'token'}
