"""Plan-Rahmen PR4 — Migrationstests und Modell-Erweiterungen.

Zwei Ebenen:

1. **Modell-Ebene (SQLite, immer lauffaehig):** die neuen Modell-Constraints
   (`pr_sammlung.umfang`/`plan`, `pr_termin` Engine-Spalten + `bezug`,
   optionales `pr_verlauf.plan` + `pr_verlauf.plantyp`,
   `pr_plan.veroeffentlichter_stand`) werden gegen `Base.metadata.create_all`
   auf In-Memory-SQLite geprueft — CHECKs, partieller Unique-Index und
   FK-Aktionen, soweit SQLite sie nachbildet.

2. **Migrationsebene (Wegwerf-PostgreSQL):** `alembic upgrade pr3_planrahmen`
   -> PR3-Welt mit echten Alt-Daten (Termine OHNE `plantyp_version`) befuellen
   -> `alembic upgrade head` (pr4_planrahmen). Geprueft wird das
   Backfill-Ergebnis (gueltig_ab <= Datum, hoechste Versionsnummer),
   das Fail-closed-Verhalten bei nicht aufloesbaren Terminen (keine erfundene
   Definition, Migrationsabbruch ohne Teil-Effekt), die neuen Spalten/FKs/
   Constraints und der Downgrade auf pr3.

   Wie `tests/test_planrahmen_modell.py` verlangen diese Tests einen
   ausdruecklichen Schalter `PLANRAHMEN_DISPOSABLE_DB=1` und eine
   `DATABASE_URL`, die auf eine **Wegwerf**-Instanz zeigt; ohne den Schalter
   werden sie uebersprungen. Die Wegwerf-DB wird am Anfang des Moduls per
   `DROP SCHEMA public` zurueckgesetzt (der Lauf ist deterministisch und
   rueckt am Ende per Downgrade/Upgrade wieder auf head).
"""

from __future__ import annotations

import os
import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from diakronos_app.models import base as _base_modul  # noqa: F401  (Base-Registrierung)
import diakronos_app.models  # noqa: F401  (alle Modellklassen in Base.metadata)
from diakronos_app.models.base import Base
from diakronos_app.models.planrahmen import (
    Plan,
    Plantyp,
    PlantypVersion,
    Sammlung,
    Termin,
    Verlauf,
)
from diakronos_app.planrahmen import speicher


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Ebene 1: Modell-Constraints auf In-Memory-SQLite ────────────────────────


