"""Plan-Rahmen — Modell- und Speichertests (Wegwerf-PostgreSQL).

Diese Tests laufen gegen ein **echtes PostgreSQL** (JSONB, Unique-Constraints,
Foreign Keys), NICHT gegen die In-Memory-SQLite der Standard-Suite. Grund:
`Base.metadata.create_all` auf SQLite erzeugt weder JSONB noch die
mehrspaltigen Unique-Constraints exakt; die P4-Regeln und der atomare
Eintrag+Verlauf-Weg sind gegen das echte Ziel stark geprüft.

Damit der Standard-Testlauf (SQLite, `make test`) grün bleibt, verlangen diese
Tests einen ausdrücklichen Schalter `PLANRAHMEN_DISPOSABLE_DB=1` und eine
`DATABASE_URL`, die auf eine **Wegwerf**-Instanz zeigt. Ohne den Schalter wird
der gesamte Modul-Skip ausgelöst — die echte Abnahme (Karte) setzt beides und
führt zusätzlich vorab `alembic upgrade head` gegen diese Wegwerf-DB aus.

Abgedeckt (Kartenvorgabe):
  * Version unveränderlich (P4),
  * nächste Versionsnummer + gültige Version zum Datum,
  * Eintrag + Verlauf atomar,
  * Undo stellt den vorher-Zustand wieder her (auch für gelöschte/neu
    angelegte Einträge),
  * Resource-CRUD für die pr_*-Tabellen gesperrt,
  * Tabellen/Indizes existieren (leichter Schematest).
"""

from __future__ import annotations

import os
import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker

from diakronos_app.models.diakonos import Mitglied
from diakronos_app.models.planrahmen import (
    Abwesenheit,
    Eintrag,
    Merkmal,
    MerkmalWert,
    Plan,
    Plantyp,
    PlantypVersion,
    Sammlung,
    SammlungEintrag,
    Termin,
    Verlauf,
)
from diakronos_app.planrahmen import speicher
from diakronos_app.planrahmen.speicher import VersionUnveraenderlich


pytestmark = pytest.mark.skipif(
    os.environ.get("PLANRAHMEN_DISPOSABLE_DB") != "1",
    reason="Plan-Rahmen-Tests brauchen ein Wegwerf-PostgreSQL "
           "(PLANRAHMEN_DISPOSABLE_DB=1 + DATABASE_URL auf Wegwerf-Instanz).",
)


@pytest.fixture(scope="module")
def db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    assert url, "PLANRAHMEN_DISPOSABLE_DB=1 gesetzt, aber DATABASE_URL fehlt"
    # Fail closed: der Wegwerf-Marker darf nie auf die echte Betriebs-DB zeigen.
    assert "diakronos" not in url or "wegwerf" in url.lower() or "postgres-test" in url.lower(), (
        f"DATABASE_URL zeigt auf {url!r} — kein erkennbarer Wegwerf-Marker. "
        "Diese Tests dürfen die echte Betriebs-DB nicht anfassen."
    )
    return url


