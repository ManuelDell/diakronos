"""TERMIN-GRUPPE — `Element.gruppe` folgt dem Kalender (BUG-T1, Manuel 17.11.).

Die Karte: `Element.gruppe` (FK -> `gruppe.name`, nur Hauptgruppen) wurde von
KEINEM Schreibweg gesetzt; `planrahmen` und die Gruppenseite lesen es aber.
Diakronos setzt es jetzt automatisch aus dem Kalender
(`diakronos_app.termin_gruppe`). Geprüft wird hier:

  A. Anlegen über den ECHTEN Endpunkt (`create_event`) in einem
     Gruppenkalender, einem Untergruppenkalender und einem Gemeinde-Kalender.
  B. Kalenderwechsel über den echten Endpunkt (`save_event`) — das Feld folgt.
  C. Serie (`create_series`): JEDES Vorkommen trägt die Gruppe.
  D. Google-/iCal-Import (`_create_element_from_dict`, legt per ORM an, NICHT
     über `_create`) — importierte Kalender sind Gemeinde-Kalender -> NULL.
  E. Kanban-Freigabe (`_update_doc` mit Status) rechnet die Gruppe NICHT neu —
     kein Kalenderwechsel, keine Abfrage, kein Gruppenwechsel.
  F. Migration `tg1_element_gruppe_kalender`: Bestand wird nachgetragen,
     idempotent, Gemeinde-Kalender werden auf NULL gezogen.

Die Welt wird wie in `test_bugt1_gruppe_termine` direkt angelegt (die Termine
selbst immer über den getesteten Weg — sonst prüfte der Test den Fehler nicht).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from diakronos_app.frappe_compat.session import set_user

EVENT_CRUD = "diakronos.kronos.api.event_crud"
GRUPPEN = "diakronos.diakonos.api.gruppen"

ANGEMELDET = "tg-verwaltung@example.org"

GRUPPE_JK = "GRU-JK"
UNTERGRUPPE_GT = "UG-GT"
KALENDER_JK = "KAL-JK"
KALENDER_GT = "KAL-GT"
KALENDER_GEMEINDE = "KAL-GEM"


def _in_tagen(tage: int, stunde: int = 18) -> datetime:
    from diakronos_app.zeit import heute_gemeinde

    return datetime.combine(
        heute_gemeinde() + timedelta(days=tage), datetime.min.time()
    ).replace(hour=stunde)


@pytest.fixture()
def welt(patched_db, fake_redis):
    """Hauptgruppe mit Kalender, Untergruppe mit Kalender, Gemeinde-Kalender."""
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import (
        Gruppe,
        Gruppenmitgliedschaft,
        Mitglied,
        Untergruppe,
    )
    from diakronos_app.models.kronos import Kalender
    from diakronos_app.models.rechte import (
        RechteFreigabe,
        RechteGruppenrolle,
        RechteModul,
        RechteObjekt,
    )

    sess = patched_db()
    sess.add_all([
        User(name=ANGEMELDET, email=ANGEMELDET, full_name="Tina Verwaltung", enabled=1),
        Mitglied(name="MIT-TG", vorname="Tina", nachname="Verwaltung", email=ANGEMELDET,
                 user=ANGEMELDET, status="Mitglied"),
    ])
    sess.add_all([
        Gruppe(name=GRUPPE_JK, gruppenname="Jugendkreis", status="Aktiv", docstatus=0, idx=0),
        Untergruppe(name=UNTERGRUPPE_GT, untergruppenname="Gemeinschaftsteam",
                    gruppe=GRUPPE_JK, status="Aktiv", docstatus=0, idx=0),
    ])
    sess.add_all([
        Gruppenmitgliedschaft(name="GM-TG", parent=GRUPPE_JK, parenttype="Gruppe",
                              parentfield="mitglieder", mitglied="MIT-TG", rolle="Mitglied",
                              status="Aktiv", docstatus=0, idx=0),
        # HV der Hauptgruppe: darf in allen drei Kalendern schreiben.
        RechteGruppenrolle(gruppe=GRUPPE_JK, benutzer=ANGEMELDET, rolle="HV"),
        RechteModul(gruppe=GRUPPE_JK, modul="kalender"),
        # Der Gemeinde-Kalender gehoert keiner Gruppe — Schreibrecht als
        # Einzelfreigabe (wie ein Kalender-Admin sie hat).
        RechteFreigabe(typ="kalender", objekt=KALENDER_GEMEINDE, benutzer=ANGEMELDET,
                       lesen=True, schreiben=True),
    ])
    sess.add_all([
        Kalender(name=KALENDER_JK, calendar_name="Jugendkreis", selbstverwaltet=0,
                 docstatus=0, idx=0),
        Kalender(name=KALENDER_GT, calendar_name="Gemeinschaftsteam", selbstverwaltet=0,
                 docstatus=0, idx=0),
        Kalender(name=KALENDER_GEMEINDE, calendar_name="Gemeinde", selbstverwaltet=0,
                 docstatus=0, idx=0),
        # Zuordnung aus dem Rechtesystem: Untergruppen-Kalender traegt die
        # HAUPTgruppe (der FK laesst nur Hauptgruppen zu).
        RechteObjekt(typ="kalender", objekt=KALENDER_JK, gruppe=GRUPPE_JK),
        RechteObjekt(typ="kalender", objekt=KALENDER_GT, gruppe=GRUPPE_JK,
                     untergruppe=UNTERGRUPPE_GT),
        RechteObjekt(typ="kalender", objekt=KALENDER_GEMEINDE),
    ])
    sess.commit()
    set_user(ANGEMELDET)
    yield sess
    set_user("Administrator")
    sess.close()


def _gruppe_von(welt, name: str) -> str | None:
    from diakronos_app.models.kronos import Element

    welt.expire_all()
    zeile = welt.get(Element, name)
    assert zeile is not None, name
    return zeile.gruppe


def _termin(client, kalender: str, titel: str, tage: int = 3) -> str:
    start = _in_tagen(tage)
    antwort = client.post(
        f"/api/method/{EVENT_CRUD}.create_event",
        json={
            "element_name": titel,
            "element_start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "element_end": (start + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "all_day": 0,
            "element_calendar": kalender,
            "ressource": None,
            "description": None,
            "element_category": None,
            "ignore_conflict": 0,
            "zusaetzliche_ressourcen": "[]",
        },
    )
    assert antwort.status_code == 200, antwort.text
    kennung = antwort.json()["message"]["id"]
    assert kennung
    return kennung


# ── A · Anlegen: drei Kalenderarten ─────────────────────────────────────────


def test_neuer_termin_im_gruppenkalender_traegt_die_gruppe(client, welt):
    kennung = _termin(client, KALENDER_JK, "Jugendtreff")
    assert _gruppe_von(welt, kennung) == GRUPPE_JK


def test_neuer_termin_im_untergruppenkalender_traegt_die_hauptgruppe(client, welt):
    """FK ist `gruppe.name` — der Untergruppen-Kalender liefert die HAUPTgruppe."""
    kennung = _termin(client, KALENDER_GT, "Teamabend")
    assert _gruppe_von(welt, kennung) == GRUPPE_JK


def test_neuer_termin_im_gemeindekalender_bleibt_ohne_gruppe(client, welt):
    kennung = _termin(client, KALENDER_GEMEINDE, "Gottesdienst")
    assert _gruppe_von(welt, kennung) is None


def test_ausdrueckliche_abweichende_gruppe_verliert_gegen_den_kalender(client, welt):
    """Der Kalender ist die Wahrheit — auch gegen ein mitgegebenes `gruppe`."""
    from diakronos_app.frappe_compat.api_helpers import _create
    from diakronos_app.models.kronos import Element

    name = _create("Element", {
        "element_name": "Termin mit falscher Gruppe",
        "element_calendar": KALENDER_JK,
        "gruppe": UNTERGRUPPE_GT,
        "element_start": _in_tagen(5).strftime("%Y-%m-%d %H:%M:%S"),
        "element_end": _in_tagen(5).strftime("%Y-%m-%d %H:%M:%S"),
        "status": "Festgelegt",
    })
    welt.expire_all()
    assert welt.get(Element, name).gruppe == GRUPPE_JK


def test_gemeindekalender_laesst_mitgegebene_gruppe_stehen(client, welt):
    """Kalender OHNE Zuordnung ist keine Aussage: nichts wird gesetzt/geloescht."""
    from diakronos_app.frappe_compat.api_helpers import _create
    from diakronos_app.models.kronos import Element

    name = _create("Element", {
        "element_name": "Vertretung im Gemeindekalender",
        "element_calendar": KALENDER_GEMEINDE,
        "gruppe": GRUPPE_JK,
        "element_start": _in_tagen(5).strftime("%Y-%m-%d %H:%M:%S"),
        "element_end": _in_tagen(5).strftime("%Y-%m-%d %H:%M:%S"),
        "status": "Festgelegt",
    })
    welt.expire_all()
    assert welt.get(Element, name).gruppe == GRUPPE_JK


# ── B · Kalenderwechsel ─────────────────────────────────────────────────────


def test_kalenderwechsel_zieht_die_gruppe_nach(client, welt):
    from diakronos_app.frappe_compat.api_helpers import _update_doc
    from diakronos_app.frappe_compat.query import get_value

    kennung = _termin(client, KALENDER_GT, "Wanderung")
    assert _gruppe_von(welt, kennung) == GRUPPE_JK

    # Verschieben aus einem Gruppenkalender in einen Gemeinde-Kalender: die
    # Gruppe war abgeleitet und folgt dem Kalender — der Termin verlaesst die
    # alte Gruppenseite (Review 18.11.).
    _update_doc("Element", kennung, {"element_calendar": KALENDER_GEMEINDE})
    assert _gruppe_von(welt, kennung) is None, (
        "abgeleitete Gruppe blieb nach dem Verschieben stehen"
    )

    # Wechsel auf einen Gruppenkalender setzt die (gleiche) Hauptgruppe.
    _update_doc("Element", kennung, {"element_calendar": KALENDER_JK})
    assert _gruppe_von(welt, kennung) == GRUPPE_JK
    assert get_value("Element", kennung, "element_calendar") == KALENDER_JK


def test_kalenderwechsel_auf_fremden_gruppenkalender_setzt_dessen_gruppe(client, welt):
    """Kalender MIT Gruppe -> neue Gruppe (Kalender ist die Wahrheit)."""
    from diakronos_app.frappe_compat.api_helpers import _update_doc
    from diakronos_app.models.diakonos import Gruppe
    from diakronos_app.models.kronos import Kalender
    from diakronos_app.models.rechte import RechteFreigabe, RechteObjekt

    # Zweite Gruppe mit eigenem Kalender, auf den der Aufrufer schreiben darf.
    welt.add_all([
        Gruppe(name="GRU-CHOR", gruppenname="Chor", status="Aktiv", docstatus=0, idx=0),
        Kalender(name="KAL-CHOR", calendar_name="Chor", selbstverwaltet=0, docstatus=0, idx=0),
        RechteObjekt(typ="kalender", objekt="KAL-CHOR", gruppe="GRU-CHOR"),
        RechteFreigabe(typ="kalender", objekt="KAL-CHOR", benutzer=ANGEMELDET,
                       lesen=True, schreiben=True),
    ])
    welt.commit()

    kennung = _termin(client, KALENDER_JK, "Chorprobe")
    assert _gruppe_von(welt, kennung) == GRUPPE_JK

    _update_doc("Element", kennung, {"element_calendar": "KAL-CHOR"})
    assert _gruppe_von(welt, kennung) == "GRU-CHOR", (
        "Kalenderwechsel auf einen anderen Gruppenkalender liess die alte Gruppe stehen"
    )


def test_save_event_zieht_die_gruppe_mit(client, welt):
    """Der echte Endpunkt: derselbe Weg, den die Oberflaeche nimmt."""
    from diakronos_app.models.diakonos import Gruppe
    from diakronos_app.models.kronos import Kalender
    from diakronos_app.models.rechte import (
        RechteFreigabe,
        RechteGruppenrolle,
        RechteModul,
        RechteObjekt,
    )

    welt.add_all([
        Gruppe(name="GRU-CHOR", gruppenname="Chor", status="Aktiv", docstatus=0, idx=0),
        Kalender(name="KAL-CHOR", calendar_name="Chor", selbstverwaltet=0, docstatus=0, idx=0),
        RechteObjekt(typ="kalender", objekt="KAL-CHOR", gruppe="GRU-CHOR"),
        # Schreibrecht auf den Zielkalender (sonst 403 im Endpunkt).
        RechteGruppenrolle(gruppe="GRU-CHOR", benutzer=ANGEMELDET, rolle="HV"),
        RechteModul(gruppe="GRU-CHOR", modul="kalender"),
        RechteFreigabe(typ="kalender", objekt="KAL-CHOR", benutzer=ANGEMELDET,
                       lesen=True, schreiben=True),
    ])
    welt.commit()

    kennung = _termin(client, KALENDER_JK, "Kreismitternacht")
    assert _gruppe_von(welt, kennung) == GRUPPE_JK
    start = _in_tagen(6)
    antwort = client.post(
        f"/api/method/{EVENT_CRUD}.save_event",
        json={
            "name": kennung,
            "element_name": "Kreismitternacht",
            "element_start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "element_end": (start + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "element_calendar": "KAL-CHOR",
        },
    )
    assert antwort.status_code == 200, antwort.text
    assert _gruppe_von(welt, kennung) == "GRU-CHOR"


# ── C · Serie ───────────────────────────────────────────────────────────────


def test_serie_traegt_die_gruppe_an_jedem_vorkommen(client, welt):
    start = _in_tagen(2)
    antwort = client.post(
        f"/api/method/{EVENT_CRUD}.create_series",
        json={
            "element_name": "Wöchentlicher Treff",
            "element_start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "element_end": (start + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "element_calendar": KALENDER_GT,
            "repeat_type": "weekly",
            "series_end": (start + timedelta(days=20)).strftime("%Y-%m-%d"),
            "all_day": 0,
            "zusaetzliche_ressourcen": "[]",
        },
    )
    assert antwort.status_code == 200, antwort.text
    angelegt = antwort.json()["message"]["created_ids"]
    assert len(angelegt) >= 3, angelegt
    for kennung in angelegt:
        assert _gruppe_von(welt, kennung) == GRUPPE_JK, kennung


# ── D · Google-/iCal-Import (eigener ORM-Weg) ───────────────────────────────


def test_google_import_setzt_die_kalendergruppe(welt):
    """`_create_element_from_dict` laeuft NICHT durch `_create`."""
    from diakronos_app.api.kronos.google_import import _create_element_from_dict, _ensure_kalender
    from diakronos_app.models.kronos import Element

    sess = welt

    def _nach_kennung(kennung: str) -> str:
        """Kennung (`name`) der gerade importierten Zeile — die Query gibt sie
        als String der Ergebnismenge zurueck (kein ORM-Objekt)."""
        return str(sess.execute(
            Element.__table__.select().where(Element.google_event_id == kennung)
        ).first()[0])

    _create_element_from_dict({
        "element_name": "Importierter Gemeindetermin",
        "element_calendar": KALENDER_GEMEINDE,
        "element_start": _in_tagen(7).strftime("%Y-%m-%d %H:%M:%S"),
        "element_end": _in_tagen(7).strftime("%Y-%m-%d %H:%M:%S"),
        "status": "Festgelegt",
        "google_event_id": "gcal:import-1",
    }, sess)
    sess.commit()
    zeile = _nach_kennung("gcal:import-1")
    sess.expire_all()
    assert sess.get(Element, zeile).gruppe is None, "Gemeinde-Kalender -> keine Gruppe"

    # Ein importierter Kalender ist ein Gemeinde-Kalender (`RechteObjekt` ohne
    # Gruppe) — auch hier keine geratene Gruppe.
    import_name = _ensure_kalender("Importiert", "#123456", sess)
    _create_element_from_dict({
        "element_name": "Importierter Termin",
        "element_calendar": import_name,
        "element_start": _in_tagen(8).strftime("%Y-%m-%d %H:%M:%S"),
        "element_end": _in_tagen(8).strftime("%Y-%m-%d %H:%M:%S"),
        "status": "Festgelegt",
        "google_event_id": "ical:import-2",
    }, sess)
    sess.commit()
    treffer = _nach_kennung("ical:import-2")
    sess.expire_all()
    assert sess.get(Element, treffer).gruppe is None, "importierter Kalender -> keine Gruppe"

    # Gegenprobe: derselbe Weg in einem KALENDER MIT Gruppe setzt sie.
    _create_element_from_dict({
        "element_name": "Importierter Gruppentermin",
        "element_calendar": KALENDER_GT,
        "element_start": _in_tagen(9).strftime("%Y-%m-%d %H:%M:%S"),
        "element_end": _in_tagen(9).strftime("%Y-%m-%d %H:%M:%S"),
        "status": "Festgelegt",
        "google_event_id": "gcal:import-3",
    }, sess)
    sess.commit()
    gruppe = _nach_kennung("gcal:import-3")
    sess.expire_all()
    assert sess.get(Element, gruppe).gruppe == GRUPPE_JK


# ── E · Kanban: kein Kalenderwechsel, keine Neuberechnung ──────────────────

def test_resource_weg_setzt_die_gruppe(client, welt):
    """`/api/resource/{Element}` schreibt mit eigener Sitzung, nicht ueber `_create`."""
    from diakronos_app.frappe_compat.session import set_user
    from diakronos_app.models.kronos import Element

    # Der generische REST-Weg prueft die Kalender-Rechte NICHT (eigene Schranke
    # in `_resource_denied`) — als Administrator ist die Anlage unstrittig; hier
    # geht es allein um die abgeleitete Gruppe.
    set_user("Administrator")
    start = _in_tagen(4)
    antwort = client.post(
        "/api/resource/Element",
        json={
            "element_name": "Termin ueber /api/resource",
            "element_calendar": KALENDER_GT,
            "element_start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "element_end": (start + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "status": "Festgelegt",
        },
    )
    assert antwort.status_code == 200, antwort.text
    kennung = antwort.json()["data"]["name"]
    welt.expire_all()
    assert welt.get(Element, kennung).gruppe == GRUPPE_JK, (
        "Untergruppen-Kalender -> HAUPTgruppe (FK laesst nur Hauptgruppen zu)"
    )

    # Kalenderwechsel ueber denselben Weg.
    antwort = client.put(
        f"/api/resource/Element/{kennung}",
        json={"element_calendar": KALENDER_JK},
    )
    assert antwort.status_code == 200, antwort.text
    welt.expire_all()
    assert welt.get(Element, kennung).gruppe == GRUPPE_JK

    # Verschieben in den Gemeinde-Kalender: abgeleitete Gruppe folgt -> leer.
    antwort = client.put(
        f"/api/resource/Element/{kennung}",
        json={"element_calendar": KALENDER_GEMEINDE},
    )
    assert antwort.status_code == 200, antwort.text
    welt.expire_all()
    assert welt.get(Element, kennung).gruppe is None
    set_user(ANGEMELDET)


def test_statuswechsel_rechnet_die_gruppe_nicht_neu(client, welt):
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    kennung = _termin(client, KALENDER_JK, "Freigabe pruefen")
    _update_doc("Element", kennung, {"status": "Festgelegt"})
    assert _gruppe_von(welt, kennung) == GRUPPE_JK


# ── F · Migration ──────────────────────────────────────────────────────────


def _migration():
    """Die Revision als Modul (Aufruf ohne Ketten-Rahmen, wie in BS-1a-2)."""
    import importlib.util

    from pathlib import Path

    pfad = Path(__file__).resolve().parents[1] / "alembic" / "versions" / \
        "tg1_element_gruppe_kalender.py"
    spec = importlib.util.spec_from_file_location("tg1_revision", pfad)
    assert spec is not None and spec.loader is not None
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_migration_traegt_den_bestand_nach(patched_db):
    """Bestand: leer, falsch, passend, Gemeinde-Kalender -> Zielzustand."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import text

    from diakronos_app.models.diakonos import Gruppe
    from diakronos_app.models.kronos import Element, Kalender
    from diakronos_app.models.rechte import RechteObjekt

    sess = patched_db()
    sess.add_all([
        Gruppe(name="GRU-A", gruppenname="Gruppe A", status="Aktiv", docstatus=0, idx=0),
        Gruppe(name="GRU-B", gruppenname="Gruppe B", status="Aktiv", docstatus=0, idx=0),
        Kalender(name="KAL-A", calendar_name="A", selbstverwaltet=0, docstatus=0, idx=0),
        Kalender(name="KAL-B", calendar_name="B", selbstverwaltet=0, docstatus=0, idx=0),
        Kalender(name="KAL-GEM", calendar_name="Gemeinde", selbstverwaltet=0, docstatus=0, idx=0),
        RechteObjekt(typ="kalender", objekt="KAL-A", gruppe="GRU-A"),
        RechteObjekt(typ="kalender", objekt="KAL-B", gruppe="GRU-B", untergruppe="UG-B"),
        RechteObjekt(typ="kalender", objekt="KAL-GEM"),
    ])
    _element = dict(element_start=datetime(2026, 11, 20, 18, 0),
                    element_end=datetime(2026, 11, 20, 20, 0),
                    status="Festgelegt", docstatus=0, idx=0)
    sess.add_all([
        Element(name="E-LEER", element_calendar="KAL-A", **(_element)),
        Element(name="E-FALSCH", element_calendar="KAL-B", gruppe="GRU-A", **(_element)),
        Element(name="E-PASST", element_calendar="KAL-A", gruppe="GRU-A", **(_element)),
        Element(name="E-GEMEINDE", element_calendar="KAL-GEM", gruppe="GRU-A", **(_element)),
        Element(name="E-OHNE-KALENDER", gruppe="GRU-A", **(_element)),
    ])
    sess.commit()

    modul = _migration()

    def _lauf(schritt) -> None:
        """Migration ohne Ketten-Rahmen ausfuehren (eigene Verbindung).

        `MigrationContext.configure` liefert beim Session-Bind eine Verbindung
        aus der laufenden Transaktion — `with sess.begin()` kollidiert damit
        („A transaction is already begun“). Gebraucht wird nur das Operations-
        Objekt; committet wird davor mit `sess.commit()`.
        """
        ctx = MigrationContext.configure(sess.connection())
        with Operations.context(ctx):
            schritt()

    sess.commit()
    _lauf(modul.upgrade)
    sess.commit()

    sess.expire_all()
    schluessel = ("E-LEER", "E-FALSCH", "E-PASST", "E-GEMEINDE", "E-OHNE-KALENDER")
    stand = {k: sess.get(Element, k).gruppe for k in schluessel}
    assert stand == {
        "E-LEER": "GRU-A",         # leer + Kalender mit Gruppe -> nachgetragen
        "E-FALSCH": "GRU-A",       # vorhandener Wert bleibt (nie ueberschreiben)
        "E-PASST": "GRU-A",        # unveraendert
        "E-GEMEINDE": "GRU-A",     # Kalender ohne Zuordnung -> nie NULL schreiben
        "E-OHNE-KALENDER": "GRU-A",  # ohne Kalender keine Ableitung -> bleibt
    }, stand

    # idempotent: zweiter Lauf aendert nichts
    _lauf(modul.upgrade)
    sess.commit()
    sess.expire_all()
    assert {k: sess.get(Element, k).gruppe for k in schluessel} == stand

    # downgrade ist ein bewusstes No-op: der abgeleitete Stand bleibt stehen
    _lauf(modul.downgrade)
    sess.commit()
    sess.expire_all()
    assert {k: sess.get(Element, k).gruppe for k in schluessel} == stand
    assert sess.execute(text("SELECT 1")).first() is not None
    sess.close()