@pytest.fixture()
def engine_sqlite():
    """Frische In-Memory-SQLite mit allen Tabellen und eingeschaltetem FK-Pfad.

    Die Standard-Suite legt keine FK-Pragmas (conftest-Engine), hier sind
    ON-DELETE-Aktionen (CASCADE/SET NULL) Teil des Vertrags und werden geprueft.
    """
    eng = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    @event.listens_for(eng, "connect")
    def _foreign_keys(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session_sqlite(engine_sqlite):
    sess = sessionmaker(bind=engine_sqlite, autoflush=False, future=True)()
    yield sess
    sess.rollback()
    sess.close()


def _plantyp(session, schluessel: str = "chorplan") -> Plantyp:
    pt = Plantyp(schluessel=schluessel, name=schluessel.title(), aktiv=True)
    session.add(pt)
    session.flush()
    return pt


def _version(session, plantyp: Plantyp, gueltig_ab: date = date(2026, 1, 1)) -> PlantypVersion:
    return speicher.version_anlegen(
        session, plantyp_id=plantyp.id, gueltig_ab=gueltig_ab, definition={"felder": []}
    )


def _plan(session, plantyp: Plantyp, titel: str = "Chorplan 2026") -> Plan:
    plan = Plan(plantyp=plantyp.id, titel=titel, status="entwurf")
    session.add(plan)
    session.flush()
    return plan


def _termin(session, plan: Plan, version: PlantypVersion, datum: date = date(2026, 10, 4)) -> Termin:
    termin = Termin(plan=plan.id, datum=datum, quelle="manuell", plantyp_version=version.id)
    session.add(termin)
    session.flush()
    return termin


def _sperre_meldung(fehler_text: str, constraint: str, *spalten: str) -> None:
    """Assert auf eine Verletzung — dialect aware.

    PostgreSQL nennt den verletzten Constraint (z. B.
    ``uq_pr_sammlung_schluessel_plan``), SQLite bei Unique-VerstoesSEN nur die
    beteiligten Spalten (``UNIQUE constraint failed: pr_sammlung.schluessel,
    pr_sammlung.plan``). Beides gilt als Treffer.
    """
    if constraint in fehler_text:
        return
    assert all(s in fehler_text for s in spalten), (
        f"unerwartete Sperr-Meldung: {fehler_text!r} — weder Constraint "
        f"{constraint!r} noch Spalten {spalten!r} darin enthalten"
    )


# ── Sammlung: Umfang + planbezoegene Eindeutigkeit ──────────────────────────


def test_sammlung_umfang_grundwert_gemeinde(session_sqlite):
    """Ohne Angabe gilt umfang='gemeinde' (Vorgabe des Plantyp-Schemas)."""
    s = Sammlung(schluessel="lieder", name="Lieder")
    session_sqlite.add(s)
    session_sqlite.commit()
    assert s.umfang == "gemeinde"
    assert s.plan is None


def test_sammlung_umfang_nur_gemeinde_oder_plan(session_sqlite):
    s = Sammlung(schluessel="x", name="X", umfang="kirchenkreis")
    session_sqlite.add(s)
    with pytest.raises(Exception) as fehler:
        session_sqlite.commit()
    assert "ck_pr_sammlung_umfang_werte" in str(fehler.value)
    session_sqlite.rollback()


def test_sammlung_umfang_plan_ohne_plan_ist_verboten(session_sqlite):
    """Konsistenz-Check: umfang='plan' ohne plan-Verweis bricht."""
    s = Sammlung(schluessel="themen", name="Themen", umfang="plan", plan=None)
    session_sqlite.add(s)
    with pytest.raises(Exception) as fehler:
        session_sqlite.commit()
    assert "ck_pr_sammlung_umfang_plan" in str(fehler.value)
    session_sqlite.rollback()


def test_sammlung_umfang_gemeinde_darf_keinen_plan_tragen(session_sqlite):
    """Konsistenz-Check in der anderen Richtung: plan-Verweis nur bei umfang='plan'."""
    pt = _plantyp(session_sqlite)
    plan = _plan(session_sqlite, pt)
    s = Sammlung(schluessel="lieder", name="Lieder", umfang="gemeinde", plan=plan.id)
    session_sqlite.add(s)
    with pytest.raises(Exception) as fehler:
        session_sqlite.commit()
    assert "ck_pr_sammlung_umfang_plan" in str(fehler.value)
    session_sqlite.rollback()


def test_sammlung_schluessel_je_plan_eindeutig(session_sqlite):
    """Gleicher schluessel in zwei verschiedenen Plaenen ist erlaubt."""
    pt = _plantyp(session_sqlite)
    p1 = _plan(session_sqlite, pt, "Freizeit 2026")
    p2 = _plan(session_sqlite, pt, "Freizeit 2027")
    session_sqlite.add_all([
        Sammlung(schluessel="bibelarbeiten", name="BA 2026", umfang="plan", plan=p1.id),
        Sammlung(schluessel="bibelarbeiten", name="BA 2027", umfang="plan", plan=p2.id),
    ])
    session_sqlite.commit()  # zweimal gleicher schluessel, anderes plan -> ok

    session_sqlite.add(
        Sammlung(schluessel="bibelarbeiten", name="BA 2026 nochmal", umfang="plan", plan=p1.id)
    )
    with pytest.raises(Exception) as fehler:
        session_sqlite.commit()
    _sperre_meldung(str(fehler.value), "uq_pr_sammlung_schluessel_plan",
                    "pr_sammlung.schluessel", "pr_sammlung.plan")
    session_sqlite.rollback()


def test_sammlung_schluessel_ohne_plan_eindeutig(session_sqlite):
    """Partieller Unique-Index: zwei gemeinde-weite Sammlungen gleichen
    schluessel sind verboten (ersetzt das fruehere Unique auf schluessel)."""
    session_sqlite.add(Sammlung(schluessel="lieder", name="Lieder"))
    session_sqlite.commit()

    session_sqlite.add(Sammlung(schluessel="lieder", name="Lieder (doppelt)"))
    with pytest.raises(Exception) as fehler:
        session_sqlite.commit()
    _sperre_meldung(str(fehler.value), "uq_pr_sammlung_schluessel_ohne_plan",
                    "pr_sammlung.schluessel")
    session_sqlite.rollback()


def test_sammlung_plan_loeschen_loescht_plan_sammlung(session_sqlite):
    """FK pr_sammlung.plan ON DELETE CASCADE."""
    pt = _plantyp(session_sqlite)
    plan = _plan(session_sqlite, pt)
    s = Sammlung(schluessel="themen", name="Themen", umfang="plan", plan=plan.id)
    session_sqlite.add(s)
    session_sqlite.commit()

    session_sqlite.delete(plan)
    session_sqlite.commit()
    assert session_sqlite.execute(select(Sammlung)).scalars().all() == []


# ── Termin: Engine-Kontextspalten + plantyp_version Pflicht ─────────────────


def test_termin_grundwerte_aus_engine_modell(session_sqlite):
    """reihe='standard', index=0, positionsnr_im_monat=1, position_von_hinten=1,
    ablauf={} — dieselben Grundwerte wie `engine.modell.Termin`."""
    pt = _plantyp(session_sqlite)
    v = _version(session_sqlite, pt)
    plan = _plan(session_sqlite, pt)
    t = _termin(session_sqlite, plan, v)
    session_sqlite.commit()
    assert t.reihe == "standard"
    assert t.index == 0
    assert t.positionsnr_im_monat == 1
    assert t.position_von_hinten == 1
    assert t.ablauf == {}
    assert t.bezug is None


def test_termin_plantyp_version_ist_pflicht(session_sqlite):
    """Snapshot/Undo: jeder Termin traegt seine unveraenderliche Version."""
    pt = _plantyp(session_sqlite)
    plan = _plan(session_sqlite, pt)
    session_sqlite.add(Termin(plan=plan.id, datum=date(2026, 10, 4), quelle="manuell"))
    with pytest.raises(Exception):
        session_sqlite.commit()
    session_sqlite.rollback()


def test_termin_bezug_ist_self_fk_mit_set_null(session_sqlite):
    """bezug -> pr_termin.id, ON DELETE SET NULL (abgeleitete Reihen)."""
    pt = _plantyp(session_sqlite)
    v = _version(session_sqlite, pt)
    plan = _plan(session_sqlite, pt)
    t_basis = _termin(session_sqlite, plan, v)
    t_abgeleitet = _termin(session_sqlite, plan, v)
    t_abgeleitet.bezug = t_basis.id
    session_sqlite.commit()

    session_sqlite.delete(t_basis)
    session_sqlite.commit()
    assert session_sqlite.get(Termin, t_abgeleitet.id).bezug is None


# ── Verlauf: optionales plan + plantyp fuer globale Schreibdienste ──────────


def test_verlauf_plan_ist_optional(session_sqlite):
    """Globale Schreibdienste (Plantyp/Merkmal/Abwesenheit ohne Plan)
    schreiben Verlauf mit plan=None — Undo-Einheit bleibt die gruppe_id."""
    pt = _plantyp(session_sqlite)
    gruppe = _uuid()
    v = Verlauf(aktion="plantyp_angelegt", plan=None, plantyp=pt.id, gruppe_id=gruppe)
    session_sqlite.add(v)
    session_sqlite.commit()
    assert v.plan is None
    assert v.gruppe_id == gruppe


def test_verlauf_plantyp_wird_null_statt_geloescht(session_sqlite):
    """FK pr_verlauf.plantyp ON DELETE SET NULL: der Verlauf eines geloeschten
    Plantyps bleibt erhalten (Undo-Basis), nur die Referenz faellt aus."""
    pt_global = _plantyp(session_sqlite, "globaler-plantyp")
    v = Verlauf(aktion="plantyp_geaendert", plan=None, plantyp=pt_global.id)
    session_sqlite.add(v)
    session_sqlite.commit()

    session_sqlite.delete(pt_global)
    session_sqlite.commit()
    verlauf = session_sqlite.execute(select(Verlauf)).scalar_one()
    assert verlauf.plantyp is None
    assert verlauf.aktion == "plantyp_geaendert"


# ── Plan: veroeffentlichter Stand ───────────────────────────────────────────


def test_plan_veroeffentlichter_stand_ist_optional(session_sqlite):
    """Beim Veroeffentlichen eingefrorener Schnappschuss; bis dahin None.
    (Die API-Sichtregel fuer Nicht-Berechtigte kommt mit dem Endpunkt-PR.)"""
    pt = _plantyp(session_sqlite)
    plan = _plan(session_sqlite, pt)
    session_sqlite.commit()
    assert plan.veroeffentlichter_stand is None

    snapshot = {"stand_am": "2026-10-01", "termine": [{"datum": "2026-10-04"}]}
    plan.veroeffentlichter_stand = snapshot
    session_sqlite.commit()
    assert session_sqlite.get(Plan, plan.id).veroeffentlichter_stand == snapshot


# ── Ebene 2: Migration gegen Wegwerf-PostgreSQL ─────────────────────────────

BACKEND = Path(__file__).resolve().parents[1]

# Feste Kennungen der PR3-Testwelt (lesbar in Assertions).
PT_ID = "10000000-0000-0000-0000-0000000000pt"
V1_ID = "10000000-0000-0000-0000-0000000000v1"
V2_ID = "10000000-0000-0000-0000-0000000000v2"
V3_ID = "10000000-0000-0000-0000-0000000000v3"
P1_ID = "10000000-0000-0000-0000-0000000000p1"
P2_ID = "10000000-0000-0000-0000-0000000000p2"
PT2_ID = "10000000-0000-0000-0000-000000000002"
T_ALT_ID = "10000000-0000-0000-0000-000000000t01"  # 2026-03-01 -> v1
T_NEU_ID = "10000000-0000-0000-0000-000000000t02"  # 2026-09-01 -> v3
T_GRENZE_ID = "10000000-0000-0000-0000-000000000t03"  # 2026-07-01 -> v3 (gueltig_ab == datum)
T_ZU_FRUEH_ID = "10000000-0000-0000-0000-000000000t04"  # 2025-12-31 -> nicht aufloesbar


def _alembic_cfg(url: str):
    """Alembic-Config fuer die Wegwerf-DB (env.py liest settings.database_url)."""
    from alembic.config import Config
    from diakronos_app.settings import settings

    settings.database_url = url  # derselbe Singleton, den env.py liest
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return cfg


def _pr3_welt_beifuellen(engine) -> None:
    """Legt PR3-Alt-Daten an: Plantyp mit 3 Versionen, 2 Plaene, 4 Termine
    OHNE plantyp_version (die zu 100% per Migration aufgeloest werden)."""
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO pr_plantyp (id, schluessel, name, aktiv) "
            "VALUES (:id, 'chorplan', 'Chorplan', true)"
        ), {"id": PT_ID})
        conn.execute(text(
            "INSERT INTO pr_plantyp (id, schluessel, name, aktiv) "
            "VALUES (:id, 'losbarer-global', 'Globaler Plantyp', true)"
        ), {"id": PT2_ID})
        for vid, nr, ab in ((V1_ID, 1, "2026-01-01"), (V2_ID, 2, "2026-07-01"), (V3_ID, 3, "2026-07-01")):
            conn.execute(text(
                "INSERT INTO pr_plantyp_version "
                "(id, plantyp, versionsnummer, gueltig_ab, definition, schema_version) "
                "VALUES (:id, :plantyp, :nr, :ab, '{}'::jsonb, '1')"
            ), {"id": vid, "plantyp": PT_ID, "nr": nr, "ab": ab})
        for pid, titel in ((P1_ID, "Chorplan 2026"), (P2_ID, "Chorplan 2027")):
            conn.execute(text(
                "INSERT INTO pr_plan (id, plantyp, titel, parameter, status) "
                "VALUES (:id, :plantyp, :titel, '{}'::jsonb, 'entwurf')"
            ), {"id": pid, "plantyp": PT_ID, "titel": titel})
        for tid, pid, datum in (
            (T_ALT_ID, P1_ID, "2026-03-01"),
            (T_NEU_ID, P1_ID, "2026-09-01"),
            (T_GRENZE_ID, P1_ID, "2026-07-01"),
            (T_ZU_FRUEH_ID, P2_ID, "2025-12-31"),
        ):
            conn.execute(text(
                "INSERT INTO pr_termin (id, plan, datum, anlaesse, quelle, entfaellt) "
                "VALUES (:id, :plan, :datum, '[]'::jsonb, 'manuell', false)"
            ), {"id": tid, "plan": pid, "datum": datum})


