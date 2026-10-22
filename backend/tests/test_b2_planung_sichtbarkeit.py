"""B2: A hidden birthday must not be disclosed through a participant's age."""
import json
from datetime import date

import pytest
from sqlalchemy import delete

from tests.test_p4d1_planung_teil1 import welt, PLAN, ANNA
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.diakonos import (
    Mitglied, DienstplanTeilnehmer, Dienstplan, Dienstbereich, GruppeVerantwortlicher,
)


@pytest.fixture()
def teilnehmer_welt(welt):
    welt.execute(delete(GruppeVerantwortlicher).where(GruppeVerantwortlicher.user == ANNA))
    welt.get(Mitglied, 'M-0001').ancestor_path = '/G-1/|/DB-GOTTESDIENST/'
    welt.get(Dienstbereich, 'DB-GOTTESDIENST').ancestor_path = '/G-1/|/DB-GOTTESDIENST/'
    plan = welt.get(Dienstplan, PLAN)
    plan.ist_entwurf = False
    plan.status = 'Veroeffentlicht'
    plan.owner = 'zz-b-other-owner'
    plan.leitung = 'M-0002'
    from diakronos_app.models.core import User, HasRole
    for role in ['System Manager', 'Mitgliederadministrator']:
        user = f'zz-b-{role}@example.invalid'
        welt.add(User(name=user, email=user, enabled=True))
        welt.flush()
        welt.add(HasRole(name=f'zz-b-role-{role}', parent=user,
                         parenttype='User', parentfield='roles', role=role))
    member = welt.get(Mitglied, 'M-0002')
    member.geburtstag = date(1985, 5, 5)
    member.adressbuch_sichtbarkeit = '{}'
    welt.add(DienstplanTeilnehmer(name='zz-b-participant', parent=PLAN,
        parenttype='Dienstplan', parentfield='teilnehmer', mitglied=member.name))
    welt.commit()
    return welt


def age_response(client, user=ANNA):
    set_user(user)
    response = client.get('/api/method/planung.get_teilnehmer', params={'plan': PLAN})
    assert response.status_code == 200, response.text
    row = next(z for z in response.json()['message'] if z['mitglied'] == 'M-0002')
    print('participant:', json.dumps(row))
    return row['alter']


@pytest.mark.parametrize('policy', [
    None, '', '{}', 'broken', '[]', 'null',
    '{"geburtstag": false}', '{"geburtstag": "false"}',
    '{"geburtstag": "true"}', '{"geburtstag": 1}',
    '{"email": true}',
])
def test_hidden_birthday_not_exposed_as_age(client, teilnehmer_welt, policy):
    teilnehmer_welt.get(Mitglied, 'M-0002').adressbuch_sichtbarkeit = policy
    teilnehmer_welt.commit()
    assert age_response(client) is None


@pytest.mark.parametrize('user,policy', [
    (ANNA, '{"geburtstag": true}'),
    ('bruno@example.org', '{}'),
    ('zz-b-System Manager@example.invalid', '{}'),
    ('zz-b-Mitgliederadministrator@example.invalid', '{}'),
])
def test_explicit_own_and_admin_birthday_visible(client, teilnehmer_welt, user, policy):
    teilnehmer_welt.get(Mitglied, 'M-0002').adressbuch_sichtbarkeit = policy
    teilnehmer_welt.commit()
    today = date.today()
    expected = today.year - 1985 - ((today.month, today.day) < (5, 5))
    assert age_response(client, user) == expected


def test_group_leader_has_no_birthday_exception(client, teilnehmer_welt):
    teilnehmer_welt.add(GruppeVerantwortlicher(name='zz-b-leader', parent='G-1',
        parenttype='Gruppe', parentfield='verantwortliche', user=ANNA))
    teilnehmer_welt.commit()
    assert age_response(client) is None