# ── G · Folge in der Gruppenseite (BUG-T1 bleibt ganz) ─────────────────────


def test_untergruppen_termin_steht_nicht_auf_der_hauptgruppenseite(client, welt):
    """Seit `gruppe` = Hauptgruppe ist, muss die Kalenderzuordnung gewinnen.

    `get_gruppe_termine` siebte die Termine einer Seite früher ZUSÄTZLICH über
    `Element.gruppe == <seite>`. Mit der abgeleiteten Gruppe zog das jeden
    Termin des Untergruppen-Kalenders auf die Seite der Hauptgruppe. Die
    Ersatzregel gilt deshalb nur für Termine in Kalendern OHNE
    Gruppenzuordnung.
    """
    from diakronos_app.api.gruppen import get_gruppe_termine  # noqa: F401 (Importpfad)

    untergruppe = _termin(client, KALENDER_GT, "Teamabend", 3)
    hauptgruppe = _termin(client, KALENDER_JK, "Jugendtreff", 4)
    assert _gruppe_von(welt, untergruppe) == GRUPPE_JK  # abgeleitet = Hauptgruppe

    liste_haupt = client.get(f"/api/method/{GRUPPEN}.get_gruppe_termine",
                             params={"gruppe_id": GRUPPE_JK})
    assert liste_haupt.status_code == 200, liste_haupt.text
    kennungen = [t["name"] for t in liste_haupt.json()["message"]["termine"]]
    assert hauptgruppe in kennungen, kennungen
    assert untergruppe not in kennungen, (
        "Termin des Untergruppen-Kalenders steht auf der Hauptgruppen-Seite — "
        "die abgeleitete `gruppe` darf die Kalenderzuordnung nicht ersetzen"
    )

    liste_unter = client.get(f"/api/method/{GRUPPEN}.get_gruppe_termine",
                             params={"gruppe_id": UNTERGRUPPE_GT})
    assert liste_unter.status_code == 200, liste_unter.text
    kennungen_unter = [t["name"] for t in liste_unter.json()["message"]["termine"]]
    assert untergruppe in kennungen_unter, kennungen_unter
    assert hauptgruppe in kennungen_unter, kennungen_unter


