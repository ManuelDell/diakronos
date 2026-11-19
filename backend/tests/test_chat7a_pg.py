"""CHAT-7a: Migration ``chat7a_direkt`` gegen ECHTES PostgreSQL 17.

Warum ein eigener PG-Lauf (und nicht nur SQLite)
------------------------------------------------
Die Karte verlangt ``upgrade`` / ``downgrade`` / ``upgrade`` „auf PG 17 testen
(Wegwerf-Container mit eigenem Netz/Namen, danach entfernen)“. Der Grund ist
konkret: die Migration ändert eine SPALTE (``gruppe`` nullable) und zwei
PARTIELLE Unique-Indizes (``uq_chat_gespraech_einheit`` verengt,
``uq_chat_gespraech_paar`` neu). Beides formuliert PostgreSQL anders als
SQLite; die Zusagen „ein Gespräch je Personenpaar“ und „Bestandsdaten
bleiben“ müssen in der Form gelten, die im Betrieb läuft.

Geprüft wird:
  * ``upgrade`` vom vorherigen Kopf: Spalte ``paar_schluessel`` da und
    nullable, ``gruppe`` nullable, beide Indizes partiel und unique,
    Bestandszeile unangetastet
  * der Unique-Index hält: zweites 1:1-Zeile desselben Paares → Fehler,
    zwei GRUPPEN-Gespräche derselben Gruppe weiterhin → Fehler (keine Lücke)
  * zweiter ``upgrade``-Lauf bricht nichts (Idempotenz, wie im Entrypoint)
  * ``downgrade`` → ``upgrade`` läuft rund; mit vorhandenem Direktgespräch
    verweigert ``downgrade`` LAUT (kein stiller Datenverlust)
  * ``alembic check`` meldet keinen Drift

Aufruf (eigener Container, eigenes Netz, Worktree nur lesend):

    docker network create chat7a-net
    docker run -d --name chat7a-pg --network chat7a-net \\
      -e POSTGRES_USER=chat7a -e POSTGRES_PASSWORD=chat7a -e POSTGRES_DB=chat7a \\
      postgres:17-alpine
    docker run --rm --network chat7a-net -v <wt>:/repo:ro -w /repo/backend \\
      -e PYTHONPATH=/repo/backend/src -e PYTHONDONTWRITEBYTECODE=1 \\
      -e CHAT7A_PG_URL=postgresql+psycopg://chat7a:chat7a@chat7a-pg:5432/chat7a \\
      --entrypoint python <vorbau> -m pytest -q -p no:cacheprovider \\
      tests/test_chat7a_pg.py

Ohne ``CHAT7A_PG_URL`` werden die PG-Tests SKIP gemeldet und NICHTS verbunden —
keine eigene Variable mit Default, damit kein Lauf versehentlich die
Betriebsdatenbank anfasst (dieselbe Regel wie ``test_chat6_pg``).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PG_URL = os.environ.get("CHAT7A_PG_URL", "").strip()
BACKEND = Path(__file__).resolve().parents[1]
ALEMBIC_TIMEOUT = int(os.environ.get("CHAT7A_ALEMBIC_TIMEOUT", "600"))

pg = pytest.mark.skipif(
    not PG_URL, reason="CHAT7A_PG_URL nicht gesetzt — PG-Lauf nur mit Wegwerf-PostgreSQL"
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
    """``alembic <befehle>`` gegen die Wegwerf-Datenbank; Ausgabe als Text.

    Die Ausgabe geht in DATEIEN, nicht in Pipes: ``alembic upgrade`` schreibt
    bei ~150 Migrationen viel, und ein voller Pipe-Puffer blockiert den
    Kindprozess, während der Elternprozess noch auf das Prozessende wartet —
    ein Deadlock, der als Timeout endet (im ersten PG-Lauf passiert).
    """
    import tempfile

    env = dict(os.environ)
    env["DATABASE_URL"] = PG_URL
    env.setdefault("SECRET_KEY", "test-only-secret-key-never-use-in-production")
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as aus, \
            tempfile.TemporaryFile(mode="w+", encoding="utf-8") as fehler:
        ergebnis = subprocess.run(
            [sys.executable, "-m", "alembic", *befehle],
            cwd=str(BACKEND), env=env, stdout=aus, stderr=fehler,
            text=True, timeout=ALEMBIC_TIMEOUT,
        )
        aus.seek(0)
        fehler.seek(0)
        stdout_text = aus.read()
        stderr_text = fehler.read()
    if ergebnis.returncode != 0:
        raise AssertionError(
            f"alembic {' '.join(befehle)} exit {ergebnis.returncode}\n"
            f"--- stdout ---\n{stdout_text[-4000:]}\n"
            f"--- stderr ---\n{stderr_text[-4000:]}"
        )
    return f"{stdout_text}\n{stderr_text}"


def _leere_db() -> None:
    _sql("DROP SCHEMA IF EXISTS public CASCADE")
    _sql("CREATE SCHEMA public")


def _bis_vorherigen_kopf() -> None:
    """Bestand herstellen: die Kette bis UNMITTELBAR VOR ``chat7a_direkt``.

    Der vorherige Kopf ist ``chat8_fristen`` (CHAT-8, nach dem zweiten
    Nachziehen von ``main``); die Kante selbst prüft ``test_chat7a_direkt.py``.
    """
    _alembic("upgrade", "chat8_fristen")


def _bestand() -> None:
    """Eine Gruppe mit Gespräch + Nachricht + zwei Konten als Altbestand."""
    for konto in ("a@x.org", "b@x.org"):
        _sql('INSERT INTO "user" (name, email, full_name, enabled) '
             "VALUES (:n, :n, :n, true)", n=konto)
    _sql("INSERT INTO chat_gespraech (name, art, gruppe) VALUES ('G-1', 'gruppe', 'Chor')")
    _sql("INSERT INTO chat_nachricht (name, gespraech, autor_benutzer, text, erstellt_am) "
         "VALUES ('N-1', 'G-1', 'a@x.org', 'Text', '2026-11-19 09:00:00')")


#: Trenner des Kontenpaars — MUSS der von ``api.chat.PAAR_TRENNER`` sein
#: (``\x1f``): PostgreSQL-Textfelder verbieten das NUL-Byte, und genau das hat
#: dieser Lauf beim ersten Anlauf aufgedeckt.
TRENNER = "\x1f"


def _direkt(name: str, paar: str) -> None:
    _sql("INSERT INTO chat_gespraech (name, art, gruppe, paar_schluessel) "
         "VALUES (:n, 'direkt', NULL, :p)", n=name, p=paar)


@pg
def test_upgrade_downgrade_upgrade_und_die_regeln_auf_postgres():
    _leere_db()
    _bis_vorherigen_kopf()
    _bestand()

    # Vor dem Schritt: keine Paar-Spalte.
    assert "paar_schluessel" not in {z[0] for z in _sql(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'chat_gespraech'")}

    _alembic("upgrade", "head")

    spalten = {z[0]: z[1] for z in _sql(
        "SELECT column_name, is_nullable FROM information_schema.columns "
        "WHERE table_name = 'chat_gespraech'")}
    assert spalten["paar_schluessel"] == "YES"
    assert spalten["gruppe"] == "YES", "gruppe muss NULLABLE sein (Direktgespräch)"

    # Bestandszeile unangetastet.
    assert _sql("SELECT gruppe, paar_schluessel FROM chat_gespraech "
                "WHERE name = 'G-1'")[0] == ("Chor", None)
    assert _sql("SELECT count(*) FROM chat_nachricht")[0][0] == 1

    indizes = dict(_sql(
        "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'chat_gespraech'"))
    assert "uq_chat_gespraech_paar" in indizes
    assert "UNIQUE" in indizes["uq_chat_gespraech_paar"].upper()
    assert "WHERE" in indizes["uq_chat_gespraech_paar"].upper()
    assert "direkt" in indizes["uq_chat_gespraech_paar"]
    # Der Einheits-Index erfasst Direktgespräche NICHT mehr.
    assert "paar_schluessel IS NULL" in indizes["uq_chat_gespraech_einheit"]

    # EIN Gespräch je Personenpaar — auch bei vertauschter Reihenfolge.
    _direkt("D-1", "a@x.org\x1fb@x.org")
    with pytest.raises(Exception):
        _direkt("D-2", "a@x.org\x1fb@x.org")

    # Die Einheits-Regel bleibt für GRUPPEN scharf (keine Lücke durch NULL).
    with pytest.raises(Exception):
        _sql("INSERT INTO chat_gespraech (name, art, gruppe) "
             "VALUES ('G-2', 'gruppe', 'Chor')")

    # Mehrere Direktgespräche (verschiedene Paare) sind kein Konflikt.
    _sql('INSERT INTO "user" (name, email, full_name, enabled) '
         "VALUES ('c@x.org', 'c@x.org', 'C', true)")
    _direkt("D-3", "b@x.org\x1fc@x.org")
    assert _sql("SELECT count(*) FROM chat_gespraech WHERE art = 'direkt'")[0][0] == 2

    # Zweiter Lauf: idempotent.
    _alembic("upgrade", "head")
    assert _sql("SELECT count(*) FROM chat_gespraech")[0][0] == 3

    # Kein Drift zwischen Modell und Datenbank.
    ausgabe = _alembic("check")
    assert "No new upgrade operations detected" in ausgabe or "no new" in ausgabe.lower(), \
        ausgabe[-2000:]

    # Downgrade VERWEIGERT laut, solange Direktgespräche existieren.
    _alembic_erwartet_fehler("downgrade", "chat8_fristen")

    # Erst leeren, dann rund: downgrade → upgrade.
    _sql("DELETE FROM chat_gespraech WHERE art = 'direkt'")
    _alembic("downgrade", "chat8_fristen")
    assert "paar_schluessel" not in {z[0] for z in _sql(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'chat_gespraech'")}
    spalten = {z[0]: z[1] for z in _sql(
        "SELECT column_name, is_nullable FROM information_schema.columns "
        "WHERE table_name = 'chat_gespraech'")}
    assert spalten["gruppe"] == "NO"
    _alembic("upgrade", "head")
    assert _sql("SELECT gruppe FROM chat_gespraech WHERE name = 'G-1'")[0][0] == "Chor"


def _alembic_erwartet_fehler(*befehle: str) -> None:
    """``alembic <befehle>`` MUSS scheitern — dieselbe Ausgabe-Behandlung."""
    import tempfile

    env = dict(os.environ)
    env["DATABASE_URL"] = PG_URL
    env.setdefault("SECRET_KEY", "test-only-secret-key-never-use-in-production")
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as aus, \
            tempfile.TemporaryFile(mode="w+", encoding="utf-8") as fehler:
        ergebnis = subprocess.run(
            [sys.executable, "-m", "alembic", *befehle],
            cwd=str(BACKEND), env=env, stdout=aus, stderr=fehler,
            text=True, timeout=ALEMBIC_TIMEOUT,
        )
        aus.seek(0)
        fehler.seek(0)
        stdout_text = aus.read()
        stderr_text = fehler.read()
    gesamt = f"{stdout_text}\n{stderr_text}"
    assert ergebnis.returncode != 0, (
        f"alembic {' '.join(befehle)} hätte fehlschlagen müssen\n{gesamt[-2000:]}")
    assert "Rücknahme nicht möglich" in gesamt, gesamt[-2000:]


@pg
def test_zwei_gleichzeitige_anlagen_ergeben_genau_ein_gespraech():
    """Das Rennen auf PG: zwei Verbindungen legen DASSELBE Paar an.

    Der Unique-Index ``uq_chat_gespraech_paar`` lässt genau eine Zeile zu; der
    Verlierer bekommt ``IntegrityError`` (den ``_direkt_holen`` im Savepoint
    abfängt). Belegt wird hier die DATENBANK-Regel selbst — zwei Threads, zwei
    Transaktionen, ein Gewinner.
    """
    import threading

    import sqlalchemy as sa

    _leere_db()
    _bis_vorherigen_kopf()
    _alembic("upgrade", "head")
    for konto in ("a@x.org", "b@x.org"):
        _sql('INSERT INTO "user" (name, email, full_name, enabled) '
             "VALUES (:n, :n, :n, true)", n=konto)

    engine = sa.create_engine(PG_URL, future=True)
    start = threading.Barrier(2, timeout=20)
    ergebnisse: dict[int, str] = {}

    def _anlegen(nummer: int) -> None:
        try:
            start.wait()
            with engine.begin() as conn:
                conn.execute(sa.text(
                    "INSERT INTO chat_gespraech (name, art, gruppe, paar_schluessel) "
                    "VALUES (:n, 'direkt', NULL, :p)"),
                    {"n": f"D-{nummer}", "p": f"a@x.org{TRENNER}b@x.org"})
            ergebnisse[nummer] = "ok"
        except Exception as fehler:                      # noqa: BLE001 — Diagnose
            ergebnisse[nummer] = type(fehler).__name__

    faden = [threading.Thread(target=_anlegen, args=(i,)) for i in (1, 2)]
    for f in faden:
        f.start()
    for f in faden:
        f.join(timeout=60)
    engine.dispose()

    assert sorted(ergebnisse) == [1, 2], ergebnisse
    assert sorted(ergebnisse.values()) == ["IntegrityError", "ok"], ergebnisse
    assert _sql("SELECT count(*) FROM chat_gespraech WHERE art = 'direkt'")[0][0] == 1
