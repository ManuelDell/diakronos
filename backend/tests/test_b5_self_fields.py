"""B5.2: Status ist Admin-Sache, Einwilligung nie ohne Log."""
import pytest

from test_b5_email import A, ADMIN, email_world  # noqa: F401 — Fixture
from diakronos_app.models.diakonos import Mitglied


@pytest.mark.parametrize('endpoint', ['update_mitglied', 'update_mitglied_with_confirmation'])
@pytest.mark.parametrize('field,value', [('status', 'Ausgetreten'), ('datenschutz_einwilligung', True)])
def test_self_cannot_change_protected_fields(client, email_world, set_user, endpoint, field, value):
    set_user(A)
    r = client.post('/api/method/mitglieder.' + endpoint,
                    json={'mitglied_id': 'M-0001', 'data': {field: value, 'vorname': 'Forbidden'},
                          'audit_confirmation': {}})
    assert r.status_code == 403
    email_world.expire_all()
    m = email_world.get(Mitglied, 'M-0001')
    assert m.status == 'Mitglied'
    assert not m.datenschutz_einwilligung
    assert m.vorname == 'Anna'


@pytest.mark.parametrize('endpoint', ['update_mitglied', 'update_mitglied_with_confirmation'])
def test_admin_can_change_status(client, email_world, set_user, endpoint):
    set_user(ADMIN)
    r = client.post('/api/method/mitglieder.' + endpoint,
                    json={'mitglied_id': 'M-0001', 'data': {'status': 'Ausgetreten'}, 'audit_confirmation': {}})
    assert r.status_code == 200
    email_world.expire_all()
    assert email_world.get(Mitglied, 'M-0001').status == 'Ausgetreten'


@pytest.mark.parametrize('endpoint', ['update_mitglied', 'update_mitglied_with_confirmation'])
def test_admin_cannot_write_consent_without_log(client, email_world, set_user, endpoint):
    set_user(ADMIN)
    r = client.post('/api/method/mitglieder.' + endpoint,
                    json={'mitglied_id': 'M-0001', 'data': {'datenschutz_einwilligung': True}, 'audit_confirmation': {}})
    assert r.status_code == 403
    email_world.expire_all()
    assert not email_world.get(Mitglied, 'M-0001').datenschutz_einwilligung


def test_unchanged_protected_values_do_not_block_regular_save(client, email_world, set_user):
    set_user(A)
    r = client.post('/api/method/mitglieder.update_mitglied',
                    json={'mitglied_id': 'M-0001', 'data': {'status': 'Mitglied', 'datenschutz_einwilligung': 0,
                                                         'email': A, 'vorname': 'Allowed'}})
    assert r.status_code == 200
    email_world.expire_all()
    assert email_world.get(Mitglied, 'M-0001').vorname == 'Allowed'