def test_altbestand_ohne_kalender_bleibt_ueber_das_feld_sichtbar(client, welt):
    """Ersatzregel: Termine OHNE Kalendergruppe (hier: ohne Kalender)."""
    from diakronos_app.frappe_compat.session import set_user
    from diakronos_app.models.kronos import Element

    sess = welt
    set_user("Administrator")  # Altbestand wird ausserhalb der Oberflaeche gesetzt
    sess.add(Element(
        name="E-ALT-OHNE-KALENDER", element_name="Alter Gruppenabend",
        element_calendar=None, gruppe=GRUPPE_JK, status="Festgelegt",
        element_start=_in_tagen(2), element_end=_in_tagen(2), docstatus=0, idx=0,
    ))
    sess.commit()
    set_user(ANGEMELDET)

    liste = client.get(f"/api/method/{GRUPPEN}.get_gruppe_termine",
                       params={"gruppe_id": GRUPPE_JK})
    assert liste.status_code == 200, liste.text
    kennungen = [t["name"] for t in liste.json()["message"]["termine"]]
    assert "E-ALT-OHNE-KALENDER" in kennungen, (
        f"Altbestand ohne Kalender muss über `Element.gruppe` sichtbar bleiben ({kennungen})"
    )


# ── H · Kein Leck über das abgeleitete Feld (Review 17.11., Fälle A und B) ──