@pytest.fixture(scope="module")
def migrationslauf():
    """Fuehrt die PR4-Migration zweimal aus: fail-closed-Versuch, dann sauber.

    Ablauf (deterministisch, Modul-Reihenfolge):
      1. Wegwerf-DB per DROP SCHEMA zuruecksetzen, `upgrade pr3_planrahmen`,
      2. PR3-Alt-Daten befuellen (inkl. nicht aufloesbarem Termin),
      3. `upgrade head` -> muss scheitern (fail closed, kein Teil-Effekt),
      4. den nicht aufloesbaren Termin loeschen, `upgrade head` -> erfolgreich.
    """
    from alembic import command
    from alembic.runtime.migration import MigrationContext

    if os.environ.get("PLANRAHMEN_DISPOSABLE_DB") != "1":
        pytest.skip(
            "Plan-Rahmen-Migrationstests brauchen ein Wegwerf-PostgreSQL "
            "(PLANRAHMEN_DISPOSABLE_DB=1 + DATABASE_URL auf Wegwerf-Instanz)."
        )
    url = os.environ.get("DATABASE_URL")
    assert url, "PLANRAHMEN_DISPOSABLE_DB=1 gesetzt, aber DATABASE_URL fehlt"
    assert "diakronos" not in url or "wegwerf" in url.lower() or "postgres-test" in url.lower(), (
        f"DATABASE_URL zeigt auf {url!r} — kein erkennbarer Wegwerf-Marker. "
        "Diese Tests duerfen die echte Betriebs-DB nicht anfassen."
    )

    eng = create_engine(url, future=True)
    try:
        with eng.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))

        cfg = _alembic_cfg(url)
        command.upgrade(cfg, "pr3_planrahmen")
        _pr3_welt_beifuellen(eng)

        # ── Versuch 1: nicht aufloesbarer Termin -> fail closed ────────────
        fehler = None
        try:
            command.upgrade(cfg, "head")
        except Exception as exc:  # noqa: BLE001 — jeder Abbruch zaehlt
            fehler = exc
        with eng.connect() as conn:
            revision_nach_abbruch = MigrationContext.configure(conn).get_current_revision()
        spalten_nach_abbruch = {c["name"] for c in inspect(eng).get_columns("pr_termin")}
        with eng.connect() as conn:
            zu_frueh = conn.execute(
                text("SELECT plantyp_version FROM pr_termin WHERE id = :id"),
                {"id": T_ZU_FRUEH_ID},
            ).scalar()

        # ── Aufraeumen, dann sauberer Durchlauf ────────────────────────────
        with eng.begin() as conn:
            conn.execute(text("DELETE FROM pr_termin WHERE id = :id"), {"id": T_ZU_FRUEH_ID})
        command.upgrade(cfg, "head")

        session = sessionmaker(bind=eng, autoflush=False, future=True)()
        yield {
            "engine": eng,
            "cfg": cfg,
            "session": session,
            "fehler": fehler,
            "revision_nach_abbruch": revision_nach_abbruch,
            "spalten_nach_abbruch": spalten_nach_abbruch,
            "plantyp_version_nach_abbruch": zu_frueh,
        }
        session.close()
    finally:
        eng.dispose()


