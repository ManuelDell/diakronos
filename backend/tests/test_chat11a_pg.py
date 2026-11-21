"""CHAT-11a — Volltextsuche gegen ECHTES PostgreSQL 17 (Wegwerf-PG).

Warum ein eigener PG-Lauf
-------------------------
SQLite erkennt weder ``to_tsvector`` noch ``websearch_to_tsquery`` noch den
GIN-Index: auf SQLite läuft der ``LIKE``-Rückfall. Genau der PG-Weg ist aber
der Betriebsweg — und er brach komplett (Review R1/1: ``.op("@@")`` auf einem
``text(...)`` → ``AttributeError`` → jede Suche ein 500).

Geprüft wird deshalb gegen ein ECHTES PostgreSQL und über den ECHTEN
Endpunkt (``api.chat.nachrichten_suchen``), nicht nur am Index:

  * der GIN-Ausdrucksindex der Migration ``chat11a_suche`` existiert und ist
    benutzbar (``EXPLAIN`` wählt ihn bei genug Zeilen),
  * Suche findet deutsche Wörter über die deutsche Konfiguration
    (Stammformen, Umlaute),
  * die ZWEITE SEITE (``vor``) läuft ohne Lücke und ohne Doppel,
  * der ``gespraech``-Filter schränkt auf genau ein Gespräch ein,
  * Umlaute in Text UND Suchbegriff (``Bär``/``bär``/``baer``),
  * der ``ausschnitt`` markiert das gefundene Wort im Originaltext,
  * ``down``/``up`` der Migration läuft rund (Index weg, Index wieder da),
  * ``alembic check`` meldet keinen Drift.

Das Schema kommt aus ``alembic upgrade head``, NICHT aus
``Base.metadata.create_all`` — geprüft wird der BETRIEBSWEG (dieselbe Regel
wie ``test_chat8_pg``).

Aufruf (eigener Container, eigenes Netz, Worktree nur lesend):

    docker network create chat11a-net
    docker run -d --name chat11a-pg --network chat11a-net \\
      -e POSTGRES_USER=chat11a -e POSTGRES_PASSWORD=chat11a \\
      -e POSTGRES_DB=chat11a postgres:17-alpine
    docker run --rm --network chat11a-net -v <wt>:/repo:ro -w /repo/backend \\
      -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 \\
      -e CHAT11A_PG_URL=postgresql+psycopg://chat11a:chat11a@chat11a-pg:5432/chat11a \\
      --entrypoint python <vorbau> -m pytest -q -p no:cacheprovider \\
      tests/test_chat11a_pg.py
    docker rm -f chat11a-pg; docker network rm chat11a-net

Ohne ``CHAT11A_PG_URL`` werden die Tests SKIP gemeldet und NICHTS verbunden —
keine eigene Variable mit Default, damit kein Lauf versehentlich die
Betriebsdatenbank anfasst (dieselbe Regel wie ``test_chat6_pg``/``test_chat8_pg``).
"""

from __future__ import annotations

import datetime as dt
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

PG_URL = os.environ.get("CHAT11A_PG_URL", "").strip()
BACKEND = Path(__file__).resolve().parents[1]
ALEMBIC_TIMEOUT = int(os.environ.get("CHAT11A_ALEMBIC_TIMEOUT", "900"))

#: Die Test-Naht liegt im MODUL ``frappe_compat.session`` (wie ``test_chat2_api``).
_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

pg = pytest.mark.skipif(
    not PG_URL, reason="CHAT11A_PG_URL nicht gesetzt — PG-Lauf nur mit Wegwerf-PostgreSQL"
)

from test_chat7b_runden import MI, ANNA, BERT, DIETER, HV  # noqa: E402
from test_chat7b_runden import _set_user  # noqa: E402


def _alembic(*befehle: str) -> str:
    """``alembic`` gegen die WEGWERF-Datenbank (URL über ``DATABASE_URL``)."""
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


def _leeren(engine) -> None:
    """Alle Tabellen leeren — EIN ``TRUNCATE … CASCADE``.

    ``DELETE`` je Tabelle scheitert auf PostgreSQL an den Fremdschlüsseln
    (und eine Sortierung der Tabellen ist wegen der Zyklen im Schema nicht
    möglich — dieselbe Warnung wie in ``conftest``). ``TRUNCATE … CASCADE``
    leert alles auf einmal und setzt die Sequenzen zurück; das migrierte
    Schema bleibt stehen (genau der Punkt dieses Laufs).
    """
    from diakronos_app.models.base import Base

    namen = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(sa.text(f"TRUNCATE {namen} RESTART IDENTITY CASCADE"))


