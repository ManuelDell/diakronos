"""P2-1: ausdrücklich beauftragte Restpunkte R1/R2/R3 von P1-10b."""
import pytest
from test_p1_10_lieder_material import welt, als_bruno, als_anna, als_admin, BRUNO
from diakronos_app.planrahmen.dienste import Dienste, DienstFehler


@pytest.mark.parametrize('owner,typ,ziel', [(None, None, None), (BRUNO, 'Liedfassung', 'andere-fassung'), (BRUNO, None, 'anderes-ziel')])
def test_dateibindung_schuetzt_owner_und_vorhandenes_ziel(welt, owner, typ, ziel):
    from diakronos_app.models.core import FileModel
    datei = FileModel(name='p21-datei', file_name='p21.pdf', file_url='/private/files/p21.pdf', owner=owner,
                      attached_to_doctype=typ, attached_to_name=ziel)
    welt.add(datei)
    welt.commit()
    with pytest.raises(DienstFehler):
        Dienste(welt, BRUNO)._datei_an_liedfassung_binden('/private/files/p21.pdf', 'FAS-1')
    assert datei.attached_to_doctype == typ
    assert datei.attached_to_name == ziel


def test_dateibindung_eigene_datei_ist_idempotent(welt):
    from diakronos_app.models.core import FileModel
    datei = FileModel(name='p21-datei', file_name='p21.pdf', file_url='/private/files/p21.pdf', owner=BRUNO)
    welt.add(datei)
    welt.commit()
    dienst = Dienste(welt, BRUNO)
    dienst._datei_an_liedfassung_binden('/private/files/p21.pdf', 'FAS-1')
    dienst._datei_an_liedfassung_binden('/private/files/p21.pdf', 'FAS-1')
    assert datei.attached_to_name == 'FAS-1'


@pytest.mark.parametrize('status,streaming', [('gemeinfrei', False), ('geschuetzt', False), ('gesperrt', True)])
def test_audio_sperre_genuegt_allein(welt, als_anna, status, streaming):
    from diakronos_app.models.psalmos import Lied
    from diakronos_app.files import attachment_allowed
    lied = welt.get(Lied, 'LIED-1')
    lied.rechte_status = status
    lied.streaming_erlaubt = streaming
    welt.commit()
    assert attachment_allowed('Liedfassung', 'FAS-1', dateiname='lied.mp3') is False
    assert attachment_allowed('Liedfassung', 'FAS-1', dateiname='noten.pdf') is True


def test_audio_sperre_musikverantwortlicher_bleibt_berechtigt(welt, als_bruno):
    from diakronos_app.files import attachment_allowed
    assert attachment_allowed('Liedfassung', 'FAS-1', dateiname='lied.mp3') is True


def test_liedgruppe_verweist_auf_gemeindegruppe(client, als_bruno):
    r = client.post('/api/method/diakronos.psalmos.api.musik.save_liedgruppe', json={'daten': {
        'gruppenname': 'Neue Sammlung', 'typ': 'Sammlung', 'gruppe': 'GRP-WORSHIP'}})
    assert r.status_code == 200, r.text


def test_unbekannte_gemeindegruppe_wird_verstaendlich_abgelehnt(client, als_bruno):
    r = client.post('/api/method/diakronos.psalmos.api.musik.save_liedgruppe', json={'daten': {
        'gruppenname': 'Neue Sammlung', 'typ': 'Sammlung', 'gruppe': 'nicht-da'}})
    assert r.status_code == 417, r.text
    assert 'Gruppe' in r.json()['message']


def test_k9_kataloge_sortieren_umlaute_wie_grundbuchstaben(client, als_anna, welt):
    """Alle Katalogwerte bleiben sichtbar, auch ohne ein zugeordnetes Lied."""
    from diakronos_app.models.psalmos import Liedgruppe, Liedkategorie, Liedanlass
    for modell, feld in [(Liedgruppe, 'gruppenname'), (Liedkategorie, 'kategoriename'), (Liedanlass, 'anlassname')]:
        for i, text in enumerate(['Zusage', 'Übermut', 'Ähre', 'Ölberg', 'Andacht', 'Straße', 'Strasse']):
            welt.add(modell(name=f'p21-k9-{modell.__tablename__}-{i}', **{feld: text}))
    welt.commit()
    antwort = client.get('/api/method/diakronos.psalmos.api.musik.get_lied_filteroptionen')
    assert antwort.status_code == 200, antwort.text
    for feld in ['gruppen', 'kategorien', 'anlaesse']:
        werte = [wert for wert in antwort.json()['message'][feld]
                 if wert in {'Zusage', 'Übermut', 'Ähre', 'Ölberg', 'Andacht', 'Straße', 'Strasse'}]
        assert werte == ['Ähre', 'Andacht', 'Ölberg', 'Strasse', 'Straße', 'Übermut', 'Zusage']
