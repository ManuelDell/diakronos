"""P3-2: Nach FK-Reparatur duerfen Schreibwege keine Leerlinks neu anlegen."""
import pytest


@pytest.mark.parametrize('weg', ['methode', 'resource'])
def test_leere_optionale_element_links_sind_null(client, patched_db, weg):
    from diakronos_app.models.kronos import Kalender, Element
    with patched_db.begin() as s:
        s.add(Kalender(name='p32-kalender', calendar_name='P32'))
    daten = {'element_name': 'P32 Null-Links', 'element_start': '2026-10-21T10:00:00',
             'element_end': '2026-10-21T11:00:00', 'element_calendar': 'p32-kalender',
             'element_category': '', 'ressource': '', 'description': ''}
    if weg == 'methode':
        r = client.post('/api/method/diakronos.kronos.api.event_crud.create_event', json=daten)
        assert r.status_code == 200, r.text
        name = r.json()['message']['id']
    else:
        r = client.post('/api/resource/Element', json={**daten, 'name': 'P32-NULL',
                        'element_start': None, 'element_end': None})
        assert r.status_code == 200, r.text
        name = r.json()['data']['name']
    with patched_db() as s:
        e = s.get(Element, name)
        assert e.element_category is None
        assert e.ressource is None
        assert e.description == ''


def test_leere_links_in_kindzeilen_und_updates_ohne_filterveraenderung(patched_db):
    from diakronos_app.frappe_compat.api_helpers import _child_insert, _create, _update_doc, _coerce_filters
    from diakronos_app.models.kronos import AblaufplanPosition, Element
    name = _create('Element', {'element_name': 'P32', 'ressource': '', 'element_category': ''})
    _update_doc('Element', name, {'ressource': '', 'element_category': ''})
    k = _child_insert('Ablaufplan Position', 'P32', 'positionen', {'gruppe': '', 'referenz_doctype': ''}, parenttype='Ablaufplan')
    with patched_db() as s:
        assert s.get(Element, name).ressource is None
        assert s.get(AblaufplanPosition, k).gruppe is None
        assert s.get(AblaufplanPosition, k).referenz_doctype is None
    assert _coerce_filters('Element', {'ressource': ''}) == {'ressource': ''}
