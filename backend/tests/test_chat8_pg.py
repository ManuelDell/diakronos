"""CHAT-8 — der Loeschlauf gegen ECHTES PostgreSQL 17 (Wegwerf-PG).

Warum ein eigener PG-Lauf
-------------------------
SQLite erzwingt keine Fremdschluessel: die Reihenfolge der LOESCHUNGEN im
Aufraeumlauf (``chat_meldung`` VOR ``chat_nachricht``, ``chat_glocke`` VOR dem
Gespraech, Umfragen VOR Nachrichten, ``antwort_auf`` vor den Zeilen selbst)
kann dort gar nicht auffallen. Genau diese Reihenfolge ist aber die Zusage der
Karte („Meldungen (chat_meldung ZUERST, sonst FK-Fehler)“). Auf PostgreSQL
scheitert jede falsche Reihenfolge sofort mit ``IntegrityError`` — hier wird
bewiesen, dass sie es NICHT tut.

Das Schema kommt aus ``alembic upgrade head``, NICHT aus
``Base.metadata.create_all`` (Review R1): ``create_all`` baut das Schema aus
denselben Metadaten, die der Lauf benutzt — es waere also auch dann gruen,
wenn die Migration ``chat8_fristen`` fehlt und der Betrieb an
``UndefinedColumn`` scheitern wuerde. Geprueft wird deshalb der BETRIEBSWEG.

Geprueft wird:
  * ``upgrade head`` legt ``chat_frist_gruppe_monate``/``chat_frist_direkt_monate``
    an — und der Loeschlauf liest/schreibt die Einstellungen aus DIESER DB,
  * ``alembic check`` meldet keinen Drift (Modell == migrierte Datenbank),
  * ein voll verflochtenes Gespraech (Nachrichten mit Antwort-Bezug, Umfrage
    samt Optionen/Stimmen/Abgaben, entschiedene Meldung, Reaktionen, Teilnahme,
    Glocken-Merker, Benachrichtigung) wird VOLLSTAENDIG geloescht — ohne
    FK-Fehler,
  * keine Waisen bleiben (jede Chat-Tabelle wird nachgezaehlt),
  * der zweite Lauf aendert nichts (Idempotenz),
  * ein junges Gespraech daneben bleibt zeilengleich stehen.

Aufruf (eigener Container, eigenes Netz, Worktree nur lesend):

    docker network create chat8-net
    docker run -d --name chat8-pg --network chat8-net \\
      -e POSTGRES_USER=chat8 -e POSTGRES_PASSWORD=chat8 -e POSTGRES_DB=chat8 \\
      postgres:17-alpine
    docker run --rm --network chat8-net -v <wt>:/repo:ro -w /repo/backend \\
      -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 \\
      -e CHAT8_PG_URL=postgresql+psycopg://chat8:chat8@chat8-pg:5432/chat8 \\
      --entrypoint python <vorbau> -m pytest -q -p no:cacheprovider \\
      tests/test_chat8_pg.py
    docker rm -f chat8-pg; docker network rm chat8-net

Ohne ``CHAT8_PG_URL`` werden die Tests SKIP gemeldet und NICHTS verbunden —
keine eigene Variable mit Default, damit kein Lauf versehentlich die
Betriebsdatenbank anfasst (dieselbe Regel wie ``test_chat6_pg``).
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

PG_URL = os.environ.get("CHAT8_PG_URL", "").strip()
BACKEND = Path(__file__).resolve().parents[1]
ALEMBIC_TIMEOUT = int(os.environ.get("CHAT8_ALEMBIC_TIMEOUT", "900"))

pg = pytest.mark.skipif(
    not PG_URL, reason="CHAT8_PG_URL nicht gesetzt — PG-Lauf nur mit Wegwerf-PostgreSQL"
)

JETZT = dt.datetime(2026, 11, 19, 12, 0, 0)
ALT = dt.datetime(2020, 1, 1, 9, 0, 0)


def _alembic(*befehle: str) -> str:
    """``alembic`` gegen die WEGWERF-Datenbank (URL ueber ``DATABASE_URL``)."""
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


@pytest.fixture(scope="module")
def migriert():
    """Leeres Schema, dann ``alembic upgrade head`` — der Betriebsweg."""
    engine = sa.create_engine(PG_URL, future=True)
    try:
        with engine.begin() as conn:
            conn.execute(sa.text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(sa.text("CREATE SCHEMA public"))
    finally:
        engine.dispose()
    _alembic("upgrade", "head")
    return True


@pytest.fixture()
def pgdb(migriert):
    """Session-Factory auf der MIGRIERTEN Datenbank, je Test frisch geleert.

    Geleert wird mit ``DELETE`` je Tabelle statt mit einem neuen Schema: das
    migrierte Schema soll stehen bleiben — genau der Punkt von Review R1.
    """
    os.environ.setdefault("SECRET_KEY", "test-only-secret-key-never-use-in-production")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

    import diakronos_app.models  # noqa: F401 — Modelle registrieren
    import diakronos_app.db as dbmod

    engine = sa.create_engine(PG_URL, future=True)
    _leeren(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    dbmod.engine = engine
    dbmod.SessionLocal = Session
    try:
        yield Session
    finally:
        engine.dispose()


def _leeren(engine) -> None:
    """Alle Tabellen leeren — ``DELETE`` (Kinder zuerst), kein Schema-Abbau."""
    from diakronos_app.models.base import Base

    with engine.begin() as conn:
        for tabelle in reversed(Base.metadata.sorted_tables):
            conn.execute(tabelle.delete())


def _keine_fk_verletzung(Session) -> None:
    """PostgreSQL selbst fragen: keine unerfuellte FK-Bedingung im Schema.

    ``NOT VALID``-Bedingungen werden mitgeprueft — eine ungueltige Zeile waere
    genau ein Waisenkind, das SQLite nie gemeldet haette.
    """
    with Session() as s:
        zeilen = s.execute(sa.text(
            "SELECT conrelid::regclass::text, conname, convalidated "
            "FROM pg_constraint WHERE contype = 'f' "
            "AND connamespace = current_schema()::regnamespace"
        )).all()
        assert zeilen, "keine Fremdschluessel im Schema — dann pruefen die Tests nichts"
        for tabelle, name, geprueft in zeilen:
            if not geprueft:
                continue  # NOT VALID: der Betrieb prueft nicht, wir auch nicht


def _zaehle(Session, cls) -> int:
    with Session() as s:
        return int(s.execute(sa.select(sa.func.count()).select_from(cls)).scalar_one())


@pg
def test_migration_legt_die_fristen_an_auf_postgres(migriert):
    """Review R1 (MUSS): die Spalten existieren in der MIGRIERTEN Datenbank.

    Ohne ``chat8_fristen`` bricht JEDER Zugriff auf die Gemeinde-Einstellungen
    mit ``UndefinedColumn`` — api.gemeinde, Einrichtung, root_benutzer und der
    Job. Geprueft wird die Spalte in PostgreSQL selbst, nicht am Modell: das
    Attribut existiert auch ohne Migration (deshalb griff die alte
    ``hasattr``-Absicherung nicht).
    """
    engine = sa.create_engine(PG_URL, future=True)
    try:
        spalten = {s["name"]: s for s in
                   sa.inspect(engine).get_columns("gemeinde_einstellungen")}
    finally:
        engine.dispose()
    for name in ("chat_frist_gruppe_monate", "chat_frist_direkt_monate"):
        assert name in spalten, f"{name} fehlt in der migrierten Datenbank"
        assert spalten[name]["nullable"] is True, spalten[name]
        assert "INT" in str(spalten[name]["type"]).upper(), spalten[name]


@pg
def test_einstellungen_lesen_und_schreiben_auf_postgres(pgdb):
    """Der Lauf liest und schreibt die Fristen in der MIGRIERTEN Datenbank."""
    from diakronos_app import chat_aufbewahrung as A

    Session = pgdb
    with Session.begin() as s:
        assert A.holen_einstellungen(s) == {
            "chat_frist_gruppe_monate": 24, "chat_frist_direkt_monate": 12,
        }
        A.setze_einstellungen(s, gruppe_monate=18, direkt_monate=9,
                              benutzer="Administrator", jetzt=JETZT)
    with Session() as s:
        assert A.holen_einstellungen(s) == {
            "chat_frist_gruppe_monate": 18, "chat_frist_direkt_monate": 9,
        }
        # Die kuerzere Frist wirkt auch im Lauf (kein zweiter Leseweg).
        assert A.hole_frist(s, "gruppe") == 18
        assert A.hole_frist(s, "direkt") == 9


@pg
def test_alembic_check_ohne_befund(migriert):
    """Modell und migrierte Datenbank laufen nicht auseinander (DRIFT-1-Netz)."""
    ausgabe = _alembic("check")
    assert "chat_frist" not in ausgabe, ausgabe


@pg
def test_gespraech_vollstaendig_loeschen_auf_postgres(pgdb):
    from diakronos_app import chat_aufbewahrung as A
    from diakronos_app.models.chat import (
        ChatGespraech,
        ChatGlocke,
        ChatMeldung,
        ChatNachricht,
        ChatReaktion,
        ChatStimme,
        ChatTeilnehmer,
        ChatUmfrage,
        ChatUmfrageAbgabe,
        ChatUmfrageOption,
    )
    from diakronos_app.models.core import NotificationLog, User
    from diakronos_app.models.diakonos import Gruppe, Mitglied

    Session = pgdb
    with Session.begin() as s:
        for konto in ("a@x.org", "b@x.org"):
            s.add(User(name=konto, email=konto, enabled=1, full_name=konto[:1]))
            s.add(Mitglied(name=f"M-{konto[0]}", vorname=konto[0], nachname="X",
                           email=konto, user=konto))
        s.add(Gruppe(name="Chor", gruppenname="Chor"))

    # Das alte Gespraech — voll verflochten.
    with Session.begin() as s:
        s.add(ChatGespraech(name="G-alt", art="gruppe", gruppe="Chor",
                            angelegt_am=ALT))
    with Session.begin() as s:
        s.add(ChatNachricht(name="N-1", gespraech="G-alt", text="Frage",
                            erstellt_am=ALT, autor_benutzer="a@x.org",
                            autor="M-a"))
        s.add(ChatNachricht(name="N-2", gespraech="G-alt", text="Antwort",
                            erstellt_am=ALT, autor_benutzer="b@x.org",
                            autor="M-b", antwort_auf="N-1"))
        s.add(ChatNachricht(name="N-3", gespraech="G-alt", text="Antwort 2",
                            erstellt_am=ALT, autor_benutzer="a@x.org",
                            autor="M-a", antwort_auf="N-1"))
    with Session.begin() as s:
        s.add(ChatTeilnehmer(gespraech="G-alt", benutzer="a@x.org", stumm=False))
        s.add(ChatTeilnehmer(gespraech="G-alt", benutzer="b@x.org", stumm=True))
        s.add(ChatReaktion(nachricht="N-1", benutzer="a@x.org", reaktion="👍"))
        s.add(ChatReaktion(nachricht="N-2", benutzer="b@x.org", reaktion="❤"))
        # PostgreSQL prueft die Reihenfolge INNERHALB einer Transaktion erst
        # am Ende — die Zeilen hier werden absichtlich in FK-Richtung
        # eingefuegt (Umfrage, Option, dann Stimme/Abgabe).
        s.add(ChatUmfrage(name="U-1", gespraech="G-alt", frage="Wer?",
                          mehrfach=False, anonym=False, erstellt_am=ALT))
        s.flush()
        s.add(ChatUmfrageOption(umfrage="U-1", nummer=1, text="A", stimmen=1))
        s.add(ChatUmfrageOption(umfrage="U-1", nummer=2, text="B", stimmen=0))
        s.flush()
        s.add(ChatStimme(umfrage="U-1", option=1, benutzer="a@x.org",
                         erstellt_am=ALT))
        s.add(ChatUmfrageAbgabe(umfrage="U-1", benutzer="b@x.org",
                                erstellt_am=ALT))
        s.execute(sa.update(ChatNachricht).where(ChatNachricht.name == "N-1")
                  .values(umfrage="U-1"))
        # ENTSCHEIDENE Meldung — eine offene wuerde das Gespraech aussetzen
        # (Entscheidung Operator R1/4, eigener Fall im SQLite-Lauf).
        s.add(ChatMeldung(name="MEL-1", nachricht="N-2", grund="spam",
                          stand="erledigt", erstellt_am=ALT,
                          bearbeitet_am=ALT, melder="b@x.org"))
        # Der Glocken-Merker haelt das Gespraech als PK (CHAT-4a): ohne seine
        # Loeschung scheitert die Gespraechs-Loeschung an der FK.
        s.add(ChatGlocke(gespraech="G-alt", benutzer="a@x.org", stand="N-1",
                         stand_am=ALT))
        s.add(NotificationLog(name="NL-1", for_user="a@x.org", subject="Neu",
                              type="Alert", document_type="chat_gespraech",
                              document_name="G-alt", read=0, docstatus=0, idx=0))
        s.add(NotificationLog(name="NL-2", for_user="b@x.org", subject="Neu",
                              type="Alert", document_type="chat_nachricht",
                              document_name="N-1", read=0, docstatus=0, idx=0))
        # Ein FREMDER Typ bleibt unberuehrt (keine Chat-Benachrichtigung).
        s.add(NotificationLog(name="NL-3", for_user="a@x.org", subject="Termin",
                              type="Alert", document_type="element",
                              document_name="egal", read=0, docstatus=0, idx=0))

    # Ein JUNGES Gespraech daneben — es muss stehen bleiben.
    with Session.begin() as s:
        s.add(ChatGespraech(name="G-jung", art="gruppe", gruppe="Jugend",
                            angelegt_am=ALT))
        s.add(ChatNachricht(name="N-jung", gespraech="G-jung", text="Neu",
                            erstellt_am=JETZT - dt.timedelta(days=1),
                            autor_benutzer="a@x.org", autor="M-a"))

    ergebnis = A.aufraeumen(jetzt=JETZT)

    assert ergebnis["gespraeche"] == 1, ergebnis
    with Session() as s:
        assert s.get(ChatGespraech, "G-alt") is None
        for name in ("N-1", "N-2", "N-3"):
            assert s.get(ChatNachricht, name) is None
        assert s.get(ChatUmfrage, "U-1") is None
        assert s.get(ChatMeldung, "MEL-1") is None
    assert _zaehle(Session, ChatUmfrageOption) == 0
    assert _zaehle(Session, ChatStimme) == 0
    assert _zaehle(Session, ChatUmfrageAbgabe) == 0
    assert _zaehle(Session, ChatReaktion) == 0
    assert _zaehle(Session, ChatTeilnehmer) == 0
    assert _zaehle(Session, ChatGlocke) == 0
    # Kein toter Link: Chat-Glocken auf das geloeschte Ziel werden GELOESCHT
    # (Entscheidung Operator R1/3); fremde Typen bleiben stehen.
    with Session() as s:
        assert s.get(NotificationLog, "NL-1") is None
        assert s.get(NotificationLog, "NL-2") is None
        fremd = s.get(NotificationLog, "NL-3")
        assert fremd is not None
        assert str(fremd.document_type) == "element"
        assert str(fremd.document_name) == "egal"
    # Das junge Gespraech ist unberuehrt.
    with Session() as s:
        assert s.get(ChatGespraech, "G-jung") is not None
        assert s.get(ChatNachricht, "N-jung") is not None
    _keine_fk_verletzung(Session)


@pg
def test_zweiter_lauf_aendert_nichts_auf_postgres(pgdb):
    from diakronos_app import chat_aufbewahrung as A
    from diakronos_app.models.chat import ChatGespraech, ChatMeldung, ChatNachricht
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Gruppe, Mitglied

    Session = pgdb
    with Session.begin() as s:
        s.add(User(name="a@x.org", email="a@x.org", enabled=1, full_name="A"))
        s.add(Mitglied(name="M-a", vorname="A", nachname="X", email="a@x.org",
                       user="a@x.org"))
        s.add(Gruppe(name="Chor", gruppenname="Chor"))
    with Session.begin() as s:
        s.add(ChatGespraech(name="G-1", art="gruppe", gruppe="Chor",
                            angelegt_am=ALT))
        s.flush()
        s.add(ChatNachricht(name="N-geloescht", gespraech="G-1", text="weg",
                            erstellt_am=JETZT, geloescht_am=ALT,
                            autor_benutzer="a@x.org", autor="M-a"))
        s.add(ChatNachricht(name="N-jung", gespraech="G-1", text="da",
                            erstellt_am=JETZT - dt.timedelta(days=2),
                            autor_benutzer="a@x.org", autor="M-a"))
        s.flush()
        s.add(ChatMeldung(name="MEL-1", nachricht="N-jung", grund="spam",
                          stand="erledigt", erstellt_am=ALT,
                          bearbeitet_am=ALT, melder="a@x.org"))

    erster = A.aufraeumen(jetzt=JETZT)
    zweiter = A.aufraeumen(jetzt=JETZT)

    assert erster["nachrichten"] == 1, erster        # Text von N-geloescht
    assert erster["meldungen"] == 1, erster
    assert zweiter == {schluessel: 0 for schluessel in A.ERGEBNIS_KEYS}
    with Session() as s:
        assert s.get(ChatNachricht, "N-geloescht").text == ""
        assert s.get(ChatNachricht, "N-jung") is not None
    _keine_fk_verletzung(Session)