@pytest.fixture(scope="module")
def mig_session(migrationslauf):
    return migrationslauf["session"]


def test_nicht_aufloesbarer_termin_bricht_migration_ab(migrationslauf):
    """Fail closed: ohne gueltige Version zum Termin-Datum wird NICHTS
    erfunden und nichts teilweise geaendert — der Lauf bleibt auf pr3."""
    assert migrationslauf["fehler"] is not None, (
        "upgrade head muss bei nicht aufloesbarem Termin scheitern"
    )
    assert migrationslauf["revision_nach_abbruch"] == "pr3_planrahmen", (
        "der abgebrochene Lauf darf keine Teilwirkung hinterlassen"
    )
    assert "reihe" not in migrationslauf["spalten_nach_abbruch"], (
        "Spalten von pr4 duerfen nach dem Abbruch nicht existieren"
    )
    assert migrationslauf["plantyp_version_nach_abbruch"] is None, (
        "kein erfundener Versionsverweis — der NULL-Wert bleibt unangetastet"
    )


def test_backfill_loest_versionsbezug_nach_gueltig_ab_und_nr(mig_session, migrationslauf):
    """gueltig_ab <= datum, hoechste Versionsnummer gewinnt; gueltig_ab ==
    datum zaehlt; vor der ersten Version aufloesbar."""
    erwartet = {T_ALT_ID: V1_ID, T_NEU_ID: V3_ID, T_GRENZE_ID: V3_ID}
    for tid, vid in erwartet.items():
        wert = mig_session.execute(
            text("SELECT plantyp_version FROM pr_termin WHERE id = :id"), {"id": tid}
        ).scalar()
        assert wert == vid, f"Termin {tid}: {wert!r} statt {vid!r}"
    verwaist = mig_session.execute(
        text("SELECT count(*) FROM pr_termin WHERE plantyp_version IS NULL")
    ).scalar()
    assert verwaist == 0


