"""P1-4b — Nacharbeit zu P1-4 (Ressourcen: Termin-Anfragen entscheidbar,
Status nicht still zurueckstufen).

Deckt die blockierenden Befunde des unabhaengigen Code-Reviews
(dem vorausgehenden Review) VERHALTENSBASIERT ab — nicht per Quelltext-Regex:

  * B1  Gespiegelte Termin-Anfragen (`quelle="termin"`) waren in der Oberflaeche
        mit „Bestätigen“/„Ablehnen“ bedienbar, `decide_buchung` laedt aber nur
        `Ressourcen Buchung` -> der Moderator sah Knoepfe, die nur Fehler
        erzeugten. `decide_termin_ressource` entscheidet sie am richtigen Ort.
  * B2  `_normalize_ressourcen` stufte „Bestätigt“ bei Nutzern ohne
        Ressourcenmoderator-Rolle immer auf „Angefragt“ zurueck — der
        Bearbeiten-Dialog schickt die geladenen Zeilen zurueck, ein reines
        Titel-Aendern verlor damit die bestaetigte Zuordnung.
  * K1  Bucher-Name im Konfliktdialog nur fuer Ressourcen-Moderatoren/Admins.
  * K2  Positivtest: ein lesbarer Kalender zeigt seinen Titel weiterhin.
  * K3  `update_buchung` validiert Zeiten (417 statt 500).

Die Frontend-Quellen sichern die Node-Tests
`frontend/tests/p1-4b-ressourcen.test.mjs`.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from diakronos_app.frappe_compat.registry import lookup
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User, UserRole
from diakronos_app.models.diakonos import RessourcenBuchung
from diakronos_app.models.kronos import (
    Element,
    ElementRessource,
    Kalender,
    KalenderModerator,
    Ressource,
)

RES_MODUL = "diakronos.diakonos.api.ressourcen"
KONFLIKT_MODUL = "diakronos.kronos.api.ressource_api"
EVENT_MODUL = "diakronos.kronos.api.event_crud"

ANNA = "anna@example.org"
BRUNO = "bruno@example.org"
MODERATOR = "moderator@example.org"
KALMODERATOR = "kalmoderator@example.org"


@pytest.fixture()
def welt(patched_db):
    """Ein lesbarer Kalender, zwei Ressourcen, Nutzer/Moderatoren, Termine."""
    sess = patched_db()

    sess.add_all([
        User(name=ANNA, email=ANNA, full_name="Anna Beispiel", enabled=True),
        User(name=BRUNO, email=BRUNO, full_name="Bruno Beispiel", enabled=True),
        User(name=MODERATOR, email=MODERATOR, full_name="Moderator", enabled=True),
        User(name=KALMODERATOR, email=KALMODERATOR, full_name="Kalmod", enabled=True),
        Ressource(name="RES-BEAMER", ressource_name="Beamer", typ="Gegenstand",
                  kapazitaet=None, beschreibung="Full HD", tags="technik",
                  bild="", wartung=0, docstatus=0, idx=0),
        Ressource(name="RES-SAAL", ressource_name="Gemeindesaal", typ="Raum",
                  kapazitaet=80, beschreibung="Grosser Saal", tags="saal",
                  bild="", wartung=0, docstatus=0, idx=0),
        # Lesbarer Kalender „Gemeinde“ (Leserecht „All“).
        Kalender(name="Gemeinde", calendar_name="Gemeinde",
                 selbstverwaltet=0, docstatus=0, idx=0),
    ])
    sess.add_all([
        HasRole(name="HR-MOD", parent=MODERATOR, parenttype="User",
                parentfield="roles", role="Ressourcenmoderator", docstatus=0, idx=1),
        HasRole(name="HR-KALMOD", parent=KALMODERATOR, parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
        # Leserecht „All“ auf „Gemeinde“ — jeder angemeldete Nutzer darf lesen.
        UserRole(name="UR-GEM-1", parent="Gemeinde", parenttype="Kalender",
                 parentfield="leserechte", role="All", docstatus=0, idx=1),
    ])
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def als_anna(welt):
    set_user(ANNA)
    yield ANNA
    set_user("Administrator")


@pytest.fixture()
def als_moderator(welt):
    set_user(MODERATOR)
    yield MODERATOR
    set_user("Administrator")


def _termin(sess, name, titel, tage, stunden=2, owner=BRUNO, kalender="Gemeinde"):
    start = (datetime.now() + timedelta(days=tage)).replace(microsecond=0)
    el = Element(
        name=name, element_name=titel, element_start=start,
        element_end=start + timedelta(hours=stunden), element_calendar=kalender,
        ressource="", status="Festgelegt", ignore_conflict=0, docstatus=0,
        idx=0, owner=owner,
    )
    sess.add(el)
    sess.commit()
    return el


# ── B1: Termin-Anfragen sind entscheidbar ───────────────────────────────────


def test_b1_termin_anfrage_bestaetigen(client, als_moderator, welt):
    """`decide_termin_ressource` bestaetigt die Kind-Zeile am Termin."""
    _termin(welt, "EL-1", "Adventssingen", 10, owner=BRUNO)
    welt.add(ElementRessource(
        name="ER-1", parent="EL-1", parenttype="Element",
        parentfield="zusaetzliche_ressourcen", ressource="RES-BEAMER",
        freitext_ressource="", status="Angefragt", notiz="", docstatus=0, idx=1,
    ))
    welt.commit()

    r = client.post(f"/api/method/{RES_MODUL}.decide_termin_ressource",
                    json={"zeile_id": "ER-1", "entscheidung": "bestaetigen"})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["status"] == "Bestätigt"

    zeile = welt.get(ElementRessource, "ER-1")
    welt.refresh(zeile)
    assert zeile.status == "Bestätigt"


def test_b1_termin_anfrage_ablehnen_entfernt_zeile(client, als_moderator, welt):
    """`ablehnen` loescht die Zuordnung — sie darf am Termin nicht stehen bleiben."""
    _termin(welt, "EL-2", "Jugendabend", 12, owner=BRUNO)
    welt.add(ElementRessource(
        name="ER-2", parent="EL-2", parenttype="Element",
        parentfield="zusaetzliche_ressourcen", ressource="RES-BEAMER",
        freitext_ressource="", status="Angefragt", notiz="", docstatus=0, idx=1,
    ))
    welt.commit()

    r = client.post(f"/api/method/{RES_MODUL}.decide_termin_ressource",
                    json={"zeile_id": "ER-2", "entscheidung": "ablehnen"})
    assert r.status_code == 200, r.text
    assert welt.get(ElementRessource, "ER-2") is None


def test_b1_termin_anfrage_nicht_selbst_entscheiden(client, welt):
    """Wer den Termin angelegt hat, darf ihn nicht selbst bestaetigen."""
    _termin(welt, "EL-3", "Eigener Termin", 14, owner=MODERATOR)
    welt.add(ElementRessource(
        name="ER-3", parent="EL-3", parenttype="Element",
        parentfield="zusaetzliche_ressourcen", ressource="RES-BEAMER",
        freitext_ressource="", status="Angefragt", notiz="", docstatus=0, idx=1,
    ))
    welt.commit()

    set_user(MODERATOR)
    try:
        r = client.post(f"/api/method/{RES_MODUL}.decide_termin_ressource",
                        json={"zeile_id": "ER-3", "entscheidung": "bestaetigen"})
        assert r.status_code == 403, r.text
    finally:
        set_user("Administrator")


def test_b1_termin_anfrage_ohne_moderatorrolle_verweigert(client, als_anna, welt):
    """Ein normaler Nutzer darf Termin-Anfragen nicht entscheiden."""
    _termin(welt, "EL-4", "Fremd", 16, owner=BRUNO)
    welt.add(ElementRessource(
        name="ER-4", parent="EL-4", parenttype="Element",
        parentfield="zusaetzliche_ressourcen", ressource="RES-BEAMER",
        freitext_ressource="", status="Angefragt", notiz="", docstatus=0, idx=1,
    ))
    welt.commit()

    r = client.post(f"/api/method/{RES_MODUL}.decide_termin_ressource",
                    json={"zeile_id": "ER-4", "entscheidung": "bestaetigen"})
    assert r.status_code == 403, r.text


def test_b1_termin_anfrage_harter_konflikt_blockt(client, als_moderator, welt):
    """Vor dem Bestaetigen prueft der Server hart gegen bestehende Belegung."""
    _termin(welt, "EL-5", "Blockierer", 20, owner=BRUNO)
    # Bestaetigte Buchung auf RES-BEAMER im selben Zeitraum.
    start = (datetime.now() + timedelta(days=20)).replace(microsecond=0)
    welt.add(RessourcenBuchung(
        name="BUC-BLOCK", ressource="RES-BEAMER", zweck="Andere Nutzung",
        datum_von=start, datum_bis=start + timedelta(hours=1),
        gebucht_von=ANNA, gebucht_von_name="Anna Beispiel",
        status="Bestätigt", notizen="", docstatus=0, idx=0,
    ))
    welt.add(ElementRessource(
        name="ER-5", parent="EL-5", parenttype="Element",
        parentfield="zusaetzliche_ressourcen", ressource="RES-BEAMER",
        freitext_ressource="", status="Angefragt", notiz="", docstatus=0, idx=1,
    ))
    welt.commit()

    r = client.post(f"/api/method/{RES_MODUL}.decide_termin_ressource",
                    json={"zeile_id": "ER-5", "entscheidung": "bestaetigen"})
    assert r.status_code == 417, r.text
    assert "Konflikt" in r.json()["message"]
    assert welt.get(ElementRessource, "ER-5").status == "Angefragt"


def test_b1_gespiegelte_anfrage_kennt_quelle_creation_und_konflikt(
    client, als_moderator, welt
):
    """Die Spiegelung nennt `quelle`, `creation` und Konflikte (B1-Rest)."""
    _termin(welt, "EL-6", "Spiegel", 22, owner=BRUNO)
    welt.add(ElementRessource(
        name="ER-6", parent="EL-6", parenttype="Element",
        parentfield="zusaetzliche_ressourcen", ressource="RES-BEAMER",
        freitext_ressource="", status="Angefragt", notiz="", docstatus=0,
        idx=1, creation=datetime.now(),
    ))
    # Ein bestaetigter Termin auf derselben Ressource im selben Fenster.
    start = (datetime.now() + timedelta(days=22)).replace(microsecond=0)
    welt.add(Element(
        name="EL-6B", element_name="Kollision", element_start=start,
        element_end=start + timedelta(hours=1), element_calendar="Gemeinde",
        ressource="RES-BEAMER", status="Festgelegt", ignore_conflict=0,
        docstatus=0, idx=0, owner=ANNA,
    ))
    welt.commit()

    r = client.get(f"/api/method/{RES_MODUL}.get_anfragen")
    assert r.status_code == 200, r.text
    anfragen = r.json()["message"]["anfragen"]
    a = next(x for x in anfragen if x["id"] == "ER-6")
    assert a["quelle"] == "termin"
    assert a["creation"], "creation der Kind-Zeile fehlt"
    assert a["konflikt_hinweis"], "Konflikt der Anfrage fehlt"


# ── B2: Status wird nicht still zurueckgestuft ──────────────────────────────


def _termin_mit_bestaetigter_ressource(sess, name="EL-B2"):
    el = _termin(sess, name, "Bestaetigt am Termin", 30, owner=BRUNO)
    sess.add(ElementRessource(
        name=f"ER-{name}", parent=name, parenttype="Element",
        parentfield="zusaetzliche_ressourcen", ressource="RES-BEAMER",
        freitext_ressource="", status="Bestätigt", notiz="", docstatus=0, idx=1,
    ))
    sess.commit()
    return el


def test_b2_nichtmoderator_titel_aendern_laesst_status_stehen(welt):
    """Ein Nicht-Moderator aendert nur den Titel -> Status bleibt „Bestätigt“."""
    from diakronos_app.api.kronos import event_crud

    _termin_mit_bestaetigter_ressource(welt, "EL-B2A")
    set_user(ANNA)
    try:
        zeilen = event_crud._normalize_ressourcen(
            [{"ressource": "RES-BEAMER", "status": "Bestätigt"}],
            element_name="EL-B2A",
        )
    finally:
        set_user("Administrator")

    # Vor der Behebung stand hier „Angefragt“ — die bestaetigte Zuordnung war
    # durch ein reines Titel-Aendern verloren.
    assert zeilen[0]["status"] == "Bestätigt"


def test_b2_neue_zeile_ohne_moderatorrolle_wird_anfrage(welt):
    """Eine NEUE „Bestätigt“-Zeile bleibt die Schranke (OP-EVENT-10)."""
    from diakronos_app.api.kronos import event_crud

    _termin(welt, "EL-B2B", "Ohne Zuordnung", 32, owner=BRUNO)
    set_user(ANNA)
    try:
        zeilen = event_crud._normalize_ressourcen(
            [{"ressource": "RES-BEAMER", "status": "Bestätigt"}],
            element_name="EL-B2B",
        )
    finally:
        set_user("Administrator")

    assert zeilen[0]["status"] == "Angefragt"


def test_b2_kalendermoderator_speichern_laesst_status_stehen(client, welt, session_factory):
    """Freigabe durch einen reinen Kalendermoderator stutzt nichts zurueck.

    Der Kalendermoderator darf den Termin bearbeiten, hat aber KEINE
    Ressourcenmoderator-Rolle. `save_event` schickt die geladene Zeile mit
    „Bestätigt“ zurueck — der Status muss stehen bleiben.
    """
    from diakronos_app.api.kronos import event_crud

    _termin_mit_bestaetigter_ressource(welt, "EL-B2C")
    # Kalendermoderator fuer „Gemeinde“ einrichten.
    welt.add(KalenderModerator(
        name="KM-1", parent="Gemeinde", parenttype="Kalender",
        parentfield="kalendermoderatoren", user=KALMODERATOR, docstatus=0, idx=1,
    ))
    welt.commit()

    start = str(welt.get(Element, "EL-B2C").element_start)
    ende = str(welt.get(Element, "EL-B2C").element_end)

    set_user(KALMODERATOR)
    try:
        event_crud.save_event(
            name="EL-B2C",
            element_name="Nur der Titel",
            element_start=start,
            element_end=ende,
            element_calendar="Gemeinde",
            status="Festgelegt",
            zusaetzliche_ressourcen='[{"ressource": "RES-BEAMER", "status": "Bestätigt"}]',
        )
    finally:
        set_user("Administrator")

    # Frische Sitzung: `save_event` schreibt ueber eine eigene Transaktion und
    # legt die Kind-Zeilen neu an (Name wird neu vergeben).
    frisch = session_factory()
    try:
        zeilen = frisch.query(ElementRessource).filter(
            ElementRessource.parent == "EL-B2C"
        ).all()
        assert len(zeilen) == 1, f"Zuordnung fehlt/doppelt: {len(zeilen)}"
        assert zeilen[0].status == "Bestätigt", "Kalendermoderator stufte still zurueck"
    finally:
        frisch.close()


# ── K1: Bucher-Name nur fuer Ressourcen-Moderatoren/Admins ──────────────────


def test_k1_bucher_name_nur_fuer_moderatoren(als_anna, als_moderator, welt):
    from diakronos_app.api.kronos import ressource_api

    start = (datetime.now() + timedelta(days=5)).replace(microsecond=0)
    welt.add(RessourcenBuchung(
        name="BUC-K1", ressource="RES-BEAMER", zweck="Jugendabend",
        datum_von=start, datum_bis=start + timedelta(hours=2),
        gebucht_von=BRUNO, gebucht_von_name="Bruno Beispiel",
        status="Bestätigt", notizen="", docstatus=0, idx=0,
    ))
    welt.commit()

    def _nutzer():
        res = ressource_api.check_resource_conflict(
            ressource="RES-BEAMER",
            element_start=start.strftime("%Y-%m-%d %H:%M:%S"),
            element_end=(start + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
        )
        return [b["nutzer"] for c in res["conflicts"] for b in c.get("buchungen") or []]

    set_user(ANNA)
    try:
        assert _nutzer() == ["Belegt"], "Mitglied sah den Buchernamen"
    finally:
        set_user("Administrator")

    set_user(MODERATOR)
    try:
        assert _nutzer() == ["Bruno Beispiel"], "Moderator bekam den Buchernamen nicht"
    finally:
        set_user("Administrator")


# ── K2: Positivtest — lesbarer Kalender zeigt seinen Titel ──────────────────


def test_k2_lesbarer_kalender_zeigt_titel(als_anna, welt):
    from diakronos_app.api import ressourcen as R

    start = (datetime.now() + timedelta(days=7)).replace(microsecond=0)
    welt.add(Element(
        name="EL-K2", element_name="Gottesdienst", element_start=start,
        element_end=start + timedelta(hours=2), element_calendar="Gemeinde",
        ressource="RES-BEAMER", status="Festgelegt", ignore_conflict=0,
        docstatus=0, idx=0, owner=BRUNO,
    ))
    welt.commit()

    konflikte = R._check_konflikte(
        "RES-BEAMER",
        start.strftime("%Y-%m-%d %H:%M:%S"),
        (start + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
    )
    titel = {k["name"] for k in konflikte["kalender_konflikte"]}
    assert "Gottesdienst" in titel, "lesbarer Kalender zeigt seinen Titel nicht"


# ── K3: ungueltige Zeiten -> 417, nicht 500 ─────────────────────────────────


def test_k3_update_buchung_ungueltige_zeit_ist_417(client, als_anna, welt):
    from diakronos_app.api import ressourcen as R

    set_user(ANNA)
    try:
        buchung_id = R._create("Ressourcen Buchung", {
            "ressource": "RES-BEAMER", "zweck": "Zeiten", "status": "Angefragt",
            "datum_von": datetime(2032, 1, 1, 8, 0),
            "datum_bis": datetime(2032, 1, 1, 9, 0),
            "gebucht_von": ANNA, "gebucht_von_name": "Anna Beispiel",
        })
    finally:
        set_user("Administrator")

    set_user(ANNA)
    try:
        r = client.post(f"/api/method/{RES_MODUL}.update_buchung", json={
            "buchung_id": buchung_id, "zweck": "Zeiten",
            "datum_von": "kein-datum",
            "datum_bis": "2032-01-01 10:00:00",
        })
        # Vor der Behebung: 500 (roher ValueError aus compat_get_datetime).
        assert r.status_code == 417, f"{r.status_code}: {r.text}"
    finally:
        set_user("Administrator")


def test_k3_termin_ressource_endpunkt_ist_erreichbar():
    assert lookup(f"{RES_MODUL}.decide_termin_ressource") is not None
