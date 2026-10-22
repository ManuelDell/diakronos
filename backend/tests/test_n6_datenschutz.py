"""N6: echte HTTP-Pfade, Personenstatus, Auskunft und sichere Antragsbearbeitung."""
import pytest

from test_ma1_mailversand import _smtp_einrichten

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import User
from sqlalchemy import select

from diakronos_app.models.diakonos import Mitglied, DSGVOEinwilligung

PFAD = '/api/method/diakronos.diakonos.api.datenschutz.'


@pytest.fixture
def welt(patched_db):
    from diakronos_app.models.core import HasRole
    with patched_db.begin() as s:
        s.add(User(name='admin@example.org', enabled=True))
        s.add(HasRole(name='N6-admin-role', parent='admin@example.org', role='System Manager'))
        s.add(User(name='person@example.org', email='person@example.org', password_hash='geheim'))
        s.flush()
        s.add_all([
            Mitglied(name='N6-A', vorname='Anna', nachname='Beispiel', user='person@example.org',
                     email='person@example.org', notiz='vertraulich', datenschutz_einwilligung=True),
            Mitglied(name='N6-B', vorname='Ben', datenschutz_einwilligung=False),
            Mitglied(name='N6-C', vorname='Clara', datenschutz_einwilligung=False),
        ])
        s.add_all([
            DSGVOEinwilligung(name='N6-L1', mitglied='N6-A', typ='foto', aktion='widerrufen'),
            DSGVOEinwilligung(name='N6-L2', mitglied='N6-C', typ='datenschutz', aktion='widerrufen'),
            DSGVOEinwilligung(name='N6-L3', mitglied='N6-C', typ='datenschutz', aktion='widerrufen'),
        ])
    set_user('admin@example.org')
    return patched_db


@pytest.fixture(autouse=True)
def _mailversand(monkeypatch, tmp_path, patched_db):
    """Fake-SMTP fuer den Antragsweg.

    N-5 (DSGVO-1c): Löschungen laufen NUR über Antrag → Bestätigung → Mail.
    Der Test braucht deshalb einen Versand, der nicht ins Netz geht; die
    Prüfungen der Tests bleiben unverändert (die Meldung ist Teil des Wegs).
    """
    from diakronos_app import files, mailversand
    from diakronos_app.settings import get_settings

    class Fake:
        def __init__(self):
            self.nachrichten = []

        def ehlo(self):
            pass

        def has_extn(self, name):
            return True

        def starttls(self, **kw):
            pass

        def login(self, *a):
            pass

        def send_message(self, nachricht):
            self.nachrichten.append(nachricht)

        def quit(self):
            pass

    # MAIL-1: die SMTP-Werte stehen in der DB (Tabelle `smtp_einstellungen`),
    # nicht mehr in der Umgebung — siehe `_smtp_einrichten`.
    _smtp_einrichten(patched_db)
    s = get_settings()
    for feld, wert in (
        ("files_dir", str(tmp_path)),
    ):
        monkeypatch.setattr(s, feld, wert, raising=False)
    monkeypatch.setattr(files.settings, "files_dir", str(tmp_path), raising=False)
    fake = Fake()
    fake.dir = tmp_path
    monkeypatch.setattr(mailversand, "VERBINDUNG", fake)
    return fake


def post(client, fn, **kw):
    return client.post(PFAD + fn, json=kw)


def test_personenstand_ohne_foto_oder_logzeilenzaehlung(client, welt):
    r = client.post('/api/method/diakronos.diakronos.api.admin_hub.get_dsgvo_uebersicht')
    assert r.status_code == 200
    data = r.json()['message']
    assert data['stats'] == {'gesamt': 3, 'ok': 1, 'fehlt': 1, 'widerrufen': 1}
    assert {m['name']: m['dsgvo_status'] for m in data['mitglieder']} == {
        'N6-A': 'ok', 'N6-B': 'fehlt', 'N6-C': 'widerrufen'}


def test_auskunft_enthaelt_daten_und_nachweise_aber_keinen_hash(client, welt):
    r = post(client, 'auskunft', mitglied_id='N6-A')
    assert r.status_code == 200
    d = r.json()['message']
    assert d['mitglied']['notiz'] == 'vertraulich'
    assert d['bezug']['dsgvo_einwilligung'][0]['typ'] == 'foto'
    assert 'password_hash' not in str(d) and 'geheim' not in str(d)