def test_termin_plantyp_version_ist_in_db_not_null(mig_session, migrationslauf):
    is_nullable = mig_session.execute(text(
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_name = 'pr_termin' AND column_name = 'plantyp_version'"
    )).scalar()
    assert is_nullable == "NO"


def test_termin_traegt_engine_standardwerte(mig_session, migrationslauf):
    """Bestehende Zeilen bekommen die Defaults; neue Zeilen aus dem Modell
    liefern dieselben Werte wie engine.modell.Termin (Modell <-> Migration)."""
    reihe, index, im_monat, von_hinten, ablauf = mig_session.execute(text(
        "SELECT reihe, \"index\", positionsnr_im_monat, position_von_hinten, ablauf "
        "FROM pr_termin WHERE id = :id"
    ), {"id": T_ALT_ID}).one()
    assert (reihe, index, im_monat, von_hinten) == ("standard", 0, 1, 1)
    assert ablauf == {}

    termin = mig_session.get(Termin, T_ALT_ID)
    mig_session.add(Termin(
        plan=termin.plan, datum=date(2027, 1, 3), quelle="manuell",
        plantyp_version=termin.plantyp_version,
    ))
    mig_session.commit()
    neu = mig_session.execute(
        select(Termin).where(Termin.datum == date(2027, 1, 3))
    ).scalar_one()
    assert (neu.reihe, neu.index, neu.positionsnr_im_monat, neu.position_von_hinten) == (
        "standard", 0, 1, 1,
    )
    assert neu.ablauf == {}


