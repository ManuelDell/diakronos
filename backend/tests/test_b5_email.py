"""B5.1: E-Mail ist eine Berechtigungsbindung, niemals erster Treffer."""
import pytest

from diakronos_app.frappe_compat import permissions
from diakronos_app.frappe_compat.exceptions import ValidationError
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Mitglied

A = 'zz-b-email-a@example.invalid'
B = 'zz-b-email-b@example.invalid'
ADMIN = 'zz-b-email-admin@example.invalid'


@pytest.fixture()
def email_world(client, seed_mitglieder):
    s = seed_mitglieder
    s.add_all([User(name=A, email=A, enabled=True), User(name=B, email=B, enabled=True),
               User(name=ADMIN, email=ADMIN, enabled=True),
               HasRole(name='zz-b-admin-role', parent=ADMIN, parenttype='User', parentfield='roles', role='System Manager')])
    s.get(Mitglied, 'M-0001').email = A
    s.get(Mitglied, 'M-0002').email = B
    s.commit()
    return s


@pytest.mark.parametrize('endpoint', ['update_mitglied', 'update_mitglied_with_confirmation'])
@pytest.mark.parametrize('email', [A, ADMIN])
def test_admin_cannot_move_member_onto_occupied_email(client, email_world, set_user, endpoint, email):
    set_user(ADMIN)
    r = client.post('/api/method/mitglieder.' + endpoint,
                    json={'mitglied_id': 'M-0002', 'data': {'email': email, 'vorname': 'Not written'},
                          'audit_confirmation': {'bestaetigt': True}})
    assert r.status_code == 417
    assert r.json()['exception'] == 'ValidationError'
    email_world.expire_all()
    assert email_world.get(Mitglied, 'M-0002').email == B
    assert email_world.get(Mitglied, 'M-0002').vorname == 'Bruno'


@pytest.mark.parametrize('endpoint', ['update_mitglied', 'update_mitglied_with_confirmation'])
@pytest.mark.parametrize('email', ['zz-b-free@example.invalid', '', None])
def test_member_cannot_change_binding_email(client, email_world, set_user, endpoint, email):
    set_user(A)
    r = client.post('/api/method/mitglieder.' + endpoint,
                    json={'mitglied_id': 'M-0001', 'data': {'email': email}, 'audit_confirmation': {}})
    assert r.status_code == 403
    email_world.expire_all()
    assert email_world.get(Mitglied, 'M-0001').email == A


def test_spa_unchanged_email_and_regular_fields_are_allowed(client, email_world, set_user):
    set_user(A)
    r = client.post('/api/method/mitglieder.update_mitglied',
                    json={'mitglied_id': 'M-0001', 'data': {'email': A, 'vorname': 'Updated'}})
    assert r.status_code == 200
    assert r.json()['message']['success'] is True
    email_world.expire_all()
    assert email_world.get(Mitglied, 'M-0001').vorname == 'Updated'


def test_admin_can_change_to_unused_email(client, email_world, set_user):
    set_user(ADMIN)
    r = client.post('/api/method/mitglieder.update_mitglied',
                    json={'mitglied_id': 'M-0002', 'data': {'email': 'zz-b-free@example.invalid'}})
    assert r.status_code == 200
    email_world.expire_all()
    assert email_world.get(Mitglied, 'M-0002').email == 'zz-b-free@example.invalid'


def test_duplicate_member_email_fails_closed_with_warning(client, email_world, set_user, caplog):
    """Zwei Mitglieder mit derselben Adresse gibt es nicht mehr.

    SEC-b (Fachentscheidung Manuel 2026-10-19): Der frueher hier geprueften
    Zustand „zwei Mitglieder, eine Adresse“ ist auf Datenebene nicht mehr
    herstellbar. Geprueft wird die neue Zusage: der direkte Schreibweg wird
    von der Datenbank verweigert, und die Mitgliedssicht bleibt danach
    eindeutig (die Person, die die Adresse belegt, ist die eigene).
    """
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        email_world.get(Mitglied, 'M-0002').email = A
        email_world.commit()
    email_world.rollback()
    set_user(A)
    eigene = permissions._get_current_user_mitglied()
    assert eigene is not None and eigene['name'] == 'M-0001'
    for endpoint in ('get_mitglieder_liste', 'get_adressbuch'):
        r = client.get('/api/method/mitglieder.' + endpoint)
        assert r.status_code == 200
        assert r.json()['message']['data'] != []
    assert permissions.mitglied_permissions('M-0001')['can_edit'] is True


def test_profile_email_fallback_never_picks_first_duplicate(client, email_world, set_user):
    """Kein „erster Treffer“: die Adresse gehoert genau einer Person."""
    from sqlalchemy.exc import IntegrityError

    from diakronos_app.api.profile import _get_my_mitglied
    with pytest.raises(IntegrityError):
        email_world.get(Mitglied, 'M-0002').email = A
        email_world.commit()
    email_world.rollback()
    set_user(A)
    assert _get_my_mitglied() == 'M-0001'
