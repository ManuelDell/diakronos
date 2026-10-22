"""P2-4c: Serienabsage, Rückstufung und lesbare Sammelmeldung."""
from datetime import datetime
import pytest
from sqlalchemy import select
from test_p2_4_benachrichtigungen import _kalender_moderator_welt, anmelden


def nachrichten(sf, user='talente'):
    from diakronos_app.models.core import NotificationLog
    with sf() as s:
        return [dict(titel=n.subject, text=n.email_content, ziel=n.document_name) for n in s.scalars(select(NotificationLog).where(NotificationLog.for_user==user))]


def serie(sf):
    from diakronos_app.models.kronos import Element, ElementMitarbeiter
    with sf.begin() as s:
        s.get(Element, 'E-1').series_id = 'p21-serie'
        s.add(Element(name='E-2', element_name='Chorprobe', element_calendar='K-GD', series_id='p21-serie', status='Festgelegt', element_start=datetime(2026,12,13,10),element_end=datetime(2026,12,13,11)))
        s.add(ElementMitarbeiter(name='EM-2',parent='E-2',parenttype='Element',parentfield='mitarbeiter',mitglied='M-TAL'))


@pytest.mark.parametrize('fn,args', [('delete_series_batch_fast',{}), ('delete_future_series_events',{'from_date':'2026-12-01'})])
def test_serien_absage_gebuendelt_ohne_toten_link(client, patched_db, fn, args):
    _kalender_moderator_welt(patched_db)
    serie(patched_db)
    anmelden(client, 'moderator')
    r=client.post('/api/method/diakronos.kronos.api.series.'+fn,json={'series_id':'p21-serie',**args})
    assert r.status_code==200,r.text
    assert r.json()['message']['deleted_count']==2
    zeilen=nachrichten(patched_db)
    assert len(zeilen)==1
    assert 'abgesagt' in zeilen[0]['titel']
    assert 'Gottesdienst' in zeilen[0]['text'] and 'Chorprobe' in zeilen[0]['text']
    assert '06.12.2026' in zeilen[0]['text'] and '13.12.2026' in zeilen[0]['text']
    assert not zeilen[0]['ziel']
    assert nachrichten(patched_db,'moderator')==[]


@pytest.mark.parametrize('status',['Vorschlag','Abgelehnt','Konflikt'])
def test_rueckstufung_meldet_ohne_link(client, patched_db, status):
    _kalender_moderator_welt(patched_db)
    anmelden(client,'moderator')
    r=client.post('/api/method/diakronos.kronos.api.event_crud.save_event',json={'name':'E-1','element_name':'Gottesdienst','element_calendar':'K-GD','element_start':'2026-12-06 10:00:00','element_end':'2026-12-06 11:00:00','status':status})
    assert r.status_code==200,r.text
    zeilen=nachrichten(patched_db)
    assert len(zeilen)==1
    assert not zeilen[0]['ziel']


def test_serien_absage_ohne_leserecht_still(client, patched_db):
    _kalender_moderator_welt(patched_db,mit_leserecht=False)
    # Schreibrecht gilt ebenfalls als Leserecht: Empfänger explizit abtrennen.
    from diakronos_app.models.core import HasRole
    with patched_db.begin() as s:
        s.get(HasRole,'r-ein').role='OhneLeserecht'
    serie(patched_db)
    anmelden(client,'moderator')
    r=client.post('/api/method/diakronos.kronos.api.series.delete_series_batch_fast',json={'series_id':'p21-serie'})
    assert r.status_code==200,r.text
    assert nachrichten(patched_db)==[]


def test_serien_rueckstufung_buendelt_ohne_link(client, patched_db):
    _kalender_moderator_welt(patched_db)
    serie(patched_db)
    anmelden(client, 'moderator')
    r = client.post('/api/method/diakronos.kronos.api.series.update_series_batch_fast', json={
        'series_id': 'p21-serie', 'updates': {'status': 'Vorschlag'}})
    assert r.status_code == 200, r.text
    zeilen = nachrichten(patched_db)
    assert len(zeilen) == 1
    assert not zeilen[0]['ziel']
    assert 'Chorprobe' in zeilen[0]['text']


