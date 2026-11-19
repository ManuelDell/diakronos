"""CHAT-4a gegen ein WEGWERF-PostgreSQL 17: Migration ``chat4a_glocke``.

Der SQLite-Lauf (``test_chat4a_glocke.py``) belegt die Fachlogik und den
Rundlauf der Migration; PostgreSQL 17 prüft, was SQLite nicht kann:
Fremdschlüssel, Spaltentypen und der Betriebsweg ``alembic upgrade head``.

Geprüft wird:
  * ``upgrade head`` legt ``chat_glocke`` mit PK (gespraech, benutzer),
    drei Fremdschlüsseln und dem Index an
  * der zusammengesetzte Primärschlüssel hält: eine zweite Zeile derselben
    Person im selben Gespräch ist nicht möglich
  * ``stand`` verweist auf ``chat_nachricht`` — ein unbekannter Wert scheitert
  * zweiter ``upgrade``-Lauf ändert nichts (Idempotenz, wie im Entrypoint)
  * ``downgrade`` → ``upgrade`` läuft rund
  * ``alembic check``: das Modell ist migrationsfrei

Aufruf (Karte CHAT-4a):

    docker network create chat4a-net
    docker run -d --name chat4a-pg --network chat4a-net \\
      -e POSTGRES_USER=chat4a -e POSTGRES_PASSWORD=chat4a -e POSTGRES_DB=chat4a \\
      postgres:17-alpine
    docker run --rm --network chat4a-net --entrypoint python -v <wt>:/repo:ro \\
      -w /repo/backend -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 \\
      -e CHAT4A_PG_URL=postgresql+psycopg://chat4a:chat4a@chat4a-pg:5432/chat4a \\
      <vorbau> -m pytest -q -p no:cacheprovider --timeout=900 tests/test_chat4a_pg.py

``--timeout=900`` ist PFLICHT (CHAT-4b, Restpunkt d): der Lauf braucht rund
400 s — ``upgrade head`` der GANZEN Kette auf einem frischen PostgreSQL,
zweimal. Mit dem pytest-Default (bzw. einem kurzen Zeitlimit) bricht er
grundlos ab. Ohne ``CHAT4A_PG_URL`` werden die Tests ÜBERSPRUNGEN — dieser Test
fasst NIE eine Betriebsdatenbank an (dieselbe Regel wie ``test_chat6_pg``).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PG_URL = os.environ.get("CHAT4A_PG_URL", "").strip()
BACKEND = Path(__file__).resolve().parents[1]
ALEMBIC_TIMEOUT = int(os.environ.get("CHAT4A_ALEMBIC_TIMEOUT", "600"))

pg = pytest.mark.skipif(
    not PG_URL, reason="CHAT4A_PG_URL nicht gesetzt — PG-Lauf nur mit Wegwerf-PostgreSQL"
)


def _sql(anweisung: str, **werte):
    import sqlalchemy as sa

    engine = sa.create_engine(PG_URL, future=True)
    try:
        with engine.begin() as conn:
            ergebnis = conn.execute(sa.text(anweisung), werte)
            return list(ergebnis.all()) if ergebnis.returns_rows else []
    finally:
        engine.dispose()


def _alembic(*befehle: str) -> str:
    env = dict(os.environ)
    env["DATABASE_URL"] = PG_URL
    env.setdefault("SECRET_KEY", "test-only-secret-key-never-use-in-production")
    ergebnis = subprocess.run(
        [sys.executable, "-m", "alembic", *befehle],
        cwd=str(BACKEND), env=env, capture_output=True, text=True,
        timeout=ALEMBIC_TIMEOUT,
    )
    if ergebnis.returncode != 0:
        raise AssertionError(
            f"alembic {' '.join(befehle)} exit {ergebnis.returncode}\n"
            f"--- stdout ---\n{ergebnis.stdout[-4000:]}\n"
            f"--- stderr ---\n{ergebnis.stderr[-4000:]}"
        )
    return f"{ergebnis.stdout}\n{ergebnis.stderr}"


def _leere_db() -> None:
    _sql("DROP SCHEMA IF EXISTS public CASCADE")
    _sql("CREATE SCHEMA public")


def _bis_chat6() -> None:
    """Bestand herstellen: die Kette bis UNMITTELBAR VOR ``chat4a_glocke``."""
    _alembic("upgrade", "chat5_umfrage")


def _gespraech_und_nachricht() -> None:
    for konto in ("anna@x.org", "bert@x.org"):
        _sql('INSERT INTO "user" (name, email, full_name, enabled) '
             "VALUES (:n, :n, :n, true)", n=konto)
    _sql("INSERT INTO chat_gespraech (name, art, gruppe) VALUES ('G-1', 'gruppe', 'Chor')")
    _sql("INSERT INTO chat_nachricht (name, gespraech, autor_benutzer, text, erstellt_am) "
         "VALUES ('N-1', 'G-1', 'anna@x.org', 'Text', '2026-11-18 09:00:00')")


@pg
def test_upgrade_legt_chat_glocke_mit_pk_fks_und_index_an():
    _leere_db()
    _bis_chat6()
    _gespraech_und_nachricht()

    assert not _sql("SELECT to_regclass('public.chat_glocke') IS NOT NULL AS da")[0][0]
    _alembic("upgrade", "head")
    assert _sql("SELECT to_regclass('public.chat_glocke') IS NOT NULL AS da")[0][0]

    spalten = dict(_sql(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = 'chat_glocke'"
    ))
    assert set(spalten) == {"gespraech", "benutzer", "stand", "stand_am",
                            "stand_nachricht", "merker_am", "geglockt_am", "gelesen_am"}
    assert spalten["geglockt_am"] == "timestamp without time zone"
    assert spalten["merker_am"] == "timestamp without time zone"
    assert spalten["stand_am"] == "timestamp without time zone"

    pk = _sql(
        "SELECT a.attname FROM pg_index i "
        "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
        "WHERE i.indrelid = 'chat_glocke'::regclass AND i.indisprimary "
        "ORDER BY array_position(i.indkey, a.attnum)"
    )
    assert [z[0] for z in pk] == ["gespraech", "benutzer"]

    ziele = set(_sql(
        "SELECT kcu.column_name, ccu.table_name FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu "
        "  ON kcu.constraint_name = tc.constraint_name "
        "JOIN information_schema.constraint_column_usage ccu "
        "  ON ccu.constraint_name = tc.constraint_name "
        "WHERE tc.table_name = 'chat_glocke' AND tc.constraint_type = 'FOREIGN KEY'"
    ))
    assert ("gespraech", "chat_gespraech") in ziele
    assert ("benutzer", "user") in ziele
    assert ("stand", "chat_nachricht") in ziele

    indizes = {z[0] for z in _sql(
        "SELECT indexname FROM pg_indexes WHERE tablename = 'chat_glocke'")}
    assert "ix_chat_glocke_gespraech" in indizes
    assert "ix_chat_glocke_benutzer" in indizes
    # Review R1/f: der Merker darf eine geloeschte Nachricht ueberleben.
    set_null = _sql(
        "SELECT rc.delete_rule FROM information_schema.referential_constraints rc "
        "JOIN information_schema.table_constraints tc "
        "  ON tc.constraint_name = rc.constraint_name "
        "JOIN information_schema.key_column_usage kcu "
        "  ON kcu.constraint_name = tc.constraint_name "
        "WHERE tc.table_name = 'chat_glocke' AND kcu.column_name = 'stand'"
    )
    assert [z[0] for z in set_null] == ["SET NULL"], set_null


@pg
def test_nachricht_loeschen_nullt_den_stand_aber_nicht_den_merker():
    """CHAT-8 loescht Nachrichten: ``stand`` wird genullt, ``stand_am`` bleibt."""
    _leere_db()
    _bis_chat6()
    _gespraech_und_nachricht()
    _alembic("upgrade", "head")

    _sql("INSERT INTO chat_glocke (gespraech, benutzer, stand, stand_am, merker_am) "
         "VALUES ('G-1', 'anna@x.org', 'N-1', '2026-11-18 09:00:00', "
         "'2026-11-18 09:00:00')")
    _sql("DELETE FROM chat_nachricht WHERE name = 'N-1'")
    zeile = _sql("SELECT stand, stand_am, merker_am FROM chat_glocke")[0]
    assert zeile[0] is None                      # Verweis weg …
    assert zeile[1] is not None and zeile[2] is not None  # … Merker bleibt


@pg
def test_zwei_laeufe_sperren_sich_gegenseitig():
    """Review R1/e: ``pg_try_advisory_xact_lock`` laesst nur EINEN Lauf arbeiten."""
    import sqlalchemy as sa

    from diakronos_app.api.chat import GLOCKE_SPERRE

    _leere_db()
    _bis_chat6()
    _alembic("upgrade", "head")

    engine = sa.create_engine(PG_URL, future=True)
    try:
        with engine.connect() as eins, engine.connect() as zwei:
            # Jede Verbindung führt GENAU EINE offene Transaktion (``begin()``
            # wirft sonst, weil das SELECT schon eine begonnen hat).
            eins.exec_driver_sql("BEGIN")
            assert eins.execute(sa.text("SELECT pg_try_advisory_xact_lock(:k)"),
                                {"k": GLOCKE_SPERRE}).scalar() is True
            # Der zweite Lauf bekommt die Sperre NICHT — er tut nichts.
            zwei.exec_driver_sql("BEGIN")
            assert zwei.execute(sa.text("SELECT pg_try_advisory_xact_lock(:k)"),
                                {"k": GLOCKE_SPERRE}).scalar() is False
            eins.exec_driver_sql("COMMIT")
            zwei.exec_driver_sql("COMMIT")
            # Nach dem Ende der Transaktion ist sie wieder frei.
            zwei.exec_driver_sql("BEGIN")
            assert zwei.execute(sa.text("SELECT pg_try_advisory_xact_lock(:k)"),
                                {"k": GLOCKE_SPERRE}).scalar() is True
            zwei.exec_driver_sql("COMMIT")
    finally:
        engine.dispose()


@pg
def test_zwei_laeufe_schreiben_nur_eine_glocke():
    """Review R1/e auf dem ECHTEN Weg: der zweite Lauf tut nichts.

    ``_lauf_sperren`` nimmt die Sitzungssperre; solange ein Lauf sie hält,
    steigt der zweite sofort aus (``0`` Glocken) — statt dieselbe
    Benachrichtigung ein zweites Mal zu schreiben.
    """
    import sqlalchemy as sa

    from diakronos_app.api import chat as C

    _leere_db()
    _alembic("upgrade", "head")
    _gespraech_und_nachricht()

    engine = sa.create_engine(PG_URL, future=True)
    halter = engine.connect()
    try:
        halter.exec_driver_sql("BEGIN")
        assert halter.execute(sa.text("SELECT pg_try_advisory_xact_lock(:k)"),
                              {"k": C.GLOCKE_SPERRE}).scalar() is True

        lauf = sa.create_engine(PG_URL, future=True)
        try:
            with sa.orm.Session(lauf) as s, s.begin():
                assert C._lauf_sperren(s) is False
        finally:
            lauf.dispose()
    finally:
        halter.exec_driver_sql("COMMIT")
        halter.close()
        engine.dispose()

    # Ohne Halter nimmt der Lauf die Sperre.
    frei = sa.create_engine(PG_URL, future=True)
    try:
        with sa.orm.Session(frei) as s, s.begin():
            assert C._lauf_sperren(s) is True
    finally:
        frei.dispose()


@pg
def test_pk_verhindert_zweite_zeile_und_stand_muss_existieren():
    _leere_db()
    _bis_chat6()
    _gespraech_und_nachricht()
    _alembic("upgrade", "head")

    _sql("INSERT INTO chat_glocke (gespraech, benutzer, stand, geglockt_am) "
         "VALUES ('G-1', 'anna@x.org', 'N-1', '2026-11-18 10:00:00')")
    # Zweite Zeile derselben Person im selben Gespräch: der PK hält.
    with pytest.raises(Exception):
        _sql("INSERT INTO chat_glocke (gespraech, benutzer) "
             "VALUES ('G-1', 'anna@x.org')")
    # Andere Person im selben Gespräch ist erlaubt.
    _sql("INSERT INTO chat_glocke (gespraech, benutzer) VALUES ('G-1', 'bert@x.org')")
    # ``stand`` ist ein echter Verweis auf eine Nachricht.
    with pytest.raises(Exception):
        _sql("INSERT INTO chat_glocke (gespraech, benutzer, stand) "
             "VALUES ('G-1', 'anna@x.org', 'gibt-es-nicht')")
    assert _sql("SELECT count(*) FROM chat_glocke")[0][0] == 2


@pg
def test_zweiter_upgrade_idempotent_und_rundlauf():
    _leere_db()
    _bis_chat6()
    _gespraech_und_nachricht()
    _alembic("upgrade", "head")
    _sql("INSERT INTO chat_glocke (gespraech, benutzer) VALUES ('G-1', 'anna@x.org')")

    # Der Entrypoint ruft `upgrade head` bei jedem Start.
    _alembic("upgrade", "head")
    assert _sql("SELECT count(*) FROM chat_glocke")[0][0] == 1

    # Rundlauf: downgrade nimmt die Tabelle weg, upgrade legt sie wieder an.
    _alembic("downgrade", "chat5_umfrage")
    assert not _sql("SELECT to_regclass('public.chat_glocke') IS NOT NULL AS da")[0][0]
    _alembic("upgrade", "head")
    assert _sql("SELECT to_regclass('public.chat_glocke') IS NOT NULL AS da")[0][0]


@pg
def test_alembic_check_meldet_keine_abweichung():
    """Modell und Migration stimmen überein (kein vergessener Schritt)."""
    _leere_db()
    _alembic("upgrade", "head")
    ausgabe = _alembic("check")
    assert "No new upgrade operations detected" in ausgabe or "no new" in ausgabe.lower(), \
        ausgabe[-2000:]
