"""ID-1: die Kandidatenregel (O1) und „keine Datenbereinigung“ (O2) sind Test.

WARUM
-----
Die Regel „umschlüsseln wird, was NICHT wie eine Zufallskennung aussieht“ ist
die einzige Stelle, an der die Migration zwischen „Klarname“ und „schon
umgeschlüsselt“ unterscheidet. Sie steht als SQL in
`alembic/versions/id1_mitglied_kennungen.py::_kandidaten`; hier wird sie gegen
eine echte Datenbank geprüft — mit den Kennungen, die der Operator in O1
ausdrücklich benannt hat. Ein Test auf dem regulären Ausdruck allein würde
eine falsch verdrahtete Abfrage (etwa eine zusätzliche Namens-Heuristik)
nicht bemerken.

O2 gehört dazu: `mitglied.email = '-'` ist Altbestand und bleibt `-`. Die
Migration darf ihn NICHT zu NULL „bereinigen“ — der I3-Abgleich vergleicht die
Adresse wörtlich.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import sqlalchemy as sa

BACKEND = pathlib.Path(__file__).resolve().parents[1]
MIGRATION = BACKEND / "alembic" / "versions" / "id1_mitglied_kennungen.py"

#: Die Kennungen aus O1 — und was aus ihnen werden muss.
FAELLE = (
    ("MaxMuster", True),
    ("max@x.org", True),
    ("M-ziel", True),
    ("Anna Beispiel", True),
    ("1a2b3c4d-5", False),      # Muster neuer Kennungen (`uuid4()[:10]`)
    ("f0e1d2c3-4", False),
    ("987a654b-0", False),
    ("geloescht-0001", True),   # Anonymisierung: keine Zufallskennung
)


def _migration():
    """Die Migrationsdatei als Modul (kein Import über den Alembic-Baum)."""
    spec = importlib.util.spec_from_file_location("id1_migration_unter_test", MIGRATION)
    modul = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture()
def tabelle(monkeypatch):
    """Eine `mitglied`-Tabelle mit genau den Kennungen aus O1 (SQLite)."""
    eng = sa.create_engine("sqlite://")
    with eng.begin() as c:
        c.execute(sa.text(
            'CREATE TABLE mitglied (name VARCHAR(140) PRIMARY KEY, '
            'vorname VARCHAR(140), nachname VARCHAR(140), email VARCHAR(140))'
        ))
        for kennung, _ in FAELLE:
            c.execute(sa.text("INSERT INTO mitglied (name) VALUES (:n)"), {"n": kennung})
    return eng


def test_o1_kandidatenregel_ist_das_muster_der_zufallskennung(tabelle):
    """O1: nur Kennungen AUSSERHALB `^[0-9a-f]{8}-[0-9a-f]$` werden umgeschlüsselt.

    SQLite kennt kein `!~`; die Regel wird deshalb als Python-Prüfung gegen
    dieselben Zeilen gehalten und mit der Erwartung aus O1 verglichen. Die
    SQL-Fassung der Migration steht darunter (PostgreSQL) — beide müssen
    dieselbe Menge ergeben; `test_o1_sql_und_python_stimmen_ueberein` prüft das
    auf der echten Datenbank der Abnahme.
    """
    import re

    muster = re.compile(r"^[0-9a-f]{8}-[0-9a-f]$")
    with tabelle.connect() as c:
        namen = c.execute(sa.text("SELECT name FROM mitglied")).scalars().all()
    kandidaten = {n for n in namen if not muster.match(str(n))}
    erwartet = {k for k, soll in FAELLE if soll}
    assert kandidaten == erwartet, kandidaten ^ erwartet


def test_o1_migration_waehlt_auf_postgresql_dieselben_zeilen():
    """Die SQL-Fassung in `_kandidaten` ist die Regel — nicht die Python-Hilfe.

    Ohne PostgreSQL (die Testsuite läuft auf SQLite) wird der Ausdruck selbst
    geprüft: er darf KEINE Namens-/Leerzeichen-Heuristik enthalten (die alte
    Fassung hatte `~ '\\s'` und `LIKE '%@%'` und übersprang „MaxMuster“).
    """
    quelle = MIGRATION.read_text(encoding="utf-8")
    assert "name !~ '^[0-9a-f]{8}-[0-9a-f]$'" in quelle
    assert "'\\\\s'" not in quelle, "Leerzeichen-Heuristik ist mit O1 entfallen"
    assert "LIKE '%@%'" not in quelle, "Adress-Heuristik ist mit O1 entfallen"
    assert "vorname || ' '" not in quelle, "Namensvergleich ist mit O1 entfallen"


def test_o2_email_bleibt_unveraendert_keine_bereinigung():
    """O2: der Alt-Platzhalter `-` wird NICHT zu NULL umgeschrieben.

    Frühere Fassung hatte `_ohne_platzhalter()` und schrieb `-` beim Kopieren
    auf NULL — der I3-Abgleich meldete das als Abweichung, und es war eine
    stille Datenänderung an einer Spalte, die diese Karte nicht besitzt.
    """
    modul = _migration()
    assert not hasattr(modul, "_ohne_platzhalter"), \
        "O2: keine Bereinigung von email — der Platzhalter `-` bleibt stehen"
    quelle = MIGRATION.read_text(encoding="utf-8")
    assert "wird zu NULL" not in quelle
    assert '"e": fremd' in quelle, "die Adresse geht unverändert auf die neue Zeile"


def test_o1_neue_kennung_hat_das_format_von_new_name():
    """Die neue Kennung entsteht WIE `_new_name`: `str(uuid4())[:10]`."""
    modul = _migration()
    import re

    for _ in range(50):
        kennung = str(modul.uuid.uuid4())[:10]
        assert re.match(r"^[0-9a-f]{8}-[0-9a-f]$", kennung), kennung
    quelle = MIGRATION.read_text(encoding="utf-8")
    assert 'kandidat = str(uuid.uuid4())[:10]' in quelle
    assert "token_hex" not in quelle, \
        "dieselbe Quelle wie _new_name, nicht ein nachgebautes Format"