def test_fehlgeschlagene_loeschung_meldet_keine_absage(client, patched_db, monkeypatch):
    _kalender_moderator_welt(patched_db)
    serie(patched_db)
    anmelden(client, 'moderator')
    from diakronos_app.api.kronos import series
    def verweigert(*args):
        raise RuntimeError('Test: Löschen nicht möglich')
    monkeypatch.setattr(series, '_delete_doc', verweigert)
    r = client.post('/api/method/diakronos.kronos.api.series.delete_series_batch_fast', json={'series_id': 'p21-serie'})
    assert r.status_code == 200, r.text
    assert r.json()['message']['deleted_count'] == 0
    assert nachrichten(patched_db) == []


def test_serien_absage_mit_gemischten_empfaengern_nennt_je_person_eigene_termine(client, patched_db):
    """K-5: Bei einer Serie mit unterschiedlich Eingeteilten bekommt jede
    Person nur IHRE Termine genannt — nicht die ganze Serie."""
    from diakronos_app.models.core import HasRole, User, UserRole
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.models.kronos import ElementMitarbeiter
    _kalender_moderator_welt(patched_db)
    # Zweite eingeteilte Person mit eigenem Leserecht am selben Kalender.
    with patched_db.begin() as s:
        s.add(User(name='leser', email='leser', enabled=True))
        s.add(Mitglied(name='M-LES', user='leser', email='leser',
                       vorname='Lena', nachname='Leser', status='Mitglied'))
        # W-3: ohne eigenes Leserecht bekommt Lena keine Nachricht (das prüft
        # test_serien_absage_ohne_leserecht_still); hier ist sie ausdrücklich
        # berechtigt, damit nur die Terminfilterung gemessen wird.
        s.add(HasRole(name='r-les', parent='leser', parenttype='User',
                      parentfield='roles', role='Mitglied'))
        s.add(UserRole(name='ur-les', parent='K-GD', parenttype='Kalender',
                       parentfield='leserechte', role='Mitglied', docstatus=0, idx=3))
    serie(patched_db)  # E-2 „Chorprobe“ am 13.12.2026 mit M-TAL
    with patched_db.begin() as s:
        s.get(ElementMitarbeiter, 'EM-2').mitglied = 'M-LES'
    # Dritte Person ist nur an E-1 (Gottesdienst, 06.12.2026) eingeteilt.
    anmelden(client, 'moderator')
    r = client.post('/api/method/diakronos.kronos.api.series.delete_series_batch_fast',
                    json={'series_id': 'p21-serie'})
    assert r.status_code == 200, r.text
    assert r.json()['message']['deleted_count'] == 2

    # Tina (M-TAL, aus der Basiswelt) war an E-1 -> nur der Gottesdienst.
    tina = nachrichten(patched_db, 'talente')
    assert len(tina) == 1
    assert 'Gottesdienst' in tina[0]['text']
    assert 'Chorprobe' not in tina[0]['text'], 'fremde Termine in Tinas Meldung'
    # Lena war nur an E-2 -> nur die Chorprobe.
    lena = nachrichten(patched_db, 'leser')
    assert len(lena) == 1
    assert 'Chorprobe' in lena[0]['text']
    assert 'Gottesdienst' not in lena[0]['text'], 'fremde Termine in Lenas Meldung'
    # Der Auslöser erhält keine eigene Meldung.
    assert nachrichten(patched_db, 'moderator') == []


def test_sammelaenderung_nennt_zeitraum_und_titel(client, patched_db):
    _kalender_moderator_welt(patched_db)
    serie(patched_db)
    anmelden(client, 'moderator')
    r = client.post('/api/method/diakronos.kronos.api.series.update_series_batch_fast', json={
        'series_id': 'p21-serie', 'updates': {'element_start': '2026-12-20 10:00:00', 'element_end': '2026-12-20 11:00:00'}})
    assert r.status_code == 200, r.text
    zeilen = nachrichten(patched_db)
    assert len(zeilen) == 1
    assert '20.12.2026' in zeilen[0]['text']
    assert 'Gottesdienst' in zeilen[0]['text'] and 'Chorprobe' in zeilen[0]['text']


def test_alter_glockenclient_bekommt_neuladehinweis(client,patched_db):
    _kalender_moderator_welt(patched_db)
    anmelden(client,'moderator')
    r=client.post('/api/method/diakronos.diakonos.api.audit.mark_notifications_read',json={})
    assert r.status_code==400,r.text
    assert 'neu laden' in r.json()['message']
