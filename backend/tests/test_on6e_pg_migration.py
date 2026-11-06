"""ON-6e — ``on6_root_benutzer`` gegen ECHTES PostgreSQL 17 (Wegwerf-Container).

Warum eigener Test und nicht nur der SQLite-Rundlauf
----------------------------------------------------
Der Live-Abbruch vom 06.11. war eine REINE PostgreSQL-Eigenheit: derselbe
gebundene Parameter, zweimal in einer Anweisung, einmal gegen
``VARCHAR(140)`` und einmal gegen eine typenlose ``SELECT``-Zielecke —
``psycopg.errors.AmbiguousParameter: inconsistent types deduced for
parameter $1 — text versus character varying``. SQLite kennt diese
Typpruefung nicht und blieb gruen; auf dem Betrieb startete die App in einer
Schleife, weil ``alembic upgrade head`` im Entrypoint scheiterte.

Zwei Ebenen
-----------
1. **Immer gruen, ohne Netz** (``test_quelltext_*``): der Quelltext der
   Migration. ``AmbiguousParameter`` entsteht, wenn ein Parameter in EINER
   Anweisung an zwei Stellen mit verschiedenem Typ gebunden wird — deshalb
   darf kein Schreibvorgang mehr ``INSERT … SELECT … WHERE NOT EXISTS`` mit
   geteiltem Parameter benutzen, und jedes Vorkommen eines Parameters traegt
   einen ausdruecklichen ``CAST``. Das beisst auf jeder Maschine und in jedem
   Image, auch ohne PostgreSQL.

2. **Nur mit Wegwerf-PostgreSQL** (``test_pg_*``, sonst SKIP):
   ``ON6E_PG_URL=postgresql+psycopg://on6e:on6e@on6e-pg:5432/on6e``.
   Geprueft wird die ECHTE Kette:

     * frische DB ``upgrade head`` (kein Fehler, kein root erfunden)
     * Bestands-DB ``ux2b_papierkorb`` + Daten, Gemeinde-Zeile vorhanden
     * Bestands-DB ``ux2b_papierkorb`` + Daten, Gemeinde-Zeile FEHLEND
       (genau der Live-Fall)
     * zweiter ``upgrade``-Lauf aendert nichts (der Entrypoint ruft ihn bei
       jedem Start)
     * ``downgrade`` -> ``upgrade`` (Rundlauf)
     * ``alembic check`` meldet keinen Drift

Warum eine EIGENE Variable und nicht ``DATABASE_URL``: die App bildet ihre
Verbindung aus ``settings.database_url`` (Default ``…@db:5432/…``). Haenge
die Pruefung an ``DATABASE_URL``, zeigte ein Lauf OHNE die Variable auf
``db`` — also auf die Betriebs-DB (Regel 11, Vorfall ID-1f). Mit
``ON6E_PG_URL`` gibt es keinen Default: fehlt sie, wird SKIP gemeldet und
NICHTS verbunden. Fuer ``alembic`` im Unterprozess wird sie dort ausdruecklich
als ``DATABASE_URL`` gesetzt.

Aufruf (eigener Container, eigenes Netz, Worktree nur lesend):

    docker run --rm --network on6e-net -v <worktree>:/repo:ro -w /repo/backend \\
      -e PYTHONPATH=/repo/backend/src:/repo/tools \\
      -e ON6E_PG_URL=postgresql+psycopg://on6e:on6e@on6e-pg:5432/on6e \\
      --entrypoint python diakronos-standalone-app:latest \\
      -m pytest tests/test_on6e_pg_migration.py -o timeout_method=signal
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

PG_URL = os.environ.get("ON6E_PG_URL", "").strip()

BACKEND = Path(__file__).resolve().parents[1]
MIGRATION = BACKEND / "alembic" / "versions" / "on6_root_benutzer.py"

GEMEINDE_ZEILE = "Gemeinde Einstellungen"
ROOT = "gruender@gemeinde.example"
ZWEITER = "spaeter@gemeinde.example"
GESPERRT = "gesperrt@gemeinde.example"

#: Timeout fuer einen ``alembic``-Lauf auf der Wegwerf-DB. Die Kette hat ueber
#: 100 Migrationen; warm ~25 s, auf kaltem Dateisystem deutlich mehr.
ALEMBIC_TIMEOUT = int(os.environ.get("ON6E_ALEMBIC_TIMEOUT", "600"))


# ── 1. Quelltext-Pruefung (immer, ohne Netz) ────────────────────────────────


def _quelle() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _anweisungen(quelle: str) -> list[str]:
    """Alle ``sa.text(…)``-Blöcke der Migration (Klammern werden gezaehlt)."""
    bloecke: list[str] = []
    for treffer in re.finditer(r"sa\.text\(", quelle):
        tiefe, i = 1, treffer.end()
        while i < len(quelle) and tiefe:
            if quelle[i] == "(":
                tiefe += 1
            elif quelle[i] == ")":
                tiefe -= 1
            i += 1
        bloecke.append(quelle[treffer.start():i])
    return bloecke


def test_quelltext_kein_insert_select_mit_geteiltem_parameter():
    """Kein ``INSERT … SELECT … WHERE NOT EXISTS`` mit geteiltem Parameter.

    Genau diese Form brach auf PostgreSQL 17 ab (``$1`` einmal als
    ``character varying`` der Zielecke, einmal als Parameter der
    ``WHERE``-Bedingung — der Live-Abbruch). Schreibvorgaenge lesen jetzt erst
    und fuegen dann ein.
    """
    for block in _anweisungen(_quelle()):
        if "INSERT" not in block.upper():
            continue
        assert "WHERE NOT EXISTS" not in block, (
            "INSERT … WHERE NOT EXISTS mit geteiltem Parameter: "
            + " ".join(block.split())[:200]
        )


def test_quelltext_jeder_schreibparameter_hat_cast():
    """Jeder gebundene Parameter einer Schreib-Anweisung ist typisiert.

    ``CAST(:x AS VARCHAR(140))`` legt den Typ EINDEUTIG fest — unabhaengig
    davon, in welcher Spalte der Parameter sonst noch vorkommt.
    """
    geprueft = 0
    for block in _anweisungen(_quelle()):
        if not re.search(r"\b(INSERT|UPDATE)\b", block, re.I):
            continue
        for parameter in set(re.findall(r":([a-z_]+)", block)):
            vorkommen = re.findall(rf":{re.escape(parameter)}\b", block)
            gecastet = re.findall(
                rf"CAST\(\s*:{re.escape(parameter)}\s+AS\s+VARCHAR\(\d+\)\s*\)",
                block,
            )
            assert len(gecastet) == len(vorkommen), (
                f"Parameter :{parameter} ohne CAST in: "
                + " ".join(block.split())[:220]
            )
            geprueft += 1
    assert geprueft >= 5, f"zu wenige gepruefte Parameter ({geprueft})"


def test_quelltext_zeitpunkt_kommt_von_der_datenbank():
    """``created`` kommt aus ``CURRENT_TIMESTAMP``, nie als Parameter.

    Vorfall DM1 (15.10.): ``now()`` als gebundener Parameter scheiterte erst
    an echten Zeilen.
    """
    quelle = _quelle()
    assert "CURRENT_TIMESTAMP" in quelle
    assert not re.search(r":\w*(zeit|now|created)\w*", quelle), \
        "Zeitpunkt als gebundener Parameter"


# ── 2. PostgreSQL (nur mit eigener Wegwerf-DB) ──────────────────────────────

pg = pytest.mark.skipif(
    not PG_URL,
    reason="ON6E_PG_URL nicht gesetzt — PG-Test nur mit Wegwerf-PostgreSQL 17",
)


def _sql(anweisung: str, **werte):
    """Eine Anweisung gegen die Wegwerf-DB; Tupel, bei INSERT leer."""
    import sqlalchemy as sa

    engine = sa.create_engine(PG_URL, future=True)
    try:
        with engine.begin() as conn:
            ergebnis = conn.execute(sa.text(anweisung), werte)
            return list(ergebnis.all()) if ergebnis.returns_rows else []
    finally:
        engine.dispose()


def _alembic(*befehle: str):
    """``alembic <befehl>`` gegen die Wegwerf-DB (wie der App-Start)."""
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
    return ergebnis


def _leere_db() -> None:
    """Leere DB — jeder Fall startet ohne Reste eines Vorlaufs."""
    _sql("DROP SCHEMA IF EXISTS public CASCADE")
    _sql("CREATE SCHEMA public")


def _bis_ux2b() -> None:
    """Bestand herstellen: die Kette bis UNMITTELBAR VOR ``on6_root_benutzer``."""
    _alembic("upgrade", "ux2b_papierkorb")


def _bestand_anlegen(*, gemeinde_zeile: bool) -> None:
    """Bestandsdaten wie im Betrieb: ein aktiver, ein deaktivierter System Manager.

    ``creation`` bewusst so gesetzt, dass der AKTIVE der aeltere ist — die
    Migration muss ihn nehmen und den deaktivierten ueberspringen.
    """
    for name, enabled in ((ROOT, True), (ZWEITER, True), (GESPERRT, False)):
        _sql('INSERT INTO "user" (name, email, full_name, enabled) '
             "VALUES (:n, :n, :n, :e)", n=name, e=enabled)
    _sql(
        "INSERT INTO has_role (name, parent, parenttype, parentfield, role, "
        "docstatus, idx, creation) VALUES "
        "('r1', :a, 'User', 'roles', 'System Manager', 0, 0, '2026-01-02 09:00:00'), "
        "('r2', :b, 'User', 'roles', 'System Manager', 0, 1, '2026-03-01 10:00:00'), "
        "('r3', :c, 'User', 'roles', 'System Manager', 0, 0, '2025-01-01 08:00:00')",
        a=ROOT, b=ZWEITER, c=GESPERRT,
    )
    if gemeinde_zeile:
        _sql("INSERT INTO gemeinde_einstellungen (name) VALUES (:n)",
             n=GEMEINDE_ZEILE)


def _stand() -> dict:
    """Der Zustand, den die Karte sehen will — direkt aus der DB gelesen."""
    hat_spalte = bool(_sql(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'gemeinde_einstellungen' "
        "AND column_name = 'root_benutzer'"
    ))
    hat_tabelle = bool(_sql(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = 'gruppen_root_user'"
    ))
    ergebnis = {"spalte": hat_spalte, "tabelle": hat_tabelle, "root": None,
                "kennrolle": [], "has_role": [], "zeilen": 0,
                "revision": [r[0] for r in _sql(
                    "SELECT version_num FROM alembic_version")]}
    if hat_spalte:
        zeilen = _sql(
            "SELECT name, root_benutzer FROM gemeinde_einstellungen ORDER BY name")
        ergebnis["zeilen"] = len(zeilen)
        for name, root in zeilen:
            if name == GEMEINDE_ZEILE:
                ergebnis["root"] = root
    if hat_tabelle:
        ergebnis["kennrolle"] = [r[0] for r in _sql(
            "SELECT konto FROM gruppen_root_user ORDER BY konto")]
    ergebnis["has_role"] = [r[0] for r in _sql(
        "SELECT parent FROM has_role WHERE role = 'root' ORDER BY parent")]
    return ergebnis


@pg
def test_pg_frische_db_upgrade_erfindet_keinen_root():
    """Leere DB: Kette laeuft durch (kein ``AmbiguousParameter``), ohne root."""
    _leere_db()
    ergebnis = _alembic("upgrade", "head")
    assert "AmbiguousParameter" not in ergebnis.stderr

    stand = _stand()
    assert stand["revision"] == ["on6_root_benutzer"]
    assert stand["spalte"] is True and stand["tabelle"] is True
    assert stand["root"] is None, f"root ohne Konto erfunden: {stand['root']!r}"
    assert stand["kennrolle"] == []
    assert stand["has_role"] == []
    # Die Single-Zeile wurde angelegt, aber ohne root.
    assert stand["zeilen"] == 1


@pg
def test_pg_bestand_mit_gemeinde_zeile_setzt_root():
    """Bestand mit vorhandener Gemeinde-Zeile: aktiver System Manager wird root."""
    _leere_db()
    _bis_ux2b()
    _bestand_anlegen(gemeinde_zeile=True)

    ergebnis = _alembic("upgrade", "head")
    assert "AmbiguousParameter" not in ergebnis.stderr

    stand = _stand()
    assert stand["revision"] == ["on6_root_benutzer"]
    assert stand["root"] == ROOT, stand
    assert stand["kennrolle"] == [ROOT]
    assert stand["has_role"] == [ROOT]
    # Der deaktivierte Administrator ist NICHT root geworden.
    assert GESPERRT not in stand["has_role"]
    assert ZWEITER not in stand["has_role"]


@pg
def test_pg_bestand_ohne_gemeinde_zeile_setzt_root():
    """Bestand OHNE Gemeinde-Zeile — der Live-Fall vom 06.11.

    Die Migration legt die Single-Zeile an (sonst liefe das UPDATE ins Leere
    und es entstuende eine verwaiste ``has_role``-Zeile). Genau hier brach
    PostgreSQL vorher mit ``AmbiguousParameter`` ab.
    """
    _leere_db()
    _bis_ux2b()
    _bestand_anlegen(gemeinde_zeile=False)
    assert _sql("SELECT count(*) FROM gemeinde_einstellungen")[0][0] == 0

    ergebnis = _alembic("upgrade", "head")
    assert "AmbiguousParameter" not in ergebnis.stderr

    stand = _stand()
    assert stand["zeilen"] == 1, "Single-Zeile nicht angelegt"
    assert stand["root"] == ROOT, stand
    assert stand["kennrolle"] == [ROOT]
    assert stand["has_role"] == [ROOT]


@pg
def test_pg_zweiter_upgrade_lauf_aendert_nichts():
    """Idempotenz: der Entrypoint ruft ``alembic upgrade head`` bei JEDEM Start."""
    _leere_db()
    _bis_ux2b()
    _bestand_anlegen(gemeinde_zeile=True)
    _alembic("upgrade", "head")
    vorher = _stand()

    _alembic("upgrade", "head")
    assert _stand() == vorher


@pg
def test_pg_downgrade_und_wieder_upgrade():
    """Rundlauf: ``downgrade`` raeumt auf, ``upgrade`` setzt denselben root."""
    _leere_db()
    _bis_ux2b()
    _bestand_anlegen(gemeinde_zeile=True)
    _alembic("upgrade", "head")
    assert _stand()["root"] == ROOT

    _alembic("downgrade", "ux2b_papierkorb")
    zurueck = _stand()
    assert zurueck["revision"] == ["ux2b_papierkorb"]
    assert zurueck["spalte"] is False
    assert zurueck["tabelle"] is False
    assert zurueck["has_role"] == [], "has_role-Zeile der Kennrolle blieb stehen"

    _alembic("upgrade", "head")
    wieder = _stand()
    assert wieder["revision"] == ["on6_root_benutzer"]
    assert wieder["root"] == ROOT
    assert wieder["kennrolle"] == [ROOT]
    assert wieder["has_role"] == [ROOT]


@pg
def test_pg_alembic_check_ohne_drift():
    """``alembic check``: Modelle und migrierte DB stimmen ueberein."""
    _leere_db()
    _alembic("upgrade", "head")
    ergebnis = _alembic("check")
    assert "No new upgrade operations detected" in (
        ergebnis.stdout + ergebnis.stderr
    ), (ergebnis.stdout + ergebnis.stderr)[-2000:]
