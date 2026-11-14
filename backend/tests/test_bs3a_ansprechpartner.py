"""BS-3a — Ansprechpartner mit Einwilligung (Backend + öffentliche Ausgabe).

Was hier festgehalten wird (Kartenvorgabe P1–P3 + TESTS)
=======================================================

  * **Ohne Einwilligung nie öffentlich** — auch nicht als Platzhalter und
    auch nicht mit Namen (Default AUS, G1).
  * **Der Widerruf wirkt sofort**: derselbe Aufruf liefert die Person vor und
    nach dem Widerruf unterschiedlich, ohne Zwischenspeicher.
  * **Foto nur bei Zustimmung**: ``foto_url`` und die Bild-Route antworten nur,
    wenn ``website_einwilligung`` UND ``website_einwilligung_foto`` gesetzt
    sind — die Bild-Route zusätzlich mit 404 (keine Auskunft, dass es die
    Person gibt).
  * **Der Admin kann eine Einwilligung NICHT setzen**: kein Verwaltungs-
    Endpunkt nimmt ein Einwilligungsfeld an (403, nichts geschrieben), und
    die Einwilligungs-Endpunkte verlangen KEINE Website-Rolle (sonst könnten
    normale Mitglieder nicht zustimmen) — sie lesen ausschliesslich das
    eigene Mitglied.
  * **Feld-Allowlist negativ geprüft**: keine E-Mail, kein Telefon, keine
    Adresse, kein Geburtstag, keine interne Personenkennung, keine
    Einwilligungsdaten in einer öffentlichen Antwort.
  * **Auswahl der Bereiche** durch die Verwaltung: Rollen wie BS-1a,
    delete-and-replace, unbekannte Funktion/Postfach -> 417, nichts
    geschrieben.
  * **DSGVO-Audit**: Erteilen und Widerruf erzeugen einen Eintrag in
    ``DSGVO Einwilligung`` (typ ``website``).

Netz (Kartenregel 11): ``patched_db`` (In-Memory-SQLite), ``fake_redis``;
kein Test greift auf ``settings.database_url`` zu, keiner spricht Primo an.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
from diakronos_app.frappe_compat import sitzungen  # noqa: F401 — Fixture-Naht
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import (
    Dienstbereich,
    DienstbereichVerantwortlicher,
    Gruppe,
    GruppeVerantwortlicher,
    Mitglied,
)
from diakronos_app.models.website_ansprechpartner import WebsiteAnsprechpartner
from diakronos_app.models.website_kontakt import WebsiteKontaktPostfach

MODUL = "diakronos_app.api.website"
PFAD_EINW_LESEN = f"{MODUL}.meine_einwilligung_lesen"
PFAD_EINW_SETZEN = f"{MODUL}.meine_einwilligung_setzen"
PFAD_BEREICHE_LESEN = f"{MODUL}.ansprechpartner_bereiche_lesen"
PFAD_BEREICHE_SETZEN = f"{MODUL}.ansprechpartner_bereiche_setzen"
PFAD_OEFFENTLICH = "website.oeffentlich"

ADMIN_MAIL = "verwaltung@example.org"
PERSON_MAIL = "anna@example.org"
FREMD_MAIL = "bert@example.org"

#: Diese Schlüssel dürfen in KEINER öffentlichen Antwort auftauchen.
VERBOTEN = frozenset(
    {
        "email",
        "telefonnummer",
        "telefon",
        "straße",
        "strasse",
        "nummer",
        "postleitzahl",
        "wohnort",
        "geburtstag",
        "mitglied",
        "user",
        "owner",
        "modified_by",
        "website_einwilligung",
        "website_einwilligung_am",
        "website_einwilligung_foto",
        "website_anzeigename",
    }
)


# ── Helfer ─────────────────────────────────────────────────────────────────


def _benutzer(sess, email: str, rollen=()) -> str:
    if sess.get(User, email) is None:
        sess.add(User(name=email, email=email, full_name=email, enabled=True))
        for idx, rolle in enumerate(rollen, start=1):
            sess.add(
                HasRole(
                    name=f"{email}-{rolle}",
                    parent=email,
                    parenttype="User",
                    parentfield="roles",
                    role=rolle,
                    docstatus=0,
                    idx=idx,
                )
            )
    return email


def _mitglied(sess, name: str, *, user: str | None = None, vorname="Anna",
              nachname="Beispiel", foto=None, einwilligung=False,
              foto_zustimmung=False, anzeigename=None) -> Mitglied:
    zeile = Mitglied(
        name=name,
        vorname=vorname,
        nachname=nachname,
        email=f"{name}@example.org",
        user=user,
        foto=foto,
        website_einwilligung=einwilligung,
        website_einwilligung_foto=foto_zustimmung,
        website_anzeigename=anzeigename,
    )
    sess.add(zeile)
    return zeile


@pytest.fixture()
def welt(patched_db):
    """Bestand: Verwaltung, zwei Mitglieder, ein Dienstbereich, eine Gruppe."""
    sess = patched_db()
    _benutzer(sess, ADMIN_MAIL, ("Website-Moderator",))
    _benutzer(sess, PERSON_MAIL, ("Mitglied",))
    _benutzer(sess, FREMD_MAIL, ("Mitglied",))

    _mitglied(sess, "anna", user=PERSON_MAIL, vorname="Anna", nachname="Beispiel")
    _mitglied(sess, "bert", user=FREMD_MAIL, vorname="Bert", nachname="Berger")

    sess.add(Dienstbereich(name="musik", ministry="Musik", sortierung=1))
    sess.add(
        Gruppe(
            name="chor",
            gruppenname="Chor",
            status="Aktiv",
            website_freigabe=True,
            website_slug="chor",
        )
    )
    # Verantwortlich: je Funktion genau eine Person.
    sess.add(
        DienstbereichVerantwortlicher(
            name="dbv-1", parent="musik", parenttype="Dienstbereich",
            parentfield="verantwortliche", user=PERSON_MAIL, idx=1,
        )
    )
    sess.add(
        GruppeVerantwortlicher(
            name="gv-1", parent="chor", parenttype="Gruppe",
            parentfield="verantwortliche", user=FREMD_MAIL, idx=1,
        )
    )
    # R-11d: die Leitung der Gruppe steht im EINEN Rechtesystem (wie nach der
    # Uebernahme r1 aus der Alt-Tabelle oben).
    from diakronos_app.models.rechte import RechteGruppenrolle

    sess.add(RechteGruppenrolle(gruppe="chor", benutzer=FREMD_MAIL, rolle="HV"))
    sess.add(
        WebsiteKontaktPostfach(
            slug="musik", bezeichnung="Musik", email="musik@example.org", aktiv=True
        )
    )
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def als_benutzer(welt, patched_db, fake_redis):
    """Factory: HTTP-Client mit echter Sitzung und CSRF-Token."""
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    erzeugt: list[TestClient] = []

    def _bauen(benutzer: str) -> TestClient:
        set_user(benutzer)
        sid, csrf = sitzungen.anlegen(benutzer)
        c = TestClient(app)
        c.__enter__()
        c.cookies.set("sid", sid)
        c.headers["X-Frappe-CSRF-Token"] = csrf
        erzeugt.append(c)
        return c

    yield _bauen
    for c in erzeugt:
        c.__exit__(None, None, None)


@pytest.fixture()
def gast(patched_db, fake_redis):
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    c = TestClient(app)
    c.__enter__()
    yield c
    c.__exit__(None, None, None)


def _oeffentlich(client, **params):
    return client.get(f"/api/method/{PFAD_OEFFENTLICH}.ansprechpartner", params=params)


def _schluessel(daten) -> set[str]:
    gefunden: set[str] = set()
    if isinstance(daten, dict):
        for k, v in daten.items():
            gefunden.add(str(k))
            gefunden |= _schluessel(v)
    elif isinstance(daten, list):
        for eintrag in daten:
            gefunden |= _schluessel(eintrag)
    return gefunden


# ── P3: ohne Einwilligung nie öffentlich ───────────────────────────────────


def test_ohne_einwilligung_erscheint_niemand(gast, welt):
    """Default AUS: ausgewählter Bereich, aber niemand hat zugestimmt -> leer."""
    welt.add(WebsiteAnsprechpartner(art="dienstbereich", funktion="musik",
                                    bezeichnung="", postfach=None, sortierung=1))
    welt.commit()
    antwort = _oeffentlich(gast)
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["message"] == [], "Person ohne Einwilligung ist öffentlich"


def test_keine_auswahl_keine_ausgabe(gast, welt):
    """Ohne Verwaltungsauswahl gibt es nichts — auch wenn jemand zugestimmt hat."""
    anna = welt.get(Mitglied, "anna")
    anna.website_einwilligung = True
    welt.commit()
    assert _oeffentlich(gast).json()["message"] == []


def test_mit_einwilligung_erscheint_genau_die_person(gast, welt):
    anna = welt.get(Mitglied, "anna")
    anna.website_einwilligung = True
    welt.add(WebsiteAnsprechpartner(art="dienstbereich", funktion="musik",
                                    bezeichnung="", postfach="musik", sortierung=1))
    welt.commit()

    daten = _oeffentlich(gast).json()["message"]
    assert len(daten) == 1, daten
    eintrag = daten[0]
    assert set(eintrag) == {"bereich", "funktion", "name", "foto_url", "postfach"}
    assert eintrag["bereich"] == "Musik"
    # Review BS-3a (Punkt 8): nach aussen geht die GESALZENE Kennung, nie der
    # interne Schluessel. Stabil (gleiche Funktion -> gleiche Kennung).
    from diakronos_app.website import oeffentlich_auswahl as auswahl

    assert eintrag["funktion"] == auswahl.oeffentliche_kennung(
        "funktion", "dienstbereich:musik"
    )
    assert "musik" not in eintrag["funktion"], "interne Funktionskennung nach außen"
    assert eintrag["name"] == "Anna Beispiel"
    assert eintrag["postfach"] == auswahl.oeffentliche_kennung("postfach", "musik")
    assert "musik" not in eintrag["postfach"], "interner Postfach-Slug nach außen"
    assert eintrag["foto_url"] == ""


def test_feld_allowlist_negativ(gast, welt):
    """EXPLIZIT NEGATIV: keine Personendaten, keine Kennungen, keine E-Mails."""
    anna = welt.get(Mitglied, "anna")
    anna.website_einwilligung = True
    anna.website_einwilligung_foto = True
    anna.telefonnummer = "0123 456789"
    anna.strasse = "Lindenweg 3"
    anna.postleitzahl = "12345"
    anna.wohnort = "Musterhausen"
    welt.add(WebsiteAnsprechpartner(art="dienstbereich", funktion="musik",
                                   bezeichnung="", postfach=None, sortierung=1))
    welt.commit()

    antwort = _oeffentlich(gast)
    roh = antwort.text
    daten = antwort.json()["message"]
    assert _schluessel(daten) & VERBOTEN == set(), "verbotener Schlüssel in der Antwort"
    assert "@example.org" not in roh, "E-Mail-Adresse in der öffentlichen Antwort"
    assert "0123 456789" not in roh
    assert "Lindenweg" not in roh
    assert "12345" not in roh
    assert "anna" not in roh, "interne Personenkennung in der Antwort"
    assert "einwilligung" not in roh.lower()
    # Review BS-3a (Punkt 8): auch die Funktions-/Postfach-Schluessel des
    # Bestands sind interne Kennungen. Nach aussen gehen nur gesalzene Werte.
    assert '"musik"' not in roh.replace("Musik", ""), "interne Funktionskennung"
    assert '"chor"' not in roh, "interne Funktionskennung"


def test_widerruf_wirkt_sofort(gast, welt):
    anna = welt.get(Mitglied, "anna")
    anna.website_einwilligung = True
    welt.add(WebsiteAnsprechpartner(art="dienstbereich", funktion="musik",
                                    bezeichnung="", postfach=None, sortierung=1))
    welt.commit()
    assert len(_oeffentlich(gast).json()["message"]) == 1

    anna.website_einwilligung = False
    welt.commit()
    assert _oeffentlich(gast).json()["message"] == [], "Widerruf wirkt nicht sofort"


def test_anzeigename_ersetzt_den_namen(gast, welt):
    anna = welt.get(Mitglied, "anna")
    anna.website_einwilligung = True
    anna.website_anzeigename = "Anna B."
    welt.add(WebsiteAnsprechpartner(art="dienstbereich", funktion="musik",
                                    bezeichnung="", postfach=None, sortierung=1))
    welt.commit()
    daten = _oeffentlich(gast).json()["message"]
    assert daten[0]["name"] == "Anna B."


def test_geloeschte_funktion_und_papierkorb_gruppe_fallen_heraus(gast, welt):
    """Eine Funktion, die es nicht mehr gibt (oder im Papierkorb), zeigt nichts."""
    from datetime import datetime

    bert = welt.get(Mitglied, "bert")
    bert.website_einwilligung = True
    welt.get(Gruppe, "chor").geloescht_am = datetime(2026, 11, 1, 12, 0, 0)
    welt.add(WebsiteAnsprechpartner(art="gruppe", funktion="chor",
                                    bezeichnung="", postfach=None, sortierung=2))
    welt.add(WebsiteAnsprechpartner(art="dienstbereich", funktion="fort",
                                    bezeichnung="", postfach=None, sortierung=3))
    welt.commit()
    assert _oeffentlich(gast).json()["message"] == []


def test_bereich_filter(gast, welt):
    anna = welt.get(Mitglied, "anna")
    anna.website_einwilligung = True
    bert = welt.get(Mitglied, "bert")
    bert.website_einwilligung = True
    welt.add(WebsiteAnsprechpartner(art="dienstbereich", funktion="musik",
                                    bezeichnung="", postfach=None, sortierung=1))
    welt.add(WebsiteAnsprechpartner(art="gruppe", funktion="chor",
                                    bezeichnung="", postfach=None, sortierung=2))
    welt.commit()

    alle = _oeffentlich(gast).json()["message"]
    assert [e["bereich"] for e in alle] == ["Musik", "Chor"]

    nur = _oeffentlich(gast, bereich="musik").json()["message"]
    assert [e["bereich"] for e in nur] == ["Musik"]


# ── Foto nur bei Zustimmung ────────────────────────────────────────────────


def test_foto_nur_mit_eigener_foto_zustimmung(gast, welt):
    anna = welt.get(Mitglied, "anna")
    anna.website_einwilligung = True
    anna.foto = "/files/anna.png"
    welt.add(WebsiteAnsprechpartner(art="dienstbereich", funktion="musik",
                                    bezeichnung="", postfach=None, sortierung=1))
    welt.commit()
    eintrag = _oeffentlich(gast).json()["message"][0]
    assert eintrag["foto_url"] == "", "Foto ohne Foto-Zustimmung wird verlinkt"

    anna.website_einwilligung_foto = True
    welt.commit()
    eintrag = _oeffentlich(gast).json()["message"][0]
    assert eintrag["foto_url"].startswith("/website/bild/person/"), eintrag["foto_url"]
    # Die Adresse enthält NICHT die interne Personenkennung.
    assert "anna" not in eintrag["foto_url"]


def test_bild_route_person_nur_mit_einwilligung(gast, welt, tmp_path):
    """Bild-Route: 404 ohne Einwilligung/ Foto-Zustimmung/ Bild."""
    from diakronos_app import files as dateien

    anna = welt.get(Mitglied, "anna")
    anna.website_einwilligung = True
    anna.foto = "anna.png"
    welt.add(WebsiteAnsprechpartner(art="dienstbereich", funktion="musik",
                                    bezeichnung="", postfach=None, sortierung=1))
    welt.commit()

    from diakronos_app.website import oeffentlich_auswahl as auswahl

    kennung = auswahl.oeffentliche_kennung("person", "anna")
    antwort = gast.get(f"/website/bild/person/{kennung}")
    assert antwort.status_code == 404, "Bild ohne Foto-Zustimmung ausgeliefert"

    # Ohne Einwilligung ebenfalls 404 — auch wenn die Foto-Zustimmung steht.
    anna.website_einwilligung = False
    anna.website_einwilligung_foto = True
    welt.commit()
    assert gast.get(f"/website/bild/person/{kennung}").status_code == 404


# ── P1: die Person selbst ──────────────────────────────────────────────────


def test_eigene_einwilligung_lesen_und_setzen(als_benutzer, welt):
    client = als_benutzer(PERSON_MAIL)
    antwort = client.get(f"/api/method/{PFAD_EINW_LESEN}")
    assert antwort.status_code == 200, antwort.text
    stand = antwort.json()["message"]
    assert stand["website_einwilligung"] is False
    assert stand["website_einwilligung_am"] is None
    assert stand["oeffentlich"] is False

    gesetzt = client.post(f"/api/method/{PFAD_EINW_SETZEN}",
                          json={"einwilligung": True, "foto": True,
                                "anzeigename": "Anna B."})
    assert gesetzt.status_code == 200, gesetzt.text
    stand = gesetzt.json()["message"]
    assert stand["website_einwilligung"] is True
    assert stand["website_einwilligung_am"], "Zeitstempel fehlt"
    assert stand["website_einwilligung_foto"] is True
    assert stand["website_anzeigename"] == "Anna B."
    assert stand["foto_erlaubt"] is True
    assert stand["oeffentlich"] is True

    # Widerruf: alles aus, Zeitstempel weg, Foto-Zustimmung mit widerrufen.
    widerruf = client.post(f"/api/method/{PFAD_EINW_SETZEN}",
                           json={"einwilligung": False})
    assert widerruf.status_code == 200, widerruf.text
    stand = widerruf.json()["message"]
    assert stand["website_einwilligung"] is False
    assert stand["website_einwilligung_am"] is None
    assert stand["website_einwilligung_foto"] is False
    assert stand["oeffentlich"] is False


def test_foto_ohne_einwilligung_wird_abgelehnt(als_benutzer, welt):
    client = als_benutzer(PERSON_MAIL)
    antwort = client.post(f"/api/method/{PFAD_EINW_SETZEN}", json={"foto": True})
    assert antwort.status_code == 417, antwort.text
    assert welt.get(Mitglied, "anna").website_einwilligung_foto is False


def test_einwilligung_setzen_braucht_keine_website_rolle(als_benutzer, welt):
    """Ein normales Mitglied (Rolle „Mitglied") darf zustimmen."""
    client = als_benutzer(PERSON_MAIL)
    antwort = client.post(f"/api/method/{PFAD_EINW_SETZEN}", json={"einwilligung": True})
    assert antwort.status_code == 200, antwort.text


def test_einwilligung_ohne_csrf_wird_abgewiesen(welt, patched_db, fake_redis):
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    set_user(PERSON_MAIL)
    sid, _csrf = sitzungen.anlegen(PERSON_MAIL)
    c = TestClient(app)
    with c:
        c.cookies.set("sid", sid)
        antwort = c.post(f"/api/method/{PFAD_EINW_SETZEN}", json={"einwilligung": True})
    assert antwort.status_code == 417, antwort.text
    assert welt.get(Mitglied, "anna").website_einwilligung is False


def test_einwilligung_ist_nur_die_eigene(als_benutzer, welt):
    """Jeder sieht und ändert NUR sein eigenes Mitglied — es gibt keinen Parameter."""
    anna = welt.get(Mitglied, "anna")
    anna.website_einwilligung = True
    welt.commit()

    client = als_benutzer(FREMD_MAIL)
    stand = client.get(f"/api/method/{PFAD_EINW_LESEN}").json()["message"]
    assert stand["website_einwilligung"] is False, "fremde Einwilligung sichtbar"

    # Ein Versuch, `mitglied` mitzuschicken, wird NICHT angenommen (kein
    # Parameter) — er darf die fremde Zeile nicht ändern.
    client.post(f"/api/method/{PFAD_EINW_SETZEN}",
                json={"einwilligung": True, "mitglied": "anna"})
    welt.expire_all()
    assert welt.get(Mitglied, "bert").website_einwilligung is True
    assert welt.get(Mitglied, "anna").website_einwilligung is True  # unverändert


def test_dsgvo_eintraege_bei_erteilen_und_widerruf(als_benutzer, welt):
    # Der Name kommt aus dem MODUL-ATTRIBUT (nicht per `from … import` im
    # Funktionskörper): SQLAlchemy haengt an `diakronos_app.models.diakonos`
    # einen clsregistry-Proxy, auf dem ein spaeterer Import scheitert.
    from diakronos_app.models import DSGVOEinwilligung

    client = als_benutzer(PERSON_MAIL)
    client.post(f"/api/method/{PFAD_EINW_SETZEN}", json={"einwilligung": True})
    client.post(f"/api/method/{PFAD_EINW_SETZEN}", json={"einwilligung": False})

    welt.expire_all()
    eintraege = welt.query(DSGVOEinwilligung).filter(
        DSGVOEinwilligung.mitglied == "anna"
    ).all()
    # NACHTRAG 2 (MITTEL 3): je geaendertem Feld genau EIN Eintrag.
    #   Erteilen  -> website/erteilt (das Foto ist dabei NICHT mitgeschickt,
    #                der Aufruf setzt es nicht)
    #   Widerruf  -> website/widerrufen UND website_foto/widerrufen (der
    #                Widerruf setzt die Foto-Zustimmung zurueck — eine eigene
    #                Aenderung, die (nur noch) EINMAL protokolliert wird).
    # Die alte elif-Kette protokollierte den Foto-Widerruf gar nicht bzw. den
    # Anzeigenamen doppelt — siehe `test_bs3a_nachtrag2.py`.
    assert sorted((str(e.typ), str(e.aktion)) for e in eintraege) == [
        ("website", "erteilt"),
        ("website", "widerrufen"),
        ("website_foto", "widerrufen"),
    ], [(e.typ, e.aktion) for e in eintraege]


# ── P2: Verwaltung kann die Einwilligung NICHT setzen ──────────────────────


def test_admin_kann_einwilligung_nicht_setzen(als_benutzer, welt):
    client = als_benutzer(ADMIN_MAIL)
    antwort = client.post(
        f"/api/method/{PFAD_BEREICHE_SETZEN}",
        json={
            "bereiche": [
                {"art": "dienstbereich", "funktion": "musik", "postfach": ""},
            ],
            "website_einwilligung": True,
        },
    )
    assert antwort.status_code == 403, antwort.text
    welt.expire_all()
    assert welt.query(WebsiteAnsprechpartner).count() == 0, "trotz Ablehnung geschrieben"
    assert welt.get(Mitglied, "anna").website_einwilligung is False


def test_kein_verwaltungs_endpunkt_nimmt_einwilligungsfelder(als_benutzer, welt):
    """Parametergenaue Prüfung: die Allowlist der Verwaltung ist sauber."""
    import inspect

    from diakronos_app.api import website as modul

    for name in ("freigabe_setzen", "beitrag_auf_website", "postfach_speichern",
                 "ansprechpartner_bereiche_setzen", "kategorie_oeffentlich"):
        fn = getattr(modul, name)
        parameter = set(inspect.signature(fn).parameters)
        assert not parameter.intersection(modul.EINWILLIGUNGS_FELDER), (
            f"{name} nimmt ein Einwilligungsfeld an: {parameter}"
        )


# ── P2: Auswahl der Bereiche ───────────────────────────────────────────────


def test_bereiche_lesen_braucht_website_rolle(als_benutzer, welt):
    client = als_benutzer(PERSON_MAIL)
    assert client.get(f"/api/method/{PFAD_BEREICHE_LESEN}").status_code == 403
    verwaltung = als_benutzer(ADMIN_MAIL)
    antwort = verwaltung.get(f"/api/method/{PFAD_BEREICHE_LESEN}")
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()["message"]
    assert {a for a in daten["auswahl"]} == {"dienstbereich", "gruppe"}
    assert [e["funktion"] for e in daten["auswahl"]["dienstbereich"]] == ["musik"]
    assert [e["funktion"] for e in daten["auswahl"]["gruppe"]] == ["chor"]
    assert daten["postfaecher"] == [{"slug": "musik", "bezeichnung": "Musik"}]
    assert daten["einwilligungen_verwaltbar"] is False
    # Keine Einwilligung, keine Personendaten in der Verwaltungsantwort.
    assert "einwilligung" not in str(_schluessel(daten)).replace(
        "einwilligungen_verwaltbar", ""
    )


def test_bereiche_setzen_ersetzt_vollstaendig(als_benutzer, welt):
    client = als_benutzer(ADMIN_MAIL)
    erst = client.post(f"/api/method/{PFAD_BEREICHE_SETZEN}", json={
        "bereiche": [
            {"art": "dienstbereich", "funktion": "musik", "postfach": "musik",
             "bezeichnung": "Kirchenmusik"},
            {"art": "gruppe", "funktion": "chor", "postfach": ""},
        ]
    })
    assert erst.status_code == 200, erst.text
    welt.expire_all()
    zeilen = welt.query(WebsiteAnsprechpartner).order_by(
        WebsiteAnsprechpartner.sortierung
    ).all()
    assert [(z.art, z.funktion) for z in zeilen] == [
        ("dienstbereich", "musik"), ("gruppe", "chor")
    ]
    assert zeilen[0].bezeichnung == "Kirchenmusik"
    assert zeilen[0].postfach == "musik"
    assert zeilen[1].postfach is None

    # Zweiter Aufruf mit EINEM Eintrag: der andere verschwindet (delete-and-replace).
    zweit = client.post(f"/api/method/{PFAD_BEREICHE_SETZEN}", json={
        "bereiche": [{"art": "gruppe", "funktion": "chor", "postfach": ""}]
    })
    assert zweit.status_code == 200, zweit.text
    welt.expire_all()
    zeilen = welt.query(WebsiteAnsprechpartner).all()
    assert [(z.art, z.funktion) for z in zeilen] == [("gruppe", "chor")]

    # Leere Liste schaltet ab.
    leer = client.post(f"/api/method/{PFAD_BEREICHE_SETZEN}",
                       json={"bereiche": []})
    assert leer.status_code == 200, leer.text
    welt.expire_all()
    assert welt.query(WebsiteAnsprechpartner).count() == 0


def test_bereiche_setzen_prueft_eingaben(als_benutzer, welt):
    client = als_benutzer(ADMIN_MAIL)
    faelle = [
        {"bereiche": [{"art": "abteilung", "funktion": "musik"}]},
        {"bereiche": [{"art": "dienstbereich", "funktion": "gibt-es-nicht"}]},
        {"bereiche": [{"art": "dienstbereich", "funktion": "musik", "postfach": "xyz"}]},
        {"bereiche": [
            {"art": "dienstbereich", "funktion": "musik"},
            {"art": "dienstbereich", "funktion": "musik"},
        ]},
        {"bereiche": "keine Liste"},
    ]
    for koerper in faelle:
        antwort = client.post(f"/api/method/{PFAD_BEREICHE_SETZEN}", json=koerper)
        assert antwort.status_code == 417, (koerper, antwort.text)
    welt.expire_all()
    assert welt.query(WebsiteAnsprechpartner).count() == 0, "trotz Fehler geschrieben"


def test_bereiche_setzen_ohne_rolle_ist_403(als_benutzer, welt):
    client = als_benutzer(PERSON_MAIL)
    antwort = client.post(f"/api/method/{PFAD_BEREICHE_SETZEN}",
                          json={"bereiche": []})
    assert antwort.status_code == 403, antwort.text


# ── Route `/website/oeffentlich/ansprechpartner` (CORS-Fassung) ────────────


def test_oeffentliche_route_liefert_dasselbe(gast, welt):
    anna = welt.get(Mitglied, "anna")
    anna.website_einwilligung = True
    welt.add(WebsiteAnsprechpartner(art="dienstbereich", funktion="musik",
                                    bezeichnung="", postfach="musik", sortierung=1))
    welt.commit()
    antwort = gast.get("/website/oeffentlich/ansprechpartner")
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    ergebnis = daten["message"] if isinstance(daten, dict) else daten
    assert ergebnis[0]["name"] == "Anna Beispiel"


# ── Migration: Kette, Kopf, Auf-/Abbau ────────────────────────────────────


def test_migration_ist_ein_kopf_und_laesst_sich_auf_und_ab():
    backend = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "alembic"))
    skript = ScriptDirectory.from_config(cfg)
    # R-1/R-5 bauen auf bs3a auf: genau EIN Kopf, bs3a liegt in seiner Kette.
    koepfe = skript.get_heads()
    assert len(koepfe) == 1
    assert "bs3a_website_einwilligung" in {r.revision for r in skript.iterate_revisions(koepfe[0], "base")}
    rev = skript.get_revision("bs3a_website_einwilligung")
    assert rev is not None
    assert rev.down_revision == "on6_root_benutzer"


