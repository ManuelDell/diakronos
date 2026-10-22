"""P3-2: Waisen, Import-Nachkontrolle, konstante Abfragen und Ortszeit."""
from datetime import datetime
import importlib.util
from pathlib import Path
import sys

import pytest
from sqlalchemy import text


def importwerkzeug():
    tools = Path(__file__).resolve().parents[1] / "tools"
    if not tools.exists():
        tools = Path(__file__).resolve().parents[2] / "tools"
    sys.path.insert(0, str(tools))
    import import_aus_frappe
    return import_aus_frappe


def migration():
    pfad = Path(__file__).resolve().parents[1] / "alembic/versions/p32_datenbereinigung.py"
    spec = importlib.util.spec_from_file_location("p32_migration", pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_bld_01_02_03_05_und_kommentare_bereinigen_idempotent(engine):
    # SQLite ohne FK-Checks bildet den damaligen replica-Import ab.
    with engine.begin() as c:
        from diakronos_app.models.base import Base
        for tabelle, daten in [
            ('lied', [{'name': 'gut'}]),
            ('liedfassung', [{'name': 'waise', 'lied': 'fehlt'}, {'name': 'ok', 'lied': 'gut'}]),
            ('audit_log', [{'name': 'historie', 'policy_triggered': 'fehlt'}]),
            ('mitglied_bereich', [{'name': 'waise', 'dienstbereich': 'fehlt'}]),
            ('element', [{'name': 'e', 'element_category': '', 'ressource': ''}]),
            ('ablaufplan_position', [{'name': 'a', 'gruppe': '', 'referenz_doctype': '', 'verantwortlicher': ''}]),
            ('beitrag', [{'name': 'gut', 'veroeffentlicht': True}]),
            ('beitrag_kommentar', [{'name': 'waise', 'parent': 'fehlt', 'parenttype': 'Beitrag'},
                                  {'name': 'ok', 'parent': 'gut', 'parenttype': 'Beitrag'}]),
        ]:
            c.execute(Base.metadata.tables[tabelle].insert(), daten)
        m = migration()
        m.bereinigen(c)
        m.bereinigen(c)
        assert c.execute(text("SELECT name FROM liedfassung ORDER BY name")).scalars().all() == ['ok']
        assert c.execute(text("SELECT policy_triggered FROM audit_log WHERE name='historie'")).scalar() is None
        assert c.execute(text("SELECT count(*) FROM audit_log")).scalar() == 1
        assert c.execute(text("SELECT count(*) FROM mitglied_bereich")).scalar() == 0
        assert c.execute(text("SELECT element_category,ressource FROM element")).one() == (None, None)
        assert c.execute(text("SELECT gruppe,referenz_doctype,verantwortlicher FROM ablaufplan_position")).one() == (None, None, None)
        assert c.execute(text("SELECT name FROM beitrag_kommentar")).scalars().all() == ['ok']


def test_import_leere_links_sind_null_freitext_bleibt_leer(monkeypatch):
    m = importwerkzeug()
    t = m.DocTypeTarget('Test', 'test', False, False,
                        [m.Column('link', 'link'), m.Column('titel', 'text')])
    monkeypatch.setattr(m, 'existing_pg_columns', lambda *_: ['name', 'link', 'titel'])
    class Conn:
        def execute(self, stmt, daten):
            assert daten == [{'name': 'eins', 'link': None, 'titel': ''},
                             {'name': 'zwei', 'link': None, 'titel': None}]
    m.import_table(Conn(), t, m.TableData(['name', 'link', 'titel'],
                   [['eins', '', ''], ['zwei', None, None]]), dry_run=False, report={})
    assert m._fieldtype_to_kind('Link') == 'link'


def test_import_waisenpruefung_zaehlt_ohne_personendaten(monkeypatch, engine):
    m = importwerkzeug()
    import import_pruefung
    monkeypatch.setattr(import_pruefung, 'load_link_fields', lambda: [('Kind', 'link', 'Ziel')])
    kind = m.DocTypeTarget('Kind', 'kind', False, False, [m.Column('link', 'link')])
    ziel = m.DocTypeTarget('Ziel', 'ziel', False, False, [])
    tables = {'tabKind': m.TableData(['name', 'link'], [['k', 'fehlt']]),
              'tabZiel': m.TableData(['name'], [['ok']])}
    with engine.begin() as c:
        c.execute(text('CREATE TABLE kind (name TEXT, link TEXT)'))
        c.execute(text('CREATE TABLE ziel (name TEXT)'))
        c.execute(text("INSERT INTO kind VALUES ('k','fehlt')"))
        c.execute(text("INSERT INTO ziel VALUES ('ok')"))
        monkeypatch.setattr(import_pruefung, 'existing_pg_columns', lambda _, t: ['name', 'link'] if t == 'kind' else ['name'])
        report = {}
        m.pruefe_import_links(c, tables, [kind], [ziel], report)
        assert report['waisenpruefung']['quelle_verwaist'] == 1
        assert report['waisenpruefung']['import_verwaist'] == 0
        assert 'fehlt' not in str(report) and "'k'" not in str(report)


@pytest.mark.parametrize('weg', ['methode', 'resource'])
def test_op_handy_27_beitrag_loeschen_nimmt_nur_eigene_kommentare_mit(client, patched_db, weg):
    from diakronos_app.models.diakonos import Beitrag, BeitragKommentar
    from diakronos_app.models.core import HasRole, Role
    with patched_db.begin() as s:
        s.add(Role(name='System Manager'))
        s.flush()
        s.add(HasRole(name='adminrolle', parent='Administrator', parenttype='User',
                      parentfield='roles', role='System Manager'))
        s.add_all([Beitrag(name='eins'), Beitrag(name='zwei')])
        s.flush()
        s.add_all([BeitragKommentar(name='k1', parent='eins', parenttype='Beitrag', parentfield='kommentare'),
                   BeitragKommentar(name='k2', parent='zwei', parenttype='Beitrag', parentfield='kommentare')])
    if weg == 'resource':
        r = client.delete('/api/resource/Beitrag/eins')
        assert r.status_code == 202, r.text
    else:
        r = client.post('/api/method/diakronos.diakonos.api.beitraege.delete_beitrag', json={'beitrag_id': 'eins'})
        assert r.status_code == 200, r.text
    with patched_db() as s:
        assert s.get(Beitrag, 'eins') is None
        assert s.get(BeitragKommentar, 'k1') is None
        assert s.get(BeitragKommentar, 'k2') is not None


def test_bld_06_hierarchie_braucht_nicht_eine_abfrage_je_gruppe(monkeypatch):
    from diakronos_app.api import gruppen as g
    monkeypatch.setattr(g, '_is_admin', lambda: True)
    aufrufe = []
    def laden(typ, **kwargs):
        aufrufe.append(typ)
        if typ == 'Gruppe':
            return [dict(name=str(i), gruppenname=str(i), dienstbereich=None, gruppentyp=None,
                         status='Aktiv', sichtbarkeit='Oeffentlich', beschreibung=None) for i in range(50)]
        if typ == 'Untergruppe':
            return [dict(name='u', gruppe='0', untergruppenname='U', status='Aktiv', sichtbarkeit='Oeffentlich', beschreibung=None)]
        if typ == 'Gruppenmitgliedschaft':
            return [{'parent': '0'}, {'parent': '0'}]
        if typ == 'Untergruppenmitgliedschaft':
            return [{'parent': 'u'}]
        raise AssertionError(typ)
    monkeypatch.setattr(g, 'get_all', laden)
    monkeypatch.setattr(g, '_count', lambda *_: pytest.fail('N+1-Zaehler benutzt'))
    result = g.get_gruppen_hierarchie()['gruppen']
    assert len(aufrufe) == 4
    assert result[0]['mitglieder_count'] == 2
    assert result[0]['untergruppen'][0]['mitglieder_count'] == 1


@pytest.mark.parametrize('eingabe,erwartet', [
    ('2026-07-01T08:00:00Z', '2026-07-01 10:00:00'),
    ('2026-12-01T08:00:00+00:00', '2026-12-01 09:00:00'),
    ('2026-07-01T10:00:00+02:00', '2026-07-01 10:00:00'),
    ('2026-07-01T10:00:00', '2026-07-01 10:00:00'),
    ('2026-07-01 10:00', '2026-07-01 10:00:00'),
])
def test_bld_07_aware_zeiten_werden_gemeindeortszeit(monkeypatch, eingabe, erwartet):
    from diakronos_app.api.kronos.event_crud import parse_iso_datetime_raw
    from diakronos_app.settings import settings
    monkeypatch.setattr(settings, 'calendar_timezone', 'Europe/Berlin')
    assert parse_iso_datetime_raw(eingabe) == erwartet


def test_bld_07_konfigurierte_zeitzone(monkeypatch):
    from diakronos_app.api.kronos.event_crud import parse_iso_datetime_raw
    from diakronos_app.settings import settings
    monkeypatch.setattr(settings, 'calendar_timezone', 'America/New_York')
    assert parse_iso_datetime_raw('2026-07-01T08:00:00Z') == '2026-07-01 04:00:00'


# ── DES-REST-b, K2: reines Datum (ganztägig) darf nicht scheitern ───────────
#
# Befund: Der ganztägige Zweig im Termin-Dialog sendet seit OP-UI-20 nur noch
# „2026-03-05“ statt „2026-03-05 00:00“. Das muss der Server unverändert
# annehmen — und zwar als Beginn 00:00 des genannten Tages, nicht als Fehler.


@pytest.mark.parametrize('eingabe,erwartet', [
    ('2026-03-05', '2026-03-05 00:00:00'),
    ('2026-03-05T00:00', '2026-03-05 00:00:00'),
    ('2026-03-05 00:00', '2026-03-05 00:00:00'),
    # Mehrtägig ganztägig: das Ende trägt sein eigenes Datum.
    ('2026-03-08', '2026-03-08 00:00:00'),
])
def test_des_rest_b_k2_reines_datum_ist_ganztags_gueltig(eingabe, erwartet):
    from diakronos_app.api.kronos.event_crud import parse_iso_datetime_raw
    assert parse_iso_datetime_raw(eingabe) == erwartet


def test_des_rest_b_k2_reines_datum_verschiebt_sich_nicht_ueber_zeitzonen(monkeypatch):
    # Ein nacktes Datum ist ein Kalendertag, kein Zeitpunkt: Die Gemeinde-
    # Zeitzone darf den Tag nicht verschieben (sonst würde aus dem 05.03. je
    # nach Einstellung der 04.03.).
    from diakronos_app.api.kronos.event_crud import parse_iso_datetime_raw
    from diakronos_app.settings import settings
    for zone in ('Europe/Berlin', 'America/New_York', 'Pacific/Auckland'):
        monkeypatch.setattr(settings, 'calendar_timezone', zone)
        assert parse_iso_datetime_raw('2026-03-05') == '2026-03-05 00:00:00', zone


def test_des_rest_b_k2_datum_bleibt_auch_bei_quelltext_gleich():
    # Gegenprobe zur Vorschau: derselbe Tag, wie das Frontend ihn baut.
    from diakronos_app.api.kronos.event_crud import parse_iso_datetime_raw
    assert parse_iso_datetime_raw('2026-02-23') == parse_iso_datetime_raw('2026-02-23 00:00')