def test_termin_bezug_fk_set_null(mig_session, migrationslauf):
    mig_session.execute(text(
        "INSERT INTO pr_termin (id, plan, datum, anlaesse, quelle, entfaellt, "
        "plantyp_version, reihe, bezug) "
        "VALUES (:id, :plan, '2026-10-11', '[]'::jsonb, 'manuell', false, :pv, 'standard', :bezug)"
    ), {"id": _uuid(), "plan": P1_ID, "pv": V1_ID, "bezug": T_ALT_ID})
    mig_session.commit()

    mig_session.delete(mig_session.get(Termin, T_ALT_ID))
    mig_session.commit()
    rest = mig_session.execute(text(
        "SELECT count(*) FROM pr_termin WHERE bezug IS NOT NULL"
    )).scalar()
    assert rest == 0


def test_sammlung_umfang_spalten_und_constraints(mig_session, migrationslauf):
    engine = migrationslauf["engine"]
    insp = inspect(engine)

    checks = {c["name"] for c in insp.get_check_constraints("pr_sammlung")}
    assert {"ck_pr_sammlung_umfang_werte", "ck_pr_sammlung_umfang_plan"} <= checks
    uniques = {c["name"] for c in insp.get_unique_constraints("pr_sammlung")}
    assert "uq_pr_sammlung_schluessel_plan" in uniques
    assert "uq_pr_sammlung_schluessel" not in uniques, "das alte Unique muss entfernt sein"
    teilweise = [
        i for i in insp.get_indexes("pr_sammlung")
        if i["name"] == "uq_pr_sammlung_schluessel_ohne_plan"
    ]
    assert teilweise and teilweise[0]["unique"] is True
    assert "fk_pr_sammlung_plan" in {c["name"] for c in insp.get_foreign_keys("pr_sammlung")}

    # Alt-Bestand 'lieder' traegt per Server-Default umfang='gemeinde'.
    umfang, plan = mig_session.execute(text(
        "SELECT umfang, plan FROM pr_sammlung WHERE schluessel = 'lieder'"
    )).one()
    assert (umfang, plan) == ("gemeinde", None)