# ══════════════════════════════════════════════════════════════════════════
# NACHARBEIT (Datenschutz-Review 08.11.)
#
# Der Befund war der schwerste der Karte: die Einwilligung war nur in den
# EIGENEN Endpunkten geschützt. Der generische Schreibweg
# (`PUT/POST /api/resource`, `frappe.client.insert`, `doc.save()`,
# `db_set`) nahm sie trotzdem an — danach war die Person öffentlich.
# ══════════════════════════════════════════════════════════════════════════

#: Einwilligungsfelder, die auf KEINEM generischen Weg schreibbar sind.
GESPERRTE_FELDER = (
    "website_einwilligung",
    "website_einwilligung_am",
    "website_einwilligung_foto",
    "website_anzeigename",
)

#: Rollen, mit denen der Review den Weg nachgestellt hat. „root“ ist die
#: stärkste Rolle — auch sie darf eine fremde Einwilligung nicht setzen.
ANGREIFER = (
    (ADMIN_MAIL, ("System Manager",)),
    (ADMIN_MAIL, ("Mitgliederadministrator",)),
    ("root@example.org", ("root",)),
)


def _admin(sess, email: str, rollen) -> str:
    _benutzer(sess, email, rollen)
    if sess.get(Mitglied, f"m-{email}") is None:
        _mitglied(sess, f"m-{email}", user=email, vorname="Verwaltung",
                  nachname="Konto")
    sess.commit()
    return email