def test_antrag_idempotent_ohne_datenverlust_und_admin_erledigt(client, welt):
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.models.passwortzugang import Passwortzugang
    with welt.begin() as s:
        s.add(Passwortzugang(user='person@example.org', token_hash='a' * 64, wechsel_noetig=True))
    sid, _ = sitzungen.anlegen('person@example.org')
    set_user('person@example.org')
    for _ in range(2):
        r = post(client, 'loeschung_beantragen', bestaetigt=True)
        assert r.status_code == 200
    with welt() as s:
        assert s.get(Mitglied, 'N6-A').vorname == 'Anna'
        assert s.get(User, 'person@example.org').enabled
    set_user('admin@example.org')
    liste = post(client, 'get_loeschantraege').json()['message']
    assert len(liste) == 1 and liste[0]['mitglied'] == 'N6-A'
    r = post(client, 'anonymisieren', mitglied_id='N6-A', bestaetigt=True, bestaetigung='ANONYMISIEREN', nur_antrag=True)
    assert r.status_code == 200
    assert post(client, 'get_loeschantraege').json()['message'] == []
    assert sitzungen.lesen(sid) is None
    with welt() as s:
        # DSGVO-1b (K1): die alte Kennung ist weg; die Person lebt als Zeile
        # mit der neutralen Kennung `geloescht-<hex>` weiter. Sie heißt
        # „Gelöschte Person“, ihr Konto ist WEG (nicht nur gesperrt) —
        # `user.name` ist die Mail, D5 verlangt „keine Mail mehr da“.
        assert s.get(Mitglied, 'N6-A') is None
        kennung = [n for n in s.scalars(select(Mitglied.name)).all()
                   if str(n).startswith('geloescht-')][0]
        m = s.get(Mitglied, kennung)
        assert m.vorname == 'Gelöschte' and m.nachname == 'Person'
        assert m.status == 'geloescht'
        assert not m.notiz and not m.datenschutz_einwilligung
        assert s.get(User, 'person@example.org') is None
        assert s.get(Passwortzugang, 'person@example.org') is None
        # Der Einwilligungs-Nachweis bleibt — am neuen technischen Bezug.
        nachweis = s.get(DSGVOEinwilligung, 'N6-L1')
        assert nachweis is not None and nachweis.mitglied == kennung


@pytest.mark.parametrize('args', [{}, {'bestaetigt': True}, {'bestaetigt': 'false', 'bestaetigung': 'ANONYMISIEREN'}])
def test_doppelte_serverbestaetigung(client, welt, args):
    assert post(client, 'anonymisieren', mitglied_id='N6-A', **args).status_code == 417
    with welt() as s:
        assert s.get(Mitglied, 'N6-A').vorname == 'Anna'


@pytest.mark.parametrize('fn', ['auskunft', 'anonymisieren', 'get_loeschantraege'])
def test_adminrechte_serverseitig(client, welt, fn):
    set_user('person@example.org')
    assert post(client, fn, mitglied_id='N6-B', bestaetigt=True, bestaetigung='ANONYMISIEREN').status_code == 403


def test_schreiben_nicht_per_get(client, welt):
    assert client.get(PFAD + 'anonymisieren', params={'mitglied_id': 'N6-A', 'bestaetigt': True, 'bestaetigung': 'ANONYMISIEREN'}).status_code == 417


def test_erledigung_verlangt_offenen_antrag(client, welt):
    assert post(client, 'anonymisieren', mitglied_id='N6-B', bestaetigt=True, bestaetigung='ANONYMISIEREN', nur_antrag=True).status_code == 417


def test_letzter_system_manager_nicht_anonymisierbar(client, welt):
    with welt.begin() as s:
        s.get(Mitglied, 'N6-B').user = 'admin@example.org'
    r = post(client, 'anonymisieren', mitglied_id='N6-B', bestaetigt=True, bestaetigung='ANONYMISIEREN')
    assert r.status_code == 403
    with welt() as s:
        assert s.get(User, 'admin@example.org').enabled
        assert s.get(Mitglied, 'N6-B').vorname == 'Ben'