def _zweitwelt(patched_db):
    """Hauptgruppe G OHNE Kalender, Untergruppe U MIT Kalender (Fall A)."""
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import (
        Gruppe,
        Gruppenmitgliedschaft,
        Mitglied,
        Untergruppe,
    )
    from diakronos_app.models.kronos import Kalender
    from diakronos_app.models.rechte import (
        RechteGruppenrolle,
        RechteModul,
        RechteObjekt,
    )

    sess = patched_db()
    sess.add_all([
        User(name=ANGEMELDET, email=ANGEMELDET, full_name="Tina Verwaltung", enabled=1),
        Mitglied(name="MIT-TG", vorname="Tina", nachname="Verwaltung", email=ANGEMELDET,
                 user=ANGEMELDET, status="Mitglied"),
        Gruppe(name="GRU-O", gruppenname="Offene Gruppe", status="Aktiv", docstatus=0, idx=0),
        Untergruppe(name="UG-O", untergruppenname="Offene Untergruppe",
                    gruppe="GRU-O", status="Aktiv", docstatus=0, idx=0),
        Gruppenmitgliedschaft(name="GM-O", parent="GRU-O", parenttype="Gruppe",
                              parentfield="mitglieder", mitglied="MIT-TG", rolle="HV",
                              status="Aktiv", docstatus=0, idx=0),
        RechteGruppenrolle(gruppe="GRU-O", benutzer=ANGEMELDET, rolle="HV"),
        RechteModul(gruppe="GRU-O", modul="kalender"),
        # NUR die Untergruppe hat einen Kalender; die Hauptgruppe keinen.
        Kalender(name="KAL-O-UG", calendar_name="Offene Untergruppe",
                 selbstverwaltet=0, docstatus=0, idx=0),
        RechteObjekt(typ="kalender", objekt="KAL-O-UG", gruppe="GRU-O",
                     untergruppe="UG-O"),
    ])
    sess.commit()
    set_user(ANGEMELDET)
    return sess