def _ist_einwilligung(sess, name: str) -> bool:
    """Frisch aus der Datenbank gelesen (kein Sitzungs-Cache)."""
    sess.expire_all()
    zeile = sess.get(Mitglied, name)
    return bool(zeile.website_einwilligung)


def test_kein_generischer_weg_setzt_die_einwilligung(patched_db, fake_redis):
    """PUT/POST resource, client.insert, doc.save, db_set — alle 403.

    Geprüft wird je Weg UND je Rolle (System Manager,
    Mitgliederadministrator, root). Nach jedem Versuch wird frisch gelesen:
    die Einwilligung darf NICHTS geworden sein.
    """
    from fastapi.testclient import TestClient

    from diakronos_app.frappe_compat import api_helpers
    from diakronos_app.api import frappe_core
    from diakronos_app.frappe_compat.query import get_doc
    from diakronos_app.frappe_compat.exceptions import PermissionError
    from diakronos_app.main import app

    sess = patched_db()
    _mitglied(sess, "anna", vorname="Anna", nachname="Beispiel")
    sess.commit()

    for email, rollen in ANGREIFER:
        _admin(sess, email, rollen)

    for email, rollen in ANGREIFER:
        set_user(email)
        sid, csrf = sitzungen.anlegen(email)
        client = TestClient(app)
        with client:
            client.cookies.set("sid", sid)
            client.headers["X-Frappe-CSRF-Token"] = csrf

            # 1) PUT /api/resource/Mitglied/<x>
            antwort = client.put(
                "/api/resource/Mitglied/anna",
                json={"website_einwilligung": True, "website_anzeigename": "Hacked"},
            )
            assert antwort.status_code == 403, (email, "PUT", antwort.text)
            assert not _ist_einwilligung(sess, "anna"), (email, "PUT geschrieben")

            # 2) POST /api/resource/Mitglied (Anlegen mit Einwilligung)
            antwort = client.post(
                "/api/resource/Mitglied",
                json={"vorname": "Neu", "nachname": f"Person-{email}",
                      "website_einwilligung": True},
            )
            assert antwort.status_code == 403, (email, "POST", antwort.text)

        # 3) frappe.client.insert
        with pytest.raises(PermissionError):
            frappe_core.insert({
                "doctype": "Mitglied",
                "vorname": "Neu",
                "nachname": f"Insert-{email}",
                "website_einwilligung": True,
            })

        # 4) Document.save()  (doc.website_einwilligung = True; doc.save())
        dokument = get_doc("Mitglied", "anna")
        dokument.website_einwilligung = True
        with pytest.raises(PermissionError):
            dokument.save()
        sess.rollback()
        assert not _ist_einwilligung(sess, "anna"), (email, "save geschrieben")

        # 5) Document.db_set()
        dokument = get_doc("Mitglied", "anna")
        with pytest.raises(PermissionError):
            dokument.db_set("website_anzeigename", "Hacked")
        sess.rollback()
        sess.expire_all()
        assert not str(sess.get(Mitglied, "anna").website_anzeigename or ""), (
            email, "db_set geschrieben"
        )

        # 6) _create / _update_doc (die Helfer hinter client.insert/update)
        with pytest.raises(PermissionError):
            api_helpers._create("Mitglied", {"vorname": "A", "nachname": "B",
                                             "website_einwilligung": True})
        with pytest.raises(PermissionError):
            api_helpers._update_doc("Mitglied", "anna",
                                    {"website_einwilligung": True})

    sess.expire_all()
    zeile = sess.get(Mitglied, "anna")
    assert bool(zeile.website_einwilligung) is False
    assert not str(zeile.website_anzeigename or "")


