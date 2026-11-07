"""DEMO-2: `--entfernen` und Moderator/Prediger-Felder der Demo (Musterhausen).

Der laufende Betrieb ist PostgreSQL (``compose/stack.yml``). Die bisherigen
Tests der Demo liefen nur auf In-Memory-SQLite. Dort sind Fremdschluessel
standardmaessig AUS — eine falsche Loeschreihenfolge faellt nicht auf. Genau
das war der Befund:

* ``--entfernen`` bricht unter PostgreSQL an einem Fremdschluessel ab,
* Moderator-/Prediger-Felder im Gottesdienst-Ablauf werden beim Seed
  abgelehnt („Unbekannte Person …“).

Beide Tests laufen deshalb gegen eine ECHTE PostgreSQL, wenn
``DIAKRONOS_TEST_DATABASE_URL`` gesetzt ist (Wegwerf-Container, eigenes Netz).
Ohne die Variable werden sie uebersprungen — ein Testlauf gegen den Betrieb
ist damit ausgeschlossen (Regel 11).
"""

from __future__ import annotations

import importlib
from datetime import date

import pytest
from sqlalchemy import text

STICHTAG = date(2026, 11, 2)

#: Die Datenbank kommt aus ``pg_engine``; die autouse-Fixture ``_testnaht``
#: (conftest) schaltet nur die Naht ein und baut KEIN SQLite-Schema mit. Der
#: Seed laeuft in der echten PostgreSQL, das Schema kommt aus
#: ``alembic upgrade head`` (unten ``_alembic_upgrade``).


@pytest.fixture()
def pg_url() -> str:
    import os

    url = (os.environ.get("DIAKRONOS_TEST_DATABASE_URL") or "").strip()
    if not url:
        pytest.skip("ohne DIAKRONOS_TEST_DATABASE_URL (Wegwerf-PostgreSQL) nicht pruefbar")
    return url


@pytest.fixture()
def pg_engine(pg_url, monkeypatch):
    """Frische PostgreSQL je Test: Schema ueber ``alembic upgrade head``.

    ``create_all`` scheitert auf PostgreSQL: das Frappe-Schema hat echte
    FK-Zyklen (Element <-> Ablaufplan, Element <-> Registrierungslink), die
    Alembic in einem eigenen Hook hinter die Tabellen stellt. Gepatcht wird wie
    bei ``patched_db`` (SQLite) — inklusive der Module, die ``SessionLocal``
    per ``from ... import`` gebunden haben.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from diakronos_app import db as db_mod
    from diakronos_app.settings import settings

    # Frische Datenbank je Test (`DROP DATABASE`): ein Schema-Neuaufbau laesst
    # die Typen (pg_type) der Verbindung im Cache — Alembic scheitert dann an
    # „duplicate key … alembic_version“.
    _datenbank_neu(pg_url)
    engine = create_engine(pg_url, future=True)

    alt_url = settings.database_url
    settings.database_url = pg_url
    try:
        _alembic_upgrade()
    finally:
        settings.database_url = alt_url

    fabrik = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(db_mod, "engine", engine)
    monkeypatch.setattr(db_mod, "SessionLocal", fabrik)
    for modname in ("diakronos_app.frappe_compat.query", "diakronos_app.frappe_compat.db",
                    "diakronos_app.frappe_compat.doc", "diakronos_app.frappe_compat.router"):
        mod = __import__(modname, fromlist=["_"])
        if hasattr(mod, "SessionLocal"):
            monkeypatch.setattr(mod, "SessionLocal", fabrik)
    try:
        yield engine
    finally:
        engine.dispose()


def _datenbank_neu(pg_url: str) -> None:
    """Wegwerf-Datenbank auf der Test-Instanz neu anlegen (nur die eigene).

    ``DROP DATABASE`` ist nicht rueckgaengig zu machen. Der Aufruf laeuft
    gegen ``DIAKRONOS_TEST_DATABASE_URL`` — zeigt die Variable versehentlich auf
    eine echte Datenbank, darf hier NICHTS gedroppt werden. Erlaubt sind nur
    Namen mit Praefix ``test_`` oder ``wegwerf``.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    ziel = make_url(pg_url).database or ""
    if not ziel.startswith(("test_", "wegwerf")):
        pytest.fail(
            f"DIAKRONOS_TEST_DATABASE_URL zeigt auf Datenbank {ziel!r} — erlaubt "
            "sind nur Namen mit Praefix 'test_' oder 'wegwerf'. Es wird nichts "
            "gedroppt."
        )
    ziel_url = make_url(pg_url)
    verwaltung = ziel_url.set(database="postgres")
    eng = create_engine(verwaltung, future=True, isolation_level="AUTOCOMMIT")
    try:
        with eng.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{ziel}" WITH (FORCE)'))
            c.execute(text(f'CREATE DATABASE "{ziel}"'))
    finally:
        eng.dispose()


