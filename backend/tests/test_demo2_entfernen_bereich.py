"""DEMO-2 (Nacharbeit): `--entfernen` trifft NUR die Demo — Abbruch bei fremden Konten.

Zwei Punkte aus der Review zur ersten Fassung:

1. „Gruppe 3“ ist ein allgemeiner Name. Fruehere Fassung loeschte Untergruppen
   allein ueber den Namen — eine gleichnamige ECHTE Untergruppe unter einer
   fremden Gruppe waere mitgeloescht worden. Ebenso eine echte Buchung, deren
   `moderiert_von` zufaellig auf ein Demo-Konto zeigt, und ein echtes Konto,
   das nur zufaellig wie ein Demo-Konto heisst.
2. `entfernen()` nullt `audit_log.actor` und loescht die Konten. Gehoeren die
   Konten in dieser Datenbank gar nicht zur Demo, muss es VOR dem ersten DELETE
   abbrechen und alles unveraendert lassen.

Lauf: SQLite (``patched_db``). Der Nachweis gegen echtes PostgreSQL steht in
``test_demo2_entfernen_pg.py``.
"""

from __future__ import annotations

import importlib
from datetime import date, datetime

import pytest
from sqlalchemy import select, text

STICHTAG = date(2026, 11, 2)


@pytest.fixture()
def demo(patched_db):
    """Laedt das Demo-Modul gegen die Testdatenbank."""
    return importlib.import_module("musterhausen")


def _zaehle(session, tabelle: str, where: str = "", **params) -> int:
    sql = f'SELECT count(*) FROM "{tabelle}"' + (f" WHERE {where}" if where else "")
    return session.execute(text(sql), params).scalar_one()


def _fremde_zeilen_anlegen(session, demo_gruppen: list[str], demo_untergruppen: list[str],
                           demo_mitglieder: list[str]) -> str:
    """Echte Datensaetze, die die Demo NICHT anfassen darf.

    * eine ECHTE Untergruppe (``untergruppenname`` „Gruppe 3“ wie ein
      Musikteam, Kennung aber anders) unter einer FREMDEN Gruppe samt
      Mitglied und Verantwortlichem,
    * ein echtes Konto ``audit@example.org`` mit Protokollzeile,
    * eine echte Buchung, die von einem Demo-Konto moderiert wird
      (``ressourcen_buchung.moderiert_von`` -> ``user``) und von einem echten
      Mitglied gebucht wurde.

    Rueckgabe: die Kennung/Alias der fremden Untergruppe.
    """
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import (
        AuditLog, Gruppe, RessourcenBuchung, Untergruppe,
        Untergruppenmitgliedschaft, UntergruppeVerantwortlicher,
    )
    from diakronos_app.models.kronos import Ressource

    jetzt = datetime(2026, 10, 1, 9, 0, 0)
    basis = dict(docstatus=0, idx=0, creation=jetzt, modified=jetzt,
                 owner="Administrator", modified_by="Administrator")
    # Eine fremde Untergruppe darf nie den Namen eines Musikteams tragen (die
    # Demo sucht ueber `name IN (Musikteams)`, und `name` ist der Primaerschluessel).
    # Getestet wird die gefaehrliche Nachbarschaft: gleicher NAME
    # („Team Montag“, so heisst ein Demo-Musikteam), ABER unter einer FREMDEN
    # Dachgruppe. Ohne die Dachgruppen-Bedingung in `entfernen` wuerde sie
    # mitgeloescht.
    fremd_untergruppe = "team-montag-fremd"
    assert fremd_untergruppe not in demo_untergruppen
    fremd_gruppe = "Fremdgruppe"
    assert fremd_gruppe not in demo_gruppen

    session.add(Gruppe(name=fremd_gruppe, gruppenname="Fremdgruppe",
                       status="Aktiv", sichtbarkeit="Alle Mitglieder", **basis))
    session.flush()
    session.add(Untergruppe(name=fremd_untergruppe, untergruppenname="Team Montag",
                            gruppe=fremd_gruppe, status="Aktiv",
                            sichtbarkeit="Alle Mitglieder", **basis))
    session.flush()
    session.add(User(name="audit@example.org", email="audit@example.org",
                     full_name="Echtes Konto", enabled=True))
    session.flush()
    session.add(UntergruppeVerantwortlicher(name="echte-untergruppe-verantwortlich-1",
                                            parent=fremd_untergruppe,
                                            parenttype="Untergruppe",
                                            parentfield="verantwortliche",
                                            user="audit@example.org", **basis))
    session.add(Untergruppenmitgliedschaft(name="echte-untergruppe-mitglied-1",
                                           parent=fremd_untergruppe,
                                           parenttype="Untergruppe",
                                           parentfield="mitglieder",
                                           mitglied=demo_mitglieder[0],
                                           rolle="Mitglied", **basis))
    session.add(AuditLog(name="fremder-audit-eintrag", actor="audit@example.org",
                         action_typ="Änderung", zeitstempel=jetzt,
                         notification_gesendet=False, **basis))
    session.add(Ressource(name="Fremdraum", ressource_name="Fremdraum", typ="Raum",
                          kapazitaet=10, wartung=False, **basis))
    session.flush()
    # `moderiert_von` haengt an `user` — eine echte Buchung, die zufaellig von
    # einem Demo-Konto moderiert wird, muss die Konten-Loeschung ueberleben.
    session.add(RessourcenBuchung(name="fremde-buchung", ressource="Fremdraum",
                                  zweck="Externe Nutzung", status="Bestätigt",
                                  moderiert_von="admin@example.org",
                                  gebucht_von="audit@example.org", **basis))
    session.commit()
    return fremd_untergruppe