def test_das_zeitfenster_gibt_nur_einwilligungsfelder(patched_db):
    """Ein Fenster für ``status`` wäre ein Loch — es wird abgelehnt."""
    from diakronos_app.website import einwilligung as regel

    with pytest.raises(ValueError):
        with regel.zustimmungs_fenster(("website_einwilligung", "status")):
            pass

    with regel.zustimmungs_fenster(("website_einwilligung",)):
        assert "website_einwilligung" in regel.SCHREIBEN_ERLAUBT.get()
    # Nach dem Fenster ist wieder zu (kein Prozess-Schalter).
    assert regel.SCHREIBEN_ERLAUBT.get() == frozenset()


def test_geloeschte_ausgetretene_ausgeschlossene_nie_oeffentlich(gast, welt):
    """Punkt 7: der Status schlägt die Einwilligung — nie öffentlich."""
    from diakronos_app.website import einwilligung as regel

    anna = welt.get(Mitglied, "anna")
    anna.website_einwilligung = True
    welt.add(WebsiteAnsprechpartner(art="dienstbereich", funktion="musik",
                                   bezeichnung="", postfach=None, sortierung=1))
    welt.commit()
    assert len(_oeffentlich(gast).json()["message"]) == 1

    for status in ("ausgeschlossen", "geloescht", "ausgetreten"):
        anna.status = status
        welt.commit()
        welt.expire_all()
        zeile = welt.get(Mitglied, "anna")
        assert not regel.ist_oeffentlich(zeile), status
        assert _oeffentlich(gast).json()["message"] == [], status

    anna.status = "aktiv"
    welt.commit()
    assert len(_oeffentlich(gast).json()["message"]) == 1, "Rückweg kaputt"


