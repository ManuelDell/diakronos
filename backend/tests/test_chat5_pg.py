"""CHAT-5: Migration ``chat5_umfrage`` gegen ECHTES PostgreSQL 17.

Warum ein eigener PG-Lauf (und nicht nur SQLite)
------------------------------------------------
Die Karte verlangt die Migration „gegen Wegwerf-Postgres (nicht nur SQLite)“.
Die Gründe sind konkret:

  * ``uq_chat_nachricht_umfrage`` ist ein UNIQUE-Index über eine NULLABLE
    Spalte — die Zusage „höchstens EINE Umfrage je Nachricht, beliebig viele
    Nachrichten OHNE Umfrage“ hängt daran, dass PostgreSQL NULLs nicht als
    gleich behandelt. Das ist eine Eigenschaft der BETRIEBSDATENBANK.
  * ``chat_umfrage_abgabe`` trägt die Sperre gegen die zweite anonyme Abgabe
    allein im Primärschlüssel. Ob ein doppeltes ``INSERT`` wirklich scheitert,
    zeigt nur ein echter PG-Lauf.
  * ``upgrade``/``downgrade`` der Kette ``chat2_chat_s1 -> chat6_meldung ->
    chat5_umfrage`` läuft im Betrieb als Ganzes (``alembic upgrade head``);
    genau dieser Lauf wird hier gefahren, inklusive Rückweg.
  * ``alembic check`` darf keinen Drift melden.

Aufruf (eigener Container, eigenes Netz, Worktree nur lesend):

    docker network create chat5-net
    docker run -d --name chat5-pg --network chat5-net \\
      -e POSTGRES_USER=chat5 -e POSTGRES_PASSWORD=chat5 -e POSTGRES_DB=chat5 \\
      postgres:17-alpine
    docker run --rm --network chat5-net -v <wt>:/repo:ro -w /repo/backend \\
      -e PYTHONPATH=/repo/backend/src -e PYTHONDONTWRITEBYTECODE=1 \\
      -e CHAT5_PG_URL=postgresql+psycopg://chat5:chat5@chat5-pg:5432/chat5 \\
      --entrypoint python diakronos-vorbau:3900e4504ed1c34483c739517a959126b7ff2b6c \\
      -m pytest -q -p no:cacheprovider tests/test_chat5_pg.py

Ohne ``CHAT5_PG_URL`` werden diese Tests SKIP gemeldet und NICHTS verbunden —
keine eigene Variable mit Default, damit kein Lauf versehentlich die
Betriebsdatenbank anfasst (dieselbe Regel wie ``test_chat6_pg``).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PG_URL = os.environ.get("CHAT5_PG_URL", "").strip()
BACKEND = Path(__file__).resolve().parents[1]
ALEMBIC_TIMEOUT = int(os.environ.get("CHAT5_ALEMBIC_TIMEOUT", "600"))

pg = pytest.mark.skipif(
    not PG_URL, reason="CHAT5_PG_URL nicht gesetzt — PG-Lauf nur mit Wegwerf-PostgreSQL"
)

#: Die Kette, die im Betrieb läuft: chat2 legt den Chat an, chat6 die Meldung,
#: chat5 die Umfrage. `head` ist damit `chat5_umfrage`.
KETTE = ["chat2_chat_s1", "chat6_meldung", "chat5_umfrage"]


def _sql(anweisung: str, **werte):
    import sqlalchemy as sa

    engine = sa.create_engine(PG_URL, future=True)
    try:
        with engine.begin() as verbindung:
            ergebnis = verbindung.exec_driver_sql(anweisung, werte)
            # DDL liefert keine Zeilen — `.fetchall()` würde dort mit
            # ``ResourceClosedError`` abbrechen.
            return ergebnis.fetchall() if ergebnis.returns_rows else []
    finally:
        engine.dispose()


def _alembic(*argumente: str) -> subprocess.CompletedProcess:
    """``alembic`` im Kindprozess gegen die Wegwerf-Datenbank."""
    umgebung = dict(os.environ)
    umgebung["PYTHONPATH"] = f"{BACKEND / 'src'}"
    umgebung["PYTHONDONTWRITEBYTECODE"] = "1"
    # `env.py` liest die URL aus ``DATABASE_URL`` (wie ``test_chat6_pg``);
    # ``alembic.ini`` bleibt unberührt.
    umgebung["DATABASE_URL"] = PG_URL
    umgebung.setdefault("SECRET_KEY", "test-only-secret-key-never-use-in-production")
    return subprocess.run(
        [sys.executable, "-m", "alembic", *argumente],
        cwd=str(BACKEND), env=umgebung, capture_output=True, text=True,
        timeout=ALEMBIC_TIMEOUT,
    )


@pytest.fixture(scope="module")
def frisch():
    """Leere Datenbank: alles wegwerfen, was ein früherer Lauf hinterliess."""
    if not PG_URL:
        pytest.skip("CHAT5_PG_URL nicht gesetzt")
    _sql("DROP SCHEMA IF EXISTS public CASCADE")
    _sql("CREATE SCHEMA public")
    yield PG_URL


def _tabelle_existiert(name: str) -> bool:
    return bool(_sql(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = %(n)s", n=name,
    ))


def _spalte_existiert(tabelle: str, spalte: str) -> bool:
    return bool(_sql(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %(t)s AND column_name = %(s)s",
        t=tabelle, s=spalte,
    ))


@pg
def test_kette_bis_kopf_legt_die_umfrage_tabellen_an(frisch):
    """``upgrade head`` von Null: die ganze Kette läuft, der Kopf ist chat5."""
    ergebnis = _alembic("upgrade", "head")
    assert ergebnis.returncode == 0, (ergebnis.stdout, ergebnis.stderr)

    for tabelle in ("chat_umfrage", "chat_umfrage_option", "chat_stimme",
                    "chat_umfrage_abgabe", "chat_meldung", "chat_nachricht"):
        assert _tabelle_existiert(tabelle), tabelle
    assert _spalte_existiert("chat_nachricht", "umfrage")

    # Der EINE Kopf steht in der Versions-Tabelle.
    zeilen = _sql("SELECT version_num FROM alembic_version")
    assert [z[0] for z in zeilen] == ["chat4a_glocke"], zeilen


@pg
def test_unique_index_laesst_viele_nachrichten_ohne_umfrage_zu(frisch):
    """„Höchstens EINE Umfrage je Nachricht“ — NULL zählt nicht als gleich."""
    _sql("DROP SCHEMA public CASCADE")
    _sql("CREATE SCHEMA public")
    assert _alembic("upgrade", "head").returncode == 0

    # Zwei Nachrichten OHNE Umfrage: der UNIQUE-Index stört NICHT (sonst
    # könnte ein Gespräch nur eine Nachricht haben).
    _sql("INSERT INTO chat_gespraech (name, art, gruppe, angelegt_am) "
         "VALUES ('g1', 'gruppe', 'Chor', now())")
    _sql("INSERT INTO chat_nachricht (name, gespraech, text, erstellt_am) "
         "VALUES ('n1', 'g1', 'eins', now())")
    _sql("INSERT INTO chat_nachricht (name, gespraech, text, erstellt_am) "
         "VALUES ('n2', 'g1', 'zwei', now())")

    _sql("INSERT INTO chat_umfrage (name, gespraech, frage, erstellt_am) "
         "VALUES ('u1', 'g1', 'Frage?', now())")
    _sql("INSERT INTO chat_nachricht (name, gespraech, text, erstellt_am, umfrage) "
         "VALUES ('n3', 'g1', 'Frage?', now(), 'u1')")

    # Eine ZWEITE Nachricht mit DERSELBEN Umfrage: 1:1, nicht 1:n.
    import sqlalchemy as sa

    with pytest.raises(sa.exc.IntegrityError):
        _sql("INSERT INTO chat_nachricht (name, gespraech, text, erstellt_am, umfrage) "
             "VALUES ('n4', 'g1', 'nochmal', now(), 'u1')")

    # F5: Standard ANONYM steht als DEFAULT im Schema.
    standard = _sql(
        "SELECT column_default FROM information_schema.columns "
        "WHERE table_name = 'chat_umfrage' AND column_name = 'anonym'")
    assert "true" in str(standard[0][0]).lower(), standard


@pg
def test_anonyme_doppelabgabe_scheitert_im_primerschluessel(frisch):
    """Die Sperre ist der PK — zwei Marken derselben Person sind unmöglich."""
    import sqlalchemy as sa

    _sql("DROP SCHEMA public CASCADE")
    _sql("CREATE SCHEMA public")
    assert _alembic("upgrade", "head").returncode == 0

    _sql('INSERT INTO "user" (name, email, enabled) '
         "VALUES ('a@x.org', 'a@x.org', true)")
    _sql("INSERT INTO chat_gespraech (name, art, gruppe, angelegt_am) "
         "VALUES ('g1', 'gruppe', 'Chor', now())")
    _sql("INSERT INTO chat_umfrage (name, gespraech, frage, erstellt_am) "
         "VALUES ('u1', 'g1', 'Frage?', now())")
    _sql("INSERT INTO chat_umfrage_abgabe (umfrage, benutzer, erstellt_am) "
         "VALUES ('u1', 'a@x.org', now())")
    with pytest.raises(sa.exc.IntegrityError):
        _sql("INSERT INTO chat_umfrage_abgabe (umfrage, benutzer, erstellt_am) "
             "VALUES ('u1', 'a@x.org', now())")

    # Und die Tabelle hat KEINE Spalte für die gewählte Option — die
    # Anonymitätszusage ist nicht weglassbar, sie steht im Schema.
    spalten = {z[0] for z in _sql(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'chat_umfrage_abgabe'")}
    assert spalten == {"umfrage", "benutzer", "erstellt_am"}, spalten


@pg
def test_downgrade_und_wieder_hoch(frisch):
    """upgrade → downgrade → upgrade läuft rund (Kette, nicht nur chat5)."""
    _sql("DROP SCHEMA public CASCADE")
    _sql("CREATE SCHEMA public")
    assert _alembic("upgrade", "head").returncode == 0

    # Einen Schritt zurück: chat5 fällt, chat6 und chat2 bleiben.
    zurueck = _alembic("downgrade", "chat6_meldung")
    assert zurueck.returncode == 0, (zurueck.stdout, zurueck.stderr)
    assert not _tabelle_existiert("chat_umfrage")
    assert not _spalte_existiert("chat_nachricht", "umfrage")
    assert _tabelle_existiert("chat_meldung")
    assert _tabelle_existiert("chat_nachricht")

    # Und wieder hoch.
    hoch = _alembic("upgrade", "head")
    assert hoch.returncode == 0, (hoch.stdout, hoch.stderr)
    assert _tabelle_existiert("chat_umfrage")
    assert _spalte_existiert("chat_nachricht", "umfrage")

    # Zweiter Durchlauf: der Rückweg ist idempotent-fähig und legt nichts
    # doppelt an (derselbe Schritt, den der Entrypoint beim Neustart fährt).
    assert _alembic("upgrade", "head").returncode == 0
    assert [z[0] for z in _sql("SELECT version_num FROM alembic_version")] == [
        "chat5_umfrage"]
    # Hinweis: ein ``downgrade base`` der GANZEN Kette ist hier NICHT geprüft —
    # er scheitert in ``chat1``/ID-1 an ``DROP TABLE mitglied`` mit abhängigen
    # Objekten (Bestand des Repos, nicht CHAT-5). Die Karte verlangt
    # upgrade/downgrade/upgrade der NEUEN Migration; genau das steht oben.


@pg
def test_alembic_check_meldet_keinen_drift(frisch):
    """Schema und Modelle stimmen überein (``alembic check``)."""
    _sql("DROP SCHEMA public CASCADE")
    _sql("CREATE SCHEMA public")
    assert _alembic("upgrade", "head").returncode == 0
    pruefung = _alembic("check")
    assert pruefung.returncode == 0, (pruefung.stdout, pruefung.stderr)