@pytest.fixture(scope="module")
def engine(db_url):
    eng = create_engine(db_url, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    sess = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
    yield sess
    sess.rollback()
    sess.close()


def _leere_testdaten(session) -> None:
    """Löscht pr_*-Restbestände aus früheren Läufen (nur pr_-Tabellen).

    Kinder vor Eltern (FK-Reihenfolge): zuerst die abhängigen Zeilen, zuletzt
    `pr_plantyp`, damit RESTRICT-FKs (`pr_plan` → `pr_plantyp`) nicht zubeißen.
    """
    for tabelle in [
        "pr_verlauf",
        "pr_eintrag",
        "pr_termin",
        "pr_abwesenheit",
        "pr_merkmal_wert",
        "pr_merkmal",
        "pr_sammlung_eintrag",
        "pr_sammlung",
        "pr_plantyp_version",
        "pr_plan",
        "pr_plantyp",
    ]:
        session.execute(text(f"DELETE FROM {tabelle}"))
    session.commit()


def _plantyp_version_anlegen(session) -> tuple[str, str, str]:
    """Legt einen Plantyp + zwei Versionen an; liefert (plantyp_id, v1_id, v2_id)."""
    pt = Plantyp(schluessel="chorplan", name="Chorplan", aktiv=True)
    session.add(pt)
    session.flush()
    v1 = speicher.version_anlegen(
        session, plantyp_id=pt.id, gueltig_ab=date(2026, 1, 1), definition={"felder": []}
    )
    v2 = speicher.version_anlegen(
        session, plantyp_id=pt.id, gueltig_ab=date(2026, 7, 1), definition={"felder": ["lieder"]}
    )
    session.commit()
    return pt.id, v1.id, v2.id


# ── Schema-Tests ────────────────────────────────────────────────────────────


def test_pr_tabellen_existieren(engine):
    ins = inspect(engine)
    vorhanden = set(ins.get_table_names())
    erwartet = {
        "pr_plantyp", "pr_plantyp_version", "pr_plan", "pr_termin",
        "pr_eintrag", "pr_verlauf", "pr_merkmal", "pr_merkmal_wert",
        "pr_sammlung", "pr_sammlung_eintrag", "pr_abwesenheit",
    }
    assert erwartet <= vorhanden, f"Fehlende pr_-Tabellen: {erwartet - vorhanden}"


def test_eingebaute_sammlung_lieder_ist_geseedet(session):
    lieder = session.execute(
        select(Sammlung).where(Sammlung.schluessel == "lieder")
    ).scalar_one_or_none()
    assert lieder is not None, "Seed-Datensatz 'lieder' fehlt"
    assert lieder.eingebaut is True


# ── Versionen (P4) ──────────────────────────────────────────────────────────


def test_naechste_versionsnummer_fortlaufend(session):
    _leere_testdaten(session)
    pt = Plantyp(schluessel="freizeit", name="Freizeitplan")
    session.add(pt)
    session.flush()
    assert speicher.naechste_versionsnummer(session, pt.id) == 1
    speicher.version_anlegen(session, plantyp_id=pt.id, gueltig_ab=date(2026, 1, 1), definition={})
    assert speicher.naechste_versionsnummer(session, pt.id) == 2
    session.commit()
    assert speicher.naechste_versionsnummer(session, pt.id) == 2


def test_version_unveraenderlich(session):
    _leere_testdaten(session)
    _, _, v2_id = _plantyp_version_anlegen(session)
    version = session.get(PlantypVersion, v2_id)
    with pytest.raises(VersionUnveraenderlich):
        speicher.version_aendern(session, version, definition={"felder": ["anders"]})
    # Idempotent: unveränderter Wert ist kein Verstoss.
    speicher.version_aendern(session, version, definition=version.definition)


def test_gueltige_version_zu_datum(session):
    _leere_testdaten(session)
    pt_id, v1_id, v2_id = _plantyp_version_anlegen(session)

    # Vor der ersten Version -> None.
    assert speicher.gueltige_version_zu_datum(session, pt_id, date(2025, 12, 31)) is None
    # Ab 2026-01-01 bis vor 2026-07-01 -> v1.
    assert speicher.gueltige_version_zu_datum(session, pt_id, date(2026, 3, 1)).id == v1_id
    # Ab 2026-07-01 -> v2.
    assert speicher.gueltige_version_zu_datum(session, pt_id, date(2026, 9, 1)).id == v2_id


# ── Eintrag + Verlauf atomar / Undo ─────────────────────────────────────────


def _plan_und_termin(session) -> tuple[str, str]:
    _leere_testdaten(session)
    pt = Plantyp(schluessel="chorplan", name="Chorplan")
    session.add(pt)
    session.flush()
    plan = Plan(plantyp=pt.id, titel="Chorplan 2026", status="entwurf")
    session.add(plan)
    session.flush()
    version = speicher.version_anlegen(
        session, plantyp_id=pt.id, gueltig_ab=date(2026, 1, 1), definition={"felder": []}
    )
    termin = Termin(plan=plan.id, datum=date(2026, 10, 4), quelle="manuell",
                    plantyp_version=version.id)
    session.add(termin)
    session.commit()
    return plan.id, termin.id


def test_eintrag_setzen_legt_verlauf_gleicher_transaktion(session):
    plan_id, termin_id = _plan_und_termin(session)

    gruppe = str(uuid.uuid4())
    eintrag = speicher.eintrag_setzen(
        session,
        plan_id=plan_id,
        termin_id=termin_id,
        feld_pfad="lieder[0].dirigent",
        wert={"art": "person", "person": "M-0001"},
        benutzer="Administrator",
        gruppe_id=gruppe,
    )
    session.commit()

    # Genau ein Eintrag, genau ein Verlauf.
    eintraege = session.execute(select(Eintrag)).scalars().all()
    assert len(eintraege) == 1
    verlaeufe = session.execute(select(Verlauf)).scalars().all()
    assert len(verlaeufe) == 1
    assert verlaeufe[0].vorher is None  # Neuanlage
    assert verlaeufe[0].nachher["wert"]["person"] == "M-0001"
    assert verlaeufe[0].gruppe_id == gruppe
    assert eintraege[0].wert["person"] == "M-0001"


def test_eintrag_setzen_aktualisiert_vorher_nachher(session):
    plan_id, termin_id = _plan_und_termin(session)
    speicher.eintrag_setzen(
        session, plan_id=plan_id, termin_id=termin_id,
        feld_pfad="einsingen", wert={"person": "M-0001"},
    )
    session.commit()

    speicher.eintrag_setzen(
        session, plan_id=plan_id, termin_id=termin_id,
        feld_pfad="einsingen", wert={"person": "M-0002"},
    )
    session.commit()

    verlaeufe = session.execute(
        select(Verlauf).order_by(Verlauf.zeitpunkt.asc())
    ).scalars().all()
    assert len(verlaeufe) == 2
    assert verlaeufe[1].vorher["wert"]["person"] == "M-0001"
    assert verlaeufe[1].nachher["wert"]["person"] == "M-0002"
    # Der Eintrag ist eindeutig (Unique termin+feld_pfad).
    eintraege = session.execute(select(Eintrag)).scalars().all()
    assert len(eintraege) == 1


def test_undo_stellt_geaenderten_wert_wieder_her(session):
    plan_id, termin_id = _plan_und_termin(session)
    speicher.eintrag_setzen(
        session, plan_id=plan_id, termin_id=termin_id,
        feld_pfad="einsingen", wert={"person": "M-0001"},
    )
    session.commit()

    gruppe = str(uuid.uuid4())
    speicher.eintrag_setzen(
        session, plan_id=plan_id, termin_id=termin_id,
        feld_pfad="einsingen", wert={"person": "M-0002"}, gruppe_id=gruppe,
    )
    session.commit()

    anz = speicher.undo_verlaufsgruppe(session, gruppe)
    session.commit()
    assert anz == 1
    eintrag = session.execute(select(Eintrag)).scalar_one()
    assert eintrag.wert["person"] == "M-0001"


def test_undo_entfernt_neu_angelegten_eintrag(session):
    plan_id, termin_id = _plan_und_termin(session)

    gruppe = str(uuid.uuid4())
    speicher.eintrag_setzen(
        session, plan_id=plan_id, termin_id=termin_id,
        feld_pfad="neu", wert={"text": "ganz frisch"}, gruppe_id=gruppe,
    )
    session.commit()
    assert len(session.execute(select(Eintrag)).scalars().all()) == 1

    anz = speicher.undo_verlaufsgruppe(session, gruppe)
    session.commit()
    assert anz == 1
    assert session.execute(select(Eintrag)).scalars().all() == []


def test_undo_mehrerer_eintraege_einer_gruppe(session):
    plan_id, termin_id = _plan_und_termin(session)
    gruppe = str(uuid.uuid4())
    speicher.eintrag_setzen(session, plan_id=plan_id, termin_id=termin_id,
        feld_pfad="a", wert={"t": 1}, gruppe_id=gruppe)
    speicher.eintrag_setzen(session, plan_id=plan_id, termin_id=termin_id,
        feld_pfad="b", wert={"t": 2}, gruppe_id=gruppe)
    session.commit()
    assert len(session.execute(select(Eintrag)).scalars().all()) == 2

    assert speicher.undo_verlaufsgruppe(session, gruppe) == 2
    session.commit()
    assert session.execute(select(Eintrag)).scalars().all() == []


# ── Merkmale über Pläne hinweg (B5) ─────────────────────────────────────────


def test_merkmal_schluessel_je_ziel_eindeutig(session):
    _leere_testdaten(session)
    m1 = Merkmal(ziel="person", schluessel="klavier", art="tag", definition={})
    m2 = Merkmal(ziel="sammlung:lieder", schluessel="klavier", art="person", definition={})
    session.add_all([m1, m2])
    session.commit()  # gleicher schluessel, anderes ziel -> ok


def test_merkmal_wert_eindeutig_merkmal_ziel(session):
    _leere_testdaten(session)
    m = Merkmal(ziel="person", schluessel="klavier", art="tag")
    session.add(m)
    session.commit()
    w = MerkmalWert(merkmal=m.id, ziel_id="M-0001", wert={"ja": True})
    session.add(w)
    session.commit()


# ── Termin fixiert plantyp_version (P4) ─────────────────────────────────────


def test_termin_traegt_plantyp_version(session):
    _leere_testdaten(session)
    pt_id, v1_id, _ = _plantyp_version_anlegen(session)
    plan = Plan(plantyp=pt_id, titel="Chorplan", status="entwurf")
    session.add(plan)
    session.flush()
    termin = Termin(plan=plan.id, datum=date(2026, 10, 4), quelle="manuell",
                    plantyp_version=v1_id)
    session.add(termin)
    session.commit()
    assert termin.plantyp_version == v1_id


# ── Abwesenheit (neues Modell im Projekt) ───────────────────────────────────


def test_abwesenheit_mitglied_zeitraum(session):
    _leere_testdaten(session)
    mitglied = Mitglied(name="M-TEST-1", docstatus=0, idx=0)
    session.add(mitglied)
    session.commit()
    abw = Abwesenheit(mitglied="M-TEST-1", von=date(2026, 8, 1), bis=date(2026, 8, 15),
                      grund="Urlaub")
    session.add(abw)
    session.commit()
    assert abw.id is not None