def test_demo2_entfernen_trifft_nur_die_demo(engine, session_factory, demo):
    """Seed + echte Fremdzeilen → `entfernen` → Fremdzeilen unveraendert da."""
    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        demo_gruppen = [g["name"] for g in demo.daten.GRUPPEN]
        demo_untergruppen = [t["name"] for t in demo.daten.MUSIKTEAMS]
        demo_mitglieder = [name for (name,) in s.execute(
            text("SELECT name FROM mitglied ORDER BY name")).all()]
        fremd_untergruppe = _fremde_zeilen_anlegen(
            s, demo_gruppen, demo_untergruppen, demo_mitglieder)

    demo.entfernen()

    with session_factory() as s:
        # Fremde Untergruppe und Dachgruppe: bleiben vollstaendig stehen.
        assert _zaehle(s, "untergruppe", "name = :n",
                       n=fremd_untergruppe) == 1
        assert s.execute(
            text("SELECT gruppe FROM untergruppe WHERE name = :n"),
            {"n": fremd_untergruppe}).scalar_one() == "Fremdgruppe"
        assert _zaehle(s, "gruppe", "name = 'Fremdgruppe'") == 1
        # Echtes Konto: Protokollzeile nennt ihn weiterhin.
        assert _zaehle(s, "user", "name = 'audit@example.org'") == 1
        assert s.execute(
            text("SELECT actor FROM audit_log WHERE name = 'fremder-audit-eintrag'")
        ).scalar_one() == "audit@example.org"
        # Echte Buchung: bleibt, samt Moderator-Verweis.
        assert _zaehle(s, "ressourcen_buchung", "name = 'fremde-buchung'") == 1
        assert s.execute(
            text("SELECT moderiert_von FROM ressourcen_buchung "
                 "WHERE name = 'fremde-buchung'")).scalar_one() == "admin@example.org"
        # Die Demo-Untergruppen (Musikteams) sind weg, die fremde nicht.
        for name in demo_untergruppen:
            assert _zaehle(s, "untergruppe", "name = :n", n=name) == 0
        assert _zaehle(s, "untergruppe") >= 1


def test_demo2_entfernen_bricht_ab_wenn_konten_nicht_zur_demo_gehoeren(
        engine, session_factory, demo):
    """Fremdes Konto unter Demo-Adresse → Abbruch VOR dem ersten DELETE."""
    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        # Das Verwaltungskonto gehoert jetzt zu jemand anderem: die
        # Verknuepfung zeigt nicht mehr auf „Miriam Sonnleitner“.
        from diakronos_app.models.diakonos import Mitglied
        s.execute(text('UPDATE mitglied SET "user" = NULL WHERE "user" = :e'),
                  {"e": "admin@example.org"})
        fremd = s.scalar(select(Mitglied.name).where(
            Mitglied.vorname == "Anna", Mitglied.nachname == "Beispiel"))
        s.execute(text('UPDATE mitglied SET "user" = :e WHERE name = :n'),
                  {"e": "admin@example.org", "n": fremd})
        s.commit()

    with pytest.raises(demo.DemoFehler) as fehler:
        demo.entfernen()
    assert "Demo-Merkmale" in str(fehler.value)

    with session_factory() as s:
        # Nichts geloescht, nichts genullt — der Abbruch kam vor dem DELETE.
        assert _zaehle(s, "mitglied") >= 40
        assert _zaehle(s, "gruppe") > 0
        assert _zaehle(s, "user") == 6   # SEED-R1: Verwaltung, Mitglied, 4 Leitungs-Konten
        assert _zaehle(s, "audit_log", "actor IS NULL") == 0


def test_demo2_person_kennung_bricht_statt_anzeigename(demo):
    """Unbekannte Person → DemoFehler, kein stiller Rueckfall (Befund 2)."""
    with pytest.raises(demo.DemoFehler) as fehler:
        demo.person_kennung("Niemand Bekannt")
    assert "Niemand Bekannt" in str(fehler.value)