def test_dsgvo_loeschung_hebt_die_einwilligung_auf(patched_db):
    """Punkt 2: nach der Anonymisierung ist niemand mehr öffentlich."""
    from diakronos_app import dsgvo_anonymisierung as dsgvo

    sess = patched_db()
    anna = _mitglied(sess, "anna", user=None, vorname="Anna", nachname="Beispiel")
    anna.website_einwilligung = True
    anna.website_einwilligung_foto = True
    anna.website_anzeigename = "Anna B."
    sess.commit()

    werte = dsgvo._mitglied_werte()
    assert werte["website_einwilligung"] is False
    assert werte["website_einwilligung_foto"] is False
    assert werte["website_einwilligung_am"] is None
    assert werte["website_anzeigename"] is None

    # Und die NEUE Zeile trägt diese Werte wirklich (nicht nur das Dict).
    dsgvo._neue_zeile(sess, "anna", "geloescht-abc123")
    sess.commit()
    sess.expire_all()
    neu = sess.get(Mitglied, "geloescht-abc123")
    assert neu is not None
    assert bool(neu.website_einwilligung) is False
    assert bool(neu.website_einwilligung_foto) is False
    assert neu.website_einwilligung_am is None
    assert not str(neu.website_anzeigename or "")

    from diakronos_app.website import einwilligung as regel

    assert not regel.ist_oeffentlich(neu)


