"""CHAT-6: Migration ``chat6_meldung`` gegen ECHTES PostgreSQL 17.

Warum ein eigener PG-Lauf (und nicht nur SQLite)
------------------------------------------------
Die Karte verlangt die Migration „gegen Wegwerf-Postgres (nicht nur SQLite)“.
Der Grund ist konkret: ``uq_chat_meldung_offen`` ist ein PARTIELLER
Unique-Index (``WHERE stand = 'offen'``). SQLite und PostgreSQL formulieren
ihn unterschiedlich, und die Regel „eine offene Meldung je (Nachricht,
Melder)“ muss auf BEIDEN halten — auf PostgreSQL zusätzlich in der Form, die
im Betrieb läuft (die SQLite-Prüfung allein belegt das nicht).

Geprüft wird:
  * ``upgrade`` von ``chat2_chat_s1`` legt die Tabelle + beide Indizes an,
  * der Index ist PARTIELL (Prädikat enthält ``stand``),
  * zwei OFFENE Meldungen derselben Person scheitern (``IntegrityError``),
  * eine Meldung NACH einer Entscheidung geht durch,
  * zweiter ``upgrade``-Lauf ändert nichts (Idempotenz, wie im Entrypoint),
  * ``downgrade`` -> ``upgrade`` läuft rund,
  * ``alembic check`` meldet keinen Drift.

Aufruf (eigener Container, eigenes Netz, Worktree nur lesend):

    docker network create chat6-net
    docker run -d --name chat6-pg --network chat6-net \\
      -e POSTGRES_USER=chat6 -e POSTGRES_PASSWORD=chat6 -e POSTGRES_DB=chat6 \\
      postgres:17-alpine
    docker run --rm --network chat6-net -v <wt>:/repo:ro -w /repo/backend \\
      -e PYTHONPATH=/repo/backend/src -e PYTHONDONTWRITEBYTECODE=1 \\
      -e CHAT6_PG_URL=postgresql+psycopg://chat6:chat6@chat6-pg:5432/chat6 \\
      --entrypoint python diakronos-vorbau:3900e4504ed1c34483c739517a959126b7ff2b6c \\
      -m pytest -q -p no:cacheprovider tests/test_chat6_pg.py

Ohne ``CHAT6_PG_URL`` werden die PG-Tests SKIP gemeldet und NICHTS verbunden —
keine eigene Variable mit Default, damit kein Lauf versehentlich die
Betriebsdatenbank anfasst (dieselbe Regel wie ``test_on6e_pg_migration``).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PG_URL = os.environ.get("CHAT6_PG_URL", "").strip()
BACKEND = Path(__file__).resolve().parents[1]
ALEMBIC_TIMEOUT = int(os.environ.get("CHAT6_ALEMBIC_TIMEOUT", "600"))

pg = pytest.mark.skipif(
    not PG_URL, reason="CHAT6_PG_URL nicht gesetzt — PG-Lauf nur mit Wegwerf-PostgreSQL"
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


def _bis_chat2() -> None:
    """Bestand herstellen: die Kette bis UNMITTELBAR VOR ``chat6_meldung``."""
    _alembic("upgrade", "chat2_chat_s1")


def _gespraech_und_nachricht() -> str:
    """Ein Gespräch + eine Nachricht + zwei Konten als Bestand."""
    for konto in ("melder@x.org", "autor@x.org"):
        _sql('INSERT INTO "user" (name, email, full_name, enabled) '
             "VALUES (:n, :n, :n, true)", n=konto)
    _sql("INSERT INTO chat_gespraech (name, art, gruppe) VALUES ('G-1', 'gruppe', 'Chor')")
    _sql("INSERT INTO chat_nachricht (name, gespraech, autor_benutzer, text, erstellt_am) "
         "VALUES ('N-1', 'G-1', 'autor@x.org', 'Text', '2026-11-18 09:00:00')")
    return "N-1"


def _meldung(name: str, stand: str = "offen"):
    _sql("INSERT INTO chat_meldung (name, nachricht, melder, grund, stand, erstellt_am) "
         "VALUES (:n, 'N-1', 'melder@x.org', 'spam', :s, '2026-11-18 10:00:00')",
         n=name, s=stand)


@pg
def test_upgrade_legt_tabelle_partielle_indizes_und_die_regel_an():
    _leere_db()
    _bis_chat2()
    _gespraech_und_nachricht()

    # Vor dem Schritt: es gibt die Tabelle noch nicht.
    assert not _sql("SELECT to_regclass('public.chat_meldung') IS NOT NULL AS da")[0][0]

    _alembic("upgrade", "head")
    assert _sql("SELECT to_regclass('public.chat_meldung') IS NOT NULL AS da")[0][0]

    # Beide Indizes sind da und der Unique-Index ist PARTIELL.
    indizes = dict(_sql(
        "SELECT indexname, indexdef FROM pg_indexes "
        "WHERE tablename = 'chat_meldung'"
    ))
    assert "uq_chat_meldung_offen" in indizes
    assert "ix_chat_meldung_stand" in indizes
    assert "UNIQUE" in indizes["uq_chat_meldung_offen"].upper()
    assert "WHERE" in indizes["uq_chat_meldung_offen"].upper()
    assert "stand" in indizes["uq_chat_meldung_offen"]

    # Die Regel hält auf PostgreSQL: zwei OFFENE Meldungen derselben Person
    # an derselben Nachricht sind nicht möglich.
    _meldung("M-1", "offen")
    with pytest.raises(Exception):
        _meldung("M-2", "offen")

    # Eine Meldung NACH einer Entscheidung geht durch — der Index ist partiell.
    _meldung("M-3", "verworfen")
    _meldung("M-4", "erledigt")
    assert _sql("SELECT count(*) FROM chat_meldung")[0][0] == 3

    # Zweiter Lauf: idempotent (der Entrypoint ruft `upgrade head` bei jedem Start).
    _alembic("upgrade", "head")
    assert _sql("SELECT count(*) FROM chat_meldung")[0][0] == 3

    # Rundlauf downgrade -> upgrade.
    _alembic("downgrade", "chat2_chat_s1")
    assert not _sql("SELECT to_regclass('public.chat_meldung') IS NOT NULL AS da")[0][0]
    _alembic("upgrade", "head")
    assert _sql("SELECT to_regclass('public.chat_meldung') IS NOT NULL AS da")[0][0]

    # Kein Drift zwischen Modell und Datenbank.
    ausgabe = _alembic("check")
    assert "No new upgrade operations detected" in ausgabe or "no new" in ausgabe.lower(), ausgabe[-2000:]


@pg
def test_nachrichtensperre_serialisiert_entscheidungen_derselben_nachricht():
    """A1: die Nachrichtenzeile wird VOR der Meldung gesperrt — dadurch können
    sich zwei Entscheidungen zu VERSCHIEDENEN Meldungen derselben Nachricht
    nicht überkreuzen.

    Nachgestellt wird die Anweisungsfolge aus ``meldung_entscheiden`` auf
    PG-Ebene (2 Verbindungen, 2 Threads). Beide Aufrufe laufen nacheinander:
    der zweite sieht die Sperre, wartet, und entscheidet erst nach dem Commit
    des ersten. Belegt wird:

      * die zweite ``SELECT … FOR UPDATE`` blockiert, solange der erste Aufruf
        seine Transaktion offen hält (Nachweis über ``pg_locks``),
      * nach dem Commit laufen beide durch, jede Meldung genau EINMAL,
      * keine ``DeadlockDetected`` und kein 500.

    HINWEIS (ehrlich): ein Deadlock ließ sich mit dieser Anweisungsfolge auf
    PG 17 NICHT künstlich herbeiführen (Gegenprobe mit umgekehrter Reihenfolge
    lief ebenfalls durch) — der Test belegt daher die Serialisierung, nicht das
    Ausbleiben eines zuvor gemessenen Deadlocks.
    """
    import threading

    import sqlalchemy as sa

    _leere_db()
    _bis_chat2()
    _alembic("upgrade", "head")
    _gespraech_und_nachricht()
    for konto in ("mod-a@x.org", "mod-b@x.org"):
        _sql('INSERT INTO "user" (name, email, full_name, enabled) '
             "VALUES (:n, :n, :n, true)", n=konto)
    for name, melder in (("M-1", "mod-a@x.org"), ("M-2", "mod-b@x.org")):
        _sql("INSERT INTO chat_meldung (name, nachricht, melder, grund, stand, erstellt_am) "
             "VALUES (:n, 'N-1', :m, 'spam', 'offen', '2026-11-18 10:00:00')",
             n=name, m=melder)

    engine = sa.create_engine(PG_URL, future=True)
    ergebnisse: dict[str, str] = {}
    sperre_genommen = threading.Event()
    zuerst_fertig = threading.Event()

    def _entscheiden(kennung: str, warten: threading.Event | None) -> None:
        try:
            with engine.begin() as conn:
                if warten is not None:
                    warten.wait(timeout=20)
                # 1) Nachrichtenzeile sperren — GENAU wie der Endpunkt.
                conn.execute(sa.text("SELECT name FROM chat_nachricht "
                                     "WHERE name = 'N-1' FOR UPDATE"))
                sperre_genommen.set()
                zuerst_fertig.wait(timeout=20)
                # 2) Bedingtes UPDATE der eigenen Meldung.
                anzahl = conn.execute(
                    sa.text("UPDATE chat_meldung SET stand = 'erledigt' "
                            "WHERE name = :k AND stand = 'offen'"), {"k": kennung}
                ).rowcount
                # 3) Die Nachricht entfernen (zweiter Schreibzugriff).
                conn.execute(sa.text(
                    "UPDATE chat_nachricht SET geloescht_am = now(), "
                    "entfernt_grund = 'Test' WHERE name = 'N-1'"))
                ergebnisse[kennung] = f"ok:{anzahl}"
        except Exception as fehler:                    # noqa: BLE001 — Diagnose
            ergebnisse[kennung] = f"{type(fehler).__name__}: {fehler}"
        finally:
            zuerst_fertig.set()     # der Wartende darf nachrücken

    # Aufruf 1 startet sofort, Aufruf 2 erst, wenn Aufruf 1 die Sperre hält.
    erster = threading.Thread(target=_entscheiden, args=("M-1", None))
    erster.start()
    assert sperre_genommen.wait(timeout=20), "Aufruf 1 hat die Sperre nie genommen"
    zweiter = threading.Thread(target=_entscheiden, args=("M-2", sperre_genommen))
    zweiter.start()

    # Während Aufruf 1 offen ist: Aufruf 2 hängt an der Zeilensperre. Eine
    # Zeilensperre erscheint in pg_locks als WARTENDE Transaktions-Sperre
    # (``locktype='transactionid'``, ``NOT granted``), nicht als ``tuple``.
    import time
    time.sleep(1.0)
    assert "M-2" not in ergebnisse, "Aufruf 2 lief OHNE Sperre durch"
    wartend = _sql(
        "SELECT count(*) FROM pg_locks WHERE NOT granted "
        "AND locktype = 'transactionid'")
    assert wartend[0][0] >= 1, "Aufruf 2 wartet nicht auf die Zeilensperre"

    zuerst_fertig.set()
    for f in (erster, zweiter):
        f.join(timeout=60)
    engine.dispose()

    assert set(ergebnisse) == {"M-1", "M-2"}, ergebnisse
    for wert in ergebnisse.values():
        assert wert.startswith("ok:"), ergebnisse
        assert "DeadlockDetected" not in wert, ergebnisse
    # Jede Meldung genau EINMAL entschieden (rowcount 1) — keine Doppelarbeit.
    assert sorted(ergebnisse.values()) == ["ok:1", "ok:1"], ergebnisse
    assert {z[0] for z in _sql("SELECT stand FROM chat_meldung")} == {"erledigt"}
    assert _sql("SELECT geloescht_am FROM chat_nachricht WHERE name = 'N-1'")[0][0] is not None


@pg
def test_anonymisierung_nullt_den_melder_auf_postgres():
    """Art. 17: ``melder`` verschwindet, der Vorgang bleibt nachvollziehbar."""
    _leere_db()
    _bis_chat2()
    _alembic("upgrade", "head")
    _gespraech_und_nachricht()
    _meldung("M-1", "offen")

    # Die Spalte ist auf ``user.name`` gebunden — das Nullen ist ein UPDATE,
    # das die echte Anonymisierung genauso fährt (``user_null`` im Inventar).
    _sql("UPDATE chat_meldung SET melder = NULL WHERE melder = :k", k="melder@x.org")
    zeile = _sql("SELECT melder, stand, grund FROM chat_meldung WHERE name = 'M-1'")[0]
    assert zeile[0] is None
    assert zeile[1] == "offen" and zeile[2] == "spam"
