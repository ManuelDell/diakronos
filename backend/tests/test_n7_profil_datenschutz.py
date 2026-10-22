"""N7: Selbstauskunft, Antrag statt Sofortlöschung und N6-Nacharbeit."""
from datetime import date

import pytest

from test_ma1_mailversand import _smtp_einrichten
from sqlalchemy import event, select

from test_n6_datenschutz import welt, post, PFAD  # noqa: F401
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import User
from diakronos_app.models.diakonos import (
    Mitglied, Anmeldung, AnmeldungAntwort, AnmeldungKind,
    MitgliedBereich, MitgliedBeziehung,
)


@pytest.fixture(autouse=True)
def _mailversand(monkeypatch, tmp_path, patched_db):
    """Fake-SMTP fuer den Antragsweg (N-5, DSGVO-1c).

    Löschungen laufen NUR über Antrag → Bestätigung → Mail, die Bestätigung
    also IMMER über `mailversand`. Ohne Fake ginge dieser Test ins Netz.
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

PROFIL = '/api/method/diakronos.diakonos.api.profile.'


@pytest.mark.parametrize('fn', ['meine_auskunft', 'mein_loeschantrag', 'loeschung_beantragen'])
def test_gast_ohne_zugriff(guest_client, welt, fn):
    # P2-1 (OP-UI-1): Ohne Sitzung antwortet der Server 401 SessionExpired — die
    # SPA kann daraufhin neu anmelden. Frueher war es 403; die Trennung von
    # „nicht angemeldet" und „nicht berechtigt" ist in planrahmen/doku/API.md
    # festgehalten. Entscheidend bleibt: der Gast erhaelt keine Daten.
    set_user('Guest')
    r = post(guest_client, fn, bestaetigt=True)
    assert r.status_code == 401
    assert r.json()['exc_type'] == 'SessionExpired'
    assert 'person@example.org' not in r.text and 'vertraulich' not in r.text


@pytest.mark.parametrize('fn', ['meine_auskunft', 'mein_loeschantrag', 'loeschung_beantragen'])
def test_ohne_personenzuordnung_kein_fremder_zugriff(client, welt, fn):
    # Das Verwaltungskonto hat absichtlich keinen Personeneintrag.
    r = post(client, fn, bestaetigt=True, mitglied_id='N6-A')
    assert r.status_code == 417
    # P2-1 (OP-UI-15): Der interne Text „Kein Mitglied-Datensatz" ist durch eine
    # verstaendliche Meldung ersetzt; die Aussage (kein Fremdzugriff) bleibt.
    assert 'kein Mitglied zugeordnet' in r.json()['message']


def test_selbstauskunft_ohne_adminrecht_und_ohne_fremdauswahl(client, welt):
    set_user('person@example.org')
    r = post(client, 'meine_auskunft', mitglied_id='N6-B')
    assert r.status_code == 200, r.text
    d = r.json()['message']
    assert d['mitglied']['name'] == 'N6-A'
    assert d['mitglied']['notiz'] == 'vertraulich'
    assert 'geheim' not in str(d) and 'password_hash' not in str(d)
    assert post(client, 'auskunft', mitglied_id='N6-A').status_code == 403


def test_antragsstand_eigen_und_nach_neuladen(client, welt):
    set_user('person@example.org')
    assert post(client, 'mein_loeschantrag').json()['message'] is None
    r = post(client, 'loeschung_beantragen', bestaetigt=True)
    assert r.status_code == 200
    status = post(client, 'mein_loeschantrag', mitglied_id='N6-B').json()['message']
    assert status['mitglied'] == 'N6-A' and status['status'] == 'offen'
    assert status['beantragt_am'] == r.json()['message']['beantragt_am']


def test_alter_sofortloeschweg_verweigert_ohne_datenverlust(client, welt):
    from diakronos_app.frappe_compat import sitzungen
    sid, _ = sitzungen.anlegen('person@example.org')
    set_user('person@example.org')
    r = client.post(PROFIL + 'delete_my_data')
    assert r.status_code == 417
    assert 'Löschantrag' in r.json()['message']
    with welt() as s:
        assert s.get(Mitglied, 'N6-A').vorname == 'Anna'
        assert s.get(User, 'person@example.org').enabled
    assert sitzungen.lesen(sid) is not None


@pytest.fixture
def registrierung(welt):
    with welt.begin() as s:
        m = s.get(Mitglied, 'N6-A')
        m.ancestor_path = 'Privater Pfad'
        m.mitglied_seit = date(2020, 1, 1)
        s.add(Anmeldung(name='N7-eigen', mitglied='N6-A', vorname='Anna', nachname='Beispiel',
                       email='privat@example.org', telefon='01234', geburtstag=date(1990, 1, 1),
                       ip_adresse='192.0.2.1', kommentar='Privater Kommentar',
                       name_freitext='Privater Name', email_freitext='privat@example.org'))
        s.add(Anmeldung(name='N7-fremd', mitglied='N6-B', vorname='Ben'))
        s.add(AnmeldungAntwort(name='N7-antwort', parent='N7-eigen', feldlabel='Private Frage', antwort='Private Antwort'))
        s.add(AnmeldungKind(name='N7-kind', parent='N7-eigen', vorname='Kind', nachname='Beispiel', geburtstag=date(2020, 1, 1)))
        s.add(AnmeldungKind(name='N7-fremdes-kind', parent='N7-fremd', vorname='Fremdes Kind'))
        s.add(MitgliedBereich(name='N7-bereich', parent='N6-A'))
        s.add(MitgliedBeziehung(name='N7-beziehung', parent='N6-A', beziehung_zu='N6-B'))
        s.add(MitgliedBeziehung(name='N7-rueckbeziehung', parent='N6-B', beziehung_zu='N6-A'))
        s.get(Mitglied, 'N6-B').ehepartner = 'N6-A'
    return welt


def antrag_stellen(client, konto):
    """Das MITGLIED stellt den Antrag — die Voraussetzung des N-5-Wegs.

    Vor DSGVO-1c durfte `anonymisieren` auch ohne Antrag löschen (N-5); die
    Löschung läuft jetzt ausschließlich über Antrag → Bestätigung → Mail. Die
    Tests rufen deshalb den echten Weg: erst beantragen, dann bestätigen.
    """
    from diakronos_app.frappe_compat import sitzungen
    sitzungen.anlegen(konto)
    set_user(konto)
    r = post(client, 'loeschung_beantragen', bestaetigt=True)
    assert r.status_code == 200, r.text
    set_user('admin@example.org')


def anonymisieren(client, mitglied='N6-A', konto='person@example.org'):
    antrag_stellen(client, konto)
    return post(client, 'anonymisieren', mitglied_id=mitglied, bestaetigt=True,
                bestaetigung='ANONYMISIEREN')


def test_anonymisierung_bereinigt_registrierungen_und_struktur(client, registrierung):
    assert anonymisieren(client).status_code == 200
    with registrierung() as s:
        a = s.get(Anmeldung, 'N7-eigen')
        for feld in ('vorname', 'nachname', 'email', 'telefon', 'geburtstag', 'ip_adresse',
                     'kommentar', 'name_freitext', 'email_freitext'):
            assert not getattr(a, feld), feld
        assert s.get(AnmeldungAntwort, 'N7-antwort') is None
        assert s.get(AnmeldungKind, 'N7-kind') is None
        assert s.get(Anmeldung, 'N7-fremd').vorname == 'Ben'
        assert s.get(AnmeldungKind, 'N7-fremdes-kind').vorname == 'Fremdes Kind'
        # DSGVO-1b (K1): die alte Kennung (hier der Bestandsname) ist WEG, die
        # Person lebt als Zeile mit neutraler Kennung weiter.
        assert s.get(Mitglied, 'N6-A') is None
        namen = [n for n in s.scalars(select(Mitglied.name)).all()
                 if str(n).startswith('geloescht-')]
        assert len(namen) == 1, namen
        kennung = namen[0]
        m = s.get(Mitglied, kennung)
        assert m.ancestor_path is None and m.mitglied_seit is None
        assert m.nachname == 'Person' and m.name != m.nachname
        assert not s.scalars(select(MitgliedBereich).where(MitgliedBereich.parent == kennung)).all()
        # N7 (wie main): Beziehungen ANDERER zur geloeschten Person werden
        # GELOESCHT, nicht mit `beziehung_zu=None` stehen gelassen — eine
        # Beziehung zu einer Person, die es nicht mehr gibt, ist kein
        # Fachdatum. Die eigenen Zeilen der Person fallen mit `parent`.
        eigenen = s.scalars(select(MitgliedBeziehung).where(
            MitgliedBeziehung.parent == kennung)).all()
        assert eigenen == []
        fremde = s.scalars(select(MitgliedBeziehung).where(
            MitgliedBeziehung.parent == 'N6-B')).all()
        assert fremde == [], [b.beziehung_zu for b in fremde]
        assert s.get(Mitglied, 'N6-B').ehepartner is None


def test_bereinigung_ist_eine_transaktion(client, registrierung):
    engine = registrierung.kw['bind']
    # Der Antrag gehoert zum Vorbereiten, nicht zur geprueften Transaktion:
    # erst beantragen, dann die Falle stellen, dann bestaetigen.
    antrag_stellen(client, 'person@example.org')
    def abbrechen(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith('INSERT INTO AUDIT_LOG'):
            raise RuntimeError('Erzwungener Transaktionsabbruch')
    event.listen(engine, 'before_cursor_execute', abbrechen)
    try:
        with pytest.raises(RuntimeError, match='Transaktionsabbruch'):
            # Bewusst NICHT `anonymisieren()`: der Antrag steht schon, hier
            # zaehlt nur die Bestaetigung unter der Falle.
            post(client, 'anonymisieren', mitglied_id='N6-A', bestaetigt=True,
                 bestaetigung='ANONYMISIEREN')
    finally:
        event.remove(engine, 'before_cursor_execute', abbrechen)
    with registrierung() as s:
        assert s.get(Mitglied, 'N6-A').vorname == 'Anna'
        assert s.get(User, 'person@example.org').enabled
        assert s.get(Anmeldung, 'N7-eigen').vorname == 'Anna'
        assert s.get(AnmeldungAntwort, 'N7-antwort').antwort == 'Private Antwort'
        assert s.get(AnmeldungKind, 'N7-kind').vorname == 'Kind'
        assert s.get(MitgliedBereich, 'N7-bereich') is not None


def test_personenkennung_wird_nicht_zum_anzeigenamen(client, welt):
    """K1: die Kennung (im Betrieb der Klarname) wird NICHT zur Anzeige —
    sie wird durch die neutrale Kennung `geloescht-<hex>` ERSETZT."""
    with welt.begin() as s:
        # Die Person braucht ein Konto: DSGVO-1c (N-5) stellt den Antrag
        # das Mitglied selbst, und ohne Konto gibt es keine antragstellende
        # Sitzung. Bestaetigt wird nachher vom Administrator.
        s.add(User(name='anna@example.org', email='anna@example.org', enabled=True))
        s.add(Mitglied(name='Anna-Klarname', vorname='Anna', nachname='Klarname',
                       user='anna@example.org', email='anna@example.org'))
    r = anonymisieren(client, mitglied='Anna-Klarname', konto='anna@example.org')
    assert r.status_code == 200
    with welt() as s:
        assert s.get(Mitglied, 'Anna-Klarname') is None
        kennung = [n for n in s.scalars(select(Mitglied.name)).all()
                   if str(n).startswith('geloescht-')][0]
        m = s.get(Mitglied, kennung)
        assert m.nachname == 'Person' and m.vorname == 'Gelöschte'
