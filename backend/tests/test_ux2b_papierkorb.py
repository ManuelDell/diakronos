"""UX2b — Papierkorb im Server (hoechstens 7 Tage).

Zusagen der Karte und wo sie hier geprueft werden:

P1  Weiches Loeschen fuer Beitrag, Termin, Gruppe, Wiki-Seite und Lied
    (``geloescht_am`` + ``geloescht_von``, eine Migration, ein Head).
    Jede Lese-Ausgabe filtert geloeschte Zeilen aus — auch die oeffentliche
    Website, CalDAV, iCal und die Suche.
    -> ``test_*_loeschen_wirkt_wie_entfernt``, ``test_website_termine_...``,
       ``test_caldav_...``, ``test_suche_findet_geloeschtes_lied_nicht``,
       ``test_*_detail_verhaelt_sich_wie_nicht_vorhanden``
P2  Endpunkte ``<bereich>.wiederherstellen_*`` (POST, gleiche Rechte wie
    Loeschen) und ``papierkorb.liste`` (Admin).
    -> ``test_wiederherstellen_*``, ``test_wiederherstellen_ohne_recht_403``,
       ``test_papierkorb_liste_nur_admin``
P3  Endgueltiges Entfernen nach 7 Tagen ueber den vorhandenen Scheduler;
    danach ist die Zeile wirklich weg (inklusive Kind-Zeilen).
    -> ``test_aufraeumen_haelt_die_frist_ein``, ``test_aufraeumen_entfernt_...``,
       ``test_scheduler_job_ist_registriert``
P4  Das bisherige Loeschen bleibt API-kompatibel (``success: True``,
    gleiche Rechte) und liefert die Kennung fuer „Rueckgaengig“.
    -> ``test_delete_antwort_ist_kompatibel_und_nennt_die_frist``

Ausserdem: ``test_schema_hat_papierkorb_spalten`` (Migration/Modelle stimmen)
und ``test_schreibende_endpunkte_nur_post`` (SEC-11: POST + Inventar).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from diakronos_app.frappe_compat.exceptions import DoesNotExistError
from diakronos_app.frappe_compat.exceptions import PermissionError as FrappePermissionError
from diakronos_app.frappe_compat.registry import lookup
from diakronos_app.frappe_compat.session import set_user

ADMIN = "pap-admin@example.org"
MITGLIED = "pap-mitglied@example.org"
MUSIK = "pap-musik@example.org"

BEITRAEGE = "diakronos.diakonos.api.beitraege"
WIKI = "diakronos.diakonos.api.wiki"
GRUPPEN = "diakronos.diakonos.api.gruppen"
KRONOS = "diakronos.kronos.api"
KALENDER_GET = "diakronos.kronos.api.calendar_get"
MUSIK_MODUL = "diakronos.psalmos.api.musik"
PAPIERKORB = "diakronos_app.api.papierkorb"


# ── Bestand ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def welt(patched_db, fake_redis):
    """Ein Admin, ein Mitglied, ein Musikverantwortlicher und je ein Objekt
    pro Bereich (Beitrag, Termin, Gruppe, Wiki-Seite, Lied)."""
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Beitrag, Gruppe, WikiArtikel
    from diakronos_app.models.kronos import Element, Kalender
    from diakronos_app.models.psalmos import Lied, Liedstrophe

    sess = patched_db()
    sess.add_all([
        User(name=ADMIN, email=ADMIN, full_name="Ada Admin", enabled=1),
        User(name=MITGLIED, email=MITGLIED, full_name="Mia Mitglied", enabled=1),
        User(name=MUSIK, email=MUSIK, full_name="Momo Musik", enabled=1),
    ])
    sess.add_all([
        HasRole(name="pap-hr-1", parent=ADMIN, parenttype="User", parentfield="roles",
                role="System Manager", docstatus=0, idx=0),
        # Termin-Schreibrecht: der Admin ist Kalenderadministrator (dieselbe
        # Rolle, die `get_accessible_calendars` fuer `write=True` verlangt).
        HasRole(name="pap-hr-2", parent=ADMIN, parenttype="User", parentfield="roles",
                role="Kalenderadministrator", docstatus=0, idx=0),
        # Musikverantwortung: Verantwortlicher des Dienstbereichs "Musik und
        # Worship" — dieselbe Regel wie `_is_musikverantwortlicher`.
        _dienstbereich_verantwortlicher(MUSIK),
    ])

    sess.add(Beitrag(
        name="BEI-1", titel="Sommerfest", kategorie="gemeinde",
        datum=date(2026, 7, 1), autor="Ada Admin", autor_email=ADMIN,
        veroeffentlicht=1, auf_website=1, auszug="Fest im Hof",
        inhalt="<p>Alle eingeladen.</p>", bild=None, docstatus=0, idx=0,
    ))
    sess.add(WikiArtikel(
        name="WIK-1", titel="Beamer", kategorie="technik", tags="Tonanlage",
        autor="Ada Admin", autor_email=ADMIN, ist_neu=1,
        auszug="So geht der Beamer", inhalt="<p>Anleitung</p>", docstatus=0, idx=0,
    ))
    sess.add(Gruppe(
        name="GRU-1", gruppenname="Jugend", status="Aktiv",
        sichtbarkeit="Intern", dienstbereich=None, docstatus=0, idx=0,
    ))
    sess.add(Kalender(name="KAL-1", calendar_name="Gottesdienste",
                      website_freigabe=1, website_slug="gottesdienste",
                      docstatus=0, idx=0))
    sess.add(Element(
        name="ELE-1", element_name="Gottesdienst", element_calendar="KAL-1",
        element_start=datetime(2026, 11, 8, 10, 0),
        element_end=datetime(2026, 11, 8, 11, 30),
        status="Festgelegt", docstatus=0, idx=0,
    ))
    sess.add(Lied(name="LIE-1", titel="Grosser Gott", aktiv=1, docstatus=0, idx=0,
                  rechte_status="frei"))
    sess.add(Liedstrophe(name="LIE-1-ST1", parent="LIE-1", parenttype="Lied",
                         parentfield="strophen", nummer="1", typ="Strophe",
                         text="Grosser Gott, wir loben dich", docstatus=0, idx=0))
    sess.commit()
    yield sess
    sess.close()


def _dienstbereich_verantwortlicher(user: str):
    from diakronos_app.models.diakonos import DienstbereichVerantwortlicher

    return DienstbereichVerantwortlicher(
        name=f"DBV-{user}", parent="Musik und Worship", parenttype="Dienstbereich",
        parentfield="verantwortlicher", user=user, docstatus=0, idx=0,
    )


@pytest.fixture()
def als_admin(welt):
    set_user(ADMIN)
    yield ADMIN
    set_user("Administrator")


@pytest.fixture()
def als_mitglied(welt):
    set_user(MITGLIED)
    yield MITGLIED
    set_user("Administrator")


@pytest.fixture()
def als_musik(welt):
    set_user(MUSIK)
    yield MUSIK
    set_user("Administrator")


def _geloescht_am(sess, doctype: str, name: str):
    """``geloescht_am`` direkt aus der Tabelle (ohne Umweg ueber die API)."""
    from diakronos_app.frappe_compat.registry_gen import model_for

    model = model_for(doctype)
    sess.expire_all()
    return sess.execute(
        model.__table__.select().with_only_columns(model.__table__.c.geloescht_am)
        .where(model.__table__.c.name == name)
    ).scalar()


# ── P1: Loeschen / Unsichtbarkeit je Bereich ────────────────────────────────


def test_beitrag_loeschen_wirkt_wie_entfernt(client, als_admin, welt):
    r = client.post(f"/api/method/{BEITRAEGE}.delete_beitrag", data={"beitrag_id": "BEI-1"})
    assert r.status_code == 200, r.text

    from diakronos_app.models.diakonos import Beitrag

    # P1: die ZEILE bleibt (Papierkorb), sie ist nur markiert.
    assert welt.get(Beitrag, "BEI-1") is not None
    assert _geloescht_am(welt, "Beitrag", "BEI-1") is not None

    liste = client.get(f"/api/method/{BEITRAEGE}.get_beitraege_liste").json()["message"]
    assert [b["id"] for b in liste] == []
    detail = client.get(f"/api/method/{BEITRAEGE}.get_beitrag_detail",
                        params={"beitrag_id": "BEI-1"})
    assert detail.status_code != 200


def test_wiki_loeschen_wirkt_wie_entfernt(client, als_admin, welt):
    r = client.post(f"/api/method/{WIKI}.delete_wiki_artikel", data={"artikel_id": "WIK-1"})
    assert r.status_code == 200, r.text
    assert _geloescht_am(welt, "Wiki Artikel", "WIK-1") is not None

    liste = client.get(f"/api/method/{WIKI}.get_wiki_artikel_liste").json()["message"]
    assert liste == []
    tags = client.get(f"/api/method/{WIKI}.get_wiki_tags").json()["message"]
    assert tags == []          # geloeschte Artikel liefern keine Tags mehr
    detail = client.get(f"/api/method/{WIKI}.get_wiki_artikel_detail",
                        params={"artikel_id": "WIK-1"})
    assert detail.status_code != 200


def test_gruppe_loeschen_wirkt_wie_entfernt(client, als_admin, welt):
    r = client.post(f"/api/method/{GRUPPEN}.delete_gruppe", data={"name": "GRU-1"})
    assert r.status_code == 200, r.text
    assert _geloescht_am(welt, "Gruppe", "GRU-1") is not None

    hier = client.get(f"/api/method/{GRUPPEN}.get_gruppen_hierarchie").json()["message"]
    assert hier["gruppen"] == []
    detail = client.get(f"/api/method/{GRUPPEN}.get_gruppe_detail",
                        params={"gruppe_id": "GRU-1"})
    assert detail.status_code != 200


def test_termin_loeschen_wirkt_wie_entfernt(client, als_admin, welt):
    r = client.post(f"/api/method/{KRONOS}.event_crud.delete_event", data={"name": "ELE-1"})
    assert r.status_code == 200, r.text
    antwort = r.json()["message"]
    assert antwort["success"] is True
    assert antwort["wiederherstellbar_bis"]          # P4: Kennung fuer Rueckgaengig
    assert _geloescht_am(welt, "Element", "ELE-1") is not None

    # UX2b2 (F1): der Haupt-Kalender-Feed (KronosCalendar/KronosDayEventsDialog)
    # darf den geloeschten Termin NICHT mehr liefern — ein echter HTTP-Aufruf
    # auf den richtigen Modulpfad, ohne Status-Schutz: ein Fehler rutscht nicht
    # mehr als „kein Ergebnis“ durch.
    set_user(ADMIN)
    liste = client.post(f"/api/method/{KALENDER_GET}.get_calendar_events",
                        json={"start_date": "2026-11-01", "end_date": "2026-11-30",
                              "calendar_filter": '["KAL-1"]'})
    assert liste.status_code == 200, liste.text
    assert liste.json()["message"] == []

    # Und im Bearbeitungsmodus (Moderator sieht alle Status) ebenso.
    bearbeiten = client.post(f"/api/method/{KALENDER_GET}.get_calendar_events",
                             json={"start_date": "2026-11-01", "end_date": "2026-11-30",
                                   "calendar_filter": '["KAL-1"]', "view_mode": False})
    assert bearbeiten.status_code == 200, bearbeiten.text
    assert bearbeiten.json()["message"] == []

    # Einzeltermin (get_mein_termin) ebenso: wie nicht vorhanden.
    einzeln = client.post(f"/api/method/{KALENDER_GET}.get_mein_termin",
                          json={"element_id": "ELE-1"})
    assert einzeln.status_code != 200, einzeln.text

    # Gegenprobe: im Papierkorb zurueckgeholt -> wieder im Feed.
    from diakronos_app import papierkorb

    papierkorb.wiederherstellen("Element", "ELE-1")
    wieder = client.post(f"/api/method/{KALENDER_GET}.get_calendar_events",
                         json={"start_date": "2026-11-01", "end_date": "2026-11-30",
                               "calendar_filter": '["KAL-1"]'})
    assert wieder.status_code == 200, wieder.text
    assert [e["id"] for e in wieder.json()["message"]] == ["ELE-1"]


def test_lied_loeschen_wirkt_wie_entfernt(client, als_musik, welt):
    r = client.post(f"/api/method/{MUSIK_MODUL}.delete_lied", data={"lied": "LIE-1"})
    assert r.status_code == 200, r.text
    assert _geloescht_am(welt, "Lied", "LIE-1") is not None

    liste = client.get(f"/api/method/{MUSIK_MODUL}.get_lieder").json()["message"]
    assert liste == []
    suche = client.get(f"/api/method/{MUSIK_MODUL}.get_lieder",
                       params={"suche": "Grosser Gott"}).json()["message"]
    assert suche == []
    detail = client.get(f"/api/method/{MUSIK_MODUL}.get_lied_detail",
                        params={"lied": "LIE-1"})
    assert detail.status_code != 200

    # Strophen bleiben bis zum endgueltigen Entfernen (Wiederherstellen soll
    # den GANZEN Liedinhalt zurueckbringen).
    from diakronos_app.models.psalmos import Liedstrophe

    welt.expire_all()
    assert welt.get(Liedstrophe, "LIE-1-ST1") is not None


# ── P1: Website, CalDAV, iCal ───────────────────────────────────────────────


def test_website_termine_und_beitraege_ohne_papierkorb(patched_db, welt):
    """Die oeffentliche Website-API zeigt geloeschte Termine/Beitraege nicht."""
    from diakronos_app import papierkorb
    from diakronos_app.website import oeffentlich_daten as daten

    sess = welt
    papierkorb.loeschen("Element", "ELE-1", von=ADMIN)
    papierkorb.loeschen("Beitrag", "BEI-1", von=ADMIN)
    papierkorb.loeschen("Gruppe", "GRU-1", von=ADMIN)

    assert daten.termine(sess, kalender=["gottesdienste"]) == []
    assert daten.beitraege_oeffentlich(sess) == []
    assert daten.gruppen(sess) == []


def test_website_nur_aktive_filter_ist_die_eine_bedingung():
    """Alle fuenf Bereiche liefern denselben Filter (eine Wahrheit)."""
    from diakronos_app import papierkorb

    for doctype in papierkorb.BEREICHE:
        assert papierkorb.nur_aktive_filter(doctype) == [["geloescht_am", "is", "not set"]]
        assert papierkorb.nicht_geloescht_ist(doctype) is not None
    with pytest.raises(KeyError):
        papierkorb.nur_aktive_filter("Mitglied")     # kein stilles „alles zeigen“


def test_caldav_und_ical_werden_echt_geprueft():
    """UX2b2 (F5): Verweis auf die ehrlichen Abruf-Tests.

    Die frueheren Fassungen hier waren Attrappen — ``test_caldav_...`` prueft
    nur ``callable(server.get_all)``, ``test_ical_...`` durchsuchte die
    Quelldateien nach dem Wort ``geloescht_am``. Beide waeren mit jedem
    Verhalten gruen gewesen (auch mit einem kaputten Filter). Die echten
    Abrufe stehen jetzt in ``tests/test_ux2b2_feedtes.py``:
    CalDAV ``_get_events``, iCal ``_ical_inhalt`` und
    ``oeffentlich_daten.termine`` — jeweils geloescht -> nicht im Ergebnis,
    wiederhergestellt -> wieder im Ergebnis. Dieser Test haelt fest, dass die
    ehrliche Fassung existiert (damit sie niemand wieder durch einen grep
    ersetzt).
    """
    from pathlib import Path

    ehrlich = Path(__file__).with_name("test_ux2b2_feedtes.py")
    assert ehrlich.is_file(), "die ehrlichen Feed-Tests fehlen"
    text = ehrlich.read_text(encoding="utf-8")
    for erwartet in ("server._get_events", "_ical_inhalt", "daten.termine",
                     "_in_papierkorb", "_zurueck"):
        assert erwartet in text, erwartet


def test_gruppe_loeschen_nur_verwaltung(client, als_mitglied, welt):
    """UX2b2 (F6): Gruppenverantwortliche duerfen NICHT loeschen.

    Das Loeschen einer Gruppe nimmt sie aus Organigramm, Auswahlen und der
    Website und entfernt nach 7 Tagen Mitgliedschaften und Verantwortlichkeiten
    endgueltig — eine Verwaltungsaufgabe. Ein Gruppenverantwortlicher soll
    seine Gruppe pflegen, nicht verschwinden lassen. Dieselbe Schranke gilt
    fuer das Zurueckholen.
    """
    from diakronos_app.models.core import HasRole
    from diakronos_app.models.diakonos import GruppeVerantwortlicher

    sess = welt
    sess.add(GruppeVerantwortlicher(
        name="GV-1", parent="GRU-1", parenttype="Gruppe",
        parentfield="verantwortlicher", user=MITGLIED, docstatus=0, idx=0,
    ))
    sess.commit()
    set_user(MITGLIED)

    r = client.post(f"/api/method/{GRUPPEN}.delete_gruppe", data={"name": "GRU-1"})
    assert r.status_code == 403, (
        f"Gruppenverantwortlicher durfte loeschen: {r.status_code} {r.text}"
    )
    assert _geloescht_am(welt, "Gruppe", "GRU-1") is None

    # Zurueckholen ebenso gesperrt.
    set_user(ADMIN)
    client.post(f"/api/method/{GRUPPEN}.delete_gruppe", data={"name": "GRU-1"})
    set_user(MITGLIED)
    r2 = client.post(f"/api/method/{GRUPPEN}.wiederherstellen_gruppe",
                     data={"name": "GRU-1"})
    assert r2.status_code == 403
    assert _geloescht_am(welt, "Gruppe", "GRU-1") is not None


def test_gruppe_loeschen_mitgliederadministrator_darf(client, welt):
    """UX2b2 (F6): `Mitgliederadministrator` ist Verwaltung — darf loeschen."""
    from diakronos_app.models.core import HasRole

    sess = welt
    sess.add(HasRole(name="pap-hr-ma", parent=MITGLIED, parenttype="User",
                     parentfield="roles", role="Mitgliederadministrator",
                     docstatus=0, idx=0))
    sess.commit()
    set_user(MITGLIED)
    r = client.post(f"/api/method/{GRUPPEN}.delete_gruppe", data={"name": "GRU-1"})
    assert r.status_code == 200, r.text
    assert _geloescht_am(welt, "Gruppe", "GRU-1") is not None


def test_lied_loeschen_wie_bisheriges_liedrecht(client, als_musik, welt):
    """UX2b2 (F6): `delete_lied` nutzt die bestehenden Lied-Rechte.

    Musikverantwortlicher darf (das ist das bisherige Schreibrecht), ein
    gewoehnliches Mitglied nicht.
    """
    r = client.post(f"/api/method/{MUSIK_MODUL}.delete_lied", data={"lied": "LIE-1"})
    assert r.status_code == 200, r.text
    assert _geloescht_am(welt, "Lied", "LIE-1") is not None

    # Ein Mitglied ohne Musikrecht: keine Berechtigung.
    papierkorb_zurueck = f"/api/method/{MUSIK_MODUL}.wiederherstellen_lied"
    set_user(MITGLIED)
    assert client.post(papierkorb_zurueck, data={"lied": "LIE-1"}).status_code == 403
    assert client.post(f"/api/method/{MUSIK_MODUL}.delete_lied",
                       data={"lied": "LIE-1"}).status_code == 403


# ── P2: Wiederherstellen ────────────────────────────────────────────────────


def test_wiederherstellen_beitrag(client, als_admin, welt):
    client.post(f"/api/method/{BEITRAEGE}.delete_beitrag", data={"beitrag_id": "BEI-1"})
    r = client.post(f"/api/method/{BEITRAEGE}.wiederherstellen_beitrag",
                    data={"beitrag_id": "BEI-1"})
    assert r.status_code == 200, r.text
    assert _geloescht_am(welt, "Beitrag", "BEI-1") is None

    liste = client.get(f"/api/method/{BEITRAEGE}.get_beitraege_liste").json()["message"]
    assert [b["id"] for b in liste] == ["BEI-1"]


def test_wiederherstellen_wiki_gruppe_termin_lied(client, als_admin, welt):
    from diakronos_app import papierkorb

    set_user(ADMIN)

    for doctype, name in (("Wiki Artikel", "WIK-1"), ("Gruppe", "GRU-1"),
                          ("Element", "ELE-1"), ("Lied", "LIE-1")):
        papierkorb.loeschen(doctype, name, von=ADMIN)

    r = client.post(f"/api/method/{WIKI}.wiederherstellen_wiki_artikel",
                    data={"artikel_id": "WIK-1"})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/method/{GRUPPEN}.wiederherstellen_gruppe", data={"name": "GRU-1"})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/method/{KRONOS}.event_crud.wiederherstellen_event",
                    data={"name": "ELE-1"})
    assert r.status_code == 200, r.text
    set_user(MUSIK)
    r = client.post(f"/api/method/{MUSIK_MODUL}.wiederherstellen_lied", data={"lied": "LIE-1"})
    assert r.status_code == 200, r.text
    set_user(ADMIN)

    for doctype, name in (("Wiki Artikel", "WIK-1"), ("Gruppe", "GRU-1"),
                          ("Element", "ELE-1"), ("Lied", "LIE-1")):
        assert _geloescht_am(welt, doctype, name) is None


def test_wiederherstellen_ohne_recht_403(client, als_mitglied, welt):
    from diakronos_app import papierkorb

    papierkorb.loeschen("Beitrag", "BEI-1", von=ADMIN)
    papierkorb.loeschen("Gruppe", "GRU-1", von=ADMIN)
    papierkorb.loeschen("Lied", "LIE-1", von=ADMIN)

    assert client.post(f"/api/method/{BEITRAEGE}.wiederherstellen_beitrag",
                       data={"beitrag_id": "BEI-1"}).status_code == 403
    assert client.post(f"/api/method/{GRUPPEN}.wiederherstellen_gruppe",
                       data={"name": "GRU-1"}).status_code == 403
    assert client.post(f"/api/method/{MUSIK_MODUL}.wiederherstellen_lied",
                       data={"lied": "LIE-1"}).status_code == 403


def test_papierkorb_liste_nur_admin(client, als_admin, als_mitglied, welt):
    from diakronos_app import papierkorb

    papierkorb.loeschen("Beitrag", "BEI-1", von=ADMIN)
    papierkorb.loeschen("Lied", "LIE-1", von=ADMIN)

    assert client.get(f"/api/method/{PAPIERKORB}.liste").status_code == 403

    # Als Admin (Fixture wechselt die Identitaet).
    set_user(ADMIN)
    r = client.get(f"/api/method/{PAPIERKORB}.liste")
    assert r.status_code == 200, r.text
    antwort = r.json()["message"]
    assert antwort["aufbewahrung_tage"] == 7
    bereiche = {e["bereich"] for e in antwort["eintraege"]}
    assert bereiche == {"Beitrag", "Lied"}
    for eintrag in antwort["eintraege"]:
        assert eintrag["geloescht_von"] == ADMIN
        assert eintrag["laeuft_ab_am"]


# ── P3: Endgueltiges Entfernen nach 7 Tagen ─────────────────────────────────


def test_aufraeumen_haelt_die_frist_ein(patched_db, welt):
    """Nach 6 Tagen bleibt die Zeile, nach 8 Tagen ist sie weg (Zeit simuliert)."""
    from diakronos_app import papierkorb
    from diakronos_app.models.diakonos import Beitrag

    papierkorb.loeschen("Beitrag", "BEI-1", von=ADMIN)

    assert papierkorb.aufraeumen(jetzt=datetime.now() + timedelta(days=6)) == 0
    welt.expire_all()
    assert welt.get(Beitrag, "BEI-1") is not None

    jetzt = datetime.now() + timedelta(days=8)
    assert papierkorb.aufraeumen(jetzt=jetzt) == 1
    welt.expire_all()
    assert welt.get(Beitrag, "BEI-1") is None
    # Idempotent: ein zweiter Lauf findet nichts mehr.
    assert papierkorb.aufraeumen(jetzt=jetzt) == 0


def test_aufraeumen_entfernt_kindzeilen_und_verweise(patched_db, welt):
    """Termin weg -> Kind-Zeilen weg, Verweise geloest, Buchung bleibt."""
    from diakronos_app import papierkorb
    from diakronos_app.models.diakonos import RessourcenBuchung
    from diakronos_app.models.kronos import Element, ElementMitarbeiter

    from diakronos_app.db import SessionLocal  # noqa: F401 — gepatcht via Fixture

    sess = welt
    sess.add(ElementMitarbeiter(name="EM-1", parent="ELE-1", parenttype="Element",
                                parentfield="mitarbeiter", docstatus=0, idx=0))
    sess.add(RessourcenBuchung(name="BUC-1", ressource="RAUM-1", docstatus=0, idx=0))
    sess.commit()

    papierkorb.loeschen("Element", "ELE-1", von=ADMIN)
    papierkorb.endgueltig_entfernen("Element", "ELE-1")

    sess.expire_all()
    assert sess.get(Element, "ELE-1") is None
    assert sess.execute(
        ElementMitarbeiter.__table__.select().where(ElementMitarbeiter.parent == "ELE-1")
    ).first() is None
    # Eine Buchung traegt den Terminbezug NICHT in ihrer eigenen Zeile (kein
    # `element`-Feld) — sie bleibt nach dem Entfernen des Termins bestehen.
    assert sess.get(RessourcenBuchung, "BUC-1") is not None


def test_aufraeumen_entfernt_lied_vollstaendig(patched_db, welt):
    from diakronos_app import papierkorb
    from diakronos_app.models.psalmos import Lied, Liedstrophe

    papierkorb.loeschen("Lied", "LIE-1", von=ADMIN)
    papierkorb.endgueltig_entfernen("Lied", "LIE-1")

    welt.expire_all()
    assert welt.get(Lied, "LIE-1") is None
    assert welt.get(Liedstrophe, "LIE-1-ST1") is None


def test_scheduler_job_ist_registriert():
    from diakronos_app import scheduler

    ids = {job_id for _fn, job_id in scheduler.DAILY_JOBS}
    assert "papierkorb_aufraeumen" in ids
    assert scheduler.job_papierkorb_aufraeumen is not None


# ── P4: API-Kompatibilitaet ─────────────────────────────────────────────────


def test_delete_antwort_ist_kompatibel_und_nennt_die_frist(client, als_admin, welt):
    for pfad, daten in ((f"{BEITRAEGE}.delete_beitrag", {"beitrag_id": "BEI-1"}),
                        (f"{WIKI}.delete_wiki_artikel", {"artikel_id": "WIK-1"}),
                        (f"{KRONOS}.event_crud.delete_event", {"name": "ELE-1"})):
        r = client.post(f"/api/method/{pfad}", data=daten)
        assert r.status_code == 200, (pfad, r.text)
        antwort = r.json()["message"]
        assert antwort["success"] is True
        assert antwort["geloescht_am"]
        bis = datetime.fromisoformat(antwort["wiederherstellbar_bis"])
        von = datetime.fromisoformat(antwort["geloescht_am"])
        assert (bis - von) == timedelta(days=7)


# ── Schema + SEC-11 ─────────────────────────────────────────────────────────


def test_schema_hat_papierkorb_spalten(engine):
    """Migration und Modelle stimmen: alle fuenf Tabellen tragen beide Spalten."""
    from sqlalchemy import inspect

    insp = inspect(engine)
    for tabelle in ("beitrag", "element", "gruppe", "wiki_artikel", "lied"):
        spalten = {s["name"] for s in insp.get_columns(tabelle)}
        assert {"geloescht_am", "geloescht_von"} <= spalten, tabelle


@pytest.mark.parametrize("pfad", [
    f"{BEITRAEGE}.wiederherstellen_beitrag",
    f"{WIKI}.wiederherstellen_wiki_artikel",
    f"{GRUPPEN}.wiederherstellen_gruppe",
    f"{KRONOS}.event_crud.wiederherstellen_event",
    f"{MUSIK_MODUL}.wiederherstellen_lied",
    f"{MUSIK_MODUL}.delete_lied",
])
def test_schreibende_endpunkte_nur_post(pfad):
    """SEC-11: neue schreibende Endpunkte sind auf POST beschraenkt."""
    fn = lookup(pfad)
    assert fn is not None, pfad
    from diakronos_app.frappe_compat.registry import options_for

    optionen = options_for(fn)
    assert tuple(optionen.get("methods") or ()) == ("POST",), (pfad, optionen)


def test_wiederherstellen_meldet_unbekannte_zeile(patched_db, welt):
    """Unbekannte Kennung -> DoesNotExistError (kein stilles Erfolg)."""
    from diakronos_app import papierkorb

    with pytest.raises(DoesNotExistError):
        papierkorb.loeschen("Beitrag", "GIBT-ES-NICHT", von=ADMIN)


# ── UX2b2 F2: endgueltiges Loeschen unter PostgreSQL ────────────────────────


def _fremdschluessel_auf(tabelle: str) -> set[tuple[str, str]]:
    """Alle (Tabelle, Spalte), die per ForeignKey auf ``tabelle.name`` zeigen."""
    import diakronos_app.models  # noqa: F401 — alle Modelle registrieren
    from diakronos_app.models.base import Base

    treffer = set()
    for name, tab in Base.metadata.tables.items():
        for spalte in tab.columns:
            for fk in spalte.foreign_keys:
                if fk.column.table.name == tabelle and fk.column.name == "name":
                    treffer.add((name, spalte.name))
    return treffer


def test_element_verweise_sind_vollstaendig():
    """UX2b2 (F2): JEDER Fremdschluessel auf ``element.name`` ist bedacht.

    Der Fehler war nicht „ein Verweis fehlt“, sondern dass die Liste still
    veraltet: ein neues Feld mit Bezug auf den Termin haette das endgueltige
    Entfernen unter PostgreSQL wieder scheitern lassen, ohne dass ein Test es
    merkt. Der Test leitet die Sollmenge aus den Modellen ab und vergleicht.
    """
    from diakronos_app import papierkorb
    from diakronos_app.frappe_compat.registry_gen import model_for

    bekannt = {
        (model_for(dt).__tablename__, "element")
        for dt in papierkorb._ELEMENT_VERWEISE_NULL
    }
    # `element_aenderung` haengt per ON DELETE CASCADE am Termin — die Zeile
    # geht mit der Zeile, sie braucht keinen Eintrag in der Loes-Liste.
    from diakronos_app.models.kronos import ElementAenderung

    ist_kaskade = {(ElementAenderung.__tablename__, "element")}
    offen = _fremdschluessel_auf("element") - bekannt - ist_kaskade
    assert not offen, (
        "Fremdschluessel auf element.name ohne Eintrag in "
        f"papierkorb._ELEMENT_VERWEISE_NULL: {sorted(offen)}"
    )


def test_gruppe_verweise_sind_vollstaendig():
    """UX2b2 (F2): JEDER Fremdschluessel auf ``gruppe.name`` ist bedacht.

    Entweder NULL setzen (``_GRUPPE_VERWEISE_NULL``) oder mit der Gruppe
    loeschen (``_GRUPPE_VERWEISE_LOESCHEN``). Der Test verhindert, dass ein
    neues Feld mit Gruppenbezug das endgueltige Loeschen wieder bricht.
    """
    from diakronos_app import papierkorb
    from diakronos_app.frappe_compat.registry_gen import model_for

    bekannt = {
        (model_for(dt).__tablename__, spalte)
        for dt, spalte in (
            [(dt, "gruppe") for dt in papierkorb._GRUPPE_VERWEISE_NULL
             if dt != "Gruppe"]
            + [("Gruppe", "obergruppe")]
            + [(dt, "gruppe") for dt in papierkorb._GRUPPE_VERWEISE_LOESCHEN]
        )
    }
    offen = _fremdschluessel_auf("gruppe") - bekannt
    assert not offen, (
        "Fremdschluessel auf gruppe.name ohne Eintrag im Papierkorb: "
        f"{sorted(offen)}"
    )


def test_beitrag_verweise_sind_vollstaendig():
    """UX2b2 (F2): Fremdschluessel auf ``beitrag.name`` sind bedacht.

    ``beitrag_kommentar`` traegt Personendaten und MUSS mitgeloescht werden —
    der Test haelt fest, dass es keine unbedachte zweite Tabelle gibt.
    """
    bekannt = {("beitrag_kommentar", "parent")}
    offen = _fremdschluessel_auf("beitrag") - bekannt
    assert not offen, (
        "Fremdschluessel auf beitrag.name ohne Eintrag im Papierkorb: "
        f"{sorted(offen)}"
    )


def test_aufraeumen_entfernt_beitrag_mit_kommentaren(patched_db, welt):
    """UX2b2 (F2): Kommentare (Personendaten) gehen mit dem Beitrag."""
    from diakronos_app import papierkorb
    from diakronos_app.models.diakonos import Beitrag, BeitragKommentar

    welt.add(BeitragKommentar(name="BK-1", parent="BEI-1", parenttype="Beitrag",
                              parentfield="kommentare", autor="Mia",
                              text="Toller Bericht", docstatus=0, idx=0))
    welt.commit()

    papierkorb.loeschen("Beitrag", "BEI-1", von=ADMIN)
    papierkorb.endgueltig_entfernen("Beitrag", "BEI-1")

    welt.expire_all()
    assert welt.get(Beitrag, "BEI-1") is None
    assert welt.get(BeitragKommentar, "BK-1") is None


def test_aufraeumen_entfernt_gruppe_mit_allen_verweisen(patched_db, welt):
    """UX2b2 (F2): Gruppe mit Verweisen weg — Verweise geloest, Zeilen bleiben.

    Die SQLite-Fassung prueft die Logik; dass PostgreSQL die Fremdschluessel
    WIRKLICH erzwingt, weist ``tools/ux2b2_pg_pruefung.py`` gegen eine eigene
    Wegwerf-PostgreSQL nach (Karten-Nachtrag 11).
    """
    from diakronos_app import papierkorb
    from diakronos_app.models import (
        GruppenAnkuendigung,
        GruppenAufgabe,
        Untergruppe,
    )

    sess = welt
    sess.add(Untergruppe(name="UG-1", untergruppenname="Kreis", gruppe="GRU-1",
                         docstatus=0, idx=0))
    sess.add(GruppenAnkuendigung(name="GA-1", gruppe="GRU-1", titel="Hallo",
                                 docstatus=0, idx=0))
    sess.add(GruppenAufgabe(name="GAuf-1", gruppe="GRU-1", titel="Kuchen",
                            docstatus=0, idx=0))
    sess.commit()

    papierkorb.loeschen("Gruppe", "GRU-1", von=ADMIN)
    papierkorb.endgueltig_entfernen("Gruppe", "GRU-1")

    sess.expire_all()
    from diakronos_app.models.diakonos import Gruppe

    assert sess.get(Gruppe, "GRU-1") is None
    for model, name in ((Untergruppe, "UG-1"), (GruppenAnkuendigung, "GA-1"),
                        (GruppenAufgabe, "GAuf-1")):
        zeile = sess.get(model, name)
        assert zeile is not None, name
        assert zeile.gruppe is None, f"{name}.gruppe muss NULL sein"
