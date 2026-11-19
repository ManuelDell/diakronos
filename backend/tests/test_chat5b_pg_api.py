"""CHAT-5b: die Umfrage-ENDPUNKTE gegen ECHTES PostgreSQL 17.

Warum getrennt von ``test_chat5_pg.py``
---------------------------------------
``test_chat5_pg.py`` prüft das SCHEMA (Migration, Indizes, rohe ``INSERT``s).
Das reicht nicht: der Review-Befund R1 war ein reiner SQL-Dialektfehler, der
NUR im Endpunkt auftrat — ``_zaehle`` schrieb ``max(0, stimmen + delta)``,
und das zweiargumentige ``max`` gibt es ausschließlich in SQLite. Jede
Stimmabgabe wäre im Betrieb mit 500 gescheitert, während alle Schema-Tests
grün waren. Diese Datei ruft deshalb die echten Endpunkte über die echte
Sitzungsschicht gegen PostgreSQL auf:

  * ANONYM abstimmen (Zähler-UPDATE + Marken-INSERT) — der Fehlerfall R1,
  * ANONYM Doppelabgabe → 400 und der Zähler bleibt genau einmal,
  * OFFEN abstimmen und die Stimme ÄNDERN (``_offene_stimmen_setzen`` samt
    ``FOR UPDATE`` und ``rowcount``) — Zähler wandern, nie negativ,
  * nach der Frist → 400, Ergebnis bleibt,
  * eine gelöschte Umfrage nimmt keine Stimme mehr an (404) — dort wird die
    Hülle-Nachricht über den Endpunkt ``loeschen`` entfernt.

Aufruf (eigener Container, eigenes Netz, Worktree nur lesend)::

    docker network create chat5b-net
    docker run -d --name chat5b-pg --network chat5b-net \\
      -e POSTGRES_USER=chat5 -e POSTGRES_PASSWORD=chat5 -e POSTGRES_DB=chat5 \\
      postgres:17-alpine
    docker run --rm --network chat5b-net -v <wt>:/repo:ro -w /repo/backend \\
      -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 \\
      -e CHAT5B_PG_URL=postgresql+psycopg://chat5:chat5@chat5b-pg:5432/chat5 \\
      -e DATABASE_URL=postgresql+psycopg://chat5:chat5@chat5b-pg:5432/chat5 \\
      --entrypoint python diakronos-vorbau:3900e4504ed1c34483c739517a959126b7ff2b6c \\
      -m pytest -q -p no:cacheprovider tests/test_chat5b_pg_api.py

Ohne ``CHAT5B_PG_URL`` → SKIP (kein Default, damit nie die Betriebsdatenbank
angefasst wird — dieselbe Regel wie ``test_chat5_pg.py``).

Achtung: ``diakronos_app.db`` liest ``DATABASE_URL`` beim IMPORT. Die Tests
verbinden deshalb NICHT über ``dbmod.engine`` aus der Umgebung, sondern
erzeugen eine eigene Engine über ``CHAT5B_PG_URL`` und patchen ``SessionLocal``
— genau wie ``patched_db`` es in der SQLite-Suite tut.
"""

from __future__ import annotations

import datetime as dt
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

PG_URL = os.environ.get("CHAT5B_PG_URL", "").strip()
BACKEND = Path(__file__).resolve().parents[1]
ALEMBIC_TIMEOUT = int(os.environ.get("CHAT5B_ALEMBIC_TIMEOUT", "600"))

pg = pytest.mark.skipif(
    not PG_URL,
    reason="CHAT5B_PG_URL nicht gesetzt — PG-Lauf nur mit Wegwerf-PostgreSQL",
)

_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

