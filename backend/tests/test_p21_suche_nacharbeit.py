"""BF1d N2: Mehrwortsuche gilt für Auswahl und Mitgliederliste."""
import pytest
from test_p4a_gruppen import hierarchie
from diakronos_app.frappe_compat.session import set_user


@pytest.mark.parametrize('suche', ['Anna Beispiel', 'beispiel anna', '  ANNA   beispiel  '])
def test_auswahl_mehrwortsuche_ohne_email(client, hierarchie, suche):
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.db import SessionLocal
    with SessionLocal.begin() as s:
        s.add(Mitglied(name='p21-anna', vorname='Anna', nachname='Beispiel', status='Mitglied'))
        s.add(Mitglied(name='p21-falsch', vorname='Anna', nachname='Anders', status='Mitglied', email='beispiel@example.org'))
    set_user('gruppenverantw@example.org')
    r = client.post('/api/method/diakronos.diakonos.api.gruppen.get_gruppe_mitglieder_auswahl', json={
        'gruppe_id':'G-A1', 'suche':suche})
    assert r.status_code == 200, r.text
    assert [x['mitglied'] for x in r.json()['message']] == ['p21-anna']
    assert set(r.json()['message'][0]) <= {'mitglied', 'name', 'in_gruppe'}