def test_personenbild_ohne_cache_und_ohne_exif(gast, welt, tmp_path, monkeypatch):
    """Punkte 5 und 6: Widerruf wirkt sofort, GPS verläßt das Haus nicht."""
    from diakronos_app.settings import settings
    from diakronos_app.website import oeffentlich_auswahl as auswahl

    ordner = tmp_path / "files"
    ordner.mkdir()
    monkeypatch.setattr(settings, "files_dir", str(ordner))

    # JPEG mit EXIF-Block (APP1) und einem GPS-Hinweis darin.
    exif = b"Exif\x00\x00" + b"GPSLatitude=49.14;GPSLongitude=9.21"
    app1 = b"\xff\xe1" + (len(exif) + 2).to_bytes(2, "big") + exif
    # SOI + APP1 + SOF0 (Bildkopfdaten) + SOS + Bilddaten + EOI
    sof = b"\xff\xc0" + (11).to_bytes(2, "big") + b"\x08\x00\x10\x00\x10\x01\x01\x11\x00"
    sos = b"\xff\xda" + (8).to_bytes(2, "big") + b"\x01\x01\x00\x00\x3f\x00"
    jpeg = b"\xff\xd8" + app1 + sof + sos + b"\x12\x34\x56" + b"\xff\xd9"
    assert b"GPSLatitude" in jpeg
    (ordner / "anna-exif.jpg").write_bytes(jpeg)

    anna = welt.get(Mitglied, "anna")
    anna.website_einwilligung = True
    anna.website_einwilligung_foto = True
    anna.foto = "anna-exif.jpg"
    welt.add(WebsiteAnsprechpartner(art="dienstbereich", funktion="musik",
                                    bezeichnung="", postfach=None, sortierung=1))
    welt.commit()

    kennung = auswahl.oeffentliche_kennung("person", "anna")
    antwort = gast.get(f"/website/bild/person/{kennung}")
    assert antwort.status_code == 200, antwort.text
    assert antwort.headers["cache-control"].startswith("no-store"), (
        antwort.headers.get("cache-control")
    )
    assert b"GPSLatitude" not in antwort.content, "EXIF/GPS im ausgelieferten Foto"
    assert antwort.content.startswith(b"\xff\xd8"), "kein gültiges JPEG mehr"
    assert antwort.content.endswith(b"\xff\xd9")
    assert len(antwort.content) < len(jpeg), "Metadatenblock nicht entfernt"

    # Widerruf: derselbe Aufruf liefert sofort 404.
    anna.website_einwilligung_foto = False
    welt.commit()
    assert gast.get(f"/website/bild/person/{kennung}").status_code == 404