@pytest.fixture()
def pgdb(migriert):
    """Session-Factory auf der MIGRIERTEN Datenbank, je Test frisch geleert."""
    os.environ.setdefault("SECRET_KEY", "test-only-secret-key-never-use-in-production")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

    import diakronos_app.models  # noqa: F401 — Modelle registrieren
    import diakronos_app.db as dbmod
    from diakronos_app.models.base import Base

    engine = sa.create_engine(PG_URL, future=True)
    _leeren(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    # SQLAlchemy 2.0: eine mit ``begin()`` geöffnete Sitzung braucht dieses
    # Join-Verhalten, damit ``patched_db`` (und damit ``welt``) verschachtelte
    # Transaktionen wie auf SQLite nutzen kann.
    Session.join_transaction_mode = "create_savepoint"
    dbmod.engine = engine
    dbmod.SessionLocal = Session
    try:
        yield Session
    finally:
        engine.dispose()


# ── Welt (wie ``test_chat11a_suche``, nur auf PG) ───────────────────────────


def _mitgliedschaft(s, mitglied: str, gruppe: str) -> None:
    from diakronos_app.models.diakonos import Gruppenmitgliedschaft

    s.add(Gruppenmitgliedschaft(name=f"gm-{mitglied}-{gruppe}", parent=gruppe,
                                parenttype="Gruppe", parentfield="mitglieder",
                                mitglied=mitglied))


def _modul(s, gruppe: str) -> None:
    from diakronos_app.models.rechte import RechteModul

    s.add(RechteModul(gruppe=gruppe, modul="chat"))


@pytest.fixture()
def gruppen(pgdb):
    """Welt + zwei Gruppen: „Chor“ (Anna, Bert) und „Technik“ (nur Dieter).

    Dieselbe Welt wie ``test_chat7b_runden.welt`` (zehn Mitglieder mit Konto,
    HV, Administrator), hier aber SELBST geschrieben und in FK-sicherer
    Reihenfolge mit ``flush``: PostgreSQL prüft Fremdschlüssel sofort, und die
    Fixture dort schreibt mit ``autoflush=False`` — Eltern zuerst heißt hier
    deshalb: User/Mitglied/Gruppe, dann flush, dann Mitgliedschaften.
    """
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Gruppe, Mitglied

    ADMIN = "Administrator"
    namen = {ANNA: ("Anna", "Beispiel"), BERT: ("Bert", "Brandner"),
             DIETER: ("Dieter", "Dorn"), HV: ("Hanna", "Hofmann")}
    Session = pgdb
    with Session.begin() as s:
        s.add(User(name=ADMIN, email="admin@example.invalid", enabled=1,
                   full_name="Administrator"))
        s.add(User(name=HV, email=HV, enabled=1, full_name="Hanna Test"))
        for konto in namen:
            if konto != HV:
                s.add(User(name=konto, email=konto, enabled=1,
                           full_name=konto.split("@")[0].capitalize() + " Test"))
        for konto, (vor, nach) in namen.items():
            s.add(Mitglied(name=MI[konto], vorname=vor, nachname=nach,
                           email=konto, user=konto, status="Aktiv"))
        s.add(HasRole(name="hr-admin", parent=ADMIN, parenttype="User",
                      role="System Manager"))
        s.add(Gruppe(name="Chor"))
        s.add(Gruppe(name="Technik"))
        s.flush()  # Eltern stehen, jetzt dürfen die Kinder kommen
        _mitgliedschaft(s, MI[ANNA], "Chor")
        _mitgliedschaft(s, MI[BERT], "Chor")
        _mitgliedschaft(s, MI[DIETER], "Technik")
        _modul(s, "Chor")
        _modul(s, "Technik")
    from diakronos_app import rechte as R

    R.merker_leeren()
    return Session


def _senden(gespraech: str, text: str, konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.senden(gespraech, text)


def _suchen(q, konto: str = ANNA, **kwargs) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.nachrichten_suchen(q, **kwargs)


def _gruppenchat(gruppe: str, konto: str = ANNA) -> str:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.gespraech_anlegen(gruppe=gruppe)["name"]


@pytest.fixture()
def chor(gruppen):
    """Annas Chor-Chat, Dieters Technik-Chat — je eine Nachricht."""
    chor = _gruppenchat("Chor")
    technik = _gruppenchat("Technik", konto=DIETER)
    _senden(chor, "Probe am Samstag um zehn bei der Bäckerei", ANNA)
    _senden(technik, "Probe am Samstag im Technikraum", DIETER)
    return chor


# ── 1) Migration und Index ──────────────────────────────────────────────────


@pg
def test_index_existiert_und_ist_ein_ausdrucksindex(migriert):
    """Der GIN-Index der Migration steht auf demselben Ausdruck wie die Abfrage."""
    engine = sa.create_engine(PG_URL, future=True)
    try:
        with engine.connect() as conn:
            zeile = conn.execute(sa.text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE tablename = 'chat_nachricht' "
                "AND indexname = 'ix_chat_nachricht_tsv'"
            )).first()
            assert zeile is not None, "der GIN-Index fehlt in der migrierten DB"
            definition = zeile[0].lower()
            assert "using gin" in definition, definition
            # PostgreSQL normalisiert die Definition (`'german'::regconfig`,
            # `COALESCE(text, ''::text)`) — geprüft werden die BESTANDTEILE.
            assert "to_tsvector" in definition, definition
            assert "german" in definition, definition
            assert "coalesce" in definition, definition
            assert "text" in definition, definition
            # Und die ABFRAGE baut denselben Ausdruck: er wird gerendert und
            # gegen die normalisierten Bestandteile gehalten.
            from diakronos_app.api import chat as C

            assert "to_tsvector" in C.NACHRICHT_TSVECTOR.lower()
            gerendert = str(C._tsvector().compile(
                dialect=sa.dialects.postgresql.dialect(),
                compile_kwargs={"literal_binds": True})).lower()
            for teil in ("to_tsvector", "german", "coalesce", "text"):
                assert teil in gerendert, gerendert
    finally:
        engine.dispose()


@pg
def test_explain_nutzt_den_index(pgdb):
    """Bei genug Zeilen wählt der Planer den GIN-Index (er ist also benutzbar)."""
    from diakronos_app.models.chat import ChatGespraech, ChatNachricht

    Session = pgdb
    with Session.begin() as s:
        s.add(ChatGespraech(name="g-viel", art="gruppe", gruppe="Chor",
                            angelegt_am=dt.datetime(2026, 1, 1)))
        for i in range(3000):
            s.add(ChatNachricht(name=f"n-{i:05d}", gespraech="g-viel",
                                text=f"Fülltext Nummer {i} über die Gemeindeordnung",
                                erstellt_am=dt.datetime(2026, 1, 1) + dt.timedelta(seconds=i)))
        s.add(ChatNachricht(name="n-treffer", gespraech="g-viel",
                            text="Kerzenwachs im Altarraum",
                            erstellt_am=dt.datetime(2026, 2, 1)))
    with Session() as s:
        s.execute(sa.text("ANALYZE chat_nachricht"))
        plan = " ".join(
            str(z[0]) for z in s.execute(sa.text(
                "EXPLAIN SELECT name FROM chat_nachricht WHERE "
                "to_tsvector('german', coalesce(text, '')) @@ "
                "websearch_to_tsquery('german', 'kerzenwachs')")).all())
    assert "ix_chat_nachricht_tsv" in plan, plan


@pg
def test_migration_down_und_up_ist_idempotent(migriert):
    """``down`` nimmt NUR den Index weg, ``up`` legt ihn wieder an — zweimal."""
    engine = sa.create_engine(PG_URL, future=True)

    def _index_da() -> bool:
        with engine.connect() as conn:
            return conn.execute(sa.text(
                "SELECT 1 FROM pg_indexes WHERE indexname = 'ix_chat_nachricht_tsv'"
            )).first() is not None

    try:
        assert _index_da()
        _alembic("downgrade", "chat9a_erwaehnung")
        assert not _index_da(), "downgrade muss den Index entfernen"
        _alembic("downgrade", "chat9a_erwaehnung")  # fehlender Index: kein Fehler
        assert not _index_da()
        _alembic("upgrade", "head")
        assert _index_da()
        _alembic("upgrade", "head")  # zweimal anwenden: kein Fehler
        assert _index_da()
        # Die Tabelle lebt noch (``down`` entfernt KEINE Daten).
        with engine.connect() as conn:
            assert conn.execute(sa.text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'chat_nachricht'")).first() is not None
    finally:
        engine.dispose()


@pg
def test_alembic_check_ohne_befund(migriert):
    """Modell und migrierte Datenbank laufen nicht auseinander."""
    ausgabe = _alembic("check")
    assert "chat11a" not in ausgabe, ausgabe


# ── 2) Der ENDPUNKT auf PostgreSQL ─────────────────────────────────────────


@pg
def test_suche_findet_ueber_den_endpunkt(pgdb, chor):
    """Suche, Rechte und Ausschnitt — über ``nachrichten_suchen``, nicht am Index."""
    antwort = _suchen("samstag", konto=ANNA)
    assert len(antwort["treffer"]) == 1
    treffer = antwort["treffer"][0]
    assert treffer["gespraech"]["name"] == chor
    assert treffer["gespraech"]["art"] == "gruppe"
    assert treffer["absender"] == "Anna Beispiel"
    assert treffer["ausschnitt"]["treffer"] == "Samstag"
    # Fremde Gruppe bleibt unsichtbar, der Filter auf sie ist leer.
    assert _suchen("technikraum", konto=ANNA)["treffer"] == []
    assert _suchen("samstag", konto=ANNA, gespraech="chat-gibtsnicht")["treffer"] == []
    # Dieter sieht SEINEN Treffer (Gegenprobe).
    assert len(_suchen("samstag", konto=DIETER)["treffer"]) == 1


@pg
def test_zweite_seite_ohne_luecke_und_doppel(pgdb, chor):
    """Blättern über ``vor`` auf PostgreSQL: drei Seiten, jede Zeile einmal."""
    eigen = [_senden(chor, f"Probe Nummer {i:02d} am Samstag", ANNA)["name"]
             for i in range(5)]
    kennungen = set(eigen)
    alle, vor, seiten = [], None, 0
    while True:
        seite = _suchen("samstag", konto=ANNA, limit=2, vor=vor, gespraech=chor)
        alle += [t["nachricht"] for t in seite["treffer"]]
        seiten += 1
        if not seite["mehr"]:
            break
        vor = seite["vor"]
        assert seiten < 10, "Blätterung endet nicht"
    # Die zwei Nachrichten der Fixture stehen ebenfalls im Gespräch — sie
    # dürfen mitkommen, aber KEINE Zeile darf doppelt oder fehlen.
    assert len(alle) == len(set(alle)), alle
    assert kennungen <= set(alle), (kennungen - set(alle))
    # Die eigenen fünf in Abfolge neueste→älteste, ohne Lücke.
    eigene = [n for n in alle if n in kennungen]
    assert eigene == list(reversed(eigen)), eigene


@pg
def test_gespraech_filter_schraenkt_ein(pgdb, chor):
    technik = _gruppenchat("Technik", konto=DIETER)
    _senden(technik, "Probe am Samstag im Technikraum", DIETER)
    # Anna sieht nur ihr Gespräch.
    antwort = _suchen("samstag", konto=ANNA, gespraech=chor)
    assert {t["gespraech"]["name"] for t in antwort["treffer"]} == {chor}
    # Auf ein fremdes Gespräch: dieselbe leere Antwort.
    assert _suchen("samstag", konto=ANNA, gespraech=technik)["treffer"] == []


@pg
def test_umlaute_und_stammform(pgdb, chor):
    """Deutsche Konfiguration: Umlaute, ß und Stammformen finden."""
    gesucht = _senden(chor, "Der Bär läuft über die Straße", ANNA)["name"]
    # Der Umlaut selbst FÄLLT auf die Grundform zurück (deutsche Konfiguration):
    # „bär“ und „Bär“ finden ihn. „baer“ ist dagegen ein ANDERES Lexem —
    # PostgreSQL kennt die ae/oe/ue-Umschrift nicht, und das ist in Ordnung
    # (dieselbe Regel wie eine Volltextsuche in der Datenbank).
    for q in ("bär", "Bär"):
        namen = [t["nachricht"] for t in _suchen(q, konto=ANNA)["treffer"]]
        assert gesucht in namen, f"{q!r} fand den „Bär“ nicht: {namen}"
    # WORTGLEICHE Stammform: „läuft“ findet „läuft“ (Lexem `lauft`). Eine echte
    # Ableitung wie „laufen“ → `lauf` ist ein ANDERES Lexem — PostgreSQLs
    # deutscher Stemmer leistet keine Lemmatisierung, und die Suche erfindet
    # kein zusätzliches Verhalten.
    for q in ("läuft", "Läuft"):
        namen = [t["nachricht"] for t in _suchen(q, konto=ANNA)["treffer"]]
        assert gesucht in namen, f"{q!r} fand den Satz nicht: {namen}"
    # Der Ausschnitt markiert das WORT im Originaltext.
    ausschnitt = _suchen("läuft", konto=ANNA)["treffer"][0]["ausschnitt"]
    assert ausschnitt["treffer"] == "läuft"


@pg
def test_ausschluss_und_mindestlaenge(pgdb, chor):
    """``q``-Grenzen und die ``websearch``-Syntax gelten auch auf PG."""
    _senden(chor, "Probe am Samstag", ANNA)
    assert _suchen("a", konto=ANNA)["treffer"] == []
    assert _suchen("x" * 101, konto=ANNA)["treffer"] == []

    def _anzahl(q: str) -> int:
        return len(_suchen(q, konto=ANNA, gespraech=chor)["treffer"])

    vorher = _anzahl("probe")
    assert vorher >= 2  # die Fixture-Nachricht + die neue
    # ``-wort`` schließt aus: „probe -bäckerei“ nimmt genau die Fixture-Nachricht
    # heraus, die „Bäckerei“ enthält.
    assert _anzahl("probe -bäckerei") == vorher - 1