def test_fall_a_termin_der_untergruppe_ohne_hauptgruppenkalender(client, patched_db, fake_redis):
    """Hauptgruppe OHNE Kalender darf keine Termine der Untergruppe zeigen."""
    from diakronos_app.models.rechte import RechteObjekt

    sess = _zweitwelt(patched_db)
    try:
        assert not sess.query(RechteObjekt).filter(
            RechteObjekt.typ == "kalender", RechteObjekt.gruppe == "GRU-O",
            RechteObjekt.untergruppe.is_(None),
        ).all(), "Voraussetzung: die Hauptgruppe hat KEINEN eigenen Kalender"

        kennung = _termin(client, "KAL-O-UG", "Abend der Untergruppe", 3)
        assert _gruppe_von(sess, kennung) == "GRU-O"  # FK kennt nur Hauptgruppen
        liste = client.get(f"/api/method/{GRUPPEN}.get_gruppe_termine",
                           params={"gruppe_id": "GRU-O"})
        assert liste.status_code == 200, liste.text
        kennungen = [t["name"] for t in liste.json()["message"]["termine"]]
        assert kennung not in kennungen, (
            "Leck: Termin des Untergruppen-Kalenders steht auf der Seite der "
            "Hauptgruppe, obwohl die Hauptgruppe keinen Kalender hat"
        )
    finally:
        set_user("Administrator")
        sess.close()


