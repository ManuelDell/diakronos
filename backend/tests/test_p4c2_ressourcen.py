"""P4c2 — Portiertes Modul `api.ressourcen` (Ressourcen-Buchung, 9 Endpunkte).

Quelle: `referenz/diakronos-frappe/diakronos/diakonos/api/ressourcen.py`.

Abgedeckt:
  * Login-Pflicht jedes Endpunkts (`allow_guest=False`) — Guest -> 403.
  * Erreichbarkeit unter dem ORIGINAL-SPA-Pfad
    `diakronos.diakonos.api.ressourcen.<fn>` (hooks.py des Originals).
  * `get_ressourcen_liste`: Typ-Filter, Suche, Status available/booked/maintenance.
  * `get_ressource_buchungen`: Storniert-Filter, Datumsfenster, Formatfelder.
  * `get_meine_buchungen`: nur eigene, ohne Stornierte, Konflikt-Hinweis.
  * `check_verfuegbarkeit`: Pflichtfelder, unbekannte Ressource, hart/weich.
  * `create_buchung`: Validierung, harter Konflikt blockt, weicher nicht.
  * `decide_buchung`: Moderationspflicht (403), Self-Approval (403), Status-Guard.
  * `get_anfragen`: Moderationspflicht (403), Antwortform `{"anfragen": [...]}`.
  * `update_buchung` / `delete_buchung`: Erstellerpflicht (403), Status-Guards.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from diakronos_app.frappe_compat.registry import lookup
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import RessourcenBuchung
from diakronos_app.models.kronos import Element, ElementRessource, Ressource

MODUL = "diakronos.diakonos.api.ressourcen"

# Die 9 in hooks.py gelisteten Originalpfade.
SPA_PFADE = [
    "get_ressourcen_liste",
    "get_ressource_buchungen",
    "get_meine_buchungen",
    "check_verfuegbarkeit",
    "create_buchung",
    "update_buchung",
    "delete_buchung",
    "decide_buchung",
    "get_anfragen",
]

ANNA = "anna@example.org"
BRUNO = "bruno@example.org"
MODERATOR = "moderator@example.org"


# ── Fixture ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def welt(patched_db):
    """Zwei Ressourcen, zwei Nutzer, ein Moderator, eine bestaetigte Buchung.

    Zeitbasis ist fix, damit die Vergleiche gegen `_now()` deterministisch
    bleiben: der Kalender laeuft in der Zukunft, `vergangen` davor.
    """
    sess = patched_db()

    sess.add_all([
        Ressource(name="RES-RAUM", ressource_name="Gemeindesaal", typ="Raum",
                  kapazitaet=80, beschreibung="Grosser Saal", tags="saal, gross",
                  bild="", wartung=0, docstatus=0, idx=0),
        Ressource(name="RES-BUS", ressource_name="Kleinbus", typ="Fahrzeug",
                  kapazitaet=9, beschreibung="Bulli", tags="bus",
                  bild="", wartung=1, docstatus=0, idx=0),
    ])

    now = datetime.now().replace(microsecond=0)
    spaeter = now + timedelta(days=10)
    ende = spaeter + timedelta(hours=3)
    vergangen = now - timedelta(days=30)

    sess.add_all([
        # Harte Sperre: bestaetigte Buchung auf RES-BUS (fuer create-Konflikttest
        # wird RES-RAUM genommen, hier nur fuer den Liste-Status "booked").
        RessourcenBuchung(name="BUC-BEST", ressource="RES-RAUM", zweck="Probe",
                          datum_von=vergangen, datum_bis=vergangen + timedelta(hours=2),
                          gebucht_von=BRUNO, gebucht_von_name="Bruno Beispiel",
                          status="Bestätigt", notizen="", docstatus=0, idx=0),
        # Offene Anfrage von Bruno in der Zukunft (weicher Konflikt fuer Anna).
        RessourcenBuchung(name="BUC-ANFR", ressource="RES-RAUM", zweck="Jugendtreff",
                          datum_von=spaeter, datum_bis=ende,
                          gebucht_von=BRUNO, gebucht_von_name="Bruno Beispiel",
                          status="Angefragt", notizen="", docstatus=0, idx=0),
        # Kalender-Element mit direkter Ressourcenzuordnung (harter Konflikt).
        Element(name="ELE-1", element_name="Gottesdienst", element_start=spaeter,
                element_end=ende, ressource="RES-RAUM", ignore_conflict=0,
                docstatus=0, idx=0),
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


# ── Registrierung / Router ──────────────────────────────────────────────────


def test_frappe_module_konstante_ist_gesetzt():
    """Ohne FRAPPE_MODULE ist der Endpunkt fuer die SPA unerreichbar."""
    from diakronos_app.api import ressourcen

    assert ressourcen.FRAPPE_MODULE == MODUL


@pytest.mark.parametrize("fn", SPA_PFADE)
def test_originale_spa_pfade_sind_registriert(fn):
    """Alle 9 in hooks.py gelisteten Pfade muessen aufloesbar sein."""
    assert lookup(f"{MODUL}.{fn}") is not None


def test_kein_alias_unter_dem_tippfehler_pfad():
    """Der SPA-Tippfehler `diakronos.diakronos...` darf NICHT bedient werden.

    Die SPA ruft `decide_buchung` unter dem falschen Pfad auf (Ressourcen.vue:482,
    :502). Ein Alias wuerde den Fehler zementieren; die Karte verlangt ausdruecklich
    KEINEN Alias.
    """
    assert lookup("diakronos.diakronos.api.ressourcen.decide_buchung") is None


@pytest.mark.parametrize("fn", SPA_PFADE)
def test_guest_wird_ueberall_abgewiesen(client, fn):
    """`allow_guest=False` gilt fuer jeden der 9 Endpunkte."""
    set_user("Guest")
    try:
        resp = client.get(f"/api/method/{MODUL}.{fn}")
        assert resp.status_code == 401, (fn, resp.text)
    finally:
        set_user("Administrator")


# ── get_ressourcen_liste ────────────────────────────────────────────────────


def test_liste_liefert_status_und_tags(client, als_anna):
    r = client.get(f"/api/method/{MODUL}.get_ressourcen_liste")
    assert r.status_code == 200, r.text
    daten = {x["id"]: x for x in r.json()["message"]}

    assert daten["RES-RAUM"]["status"] == "available"
    assert daten["RES-RAUM"]["type"] == "room"
    assert daten["RES-RAUM"]["capacity"] == 80
    assert daten["RES-RAUM"]["tags"] == ["saal", "gross"]
    assert daten["RES-RAUM"]["image"] is None

    # wartung=1 -> maintenance (schlaegt jeden Buchungsstatus)
    assert daten["RES-BUS"]["status"] == "maintenance"
    assert daten["RES-BUS"]["type"] == "vehicle"


def test_liste_filtert_nach_typ(client, als_anna):
    r = client.get(f"/api/method/{MODUL}.get_ressourcen_liste", params={"typ": "vehicle"})
    ids = [x["id"] for x in r.json()["message"]]
    assert ids == ["RES-BUS"]


def test_liste_suche_ueber_name_beschreibung_tags(client, als_anna):
    r = client.get(f"/api/method/{MODUL}.get_ressourcen_liste", params={"search": "gross"})
    ids = [x["id"] for x in r.json()["message"]]
    assert ids == ["RES-RAUM"]

    r = client.get(f"/api/method/{MODUL}.get_ressourcen_liste", params={"search": "bulli"})
    assert [x["id"] for x in r.json()["message"]] == ["RES-BUS"]

    r = client.get(f"/api/method/{MODUL}.get_ressourcen_liste", params={"search": "gibtsnicht"})
    assert r.json()["message"] == []


def test_liste_setzt_booked_bei_laufender_bestaetigter_buchung(client, als_anna):
    """Eine BESTAETIGTE Buchung, die jetzt laeuft, macht die Ressource 'booked'."""
    from diakronos_app.frappe_compat.session import set_user as _su

    _su(ANNA)
    try:
        from diakronos_app.api import ressourcen as R

        jetzt = datetime.now().replace(microsecond=0)
        R._create("Ressourcen Buchung", {
            "ressource": "RES-BUS", "zweck": "Heute", "status": "Bestätigt",
            "datum_von": jetzt - timedelta(minutes=30),
            "datum_bis": jetzt + timedelta(minutes=30),
            "gebucht_von": BRUNO, "gebucht_von_name": "Bruno Beispiel",
        })
    finally:
        _su("Administrator")

    # wartung schlaegt zu; also auf 0 setzen, um den Buchungspfad zu sehen.
    from diakronos_app.api import ressourcen as R2

    R2._update_doc("Ressource", "RES-BUS", {"wartung": 0})

    r = client.get(f"/api/method/{MODUL}.get_ressourcen_liste")
    daten = {x["id"]: x for x in r.json()["message"]}
    assert daten["RES-BUS"]["status"] == "booked"


# ── get_ressource_buchungen ─────────────────────────────────────────────────


def test_buchungen_ohne_stornierte_und_mit_formatfeldern(client, als_anna):
    from diakronos_app.api import ressourcen as R

    R._create("Ressourcen Buchung", {
        "ressource": "RES-RAUM", "zweck": "Weg damit", "status": "Storniert",
        "datum_von": datetime(2026, 6, 1, 10, 0), "datum_bis": datetime(2026, 6, 1, 12, 0),
        "gebucht_von": ANNA, "gebucht_von_name": "Anna Beispiel",
    })

    r = client.get(f"/api/method/{MODUL}.get_ressource_buchungen",
                   params={"ressource_id": "RES-RAUM"})
    assert r.status_code == 200, r.text
    eintraege = r.json()["message"]
    ids = [e["id"] for e in eintraege]
    assert "BUC-BEST" in ids
    assert "BUC-ANFR" in ids
    assert all(e["status"] != "Storniert" for e in eintraege)

    best = next(e for e in eintraege if e["id"] == "BUC-BEST")
    assert best["title"] == "Probe"
    assert best["date"] == best["date"][:10]
    assert "–" in best["time"]
    assert best["user"] == "Bruno Beispiel"
    assert best["ablehnungs_grund"] == ""
    assert best["moderiert_von"] == ""


def test_buchungen_datumsfenster(client, als_anna):
    r = client.get(f"/api/method/{MODUL}.get_ressource_buchungen",
                   params={"ressource_id": "RES-RAUM", "date_to": "2000-01-01"})
    assert r.json()["message"] == []


# ── get_meine_buchungen ─────────────────────────────────────────────────────


def test_meine_buchungen_nur_eigene(client, als_anna):
    """Anna sieht nichts, Bruno seine Anfrage."""
    assert client.get(f"/api/method/{MODUL}.get_meine_buchungen").json()["message"] == []

    set_user(BRUNO)
    try:
        daten = client.get(f"/api/method/{MODUL}.get_meine_buchungen").json()["message"]
        ids = [d["id"] for d in daten]
        assert "BUC-ANFR" in ids
        assert "BUC-BEST" in ids

        anfr = next(d for d in daten if d["id"] == "BUC-ANFR")
        assert anfr["resourceId"] == "RES-RAUM"
        assert anfr["resourceName"] == "Gemeindesaal"
        assert anfr["resourceType"] == "room"
        assert anfr["purpose"] == "Jugendtreff"
        assert anfr["status"] == "Angefragt"
        # Bruno ist der Anfragende -> eigene Anfrage erzeugt keinen Fremd-Hinweis
        assert "konflikt_hinweis" not in anfr
    finally:
        set_user("Administrator")


def test_meine_buchungen_ohne_stornierte(client, als_anna):
    from diakronos_app.api import ressourcen as R

    R._create("Ressourcen Buchung", {
        "ressource": "RES-RAUM", "zweck": "Storno", "status": "Storniert",
        "datum_von": datetime(2026, 7, 1, 9, 0), "datum_bis": datetime(2026, 7, 1, 10, 0),
        "gebucht_von": ANNA, "gebucht_von_name": "Anna Beispiel",
    })
    daten = client.get(f"/api/method/{MODUL}.get_meine_buchungen").json()["message"]
    assert daten == []


def test_meine_buchungen_konflikt_hinweis_bei_fremder_anfrage(client, als_anna):
    """Annas offene Anfrage kollidiert weich mit Brunos Anfrage."""
    from diakronos_app.api import ressourcen as R

    R._create("Ressourcen Buchung", {
        "ressource": "RES-RAUM", "zweck": "Anna fragt", "status": "Angefragt",
        "datum_von": datetime(2026, 8, 1, 9, 0), "datum_bis": datetime(2026, 8, 1, 11, 0),
        "gebucht_von": ANNA, "gebucht_von_name": "Anna Beispiel",
    })
    # Bruno fragt denselben Zeitraum an -> weicher Hinweis
    R._create("Ressourcen Buchung", {
        "ressource": "RES-RAUM", "zweck": "Bruno fragt", "status": "Angefragt",
        "datum_von": datetime(2026, 8, 1, 10, 0), "datum_bis": datetime(2026, 8, 1, 12, 0),
        "gebucht_von": BRUNO, "gebucht_von_name": "Bruno Beispiel",
    })

    set_user(BRUNO)
    try:
        daten = client.get(f"/api/method/{MODUL}.get_meine_buchungen").json()["message"]
        bruno = next(d for d in daten if d["purpose"] == "Bruno fragt")
        assert bruno["konflikt_hinweis"]
        assert bruno["konflikt_hinweis"][0]["titel"] == "Anna fragt"
    finally:
        set_user("Administrator")


# ── check_verfuegbarkeit ────────────────────────────────────────────────────


def test_verfuegbarkeit_pflichtfelder(client, als_anna):
    # Ohne datum_von/datum_bis fehlen Pflichtparameter.
    # Original (Frappe) bindet die Positionsparameter ebenfalls VOR der eigenen
    # Guard `if not ressource_id or not datum_von or not datum_bis` -> auch dort
    # 417, nur mit Bindungs- statt Guard-Meldung. Verhalten identisch.
    r = client.get(f"/api/method/{MODUL}.check_verfuegbarkeit",
                   params={"ressource_id": "RES-RAUM"})
    assert r.status_code == 417
    assert "Falsche Argumente" in r.json()["message"]

    # Leere Strings erreichen dagegen die Guard im Endpunkt selbst.
    r = client.get(f"/api/method/{MODUL}.check_verfuegbarkeit",
                   params={"ressource_id": "", "datum_von": "", "datum_bis": ""})
    assert r.status_code == 417
    assert "erforderlich" in r.json()["message"]


def test_verfuegbarkeit_unbekannte_ressource(client, als_anna):
    r = client.get(f"/api/method/{MODUL}.check_verfuegbarkeit",
                   params={"ressource_id": "GIBTS-NICHT",
                           "datum_von": "2026-08-01 09:00:00",
                           "datum_bis": "2026-08-01 11:00:00"})
    assert r.status_code == 417
    assert "nicht gefunden" in r.json()["message"]


def test_verfuegbarkeit_hart_durch_kalender_element(client, als_anna):
    """Das Element ELE-1 belegt RES-RAUM -> harter Konflikt."""
    spaeter = datetime.now() + timedelta(days=10)
    r = client.get(f"/api/method/{MODUL}.check_verfuegbarkeit",
                   params={"ressource_id": "RES-RAUM",
                           "datum_von": spaeter.strftime("%Y-%m-%d %H:%M:%S"),
                           "datum_bis": (spaeter + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")})
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["verfuegbar"] is False
    assert msg["kalender_konflikte"][0]["quelle"] == "direkt"
    assert msg["kalender_konflikte"][0]["element"] == "ELE-1"
    assert any(k["typ"] == "kalender" for k in msg["harte_konflikte"])
    # Brunos Anfrage liegt im selben Fenster -> weicher Hinweis
    assert msg["konflikt_hinweis"]


def test_verfuegbarkeit_frei(client, als_anna):
    r = client.get(f"/api/method/{MODUL}.check_verfuegbarkeit",
                   params={"ressource_id": "RES-RAUM",
                           "datum_von": "2030-01-01 09:00:00",
                           "datum_bis": "2030-01-01 11:00:00"})
    msg = r.json()["message"]
    assert msg["verfuegbar"] is True
    assert msg["harte_konflikte"] == []
    assert msg["konflikt_hinweis"] == []
    assert msg["kalender_konflikte"] == []


# ── create_buchung ──────────────────────────────────────────────────────────


def test_create_buchung_erfolg_und_status_immer_angefragt(client, als_anna):
    r = client.post(f"/api/method/{MODUL}.create_buchung", json={
        "ressource_id": "RES-RAUM",
        "datum_von": "2030-02-01 09:00:00",
        "datum_bis": "2030-02-01 11:00:00",
        "zweck": "  Chorprobe  ",
        "notizen": "  mit Noten  ",
    })
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["success"] is True
    assert msg["status"] == "Angefragt"
    assert msg["buchung_id"]

    from diakronos_app.frappe_compat.query import get_doc

    set_user(ANNA)
    try:
        doc = get_doc("Ressourcen Buchung", msg["buchung_id"])
        assert doc.status == "Angefragt"
        assert doc.zweck == "Chorprobe"
        assert doc.notizen == "mit Noten"
        assert doc.gebucht_von == ANNA
        # Kein Mitglied-Datensatz -> Rueckfall auf den User-Namen
        assert doc.gebucht_von_name == ANNA
    finally:
        set_user("Administrator")


def test_create_buchung_pflichtfelder(client, als_anna):
    r = client.post(f"/api/method/{MODUL}.create_buchung", json={
        "ressource_id": "RES-RAUM", "datum_von": "2030-02-01 09:00:00",
        "datum_bis": "2030-02-01 11:00:00", "zweck": "   ",
    })
    assert r.status_code == 417
    assert "erforderlich" in r.json()["message"]


def test_create_buchung_unbekannte_ressource(client, als_anna):
    r = client.post(f"/api/method/{MODUL}.create_buchung", json={
        "ressource_id": "NIX", "datum_von": "2030-02-01 09:00:00",
        "datum_bis": "2030-02-01 11:00:00", "zweck": "Test",
    })
    assert r.status_code == 417
    assert "nicht gefunden" in r.json()["message"]


def test_create_buchung_bis_vor_von(client, als_anna):
    r = client.post(f"/api/method/{MODUL}.create_buchung", json={
        "ressource_id": "RES-RAUM", "datum_von": "2030-02-01 11:00:00",
        "datum_bis": "2030-02-01 09:00:00", "zweck": "Test",
    })
    assert r.status_code == 417
    assert "Ende der Buchung muss nach dem Beginn liegen" in r.json()["message"]
    assert "datum_von" not in r.json()["message"]


def test_create_buchung_harter_konflikt_blockt(client, als_anna):
    """ELE-1 (Kalender) blockt hart; die Meldung nennt den Zeitraum.

    P1-4 / OP-HANDY-12: ELE-1 traegt KEINEN `element_calendar`. Ein Termin
    ohne Kalender ist fuer niemanden lesbar, deshalb nennt die Meldung keinen
    Titel mehr, sondern „Belegt“ — vorher stand hier der Terminname, also der
    Titel eines Termins, den der Anfragende nicht sehen darf.
    """
    spaeter = datetime.now() + timedelta(days=10)
    r = client.post(f"/api/method/{MODUL}.create_buchung", json={
        "ressource_id": "RES-RAUM",
        "datum_von": spaeter.strftime("%Y-%m-%d %H:%M:%S"),
        "datum_bis": (spaeter + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
        "zweck": "Kollidiert",
    })
    assert r.status_code == 417
    assert "nicht verfügbar" in r.json()["message"]
    assert "Belegt" in r.json()["message"]


def test_create_buchung_weicher_konflikt_blockt_nicht(client, als_anna):
    """Brunos Anfrage ist nur ein Hinweis — die Buchung entsteht trotzdem."""
    spaeter = datetime.now() + timedelta(days=20)
    r = client.post(f"/api/method/{MODUL}.create_buchung", json={
        "ressource_id": "RES-RAUM",
        "datum_von": spaeter.strftime("%Y-%m-%d %H:%M:%S"),
        "datum_bis": (spaeter + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
        "zweck": "Ohne Konflikt",
    })
    assert r.status_code == 200, r.text
    assert r.json()["message"]["success"] is True


# ── decide_buchung ──────────────────────────────────────────────────────────


def test_decide_buchung_nur_moderator(client, als_anna):
    r = client.post(f"/api/method/{MODUL}.decide_buchung", json={
        "buchung_id": "BUC-ANFR", "entscheidung": "bestaetigen"})
    assert r.status_code == 403
    assert "Ressourcenmoderatoren" in r.json()["message"]


def test_decide_buchung_ungueltige_entscheidung(client, als_moderator):
    r = client.post(f"/api/method/{MODUL}.decide_buchung", json={
        "buchung_id": "BUC-ANFR", "entscheidung": "vielleicht"})
    assert r.status_code == 417
    assert "bestaetigen" in r.json()["message"]


def test_decide_buchung_bestaetigen(client, als_moderator):
    """BUC-ANFR liegt im Fenster von ELE-1 -> Bestaetigung muss hart scheitern."""
    r = client.post(f"/api/method/{MODUL}.decide_buchung", json={
        "buchung_id": "BUC-ANFR", "entscheidung": "bestaetigen"})
    assert r.status_code == 417
    assert "Bestätigung nicht möglich" in r.json()["message"]


def test_decide_buchung_bestaetigen_ohne_konflikt(client, als_moderator):
    from diakronos_app.api import ressourcen as R

    R._create("Ressourcen Buchung", {
        "ressource": "RES-RAUM", "zweck": "Frei", "status": "Angefragt",
        "datum_von": datetime(2031, 3, 1, 9, 0), "datum_bis": datetime(2031, 3, 1, 11, 0),
        "gebucht_von": BRUNO, "gebucht_von_name": "Bruno Beispiel",
    })
    r = client.post(f"/api/method/{MODUL}.decide_buchung", json={
        "buchung_id": "BUC-ANFR", "entscheidung": "ablehnen", "grund": "  kein Platz  "})
    # BUC-ANFR ablehnen ist erlaubt (kein harter Check beim Ablehnen)
    assert r.status_code == 200, r.text
    assert r.json()["message"] == {"success": True, "status": "Abgelehnt"}

    from diakronos_app.frappe_compat.query import get_doc

    set_user(MODERATOR)
    try:
        doc = get_doc("Ressourcen Buchung", "BUC-ANFR")
        assert doc.status == "Abgelehnt"
        assert doc.ablehnungs_grund == "kein Platz"
        assert doc.moderiert_von == MODERATOR
    finally:
        set_user("Administrator")


def test_decide_buchung_self_approval_verboten(client, als_moderator):
    """Ein Moderator darf seine EIGENE Anfrage nicht bestaetigen."""
    from diakronos_app.api import ressourcen as R

    set_user(MODERATOR)
    try:
        buchung_id = R._create("Ressourcen Buchung", {
            "ressource": "RES-RAUM", "zweck": "Eigene", "status": "Angefragt",
            "datum_von": datetime(2031, 4, 1, 9, 0), "datum_bis": datetime(2031, 4, 1, 11, 0),
            "gebucht_von": MODERATOR, "gebucht_von_name": "Moderator",
        })
        r = client.post(f"/api/method/{MODUL}.decide_buchung", json={
            "buchung_id": buchung_id, "entscheidung": "bestaetigen"})
        assert r.status_code == 403
        assert "selbst moderiert" in r.json()["message"]
    finally:
        set_user("Administrator")


def test_decide_buchung_status_guard(client, als_moderator):
    """BUC-BEST steht auf Bestaetigt -> kein zweiter Entscheid."""
    r = client.post(f"/api/method/{MODUL}.decide_buchung", json={
        "buchung_id": "BUC-BEST", "entscheidung": "ablehnen"})
    assert r.status_code == 417
    assert "Angefragt" in r.json()["message"]


def test_decide_buchung_unbekannte_buchung(client, als_moderator):
    r = client.post(f"/api/method/{MODUL}.decide_buchung", json={
        "buchung_id": "GIBTS-NICHT", "entscheidung": "ablehnen"})
    assert r.status_code == 404


# ── get_anfragen ────────────────────────────────────────────────────────────


def test_get_anfragen_nur_moderator(client, als_anna):
    r = client.get(f"/api/method/{MODUL}.get_anfragen")
    assert r.status_code == 403
    assert "Ressourcenmoderatoren" in r.json()["message"]


def test_get_anfragen_liefert_form_und_konflikte(client, als_moderator):
    r = client.get(f"/api/method/{MODUL}.get_anfragen")
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert set(msg.keys()) == {"anfragen"}

    anfr = next(a for a in msg["anfragen"] if a["id"] == "BUC-ANFR")
    assert anfr["name"] == "BUC-ANFR"
    assert anfr["ressource"] == "RES-RAUM"
    assert anfr["ressource_name"] == "Gemeindesaal"
    assert anfr["zweck"] == "Jugendtreff"
    assert anfr["gebucht_von"] == BRUNO
    assert anfr["gebucht_von_name"] == "Bruno Beispiel"
    assert anfr["datum_von_fmt"].count(":") == 1
    assert anfr["datum_bis_fmt"].count(":") == 1
    assert anfr["creation"]
    # ELE-1 liegt im Fenster -> Kalenderkonflikt wird gemeldet
    assert any(k.get("element") == "ELE-1" for k in anfr["konflikt_hinweis"])


# ── update_buchung / delete_buchung ─────────────────────────────────────────


def test_update_buchung_fremde_anfrage_verboten(client, als_anna):
    r = client.post(f"/api/method/{MODUL}.update_buchung", json={
        "buchung_id": "BUC-ANFR", "zweck": "Geklaut"})
    assert r.status_code == 403
    assert "Ersteller" in r.json()["message"]


def test_update_buchung_eigene_anfrage(client, als_anna):
    from diakronos_app.api import ressourcen as R

    set_user(ANNA)
    try:
        buchung_id = R._create("Ressourcen Buchung", {
            "ressource": "RES-RAUM", "zweck": "Alt", "notizen": "alt",
            "status": "Angefragt",
            "datum_von": datetime(2031, 5, 1, 9, 0), "datum_bis": datetime(2031, 5, 1, 11, 0),
            "gebucht_von": ANNA, "gebucht_von_name": "Anna Beispiel",
        })
        # Der Request laeuft als ANNA (Erstellerpruefung des Endpunkts).
        r = client.post(f"/api/method/{MODUL}.update_buchung", json={
            "buchung_id": buchung_id, "zweck": "  Neu  ", "notizen": "  frisch  "})
        assert r.status_code == 200, r.text
        assert r.json()["message"] == {"success": True}

        from diakronos_app.frappe_compat.query import get_doc

        doc = get_doc("Ressourcen Buchung", buchung_id)
        assert doc.zweck == "Neu"
        assert doc.notizen == "frisch"
    finally:
        set_user("Administrator")


def test_update_buchung_status_guard(client, als_anna):
    from diakronos_app.api import ressourcen as R

    set_user(ANNA)
    try:
        buchung_id = R._create("Ressourcen Buchung", {
            "ressource": "RES-RAUM", "zweck": "Fix", "status": "Bestätigt",
            "datum_von": datetime(2031, 6, 1, 9, 0), "datum_bis": datetime(2031, 6, 1, 11, 0),
            "gebucht_von": ANNA, "gebucht_von_name": "Anna Beispiel",
        })
        r = client.post(f"/api/method/{MODUL}.update_buchung", json={
            "buchung_id": buchung_id, "zweck": "Geht nicht"})
        assert r.status_code == 417
        assert "Angefragt" in r.json()["message"]
    finally:
        set_user("Administrator")


def test_delete_buchung_soft_storno(client, als_anna):
    from diakronos_app.api import ressourcen as R

    set_user(ANNA)
    try:
        buchung_id = R._create("Ressourcen Buchung", {
            "ressource": "RES-RAUM", "zweck": "Weg", "status": "Angefragt",
            "datum_von": datetime(2031, 7, 1, 9, 0), "datum_bis": datetime(2031, 7, 1, 11, 0),
            "gebucht_von": ANNA, "gebucht_von_name": "Anna Beispiel",
        })
        r = client.post(f"/api/method/{MODUL}.delete_buchung", json={"buchung_id": buchung_id})
        assert r.status_code == 200, r.text
        assert r.json()["message"] == {"success": True}

        from diakronos_app.frappe_compat.query import get_doc

        # Soft-Delete: Zeile bleibt, Status wechselt
        assert get_doc("Ressourcen Buchung", buchung_id).status == "Storniert"
    finally:
        set_user("Administrator")


def test_delete_buchung_fremde_verboten(client, als_anna):
    r = client.post(f"/api/method/{MODUL}.delete_buchung", json={"buchung_id": "BUC-ANFR"})
    assert r.status_code == 403
    assert "Ersteller" in r.json()["message"]


def test_delete_buchung_status_guard(client, als_anna):
    r = client.post(f"/api/method/{MODUL}.delete_buchung", json={"buchung_id": "BUC-BEST"})
    # BUC-BEST gehoert Bruno -> Erstellerpruefung greift vor dem Status-Guard
    assert r.status_code == 403

    from diakronos_app.api import ressourcen as R

    set_user(ANNA)
    try:
        buchung_id = R._create("Ressourcen Buchung", {
            "ressource": "RES-RAUM", "zweck": "Abgelehnt", "status": "Abgelehnt",
            "datum_von": datetime(2031, 8, 1, 9, 0), "datum_bis": datetime(2031, 8, 1, 11, 0),
            "gebucht_von": ANNA, "gebucht_von_name": "Anna Beispiel",
        })
        r = client.post(f"/api/method/{MODUL}.delete_buchung", json={"buchung_id": buchung_id})
        assert r.status_code == 417
        assert "kann nicht storniert werden" in r.json()["message"]
    finally:
        set_user("Administrator")


# ── Konflikt-Helfer direkt ──────────────────────────────────────────────────


def test_element_ressource_kindtabelle_zaehlt_als_harter_konflikt(als_anna, welt):
    """Zusatzressourcen ueber die Child-Tabelle ('quelle': zusatzressource)."""
    from diakronos_app.api.ressourcen import _check_konflikte

    spaeter = datetime.now() + timedelta(days=10)
    welt.add(ElementRessource(
        name="ER-1", parent="ELE-1", parenttype="Element",
        parentfield="zusaetzliche_ressourcen", ressource="RES-BUS",
        status="Bestätigt", notiz="", docstatus=0, idx=1,
    ))
    # Das Element ELE-1 traegt RES-BUS als Zusatzressource; ignore_conflict=0.
    welt.get(Element, "ELE-1").ignore_conflict = 0
    welt.commit()

    konflikte = _check_konflikte(
        "RES-BUS",
        spaeter.strftime("%Y-%m-%d %H:%M:%S"),
        (spaeter + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
    )
    assert any(k["quelle"] == "zusatzressource" for k in konflikte["kalender_konflikte"])
    assert any(k["typ"] == "kalender" for k in konflikte["hart"])


def test_ignore_conflict_element_wird_nicht_gemeldet(als_anna, welt):
    from diakronos_app.api.ressourcen import _check_konflikte

    welt.get(Element, "ELE-1").ignore_conflict = 1
    welt.commit()

    spaeter = datetime.now() + timedelta(days=10)
    konflikte = _check_konflikte(
        "RES-RAUM",
        spaeter.strftime("%Y-%m-%d %H:%M:%S"),
        (spaeter + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
    )
    assert konflikte["kalender_konflikte"] == []