def test_mitgliederadmin_darf_keinen_system_manager_anonymisieren(client, welt):
    from diakronos_app.models.core import HasRole
    with welt.begin() as s:
        s.add(User(name='ma@example.org', enabled=True))
        s.add(HasRole(name='ma-role', parent='ma@example.org', role='Mitgliederadministrator'))
        s.get(Mitglied, 'N6-B').email = 'admin@example.org'  # E-Mail-Fallback, ohne user-Link
    set_user('ma@example.org')
    r = post(client, 'anonymisieren', mitglied_id='N6-B', bestaetigt=True, bestaetigung='ANONYMISIEREN')
    assert r.status_code == 403
    with welt() as s:
        assert s.get(User, 'admin@example.org').enabled


def test_antrag_ohne_bestaetigung_nicht_moeglich(client, welt):
    set_user('person@example.org')
    assert post(client, 'loeschung_beantragen', bestaetigt='false').status_code == 417
    assert client.get(PFAD + 'loeschung_beantragen', params={'bestaetigt': True}).status_code == 417


def test_zwei_wirksame_verwaltungskonten_nicht_gemeinsam_aussperren(client, welt):
    from diakronos_app.models.core import HasRole
    with welt.begin() as s:
        s.add(HasRole(name='N6-zweiter-sm', parent='person@example.org', role='System Manager'))
        m = s.get(Mitglied, 'N6-A')
        m.user = 'admin@example.org'  # user-Link + anderer eindeutiger E-Mail-Fallback
    r = post(client, 'anonymisieren', mitglied_id='N6-A', bestaetigt=True, bestaetigung='ANONYMISIEREN')
    assert r.status_code == 403
    with welt() as s:
        assert s.get(User, 'admin@example.org').enabled
        assert s.get(User, 'person@example.org').enabled


def test_auskunft_enthaelt_zugeordnete_registrierung_und_antworten(client, welt):
    from diakronos_app.models.diakonos import Anmeldung, AnmeldungAntwort
    with welt.begin() as s:
        s.add(Anmeldung(name='N6-registration', mitglied='N6-A', kommentar='Kommentar'))
        s.add(AnmeldungAntwort(name='N6-answer', parent='N6-registration', antwort='Eigene Antwort'))
        s.add(AnmeldungAntwort(name='N6-other-answer', parent='fremd', antwort='Fremde Antwort'))
    d = post(client, 'auskunft', mitglied_id='N6-A').json()['message']
    assert d['bezug']['anmeldung'][0]['kommentar'] == 'Kommentar'
    assert [r['antwort'] for r in d['bezug']['anmeldung_antwort']] == ['Eigene Antwort']


@pytest.mark.parametrize('autorenfeld', ['owner', 'modified_by'])
@pytest.mark.parametrize('fremdes_mitglied', ['N6-B', None])
def test_auskunft_fremde_registrierung_nur_als_taetigkeitsreferenz(client, welt, autorenfeld, fremdes_mitglied):
    from diakronos_app.models.diakonos import Anmeldung, AnmeldungAntwort, AnmeldungKind
    with welt.begin() as s:
        s.add(Anmeldung(name='N6-fremd', mitglied=fremdes_mitglied,
                       email='fremd-privat@example.org', kommentar='Fremder Kommentar',
                       **{autorenfeld: 'person@example.org'}))
        s.add(AnmeldungAntwort(name='N6-fremde-antwort', parent='N6-fremd',
                              owner='person@example.org', antwort='Fremde Antwort'))
        s.add(AnmeldungKind(name='N6-fremdes-kind', parent='N6-fremd',
                           modified_by='person@example.org', vorname='Fremdes Kind'))
    d = post(client, 'auskunft', mitglied_id='N6-A').json()['message']
    assert not d['bezug'].get('anmeldung')
    assert not d['bezug'].get('anmeldung_antwort')
    assert not d['bezug'].get('anmeldung_kind')
    for wert in ('fremd-privat@example.org', 'Fremder Kommentar', 'Fremde Antwort', 'Fremdes Kind'):
        assert wert not in str(d)
    ref = next(r for r in d['taetigkeiten'] if r['tabelle'] == 'anmeldung')
    assert ref == {'tabelle': 'anmeldung', 'kennung': {'name': 'N6-fremd'},
                   'felder': {autorenfeld: 'person@example.org'}}


