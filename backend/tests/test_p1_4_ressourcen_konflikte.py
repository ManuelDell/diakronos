"""P1-4 — Ressourcen: Bestaetigen/Ablehnen und Konflikte (Backend).

Deckt die serverseitigen Ursachen der Befunde des Nachtberichts ab:

  * OP-EVENT-4  `check_resource_conflict` mit `exclude_id` meldete den Termin
                als Konflikt mit SICH SELBST (Zeile `{**base_filters,
                "name": ["in", parent_ids]}` ueberschrieb `name != exclude_id`).
  * OP-EVENT-11 Der Konfliktdialog bekam fuer Ressourcenbuchungen nur den
                Gegenstand — Zweck/Zeitraum/Bucher fehlten.
  * OP-EVENT-10 Ein Termin-Formular durfte eine Ressource selbst bestaetigen
                und umging damit die Ressourcen-Moderation.
  * OP-HANDY-12 Die Konfliktmeldung trug das rohe Praefix „kalender:“ und den
                Titel eines fremden, nicht lesbaren Kalenders.
  * OP-HANDY-23 „Meine Buchungen“ zeigte englische Datumsteile („Sat, 28. Nov“).
  * OP-EVENT-14 `update_buchung` konnte nur Zweck/Notizen — kein Verschieben.

Die Frontend-Quellen sichern die Node-Tests
`frontend/tests/p1-4-ressourcen-konflikte.test.mjs`.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from diakronos_app.frappe_compat.registry import lookup
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User, UserRole
from diakronos_app.models.diakonos import RessourcenBuchung
from diakronos_app.models.kronos import Element, ElementRessource, Kalender, Ressource

RES_MODUL = "diakronos.diakonos.api.ressourcen"
KONFLIKT_MODUL = "diakronos.kronos.api.ressource_api"

ANNA = "anna@example.org"
BRUNO = "bruno@example.org"
MODERATOR = "moderator@example.org"


def _leser_kalender(name: str) -> Kalender:
    """Ein Kalender mit Leserecht „All“ (jeder angemeldete Nutzer)."""
    return Kalender(
        name=name, calendar_name=name, selbstverwaltet=0, docstatus=0, idx=0,
    )


def _leserecht(kalender_name: str, role: str, idx: int) -> UserRole:
    """Kind-Zeile `User Role` unter `leserechte` eines Kalenders."""
    return UserRole(
        name=f"UR-{kalender_name}-{idx}", parent=kalender_name,
        parenttype="Kalender", parentfield="leserechte", role=role,
        docstatus=0, idx=idx,
    )


@pytest.fixture()
def welt(patched_db):
    """Zwei Ressourcen, zwei Nutzer, ein Moderator, ein fremder Kalender."""
    sess = patched_db()

    sess.add_all([
        Ressource(name="RES-RAUM", ressource_name="Gemeindesaal", typ="Raum",
                  kapazitaet=80, beschreibung="Grosser Saal", tags="saal",
                  bild="", wartung=0, docstatus=0, idx=0),
        Ressource(name="RES-BEAMER", ressource_name="Beamer", typ="Gegenstand",
                  kapazitaet=None, beschreibung="Full HD", tags="technik",
                  bild="", wartung=0, docstatus=0, idx=0),
        # Anna lesbarer Kalender + ein fremder (nicht lesbarer) Kalender.
        _leser_kalender("Gemeinde"),
        Kalender(name="Fremd-Intern", calendar_name="Intern",
                 selbstverwaltet=0, docstatus=0, idx=0),
    ])

    # Leserecht „All“ auf „Gemeinde“; „Fremd-Intern“ bleibt ohne Leserecht.
    sess.add(_leserecht("Gemeinde", "All", 1))

    start = (datetime.now() + timedelta(days=10)).replace(microsecond=0)
    ende = start + timedelta(hours=3)

    # Der eigene Termin (Adventssingen) traegt den Beamer als Zusatzressource —
    # genau der Fall aus OP-EVENT-4 (Verschieben meldete den Selbstkonflikt).
    sess.add_all([
        Element(name="NACHT-EVENT", element_name="Adventssingen",
                element_start=start, element_end=ende,
                element_calendar="Gemeinde", ressource="RES-RAUM",
                ignore_conflict=0, docstatus=0, idx=0),
        ElementRessource(
            name="ER-BEAMER", parent="NACHT-EVENT", parenttype="Element",
            parentfield="zusaetzliche_ressourcen", ressource="RES-BEAMER",
            status="Bestätigt", notiz="", docstatus=0, idx=1,
        ),
        # Ein FREMDER Termin im nicht lesbaren Kalender (OP-HANDY-12).
        Element(name="ELE-FREMD", element_name="Teenykreis",
                element_start=start, element_end=ende,
                element_calendar="Fremd-Intern", ressource="RES-BEAMER",
                ignore_conflict=0, docstatus=0, idx=0),
    ])

    sess.add_all([
        HasRole(name="HR-1", parent=MODERATOR, parenttype="User", parentfield="roles",
                role="Ressourcenmoderator", docstatus=0, idx=1),
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


# ── OP-EVENT-4: Selbstkonflikt beim Verschieben ─────────────────────────────


def test_op_event_4_exclude_id_verhindert_selbstkonflikt(als_anna, welt):
    """Der eigene Termin darf mit `exclude_id` nicht als eigener Konflikt gelten."""
    from diakronos_app.api.kronos import ressource_api

    start = (datetime.now() + timedelta(days=10)).replace(microsecond=0)
    ergebnis = ressource_api.check_resource_conflict(
        ressource="RES-BEAMER",
        element_start=start.strftime("%Y-%m-%d %H:%M:%S"),
        element_end=(start + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
        exclude_id="NACHT-EVENT",
    )

    namen = {
        ev["name"]
        for c in ergebnis["conflicts"]
        for ev in c.get("events") or []
    }
    # Vor der Behebung stand NACHT-EVENT hier — der Termin blockierte sich selbst.
    assert "NACHT-EVENT" not in namen
    # Der fremde Termin im selben Fenster bleibt ein echter Konflikt.
    assert "ELE-FREMD" in namen


def test_op_event_4_fremder_termin_bleibt_konflikt(als_anna, welt):
    """Ohne (oder mit anderem) exclude_id wird der fremde Termin weiter erkannt."""
    from diakronos_app.api.kronos import ressource_api

    start = (datetime.now() + timedelta(days=10)).replace(microsecond=0)
    ergebnis = ressource_api.check_resource_conflict(
        ressource="RES-BEAMER",
        element_start=start.strftime("%Y-%m-%d %H:%M:%S"),
        element_end=(start + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
        exclude_id="IRGENDEIN-ANDERER",
    )
    namen = {
        ev["name"]
        for c in ergebnis["conflicts"]
        for ev in c.get("events") or []
    }
    assert "ELE-FREMD" in namen
    assert ergebnis["has_conflict"] is True


# ── OP-EVENT-11: Dialog nennt Zweck, Zeitraum und Bucher ────────────────────


def test_op_event_11_buchungen_mit_zweck_zeitraum_und_bucher(als_anna, welt):
    """Bestätigte Buchung erscheint im Konflikt mit wem/wann/wofür."""
    from diakronos_app.api.kronos import ressource_api

    start = (datetime.now() + timedelta(days=30)).replace(microsecond=0)
    welt.add(RessourcenBuchung(
        name="BUC-BEAMER", ressource="RES-BEAMER", zweck="Jugendabend",
        datum_von=start, datum_bis=start + timedelta(hours=2),
        gebucht_von=BRUNO, gebucht_von_name="Bruno Beispiel",
        status="Bestätigt", notizen="", docstatus=0, idx=0,
    ))
    welt.commit()

    ergebnis = ressource_api.check_resource_conflict(
        ressource="RES-BEAMER",
        element_start=start.strftime("%Y-%m-%d %H:%M:%S"),
        element_end=(start + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
    )

    buchungen = [b for c in ergebnis["conflicts"] for b in c.get("buchungen") or []]
    assert buchungen, "Buchung muss im Konflikt auftauchen"
    b = next(x for x in buchungen if x["name"] == "BUC-BEAMER")
    # OP-EVENT-11: diese drei Felder fehlten dem Dialog.
    assert b["titel"] == "Jugendabend"
    assert b["zeitraum"].startswith(start.strftime("%d.%m.%Y %H:%M"))
    # P1-4b (K1): Der Bucher-Name ist eine Ressourcen-Sicht. Anna ist NICHT
    # Ressourcenmoderatorin -> maskiert. Der Moderator sieht ihn (s.
    # test_p1_4b_ressourcen.py::test_k1_bucher_name_nur_fuer_moderatoren).
    assert b["nutzer"] == "Belegt"


# ── OP-EVENT-10: Selbstbestaetigung am Termin wird zur Anfrage ──────────────


def test_op_event_10_nichtmoderator_kann_ressource_nicht_selbst_bestaetigen(als_anna, welt):
    from diakronos_app.api.kronos import event_crud

    zeilen = event_crud._normalize_ressourcen([
        {"ressource": "RES-BEAMER", "status": "Bestätigt"},
    ])
    # Vor der Behebung blieb „Bestätigt“ stehen — die Moderation war umgangen.
    assert zeilen[0]["status"] == "Angefragt"


def test_op_event_10_moderator_darf_bestaetigen(als_moderator, welt):
    from diakronos_app.api.kronos import event_crud

    zeilen = event_crud._normalize_ressourcen([
        {"ressource": "RES-BEAMER", "status": "Bestätigt"},
    ])
    assert zeilen[0]["status"] == "Bestätigt"


def test_op_event_10_termin_ressourcen_erscheinen_in_den_anfragen(client, als_moderator, welt):
    """OP-EVENT-10: eine „Angefragt“-Ressource am Termin wird moderierbar."""
    # ER-BEAMER ist im Fixture „Bestätigt“ — fuer diesen Test auf Angefragt setzen.
    welt.get(ElementRessource, "ER-BEAMER").status = "Angefragt"
    welt.commit()

    r = client.get(f"/api/method/{RES_MODUL}.get_anfragen")
    assert r.status_code == 200, r.text
    anfragen = r.json()["message"]["anfragen"]

    gespiegelt = [a for a in anfragen if a.get("quelle") == "termin"]
    assert gespiegelt, "Termin-Ressource muss als Anfrage auftauchen"
    a = gespiegelt[0]
    assert a["ressource"] == "RES-BEAMER"
    assert a["ressource_name"] == "Beamer"
    assert a["zweck"] == "Adventssingen"
    assert a["datum_von_fmt"]


def test_op_event_10_angefragte_termin_ressource_ist_weicher_hinweis(als_anna, welt):
    """Eine offene Termin-Ressource sperrt nicht hart, wird aber gemeldet."""
    from diakronos_app.api import ressourcen as R

    welt.get(ElementRessource, "ER-BEAMER").status = "Angefragt"
    welt.commit()

    # NACHT-EVENT liegt im Fixture bei heute + 10 Tage.
    start = (datetime.now() + timedelta(days=10)).replace(microsecond=0)
    konflikte = R._check_konflikte(
        "RES-BEAMER",
        start.strftime("%Y-%m-%d %H:%M:%S"),
        (start + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
    )
    assert konflikte["hinweise"], "offener Vorschlag muss als Hinweis erscheinen"


# ── OP-HANDY-12: kein rohes Praefix, keine Fremdtitel ──────────────────────


def test_op_handy_12_konfliktmeldung_ohne_rohpraefix_und_ohne_fremdtitel(als_anna, welt):
    from diakronos_app.api import ressourcen as R

    start = (datetime.now() + timedelta(days=10)).replace(microsecond=0)
    konflikte = R._check_konflikte(
        "RES-BEAMER",
        start.strftime("%Y-%m-%d %H:%M:%S"),
        (start + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
    )

    # Der fremde Kalender „Fremd-Intern“ darf seinen Titel „Teenykreis“ nicht zeigen.
    titel = {k["name"] for k in konflikte["kalender_konflikte"]}
    assert "Teenykreis" not in titel
    assert "Belegt" in titel

    meldung = R._konflikt_details(konflikte["hart"])
    # Vorher: „kalender: Teenykreis (…)“. Jetzt: lesbarer Satz.
    assert "kalender:" not in meldung
    assert "buchung:" not in meldung
    assert "Belegung durch" in meldung


def test_op_handy_12_kalenderkonflikt_hat_iso_grenzen(als_anna, welt):
    """Die Verfuegbarkeitsleiste braucht ISO-Zeitstempel (von/bis).

    P1-4b: `start` wird aus dem Fixture-Termin gelesen (nicht neu aus
    `datetime.now()` gerechnet) — sonst kippte der Vergleich um eine Sekunde,
    wenn zwischen Fixture-Aufbau und Test der Sekundenwechsel lag (Flake).
    """
    from diakronos_app.api import ressourcen as R

    start = welt.get(Element, "NACHT-EVENT").element_start
    konflikte = R._check_konflikte(
        "RES-BEAMER",
        start.strftime("%Y-%m-%d %H:%M:%S"),
        (start + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
    )
    k = konflikte["kalender_konflikte"][0]
    assert k["von"] == start.strftime("%Y-%m-%d %H:%M:%S")
    assert k["bis"] == (start + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")


# ── OP-HANDY-23: deutsche Datumsteile ──────────────────────────────────────


def test_op_handy_23_meine_buchungen_deutsches_datum(client, als_anna):
    from diakronos_app.api import ressourcen as R

    # 28.11.2026 ist ein Samstag.
    R._create("Ressourcen Buchung", {
        "ressource": "RES-RAUM", "zweck": "Test", "status": "Angefragt",
        "datum_von": datetime(2026, 11, 28, 9, 0),
        "datum_bis": datetime(2026, 11, 28, 11, 0),
        "gebucht_von": ANNA, "gebucht_von_name": "Anna Beispiel",
    })

    daten = client.get(f"/api/method/{RES_MODUL}.get_meine_buchungen").json()["message"]
    eintrag = next(d for d in daten if d["purpose"] == "Test")
    # Vorher: „Sat, 28. Nov 2026“ (Server-Sprache englisch).
    assert eintrag["date"] == "Sa, 28. Nov. 2026"


def test_op_handy_23_res_buchungen_deutscher_monat(client, als_anna):
    from diakronos_app.api import ressourcen as R

    R._create("Ressourcen Buchung", {
        "ressource": "RES-RAUM", "zweck": "Monat", "status": "Angefragt",
        "datum_von": datetime(2026, 11, 28, 9, 0),
        "datum_bis": datetime(2026, 11, 28, 11, 0),
        "gebucht_von": ANNA, "gebucht_von_name": "Anna Beispiel",
    })
    daten = client.get(f"/api/method/{RES_MODUL}.get_ressource_buchungen",
                       params={"ressource_id": "RES-RAUM"}).json()["message"]
    eintrag = next(d for d in daten if d["title"] == "Monat")
    assert eintrag["month"] == "Nov."


# ── OP-EVENT-14: Verschieben mit Zeitraum + Konfliktpruefung ────────────────


def test_op_event_14_verschieben_setzt_neuen_zeitraum(client, als_anna):
    from diakronos_app.api import ressourcen as R
    from diakronos_app.frappe_compat.query import get_doc

    set_user(ANNA)
    try:
        buchung_id = R._create("Ressourcen Buchung", {
            "ressource": "RES-RAUM", "zweck": "Bus", "status": "Angefragt",
            "datum_von": datetime(2031, 7, 26, 8, 0),
            "datum_bis": datetime(2031, 7, 26, 18, 0),
            "gebucht_von": ANNA, "gebucht_von_name": "Anna Beispiel",
        })
        r = client.post(f"/api/method/{RES_MODUL}.update_buchung", json={
            "buchung_id": buchung_id, "zweck": "Bus",
            "datum_von": "2031-07-26 08:00:00",
            "datum_bis": "2031-07-30 18:00:00",
        })
        assert r.status_code == 200, r.text
        doc = get_doc("Ressourcen Buchung", buchung_id)
        assert str(doc.datum_bis).startswith("2031-07-30")
    finally:
        set_user("Administrator")


def test_op_event_14_verschieben_blockt_harten_konflikt(client, als_anna):
    from diakronos_app.api import ressourcen as R

    set_user(ANNA)
    try:
        buchung_id = R._create("Ressourcen Buchung", {
            "ressource": "RES-BEAMER", "zweck": "Verschieben", "status": "Angefragt",
            "datum_von": datetime(2031, 8, 1, 8, 0),
            "datum_bis": datetime(2031, 8, 1, 9, 0),
            "gebucht_von": ANNA, "gebucht_von_name": "Anna Beispiel",
        })
        # Zielzeitraum = auf dem fremden Termin ELE-FREMD (RES-BEAMER).
        start = (datetime.now() + timedelta(days=10)).replace(microsecond=0)
        r = client.post(f"/api/method/{RES_MODUL}.update_buchung", json={
            "buchung_id": buchung_id, "zweck": "Verschieben",
            "datum_von": start.strftime("%Y-%m-%d %H:%M:%S"),
            "datum_bis": (start + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
        })
        assert r.status_code == 417
        assert "Verschiebung nicht möglich" in r.json()["message"]
    finally:
        set_user("Administrator")


def test_op_event_14_verschieben_ohne_datum_bleibt_erlaubt(client, als_anna):
    """Bestandsaufruf (nur Zweck/Notizen) muss weiter funktionieren."""
    from diakronos_app.api import ressourcen as R
    from diakronos_app.frappe_compat.query import get_doc

    set_user(ANNA)
    try:
        buchung_id = R._create("Ressourcen Buchung", {
            "ressource": "RES-RAUM", "zweck": "Alt", "status": "Angefragt",
            "datum_von": datetime(2031, 9, 1, 8, 0),
            "datum_bis": datetime(2031, 9, 1, 9, 0),
            "gebucht_von": ANNA, "gebucht_von_name": "Anna Beispiel",
        })
        r = client.post(f"/api/method/{RES_MODUL}.update_buchung", json={
            "buchung_id": buchung_id, "zweck": "Neu",
        })
        assert r.status_code == 200, r.text
        assert get_doc("Ressourcen Buchung", buchung_id).zweck == "Neu"
    finally:
        set_user("Administrator")


def test_op_event_14_halb_angegebener_zeitraum_wird_abgewiesen(client, als_anna):
    from diakronos_app.api import ressourcen as R

    set_user(ANNA)
    try:
        buchung_id = R._create("Ressourcen Buchung", {
            "ressource": "RES-RAUM", "zweck": "Halb", "status": "Angefragt",
            "datum_von": datetime(2031, 10, 1, 8, 0),
            "datum_bis": datetime(2031, 10, 1, 9, 0),
            "gebucht_von": ANNA, "gebucht_von_name": "Anna Beispiel",
        })
        r = client.post(f"/api/method/{RES_MODUL}.update_buchung", json={
            "buchung_id": buchung_id, "zweck": "Halb",
            "datum_von": "2031-10-02 08:00:00",
        })
        assert r.status_code == 417
        assert "gemeinsam" in r.json()["message"]
    finally:
        set_user("Administrator")


# ── OP-HANDY-4: der richtige Pfad ist erreichbar, der Tippfehler nicht ─────


def test_op_handy_4_decide_buchung_unter_korrektem_pfad_erreichbar():
    assert lookup(f"{RES_MODUL}.decide_buchung") is not None
    assert lookup("diakronos.diakronos.api.ressourcen.decide_buchung") is None
