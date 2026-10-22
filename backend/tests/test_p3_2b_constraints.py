"""Regression: Import-Altlasten bei vorhandenen PostgreSQL-FK korrigieren."""
import os

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from test_p3_2_daten import migration


def test_alle_linkspalten_pro_tabelle_gleichzeitig(engine):
    """Auch ohne PostgreSQL bleibt die Ein-UPDATE-Invariante abgesichert."""
    from diakronos_app.models.base import Base

    updates = []
    with engine.begin() as c:
        for tabelle in ('ablaufplan_position', 'element'):
            daten = {'name': 'kaputt'}
            daten.update({s: '' for t, s, _ in migration().LINKS if t == tabelle})
            c.execute(Base.metadata.tables[tabelle].insert(), daten)

        def merken(conn, cursor, statement, parameters, context, executemany):
            if statement.startswith('UPDATE "'):
                updates.append(statement)
        sa.event.listen(c, 'before_cursor_execute', merken)
        migration().bereinigen(c)
        for tabelle in ('ablaufplan_position', 'element'):
            eigene = [s for s in updates if s.startswith(f'UPDATE "{tabelle}" ')]
            assert len(eigene) == 1
            for t, spalte, _ in migration().LINKS:
                if t == tabelle:
                    assert f'"{spalte}" = CASE' in eigene[0]


@pytest.mark.parametrize('validiert', [True, False])
def test_postgres_fk_bleiben_aktiv_bei_leerwerten_und_waisen(validiert):
    url = os.environ.get('P32_TEST_DATABASE_URL')
    if not url:
        pytest.skip('P32_TEST_DATABASE_URL: eigener Wegwerf-PostgreSQL erforderlich')
    engine = sa.create_engine(url)
    m = migration()
    try:
        with engine.connect() as c, c.begin():
            # Transaktionales, eigenes Schema: kein Eingriff in Anwendungsdaten.
            c.execute(sa.text('CREATE SCHEMA p32b_regression'))
            c.execute(sa.text('SET LOCAL search_path = p32b_regression'))
            for ziel in dict.fromkeys(z for _, _, z in m.LINKS):
                c.execute(sa.text(f'CREATE TABLE "{ziel}" (name text PRIMARY KEY)'))
            for tabelle in dict.fromkeys(t for t, _, _ in m.LINKS):
                spalten = ', '.join(f'"{s}" text' for t, s, _ in m.LINKS if t == tabelle)
                c.execute(sa.text(f'CREATE TABLE "{tabelle}" (name text PRIMARY KEY, {spalten})'))
            for t, s, z in m.LINKS:
                c.execute(sa.text(f'ALTER TABLE "{t}" ADD CONSTRAINT "{t}_{s}_fkey" '
                                  f'FOREIGN KEY ("{s}") REFERENCES "{z}" (name)'
                                  + ('' if validiert else ' NOT VALID')))
            for tabelle in ('liedgruppe_lied', 'dienstplan_position'):
                c.execute(sa.text(f'CREATE TABLE {tabelle} (fassung text REFERENCES liedfassung(name))'))
            c.execute(sa.text('CREATE TABLE lied_material (parenttype text, parent text)'))
            c.execute(sa.text('CREATE TABLE beitrag (name text PRIMARY KEY)'))
            c.execute(sa.text('CREATE TABLE beitrag_kommentar (parenttype text, parent text)'))
            c.execute(sa.text('SET LOCAL session_replication_role = replica'))
            for tabelle in dict.fromkeys(t for t, _, _ in m.LINKS):
                spalten = [s for t, s, _ in m.LINKS if t == tabelle]
                for name, wert in [('leer', ''), ('waise', 'fehlt')]:
                    namen = ', '.join(f'"{s}"' for s in spalten)
                    werte = ', '.join(':wert' for _ in spalten)
                    c.execute(sa.text(f'INSERT INTO "{tabelle}" (name, {namen}) VALUES (:name, {werte})'),
                              {'name': name, 'wert': wert})
            c.execute(sa.text("INSERT INTO liedgruppe_lied VALUES ('waise')"))
            c.execute(sa.text("INSERT INTO dienstplan_position VALUES ('waise')"))
            c.execute(sa.text("INSERT INTO lied_material VALUES ('Liedfassung', 'waise')"))
            c.execute(sa.text("INSERT INTO beitrag_kommentar VALUES ('Beitrag', 'fehlt')"))
            c.execute(sa.text('SET LOCAL session_replication_role = origin'))
            m.op = Operations(MigrationContext.configure(c))
            m.upgrade()
            assert not any(m.bereinigen(c).values()), 'zweiter Lauf muss wirkungslos sein'
            for t, s, _ in m.LINKS:
                assert c.execute(sa.text(f'SELECT count(*) FROM "{t}" WHERE "{s}" IS NOT NULL')).scalar_one() == 0
            assert c.execute(sa.text('SELECT fassung FROM liedgruppe_lied')).scalar_one() is None
            assert c.execute(sa.text('SELECT count(*) FROM lied_material')).scalar_one() == 0
            assert c.execute(sa.text('SELECT count(*) FROM beitrag_kommentar')).scalar_one() == 0
            assert c.execute(sa.text("SELECT count(*) FROM pg_constraint WHERE connamespace = 'p32b_regression'::regnamespace AND contype = 'f' AND NOT convalidated")).scalar_one() == 0
            c.rollback()
    finally:
        engine.dispose()