@pytest.mark.parametrize('typ', ['Mitglied', 'User'])
def test_auskunft_polymorphe_personenverweise_nur_mit_passendem_typ(client, welt, typ):
    from diakronos_app.models.core import FileModel, EventParticipants, DynamicLinkModel
    from diakronos_app.models.diakonos import AuditLog
    ziel = 'N6-A' if typ == 'Mitglied' else 'person@example.org'
    with welt.begin() as s:
        for suffix, doctype, name in [('eigen', typ, ziel), ('fremd', typ, 'N6-B'), ('falscher-typ', 'Gruppe', ziel)]:
            s.add(AuditLog(name=f'audit-{suffix}', actor='admin@example.org',
                           target_doctype=doctype, target_name=name, old_value=f'Alt-{suffix}'))
            s.add(FileModel(name=f'datei-{suffix}', file_name=f'{suffix}.pdf',
                            file_url=f'/private/files/{suffix}.pdf', owner='admin@example.org',
                            attached_to_doctype=doctype, attached_to_name=name))
            s.add(EventParticipants(name=f'teilnahme-{suffix}', reference_doctype=doctype,
                                    reference_docname=name))
            s.add(DynamicLinkModel(name=f'link-{suffix}', link_doctype=doctype, link_name=name))
    d = post(client, 'auskunft', mitglied_id='N6-A').json()['message']
    for tabelle, prefix in [('audit_log', 'audit'), ('file', 'datei'),
                            ('event_participants', 'teilnahme'), ('dynamic_link', 'link')]:
        assert [r['name'] for r in d['bezug'].get(tabelle, [])] == [f'{prefix}-eigen']
    assert d['bezug']['audit_log'][0]['old_value'] == 'Alt-eigen'
    assert d['bezug']['file'][0]['file_name'] == 'eigen.pdf'


def test_auskunft_fremdes_audit_und_benachrichtigung_nicht_ueber_actor(client, welt):
    from diakronos_app.models.core import NotificationLog
    from diakronos_app.models.diakonos import AuditLog
    with welt.begin() as s:
        s.add(AuditLog(name='N6-fremdes-audit', actor='person@example.org',
                       target_doctype='Mitglied', target_name='N6-B', old_value='Fremdes Audit-Geheimnis'))
        s.add(NotificationLog(name='N6-fremde-nachricht', for_user='admin@example.org',
                              owner='person@example.org', email_content='Fremde Nachricht'))
        s.add(NotificationLog(name='N6-eigene-nachricht', for_user='person@example.org',
                              owner='admin@example.org', email_content='Eigene Nachricht'))
    d = post(client, 'auskunft', mitglied_id='N6-A').json()['message']
    assert not d['bezug'].get('audit_log')
    assert [r['name'] for r in d['bezug']['notification_log']] == ['N6-eigene-nachricht']
    assert 'Fremdes Audit-Geheimnis' not in str(d)
    assert 'Fremde Nachricht' not in str(d)
    assert any(r['tabelle'] == 'audit_log' and r['felder'] == {'actor': 'person@example.org'}
               for r in d['taetigkeiten'])


def test_auskunft_rollen_und_beziehungen_ohne_fremden_personenstamm(client, welt):
    from diakronos_app.models.core import HasRole
    from diakronos_app.models.diakonos import MitgliedBeziehung
    with welt.begin() as s:
        s.add(HasRole(name='N6-rolle', parent='person@example.org', parenttype='User', role='Mitglied'))
        s.add(HasRole(name='N6-fremde-rolle', parent='admin@example.org', role='Mitglied'))
        s.add(MitgliedBeziehung(name='N6-beziehung', parent='N6-B', beziehung_zu='N6-A'))
        s.get(Mitglied, 'N6-B').notiz = 'Fremder Personenstamm'
    d = post(client, 'auskunft', mitglied_id='N6-A').json()['message']
    assert [r['name'] for r in d['bezug']['has_role']] == ['N6-rolle']
    assert d['bezug']['mitglied_beziehung'][0]['name'] == 'N6-beziehung'
    assert 'Fremder Personenstamm' not in str(d)


def test_auskunft_zugeteilte_fremde_person_nur_als_referenz(client, welt):
    from diakronos_app.models.diakonos import Rollenbesetzung
    with welt.begin() as s:
        s.add(Rollenbesetzung(name='N6-zuteilung', teilnehmer='N6-B', zugeteilt_von='N6-A',
                             notiz='Fremde Zuteilungsnotiz'))
    d = post(client, 'auskunft', mitglied_id='N6-A').json()['message']
    assert not d['bezug'].get('rollenbesetzung')
    assert 'Fremde Zuteilungsnotiz' not in str(d)
    assert any(r['tabelle'] == 'rollenbesetzung' and r['felder'] == {'zugeteilt_von': 'N6-A'}
               for r in d['taetigkeiten'])