def test_sammlung_plan_scoped_anlegen_und_sperren(mig_session, migrationslauf):
    p2 = mig_session.execute(text("SELECT id FROM pr_plan WHERE titel = 'Chorplan 2027'")).scalar()
    for pid in (P1_ID, p2):
        mig_session.add(Sammlung(
            schluessel="predigtreihe", name="Predigtreihe", umfang="plan", plan=pid
        ))
    mig_session.commit()  # gleicher schluessel, zwei Plaene -> ok

    mig_session.add(Sammlung(
        schluessel="predigtreihe", name="Nochmal", umfang="plan", plan=P1_ID
    ))
    with pytest.raises(Exception) as fehler:
        mig_session.commit()
    assert "uq_pr_sammlung_schluessel_plan" in str(fehler.value)
    mig_session.rollback()

    mig_session.add(Sammlung(schluessel="regen", name="Regen", umfang="plan", plan=None))
    with pytest.raises(Exception) as fehler:
        mig_session.commit()
    assert "ck_pr_sammlung_umfang_plan" in str(fehler.value)
    mig_session.rollback()


def test_verlauf_globaler_dienst_mit_plantyp(mig_session, migrationslauf):
    """Verlauf ohne plan (globaler Dienst) traegt den plantyp; das Loeschen
    des Plantyps laesst den Verlauf stehen und nullt nur die Referenz."""
    pt_global = Plantyp(schluessel="losbarer-global-2", name="Global 2", aktiv=True)
    mig_session.add(pt_global)
    mig_session.flush()
    gruppe = _uuid()
    mig_session.add(Verlauf(
        aktion="plantyp_geaendert", plan=None, plantyp=pt_global.id, gruppe_id=gruppe,
    ))
    mig_session.commit()

    mig_session.delete(pt_global)
    mig_session.commit()
    verlauf = mig_session.execute(
        select(Verlauf).where(Verlauf.aktion == "plantyp_geaendert")
    ).scalar_one()
    assert verlauf.plan is None
    assert verlauf.plantyp is None
    assert verlauf.gruppe_id == gruppe


def test_plan_veroeffentlichter_stand_spalte(mig_session, migrationslauf):
    plan = mig_session.get(Plan, P1_ID)
    assert plan.veroeffentlichter_stand is None
    snapshot = {"stand_am": "2026-10-01", "eintraege": []}
    plan.veroeffentlichter_stand = snapshot
    plan.status = "veroeffentlicht"
    mig_session.commit()
    assert mig_session.get(Plan, P1_ID).veroeffentlichter_stand == snapshot


def test_downgrade_zu_pr3_und_wieder_hoch(migrationslauf):
    """Downgrade entfernt alle PR4-Spalten/Constraints und stellt das
    PR3-Schema (inkl. Unique auf schluessel) wieder her."""
    from alembic import command

    cfg = migrationslauf["cfg"]
    eng = migrationslauf["engine"]
    # Kein offener Leser darf das DDL in einem anderen Connection blockieren.
    migrationslauf["session"].rollback()
    with pytest.raises(RuntimeError, match="PR3.*nicht darstellbar"):
        command.downgrade(cfg, "pr3_planrahmen")
    assert "umfang" in {c["name"] for c in inspect(eng).get_columns("pr_sammlung")}
    # Nur die explizit angelegten Wegwerf-Fixtures bereinigen; die Migration
    # selbst darf inkompatible Anwendungsdaten niemals löschen.
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM pr_verlauf WHERE plan IS NULL"))
        conn.execute(text("DELETE FROM pr_sammlung WHERE umfang = 'plan'"))
    command.downgrade(cfg, "pr3_planrahmen")

    insp = inspect(eng)
    sammlung_spalten = {c["name"] for c in insp.get_columns("pr_sammlung")}
    assert "umfang" not in sammlung_spalten and "plan" not in sammlung_spalten
    uniques = {c["name"] for c in insp.get_unique_constraints("pr_sammlung")}
    assert "uq_pr_sammlung_schluessel" in uniques
    termin_spalten = {c["name"] for c in insp.get_columns("pr_termin")}
    for spalte in ("reihe", "bezug", "ablauf", "index", "positionsnr_im_monat", "position_von_hinten"):
        assert spalte not in termin_spalten, f"{spalte} muss beim Downgrade verschwinden"
    verlauf_spalten = {c["name"] for c in insp.get_columns("pr_verlauf")}
    assert "plantyp" not in verlauf_spalten
    plan_spalten = {c["name"] for c in insp.get_columns("pr_plan")}
    assert "veroeffentlichter_stand" not in plan_spalten

    # Zurueck auf head, damit der Modul-Lauf im Prinzip wiederholbar bleibt.
    command.upgrade(cfg, "head")
    insp = inspect(eng)
    assert "umfang" in {c["name"] for c in insp.get_columns("pr_sammlung")}