def test_fall_b_unsichtbarer_hauptgruppenkalender_kein_leck(client, patched_db, fake_redis):
    """Hauptgruppe G hat Kalender (unfreigegeben), Nutzer sieht nur U's Kalender.

    Aufbau: der Aufrufer ist einfaches Mitglied der Hauptgruppe G. Der Kalender
    der Hauptgruppe ist NICHT freigegeben (`standard_gruppe_lesen=False`), der
    Kalender der Untergruppe U dagegen schon (Gruppen-Freigabe lesen). Der
    Termin liegt im SICHTBAREN U-Kalender und traegt die Hauptgruppe — er darf
    trotzdem nicht auf der Grundseite G stehen, weil der Aufrufer G's Kalender
    nicht sieht.
    """
    from diakronos_app.models.diakonos import Gruppe, Untergruppe, Untergruppenmitgliedschaft
    from diakronos_app.models.kronos import Kalender
    from diakronos_app.models.rechte import (
        RechteFreigabe,
        RechteGruppenrolle,
        RechteModul,
        RechteObjekt,
    )

    sess = _zweitwelt(patched_db)
    try:
        set_user("Administrator")
        sess.add_all([
            Gruppe(name="GRU-B", gruppenname="Sperrgruppe", status="Aktiv", docstatus=0, idx=0),
            Untergruppe(name="UG-B", untergruppenname="Sperr-Untergruppe",
                        gruppe="GRU-B", status="Aktiv", docstatus=0, idx=0),
            Kalender(name="KAL-B-HAUPT", calendar_name="Sperrgruppe",
                     selbstverwaltet=0, docstatus=0, idx=0),
            Kalender(name="KAL-B-UG", calendar_name="Sperr-Untergruppe",
                     selbstverwaltet=0, docstatus=0, idx=0),
            # G's Kalender: Gruppenmitglieder lesen NICHT (keine Freigabe).
            RechteObjekt(typ="kalender", objekt="KAL-B-HAUPT", gruppe="GRU-B",
                         standard_gruppe_lesen=False),
            # U's Kalender: für DIESE Person freigegeben (Einzelfreigabe mit
            # Schreibrecht) — die Gruppen-Freigabe allein gäbe einem einfachen
            # Mitglied kein Schreibrecht.
            RechteObjekt(typ="kalender", objekt="KAL-B-UG", gruppe="GRU-B",
                         untergruppe="UG-B"),
            RechteFreigabe(typ="kalender", objekt="KAL-B-UG", benutzer=ANGEMELDET,
                           lesen=True, schreiben=True),
            # Einfaches Mitglied der Hauptgruppe UND der Untergruppe (keine
            # Leitung) — nur so darf `get_gruppe_termine` die UG-Seite lesen.
            RechteGruppenrolle(gruppe="GRU-B", benutzer=ANGEMELDET, rolle="Mitglied"),
            Untergruppenmitgliedschaft(name="UM-B", parent="UG-B",
                                       parenttype="Untergruppe",
                                       parentfield="mitglieder", mitglied="MIT-TG",
                                       rolle="Mitglied", status="Aktiv",
                                       docstatus=0, idx=0),
            RechteModul(gruppe="GRU-B", modul="kalender"),
        ])
        sess.commit()
        set_user(ANGEMELDET)
        sichtbar = client.get(
            "/api/method/diakronos.kronos.api.permissions.get_accessible_calendars"
        )
        assert sichtbar.status_code == 200, sichtbar.text
        namen = [c["name"] for c in sichtbar.json()["message"]]
        assert "KAL-B-UG" in namen, namen
        assert "KAL-B-HAUPT" not in namen, (
            "Voraussetzung des Falls B: der Kalender der Hauptgruppe ist unsichtbar"
        )

        von_unter = client.post(
            f"/api/method/{EVENT_CRUD}.create_event",
            json={
                "element_name": "Abend der Sperr-Untergruppe",
                "element_start": _in_tagen(3).strftime("%Y-%m-%d %H:%M:%S"),
                "element_end": (_in_tagen(3) + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
                "all_day": 0,
                "element_calendar": "KAL-B-UG",
                "ressource": None,
                "description": None,
                "element_category": None,
                "ignore_conflict": 0,
                "zusaetzliche_ressourcen": "[]",
            },
        )
        assert von_unter.status_code == 200, von_unter.text
        kennung = von_unter.json()["message"]["id"]
        assert _gruppe_von(sess, kennung) == "GRU-B"

        liste_unter = client.get(f"/api/method/{GRUPPEN}.get_gruppe_termine",
                                 params={"gruppe_id": "UG-B"})
        assert liste_unter.status_code == 200, liste_unter.text
        assert kennung in [t["name"] for t in liste_unter.json()["message"]["termine"]]

        # Die HAUPTgruppen-Seite darf den Termin nicht fuehren, obwohl er die
        # Hauptgruppe traegt — ihr Kalender ist fuer den Aufrufer unsichtbar.
        liste_haupt = client.get(f"/api/method/{GRUPPEN}.get_gruppe_termine",
                                 params={"gruppe_id": "GRU-B"})
        assert liste_haupt.status_code == 200, liste_haupt.text
        assert kennung not in [t["name"] for t in liste_haupt.json()["message"]["termine"]], (
            "Leck: Termin eines sichtbaren Untergruppen-Kalenders steht auf der "
            "Seite der Hauptgruppe, deren Kalender der Aufrufer NICHT sieht"
        )
    finally:
        set_user("Administrator")
        sess.close()