def test_ohne_metadaten_laesst_unbekannte_formate_unberuehrt():
    """Unbekannte Typen und kaputte Dateien kommen unverändert zurück."""
    from diakronos_app.gemeinde_logo import ohne_metadaten

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    assert ohne_metadaten(png, "image/png") == png, (
        "kaputte PNG-Struktur darf nicht umgebaut werden (fail open: Eingabe)"
    )
    assert ohne_metadaten(png, "image/gif") == png
    # Kaputtes JPEG (Segmentlänge über das Ende hinaus): Eingabe zurück.
    kaputt = b"\xff\xd8\xff\xe1\xff\xffabc"
    assert ohne_metadaten(kaputt, "image/jpeg") == kaputt
    assert ohne_metadaten(b"", "image/jpeg") == b""


def test_audit_protokolliert_foto_und_anzeigename(als_benutzer, welt):
    """Punkt 9: jede Foto- und Anzeigename-Änderung erzeugt einen Eintrag."""
    from diakronos_app.models.diakonos import DSGVOEinwilligung

    client = als_benutzer(PERSON_MAIL)
    client.post(f"/api/method/{PFAD_EINW_SETZEN}",
                json={"einwilligung": True, "foto": False,
                      "anzeigename": "Anna B."})
    client.post(f"/api/method/{PFAD_EINW_SETZEN}", json={"foto": True})
    client.post(f"/api/method/{PFAD_EINW_SETZEN}", json={"anzeigename": ""})

    welt.expire_all()
    eintraege = welt.query(DSGVOEinwilligung).filter(
        DSGVOEinwilligung.mitglied == "anna"
    ).all()
    paare = sorted((str(e.typ), str(e.aktion)) for e in eintraege)
    assert ("website", "erteilt") in paare, paare
    assert ("website_anzeigename", "gesetzt") in paare, paare
    assert ("website_anzeigename", "entfernt") in paare, paare
    assert ("website_foto", "erteilt") in paare, paare