def _alembic_upgrade() -> None:
    """``alembic upgrade head`` gegen die Wegwerf-Datenbank (Schema mit FK-Zyklen)."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(ini.parent / "alembic"))
    command.upgrade(cfg, "head")


def _zaehle(engine, tabelle: str) -> int:
    with engine.connect() as c:
        return c.execute(text(f'SELECT count(*) FROM "{tabelle}"')).scalar_one()


@pytest.fixture()
def demo():
    """Laedt das Demo-Modul gegen die Testdatenbank (ohne Redis/HTTP)."""
    return importlib.import_module("musterhausen")


@pytest.mark.parametrize("tabelle", ["mitglied", "gruppe", "kalender", "element", "user",
                                     "pr_plan", "pr_plantyp", "dienstplan", "lied"])
@pytest.mark.timeout(300)
def test_demo2_entfernen_raeumt_unter_postgresql_auf(pg_engine, tabelle, demo):
    """Seed → ``--entfernen`` → leere Datenbank, mit scharfen Fremdschluesseln."""
    demo.anlegen(stichtag=STICHTAG)
    assert _zaehle(pg_engine, tabelle) > 0, f"{tabelle} wurde nicht gefuellt"

    demo.entfernen()

    assert _zaehle(pg_engine, tabelle) == 0, f"{tabelle} ist nach --entfernen nicht leer"


@pytest.mark.timeout(300)
def test_demo2_entfernen_ist_wiederholbar(pg_engine, demo):
    """Ein zweiter ``--entfernen``-Lauf bricht nicht ab — er findet nichts mehr.

    Nach dem ersten Lauf ist die Datenbank leer: keine Demo-Konten, keine
    Demo-Merkmale. Dann gibt es nichts zu schuetzen (der Waechter
    ``pruefe_demo_konten`` greift nur, wenn die Datenbank Demo-Spuren zeigt)
    und nichts zu loeschen — der Lauf bleibt ein No-op mit leerem Bericht.

    ``audit_log`` ist bewusst KEINE leere Tabelle: die Protokollzeilen bleiben
    stehen, nur ihr Urheber wird genullt (das Protokoll soll den Vorgang nicht
    verlieren). Geprueft wird deshalb, dass kein Akteur der Demo mehr daran
    haengt — sonst waere die Konten-Loeschung am Fremdschluessel gescheitert.
    """
    demo.anlegen(stichtag=STICHTAG)
    demo.entfernen()
    bericht = demo.entfernen()
    assert "nichts gefunden" in bericht
    for tabelle in ("mitglied", "gruppe", "user"):
        assert _zaehle(pg_engine, tabelle) == 0, f"{tabelle} ist nach dem 2. Lauf nicht leer"
    with pg_engine.connect() as c:
        an_demo_konten = c.execute(text(
            "SELECT count(*) FROM audit_log WHERE actor = ANY(:p)"),
            {"p": list(demo.KONTEN)}).scalar_one()
    assert an_demo_konten == 0, "audit_log haengt noch an Demo-Konten"


@pytest.mark.timeout(300)
def test_demo2_moderator_und_prediger_sind_besetzt(pg_engine, demo):
    """Der Ablauf hat Moderator UND Prediger — keine abgelehnten Felder.

    Vorher lief die Besetzung der Personenfelder auf den ANZEIGENAMEN
    („Anna Beispiel“); ``eintrag_setzen`` erwartet die SERVER-Kennung der
    Person und lehnte jedes Moderator-/Prediger-Feld mit „Unbekannte Person,
    Gruppe oder Sammlungseintrag.“ ab. Der Seed meldete das nur auf stderr.
    """
    demo.anlegen(stichtag=STICHTAG)

    with pg_engine.connect() as c:
        ablauf = c.execute(text(
            "SELECT id FROM pr_plan WHERE titel LIKE 'Gottesdienste%'")).scalar_one_or_none()
        assert ablauf is not None, "Ablaufplan fehlt"
        werte = [w for (w,) in c.execute(text(
            "SELECT CAST(e.wert AS TEXT) FROM pr_eintrag e"
            " JOIN pr_termin t ON t.id = e.termin"
            " WHERE t.plan = :p AND (e.feld_pfad LIKE '%.moderator'"
            "    OR e.feld_pfad LIKE '%.prediger')"), {"p": ablauf}).all()]
    assert werte, "kein Moderator-/Prediger-Feld im Ablauf besetzt"

    with pg_engine.connect() as c:
        kennungen = {k for (k,) in c.execute(text('SELECT name FROM mitglied')).all()}
    for wert in werte:
        roh = wert.strip('"')
        assert roh in kennungen, f"Wert {wert!r} ist keine Mitglied-Kennung"

