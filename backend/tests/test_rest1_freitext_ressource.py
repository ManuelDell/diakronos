"""REST-1 (1) — Termin mit NUR Freitext-Ressource muss auf PostgreSQL halten.

Befund der Nachtpruefung: `api/kronos/event_crud.py::_normalize_ressourcen`
liefert fuer eine Zeile ohne Katalogbezug `ressource: ""`. SQLite merkt davon
nichts (Fremdschluessel sind dort standardmaessig aus), PostgreSQL bricht beim
Schreiben der Kind-Zeile mit einer FK-Verletzung ab
(`element_ressource.ressource -> ressource.name`). Ein Termin, an dem nur ein
Freitext-Ort haengt („Gemeindehaus“, „Proberaum“), war damit im Betrieb nicht
speicherbar.

Der Test laeuft deshalb GEGEN PostgreSQL — eine Wegwerf-Instanz mit eigenem
Schema je Test. Ohne `REST1_TEST_DATABASE_URL` wird er uebersprungen; die
SQLite-Suite kann diesen Fehler grundsaetzlich nicht zeigen.
"""

from __future__ import annotations

import os
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

EVENT_MODUL = "diakronos.kronos.api.event_crud"
KALENDER = "Gemeinde"


@pytest.fixture()
def engine():
    """Wegwerf-PostgreSQL (eigenes Schema) — sonst uebersprungen."""
    url = os.environ.get("REST1_TEST_DATABASE_URL") or ""
    if not url:
        pytest.skip("REST1_TEST_DATABASE_URL: eigener Wegwerf-PostgreSQL erforderlich")
    assert "wegwerf" in url.lower() or "test" in url.lower(), (
        f"REST1_TEST_DATABASE_URL zeigt auf {url!r} — kein erkennbarer "
        "Wegwerf-Marker. Der Test darf die Betriebs-DB nicht anfassen."
    )

    admin = create_engine(url)
    schema = "rest1_" + uuid.uuid4().hex
    with admin.begin() as c:
        c.execute(text(f'CREATE SCHEMA "{schema}"'))
    eng = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})

    import diakronos_app.models  # noqa: F401 — Modelle registrieren
    from diakronos_app.models.base import Base

    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()
    with admin.begin() as c:
        c.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    admin.dispose()


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture()
def welt(patched_db):
    """Ein Kalender mit Schreibrecht fuer alle Angemeldeten."""
    from diakronos_app.models.core import UserRole
    from diakronos_app.models.kronos import Kalender

    sess = patched_db()
    sess.add(Kalender(name=KALENDER, calendar_name=KALENDER,
                      selbstverwaltet=0, docstatus=0, idx=0))
    sess.add(UserRole(name="UR-GEM-SCHREIB", parent=KALENDER, parenttype="Kalender",
                      parentfield="schreibrechte", role="All", docstatus=0, idx=1))
    sess.commit()
    yield sess
    sess.close()


def _ressourcen_zeilen(sess, termin_name):
    """Kind-Zeilen direkt aus der DB lesen (derselbe Weg wie der Betrieb)."""
    from diakronos_app.models.kronos import ElementRessource

    sess.expire_all()
    return [
        {"ressource": z.ressource, "freitext_ressource": z.freitext_ressource,
         "status": z.status}
        for z in sess.query(ElementRessource)
        .filter(ElementRessource.parent == termin_name)
        .order_by(ElementRessource.idx)
        .all()
    ]


def test_termin_mit_nur_freitext_ressource_speichert(client, welt):
    """Nur-Freitext-Zeile: kein Katalogverweis (NULL), aber Text erhalten."""
    r = client.post(f"/api/method/{EVENT_MODUL}.create_event", json={
        "element_name": "Probe Freitext",
        "element_start": "2026-11-20 18:00:00",
        "element_end": "2026-11-20 20:00:00",
        "element_calendar": KALENDER,
        "status": "Festgelegt",
        "zusaetzliche_ressourcen": [
            {"freitext_ressource": "Gemeindehaus", "status": "Angefragt"},
        ],
    })
    assert r.status_code == 200, r.text
    termin = r.json()["message"]["id"]

    zeilen = _ressourcen_zeilen(welt, termin)
    assert len(zeilen) == 1, zeilen
    assert zeilen[0]["freitext_ressource"] == "Gemeindehaus"
    # Kern des Befunds: die Spalte zeigt auf `ressource.name` — leer heisst NULL.
    assert zeilen[0]["ressource"] in (None, ""), zeilen[0]
    assert not zeilen[0]["ressource"], zeilen[0]


def test_update_haelt_freitext_ressource(client, welt):
    """Derselbe Weg beim Aendern (update_event ersetzt die Kind-Tabelle)."""
    r = client.post(f"/api/method/{EVENT_MODUL}.create_event", json={
        "element_name": "Probe Freitext 2",
        "element_start": "2026-11-21 18:00:00",
        "element_end": "2026-11-21 20:00:00",
        "element_calendar": KALENDER,
        "status": "Festgelegt",
    })
    assert r.status_code == 200, r.text
    termin = r.json()["message"]["id"]

    r = client.post(f"/api/method/{EVENT_MODUL}.update_event", json={
        "name": termin,
        "zusaetzliche_ressourcen": [
            {"freitext_ressource": "Proberaum", "status": "Angefragt"},
            {"ressource": "", "freitext_ressource": "Foyer", "status": "Angefragt"},
        ],
    })
    assert r.status_code == 200, r.text

    zeilen = _ressourcen_zeilen(welt, termin)
    texte = sorted(z["freitext_ressource"] for z in zeilen)
    assert texte == ["Foyer", "Proberaum"], zeilen
    assert all(not z["ressource"] for z in zeilen), zeilen


def test_schema_erzwingt_den_fehler_wirklich(engine):
    """Gegenprobe: ohne Normalisierung bricht PostgreSQL hier ab.

    Ohne diese Probe waere nicht belegt, dass der Test oben ueberhaupt etwas
    pruefen kann (SQLite wuerde denselben Schreibvorgang annehmen).
    """
    with engine.begin() as c:
        with pytest.raises(sa.exc.IntegrityError):
            c.execute(text(
                'INSERT INTO "element_ressource" '
                '(name, parent, parentfield, docstatus, idx, ressource) '
                "VALUES ('ER-PROBE', 'EL-X', 'zusaetzliche_ressourcen', 0, 1, '')"
            ))
