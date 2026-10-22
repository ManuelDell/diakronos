"""DSGVO-1: die Zusagen gegen den ECHTEN PostgreSQL prüfen.

Die übrigen DSGVO-Tests laufen auf SQLite. Das deckt die Logik ab, aber nicht
den Boden, auf dem der Betrieb steht: `func.lower()` faltet anders, `LIKE`
heißt dort `ILIKE`-frei, und die Anonymisierung arbeitet mit `UPDATE … WHERE`
über Tabellen, die in SQLite anders sortiert sind. Genau hier lag der Fehler,
den ein reiner SQLite-Lauf nicht sieht (ein `autoescape`-Argument, das nur
PostgreSQL/SQLAlchemy 2.1 ablehnt).

Der Lauf startet nur mit einer Wegwerf-Datenbank:
`DSGVO1_POSTGRES_URL=postgresql+psycopg://…` — ohne die Variable wird
übersprungen. Angelegt wird NICHTS: der Test baut seine Tabellen über die
Metadaten auf, prüft die Vollständigkeit der Anonymisierung und räumt sie
wieder ab. Eine Betriebs-Datenbank ist damit strukturell nicht erreichbar
(der Name muss auf `_test` enden, s. `_url`).
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DSGVO1_POSTGRES_URL"),
    reason="nur mit DSGVO1_POSTGRES_URL (Wegwerf-PostgreSQL)",
)


def _url() -> str:
    url = str(os.environ["DSGVO1_POSTGRES_URL"])
    # Sicherung gegen den falschen Server: der Test legt Tabellen an und wirft
    # sie weg — das darf nur eine ausdrückliche Testdatenbank treffen.
    assert "_test" in url, "DSGVO1_POSTGRES_URL muss eine Wegwerf-Datenbank sein (*_test)"
    return url


@pytest.fixture()
def postgres_db(monkeypatch):
    """Engine auf dem Wegwerf-PostgreSQL, Metadaten frisch angelegt."""
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.orm import sessionmaker

    import diakronos_app.db as dbmod
    import diakronos_app.models  # noqa: F401 — Modelle registrieren
    from diakronos_app.models.base import Base

    eng = create_engine(_url(), future=True)
    # Kein pauschales `drop_all`/`create_all`: `ablaufplan`, `element`,
    # `dienstplan` und `registrierungslink` verweisen im Kreis, und der Betrieb
    # hat genau diese Tabellen per Migration. Im Wegwerf-Postgres liegen sie
    # darum schon; fehlende Tabellen legt das Fixture nur einzeln an.
    vorhanden = set(inspect(eng).get_table_names())
    fehlen = [t for name, t in Base.metadata.tables.items() if name not in vorhanden]
    if fehlen:
        Base.metadata.create_all(eng, tables=fehlen)
    factory = sessionmaker(bind=eng, autoflush=False, autocommit=False, future=True)
    monkeypatch.setattr(dbmod, "engine", eng)
    monkeypatch.setattr(dbmod, "SessionLocal", factory)
    yield factory
    # Kein `drop_all` (FK-Kreis, s. o.): die Wegwerf-Datenbank wird als Ganzes
    # weggeworfen, nicht Tabelle für Tabelle abgeräumt.
    eng.dispose()


def test_anonymisierung_auf_postgres_laesst_nichts_stehen(postgres_db):
    """Freitext, Adresse, Geburtstag, Konto — auf PostgreSQL 0 Treffer."""
    from datetime import date

    from sqlalchemy import String, Text, select

    from diakronos_app.dsgvo_anonymisierung import anonymisiere
    from diakronos_app.models.base import Base
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Mitglied

    mail = "anna.beispiel@example.org"
    with postgres_db.begin() as s:
        s.add(User(name=mail, email=mail, full_name="Anna Beispiel", enabled=True))
        s.add(HasRole(name="r-anna", parent=mail, parenttype="User", role="Mitglied"))
        s.flush()
        s.add(Mitglied(
            name="PG-41", vorname="Anna", nachname="Beispiel", email=mail,
            telefonnummer="0170 998877", geburtstag=date(1985, 3, 2),
            wohnort="Beispieldorf", straße="Beispielweg", nummer="7",
            user=mail, status="Mitglied",
        ))
        s.flush()
        s.add(Mitglied(name="PG-42", vorname="Bert", nachname="Berger",
                       notiz="anna wohnt in beispieldorf, beispielweg 7, "
                             "mail ANNA.BEISPIEL@EXAMPLE.ORG, tel. 0170 998877"))
    with postgres_db.begin() as s:
        anonymisiere(s, "PG-41", {mail}, dateien=[])

    treffer = []
    with postgres_db() as s:
        for mapper in Base.registry.mappers:
            tabelle = mapper.local_table
            spalten = [c for c in tabelle.c if isinstance(c.type, (String, Text))]
            if not spalten:
                continue
            for zeile in s.execute(select(*spalten)).all():
                for spalte, wert in zip(spalten, zeile):
                    text = str(wert or "").lower()
                    for nadel in ("anna", "beispiel", mail, "0170 998877",
                                  "beispieldorf", "beispielweg", "1985-03-02"):
                        if nadel in text:
                            treffer.append((tabelle.name, spalte.name, nadel, text[:80]))
    assert treffer == [], f"Personendaten stehen auf PostgreSQL noch in: {treffer}"
    with postgres_db() as s:
        assert s.get(User, mail) is None
        m = s.get(Mitglied, "PG-41")
        assert (m.vorname, m.nachname, m.status) == ("Gelöschte", "Person", "geloescht")
        assert m.email is None and m.wohnort is None and m.geburtstag is None