ADMIN = "admin@x.org"
HV = "hv@x.org"
MV = "mv@x.org"
SAENGER = "saenger@x.org"


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
    """Frische Datenbank: Schema komplett auf ``head`` (die echte Kette).

    Das Schema wird EINMAL je Sitzung hergestellt (``alembic upgrade head``).
    Liegt es schon auf dem Kopf (zweiter Test im selben Container), entfällt
    der Unterprozess — sinnvoll bei ``-k``-Läufen.
    """
    if not PG_URL:
        pytest.skip("CHAT5B_PG_URL nicht gesetzt")
    kopf = _sql("SELECT version_num FROM alembic_version") if _sql(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = 'alembic_version'") else []
    if [z[0] for z in kopf] != ["chat5_umfrage"]:
        _sql("DROP SCHEMA IF EXISTS public CASCADE")
        _sql("CREATE SCHEMA public")
        hoch = _alembic("upgrade", "head")
        assert hoch.returncode == 0, (hoch.stdout, hoch.stderr)
    return PG_URL


@pytest.fixture()
def pg_sitzung(pg_db, monkeypatch):
    """Setzt ``SessionLocal`` der App auf die Wegwerf-Datenbank (kein SQLite)."""
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


def _set_user(konto: str | None) -> None:
    _session_mod.set_user(konto)


def _reset() -> None:
    _session_mod.reset_user()


@pytest.fixture()
def welt(pg_sitzung):
    """Chor mit Chat-Modul, vier Konten, HV als Moderator — je Test frisch."""
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import (
        Gruppe,
        Gruppenmitgliedschaft,
        Mitglied,
    )
    from diakronos_app.models.rechte import RechteGruppenrolle, RechteModul

    with pg_sitzung.begin() as s:
        # Aufräumen: die Tabellen, die dieser Test beschreibt (RESTART IDENTITY
        # gibt es hier nicht, die Kennungen sind Text).
        # Reihenfolge = umgekehrte Fremdschlüssel-Richtung (PostgreSQL prüft
        # sie sofort; die erste Fassung löschte `chat_nachricht` vor der
        # Umfrage, auf die sie zeigt).
        for tabelle in ("chat_stimme", "chat_umfrage_abgabe", "chat_umfrage_option",
                        "chat_nachricht", "chat_umfrage", "chat_teilnehmer",
                        "chat_gespraech", "rechte_modul", "rechte_gruppenrolle",
                        "gruppenmitgliedschaft", "mitglied", "has_role", "user",
                        "gruppe"):
            s.execute(__import__("sqlalchemy").text(f'DELETE FROM "{tabelle}"'))

        for konto, kurz in [(ADMIN, "Admin"), (HV, "Hv"), (MV, "Mv"), (SAENGER, "Sa")]:
            s.add(User(name=konto, email=konto, enabled=1, full_name=kurz))
            s.add(Mitglied(name=f"M-{kurz}", vorname=kurz, nachname="X", email=konto,
                           user=konto))
        s.add(HasRole(name="hr-admin", parent=ADMIN, parenttype="User",
                      role="System Manager"))
        # PostgreSQL prüft Fremdschlüssel SOFORT (SQLite tat es nicht): die
        # Mitglieder müssen stehen, bevor die Mitgliedschaften sie nennen.
        s.flush()
        s.add(Gruppe(name="Chor", gruppenname="Chor"))
        s.flush()
        s.add(Gruppenmitgliedschaft(name="gm1", parent="Chor",
                                    parentfield="mitglieder", mitglied="M-Sa"))
        s.add(Gruppenmitgliedschaft(name="gm2", parent="Chor",
                                    parentfield="mitglieder", mitglied="M-Mv"))
        s.add_all([
            RechteGruppenrolle(gruppe="Chor", benutzer=HV, rolle="HV"),
            RechteGruppenrolle(gruppe="Chor", benutzer=MV, rolle="MV"),
            RechteModul(gruppe="Chor", modul="chat"),
        ])
    yield pg_sitzung


@pytest.fixture()
def gespraech(welt):
    from diakronos_app.api import chat as C

    _set_user(SAENGER)
    name = C.gespraech_anlegen("Chor")["name"]
    _reset()
    return name


def _umfrage(gespraech: str, konto: str = SAENGER, anonym: bool = True,
             mehrfach: bool = False, frage: str = "Wann proben wir?") -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.umfrage_anlegen(gespraech, frage, optionen=["Samstag", "Sonntag"],
                             mehrfach=mehrfach, anonym=anonym)


def _abstimmen(umfrage: str, konto: str, optionen) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.umfrage_abstimmen(umfrage, optionen=optionen)


def _zaehler(umfrage: str) -> list[int]:
    return [int(z[0]) for z in _sql(
        "SELECT stimmen FROM chat_umfrage_option WHERE umfrage = %(u)s "
        "ORDER BY nummer", u=umfrage)]


# ── MUSS 1: Abstimmen läuft auf PostgreSQL überhaupt durch ─────────────────


@pg
def test_anonym_abstimmen_auf_postgres(gespraech):
    """Der R1-Fall: Zähler-UPDATE mit ``max(0, …)`` scheiterte hier mit 500."""
    antwort = _umfrage(gespraech, anonym=True)
    ergebnis = _abstimmen(antwort["umfrage"]["name"], SAENGER, 1)

    assert ergebnis["stimmen_gesamt"] == 1
    assert ergebnis["abgegeben"] == 1
    assert ergebnis["abgestimmt"] is True
    assert ergebnis["eigene_stimme"] is None          # anonym: keine Option zur Person
    assert _zaehler(antwort["umfrage"]["name"]) == [1, 0]

    # Keine Stimmenzeile, genau eine Marke ohne Option (Schema-Zusage).
    assert _sql("SELECT 1 FROM chat_stimme WHERE umfrage = %(u)s",
                u=antwort["umfrage"]["name"]) == []
    assert _sql("SELECT count(*) FROM chat_umfrage_abgabe WHERE umfrage = %(u)s",
                u=antwort["umfrage"]["name"]) == [(1,)]


@pg
def test_anonyme_doppelabgabe_auf_postgres_bleibt_bei_einer_stimme(gespraech):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    u = _umfrage(gespraech, anonym=True)["umfrage"]
    _abstimmen(u["name"], SAENGER, 1)

    _set_user(SAENGER)
    with pytest.raises(ValidationError):
        C.umfrage_abstimmen(u["name"], optionen=2)
    assert _zaehler(u["name"]) == [1, 0]
    _reset()


@pg
def test_offen_abstimmen_und_aendern_auf_postgres(gespraech):
    """``_offene_stimmen_setzen`` mit ``FOR UPDATE``/``rowcount`` auf PG."""
    u = _umfrage(gespraech, anonym=False)["umfrage"]

    erste = _abstimmen(u["name"], SAENGER, 1)
    assert erste["eigene_stimme"] == [1]
    assert _zaehler(u["name"]) == [1, 0]

    zweite = _abstimmen(u["name"], SAENGER, 2)
    assert zweite["eigene_stimme"] == [2]
    assert _zaehler(u["name"]) == [0, 1]        # umgezogen, nichts doppelt

    # Zweite Person auf dieselbe Option: Zähler 2.
    dritte = _abstimmen(u["name"], HV, 2)
    assert dritte["optionen"][1]["stimmen"] == 2
    assert dritte["abgegeben"] == 2
    assert _zaehler(u["name"]) == [0, 2]

    # Und wieder zurück: niemand verliert seine Stimme, nichts wird negativ.
    vierte = _abstimmen(u["name"], SAENGER, 1)
    assert vierte["eigene_stimme"] == [1]
    assert _zaehler(u["name"]) == [1, 1]
    _reset()


@pg
def test_offen_mehrfach_aendern_auf_postgres(gespraech):
    """Mehrfachauswahl: 2 → 1 Option → 2 Optionen, Zähler bleiben stimmig."""
    u = _umfrage(gespraech, anonym=False, mehrfach=True)["umfrage"]

    assert _abstimmen(u["name"], SAENGER, [1, 2])["eigene_stimme"] == [1, 2]
    assert _zaehler(u["name"]) == [1, 1]
    assert _abstimmen(u["name"], SAENGER, [2])["eigene_stimme"] == [2]
    assert _zaehler(u["name"]) == [0, 1]
    assert _abstimmen(u["name"], SAENGER, [1])["eigene_stimme"] == [1]
    assert _zaehler(u["name"]) == [1, 0]
    _reset()


@pg
def test_abstimmen_nach_frist_auf_postgres_ist_400(gespraech):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    u = _umfrage(gespraech, anonym=False)["umfrage"]
    _abstimmen(u["name"], SAENGER, 1)
    _sql("UPDATE chat_umfrage SET frist_am = now() - interval '1 minute' "
         "WHERE name = %(u)s", u=u["name"])

    _set_user(HV)
    with pytest.raises(ValidationError):
        C.umfrage_abstimmen(u["name"], optionen=2)

    _set_user(SAENGER)
    ergebnis = C.umfrage_ergebnis(u["name"])
    assert ergebnis["offen"] is False
    assert _zaehler(u["name"]) == [1, 0]        # Ergebnis bleibt stehen
    _reset()


# ── MUSS 2: gelöschte Umfrage auf PostgreSQL ───────────────────────────────


@pg
def test_geloeschte_umfrage_nimmt_auf_postgres_keine_stimme_an(gespraech):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    antwort = _umfrage(gespraech, anonym=False)
    _set_user(SAENGER)
    C.loeschen(antwort["name"])
    _reset()

    for konto in (SAENGER, HV):
        _set_user(konto)
        with pytest.raises(DoesNotExistError):
            C.umfrage_abstimmen(antwort["umfrage"]["name"], optionen=1)
        with pytest.raises(DoesNotExistError):
            C.umfrage_ergebnis(antwort["umfrage"]["name"])
        _reset()
    assert _zaehler(antwort["umfrage"]["name"]) == [0, 0]