def test_demo2_entfernen_ohne_kennungsspeicher(engine, session_factory, demo):
    """`--entfernen` im EIGENEN Prozess: `_KENNUNGEN` ist leer (Re-Review-Blocker).

    Der eigentliche Fehler: `_KENNUNGEN` fuellt nur `mitglieder_anlegen`.
    ``musterhausen.py --entfernen`` laeuft als neuer Prozess — dort kannte
    `person_kennung` keine einzige Person und ``entfernen`` brach mit
    ``DemoFehler`` ab, bevor irgendetwas geloescht war. Nur weil die Tests
    Anlegen und Entfernen in DEMSELBEN Prozess aufriefen, blieb das unsichtbar.

    Nachgestellt wird der neue Prozess durch Leeren des Speichers: anlegen →
    ``_KENNUNGEN.clear()`` → ``entfernen`` → alles weg.
    """
    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        demo_mitglieder = [name for (name,) in s.execute(
            text("SELECT name FROM mitglied")).all()]
        assert len(demo_mitglieder) >= 40
        # Eine Abwesenheit haengt an einer MITGLIED-Kennung — genau der Pfad,
        # der `person_kennung` braucht (und der im eigenen Prozess abbrach).
        s.execute(text(
            "INSERT INTO pr_abwesenheit (id, mitglied, von, bis, grund) "
            "VALUES ('abwesenheit-probe', :m, '2026-11-10', '2026-11-12', 'Urlaub')"),
            {"m": demo_mitglieder[0]})
        s.commit()

    demo._KENNUNGEN.clear()

    bericht = demo.entfernen()

    assert "nichts gefunden" not in bericht
    with session_factory() as s:
        for tabelle in ("mitglied", "gruppe", "user", "pr_abwesenheit"):
            assert _zaehle(s, tabelle) == 0, f"{tabelle} ist nach --entfernen nicht leer"
        assert _zaehle(s, "audit_log", "actor IN "
                       "('admin@example.org', 'anna.beispiel@example.org')") == 0


@pytest.mark.timeout(900)  # voller Seed im Unterprozess dauert 1–2 min (global timeout = 60)
def test_demo2_cli_anlegen_und_entfernen_als_unterprozess(tmp_path):
    """Das CLI wirklich starten: ``anlegen`` und dann ``--entfernen``.

    Die In-Prozess-Tests koennen diesen Fehler nicht finden — Anlegen und
    Entfernen liefen dort in DEMSELBEN Modul, ``_KENNUNGEN`` war also gefuellt.
    Erst ein zweiter Prozess hat den Blocker gezeigt. Hier laeuft beides als
    ``python tools/demo/musterhausen.py`` (echtes CLI, echtes ``main()``, echte
    ``SessionLocal``) gegen eine temporaere SQLite-Datei; die Umgebung wird
    ueber ``DIAKRONOS_DATABASE_URL`` gesetzt, nicht ueber die App-Einstellungen.

    Laufzeit: der Seed ist der volle Demo-Durchlauf (~1-2 min), der Timeout
    ist deshalb grosszuegig.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    from sqlalchemy import create_engine, text

    repo = Path(__file__).resolve().parents[2]
    skript = repo / "tools" / "demo" / "musterhausen.py"
    db_datei = tmp_path / "demo2-cli.db"
    url = f"sqlite+pysqlite:///{db_datei}"
    # Schema wie in den uebrigen Tests (`conftest.engine`): `create_all`.
    # `alembic upgrade` scheitert auf SQLite an `ALTER … CONSTRAINT` (kein
    # Batch-Modus in den Migrationen) — fuer diesen Test zaehlt die App-Logik,
    # nicht das Migrationswerkzeug.
    import diakronos_app.models  # noqa: F401 — Modelle registrieren
    from diakronos_app.models.base import Base

    eng = create_engine(url, future=True)
    Base.metadata.create_all(eng)
    eng.dispose()

    umgebung = {
        **os.environ,
        "database_url": url,
        "redis_url": "redis://127.0.0.1:1/0",
        "DIAKRONOS_DEMO_STICHTAG": STICHTAG.isoformat(),
        "PYTHONPATH": os.pathsep.join(
            [str(repo / "backend" / "src"), str(repo / "tools"), str(repo / "tools" / "demo")]),
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    def lauf(*argumente: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(skript), *argumente],
            cwd=str(repo), env=umgebung, capture_output=True, text=True, timeout=900,
        )

    anlegen = lauf("--stichtag", STICHTAG.isoformat())
    assert anlegen.returncode == 0, f"anlegen scheiterte: {anlegen.stdout}\n{anlegen.stderr}"

    eng = create_engine(url, future=True)
    try:
        with eng.connect() as c:
            vorher = c.execute(text("SELECT count(*) FROM mitglied")).scalar_one()
    finally:
        eng.dispose()
    assert vorher >= 40, f"anlegen hat nur {vorher} Mitglieder geschrieben"

    entfernen = lauf("--entfernen")
    # Genau hier brach es ab: „Zu 'Anna Beispiel' ist keine Mitglied-Kennung
    # bekannt“ / Rueckgabewert 2.
    assert entfernen.returncode == 0, (
        "entfernen scheiterte im eigenen Prozess: "
        f"{entfernen.stdout}\n{entfernen.stderr}")
    assert "nichts gefunden" not in entfernen.stdout

    eng = create_engine(url, future=True)
    try:
        with eng.connect() as c:
            for tabelle in ("mitglied", "gruppe", "user", "pr_abwesenheit"):
                anzahl = c.execute(text(f'SELECT count(*) FROM "{tabelle}"')).scalar_one()
                assert anzahl == 0, f"{tabelle} ist nach --entfernen nicht leer ({anzahl})"
    finally:
        eng.dispose()
