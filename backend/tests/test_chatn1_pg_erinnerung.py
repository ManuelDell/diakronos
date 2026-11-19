"""CHAT-N1 (MUSS 1): die Umfrage-Erinnerung gegen ECHTES PostgreSQL 17.

Warum ein eigener PG-Lauf
-------------------------
Der erste Anlauf (CHAT-N1, Punkt 5) filterte kurze Fristen mit
``func.julianday(...)`` — eine SQLite-Funktion. Auf PostgreSQL kennt sie
niemand: die Abfrage in ``_offene_umfragen_mit_frist`` läuft AUSSERHALB des
``try`` je Umfrage, der minütliche Job wäre also an ``UndefinedFunction``
gescheitert und hätte NIE erinnert — während die SQLite-Suite grün war. Dieser
Lauf führt deshalb BEIDE Wege real aus:

  * ``_offene_umfragen_mit_frist`` direkt auf PostgreSQL (Auswahl + Grenze),
  * einen ganzen Lauf von ``chat_umfrage_erinnerungen`` — inkl. Glocke und
    ``erinnert_am``.

Aufruf (Wegwerf-Container, eigenes Netz, Worktree nur lesend; die Datenbank
endet auf ``_test``)::

    docker network create chatn1-net
    docker run -d --name chatn1-pg-test --network chatn1-net \\
      -e POSTGRES_USER=chatn1 -e POSTGRES_PASSWORD=chatn1 \\
      -e POSTGRES_DB=chatn1_test postgres:17-alpine
    docker run --rm --network chatn1-net -v <wt>:/repo:ro -w /repo/backend \\
      -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 \\
      -e CHATN1_PG_URL=postgresql+psycopg://chatn1:chatn1@chatn1-pg-test:5432/chatn1_test \\
      -e DATABASE_URL=postgresql+psycopg://chatn1:chatn1@chatn1-pg-test:5432/chatn1_test \\
      --entrypoint python diakronos-vorbau:3900e4504ed1c34483c739517a959126b7ff2b6c \\
      -m pytest -q -p no:cacheprovider tests/test_chatn1_pg_erinnerung.py

Ohne ``CHATN1_PG_URL`` → SKIP (kein Default — nie die Betriebsdatenbank).

Wie bei ``test_chat5b_pg_api``: ``diakronos_app.db`` liest ``DATABASE_URL``
beim IMPORT, deshalb erzeugen die Tests eine eigene Engine über
``CHATN1_PG_URL`` und patchen ``SessionLocal``. Das Schema kommt aus der
echten Alembic-Kette bis ``head`` (der Kopf wird NIE fest verdrahtet).
"""

from __future__ import annotations

import datetime as dt
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

PG_URL = os.environ.get("CHATN1_PG_URL", "").strip()
BACKEND = Path(__file__).resolve().parents[1]
ALEMBIC_TIMEOUT = int(os.environ.get("CHATN1_ALEMBIC_TIMEOUT", "900"))

pg = pytest.mark.skipif(
    not PG_URL,
    reason="CHATN1_PG_URL nicht gesetzt — PG-Lauf nur mit Wegwerf-PostgreSQL",
)

_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")


def _sql(anweisung: str, **werte):
    import sqlalchemy as sa

    engine = sa.create_engine(PG_URL, future=True)
    try:
        with engine.begin() as verbindung:
            ergebnis = verbindung.exec_driver_sql(anweisung, werte)
            return ergebnis.fetchall() if ergebnis.returns_rows else []
    finally:
        engine.dispose()


def _alembic(*argumente: str) -> subprocess.CompletedProcess:
    umgebung = dict(os.environ)
    umgebung["PYTHONPATH"] = f"{BACKEND / 'src'}"
    umgebung["PYTHONDONTWRITEBYTECODE"] = "1"
    umgebung["DATABASE_URL"] = PG_URL
    umgebung.setdefault("SECRET_KEY", "test-only-secret-key-never-use-in-production")
    return subprocess.run(
        [sys.executable, "-m", "alembic", *argumente],
        cwd=str(BACKEND), env=umgebung, capture_output=True, text=True,
        timeout=ALEMBIC_TIMEOUT,
    )


