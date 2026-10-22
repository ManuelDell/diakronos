"""LN1 — Migration ``ln1_lied_quelle`` gegen Wegwerf-PostgreSQL.

Prueft das Zerlegen der Alt-Werte (inkl. Gross-/Kleinschreibung), die
Idempotenz (zweiter Lauf aendert nichts), dass nichts verloren geht (der
Originaltext steht in ``notiz``) und den Downgrade (Originaltext zurueck,
Spalte weg).

Wie ``test_planrahmen_migration_p4.py`` verlangt dieser Test
``PLANRAHMEN_DISPOSABLE_DB=1`` und eine ``DATABASE_URL`` auf eine
**Wegwerf**-Instanz; ohne den Schalter wird er uebersprungen.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

BACKEND = Path(__file__).resolve().parents[1]

#: (name, gesangbuch_nummer, erwartete quelle, buch, nummer, seite)
FAELLE = [
    ("l01", "KOP", "kopie", None, None, None),
    ("l02", "Kop", "kopie", None, None, None),
    ("l03", "kopie", "kopie", None, None, None),
    ("l04", "JN Nr. 1297", "buch", "JN", "1297", None),
    ("l05", "BUCH Nr. 123", "buch", "BUCH", "123", None),
    ("l06", "BUCH S. 150", "buch", "BUCH", None, "150"),
    ("l07", "WH", "buch", "WH", None, None),
    ("l08", None, "ohne", None, None, None),
    ("l09", "   ", "ohne", None, None, None),
    ("l10", "PZ5 Nr. 689", "buch", "PZ5", "689", None),
]


def _cfg(url: str):
    from alembic.config import Config
    from diakronos_app.settings import settings
    settings.database_url = url
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return cfg


@pytest.fixture(scope="module")
def ln1_lauf():
    from alembic import command

    if os.environ.get("PLANRAHMEN_DISPOSABLE_DB") != "1":
        pytest.skip("LN1-Migrationstest braucht Wegwerf-PostgreSQL "
                    "(PLANRAHMEN_DISPOSABLE_DB=1 + DATABASE_URL).")
    url = os.environ.get("DATABASE_URL")
    assert url, "PLANRAHMEN_DISPOSABLE_DB=1 gesetzt, aber DATABASE_URL fehlt"
    assert ("wegwerf" in url.lower() or "postgres-test" in url.lower()
            or "disposable" in url.lower()), (
        f"DATABASE_URL zeigt auf {url!r} — kein erkennbarer Wegwerf-Marker.")

    eng = create_engine(url, future=True)
    try:
        with eng.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))

        cfg = _cfg(url)
        # Vor-LN1-Welt: auf st3 (Vorgaenger), Lieder mit Alt-Werten befuellen.
        command.upgrade(cfg, "st3_themen_kategorien")
        with eng.begin() as conn:
            for faelle_zeile in FAELLE:
                name, num = faelle_zeile[0], faelle_zeile[1]
                conn.execute(text(
                    "INSERT INTO lied (name, titel, aktiv, docstatus, idx, streaming_erlaubt, "
                    "gesangbuch_nummer) "
                    "VALUES (:n, :n, true, 0, 0, false, :nummer)"
                ), {"n": name, "nummer": num})

        command.upgrade(cfg, "head")

        session = __import__("sqlalchemy.orm", fromlist=["sessionmaker"]).sessionmaker(
            bind=eng, autoflush=False, future=True)()

        yield {"engine": eng, "cfg": cfg, "session": session}

        session.close()
    finally:
        eng.dispose()


def _zeile(session, name):
    row = session.execute(text(
        "SELECT quelle, buch, gesangbuch_nummer, seite, notiz FROM lied WHERE name = :n"
    ), {"n": name}).mappings().one()
    result = dict(row)
    # Keine offene Transaktion hinterlassen: sonst blockiert die naechste
    # DDL-Migration (downgrade/upgrade) am `lied`-Tisch.
    session.rollback()
    return result


def test_zerlegung_und_quelle(ln1_lauf):
    s = ln1_lauf["session"]
    for name, _roh, quelle, buch, nummer, seite in FAELLE:
        z = _zeile(s, name)
        assert z["quelle"] == quelle, f"{name}: quelle {z['quelle']!r} != {quelle!r}"
        assert (z["buch"] or None) == buch, f"{name}: buch {z['buch']!r}"
        assert (z["gesangbuch_nummer"] or None) == nummer, f"{name}: nummer {z['gesangbuch_nummer']!r}"
        assert (z["seite"] or None) == seite, f"{name}: seite {z['seite']!r}"


def test_original_geht_nicht_verloren(ln1_lauf):
    """Der Alt-String steht mit Marker in ``notiz`` (nur wo es einen gab)."""
    s = ln1_lauf["session"]
    for name, roh, _q, _b, _nr, _se in FAELLE:
        z = _zeile(s, name)
        notiz = z["notiz"] or ""
        if roh and roh.strip():
            assert "[LN1 Original-Nummer]" in notiz, f"{name}: Original fehlt"
            assert roh.strip() in notiz, f"{name}: Originaltext nicht in notiz"
        else:
            assert "[LN1 Original-Nummer]" not in notiz


def test_idempotent(ln1_lauf):
    """Ein zweiter ``upgrade head`` aendert nichts (quelle ist gesetzt)."""
    from alembic import command
    s = ln1_lauf["session"]
    vorher = {n: dict(_zeile(s, n)) for n, *_ in FAELLE}
    command.upgrade(ln1_lauf["cfg"], "head")
    for n, *_ in FAELLE:
        assert dict(_zeile(s, n)) == vorher[n], f"{n}: zweiter Lauf veraendert die Zeile"


def test_downgrade_stellt_original_wieder_her(ln1_lauf):
    from alembic import command
    s = ln1_lauf["session"]
    s.rollback()
    command.downgrade(ln1_lauf["cfg"], "st3_themen_kategorien")

    insp = inspect(ln1_lauf["engine"])
    assert "quelle" not in {c["name"] for c in insp.get_columns("lied")}
    for name, roh, *_ in FAELLE:
        z = s.execute(text(
            "SELECT gesangbuch_nummer, notiz FROM lied WHERE name = :n"
        ), {"n": name}).mappings().one()
        assert (z["gesangbuch_nummer"] or "") == ("" if roh is None else roh.strip()), (
            f"{name}: Originaltext nicht wiederhergestellt")
        assert "[LN1 Original-Nummer]" not in (z["notiz"] or "")
    s.rollback()

    # Wieder auf head, damit der Lauf wiederholbar bleibt.
    command.upgrade(ln1_lauf["cfg"], "head")
    assert "quelle" in {c["name"] for c in inspect(ln1_lauf["engine"]).get_columns("lied")}
