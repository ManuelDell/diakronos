"""DRIFT-1 — Modell und migrierte Datenbank laufen nicht auseinander.

`alembic check` vergleicht `Base.metadata` mit dem Stand, den die Migrationen
in einer ECHTEN PostgreSQL-Datenbank hinterlassen. Ein reiner SQLite-Lauf sieht
den Unterschied nicht: dort entsteht das Schema aus denselben Metadaten, die
verglichen werden — der Vergleich ist dann per Konstruktion leer.

BEFUND (NET-1): der Lauf im App-Image meldete dauerhaft

    New upgrade operations detected: modify_nullable 'element.name'

Weil das Modell `name` als nullbar deklarierte (`Mapped[str | None]`, PUB-2),
die Spalte in der Datenbank aber NOT NULL ist — so legt die Baseline
`p1bmodelle` sie an, so steht sie im Betrieb. Fachlich richtig ist NOT NULL:
`name` ist der Primaerschluessel und traegt die Termin-Kennung, die Anzeige
steht in `element_name`. Deshalb wurde das MODELL angeglichen, nicht die
Datenbank (keine Migration).

Dieser Test haelt den Befund fest: er laeuft nur mit einer ausdruecklichen
Wegwerf-Datenbank (`DRIFT1_POSTGRES_URL=…*_test`, eigener Port, eigenes Netz)
und verweigert jede andere — die Betriebs-DB ist damit strukturell
unerreichbar. Ohne die Variable wird er MIT BEGRUENDUNG uebersprungen, nicht
still „gruen".
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

#: Wurzel des Backends — im Image `/app`, im Repo `<repo>/backend`.
BACKEND = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    not os.environ.get("DRIFT1_POSTGRES_URL"),
    reason="nur mit DRIFT1_POSTGRES_URL (Wegwerf-PostgreSQL, Name endet auf _test)",
)


def _url() -> str:
    """Wegwerf-URL aus der ENV — mit harter Schranke gegen den Betrieb."""
    url = str(os.environ["DRIFT1_POSTGRES_URL"])
    assert url.startswith("postgresql"), "DRIFT1_POSTGRES_URL muss ein PostgreSQL sein"
    assert url.rsplit("/", 1)[-1].split("?")[0].endswith("_test"), (
        "DRIFT1_POSTGRES_URL muss eine Wegwerf-Datenbank sein (Name endet auf _test)"
    )
    # Namensteile, die auf den Betrieb zeigen, sind hier ein Fehler.
    assert "diakronos-standalone" not in url, "Betriebs-DB ist tabu"
    return url


def _alembic(*args: str) -> subprocess.CompletedProcess:
    """`alembic` im Backend-Verzeichnis, DB-URL aus der Wegwerf-Variable."""
    env = dict(os.environ)
    # alembic/env.py liest die URL ueber settings (DATABASE_URL) — die
    # Anwendungs-Konfiguration, nicht `DRIFT1_POSTGRES_URL`.
    env["DATABASE_URL"] = _url()
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(BACKEND / "alembic.ini"), *args],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )


def _leeren() -> None:
    """Wegwerf-DB auf „kein Schema" setzen — fuer einen deterministischen Lauf.

    Der Test raeumt das Schema MITTELS DROP SCHEMA. Grund: `alembic downgrade`
    ist unterhalb von `p1bmodelle` nicht durchgaengig lauffaehig (der
    Downgrade der Baseline scheitert an `dropping table mitglied` wegen des
    FK-Zyklus `dienstplan <-> mitglied` — `DependentObjectsStillExist`).
    Den Abbau der Baseline deckt dieser Test bewusst NICHT ab; geprueft wird
    der AUFBAU (`upgrade head`) und danach der Vergleich mit dem Modell.
    """
    from sqlalchemy import create_engine, text

    engine = create_engine(_url())
    try:
        with engine.begin() as c:
            c.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            c.execute(text("CREATE SCHEMA public"))
    finally:
        engine.dispose()


@pytest.fixture(scope="module")
def migriert():
    """Frische Wegwerf-DB: Schema leeren, dann `upgrade head`."""
    _leeren()
    hoch = _alembic("upgrade", "head")
    assert hoch.returncode == 0, f"upgrade head fehlgeschlagen:\n{hoch.stderr}"
    return True


def test_alembic_check_ohne_befund(migriert):
    """`alembic check` meldet KEINE Abweichung Modell <-> migrierte DB.

    DRIFT-1/`element.name`: vor dem Angleichen des Modells stand hier
    „New upgrade operations detected: modify_nullable 'element.name'".
    """
    lauf = _alembic("check")
    ausgabe = f"{lauf.stdout}\n{lauf.stderr}"
    assert lauf.returncode == 0, f"alembic check meldet Drift:\n{ausgabe}"
    assert "modify_nullable" not in ausgabe, ausgabe
    assert "element.name" not in ausgabe, ausgabe


def test_element_name_ist_not_null(migriert):
    """Die Zusage hinter dem Test: `element.name` ist NOT NULL — in Code und DB."""
    from sqlalchemy import create_engine, inspect

    from diakronos_app.models.kronos import Element

    assert Element.__table__.c.name.nullable is False, (
        "Modell muss `element.name` als NOT NULL deklarieren (DRIFT-1)"
    )

    engine = create_engine(_url())
    try:
        spalten = {s["name"]: s for s in inspect(engine).get_columns("element")}
    finally:
        engine.dispose()
    assert spalten["name"]["nullable"] is False, spalten["name"]