@pytest.fixture(scope="module")
def pg_db():
    """Frische Datenbank auf dem Kopf der KETTE (``get_heads()``, kein Name)."""
    if not PG_URL:
        pytest.skip("CHATN1_PG_URL nicht gesetzt")
    kopf = _sql("SELECT version_num FROM alembic_version") if _sql(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = 'alembic_version'") else []
    from alembic.config import Config as _Config
    from alembic.script import ScriptDirectory as _Skripte

    _cfg = _Config(str(BACKEND / "alembic.ini"))
    _cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    kopf_soll = _Skripte.from_config(_cfg).get_heads()
    assert len(kopf_soll) == 1, kopf_soll          # genau EIN Kopf
    if [z[0] for z in kopf] != kopf_soll:
        _sql("DROP SCHEMA IF EXISTS public CASCADE")
        _sql("CREATE SCHEMA public")
        hoch = _alembic("upgrade", "head")
        assert hoch.returncode == 0, (hoch.stdout, hoch.stderr)
    return PG_URL


@pytest.fixture()
def pg_sitzung(pg_db, monkeypatch):
    """``SessionLocal`` der App auf die Wegwerf-Datenbank (wie chat5b)."""
    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker

    from diakronos_app import db as dbmod

    engine = sa.create_engine(pg_db, pool_pre_ping=True, future=True)
    fabrik = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    for modname in ("diakronos_app.frappe_compat.query", "diakronos_app.frappe_compat.db",
                    "diakronos_app.frappe_compat.doc", "diakronos_app.frappe_compat.router"):
        mod = importlib.import_module(modname)
        if hasattr(mod, "SessionLocal"):
            monkeypatch.setattr(mod, "SessionLocal", fabrik)
    monkeypatch.setattr(dbmod, "SessionLocal", fabrik)
    monkeypatch.setattr(dbmod, "engine", engine)
    yield fabrik
    engine.dispose()


ANNA = "anna@x.org"
BERT = "bert@x.org"


@pytest.fixture()
def welt(pg_sitzung):
    """Ein 1:1-Gespräch zweier Mitglieder — je Test frisch, ohne Reste."""
    from diakronos_app.models.chat import ChatGespraech, ChatTeilnehmer
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    with pg_sitzung.begin() as s:
        for tabelle in ("chat_stimme", "chat_umfrage_abgabe", "chat_umfrage_option",
                        "chat_nachricht", "chat_umfrage", "chat_teilnehmer",
                        "chat_gespraech", "chat_glocke", "notification_log",
                        "has_role", "mitglied", "user"):
            s.execute(__import__("sqlalchemy").text(f'DELETE FROM "{tabelle}"'))
        for konto, vorname in [(ANNA, "Anna"), (BERT, "Bert")]:
            s.add(User(name=konto, email=konto, enabled=1, full_name=vorname))
            s.add(Mitglied(name=f"M-{vorname}", vorname=vorname, nachname="Beispiel",
                           email=konto, user=konto, status="Aktiv"))
        s.flush()
        s.add(ChatGespraech(name="chat-gespraech-1", art="direkt",
                            paar_schluessel="anna|bert",
                            angelegt_am=dt.datetime(2026, 11, 19, 8, 0)))
        s.add_all([
            ChatTeilnehmer(gespraech="chat-gespraech-1", benutzer=ANNA,
                           stumm=False, hinzugefuegt_am=dt.datetime(2026, 11, 19, 8, 0)),
            ChatTeilnehmer(gespraech="chat-gespraech-1", benutzer=BERT,
                           stumm=False, hinzugefuegt_am=dt.datetime(2026, 11, 19, 8, 0)),
        ])
    yield pg_sitzung


def _umfrage(welt, *, name: str, erstellt_am, frist_am, erinnert_am=None,
             geschlossen_am=None) -> None:
    from diakronos_app.models.chat import ChatNachricht, ChatUmfrage

    with welt.begin() as s:
        s.add(ChatUmfrage(
            name=name, gespraech="chat-gespraech-1", frage="Frage?",
            anonym=False, erstellt_am=erstellt_am, frist_am=frist_am,
            erinnert_am=erinnert_am, geschlossen_am=geschlossen_am,
        ))
        # PostgreSQL prüft Fremdschlüssel SOFORT: die Umfrage muss vor der
        # Hülle-Nachricht stehen (SQLite tat das nicht).
        s.flush()
        s.add(ChatNachricht(name=f"chat-nachricht-{name}",
                            gespraech="chat-gespraech-1", autor=None,
                            autor_benutzer=ANNA, text="Umfrage",
                            erstellt_am=erstellt_am, umfrage=name))


# ── MUSS 1a: die Auswahl selbst (kein ``julianday``) ────────────────────────


@pg
def test_offene_umfragen_mit_frist_auf_postgres(welt):
    """Die SQL-Auswahl läuft auf PG und filtert kurze Fristen STRIKT.

    Grenze: ``frist_am - erstellt_am > vorlauf`` (Review CHAT-N1, MUSS 1).
    Genau ``vorlauf`` Abstand ist damit KEIN Kandidat — dieselbe Grenze wie in
    der Python-Nachprüfung.
    """
    from diakronos_app.api import chat as C

    basis = dt.datetime(2026, 11, 19, 9, 0, 0)
    _umfrage(welt, name="um-kurz", erstellt_am=basis,
             frist_am=basis + dt.timedelta(hours=12))
    _umfrage(welt, name="um-grenze", erstellt_am=basis,
             frist_am=basis + dt.timedelta(hours=24))
    _umfrage(welt, name="um-lang", erstellt_am=basis,
             frist_am=basis + dt.timedelta(hours=72))
    _umfrage(welt, name="um-spaet", erstellt_am=basis,
             frist_am=basis + dt.timedelta(days=30))
    _umfrage(welt, name="um-geschlossen", erstellt_am=basis,
             frist_am=basis + dt.timedelta(hours=48),
             geschlossen_am=basis + dt.timedelta(hours=1))
    _umfrage(welt, name="um-erinnert", erstellt_am=basis,
             frist_am=basis + dt.timedelta(hours=48),
             erinnert_am=basis + dt.timedelta(hours=1))

    zeit = basis + dt.timedelta(hours=48)
    with welt.begin() as s:
        gefunden = C._offene_umfragen_mit_frist(s, zeit, 24)
    # Nur „um-lang“ ist nahe genug (Frist = jetzt), nicht kurz und offen.
    assert gefunden == ["um-lang"], gefunden


# ── MUSS 1b: ein ganzer Joblauf auf PostgreSQL ──────────────────────────────


@pg
def test_chat_umfrage_erinnerungen_laeuft_auf_postgres(welt):
    """Der minütliche Job schreibt auf PG eine Glocke und den Merker.

    Das ist der Fehlerfall des Reviews: mit ``julianday`` stirbt die Abfrage
    hier (``UndefinedFunction``) und es kommt NIE eine Erinnerung an.
    """
    from diakronos_app.api import chat as C
    from diakronos_app.models.chat import ChatUmfrage
    from diakronos_app.models.core import NotificationLog

    basis = dt.datetime(2026, 11, 19, 9, 0, 0)
    _umfrage(welt, name="um-lang", erstellt_am=basis,
             frist_am=basis + dt.timedelta(hours=72))
    _umfrage(welt, name="um-kurz", erstellt_am=basis,
             frist_am=basis + dt.timedelta(hours=12))

    # Jetzt: 24 h vor der Frist von „um-lang“ — und 36 h nach der Frist von
    # „um-kurz“ (die ist damit nicht kurz-Frist-ausgeschlossen, sondern
    # geschlossen; beide Wege führen zu keiner Erinnerung).
    jetzt = basis + dt.timedelta(hours=48)
    geschrieben = C.chat_umfrage_erinnerungen(jetzt=jetzt, vorlauf=24)
    assert geschrieben >= 1, geschrieben

    with welt.begin() as s:
        glocken = s.query(NotificationLog).filter(
            NotificationLog.document_type == C.CHAT_UMFRAGE_GLOCKE_DOCTYPE,
            NotificationLog.document_name == "um-lang").all()
        # Beide Teilnehmenden — keiner hat abgestimmt.
        assert {str(z.for_user) for z in glocken} == {ANNA, BERT}, glocken
        lang = s.get(ChatUmfrage, "um-lang")
        assert lang.erinnert_am is not None          # Merker gesetzt
        kurz = s.get(ChatUmfrage, "um-kurz")
        assert kurz.erinnert_am is None

    # Zweiter Lauf: idempotent, nichts doppelt.
    assert C.chat_umfrage_erinnerungen(jetzt=jetzt, vorlauf=24) == 0
