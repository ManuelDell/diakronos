"""B5.3: bekannte ID darf keinen unveroeffentlichten Beitrag oeffnen."""
import pytest

from test_p4f_beitraege_wiki import ANNA, ADMIN, BRUNO, welt  # noqa: F401
from diakronos_app.models.diakonos import Beitrag, BeitragKommentar


@pytest.mark.parametrize('user,expected', [(ANNA, 404), (BRUNO, 200), (ADMIN, 200)])
def test_draft_detail_only_for_author_or_admin(client, welt, set_user, user, expected):
    set_user(user)
    r = client.get('/api/method/beitraege.get_beitrag_detail', params={'beitrag_id': 'BEI-2'})
    assert r.status_code == expected
    if expected == 200:
        assert r.json()['message']['content'] == '<p>Entwurfstext</p>'
    else:
        assert 'Entwurfstext' not in r.text
        assert 'commentList' not in r.text


def test_unpublished_without_author_is_hidden(client, welt, set_user):
    welt.get(Beitrag, 'BEI-2').autor_email = None
    welt.get(Beitrag, 'BEI-2').veroeffentlicht = False
    welt.commit()
    set_user(ANNA)
    hidden = client.get('/api/method/beitraege.get_beitrag_detail', params={'beitrag_id': 'BEI-2'})
    missing = client.get('/api/method/beitraege.get_beitrag_detail', params={'beitrag_id': 'zz-b-missing'})
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json()


def test_non_author_cannot_comment_on_hidden_draft(client, welt, set_user):
    set_user(ANNA)
    count = welt.query(BeitragKommentar).count()
    r = client.post('/api/method/beitraege.create_kommentar', json={'beitrag_id': 'BEI-2', 'text': 'Probe'})
    assert r.status_code == 404
    assert welt.query(BeitragKommentar).count() == count


def test_published_detail_stays_readable(client, welt, set_user):
    set_user(BRUNO)
    r = client.get('/api/method/beitraege.get_beitrag_detail', params={'beitrag_id': 'BEI-1'})
    assert r.status_code == 200
    assert r.json()['message']['content'] == '<p>Alle sind eingeladen.</p>'
