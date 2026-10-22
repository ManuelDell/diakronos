"""B5.4: GET und Multiget teilen exakt den Kalenderquery-Sichtbarkeitsfilter."""
import pytest
from test_p6b_caldav import _basic, kalenderwelt  # noqa: F401
from diakronos_app.models.kronos import Element

BASE = '/dav/anna@example.org/Gottesdienst/'


@pytest.mark.parametrize('status', ['Entwurf', 'Abgesagt', '', None])
def test_non_final_status_hidden_in_get_and_multiget(client, kalenderwelt, status):
    kalenderwelt.get(Element, 'EV-0004').status = status
    kalenderwelt.commit()
    headers = _basic('anna@example.org', 'geheim')
    r = client.get(BASE + 'EV-0004.ics', headers=headers)
    assert r.status_code == 404
    assert 'UID:EV-0004' not in r.text
    xml = '<C:calendar-multiget xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:D="DAV:"><D:href>' + BASE + 'EV-0004.ics</D:href></C:calendar-multiget>'
    r = client.request('REPORT', BASE, headers=headers, content=xml)
    assert r.status_code == 207
    assert 'EV-0004' not in r.text


def test_multiget_restricts_uid_to_requested_calendar(client, kalenderwelt):
    headers = _basic('anna@example.org', 'geheim')
    xml = '<C:calendar-multiget xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:D="DAV:">' + ''.join(
        '<D:href>' + BASE + uid + '.ics</D:href>' for uid in ('EV-0001', 'EV-0003', 'EV-0004', 'zz-b-missing')) + '</C:calendar-multiget>'
    r = client.request('REPORT', BASE, headers=headers, content=xml)
    assert r.status_code == 207
    assert 'UID:EV-0001@diakronos' in r.text
    assert all(uid not in r.text for uid in ('EV-0003', 'EV-0004', 'zz-b-missing'))


def test_get_final_foreign_calendar_uid_is_404(client, kalenderwelt):
    r = client.get(BASE + 'EV-0003.ics', headers=_basic('anna@example.org', 'geheim'))
    assert r.status_code == 404
    assert 'EV-0003' not in r.text


def test_all_caldav_read_paths_agree_for_visible_uid(client, kalenderwelt):
    headers = _basic('anna@example.org', 'geheim')
    get = client.get(BASE + 'EV-0001.ics', headers=headers)
    query = client.request('REPORT', BASE, headers=headers, content='<C:calendar-query xmlns:C="urn:ietf:params:xml:ns:caldav"/>')
    propfind = client.request('PROPFIND', BASE, headers={**headers, 'Depth': '1'})
    assert get.status_code == 200
    assert query.status_code == propfind.status_code == 207
    assert all('EV-0001' in r.text and 'EV-0004' not in r.text for r in (get, query, propfind))
