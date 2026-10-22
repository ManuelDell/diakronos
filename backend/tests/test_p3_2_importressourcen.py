"""R1: echte Import-Metadaten und transaktionale Nachkontrolle im Image."""
import os
from pathlib import Path
import sys

import pytest
import sqlalchemy as sa

_tools = Path(__file__).resolve().parents[1] / 'tools'
if not _tools.exists():
    _tools = Path(__file__).resolve().parents[2] / 'tools'
sys.path.insert(0, str(_tools))
import import_aus_frappe as imp
import import_pruefung as pruefung


def test_echte_import_loader_ohne_quellbaum():
    targets, spalten = imp.load_targets()
    assert len(targets) == 73
    mitglied = next(t for t in targets if t.doctype == 'Mitglied')
    assert mitglied.table == 'mitglied'
    assert 'name' not in spalten['Mitglied']
    assert ('Anmeldung', 'mitglied', 'Mitglied') in pruefung.load_link_fields()
    core = imp.core_targets()
    assert len(core) == 8
    user = next(t for t in core if t.doctype == 'User')
    assert {'name', 'email', 'enabled'} <= {c.name for c in user.columns}
    assert not imp._SECRET_COLUMNS.intersection(c.name for c in user.columns)
    report = {}
    imp.pruefe_import_links(None, {}, targets, core, report)
    assert report['waisenpruefung'] == dict(link_felder_geprueft=0,
        quelle_verwaist=0, import_verwaist=0, unpruefbar=0)


@pytest.fixture
def import_pg():
    # Ausschliesslich explizit freigegebene Wegwerf-DB; nie settings/Betriebs-DB.
    url = os.environ.get('P32_IMPORT_TEST_DATABASE_URL')
    if not url:
        pytest.skip('P32_IMPORT_TEST_DATABASE_URL fuer isolierte PostgreSQL-Abnahme setzen')
    engine = sa.create_engine(url)
    with engine.connect() as conn:
        assert conn.execute(sa.text('SELECT current_database()')).scalar() == 'p32_import_test'
    with engine.begin() as conn:
        conn.execute(sa.text('CREATE TABLE IF NOT EXISTS mitglied (name TEXT PRIMARY KEY)'))
        conn.execute(sa.text('CREATE TABLE IF NOT EXISTS anmeldung (name TEXT PRIMARY KEY, mitglied TEXT, titel TEXT)'))
        conn.execute(sa.text('TRUNCATE anmeldung, mitglied'))
        conn.execute(sa.text("INSERT INTO anmeldung VALUES ('bestand', NULL, 'bleibt')"))
    yield engine
    engine.dispose()


@pytest.mark.parametrize('fall', ['quelle', 'import', 'unpruefbar', 'gueltig'])
def test_echte_nachkontrolle_commit_oder_rollback(import_pg, fall):
    targets, _ = imp.load_targets()
    core = imp.core_targets()
    target = next(t for t in targets if t.doctype == 'Anmeldung')
    # Echte Link-/Typdefinitionen; nur die minimalen Quell-/Zielzeilen variieren.
    quelle = {'tabAnmeldung': imp.TableData(['name', 'mitglied', 'titel'],
        [['neu', 'ziel', ''], ['leer', '', '']])}
    if fall != 'unpruefbar':
        quelle['tabMitglied'] = imp.TableData(['name'], [] if fall == 'quelle' else [['ziel']])
    report = {}

    def importieren():
        with import_pg.begin() as conn:
            conn.execute(sa.text('TRUNCATE anmeldung'))
            if fall == 'gueltig':
                conn.execute(sa.text("INSERT INTO mitglied VALUES ('ziel')"))
            imp.import_table(conn, target, quelle['tabAnmeldung'], dry_run=False, report=report)
            imp.pruefe_import_links(conn, quelle, targets, core, report)

    if fall in ('import', 'unpruefbar'):
        with pytest.raises(RuntimeError, match='Link-Prüfung fehlgeschlagen'):
            importieren()
        assert report['waisenpruefung']['import_verwaist' if fall == 'import' else 'unpruefbar'] == 1
        with import_pg.connect() as conn:
            assert conn.execute(sa.text('SELECT name, titel FROM anmeldung')).all() == [('bestand', 'bleibt')]
    else:
        importieren()
        assert report['waisenpruefung']['quelle_verwaist'] == (1 if fall == 'quelle' else 0)
        with import_pg.connect() as conn:
            assert conn.execute(sa.text("SELECT mitglied, titel FROM anmeldung WHERE name='leer'")).one() == (None, '')
            assert conn.execute(sa.text('SELECT count(*) FROM anmeldung')).scalar() == 2
    assert 'ziel' not in str(report) and 'neu' not in str(report)


def test_echter_importstart_rollt_bei_unpruefbarer_waise_zurueck(import_pg, tmp_path, monkeypatch):
    dump = tmp_path / 'quelle.sql'
    dump.write_text("INSERT INTO `tabAnmeldung` (`name`, `mitglied`, `titel`) VALUES ('neu', 'fehlt', '');\n", encoding='utf-8')
    monkeypatch.setattr(sys, 'argv', ['import_aus_frappe.py', '--dump', str(dump),
        '--database-url', import_pg.url.render_as_string(hide_password=False)])
    with pytest.raises(RuntimeError, match='Link-Prüfung fehlgeschlagen'):
        imp.main()
    with import_pg.connect() as conn:
        assert conn.execute(sa.text('SELECT name, titel FROM anmeldung')).all() == [('bestand', 'bleibt')]
        assert conn.execute(sa.text('SHOW session_replication_role')).scalar() == 'origin'
